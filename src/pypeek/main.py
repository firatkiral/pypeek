import os, shutil, time, subprocess, configparser, sys, requests, math, distutils.spawn, logging
from logging.handlers import RotatingFileHandler
from .shortcut import create_shortcut
from .drawover import DrawOver
from .ffmpeg import get_ffmpeg
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

user_path, app_path, logger = None, None, None
__version__ = '2.9.2'

def init():
    global user_path, app_path, logger
    if user_path is not None:
        return
    
    user_path = os.path.join(os.path.expanduser("~"), "Peek")
    if not os.path.exists(user_path):
        os.mkdir(user_path)

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
        if(not distutils.spawn.find_executable("ffmpeg") and not distutils.spawn.find_executable("ffmpeg", ffmpeg_local)): 
            if input("Ffmpeg not found, download? (y/n): ").lower() == "y":
                get_ffmpeg()
            else:
                print("Please install ffmpeg and add it to your PATH. Exiting...")
                sys.exit()

        # add local ffmpeg to path in case its local
        os.environ["PATH"] = os.pathsep.join([ffmpeg_local, os.environ["PATH"]])
        app_path = os.path.abspath(os.path.dirname(__file__))

class PyPeek(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Settings
        self.capture = Capture(self)

        self.capture.recording_done_signal.connect(self.recording_done)
        self.capture.encoding_done_signal.connect(self.encoding_done)
        self.capture.snapshot_done_signal.connect(self.snapshot_done)
        self.capture.capture_stopped_signal.connect(self.end_capture_ui)
        self.capture.countdown_signal.connect(self.update_countdown_ui)
        self.capture.run_timer_signal.connect(self.update_timer_ui)
        self.capture.minimize_to_tray_signal.connect(self.do_minimize_to_tray)
        self.capture.hide_app_signal.connect(self.hide)
        self.capture.progress_signal.connect(self.update_progress_ui)

        self.capture.show_cursor = True
        self.capture.fullscreen = True
        self.capture.v_ext = "gif" # gif, mp4, webm
        self.capture.fps = 15
        self.capture.quality = "md" # md, hi
        self.capture.delay = 3
        self.record_width = 506
        self.record_height = 406
        self.pos_x = 0
        self.pos_y = 0
        self.minimize_to_tray = False
        self.check_update_on_startup = True
        self.needs_restart = False
        self.last_save_path =  os.path.expanduser("~")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.set_mask)
        self.drag_start_position = None
        self.minimum_header_width = 355
        self.minimum_header_height = 45
        self.minimum_body_height = 100
        self.setStyleSheet("* {font-size: 15px; color: #ddd;} QToolTip { color: #333;}")
        self.block_window_move = False
        self.block_resize_event = False

        self.drawover_options = {}

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

        if self.capture.fullscreen: 
            self.set_fullscreen()
        else:
            self.show_info_layout()
        # self.check_update_on_startup and self.check_update()
        self.try_lock()

    def create_header_widget(self):
        self.snapshot_button = PyPeek.create_button("", f"{app_path}/icon/camera.png", "#0d6efd", "#0b5ed7", "#0a58ca" )
        self.snapshot_button.setToolTip("Take a snapshot")
        self.snapshot_button.clicked.connect(self.snapshot)

        self.record_button = PyPeek.create_button(f"{self.capture.v_ext.upper()}", f"{app_path}/icon/record-fill.png", "#0d6efd", "#0b5ed7", "#0a58ca" )
        self.record_button.setFixedWidth(84)
        self.record_button.setToolTip("Start recording")
        self.record_button.clicked.connect(self.record)

        self.stop_button = PyPeek.create_button("", f"{app_path}/icon/stop-fill.png", "#dc3545", "#dd3d4c", "#db2f3f" )
        self.stop_button.setToolTip("Stop")
        self.stop_button.clicked.connect(self.stop_capture)
        self.stop_button.setFixedWidth(114)
        # self.stop_button.setStyleSheet(self.stop_button.styleSheet() + "QPushButton { text-align:left; }")
        self.stop_button.hide()

        self.stop_encoding_button = PyPeek.create_button("", f"{app_path}/icon/x.png", "#0d6efd", "#0b5ed7", "#0a58ca")
        self.stop_encoding_button.setToolTip("Stop encoding")
        self.stop_encoding_button.setIconSize(QSize(16, 16))
        self.stop_encoding_button.clicked.connect(self.stop_encoding)
        self.stop_encoding_button.hide()

        self.fullscreen_button = PyPeek.create_button("", f"{app_path}/icon/display.png")
        self.fullscreen_button.setToolTip("Record fullscreen" if not self.capture.fullscreen else "Record window")
        self.fullscreen_button.clicked.connect(lambda: self.set_fullscreen(not self.capture.fullscreen))

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
        if self.capture.v_ext == "gif":
            self.gif_radio.setChecked(True)
        elif self.capture.v_ext == "mp4":
            self.mp4_radio.setChecked(True)
        elif self.capture.v_ext == "webm":
            self.webm_radio.setChecked(True)

        self.record_button_grp = PyPeek.make_group_button(self.record_button, self.format_button, self.stop_encoding_button)

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
        self.cursor_widget = PyPeek.create_row_widget("Capture Cursor", "Capture mouse cursor", PyPeek.create_checkbox("", self.capture.show_cursor, self.show_cursor ))
        self.hide_app_widget = PyPeek.create_row_widget("Minimize To Tray", "Minimize app to tray icon when recording fullscreen", PyPeek.create_checkbox("", self.minimize_to_tray, self.set_minimize_to_tray ))
        self.framerate_widget = PyPeek.create_row_widget("Frame Rate", "Captured frames per second", PyPeek.create_spinbox(self.capture.fps, 1, 60, self.set_framerate ))
        self.quality_widget = PyPeek.create_row_widget("Quality", "Set the quality of the video", PyPeek.create_radio_button({"md":"Medium", "hi":"High"}, self.capture.quality, self.set_quality))
        self.delay_widget = PyPeek.create_row_widget("Delay Start", "Set the delay before the recording starts", PyPeek.create_spinbox(self.capture.delay, 0, 10, self.set_delay_start ))
        self.duration_widget = PyPeek.create_row_widget("Recording Limit", "Stop recording after a given time in seconds (0 = unlimited)", PyPeek.create_spinbox(self.capture.duration, 0, 600, self.set_duration ))
        self.update_widget = PyPeek.create_row_widget("Check For Updates", "Check for updates on startup", PyPeek.create_checkbox("", self.check_update_on_startup, self.set_check_update_on_startup))
        self.reset_widget = PyPeek.create_row_widget("Reset And Restart", "Reset all settings and restart the app", PyPeek.create_button("Reset Settings", callback = self.reset_settings))
        self.copyright_widget = PyPeek.create_row_widget("About", f"Peek {__version__}, Cross platform screen recorder", PyPeek.create_hyperlink("Website", "https://github.com/firatkiral/pypeek/wiki"))

        self.settings_layout = QVBoxLayout()
        self.settings_layout.setContentsMargins(20, 10, 20, 10)
        self.settings_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.settings_layout.addWidget(self.cursor_widget)
        self.settings_layout.addWidget(PyPeek.create_h_divider())
        self.settings_layout.addWidget(self.hide_app_widget)
        self.settings_layout.addWidget(PyPeek.create_h_divider())
        self.settings_layout.addWidget(self.framerate_widget)
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

        self.capture.show_cursor = config.getboolean('capture', 'show_cursor', fallback=True)
        self.minimize_to_tray = config.getboolean('capture', 'minimize_to_tray', fallback=False)
        self.capture.fullscreen = config.getboolean('capture', 'fullscreen', fallback=True)
        self.capture.v_ext = config.get('capture', 'v_ext', fallback='gif')
        self.capture.fps = config.getint('capture', 'fps', fallback=15)
        self.capture.quality = config.get('capture', 'quality', fallback='md')
        self.capture.delay = config.getint('capture', 'delay', fallback=3)
        self.capture.duration = config.getint('capture', 'duration', fallback=0)
        self.record_width = config.getint('capture', 'width', fallback=506)
        self.record_height = config.getint('capture', 'height', fallback=406)
        self.pos_x = config.getint('capture', 'pos_x', fallback=int((QGuiApplication.primaryScreen().size().width() - self.minimum_header_width) / 2))
        self.pos_y = config.getint('capture', 'pos_y', fallback=int(QGuiApplication.primaryScreen().size().height() * .5))
        self.last_save_path = config.get('capture', 'last_save_path', fallback=self.last_save_path)
        self.check_update_on_startup = config.getboolean('capture', 'check_update_on_startup', fallback=True)
        self.drawover_options['current_tool'] = config.get('drawover', 'current_color', fallback='select')
        self.drawover_options['current_shape'] = config.get('drawover', 'current_shape', fallback='line')
        self.drawover_options['pen_color'] = config.get('drawover', 'pen_color', fallback='red')
        self.drawover_options['pen_width'] = config.getint('drawover', 'pen_width', fallback=3)
        self.drawover_options['shape_color'] = config.get('drawover', 'shape_color', fallback='red')
        self.drawover_options['shape_width'] = config.getint('drawover', 'shape_width', fallback=3)
        self.drawover_options['text_color'] = config.get('drawover', 'text_color', fallback='black')
        self.drawover_options['text_size'] = config.getint('drawover', 'text_size', fallback=13)
    
    def save_settings(self):
        config_file = os.path.join(user_path, 'peek.cfg')
        config = configparser.ConfigParser()

        config['capture'] = {
            'show_cursor': str(self.capture.show_cursor),
            'minimize_to_tray': str(self.minimize_to_tray),
            'fullscreen': str(self.capture.fullscreen),
            'v_ext': self.capture.v_ext,
            'fps': str(self.capture.fps),
            'quality': self.capture.quality,
            'delay': str(self.capture.delay),
            'duration': str(self.capture.duration),
            'width': str(self.record_width),
            'height': str(self.record_height),
            'pos_x': str(self.pos_x),
            'pos_y': str(self.pos_y),
            'last_save_path': self.last_save_path,
            'check_update_on_startup': str(self.check_update_on_startup),
        }
        config['drawover'] = {
            'current_tool': self.drawover_options['current_tool'],
            'current_shape': self.drawover_options['current_shape'],
            'pen_color': self.drawover_options['pen_color'],
            'pen_width': str(self.drawover_options['pen_width']),
            'shape_color': self.drawover_options['shape_color'],
            'shape_width': str(self.drawover_options['shape_width']),
            'text_color': self.drawover_options['text_color'],
            'text_size': str(self.drawover_options['text_size']),
        }

        with open(config_file, 'w') as config_file:
            config.write(config_file)

    def reset_settings(self):
        config_file = os.path.join(user_path, 'peek.cfg')
        if os.path.exists(config_file):
            os.remove(config_file)
        self.load_settings()
        self.restart()
    
    def update_drawover_settings(self, drawover):
        self.drawover_options = {
            'current_tool': drawover.current_tool,
            'current_shape': drawover.current_shape,
            'pen_color': drawover.pen_color,
            'pen_width': drawover.pen_width,
            'shape_color': drawover.shape_color,
            'shape_width': drawover.shape_width,
            'text_color': drawover.text_color,
            'text_size': drawover.text_size
        }
    
    def restart(self):
        self.needs_restart = True
        self.close_app()
    
    def try_lock(self):
        self.try_lock_thread = TryLock()
        if self.try_lock_thread.try_lock():
            # no other instance running, claer cache dir safely
            self.capture.clear_cache_dir()
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
            self.capture.v_ext = "gif"
        elif self.mp4_radio.isChecked():
            self.capture.v_ext = "mp4"
        elif self.webm_radio.isChecked():
            self.capture.v_ext = "webm"
        self.record_button.setText(f"{self.capture.v_ext.upper()}")

    def prepare_capture_ui(self):
        self.block_resize_event = True
        if not self.capture.fullscreen:
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
        self.stop_encoding_button.show()
        
        self.hide_grips()
        self.capture.pos_x, self.capture.pos_y = PyPeek.get_global_position(self.record_area_widget)
        self.capture.width = self.record_area_widget.width() 
        self.capture.height = self.record_area_widget.height()
        if not self.capture.fullscreen:
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
            
    def end_capture_ui(self):
        self.block_resize_event = True
        self.tray_icon.hide()
        self.record_button_grp.show()
        self.stop_button.hide()
        self.record_button.setDisabled(False)
        self.record_button.setText(self.capture.v_ext.upper())
        self.record_button.setIcon(QIcon(f"{app_path}/icon/record-fill.png"))
        self.record_button.setToolTip("Start recording")
        self.stop_button.setText("")
        self.format_button.setDisabled(False)
        self.format_button.show()
        self.stop_encoding_button.hide()
        self.snapshot_button.setDisabled(False)
        self.fullscreen_button.setDisabled(False)
        self.settings_button.setDisabled(False)
        self.close_button.setDisabled(False)
        self.snapshot_button.show()
        self.fullscreen_button.show()
        self.settings_button.show()
        self.close_button.show()
        self.show_grips()
        if not self.capture.fullscreen:
            self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
            self.setMaximumSize(16777215, 16777215) # remove fixed height
            self.resize(self.record_width, self.record_height)
        else:
            self.setFixedWidth(self.minimum_header_width)
        self.capture.clear_cache_files()
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
    
    def update_progress_ui(self, value):
        self.record_button.setText(value)

    def snapshot(self):
        self.prepare_capture_ui()
        self.capture.snapshot()
    
    def snapshot_done(self, filepath):
        self.hide()
        self.tray_icon.hide()
        drawover = DrawOver(filepath, self.drawover_options, self.capture.true_fps, self)
        drawover.show()
    
    def snapshot_drawover_done(self, drawover):
        filepath = drawover.image_path
        if drawover.encode_options and drawover.encode_options["drawover_image_path"]:
            filepath = self.capture.snapshot_drawover(drawover.encode_options["drawover_image_path"])
            
        filename = f"peek{os.path.splitext(os.path.basename(filepath))[1]}"
        self.last_save_path = self.last_save_path if os.path.exists(self.last_save_path) else os.path.expanduser("~")
        new_filepath = QFileDialog.getSaveFileName(self, "Save Image", os.path.join(self.last_save_path, filename), "Images (*.jpg)")
        
        if new_filepath[0]:
            try:
                shutil.move(filepath, new_filepath[0])
                self.last_save_path = os.path.dirname(new_filepath[0])
                return True
            except Exception as e:
                logger.error(e)
            
        return False

    def record(self):
        self.prepare_capture_ui()
        self.capture.record()

    def recording_done(self, cache_folder):
        self.record_button_grp.show()
        self.stop_button.hide()
        self.hide()
        self.tray_icon.hide()
        drawover = DrawOver(cache_folder, self.drawover_options, self.capture.true_fps, self)
        drawover.show()
    
    def recording_drawover_done(self, drawover):
        self.show()
        self.capture.encode(drawover.encode_options)

    def encoding_done(self, filepath):
        if filepath:
            filename = f"peek{os.path.splitext(os.path.basename(filepath))[1]}"
            self.last_save_path = self.last_save_path if os.path.exists(self.last_save_path) else os.path.expanduser("~")
            new_filepath = QFileDialog.getSaveFileName(self, "Save Video", os.path.join(self.last_save_path, filename), f"Videos (*.{self.capture.v_ext})")
            
            if new_filepath[0]:
                try:
                    shutil.move(filepath, new_filepath[0])
                    self.last_save_path = os.path.dirname(new_filepath[0])
                except Exception as e:
                    logger.error(e)
        
        self.end_capture_ui()

    def stop_capture(self):
        self.capture.stop()

    def stop_encoding(self):
        self.capture.terminate()
        self.end_capture_ui()

    def set_mask(self):
        if self.capture.fullscreen:
            return
        self.timer.stop()
        self.clearFocus()
        empty_region = QRegion(QRect(QPoint(8,43), self.frame.size() - QSize(16, 51)), QRegion.RegionType.Rectangle)
        region = QRegion(QRect(QPoint(-2,-2), self.frame.size() + QSize(4, 4)), QRegion.RegionType.Rectangle)
        self.setMask(region - empty_region)
        self.body_layout.setCurrentIndex(0)
        self.hide()
        self.show()
        # QTimer.singleShot(1000, lambda: self.setFocus())

    def show_info_layout(self):
        self.clearMask()
        self.info_size_label.setText(f"{self.body_widget.width()}x{self.body_widget.height()}")
        self.body_layout.setCurrentIndex(1)
        self.timer.start(2000)

    def close_app(self):
        self.close()
        self.destroy()

    def do_minimize_to_tray(self, show_notification = True):
        if self.minimize_to_tray:
            self.hide()
            self.tray_icon.show()
            show_notification and self.tray_icon.showMessage("Peek is recording!", "Peek minimized to tray icon and running in background", QSystemTrayIcon.MessageIcon.Information, 6000)

    def set_quality(self, value):
        self.capture.quality = value

    def set_fullscreen(self, value=True):
        self.block_resize_event = True
        if value:
            self.hide_grips()
            self.fullscreen_button.setIcon(QIcon(f"{app_path}/icon/bounding-box-circles.png"))
            self.fullscreen_button.setToolTip("Record window")
            self.setFixedSize(self.minimum_header_width, self.minimum_header_height) # prevent manual resizing height
            self.clearMask()
        else:
            self.show_grips()
            self.fullscreen_button.setIcon(QIcon(f"{app_path}/icon/display.png"))
            self.fullscreen_button.setToolTip("Record fullscreen")
            self.setMaximumSize(16777215, 16777215) # remove fixed height
            self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
            self.resize(self.record_width, self.record_height)
            self.show_info_layout()
            self.set_mask()
        self.capture.fullscreen = value
        self.block_resize_event = False

    def set_framerate(self, value):
        self.capture.fps = value
    
    def set_minimize_to_tray(self, value):
        self.minimize_to_tray = value
    
    def set_delay_start(self, value):
        self.capture.delay = value
    
    def set_duration(self, value):
        self.capture.duration = value
    
    def set_check_update_on_startup(self, value):
        self.check_update_on_startup = value
        if value:
            self.check_update()

    def show_cursor(self, value):
        self.capture.show_cursor = value

    def show_settings(self, value):
        if value:
            self.settings_widget.show()
        else:
            self.settings_widget.hide()

    def mousePressEvent(self, event):
        if not self.block_window_move:
            if not sys.platform in ["win32", "darwin"]:
                window = self.window().windowHandle()
                window.startSystemMove()
            else:
                self.drag_start_position = event.globalPosition()
                
    def mouseMoveEvent(self, event):
        if not self.drag_start_position:
            return

        diff = event.globalPosition() - self.drag_start_position
        self.move(self.x() + int(diff.x()), self.y() + int(diff.y()))
        self.drag_start_position = event.globalPosition()

    def mouseReleaseEvent(self, event):
        self.drag_start_position = None

    def moveEvent(self, event):
        self.capture.pos_x, self.capture.pos_y = PyPeek.get_global_position(self.record_area_widget)
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
        if self.capture.isRunning():
            self.capture.terminate()
            self.capture.clear_cache_files()
        self.save_settings()
        self.settings_widget.close()
        
        self.try_lock_thread.terminate()

    @staticmethod
    def get_global_position(widget):
        pos = widget.mapToGlobal(QPoint(0, 0))
        return pos.x(), pos.y()

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
    def make_group_button(button1, button2, button3):
        group = QHBoxLayout()
        group.setContentsMargins(0, 0, 0, 0)
        group.setSpacing(0)
        group.addWidget(button1)
        group.addWidget(button2)
        group.addWidget(button3)
        button1.setStyleSheet(button1.styleSheet() + "QPushButton {border-top-right-radius: 0; border-bottom-right-radius: 0; border-right: none;}")
        button2.setStyleSheet(button2.styleSheet() + "QPushButton {border-top-left-radius: 0; border-bottom-left-radius: 0; border-left: none;}")
        button3.setStyleSheet(button2.styleSheet() + "QPushButton {border-top-left-radius: 0; border-bottom-left-radius: 0; border-left: none;}")
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
        link = QLabel(f'<a href="{url}">{text}</a>')
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
    
