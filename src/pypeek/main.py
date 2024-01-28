import os, shutil, time, subprocess, configparser, sys, requests, math, logging, tempfile
from math import atan2, pi
from .shortcut import create_shortcut
from .ffmpeg import get_ffmpeg
from .undo import Undo, ClearSceneCmd, AddSceneItemCmd
from .qrangeslider import QRangeSlider

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

user_path, app_path, logger, capturer = None, None, None, None
__version__ = '2.10.9'

def init():
    global user_path, app_path, logger, capturer
    if user_path is not None:
        return
    
    user_path = os.path.join(os.path.expanduser("~"), ".peek")
    os.makedirs(user_path, exist_ok=True)

    logger = logging.getLogger()
    logging.basicConfig(
        filename=os.path.join(user_path, "peek.log"),
        filemode='w',
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.NOTSET
    )

    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        app_path = sys._MEIPASS
        os.environ["PATH"] = os.pathsep.join([app_path, os.environ["PATH"]])
    elif __file__:
        ffmpeg_local = os.path.abspath(os.path.dirname(__file__))+"/bin"
        if(not shutil.which("ffmpeg") and not shutil.which("ffmpeg", path=ffmpeg_local)): 
            if input("Ffmpeg not found, download? (y/n): ").lower() == "y":
                get_ffmpeg()
            else:
                print("Please install ffmpeg and add it to your PATH. Exiting...")
                sys.exit()

        # add local ffmpeg to path in case its local
        os.environ["PATH"] = os.pathsep.join([ffmpeg_local, os.environ["PATH"]])
        app_path = os.path.abspath(os.path.dirname(__file__))
    
    capturer = Capturer()