class Capture(QThread):
    recording_done_signal = Signal(str)
    encoding_done_signal = Signal(str)
    snapshot_done_signal = Signal(str)
    countdown_signal = Signal(int)
    run_timer_signal = Signal(int)
    capture_stopped_signal = Signal()
    minimize_to_tray_signal = Signal()
    hide_app_signal = Signal()
    progress_signal = Signal(str)

    def __init__(self, app):
        super().__init__()

        self.app = app
        self.mode = "record" # record, encode, snapshot
        self.encode_options = None
        self.fullscreen = False
        self.show_cursor = True
        self.cursor_image = QPixmap(f"{app_path}/icon/cursor.png").scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.pos_x = 0
        self.pos_y = 0
        self.width = 0
        self.height = 0
        self.range = None
        self.UID = ""
        self.capture_count = 0
        self.halt = False
        self.cache_dir = f'{user_path}/.cache'
        self.current_cache_folder = f'{self.cache_dir}/{time.strftime("%H%M%S")}' # different folder for each capture
        self.start_capture_time = 0
        self.v_ext = "gif"
        self.ffmpeg_bin = "ffmpeg"
        self.quality = "md" # md or hi
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
        self.delay = 0
        self.duration = 0
        self.progress_range = (0, 100)

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
            self.UID = time.strftime("%Y%m%d-%H%M%S")
            self.capture_count = 0
            self.start_capture_time = time.time()
            period = 1.0/self.fps
            seconds = 0
            while not self.halt:
                st = time.time()
                self._snapshot(self.capture_count)
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
            self.true_fps = int((float(self.capture_count) / (self.stop_capture_time-self.start_capture_time))+0.5)
            self.recording_done_signal.emit(self.current_cache_folder)
        elif self.mode == "encode":
            self.progress_signal.emit("%0")
            self.progress_range = (0, 100)
            if self.encode_options and self.encode_options["drawover_image_path"]:
                self.progress_range = (0, 50)
                self._drawover()
                self.progress_range = (50, 100)
            video_file = self.encode_video()
            self.encoding_done_signal.emit(video_file)
        elif self.mode == "snapshot":
            self.delay_countdown()
            if self.halt:
                self.capture_stopped_signal.emit()
                self.quit()
                return
            self.fullscreen and self.hide_app_signal.emit()
            time.sleep(.2) # give app time to hide
            filepath = self._snapshot()
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
    
    def _drawover(self):
        drawover_pixmap = QPixmap(self.encode_options["drawover_image_path"])
        pos = QPoint()
        rng = self.encode_options["drawover_range"] or (0, self.capture_count)
        start_time = time.time()
        for i in range(*rng):
            filename = f'{self.current_cache_folder}/peek_{self.UID}_{str(i).zfill(6)}.jpg'
            pixmap = QPixmap(filename)
            painter = QPainter(pixmap)
            painter.drawPixmap(pos, drawover_pixmap)
            painter.end()
            pixmap.save(filename, "jpg", 100)
            passed_time = time.time()-start_time
            if passed_time > .3 or i == rng[1]-1 or i == rng[0]:
                self.progress_signal.emit(f"%{math.ceil(Capture.map_range(i, rng[0], rng[1]-1, self.progress_range[0], self.progress_range[1]))}")
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
                    break
                if realtime_output:
                    if "frame=" in realtime_output:
                        frame = realtime_output.split("frame=")[1].split(" ")[0]
                        if frame:
                            percent = math.ceil(Capture.map_range(int(frame), 0, vframes, self.progress_range[0], self.progress_range[1]))
                            self.progress_signal.emit(f"%{percent}")
        except Exception as e:
            logger.error(e)
            vidfile = None

        return vidfile
        
    def stop(self):
        self.halt = True
    
    def snapshot(self):
        self.UID = time.strftime("%Y%m%d-%H%M%S")
        self.capture_count = 0
        self.mode = "snapshot"
        self.start()

    def snapshot_drawover(self, drawover_image_path):
        drawover_pixmap = QPixmap(drawover_image_path)
        filename = f'{self.current_cache_folder}/peek_{self.UID}.jpg'
        pixmap = QPixmap(filename)
        painter = QPainter(pixmap)
        painter.drawPixmap(QPoint(), drawover_pixmap)
        painter.end()
        pixmap.save(filename, "jpg", 100)
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

    def _snapshot(self, capture_count=None):
        screenshot = QScreen.grabWindow(QApplication.instance().primaryScreen())
        if self.show_cursor:
            painter = QPainter(screenshot)
            painter.drawPixmap(QCursor.pos() - QPoint(7, 5), self.cursor_image)
            painter.end()
        
        pr = QScreen.devicePixelRatio(QApplication.instance().primaryScreen())
        screenshot = screenshot.scaledToWidth(int(screenshot.size().width()/pr), Qt.TransformationMode.SmoothTransformation)
        if not self.fullscreen:
            screenshot = screenshot.copy(self.pos_x, self.pos_y, self.width, self.height)

        not os.path.exists(self.current_cache_folder) and os.makedirs(self.current_cache_folder)
        file_path = (f'{self.current_cache_folder}/peek_{self.UID}.jpg')
        file_path = file_path[:-4] + f'_{capture_count:06d}.jpg' if capture_count != None else file_path

        screenshot.save(file_path, 'jpg', 100)
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
            if self.lock_file.tryLock():
                break

            time.sleep(1)
            
        self.quit()
    
    def try_lock(self):
        return self.lock_file.tryLock()


app = QApplication(sys.argv)

def _show():
    init()
    window = PyPeek()
    app.exec()
    if window.needs_restart:
        _show()

def show():
    if len(sys.argv) > 1:
        if sys.argv[1] == "-h" or sys.argv[1] == "--help":
            print("Usage: pypeek [OPTION]")
            print("no option\t\tStart pypeek")
            print("-h, --help\t\tShow this help message")
            print("-v, --version\t\tShow version")
            print("-s, --shortcut\t\tCreate shortcut")
            return
        if sys.argv[1] == "-v" or sys.argv[1] == "--version":
            print("pypeek v" + __version__)
            return
        if sys.argv[1] == "-s" or sys.argv[1] == "--shortcut":
            create_shortcut()
            return
    
    _show()