class PyPeek(QMainWindow):
    def __init__(self):
        super().__init__()

        capturer.recording_done_signal.connect(self.recording_done)
        capturer.snapshot_done_signal.connect(self.snapshot_done)
        capturer.capture_stopped_signal.connect(self.reset_ui)
        capturer.countdown_signal.connect(self.update_countdown_ui)
        capturer.run_timer_signal.connect(self.update_timer_ui)
        capturer.minimize_to_tray_signal.connect(self.do_minimize_to_tray)
        capturer.hide_app_signal.connect(self.hide)

        self.record_width = 506
        self.record_height = 406
        self.pos_x = 0
        self.pos_y = 0
        self.minimize_to_tray = False
        self.check_update_on_startup = True
        self.needs_restart = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.set_mask)
        self.drag_start_position = None
        self.minimum_header_width = 355
        self.minimum_header_height = 45
        self.minimum_body_height = 100
        self.setStyleSheet("* {font-size: 15px; color: #ddd;} QToolTip { color: #333;}")
        self.block_window_move = False
        self.block_resize_event = False
        self.window_moving = False

        # load settings from json file
        self.load_settings()

        self.header_widget = self.create_header_widget()
        self.body_widget = self.create_body_widget()
        self.settings_widget = self.create_settings_widget()

        # Main vertical layout
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.main_layout.setDirection(QBoxLayout.Direction.BottomToTop)
        self.main_layout.addWidget(self.body_widget)
        self.main_layout.addWidget(self.header_widget)

        # Mainframe
        self.frame = QFrame(self)
        self.frame.setFrameStyle(1)
        self.frame.setStyleSheet("QFrame { border: 3px solid #333; border-radius: 5px;}")
        self.frame.setLayout(self.main_layout)
        def mouseDoubleClickEvent(event):
            if self.block_window_move:
                return
            self.show_info_layout()
            if capturer.fullscreen:
                return
            if self.isMaximized():
                    self.showNormal()
            else:
                self.showMaximized()

        self.frame.mouseDoubleClickEvent = mouseDoubleClickEvent
        self.installEventFilter(self)

        # For win, right bottom corner resize handle
        self.create_grips()

        # tray icon
        self.tray_icon = self.create_tray_icon()

        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("Peek")
        self.resize(self.record_width, self.record_height)
        self.move(self.pos_x, self.pos_y)
        self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
        self.show()

        self.drawover = DrawOver(None, self)

        if capturer.fullscreen: 
            self.set_fullscreen()
        else:
            self.show_info_layout()
        # self.check_update_on_startup and self.check_update()
        self.try_lock()

        # if app is off-screen move to primary display
        def move_primary_display():
            for screen in QApplication.instance().screens():
                # check if position is inside of the any screen geometry
                if self.pos_x >= screen.geometry().topLeft().x() and self.pos_y >= screen.geometry().topLeft().y() and self.pos_x <= screen.geometry().bottomRight().x() and self.pos_y <= screen.geometry().bottomRight().y():
                    return

            self.pos_x = int((QGuiApplication.primaryScreen().size().width() - self.width()) / 2)
            self.pos_y = int((QGuiApplication.primaryScreen().size().height() - self.height()) / 2)
            # reset position and size
            self.move(self.pos_x, self.pos_y)
            self.resize(QGuiApplication.primaryScreen().size() / 2)
                
        QTimer.singleShot(1000, move_primary_display)

    def create_header_widget(self):
        self.snapshot_button = PyPeek.create_button("", f"{app_path}/icon/camera.png", "#0d6efd", "#0b5ed7", "#0a58ca" )
        self.snapshot_button.setToolTip("Take a snapshot")
        self.snapshot_button.clicked.connect(self.snapshot)

        self.record_button = PyPeek.create_button(f"{capturer.v_ext.upper()}", f"{app_path}/icon/video-camera.png", "#0d6efd", "#0b5ed7", "#0a58ca" )
        self.record_button.setFixedWidth(84)
        self.record_button.setToolTip("Start recording")
        self.record_button.clicked.connect(self.record)

        self.stop_button = PyPeek.create_button("", f"{app_path}/icon/stop-fill.png", "#dc3545", "#dd3d4c", "#db2f3f" )
        self.stop_button.setToolTip("Stop")
        self.stop_button.clicked.connect(self.stop_capture)
        self.stop_button.setFixedWidth(114)
        # self.stop_button.setStyleSheet(self.stop_button.styleSheet() + "QPushButton { text-align:left; }")
        self.stop_button.hide()

        self.fullscreen_button = PyPeek.create_button("", f"{app_path}/icon/window.png")
        self.fullscreen_button.setToolTip("Recording window" if not capturer.fullscreen else "Recording fullscreen")
        self.fullscreen_button.clicked.connect(lambda: self.set_fullscreen(not capturer.fullscreen))

        self.format_button = PyPeek.create_button("", "", "#0d6efd", "#0b5ed7", "#0a58ca")
        self.format_button.setStyleSheet( self.format_button.styleSheet() + " QPushButton::menu-indicator {subcontrol-position: center;}" )
        self.format_button.setFixedWidth(30)
        self.menu = QMenu(self.format_button)
        self.menu.setContentsMargins(10, 0, 10, 0)
        group = QActionGroup(self.menu)
       
        action1 = QWidgetAction(self.menu)
        action1.setActionGroup(group)
        self.gif_radio = QRadioButton("gif")
        self.gif_radio.setFixedHeight(25)
        action1.setDefaultWidget(self.gif_radio)
        self.menu.addAction(action1)
        self.gif_radio.setChecked(True)
        self.menu.addSeparator()

        action2 = QWidgetAction(self.menu)
        action2.setActionGroup(group)
        self.mp4_radio = QRadioButton("mp4")
        self.mp4_radio.setFixedHeight(25)
        action2.setDefaultWidget(self.mp4_radio)
        self.menu.addAction(action2)
        self.menu.addSeparator()

        # action3 = QWidgetAction(self.menu)
        # action3.setActionGroup(group)
        # self.webm_radio = QRadioButton("webm")
        # self.webm_radio.setFixedHeight(25)
        # action3.setDefaultWidget(self.webm_radio)
        # self.menu.addAction(action3)
        # self.menu.addSeparator()

        self.format_button.setMenu(self.menu)

        self.gif_radio.toggled.connect(self.update_record_format)
        self.mp4_radio.toggled.connect(self.update_record_format)
        # self.webm_radio.toggled.connect(self.update_record_format)

        # set checked radio button
        if capturer.v_ext == "gif":
            self.gif_radio.setChecked(True)
        elif capturer.v_ext == "mp4":
            self.mp4_radio.setChecked(True)
        elif capturer.v_ext == "webm":
            self.webm_radio.setChecked(True)

        self.record_button_grp = PyPeek.make_group_button(self.record_button, self.format_button)

        self.settings_button = PyPeek.create_button("", f"{app_path}/icon/gear.png")
        self.settings_button.setToolTip("Settings")
        # self.settings_button.setFixedSize(30, 30)
        self.settings_button.clicked.connect(lambda :self.settings_widget.show())

        self.close_button = PyPeek.create_button("", f"{app_path}/icon/x.png")
        self.close_button.setIconSize(QSize(20, 20))
        # self.close_button.setFixedSize(30, 30)
        self.close_button.clicked.connect(self.close_app)

        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(5, 3, 5, 5)
        self.header_layout.setSpacing(5)
        self.header_layout.addWidget(self.record_button_grp)
        self.header_layout.addWidget(self.stop_button)
        self.header_layout.addWidget(self.snapshot_button)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.fullscreen_button)
        self.header_layout.addWidget(self.settings_button)
        self.header_layout.addWidget(self.close_button)

        header_widget = QWidget()
        header_widget.setFixedHeight(40)
        header_widget.setStyleSheet("QWidget { background-color: #333; }")
        header_widget.setLayout(self.header_layout)

        return header_widget

    def create_body_widget(self):
        self.record_area_widget = QWidget()
        self.record_area_widget.setLayout(QVBoxLayout())

        self.info_widget = self.create_info_widget()

        self.body_layout = QStackedLayout()
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.addWidget(self.record_area_widget)
        self.body_layout.addWidget(self.info_widget)
        # self.body_layout.addWidget(self.settings_widget)
        self.body_layout.setCurrentIndex(0)

        body_widget = QWidget()
        body_widget.setLayout(self.body_layout)
        return body_widget

    def create_info_widget(self):
        self.info_size_label = QLabel()
        self.info_size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_shortcut_label = QLabel("Start/Stop: Ctrl+Alt+R")

        self.info_shortcut_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.info_layout = QVBoxLayout()
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(0)
        self.info_layout.addWidget(self.info_size_label)
        # self.info_layout.addWidget(self.info_shortcut_label)
        
        info_widget = QWidget()
        info_widget.setLayout(self.info_layout)
        info_widget.setStyleSheet("QWidget {background-color: rgba(33, 33, 33, 0.3); border: none;}")

        return info_widget

    def create_settings_widget(self):
        self.cursor_widget = PyPeek.create_row_widget("Capture Cursor", "Capture mouse cursor", PyPeek.create_checkbox("", capturer.show_cursor, self.show_cursor ))
        self.hide_app_widget = PyPeek.create_row_widget("Minimize To Tray", "Minimize app to tray icon when recording fullscreen", PyPeek.create_checkbox("", self.minimize_to_tray, self.set_minimize_to_tray ))
        self.framerate_widget = PyPeek.create_row_widget("Frame Rate", "Captured frames per second", PyPeek.create_spinbox(capturer.fps, 1, 60, self.set_framerate ))
        self.img_format_widget = PyPeek.create_row_widget("Image Format", "Set the image format for screenshots", PyPeek.create_radio_button({"png":"PNG", "jpg":"JPG"}, capturer.i_ext, self.set_img_format))
        self.quality_widget = PyPeek.create_row_widget("Capture Quality", "Set the quality of the capture", PyPeek.create_radio_button({"md":"Medium", "hi":"High"}, capturer.quality, self.set_quality))
        self.delay_widget = PyPeek.create_row_widget("Delay Start", "Set the delay before the recording starts", PyPeek.create_spinbox(capturer.delay, 0, 10, self.set_delay_start ))
        self.duration_widget = PyPeek.create_row_widget("Recording Limit", "Stop recording after a given time in seconds (0 = unlimited)", PyPeek.create_spinbox(capturer.duration, 0, 600, self.set_duration ))
        self.update_widget = PyPeek.create_row_widget("Check For Updates", "Check for updates on startup", PyPeek.create_checkbox("", self.check_update_on_startup, self.set_check_update_on_startup))
        self.reset_widget = PyPeek.create_row_widget("Reset And Restart", "Reset all settings and restart the app", PyPeek.create_button("Reset Settings", callback = self.reset_settings))
        self.copyright_widget = PyPeek.create_row_widget("About", f"Peek {__version__} - Cross platform screen recorder", PyPeek.create_hyperlink("Website", "https://github.com/firatkiral/pypeek/wiki"))

        self.settings_layout = QVBoxLayout()
        self.settings_layout.setContentsMargins(20, 10, 20, 10)
        self.settings_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.settings_layout.addWidget(self.cursor_widget)
        self.settings_layout.addWidget(PyPeek.create_h_divider())
        self.settings_layout.addWidget(self.hide_app_widget)
        self.settings_layout.addWidget(PyPeek.create_h_divider())
        self.settings_layout.addWidget(self.framerate_widget)
        self.settings_layout.addWidget(PyPeek.create_h_divider())
        self.settings_layout.addWidget(self.img_format_widget)
        self.settings_layout.addWidget(PyPeek.create_h_divider())
        self.settings_layout.addWidget(self.quality_widget)
        self.settings_layout.addWidget(PyPeek.create_h_divider())
        self.settings_layout.addWidget(self.delay_widget)
        self.settings_layout.addWidget(PyPeek.create_h_divider())
        self.settings_layout.addWidget(self.duration_widget)
        self.settings_layout.addWidget(PyPeek.create_h_divider())
        # self.settings_layout.addWidget(self.update_widget)
        # self.settings_layout.addWidget(PyPeek.create_h_divider())
        self.settings_layout.addWidget(self.reset_widget)
        self.settings_layout.addWidget(PyPeek.create_h_divider())
        self.settings_layout.addWidget(self.copyright_widget)
        
        settings_widget = QWidget()
        settings_widget.setStyleSheet("QWidget {background-color: #3a3a3a; color: #fff; border: none;}")
        settings_widget.setLayout(self.settings_layout)

        scroll_area = QScrollArea()
        scroll_area.setStyleSheet("QScrollArea {background-color: #3a3a3a; border: none;}")
        scroll_area.setWidget(settings_widget)
        scroll_area.setWidgetResizable(True)

        scroll_area.resize(600, 400)
        scroll_area.setWindowModality(Qt.WindowModality.ApplicationModal)
        scroll_area.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        scroll_area.setWindowTitle("Settings")
        scroll_area.setWindowIcon(QIcon(f"{app_path}/icon/peek.png"))

        return scroll_area

    def create_grips(self):
        self.grip_br = QSizeGrip(self)
        self.grip_br.setStyleSheet("background-color: transparent;")
        self.grip_br.resize(20, 20)
        self.grip_br.move(self.frame.width() - 20, self.frame.height() - 20)

        self.grip_bl = QSizeGrip(self)
        self.grip_bl.setStyleSheet("background-color: transparent;")
        self.grip_bl.resize(20, 20)
        self.grip_bl.move(0, self.frame.height() - 20)

        self.grip_tr = QSizeGrip(self)
        self.grip_tr.setStyleSheet("background-color: transparent;")
        self.grip_tr.resize(20, 20)
        self.grip_tr.move(self.frame.width() - 20, 0)
        
        self.grip_tl = QSizeGrip(self)
        self.grip_tl.setStyleSheet("background-color: transparent;")
        self.grip_tl.resize(20, 20)
        self.grip_tl.move(0, 0)

        self.grips = [self.grip_br, self.grip_bl, self.grip_tr, self.grip_tl]
    
    def resize_grips(self):
        self.grip_br.move(self.frame.width() - 20, self.frame.height() - 20)
        self.grip_bl.move(0, self.frame.height() - 20)
        self.grip_tr.move(self.frame.width() - 20, 0)
    
    def show_grips(self):
        for grip in self.grips:
            grip.show()
    
    def hide_grips(self):
        for grip in self.grips:
            grip.hide()
        
    def create_tray_icon(self):
        tray_button = QSystemTrayIcon()
        icon = QIcon(f"{app_path}/icon/peek-recording.png")
        tray_button.setIcon(icon)
        tray_button.setToolTip("Stop Capture")
        tray_button.activated.connect(self.stop_capture)

        # menu = QMenu()
        # menu.addAction("Stop", self.stop_capture)
        # tray_button.setContextMenu(menu)

        return tray_button

    def load_settings(self):
        config_file = os.path.join(user_path, 'peek.cfg')

        config = configparser.ConfigParser()
        config.read(config_file)

        capturer.show_cursor = config.getboolean('capture', 'show_cursor', fallback=True)
        capturer.fullscreen = config.getboolean('capture', 'fullscreen', fallback=True)
        capturer.v_ext = config.get('capture', 'v_ext', fallback='gif')
        capturer.fps = capturer.true_fps = config.getint('capture', 'fps', fallback=15)
        capturer.i_ext = config.get('capture', 'img_format', fallback='jpg')
        capturer.quality = config.get('capture', 'quality', fallback='hi')
        capturer.delay = config.getint('capture', 'delay', fallback=3)
        capturer.duration = config.getint('capture', 'duration', fallback=0)
        self.minimize_to_tray = config.getboolean('capture', 'minimize_to_tray', fallback=False)
        self.record_width = config.getint('capture', 'width', fallback=506)
        self.record_height = config.getint('capture', 'height', fallback=406)
        self.pos_x = config.getint('capture', 'pos_x', fallback=int((QGuiApplication.primaryScreen().size().width() - self.minimum_header_width) / 2))
        self.pos_y = config.getint('capture', 'pos_y', fallback=int(QGuiApplication.primaryScreen().size().height() * .5))
        self.check_update_on_startup = config.getboolean('capture', 'check_update_on_startup', fallback=False)
    
    def save_settings(self):
        config_file = os.path.join(user_path, 'peek.cfg')
        config = configparser.ConfigParser()

        config.read(config_file)

        config['capture'] = {
            'show_cursor': str(capturer.show_cursor),
            'fullscreen': str(capturer.fullscreen),
            'v_ext': capturer.v_ext,
            'fps': str(capturer.fps),
            'img_format': capturer.i_ext,
            'quality': capturer.quality,
            'delay': str(capturer.delay),
            'duration': str(capturer.duration),
            'minimize_to_tray': str(self.minimize_to_tray),
            'width': str(self.record_width),
            'height': str(self.record_height),
            'pos_x': str(int(self.pos_x)),
            'pos_y': str(int(self.pos_y)),
            'check_update_on_startup': str(self.check_update_on_startup),
        }

        with open(config_file, 'w') as config_file:
            config.write(config_file)

    def reset_settings(self):
        config_file = os.path.join(user_path, 'peek.cfg')
        if os.path.exists(config_file):
            os.remove(config_file)
        self.load_settings()
        self.restart()
    
    def restart(self):
        self.needs_restart = True
        self.close_app()
    
    def try_lock(self):
        self.try_lock_thread = TryLock()
        if self.try_lock_thread.try_lock():
            # no other instance running, claer cache dir safely
            capturer.clear_cache_dir()
        else:
            # acquire lock as soon as other app closed so new instances can't remove cache dir
            self.try_lock_thread.start()

    def check_update(self):
        if self.check_update_on_startup:
            self.update_mod = CheckUpdate()
            self.update_mod.update_check_done_signal.connect(self.do_update)
            self.update_mod.start()
    
    def do_update(self, latest_version):
        if latest_version != __version__:
            result, not_update = PyPeek.confirm_dialog("Update Available!", 
            f"\nNew version {latest_version} is available.\n\nDo you want to download it now?", 
            "Don't check for updates on startup")
            if result == QMessageBox.Ok:
                url = QUrl('https://github.com/firatkiral/pypeek/wiki')
                if not QDesktopServices.openUrl(url):
                    QMessageBox.warning(self, 'Open Url', 'Could not open url')
            if not_update:
                self.check_update_on_startup = not not_update
                self.restart()

    def update_record_format(self):
        if self.gif_radio.isChecked():
            capturer.v_ext = "gif"
        elif self.mp4_radio.isChecked():
            capturer.v_ext = "mp4"
        elif self.webm_radio.isChecked():
            capturer.v_ext = "webm"
        self.record_button.setText(f"{capturer.v_ext.upper()}")

    def prepare_capture_ui(self):
        # set active screen
        capturer.active_screen = self.windowHandle().screen()

        self.block_resize_event = True
        if not capturer.fullscreen:
            self.block_window_move = True
        # incase info widget showing
        if self.body_layout.currentIndex() == 1:
            self.set_mask()

        self.stop_button.show()
        self.record_button_grp.hide()
        self.record_button.setDisabled(True)
        self.record_button.setIcon(QIcon(f"{app_path}/icon/in-progress.png"))
        self.record_button.setToolTip("")
        self.record_button.setText("%0")
        self.format_button.hide()
        
        self.hide_grips()
        capturer.pos_x, capturer.pos_y = PyPeek.get_global_position(self.record_area_widget, self.windowHandle().screen())
        capturer.width = self.record_area_widget.width() 
        capturer.height = self.record_area_widget.height()
        if not capturer.fullscreen:
            self.setFixedSize(self.record_width, self.record_height)
            self.snapshot_button.setDisabled(True)
            self.fullscreen_button.setDisabled(True)
            self.settings_button.setDisabled(True)
        else:
            self.setFixedSize(132, self.minimum_header_height)
            self.snapshot_button.hide()
            self.fullscreen_button.hide()
            self.settings_button.hide()
            self.close_button.hide()
        self.block_resize_event = False
            
    def reset_ui(self):
        self.block_resize_event = True
        self.tray_icon.hide()
        self.record_button_grp.show()
        self.stop_button.hide()
        self.record_button.setDisabled(False)
        self.record_button.setText(capturer.v_ext.upper())
        self.record_button.setIcon(QIcon(f"{app_path}/icon/video-camera.png"))
        self.record_button.setToolTip("Start recording")
        self.stop_button.setText("")
        self.format_button.setDisabled(False)
        self.format_button.show()
        self.snapshot_button.setDisabled(False)
        self.fullscreen_button.setDisabled(False)
        self.settings_button.setDisabled(False)
        self.close_button.setDisabled(False)
        self.snapshot_button.show()
        self.fullscreen_button.show()
        self.settings_button.show()
        self.close_button.show()
        self.show_grips()
        if not capturer.fullscreen:
            self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
            self.setMaximumSize(16777215, 16777215) # remove fixed height
            self.resize(self.record_width, self.record_height)
        else:
            self.setFixedWidth(self.minimum_header_width)
        capturer.clear_cache_files()
        self.show()
        self.block_window_move = False
        self.block_resize_event = False

    def update_countdown_ui(self, value):
        self.stop_button.setText(f' {value}')
        if value == 0:
            self.stop_button.setText("")
    
    def update_timer_ui(self, value):
        minutes = value // 60
        seconds = value % 60
        self.stop_button.setText(f'{minutes:01d}:{seconds:02d}')

    def snapshot(self):
        self.prepare_capture_ui()
        capturer.snapshot()
    
    def snapshot_done(self, filepath):
        self.hide()
        self.tray_icon.hide()
        self.drawover.show()
        self.drawover.load_file(filepath)
            
    def record(self):
        self.prepare_capture_ui()
        capturer.record()

    def recording_done(self, cache_folder):
        self.record_button_grp.show()
        self.stop_button.hide()
        self.hide()
        self.tray_icon.hide()
        self.drawover.show()
        self.drawover.load_file(cache_folder)

    def stop_capture(self):
        capturer.stop()

    def set_mask(self):
        if capturer.fullscreen:
            return
        if self.drag_start_position: 
            return
        self.timer.stop()
        self.clearFocus()
        empty_region = QRegion(QRect(QPoint(8,43), self.frame.size() - QSize(16, 51)), QRegion.RegionType.Rectangle)
        region = QRegion(QRect(QPoint(-2,-2), self.frame.size() + QSize(4, 4)), QRegion.RegionType.Rectangle)
        self.setMask(region - empty_region)
        self.body_layout.setCurrentIndex(0)
        if sys.platform == "darwin":
            self.hide()
            self.show()

    def show_info_layout(self):
        self.clearMask()
        self.info_size_label.setText(f"{self.body_widget.width()}x{self.body_widget.height()}")
        self.body_layout.setCurrentIndex(1)
        self.timer.start(2000)

    def close_app(self):
        self.close()
        self.destroy()

    def do_minimize_to_tray(self, show_notification = True):
        if self.minimize_to_tray and sys.platform != "linux":
            self.hide()
            self.tray_icon.show()
            show_notification and self.tray_icon.showMessage("Peek is recording!", "Peek minimized to tray icon and running in background", QSystemTrayIcon.MessageIcon.Information, 6000)

    def set_quality(self, value):
        capturer.quality = value

    def set_img_format(self, value):
        capturer.i_ext = value

    def set_fullscreen(self, value=True):
        self.block_resize_event = True
        if value:
            self.hide_grips()
            self.fullscreen_button.setIcon(QIcon(f"{app_path}/icon/display.png"))
            self.fullscreen_button.setToolTip("Recording fullscreen")
            self.setFixedSize(self.minimum_header_width, self.minimum_header_height) # prevent manual resizing height
            self.clearMask()
        else:
            self.show_grips()
            self.fullscreen_button.setIcon(QIcon(f"{app_path}/icon/window.png"))
            self.fullscreen_button.setToolTip("Recording window")
            self.setMaximumSize(16777215, 16777215) # remove fixed height
            self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
            self.resize(self.record_width, self.record_height)
            self.show_info_layout()
            self.set_mask()
        capturer.fullscreen = value
        self.block_resize_event = False

    def set_framerate(self, value):
        capturer.fps = value
    
    def set_minimize_to_tray(self, value):
        self.minimize_to_tray = value
    
    def set_delay_start(self, value):
        capturer.delay = value
    
    def set_duration(self, value):
        capturer.duration = value
    
    def set_check_update_on_startup(self, value):
        self.check_update_on_startup = value
        if value:
            self.check_update()

    def show_cursor(self, value):
        capturer.show_cursor = value

    def show_settings(self, value):
        if value:
            self.settings_widget.show()
        else:
            self.settings_widget.hide()

    def mousePressEvent(self, event):
        if self.block_window_move:
            return
        
        self.drag_start_position = event.globalPosition()
                
    def mouseMoveEvent(self, event):
        if not self.drag_start_position:
            return
        
        if not self.window_moving:
            self.show_info_layout()
            self.window().windowHandle().startSystemMove()
            self.window_moving = True

        # diff = event.globalPosition() - self.drag_start_position
        # self.move(self.x() + int(diff.x()), self.y() + int(diff.y()))
        # self.drag_start_position = event.globalPosition()

    def mouseReleaseEvent(self, event):
        if self.window_moving:
            self.set_mask()
        
        self.drag_start_position = None
        self.window_moving = False

    def moveEvent(self, event):
        capturer.pos_x, capturer.pos_y = PyPeek.get_global_position(self.record_area_widget, self.windowHandle().screen())
        self.pos_x, self.pos_y = PyPeek.get_global_position(self)

    def resizeEvent(self, event):
        self.frame.setGeometry(0, 0, event.size().width(), event.size().height())
        self.resize_grips()

        if self.block_resize_event:
            return

        self.record_height = event.size().height()
        self.record_width = event.size().width()

        self.show_info_layout()

    def closeEvent(self, event):
        if capturer.isRunning():
            capturer.terminate()
            capturer.clear_cache_files()
        self.save_settings()
        self.settings_widget.close()
        
        self.try_lock_thread.terminate()

    @staticmethod
    def get_global_position(widget, screen=None):
        screen_x = 0
        screen_y = 0
        if screen:
            screen_x = screen.geometry().x()
            screen_y = screen.geometry().y()
        pos = widget.mapToGlobal(QPoint(0, 0))
        return pos.x() - screen_x, pos.y() - screen_y

    @staticmethod
    def create_spinbox(default_value, min_value, max_value, callback):
        framerate_row = QHBoxLayout()
        framerate_row.setSpacing(0)
        framerate_row.setContentsMargins(5, 5, 5, 5)
        framerate_input = QSpinBox()
        framerate_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        framerate_input.setFixedSize(40, 30)
        framerate_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        framerate_input.setRange(min_value, max_value)
        framerate_input.setSingleStep(1)
        framerate_input.setValue(default_value)
        frmaerate_dec_button = QPushButton("-")
        frmaerate_dec_button.setFixedSize(30, 30)
        frmaerate_dec_button.clicked.connect(lambda: framerate_input.stepDown())
        framerate_inc_button = QPushButton("+")
        framerate_inc_button.setFixedSize(30, 30)
        framerate_inc_button.clicked.connect(lambda: framerate_input.stepUp())
        framerate_row.addWidget(framerate_input)
        framerate_row.addWidget(frmaerate_dec_button)
        framerate_row.addWidget(framerate_inc_button)
        framerate_widget = QWidget()
        framerate_widget.setFixedSize(110, 40)
        framerate_widget.setStyleSheet("QWidget { background-color: #333; border-radius: 4px; } QWidget:focus { border: 1px solid #555; } QPushButton { background-color: #333; color: #fff; } QPushButton:hover { background-color: #555; } QPushButton:pressed { background-color: #777; }")
        framerate_widget.setLayout(framerate_row)

        framerate_input.valueChanged.connect(callback)

        return framerate_widget
    
    @staticmethod
    def create_checkbox(text, checked, callback):
        checkbox = QCheckBox(text or "on" if checked else "off" )
        checkbox.setChecked(checked)
        checkbox.setMinimumWidth(40)
        def toggle(_checked):
            checkbox.setText("on" if _checked else "off")
            callback(_checked)

        checkbox.toggled.connect(callback if text else toggle)
        return checkbox
    
    @staticmethod
    def create_radio_button(options, default, callback):
        row = QHBoxLayout()
        row.setSpacing(10)
        row.setContentsMargins(5, 5, 5, 5)
        for option in options.keys():
            text = options[option]
            radio = QRadioButton(text)
            radio.setMinimumWidth(40)
            radio.setChecked(option == default)
            row.addWidget(radio)
            radio.toggled.connect(lambda checked, opt=option: callback(opt))
        
        widget = QWidget()
        widget.setLayout(row)
        return widget

    @staticmethod
    def create_button(text="", icon=None, bgcolor= "#3e3e3e", hovercolor = "#494949", pressedcolor="#434343", callback=None):
        btn = QPushButton(text)
        btn.setStyleSheet(f"QPushButton {{ background-color: {bgcolor}; padding: 5px 10px; border-radius: 4px; border: 1px solid #434343;}} QPushButton:hover {{background-color: {hovercolor};}} QPushButton:pressed {{background-color: {pressedcolor};}}")
        btn.setFixedHeight(30)
        if icon:
            btn.setIcon(QIcon(icon))
            btn.setIconSize(QSize(20, 20))

        if callback:
            btn.clicked.connect(callback)

        return btn
    
    @staticmethod
    def make_group_button(button1, button2):
        group = QHBoxLayout()
        group.setContentsMargins(0, 0, 0, 0)
        group.setSpacing(0)
        group.addWidget(button1)
        group.addWidget(button2)
        button1.setStyleSheet(button1.styleSheet() + "QPushButton {border-top-right-radius: 0; border-bottom-right-radius: 0; border-right: none;}")
        button2.setStyleSheet(button2.styleSheet() + "QPushButton {border-top-left-radius: 0; border-bottom-left-radius: 0; border-left: none;}")
        group_widget = QWidget()
        group_widget.setLayout(group)
        return group_widget

    @staticmethod
    def create_row_widget(header, description, right_widget):
        header_label = QLabel(header)
        header_label.setStyleSheet("QLabel { color: #fff; font-size: 14px; }")
        description_label = QLabel(description)
        description_label.setStyleSheet("QLabel { color: #aaa; font-size: 12px; }")
        
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addStretch()
        left_layout.addWidget(header_label)
        left_layout.addWidget(description_label)
        left_layout.addStretch()
        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        row = QHBoxLayout()
        row.setSpacing(0)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(left_widget)
        row.addStretch()
        row.addWidget(right_widget)

        row_widget = QWidget()
        row_widget.setFixedHeight(80)
        row_widget.setLayout(row)

        return row_widget
    
    @staticmethod
    def create_h_divider(thickness=2):
        divider = QWidget()
        divider.setFixedHeight(thickness)
        divider.setStyleSheet("QWidget { background-color: #333; }")
        return divider
    
    @staticmethod
    def create_v_divider(thickness=2):
        divider = QWidget()
        divider.setFixedWidth(thickness)
        divider.setStyleSheet("QWidget { background-color: #333; }")
        return divider

    @staticmethod
    def create_hyperlink(text, url):
        link = QLabel(f'<a href="{url}"><span style="color:white;">{text}</span></a>')
        link.setStyleSheet("QLabel { color: #aaa; }")
        link.setOpenExternalLinks(True)
        return link
    
    @staticmethod
    def confirm_dialog(title, message, checkbox=False):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText(message)
        msg.setWindowTitle(title)
        msg.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
        if checkbox:
            checkbox = QCheckBox(checkbox) 
            msg.setCheckBox(checkbox)

        return msg.exec(), checkbox.isChecked() if checkbox else False

class DrawOver(QMainWindow):
    def __init__(self, image_path=None, parent=None):
        super().__init__(parent=parent)

        capturer.encoding_done_signal.connect(self.save_video)
        capturer.decoding_done_signal.connect(self.decoding_done)
        capturer.progress_signal.connect(self.update_progress_ui)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._parent = parent
        self.try_lock_thread = None
        self.setWindowTitle("Edit")
        self.setWindowIcon(QIcon(f"{app_path}/icon/peek.png"))
        self.setStyleSheet("* {background-color: #333; color: #fff;}")

        self.pos_x = 0
        self.pos_y = 0
        self.image_width = 0
        self.image_height = 0
        self.new_image_width = 0
        self.new_image_height = 0
        self.reset_parent_onclose = True
        self.last_save_path = ""

        self.is_sequence = False
        self.image_filenames = None
        self.frame_count = 0
        self.duration = 0

        self.image_path = image_path

        # Variables
        self.current_tool = "select"
        self.current_shape = "line"
        self.pen_color = "red"
        self.pen_width = 3
        self.shape_color = "red"
        self.shape_width = 3
        self.text_color = "black"
        self.text_size = 13

        self.load_settings()

        # Undo/Redo
        self.undo_history = Undo()
        undo_shortcut = QShortcut(QKeySequence('Ctrl+Z'), self)
        redo_shortcut = QShortcut(QKeySequence('Shift+Ctrl+Z'), self)
        undo_shortcut.activated.connect(self.undo_history.undo)
        redo_shortcut.activated.connect(self.undo_history.redo)

        self.dragging = False
        self.current_text_item = None
        self.slider = None
        self.current_pen = QPen(QColor(self.pen_color), self.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        self.current_brush = QBrush(QColor(self.pen_color))

        self.items = []
        self.arrow_polygon = QPolygonF([QPointF(2, 0), QPointF(-10, 5), QPointF(-10, -5)])
        
        # Toolbar
        self.toolbar = self.create_toolbar()

        # Canvas
        self.canvas_width = self.image_width
        self.canvas_height = self.image_height

        self.bg_image = self.create_bg_image_widget()
        self.canvas = self.create_canvas()
        self.text_widget = QWidget()
        self.text_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        canvas_layout = QStackedLayout()
        canvas_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        canvas_layout.addWidget(self.bg_image)
        canvas_layout.addWidget(self.canvas)
        canvas_layout.addWidget(self.text_widget)

        self.canvas_widget = QWidget()
        self.canvas_widget.setLayout(canvas_layout)
        self.canvas_widget.resize(self.canvas_width, self.canvas_height)

        self.scene = QGraphicsScene(self)
        self.scene.addWidget(self.canvas_widget)
        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet("QGraphicsView {background-color: #333; color: #fff;}")
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.view.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)

        self.canvas.mousePressEvent = self._mousePressEvent
        self.canvas.mouseMoveEvent = self._mouseMoveEvent
        self.canvas.mouseReleaseEvent = self._mouseReleaseEvent


        # QShortcut(
        #     QKeySequence(Qt.Key.Key_Up), # <---
        #     self.view,
        #     context=Qt.WidgetShortcut,
        #     activated=self.zoom_in,
        # )

        # QShortcut(
        #     QKeySequence(Qt.Key.Key_Down), # <---
        #     self.view,
        #     context=Qt.WidgetShortcut,
        #     activated=self.zoom_out,
        # )

        canvas_margin_layout = QVBoxLayout()
        canvas_margin_layout.setContentsMargins(10,10,10,10)
        canvas_margin_layout.addWidget(self.view)

        open_button = DrawOver.create_button("Open")
        open_button.setFixedWidth(100)
        open_button.clicked.connect(self.open_file)
        new_button = DrawOver.create_button("New")
        new_button.setFixedWidth(100)
        new_button.clicked.connect(self.new_file)
        save_button = DrawOver.create_button("Save", "", "#0d6efd", "#0b5ed7", "#0a58ca")
        save_button.setFixedWidth(100)
        save_button.clicked.connect(self.save_file)
        close_button = DrawOver.create_button("Close")
        close_button.setFixedWidth(100)
        close_button.clicked.connect(self.close)
        save_layout = QHBoxLayout()
        save_layout.setSpacing(10)
        save_layout.setContentsMargins(20,20,20,20)
        save_layout.addWidget(open_button)
        not self._parent and save_layout.addWidget(new_button)
        save_layout.addStretch(1)
        save_layout.addWidget(close_button)
        save_layout.addWidget(save_button)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(DrawOver.create_h_divider(2))
        main_layout.addLayout(canvas_margin_layout, 1)
        main_layout.addWidget(DrawOver.create_h_divider(2))
        main_layout.addWidget(self.create_timeline(), 0)
        main_layout.addLayout(save_layout, 0)

        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        self.move(self.pos_x, self.pos_y)

        if not self.parent():
            self.try_lock()

        self.load_file(self.image_path)
        self.set_tool("select")
        self.setFocus()

        # if app is off-screen move to primary display
        def move_primary_display():
            for screen in QApplication.instance().screens():
                # check if position is inside of the any screen geometry
                if self.pos_x >= screen.geometry().topLeft().x() and self.pos_y >= screen.geometry().topLeft().y() and self.pos_x <= screen.geometry().bottomRight().x() and self.pos_y <= screen.geometry().bottomRight().y():
                    return

            self.pos_x = int((QGuiApplication.primaryScreen().size().width() - self.width()) / 2)
            self.pos_y = int((QGuiApplication.primaryScreen().size().height() - self.height()) / 2)
            # reset position and size
            self.move(self.pos_x, self.pos_y)
                
        QTimer.singleShot(1000, move_primary_display)

    def zoom_in(self):
        scale_tr = QTransform()
        scale_tr.scale(1.1, 1.1)

        tr = self.view.transform() * scale_tr
        self.view.setTransform(tr)

    def zoom_out(self):
        scale_tr = QTransform()
        scale_tr.scale(.9, .9)

        tr = self.view.transform() * scale_tr
        self.view.setTransform(tr)
    
    def reset_zoom(self):
        self.view.resetTransform()
    
    def clear_canvas(self):
        self.undo_history.push(ClearSceneCmd(self))

    def create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(50, 30))
        toolbar.setStyleSheet("""
        QToolBar {
            background-color: #333; 
            color:#aaa; 
            spacing: 3px; 
            border: none;
        } 
        QToolBar #qt_toolbar_ext_button {
        }
        QMenu {
            background-color: #333;
        }
        QMenu::item {
            color: #aaa;
            width: 60px;
            text-align: center;
        }
        QMenu::item:selected {
            background-color: #444;
            color: #fff;
        }
        QMenu::icon {
            position: absolute;
            left: 20px;
        }
        QToolBar::separator {
            background-color: #444; 
            width: 1px;
        } 
        QToolButton {
            background-color: #333; 
            color: #aaa; 
            border: none; 
            padding: 5px; 
            border-top-left-radius: 5px;
            border-top-right-radius: 5px;
            margin-top: 5px;
        } 
        QToolButton:hover {
                background-color: #464646; 
                color: #fff;
        } 
        QToolButton:pressed {
            background-color: #484848; 
            color: #fff;
        } 
        QToolButton:checked {
            background-color: #444; 
            color: #fff;
        } 
        QToolButton:disabled {
            background-color: #333; 
            color: #555;
        }
        QToolButton::menu-button {
            width: 16px;
        }
        QToolButton::menu-arrow {
            width: 14px; height: 14px;
        }
        QToolButton::menu-arrow:open {
            top: 1px; left: 1px; /* shift it a bit */
        }
        """)

        tool_button_group = QActionGroup(self)

        # create grab tool
        self.select_tool = QAction(QIcon(f"{app_path}/icon/cursor-light.png"), "", self)
        self.select_tool.setToolTip("Select Tool")
        self.select_tool.setCheckable(True)
        tool_button_group.addAction(self.select_tool)
        self.select_tool.triggered.connect(lambda: self.set_tool("select"))
        toolbar.addAction(self.select_tool)
        
        self.pen_tool = QAction(QIcon(f"{app_path}/icon/pencil.png"), "", self)
        self.pen_tool.setToolTip("Pen Tool")
        self.pen_tool.setCheckable(True)
        tool_button_group.addAction(self.pen_tool)
        self.pen_tool.triggered.connect(lambda: self.set_tool("pen"))
        toolbar.addAction(self.pen_tool)

        self.shape_tool = self.create_shape_tool()
        self.shape_tool.setToolTip("Shape Tool")
        self.shape_tool.setCheckable(True)
        tool_button_group.addAction(self.shape_tool)
        self.shape_tool.triggered.connect(lambda: self.set_tool(self.current_shape))
        toolbar.addAction(self.shape_tool)
        shape_tool_button = toolbar.widgetForAction(self.shape_tool)
        shape_tool_button.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        shape_tool_button.setStyleSheet("QToolButton::menu-button { background-color: transparent; color: #aaa;}" )

        self.text_tool = QAction(QIcon(f"{app_path}/icon/fonts.png"), "", self)
        self.text_tool.setToolTip("Text Tool")
        self.text_tool.setCheckable(True)
        tool_button_group.addAction(self.text_tool)
        self.text_tool.triggered.connect(lambda: self.set_tool("text"))
        toolbar.addAction(self.text_tool)

        self.clear_tool = QAction(QIcon(f"{app_path}/icon/broom.png"), "", self)
        self.clear_tool.setToolTip("Clear Canvas")
        toolbar.addAction(self.clear_tool)
        self.clear_tool.triggered.connect(self.clear_canvas)

        # add separator
        toolbar.addSeparator()

        # Set up the color picker
        self.color_picker = self.create_color_tool()
        self.color_picker.setToolTip("Color Picker")
        toolbar.addAction(self.color_picker)

        # add separator
        self.separator1 = toolbar.addSeparator()

        # set up size picker
        self.width_tool = self.create_width_tool()
        self.width_tool.setToolTip("Brush / Text Size")
        toolbar.addAction(self.width_tool)

        # add separator
        self.separator2 = toolbar.addSeparator()

        # add zoom tools
        self.zoom_in_tool = QAction(QIcon(f"{app_path}/icon/zoom-in.png"), "", self)
        self.zoom_in_tool.setToolTip("Zoom In")
        self.zoom_in_tool.triggered.connect(self.zoom_in)
        toolbar.addAction(self.zoom_in_tool)

        self.zoom_out_tool = QAction(QIcon(f"{app_path}/icon/zoom-out.png"), "", self)
        self.zoom_out_tool.setToolTip("Zoom Out")
        self.zoom_out_tool.triggered.connect(self.zoom_out)
        toolbar.addAction(self.zoom_out_tool)

        self.reset_zoom_tool = QAction(QIcon(f"{app_path}/icon/zoom-reset.png"), "", self)
        self.reset_zoom_tool.setToolTip("Reset Zoom")
        self.reset_zoom_tool.triggered.connect(self.reset_zoom)
        toolbar.addAction(self.reset_zoom_tool)

        # toolbar_layout = QHBoxLayout()
        # toolbar_layout.addWidget(toolbar)

        # toolbar_widget = QWidget()
        # toolbar_widget.setObjectName("toolbar")
        # toolbar_widget.setStyleSheet("QWidget#toolbar {background-color: #333; color: #aaa;}")
        # toolbar_widget.setLayout(toolbar_layout)

        return toolbar
    
    def create_bg_image_widget(self):
        bg_image = QLabel()
        bg_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bg_image.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        return bg_image

    def update_bg_image(self, image_filename):
        self.bg_pixmap = QPixmap(os.path.join(self.out_path, image_filename))
        self.bg_image.setPixmap(self.bg_pixmap)

    def create_canvas(self):
        canvas = QLabel()
        canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.pixmap = QPixmap(self.canvas_width, self.canvas_height)
        self.pixmap.fill(Qt.GlobalColor.transparent)
        canvas.setPixmap(self.pixmap)

        return canvas

    def create_timeline(self):
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 10)
        self.slider.valueChanged.connect(lambda x: (
            timeline.blockSignals(True),
            timeline.setCurrentTime((x - self.slider.minimum()) * (1000/capturer.true_fps)),
            (timeline.stop(), timeline.resume()) if timeline.state() == QTimeLine.State.Running else None, timeline.blockSignals(False),
            self.update_bg_image(self.image_filenames[self.slider.value()])
            )
        )

        timeline = QTimeLine(10, parent=self)
        timeline.setFrameRange(0, 10)
        timeline.setUpdateInterval(1000.0/capturer.true_fps)
        timeline.setLoopCount(1)
        timeline.setEasingCurve(QEasingCurve.Linear)
        timeline.frameChanged.connect(lambda x: (
            self.slider.blockSignals(True),
            self.slider.setValue(x),
            self.update_bg_image(self.image_filenames[self.slider.value()]),
            self.slider.blockSignals(False),
            ))
        timeline.stateChanged.connect(lambda x: (
            play_button.hide() if x == QTimeLine.State.Running else play_button.show(),
            pause_button.show() if x == QTimeLine.State.Running else pause_button.hide(),
        ))

        play_button = DrawOver.create_button("", f"{app_path}/icon/play-fill.png", "#0d6efd", "#0b5ed7", "#0a58ca")
        play_button.setFixedSize(50, 40)
        play_button.clicked.connect(lambda: (
            timeline.start() if self.slider.value() == self.slider.maximum() else timeline.resume(),
            play_button.hide(),
            pause_button.show()))

        pause_button = DrawOver.create_button("", f"{app_path}/icon/pause.png", "#0d6efd", "#0b5ed7", "#0a58ca")
        pause_button.setFixedSize(50, 40)
        pause_button.clicked.connect(lambda: (timeline.setPaused(True)))
        pause_button.hide()

        stop_button = DrawOver.create_button("", f"{app_path}/icon/stop-fill.png")
        stop_button.setFixedSize(50, 40)
        stop_button.clicked.connect(lambda: (timeline.stop(), timeline.setCurrentTime(0)))

        button_layout = QHBoxLayout()
        button_layout.setSpacing(2)
        button_layout.addWidget(play_button)
        button_layout.addWidget(pause_button)
        # button_layout.addWidget(stop_button)

        range_slider = QRangeSlider()
        range_slider.setRange(0, 10)
        range_slider.startValueChanged.connect(lambda x: (
            self.slider.setMinimum(x),
            self.slider.setValue(x),
            timeline.blockSignals(True),
            timeline.setCurrentTime((self.slider.value() - x) * (1000/capturer.true_fps)),
            timeline.blockSignals(False),
            timeline.setFrameRange(x, range_slider.end()),
            timeline.setDuration((range_slider.end() - x) * (1000/capturer.true_fps))
            ))
        range_slider.endValueChanged.connect(lambda x: (
            self.slider.setMaximum(x),
            self.slider.setValue(x),
            timeline.setFrameRange(range_slider.start(), x),
            timeline.setDuration((x - range_slider.start()) * (1000/capturer.true_fps))
            ))

        range_layout = QVBoxLayout()
        range_layout.setSpacing(4)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.addWidget(self.slider)
        range_layout.addWidget(range_slider)

        slider_layout = QHBoxLayout()
        slider_layout.setSpacing(10)
        slider_layout.addLayout(button_layout, 0)
        slider_layout.addLayout(range_layout, 1)

        layout = QVBoxLayout()
        layout.setSpacing(4)
        layout.addLayout(slider_layout)
        timeline_widget = QWidget()
        # timeline_widget.setStyleSheet( "QWidget {background-color: #2a2a2a; border-radius: 5px; padding: 5px;}")
        timeline_widget.setLayout(layout)
        self.timeline = timeline

        def update():
            timeline_widget.setVisible(self.is_sequence)
            if self.is_sequence:
                timeline.blockSignals(True)
                self.slider.blockSignals(True)
                range_slider.blockSignals(True)

                self.slider.setRange(0, self.frame_count - 1)
                self.slider.setValue(0)

                timeline.setDuration(self.duration)
                timeline.setFrameRange(0, self.frame_count - 1)
                timeline.setUpdateInterval(1000.0/capturer.true_fps)
                timeline.setCurrentTime(0)

                range_slider.setMax(self.frame_count - 1)
                range_slider.setRange(0, self.frame_count - 1)

                self.update_bg_image(self.image_filenames[0])

                timeline.blockSignals(False)
                self.slider.blockSignals(False)
                range_slider.blockSignals(False)

        timeline.update = update

        return timeline_widget

    def create_color_tool(self):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu {background-color: #333; color: #fff; border-radius: 5px; padding: 5px;}")
        # menu.setContentsMargins(10, 5, 10, 5)

        icon_widget = QPushButton()
        icon_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        icon_widget.setStyleSheet("QPushButton {border-radius: 5px; Background-color: transparent; color: #ddd;}")
        icon_widget.setIcon(QIcon(f"{app_path}/icon/palette.png"))
        icon_widget.setIconSize(QSize(30, 30))

        self.color_menu_button = QPushButton("", self)
        self.color_menu_button.setStyleSheet(f"QPushButton {{background-color: {self.pen_color}; border-radius: 3px;}} QPushButton::menu-indicator {{image: none;}}")
        self.color_menu_button.setFixedSize(24, 24)
        self.color_menu_button.setMenu(menu)

        action = QWidgetAction(menu)
        action_layout = QGridLayout()
        action_layout.setHorizontalSpacing(8)
        action_layout.setVerticalSpacing(16)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_widget = QWidget()
        action_widget.setLayout(action_layout)
        action.setDefaultWidget(action_widget)

        menu.addAction(action)

        def clicked(_color):
            _color = _color if _color else QColorDialog.getColor("white", self).toHsv().name()
            self.pick_color(_color)
            menu.close()

        for i, color in enumerate(['red', 'limegreen', 'blue', 'yellow', 'cyan', 'magenta', 'white', 'black', 'picker']):
            color_button = QPushButton()
            color_button.setFixedSize(14, 14)
            color_button.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
            action_layout.addWidget(color_button, int(i/3), i%3)
            if color == 'picker':
                color_button.setIcon(QIcon(f"{app_path}/icon/eyedropper.png"))
                color_button.setContentsMargins(0, 0, 0, 0)
                color_button.setStyleSheet(f"background-color: transparent;")
                color = None
            color_button.clicked.connect(lambda *args, _color=color: clicked(_color))

        hbox = QHBoxLayout()
        hbox.setSpacing(3)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addStretch()
        hbox.addWidget(icon_widget)
        hbox.addWidget(self.color_menu_button)
        hbox.addStretch()

        color_widget = QWidget()
        color_widget.setFixedWidth(80)
        color_widget.setLayout(hbox)

        color_picker_action = QWidgetAction(self)
        color_picker_action.setDefaultWidget(color_widget)

        return color_picker_action

    def create_width_tool(self):
        icon_widget = QPushButton()
        icon_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        icon_widget.setStyleSheet("QPushButton {border-radius: 5px; Background-color: transparent; color: #ddd;}")
        icon_widget.setIcon(QIcon(f"{app_path}/icon/line-width.png"))
        icon_widget.setIconSize(QSize(30, 30))

        self.width_spinner = QSpinBox()
        self.width_spinner.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.width_spinner.setFixedSize(50, 30)
        self.width_spinner.setRange(0, 100)
        self.width_spinner.setSingleStep(1)
        self.width_spinner.setValue(3)
        self.width_spinner.setStyleSheet('background-color: #333;')
        self.width_spinner.valueChanged.connect(lambda : self.set_brush_width(self.width_spinner.value()))

        hbox = QHBoxLayout()
        hbox.setSpacing(0)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addStretch()
        hbox.addWidget(icon_widget)
        hbox.addWidget(self.width_spinner)
        hbox.addStretch()

        width_widget = QWidget()
        width_widget.setFixedWidth(100)
        width_widget.setLayout(hbox)

        width_widget_action = QWidgetAction(self)
        width_widget_action.setDefaultWidget(width_widget)
        
        return width_widget_action

    def create_shape_tool(self):
        shapes = {'line':'slash-lg', 'arrow':'arrow-up-right', 'double_arrow':'arrows-angle-expand', 'rectangle':'square', 'ellipse':'circle' }
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        menu.setStyleSheet("QMenu {background-color: #333; color: #fff; border-radius: 5px; padding: 5px;}")
        menu.setContentsMargins(0, 5, 0, 5)

        menu_action = QAction(QIcon(f"{app_path}/icon/{shapes[self.current_shape]}"), "", self)
        menu_action.setMenu(menu)

        action = QWidgetAction(menu)
        action_layout = QVBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(15)
        action_widget = QWidget()
        action_widget.setLayout(action_layout)
        action.setDefaultWidget(action_widget)

        menu.addAction(action)

        def clicked(_shape, _icon):
            self.current_shape = _shape
            menu_action.setIcon(QIcon(f"{app_path}/icon/{_icon}.png"))
            self.set_tool(_shape)
            menu.close()

        for shape, icon in shapes.items():
            shape_button = QPushButton(QIcon(f"{app_path}/icon/{icon}.png"), "")
            shape_button.setFixedSize(54, 34)
            shape_button.setIconSize(QSize(18, 18))
            shape_button.setStyleSheet("QPushButton {background-color: transparent; } QPushButton:hover {background-color: #444; }")
            shape_button.clicked.connect(lambda *args, _shape=shape, _icon=icon: clicked(_shape, _icon))
            action_layout.addWidget(shape_button)

        return menu_action

    def set_tool(self, tool):
        if tool == "select":
            self.set_select_tool()
        elif tool == "pen":
            self.set_pen_tool()
        elif tool == "line":
            self.set_line_tool()
        elif tool == "arrow":
            self.set_arrow_tool()
        elif tool == "double_arrow":
            self.set_double_arrow_tool()
        elif tool == "rectangle":
            self.set_rectangle_tool()
        elif tool == "ellipse":
            self.set_ellipse_tool()
        elif tool == "text":
            self.set_text_tool()
        else:
            self.set_select_tool()

        self.update_brush_params()
    
    def set_select_tool(self):
        self.current_tool = "select"
        self.select_tool.setChecked(True)

    def set_pen_tool(self):
        self.current_tool = "pen"
        self.pen_tool.setChecked(True)

    def set_line_tool(self):
        self.current_tool = "line"
        self.shape_tool.setChecked(True)
    
    def set_arrow_tool(self):
        self.current_tool = "arrow"
        self.shape_tool.setChecked(True)

    def set_double_arrow_tool(self):
        self.current_tool = "double_arrow"
        self.shape_tool.setChecked(True)
    
    def set_rectangle_tool(self):
        self.current_tool = "rectangle"
        self.shape_tool.setChecked(True)
    
    def set_ellipse_tool(self):
        self.current_tool = "ellipse"
        self.shape_tool.setChecked(True)

    def set_text_tool(self):
        self.current_tool = "text"
        self.text_tool.setChecked(True)

    def update_brush_params(self):
        color = None
        width = None
        if self.current_tool == "line" or self.current_tool == "arrow" or self.current_tool == "double_arrow" or self.current_tool == "rectangle" or self.current_tool == "ellipse":
            color = self.shape_color
            width = self.shape_width
        elif self.current_tool == "text":
            color = self.text_color
            width = self.text_size
        else:
            color = self.pen_color
            width = self.pen_width

        self.current_pen.setColor(QColor(color))
        self.current_pen.setWidth(width)
        self.current_brush.setColor(QColor(color))
        self.width_spinner.blockSignals(True)
        self.width_spinner.setValue(width)
        self.width_spinner.blockSignals(False)
        self.color_menu_button.setStyleSheet(f"QPushButton {{background-color: {color};border-radius: 3px;}} QPushButton::menu-indicator {{image: none;}}")

        if self.current_tool == "select":
            self.color_picker.setVisible(False)
            self.width_tool.setVisible(False)
            self.separator1.setVisible(False)
            self.separator2.setVisible(False)
        else:
            self.color_picker.setVisible(True)
            self.width_tool.setVisible(True)
            self.separator1.setVisible(True)
            self.separator2.setVisible(True)
    
    def pick_color(self, color):
        if self.current_tool == "line" or self.current_tool == "arrow" or self.current_tool == "double_arrow" or self.current_tool == "rectangle" or self.current_tool == "ellipse":
            self.shape_color = color
        elif self.current_tool == "text":
            self.text_color = color
        else:
            self.pen_color = color
        self.update_brush_params()

    def set_brush_width(self, width):
        if self.current_tool == "line" or self.current_tool == "arrow" or self.current_tool == "double_arrow" or self.current_tool == "rectangle" or self.current_tool == "ellipse":
            self.shape_width = width
        elif self.current_tool == "text":
            self.text_size = width
        else:
            self.pen_width = width
        self.update_brush_params()

    def show_progress(self):
        self.progress = QProgressDialog("Processing... 0%", "Cancel", 0, 100, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.setAutoClose(False)

    def update_progress_ui(self, progress):
        if self.progress.wasCanceled():
            capturer.terminate()
            return

        self.progress.setLabelText(f"Processing... {progress}%")
        self.progress.setValue(int(progress))
        if int(progress) == 100:
            self.progress.close()
    
    def decoding_done(self, filepath):
        self.progress.close()
        if filepath:
            self.load_file(filepath)

    def save_video(self, filepath):
        if filepath:
            filename = "peek"
            ext = os.path.splitext(os.path.basename(filepath))[1]
            number = 1

            while os.path.isfile(os.path.join(self.last_save_path, f"peek_{str(number)}{ext}")):
                number += 1

            filename = f"peek_{str(number)}{ext}"
            self.last_save_path = self.last_save_path if os.path.exists(self.last_save_path) else os.path.expanduser("~")
            new_filepath = QFileDialog.getSaveFileName(self, "Save Video", os.path.join(self.last_save_path, filename), f"Videos (*.{capturer.v_ext})")
            
            if new_filepath[0]:
                try:
                    shutil.move(filepath, new_filepath[0])
                    self.last_save_path = os.path.dirname(new_filepath[0])
                except Exception as e:
                    logger.error(e)

    def save_snapshot(self, encode_options):
        if encode_options and encode_options["drawover_image_path"]:
            self.image_path = capturer.snapshot_drawover(encode_options["drawover_image_path"])
        
        filename = "peek"
        ext = os.path.splitext(os.path.basename(self.image_path))[1]
        number = 1
        while os.path.isfile(os.path.join(self.last_save_path, f"peek_{str(number)}{ext}")):
            number += 1

        filename = f"peek_{str(number)}{ext}"
        self.last_save_path = self.last_save_path if os.path.exists(self.last_save_path) else os.path.expanduser("~")
        new_filepath = QFileDialog.getSaveFileName(self, "Save Image", os.path.join(self.last_save_path, filename), f"Images (*.{capturer.i_ext})")
        
        if new_filepath[0]:
            try:
                shutil.copy(self.image_path, new_filepath[0])
                self.last_save_path = os.path.dirname(new_filepath[0])
            except Exception as e:
                logger.error(e)

    def save_file(self):
        encode_options = {"drawover_image_path": None, "drawover_range":None}
        if len(self.items) > 0:
            range = (self.slider.minimum(), self.slider.maximum() + 1) if self.slider else None
            drawover_image_path = f'{capturer.current_cache_folder}/peek_{capturer.UID}_drawover.png'
            os.makedirs(capturer.current_cache_folder, exist_ok=True)
            encode_options = {"drawover_image_path": drawover_image_path, "drawover_range":range }
            self.canvas_widget.hide()
            pixmap = QPixmap(self.image_width, self.image_height)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing,True)
            self.scene.render(painter, QRectF(), QRectF(0, 0, self.image_width, self.image_height), Qt.KeepAspectRatio)
            painter.end()
            self.canvas_widget.show()
            pixmap.save(drawover_image_path, "png", 100)

        if self.is_sequence:
            self.show_progress()
            encode_options["drawover_range"] = (self.slider.minimum(), self.slider.maximum() + 1)
            capturer.encode(encode_options)
        else:
            self.save_snapshot(encode_options)

    def load_file(self, image_path=None):
        self.clear_canvas()
        self.view.setTransform(QTransform())
        
        if image_path and os.path.isfile(image_path):
            ext = os.path.splitext(image_path)[1]

            if ext in [".gif", ".mp4"]:
                self.show_progress()
                capturer.decode({"image_path":image_path})
                return
            elif ext in [".jpg", ".jpeg", ".png"]:
                pass
            else:
                logger.error(f"Unsupported file format: {ext}")
                return

        if image_path and os.path.isdir(image_path):
            self.out_path = image_path
            image_dir = QDir(image_path)
            self.image_filenames = image_dir.entryList(['*.jpg'], QDir.Filter.Files, QDir.SortFlag.Name)
            self.is_sequence = True
            self.bg_pixmap = QPixmap(os.path.join(image_path, self.image_filenames[0]))
            self.frame_count = len(self.image_filenames)
            self.duration = (float(self.frame_count) / capturer.true_fps)*1000
        elif image_path and os.path.isfile(image_path):
            self.is_sequence = False
            self.bg_pixmap = QPixmap(image_path)
            self.out_path = os.path.dirname(image_path)
        else:
            self.is_sequence = False
            self.bg_pixmap = QPixmap(self.new_image_width, self.new_image_height)
            self.bg_pixmap.fill(Qt.GlobalColor.white)
            self.image_path = f'{capturer.current_cache_folder}/peek_{capturer.UID}.{capturer.i_ext}'
            os.makedirs(capturer.current_cache_folder, exist_ok=True)
            self.bg_pixmap.save(self.image_path, capturer.i_ext, 100)

        self.timeline.update()
        self.bg_image.setPixmap(self.bg_pixmap)

        self.canvas_width = self.image_width = self.bg_pixmap.width()
        self.canvas_height = self.image_height = self.bg_pixmap.height()

        self.canvas_widget.resize(self.canvas_width, self.canvas_height)
        self.scene.setSceneRect(0, 0, self.canvas_width, self.canvas_height)

        window_width = self.canvas_width + 35
        window_height = self.canvas_height + 220 if self.is_sequence else self.canvas_height + 160

        # this part only works if window showing
        try:
            screen_size = self.windowHandle().screen().size()

            pref_width = screen_size.width() * 0.8
            pref_height = screen_size.height() * 0.8
            if window_width > pref_width:
                window_width = pref_width
            if window_height > pref_height:
                window_height = pref_height

            self.reset_zoom()
            self.resize(window_width, window_height)
            self.pos_x = ((screen_size.width() - self.width()) / 2 )
            self.pos_y = ((screen_size.height() - self.height()) / 2)

            self.move(self.pos_x, self.pos_y)

        except Exception as e:
            logger.error(e)
    
    def open_file(self):
        image_path = QFileDialog.getOpenFileName(self, "Open File", "", "Images (*.png *.jpg *.jpeg *.gif *.mp4)")[0]
        self.load_file(image_path) 

    def new_file(self):
        # create dialog with image width and image height inputs
        dialog = QDialog(self)
        dialog.setWindowTitle("New File")
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        dialog.setFixedSize(300, 150)
        dialog.setStyleSheet("QDialog {background-color: #333; color: #fff; border-radius: 5px; padding: 5px;}")
        dialog.setContentsMargins(10, 10, 10, 10)

        width_label = QLabel("Width")
        width_label.setStyleSheet("QLabel {color: #fff;}")
        width_input = QLineEdit()
        width_input.setValidator(QIntValidator(1, 99999))
        width_input.setText(str(self.image_width))
        width_input.setStyleSheet("QLineEdit {background-color: #333; color: #fff; border-radius: 3px;}")
        width_input.setFixedWidth(100)
        width_input.setFixedHeight(30)

        height_label = QLabel("Height")
        height_label.setStyleSheet("QLabel {color: #fff;}")
        height_input = QLineEdit()
        height_input.setValidator(QIntValidator(1, 99999))
        height_input.setText(str(self.image_height))
        height_input.setStyleSheet("QLineEdit {background-color: #333; color: #fff; border-radius: 3px;}")
        height_input.setFixedWidth(100)
        height_input.setFixedHeight(30)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.setStyleSheet("QDialogButtonBox {background-color: #333; color: #fff; border-radius: 3px;}")
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        layout = QGridLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(width_label, 0, 0)
        layout.addWidget(width_input, 0, 1)
        layout.addWidget(height_label, 1, 0)
        layout.addWidget(height_input, 1, 1)
        layout.addWidget(button_box, 2, 0, 1, 2)

        dialog.setLayout(layout)

        if dialog.exec_():
            self.new_image_width = int(width_input.text())
            self.new_image_height = int(height_input.text())
            self.load_file()

    def load_settings(self):
        config_file = os.path.join(user_path, 'peek.cfg')

        config = configparser.ConfigParser()
        config.read(config_file)

        capturer.fullscreen = config.getboolean('capture', 'fullscreen', fallback=True)
        capturer.v_ext = config.get('capture', 'v_ext', fallback='gif')
        capturer.fps = capturer.true_fps = config.getint('capture', 'fps', fallback=15)
        capturer.i_ext = config.get('capture', 'img_format', fallback='jpg')
        capturer.quality = config.get('capture', 'quality', fallback='hi')
        capturer.delay = config.getint('capture', 'delay', fallback=3)
        capturer.duration = config.getint('capture', 'duration', fallback=0)
        self.pos_x = config.getint('drawover', 'pos_x', fallback=int((QGuiApplication.primaryScreen().size().width() - self.image_width) / 2))
        self.pos_y = config.getint('drawover', 'pos_y', fallback=int(QGuiApplication.primaryScreen().size().height() * .5))
        self.last_save_path = config.get('drawover', 'last_save_path', fallback=os.path.expanduser("~"))
        self.new_image_width = config.getint('drawover', 'new_image_width', fallback=800)
        self.new_image_height = config.getint('drawover', 'new_image_height', fallback=600)
        self.image_width = self.new_image_width
        self.image_height = self.new_image_height
        self.current_tool = config.get('drawover', 'current_color', fallback='select')
        self.current_shape = config.get('drawover', 'current_shape', fallback='line')
        self.pen_color = config.get('drawover', 'pen_color', fallback='red')
        self.pen_width = config.getint('drawover', 'pen_width', fallback=3)
        self.shape_color = config.get('drawover', 'shape_color', fallback='red')
        self.shape_width = config.getint('drawover', 'shape_width', fallback=3)
        self.text_color = config.get('drawover', 'text_color', fallback='black')
        self.text_size = config.getint('drawover', 'text_size', fallback=13)
    
    def save_settings(self):
        config_file = os.path.join(user_path, 'peek.cfg')
        config = configparser.ConfigParser()

        config.read(config_file)

        config['drawover'] = {
            'last_save_path': self.last_save_path,
            'pos_x': str(int(self.pos_x)),
            'pos_y': str(int(self.pos_y)),
            'new_image_width': str(int(self.new_image_width)),
            'new_image_height': str(int(self.new_image_height)),
            'current_tool': self.current_tool,
            'current_shape': self.current_shape,
            'pen_color': self.pen_color,
            'pen_width': str(self.pen_width),
            'shape_color': self.shape_color,
            'shape_width': str(self.shape_width),
            'text_color': self.text_color,
            'text_size': str(self.text_size)
        }

        with open(config_file, 'w') as config_file:
            config.write(config_file)

    def _mousePressEvent(self, e):
        self.start_point = e.position()
        if self.start_point.x() < 0 or self.start_point.y() < 0 or self.start_point.x() > self.canvas.width() or self.start_point.y() > self.canvas.height():
            return
        self.dragging = True
        if self.current_tool == "select":
            self.select_start_point = e.position()
            QApplication.setOverrideCursor(Qt.CursorShape.ClosedHandCursor)
        if self.current_tool == "pen":
            self.current_path = QPainterPath()
            self.current_path.moveTo(self.start_point)
            self.current_path_item = QGraphicsPathItem(self.current_path)
            self.current_path_item.setPen(self.current_pen)
            self.scene.addItem(self.current_path_item)
        if self.current_tool == "line":
            self.current_line_item = QGraphicsLineItem()
            self.current_line_item.setPen(self.current_pen)
            self.current_line_item.setLine(self.start_point.x(), self.start_point.y(), self.start_point.x(), self.start_point.y())
            self.scene.addItem(self.current_line_item)
        if self.current_tool == "arrow":
            line_item = QGraphicsLineItem()
            line_item.setPen(self.current_pen)
            line_item.setLine(self.start_point.x(), self.start_point.y(), self.start_point.x(), self.start_point.y())

            tr =QTransform()
            tr.scale(self.shape_width * .4, self.shape_width * .4)
            arrow = self.arrow_polygon * tr

            arrow_item = QGraphicsPolygonItem()
            arrow_item.setPos(self.start_point)
            arrow_item.setPen(self.current_pen)
            arrow_item.setBrush(self.current_brush)
            arrow_item.setPolygon(arrow)

            self.current_arrow_line_item = QGraphicsItemGroup()
            self.current_arrow_line_item.addToGroup(line_item)
            self.current_arrow_line_item.addToGroup(arrow_item)

            self.scene.addItem(self.current_arrow_line_item)
        if self.current_tool == "double_arrow":
            line_item = QGraphicsLineItem()
            line_item.setPen(self.current_pen)
            line_item.setLine(self.start_point.x(), self.start_point.y(), self.start_point.x(), self.start_point.y())

            tr =QTransform()
            tr.scale(self.shape_width * .4, self.shape_width * .4)
            arrow = self.arrow_polygon * tr

            arrow_item = QGraphicsPolygonItem()
            arrow_item.setPos(self.start_point)
            arrow_item.setPen(self.current_pen)
            arrow_item.setBrush(self.current_brush)
            arrow_item.setPolygon(arrow)

            arrow_item2 = QGraphicsPolygonItem()
            arrow_item2.setPos(self.start_point)
            arrow_item2.setPen(self.current_pen)
            arrow_item2.setBrush(self.current_brush)
            arrow_item2.setPolygon(QPolygonF(arrow))

            self.current_double_arrow_line_item = QGraphicsItemGroup()
            self.current_double_arrow_line_item.addToGroup(line_item)
            self.current_double_arrow_line_item.addToGroup(arrow_item)
            self.current_double_arrow_line_item.addToGroup(arrow_item2)

            self.scene.addItem(self.current_double_arrow_line_item)
        if self.current_tool == "rectangle":
            self.current_rectangle_item = QGraphicsRectItem()
            self.current_rectangle_item.setPen(self.current_pen)
            self.current_rectangle_item.setRect(self.start_point.x(), self.start_point.y(), 0, 0)
            self.scene.addItem(self.current_rectangle_item)
        if self.current_tool == "ellipse":
            self.current_ellipse_item = QGraphicsEllipseItem()
            self.current_ellipse_item.setPen(self.current_pen)
            self.current_ellipse_item.setRect(self.start_point.x(), self.start_point.y(), 0, 0)
            self.scene.addItem(self.current_ellipse_item)
        if self.current_tool == "text":
            if self.current_text_item:
                self.setFocus()
                self.current_text_item = None
                return
            text_input = QTextEdit()
            font = text_input.currentFont()
            font.setPointSize(self.text_size)
            text_input.setFont(font)
            text_input.setUndoRedoEnabled(False)

            text_input.setFixedSize(60, 30 * self.text_size / 10)
            text_input.setStyleSheet(f"QTextEdit {{background-color: rgba(255,255,255, .8); color:{self.text_color};}}")

            self.current_text_item = QWidget()
            self.current_text_item.setStyleSheet("background-color: transparent;")
            self.current_text_item.setFixedSize(self.canvas_width, self.canvas_height)
            text_input.setParent(self.current_text_item)
            self.scene.addWidget(self.current_text_item)

            text_input.move(self.start_point.x(), self.start_point.y())
            text_input.setFocus()

            text_input.textChanged.connect(lambda: (text_input.setFixedSize(text_input.document().idealWidth() + 20 * self.text_size / 10,
                                                                            text_input.document().size().height() + 10 * self.text_size / 10)))

            def focusOutEvent(e):
                    text_input.setReadOnly(True)
                    cursor = text_input.textCursor()
                    cursor.clearSelection()
                    text_input.setTextCursor(cursor)
            text_input.focusOutEvent = focusOutEvent

            def mousePressEvent(e):
                self.current_text_item = text_input,
                text_input.setReadOnly(False),
                text_input.setFocus(),
            text_input.mousePressEvent = mousePressEvent
        
    def _mouseMoveEvent(self, e):
        if not self.dragging:
            return
        self.end_point = e.position()
        self.end_point.setX(min(self.canvas_width, max(0, self.end_point.x())))
        self.end_point.setY(min(self.canvas_height, max(0, self.end_point.y())))
        if self.current_tool == "select" and self.select_start_point is not None:
            delta = self.end_point - self.select_start_point
            self.view.horizontalScrollBar().setValue(self.view.horizontalScrollBar().value() - delta.x())
            self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().value() - delta.y())
            self.select_start_point = self.end_point
        if self.current_tool == "pen" and self.current_path_item is not None:
            self.current_path.lineTo(self.end_point)
            self.current_path_item.setPath(self.current_path)
        if self.current_tool == "line"  and self.current_line_item is not None:
            self.current_line_item.setLine(self.current_line_item.line().x1(), self.current_line_item.line().y1(), self.end_point.x(), self.end_point.y())
        if self.current_tool == "arrow" and self.current_arrow_line_item is not None:
            line = self.current_arrow_line_item.childItems()[0]
            line.setLine(line.line().x1(), line.line().y1(), self.end_point.x(), self.end_point.y())
            arrow = self.current_arrow_line_item.childItems()[1]
            arrow.setPos(self.end_point)
            dir = self.end_point - self.start_point
            arrow.setRotation(atan2(dir.y(), dir.x()) * 180 / pi)
        if self.current_tool == "double_arrow" and self.current_double_arrow_line_item is not None:
            line = self.current_double_arrow_line_item.childItems()[0]
            line.setLine(line.line().x1(), line.line().y1(), self.end_point.x(), self.end_point.y())
            arrow = self.current_double_arrow_line_item.childItems()[1]
            arrow.setPos(self.end_point)
            dir = self.end_point - self.start_point
            arrow.setRotation(atan2(dir.y(), dir.x()) * 180 / pi)
            arrow2 = self.current_double_arrow_line_item.childItems()[2]
            arrow2.setRotation(atan2(dir.y(), dir.x()) * 180 / pi + 180)
        if self.current_tool == "rectangle" and self.current_rectangle_item is not None:
            start_point = QPointF(self.start_point)
            end_point = QPointF(self.end_point)
            width = abs(end_point.x() - start_point.x())
            height = abs(end_point.y() - start_point.y())
            if self.end_point.x() < self.start_point.x() and self.end_point.y() > self.start_point.y():
                start_point.setX(self.end_point.x())
                start_point.setY(self.end_point.y() - height)
                end_point.setX(self.start_point.x())
                end_point.setY(self.start_point.y() + height)
            elif self.end_point.x() > self.start_point.x() and self.end_point.y() < self.start_point.y():
                start_point.setX(self.end_point.x() - width)
                start_point.setY(self.end_point.y())
                end_point.setX(self.start_point.x() + width)
                end_point.setY(self.start_point.y())
            elif self.end_point.x() < self.start_point.x() and self.end_point.y() < self.start_point.y():
                start_point.setX(self.end_point.x())
                start_point.setY(self.end_point.y())
                end_point.setX(self.start_point.x())
                end_point.setY(self.start_point.y())
            self.current_rectangle_item.setRect(start_point.x(), start_point.y(), end_point.x() - start_point.x(), end_point.y() - start_point.y())
        if self.current_tool == "ellipse" and self.current_ellipse_item is not None:
            start_point = QPointF(self.start_point)
            end_point = QPointF(self.end_point)
            width = abs(end_point.x() - start_point.x())
            height = abs(end_point.y() - start_point.y())
            if self.end_point.x() < self.start_point.x() and self.end_point.y() > self.start_point.y():
                start_point.setX(self.end_point.x())
                start_point.setY(self.end_point.y() - height)
                end_point.setX(self.start_point.x())
                end_point.setY(self.start_point.y() + height)
            elif self.end_point.x() > self.start_point.x() and self.end_point.y() < self.start_point.y():
                start_point.setX(self.end_point.x() - width)
                start_point.setY(self.end_point.y())
                end_point.setX(self.start_point.x() + width)
                end_point.setY(self.start_point.y())
            elif self.end_point.x() < self.start_point.x() and self.end_point.y() < self.start_point.y():
                start_point.setX(self.end_point.x())
                start_point.setY(self.end_point.y())
                end_point.setX(self.start_point.x())
                end_point.setY(self.start_point.y())
            self.current_ellipse_item.setRect(self.start_point.x(), self.start_point.y(), self.end_point.x() - self.start_point.x(), self.end_point.y() - self.start_point.y())
    
    def _mouseReleaseEvent(self, e):
        if not self.dragging:
            return
        self.dragging = False
        if self.current_tool == "select" and self.select_start_point is not None:
            QApplication.restoreOverrideCursor()
            self.select_start_point = None
        if self.current_tool == "pen" and self.current_path_item is not None:
            self.undo_history.push(AddSceneItemCmd(self, self.current_path_item))
            self.current_path_item = None
        if self.current_tool == "line" and self.current_line_item is not None:
            self.undo_history.push(AddSceneItemCmd(self, self.current_line_item))
            self.current_line_item = None
        if self.current_tool == "arrow" and self.current_arrow_line_item is not None:
            self.undo_history.push(AddSceneItemCmd(self, self.current_arrow_line_item))
            self.current_arrow_line_item = None
        if self.current_tool == "double_arrow" and self.current_double_arrow_line_item is not None:
            self.undo_history.push(AddSceneItemCmd(self, self.current_double_arrow_line_item))
            self.current_double_arrow_line_item = None
        if self.current_tool == "rectangle" and self.current_rectangle_item is not None:
            self.undo_history.push(AddSceneItemCmd(self, self.current_rectangle_item))
            self.current_rectangle_item = None
        if self.current_tool == "ellipse" and self.current_ellipse_item is not None:
            self.undo_history.push(AddSceneItemCmd(self, self.current_ellipse_item))
            self.current_ellipse_item = None
        if self.current_tool == "text" and self.current_text_item is not None:
            self.undo_history.push(AddSceneItemCmd(self, self.current_text_item))

    def closeEvent(self, event):
        self.is_sequence and self.timeline.stop()
        self.save_settings()
        # check if self has self.try_lock_thread.terminate()
        self.try_lock_thread and self.try_lock_thread.terminate()
        self._parent and self._parent.reset_ui()
    
    def try_lock(self):
        self.try_lock_thread = TryLock()
        if self.try_lock_thread.try_lock():
            # no other instance running, claer cache dir safely
            capturer.clear_cache_dir()
        else:
            # acquire lock as soon as other app closed so new instances can't remove cache dir
            self.try_lock_thread.start()

    @staticmethod
    def create_button(text="", icon=None, bgcolor= "#3e3e3e", hovercolor = "#494949", pressedcolor="#434343", callback=None):
        btn = QPushButton(text)
        btn.setStyleSheet(f"QPushButton {{ background-color: {bgcolor}; color: #fff; padding: 5px 10px; border-radius: 4px; border: 1px solid #434343;}} QPushButton:hover {{background-color: {hovercolor};}} QPushButton:pressed {{background-color: {pressedcolor};}}")
        btn.setFixedHeight(30)
        if icon:
            btn.setIcon(QIcon(icon))
            btn.setIconSize(QSize(20, 20))

        if callback:
            btn.clicked.connect(callback)

        return btn

    @staticmethod
    def create_h_divider(thickness=2):
        divider = QWidget()
        divider.setFixedHeight(thickness)
        divider.setStyleSheet("QWidget { background-color: #444; }")
        return divider

class Capturer(QThread):
    recording_done_signal = Signal(str)
    encoding_done_signal = Signal(str)
    decoding_done_signal = Signal(str)
    snapshot_done_signal = Signal(str)
    countdown_signal = Signal(int)
    run_timer_signal = Signal(int)
    capture_stopped_signal = Signal()
    minimize_to_tray_signal = Signal()
    hide_app_signal = Signal()
    progress_signal = Signal(str)

    def __init__(self):
        super().__init__()

        self.mode = "record" # record, encode, snapshot
        self.encode_options = None
        self.fullscreen = True
        self.show_cursor = True
        self.cursor_image = QPixmap(f"{app_path}/icon/cursor.png").scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.pos_x = 0
        self.pos_y = 0
        self.width = 0
        self.height = 0
        self.range = None
        self.UID = time.strftime("%Y%m%d-%H%M%S")
        self.capture_count = 0
        self.halt = False
        self.cache_dir = f'{user_path}/.cache'
        self.current_cache_folder = f'{self.cache_dir}/{time.strftime("%H%M%S")}' # different folder for each capture
        self.start_capture_time = 0
        self.v_ext = "gif"
        self.ffmpeg_bin = "ffmpeg"
        self.quality = "hi" # md or hi
        self.ffmpeg_flags = {"giflw": ["-quality" "50", "-loop","0"],
                             "gifmd": ["-vf", "split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle", "-quality", "100", "-loop", "0"],
                             "gifhi": ["-vf", "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse", "-quality", "100", "-loop", "0"],
                             "mp4md": ["-vf", 'scale=trunc(iw/2)*2:trunc(ih/2)*2', "-crf", "32"],
                             "mp4hi": ["-vf", 'scale=trunc(iw/2)*2:trunc(ih/2)*2', "-crf", "18"],
                             "webmmd": ["-crf", "32", "-b:v", "0"],
                             "webmhi": ["-crf", "18", "-b:v", "0"]}
        self.fmt = "06d"
        self.fps = 15
        self.true_fps = 15 # Takes dropped / missed frames into account, otherwise it will play faster on drawover
        self.delay = 3
        self.duration = 0
        self.progress_range = (0, 100)
        self.active_screen = None
        self.i_ext = "jpg"

    def run(self):
        self.halt = False
        if self.mode == "record":
            self.delay_countdown()
            if self.halt:
                self.capture_stopped_signal.emit()
                self.quit()
                return
            self.run_timer_signal.emit(self.duration)
            self.fullscreen and self.minimize_to_tray_signal.emit()
            time.sleep(.2) # give the app time to move to the tray
            self.clear_cache_files()
            self.capture_count = 0
            self.start_capture_time = time.time()
            period = 1.0/self.fps
            seconds = 0
            while not self.halt:
                st = time.time()
                self.snapshot_md(self.capture_count)
                self.capture_count += 1
                td = time.time()-st
                wait = period-td
                if(wait>0):time.sleep(wait)
                total_time = int(time.time()-self.start_capture_time)
                if total_time > seconds:
                    seconds = total_time
                    self.run_timer_signal.emit(seconds if self.duration == 0 else self.duration-seconds)
                if self.duration != 0 and total_time >= self.duration:
                    self.halt = True

            self.stop_capture_time = time.time()
            self.true_fps = math.ceil((float(self.capture_count) / (self.stop_capture_time-self.start_capture_time)))
            self.recording_done_signal.emit(self.current_cache_folder)
        elif self.mode == "encode":
            self.progress_signal.emit("0")
            self.progress_range = (0, 100)
            if self.encode_options and self.encode_options["drawover_image_path"]:
                self.progress_range = (0, 50)
                self.encoding_drawover()
                self.progress_range = (50, 100)
            video_file = self.encode_video()
            self.encoding_done_signal.emit(video_file)
        elif self.mode == "decode":
            self.clear_cache_files()
            self.progress_signal.emit("0")
            self.progress_range = (0, 100)
            output = self.decode_video()
            self.decoding_done_signal.emit(output)
        elif self.mode == "snapshot":
            self.delay_countdown()
            self.clear_cache_files()
            if self.halt:
                self.capture_stopped_signal.emit()
                self.quit()
                return
            self.fullscreen and self.hide_app_signal.emit()
            time.sleep(.2) # give app time to hide
            filepath = self.snapshot_md(None, self.i_ext)
            self.snapshot_done_signal.emit(filepath)

        self.quit()
    
    def quit(self):
        self.encode_options = None
        super().quit()
    
    def delay_countdown(self):
        if self.delay > 0:
            delay = self.delay
            st = time.time()
            self.countdown_signal.emit(delay)
            while delay > 0 and not self.halt:
                passed = time.time()-st
                if passed >= 1:
                    delay -= 1
                    self.countdown_signal.emit(delay)
                    st = time.time()
            
        if self.halt:
            return False
        
        return True

    def record(self):
        self.mode = "record"
        self.start()

    def encode(self, encode_options=None):
        self.mode = "encode"
        self.encode_options = encode_options
        self.start()
    
    def decode(self, decode_options):
        self.mode = "decode"
        self.decode_options = decode_options
        self.start()
    
    def encoding_drawover(self):
        drawover_pixmap = QPixmap(self.encode_options["drawover_image_path"])
        pos = QPoint()
        rng = self.encode_options["drawover_range"] or (0, self.capture_count)
        start_time = time.time()
        for i in range(*rng):
            filename = f'{self.current_cache_folder}/peek_{self.UID}_{str(i).zfill(6)}.jpg'
            pixmap = QPixmap(filename)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing,True)
            painter.drawPixmap(pos, drawover_pixmap)
            painter.end()
            pixmap.save(filename, "jpg", 40 if self.quality == "md" else 100)
            passed_time = time.time()-start_time
            if passed_time > .3 or i == rng[1]-1 or i == rng[0]:
                self.progress_signal.emit(f"{math.ceil(Capturer.map_range(i, rng[0], rng[1]-1, self.progress_range[0], self.progress_range[1]))}")
                start_time = time.time()

    def encode_video(self):
        start_number = 0
        vframes = self.capture_count
        if self.encode_options and self.encode_options["drawover_range"]:
            start_number = self.encode_options["drawover_range"][0]
            vframes = self.encode_options["drawover_range"][1] - self.encode_options["drawover_range"][0]
        fprefix = (f'{self.current_cache_folder}/peek_{self.UID}_')
        vidfile = f"{self.current_cache_folder}/peek_{self.UID}.{self.v_ext}"

        systemcall = [str(self.ffmpeg_bin), "-r", str(self.true_fps), "-y",
                      "-start_number", str(start_number),
                      "-i", str(fprefix)+"%"+str(self.fmt)+".jpg",
                      "-vframes", str(vframes),
                      *self.ffmpeg_flags[self.v_ext + self.quality],
                      str(vidfile),
                      "-progress", "pipe:1"]

        try:
            # Shell is True on windows, otherwise the terminal window pops up on Windows app
            process = subprocess.Popen(systemcall, shell=sys.platform == "win32", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
            while True:
                realtime_output = process.stdout.readline()
                if realtime_output == '' and process.poll() is not None:
                    if process.returncode != 0:
                        vidfile = None
                        logger.error(f"ffmpeg returned {process.returncode}")
                    break
                if realtime_output:
                    if "frame=" in realtime_output:
                        frame = realtime_output.split("frame=")[1].split(" ")[0]
                        if frame:
                            percent = math.ceil(Capturer.map_range(int(frame), 0, vframes, self.progress_range[0], self.progress_range[1]))
                            self.progress_signal.emit(f"{percent}")
        except Exception as e:
            logger.error(e)
            vidfile = None

        return vidfile
    
    def decode_video(self):
        os.makedirs(self.current_cache_folder, exist_ok=True)
        image_path = self.decode_options["image_path"]
        r_frame_rate, self.true_fps, nb_frames = self.get_video_info(image_path)

        systemcall = ['ffmpeg', '-i', image_path, '-start_number', '0', f'{self.current_cache_folder}/peek_{self.UID}_%06d.jpg', "-progress", "pipe:1"]

        try:
            # Shell is True on windows, otherwise the terminal window pops up on Windows app
            process = subprocess.Popen(systemcall, shell=sys.platform == "win32", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
            while True:
                realtime_output = process.stdout.readline()
                if realtime_output == '' and process.poll() is not None:
                    if process.returncode != 0:
                        logger.error(f"ffmpeg returned {process.returncode}")
                        return None
                    break
                if realtime_output:
                    if "frame=" in realtime_output:
                        frame = realtime_output.split("frame=")[1].split(" ")[0]
                        if frame:
                            percent = math.ceil(Capturer.map_range(int(frame), 0, nb_frames, 0, 100))
                            self.progress_signal.emit(f"{percent}")
        except Exception as e:
            logger.error(e)
            return None

        return self.current_cache_folder
    
    def get_video_info(self, filename):
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=avg_frame_rate,r_frame_rate,nb_frames",
                filename,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        ffprobe_out = str(result.stdout, "utf-8")
        r_frame_rate = int(ffprobe_out.split("r_frame_rate=")[1].split("\n")[0].split("/")[0])
        avg_frame_rate = int(ffprobe_out.split("avg_frame_rate=")[1].split("\n")[0].split("/")[0])
        nb_frames = int(ffprobe_out.split("nb_frames=")[1].split("\n")[0])
        return r_frame_rate, avg_frame_rate, nb_frames

    def stop(self):
        self.halt = True
    
    def snapshot(self):
        self.UID = time.strftime("%Y%m%d-%H%M%S")
        self.capture_count = 0
        self.mode = "snapshot"
        self.start()

    def snapshot_drawover(self, drawover_image_path):
        filename = f'{self.current_cache_folder}/peek_{self.UID}.{self.i_ext}'
        pixmap = QImage(filename)
        drawover_pixmap = QImage(drawover_image_path)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing,True)
        painter.drawImage(QPoint(), drawover_pixmap)
        painter.end()

        pixmap.save(filename, self.i_ext, 60 if self.quality == "md" else 100)
        return filename

    def clear_cache_files(self):
        if os.path.exists(self.current_cache_folder):
            try:
                shutil.rmtree(self.current_cache_folder)
            except Exception as e:
                logger.error(e)
    
    def clear_cache_dir(self):
        if os.path.exists(self.cache_dir):
            try:
                shutil.rmtree(self.cache_dir)
            except Exception as e:
                logger.error(e)

    def snapshot_md(self, capture_count=None, i_ext="jpg"):
        screen = self.active_screen or QGuiApplication.primaryScreen()
        screenshot = QScreen.grabWindow(screen)
        if self.show_cursor:
            painter = QPainter(screenshot)
            painter.drawPixmap(QCursor.pos(screen) - QPoint(screen.geometry().x(), screen.geometry().y()) - QPoint(7, 5), self.cursor_image)
            painter.end()

        pr = QScreen.devicePixelRatio(screen)
        screenshot = screenshot.scaledToWidth(int(screenshot.size().width()/pr), Qt.TransformationMode.SmoothTransformation)
        if not self.fullscreen:
            screenshot = screenshot.copy(self.pos_x, self.pos_y, self.width, self.height)

        os.makedirs(self.current_cache_folder, exist_ok=True)
        file_path = (f'{self.current_cache_folder}/peek_{self.UID}.{i_ext}')
        file_path = file_path[:-4] + f'_{capture_count:06d}.{i_ext}' if capture_count != None else file_path

        screenshot.save(file_path, i_ext, 60 if self.quality == "md" else 100)
        return file_path
    
    def snapshot_hi(self, capture_count=None, i_ext="jpg"):
        screen = self.active_screen or QGuiApplication.primaryScreen()
        screenshot = QScreen.grabWindow(screen)
        pr = QScreen.devicePixelRatio(screen)
        screenshot.setDevicePixelRatio(pr)

        if self.show_cursor:
            painter = QPainter(screenshot)
            painter.drawPixmap(QCursor.pos(screen) - QPoint(screen.geometry().x() * pr, screen.geometry().y() * pr) - QPoint(7, 5), self.cursor_image)
            painter.end()
        
        if not self.fullscreen:
            screenshot = screenshot.copy(self.pos_x * pr, self.pos_y * pr, self.width * pr, self.height * pr)

        os.makedirs(self.current_cache_folder, exist_ok=True)
        file_path = (f'{self.current_cache_folder}/peek_{self.UID}.{i_ext}')
        file_path = file_path[:-4] + f'_{capture_count:06d}.{i_ext}' if capture_count != None else file_path

        img = screenshot.toImage()
        img.setDotsPerMeterX(img.dotsPerMeterX() * pr )
        img.setDotsPerMeterY(img.dotsPerMeterY() * pr )

        img.save(file_path, i_ext, 60 if self.quality == "md" else 100)
        return file_path
    
    @staticmethod
    def map_range(value, in_min, in_max, out_min, out_max):
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

class CheckUpdate(QThread):
    update_check_done_signal = Signal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            response = requests.get("https://pypi.org/pypi/pypeek/json")
            if response.status_code == 200:
                data = response.json()
                self.update_check_done_signal.emit(data["info"]["version"])
        except Exception as e:
            logger.error(e)
            
        self.quit()

class TryLock(QThread):
    def __init__(self):
        super().__init__()
        self.lock_file = QLockFile(user_path + "/peek.lock")

    def run(self):
        while True:
            if self.lock_file.tryLock(2000):
                break

            time.sleep(1)
            
        self.quit()
    
    def try_lock(self):
        return self.lock_file.tryLock(2000)

app = QApplication(sys.argv)

def _show():
    init()
    window = PyPeek()
    app.exec()
    if window.needs_restart:
        _show()

def _show_drawover():
    init()
    window = DrawOver()
    window.show()
    app.exec()

def show():
    if len(sys.argv) > 1:
        if sys.argv[1] == "-h" or sys.argv[1] == "--help":
            print("Usage: pypeek [OPTION]")
            print("no option\t\tStart pypeek")
            print("-h, --help\t\tShow this help message")
            print("-v, --version\t\tShow version")
            print("-s, --shortcut\t\tCreate shortcut")
            print("-d, --drawover\t\tOpen drawover tool")
            return
        if sys.argv[1] == "-v" or sys.argv[1] == "--version":
            print("pypeek v" + __version__)
            return
        if sys.argv[1] == "-s" or sys.argv[1] == "--shortcut":
            create_shortcut(__version__)
            return
        if sys.argv[1] == "-d" or sys.argv[1] == "--drawover":
            _show_drawover()
            return
    
    _show()
