import os, shutil, time, subprocess, tempfile, configparser, sys, requests
from .shortcut import create_shortcut
from .drawover import DrawOver
from .ffmpeg import get_ffmpeg
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    app_path = sys._MEIPASS
    os.environ["PATH"] = os.pathsep.join([app_path, os.environ["PATH"]])
elif __file__:
    get_ffmpeg()
    app_path = os.path.abspath(os.path.dirname(__file__))


user_path = os.path.join(os.path.expanduser("~"), "Peek")
if not os.path.exists(user_path):
    os.mkdir(user_path)

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
        self.capture.hide_app_signal.connect(self.hide_app)

        self.capture.show_cursor = True
        self.capture.fullscreen = True
        self.capture.v_ext = "gif" # gif, mp4, webm
        self.capture.fps = 15
        self.capture.quality = "md" # md, hi
        self.capture.delay = 3
        self.hide_on_record = True
        self.record_width = 600
        self.record_height = 400
        self.pos_x = 100
        self.pos_y = 100
        self.check_update_on_startup = True
        self.needs_restart = False

        # drawover settings
        self.drawover_options = {
            'current_tool': 'select',
            'current_shape': 'line',
            'pen_color': 'yellow',
            'pen_width': 2,
            'shape_color': 'yellow',
            'shape_width': 2,
            'text_color': 'black',
            'text_size': 13}

        # load settings from json file
        self.load_settings()

        self.version = "2.7.6"
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.set_mask)
        self.drag_start_position = None
        self.minimum_header_width = 355
        self.minimum_header_height = 45
        self.minimum_body_height = 100
        self.block_resize_event = False
        self.setStyleSheet("* {font-size: 15px; color: #ddd;}")

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

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("PyPeek")
        self.resize(self.record_width, self.record_height)
        self.move(self.pos_x, self.pos_y)
        self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
        self.show()
        self.set_mask()
        self.capture.fullscreen and self.set_fullscreen()
        self.check_update_on_startup and self.check_update()
        self.try_lock()

    def create_header_widget(self):
        self.snapshot_button = PyPeek.create_button("", f"{app_path}/icon/camera.png", "#0d6efd", "#0b5ed7", "#0a58ca" )
        self.snapshot_button.clicked.connect(self.snapshot)

        self.record_button = PyPeek.create_button(f"{self.capture.v_ext.upper()}", f"{app_path}/icon/record-fill.png", "#0d6efd", "#0b5ed7", "#0a58ca" )
        self.record_button.setFixedWidth(84)
        self.record_button.clicked.connect(self.record)

        self.stop_button = PyPeek.create_button("0:00", f"{app_path}/icon/stop-fill.png", "#dc3545", "#dd3d4c", "#db2f3f" )
        self.stop_button.clicked.connect(self.stop_capture)
        self.stop_button.setFixedWidth(114)
        # self.stop_button.setStyleSheet(self.stop_button.styleSheet() + "QPushButton { text-align:left; }")
        self.stop_button.hide()

        self.fullscreen_button = PyPeek.create_button("", f"{app_path}/icon/display.png")
        self.fullscreen_button.clicked.connect(lambda: self.set_fullscreen(not self.capture.fullscreen))


        self.menu_button = PyPeek.create_button("", "", "#0d6efd", "#0b5ed7", "#0a58ca")
        self.menu_button.setStyleSheet( self.menu_button.styleSheet() + " QPushButton::menu-indicator {subcontrol-position: center;}" )
        self.menu_button.setFixedWidth(30)
        self.menu = QMenu(self.menu_button)
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

        self.menu_button.setMenu(self.menu)

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

        self.record_button_grp = PyPeek.make_group_button(self.record_button, self.menu_button)

        self.settings_button = PyPeek.create_button("", f"{app_path}/icon/gear.png")
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
        self.hide_app_widget = PyPeek.create_row_widget("Hide App", "Hide the app while recording fullscreen", PyPeek.create_checkbox("", self.hide_on_record, self.set_hide_on_record ))
        self.framerate_widget = PyPeek.create_row_widget("Frame Rate", "Captured frames per second", PyPeek.create_spinbox(self.capture.fps, 1, 60, self.set_framerate ))
        self.quality_widget = PyPeek.create_row_widget("Quality", "Set the quality of the video", PyPeek.create_radio_button({"md":"Medium", "hi":"High"}, self.capture.quality, self.set_quality))
        self.delay_widget = PyPeek.create_row_widget("Delay Start", "Set the delay before the recording starts", PyPeek.create_spinbox(self.capture.delay, 0, 10, self.set_delay_start ))
        self.duration_widget = PyPeek.create_row_widget("Recording Duration", "Set the duration of the recording (0 for unlimited)", PyPeek.create_spinbox(self.capture.duration, 0, 600, self.set_duration ))
        self.update_widget = PyPeek.create_row_widget("Check For Updates", "Check for updates on startup", PyPeek.create_checkbox("", self.check_update_on_startup, self.set_check_update_on_startup))
        self.reset_widget = PyPeek.create_row_widget("Reset And Restart", "Reset all settings and restart the app", PyPeek.create_button("Reset Settings", callback = self.reset_settings))
        self.copyright_widget = PyPeek.create_row_widget("About", f"PyPeek {self.version}, Cross platform screen recorder", PyPeek.create_hyperlink("Website", "https://github.com/firatkiral/pypeek"))

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
        self.settings_layout.addWidget(self.update_widget)
        self.settings_layout.addWidget(PyPeek.create_h_divider())
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
        scroll_area.setWindowIcon(QIcon(f"{app_path}/icon/pypeek.png"))

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
        
    def create_tray_icon(self):
        tray_button = QSystemTrayIcon()
        icon = QIcon(f"{app_path}/icon/stop-fill.png")
        tray_button.setIcon(icon)
        tray_button.setToolTip("Stop Capture")
        tray_button.activated.connect(self.stop_capture)

        return tray_button

    def load_settings(self):
        config_file = os.path.join(user_path, 'pypeek.cfg')
        if not os.path.exists(config_file):
            return

        config = configparser.ConfigParser()
        config.read(config_file)

        self.capture.show_cursor = config.getboolean('capture', 'show_cursor', fallback=True)
        self.hide_on_record = config.getboolean('capture', 'hide_on_record', fallback=True)
        self.capture.fullscreen = config.getboolean('capture', 'fullscreen', fallback=True)
        self.capture.v_ext = config.get('capture', 'v_ext', fallback='gif')
        self.capture.fps = config.getint('capture', 'fps', fallback=15)
        self.capture.quality = config.get('capture', 'quality', fallback='md')
        self.capture.delay = config.getint('capture', 'delay', fallback=3)
        self.capture.duration = config.getint('capture', 'duration', fallback=0)
        self.record_width = config.getint('capture', 'width', fallback=600)
        self.record_height = config.getint('capture', 'height', fallback=400)
        self.pos_x = config.getint('capture', 'pos_x', fallback=100)
        self.pos_y = config.getint('capture', 'pos_y', fallback=100)
        self.check_update_on_startup = config.getboolean('capture', 'check_update_on_startup', fallback=True)
        self.drawover_options['current_tool'] = config.get('drawover', 'current_color', fallback='select')
        self.drawover_options['current_shape'] = config.get('drawover', 'current_shape', fallback='line')
        self.drawover_options['pen_color'] = config.get('drawover', 'pen_color', fallback='yellow')
        self.drawover_options['pen_width'] = config.getint('drawover', 'pen_width', fallback=2)
        self.drawover_options['shape_color'] = config.get('drawover', 'shape_color', fallback='yellow')
        self.drawover_options['shape_width'] = config.getint('drawover', 'shape_width', fallback=2)
        self.drawover_options['text_color'] = config.get('drawover', 'text_color', fallback='black')
        self.drawover_options['text_width'] = config.getint('drawover', 'text_width', fallback=13)
    
    def save_settings(self):
        config_file = os.path.join(user_path, 'pypeek.cfg')
        config = configparser.ConfigParser()

        config['capture'] = {
            'show_cursor': str(self.capture.show_cursor),
            'hide_on_record': str(self.hide_on_record),
            'fullscreen': str(self.capture.fullscreen),
            'v_ext': self.capture.v_ext,
            'fps': str(self.capture.fps),
            'quality': self.capture.quality,
            'delay': str(self.capture.delay),
            'duration': str(self.capture.duration),
            'width': str(self.record_width),
            'height': str(self.record_height),
            'pos_x': str(self.pos().x()),
            'pos_y': str(self.pos().y()),
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
        self.capture.show_cursor = True
        self.hide_on_record = True
        self.capture.fullscreen = True
        self.capture.v_ext = "gif"
        self.capture.fps = 15
        self.capture.quality = "md"
        self.capture.delay = 3
        self.capture.duration = 0
        self.record_width = 600
        self.record_height = 400
        self.pos_x = 100
        self.pos_y = 100
        self.check_update_on_startup = True
        self.drawover_options = {
            'current_tool': "select",
            'current_shape': "line",
            'pen_color': "yellow",
            'pen_width': 2,
            'shape_color': "yellow",
            'shape_width': 2,
            'text_color': "black",
            'text_size': 12
        }
        self.save_settings()
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
        if latest_version != self.version:
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
        self.record_button_grp.hide()
        self.stop_button.show()
        self.capture.pos_x, self.capture.pos_y = PyPeek.get_global_position(self.record_area_widget)
        self.capture.width = self.record_area_widget.width()
        self.capture.height = self.record_area_widget.height()
        self.snapshot_button.setDisabled(True)
        self.record_button.setDisabled(True)
        self.record_button.setIconSize(QSize(0, 0))
        self.record_button.setText("Working...")
        self.menu_button.setDisabled(True)
        self.fullscreen_button.setDisabled(True)
        self.settings_button.setDisabled(True)
        if not self.capture.fullscreen:
            self.setFixedSize(self.record_width, self.record_height)
        
    def end_capture_ui(self):
        self.tray_icon.hide()
        self.record_button_grp.show()
        self.stop_button.hide()
        self.snapshot_button.setDisabled(False)
        self.record_button.setDisabled(False)
        self.record_button.setText(self.capture.v_ext.upper())
        self.record_button.setIconSize(QSize(20, 20))
        self.stop_button.setText("0:00")
        self.menu_button.setDisabled(False)
        self.fullscreen_button.setDisabled(False)
        self.settings_button.setDisabled(False)
        self.close_button.setDisabled(False)
        if not self.capture.fullscreen:
            self.block_resize_event = True
            self.setMaximumSize(16777215, 16777215) # remove fixed height
            self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
            self.resize(self.record_width, self.record_height)
            self.block_resize_event = False
        self.capture.clear_cache_files()

    def update_countdown_ui(self, value):
        self.stop_button.setText(f' {value}')
        if value == 0:
            self.stop_button.setText("0:00")
    
    def update_timer_ui(self, value):
        minutes = value // 60
        seconds = value % 60
        self.stop_button.setText(f'{minutes:01d}:{seconds:02d}')

    def snapshot(self):
        self.prepare_capture_ui()
        self.capture.snapshot()
    
    def snapshot_done(self, filepath):
        self.setVisible(False)
        self.tray_icon.hide()
        drawover = DrawOver(filepath, self.drawover_options, self.capture.true_fps, self)
        drawover_res = drawover.exec()
        self.update_drawover_settings(drawover)
        self.setVisible(True)
        if drawover_res == 0:
            self.end_capture_ui()
            return

        if drawover_res == 1 and drawover.encode_options:
            filepath = self.capture.snapshot_drawover(drawover.encode_options["drawover_image_path"])
            
        filename = os.path.basename(filepath)
        new_filepath = QFileDialog.getSaveFileName(self, "Save Image", os.path.expanduser("~") + "/" + filename, "Images (*.jpg)")
        
        if new_filepath[0]:
            shutil.move(filepath, new_filepath[0])
        
        self.end_capture_ui()
        drawover.deleteLater()

    def record(self):
        self.prepare_capture_ui()
        self.capture.record()

    def recording_done(self, cache_folder):
        self.record_button_grp.show()
        self.stop_button.hide()
        self.setVisible(False)
        self.tray_icon.hide()
        drawover = DrawOver(cache_folder, self.drawover_options, self.capture.true_fps, self)
        drawover_res = drawover.exec()
        self.update_drawover_settings(drawover)
        self.setVisible(True)
        if drawover_res == 0:
            self.end_capture_ui()
            return

        self.capture.encode(drawover.encode_options)
        drawover.deleteLater()

    def encoding_done(self, filepath):
        if filepath:
            filename = os.path.basename(filepath)
            new_filepath = QFileDialog.getSaveFileName(self, "Save Video", os.path.expanduser("~") + "/" + filename, f"Videos (*.{self.capture.v_ext})")
            
            if new_filepath[0]:
                shutil.move(filepath, new_filepath[0])
        
        self.end_capture_ui()

    def set_mask(self):
        self.timer.stop()
        self.hide()
        empty_region = QRegion(QRect(QPoint(8,43), self.frame.size() - QSize(16, 51)), QRegion.RegionType.Rectangle)
        region = QRegion(QRect(QPoint(-2,-2), self.frame.size() + QSize(4, 4)), QRegion.RegionType.Rectangle)
        self.setMask(region - empty_region)
        self.body_layout.setCurrentIndex(0)
        self.show()

    def close_app(self):
        self.close()
        self.destroy()

    def hide_app(self):
        if self.capture.fullscreen and self.hide_on_record:
            self.hide()
            self.tray_icon.show()
    
    def stop_capture(self):
        self.capture.stop()

    def set_quality(self, value):
        self.capture.quality = value

    def set_fullscreen(self, value=True):
        self.block_resize_event = True
        if value:
            self.fullscreen_button.setIcon(QIcon(f"{app_path}/icon/bounding-box-circles.png"))
            self.setFixedSize(self.minimum_header_width, self.minimum_header_height) # prevent manual resizing height
            self.clearMask()
        else:
            self.fullscreen_button.setIcon(QIcon(f"{app_path}/icon/display.png"))
            self.setMaximumSize(16777215, 16777215) # remove fixed height
            self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
            self.resize(self.record_width, self.record_height)
            self.set_mask()
        
        self.capture.fullscreen = value
        self.block_resize_event = False

    def set_framerate(self, value):
        self.capture.fps = value
    
    def set_hide_on_record(self, value):
        self.hide_on_record = value
    
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
        self.block_resize_event = True
        self.timer.stop()
        if value:
            self.settings_widget.show()
            # self.body_layout.setCurrentIndex(2)
            # self.clearMask()
            # self.settings_button.setIcon(QIcon(f"{dir_path}/icon/gear-fill.png"))
            # self.record_button_grp.hide()
            # self.snapshot_button.hide()
            # self.fullscreen_button.hide()
            # if self.capture.fullscreen:
            #     self.setMaximumSize(16777215, 16777215) # remove fixed height
            #     self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
            # self.resize(self.settings_width, self.settings_height)
        else:
            self.settings_widget.hide()
            # self.body_layout.setCurrentIndex(0)
            # self.settings_button.setIcon(QIcon(f"{dir_path}/icon/gear.png"))
            # self.record_button_grp.show()
            # self.snapshot_button.show()
            # self.fullscreen_button.show()
            # if self.capture.fullscreen:
            #     self.setFixedSize(self.minimum_header_width, self.minimum_header_height)
            # else:
            #     self.resize(self.record_width, self.record_height)
            # self.set_mask()
            
        self.block_resize_event = False

    def mousePressEvent(self, event):
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

    def resizeEvent(self, event):
        self.frame.setGeometry(0, 0, event.size().width(), event.size().height())
        self.resize_grips()

        if self.block_resize_event:
            return

        # if event.size().height() < 100:
        #     self.resize(self.width(), 45)
        # else:
        #     self.resize(self.width(), event.size().height())
            
        self.record_height = event.size().height()
        self.record_width = event.size().width()

        self.info_size_label.setText(f"{self.body_widget.width()}x{self.body_widget.height()}")
        self.body_layout.setCurrentIndex(1)

        self.clearMask()
        self.timer.start(1000)

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
    hide_app_signal = Signal()

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
        self.ffmpeg_flags = {"gifmd": '-quality 50 -loop 0',
                             "gifhi": '-vf "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" -quality 100 -loop 0',
                             "mp4md": '-vf scale="trunc(iw/2)*2:trunc(ih/2)*2" -crf 32',
                             "mp4hi": '-vf scale="trunc(iw/2)*2:trunc(ih/2)*2" -crf 18',
                             "webmmd": '-crf 32 -b:v 0',
                             "webmhi": '-crf 18 -b:v 0'}
        self.fmt = "06d"
        self.fps = 15
        self.true_fps = 15 # Takes dropped / missed frames into account, otherwise it will play faster on drawover
        self.delay = 0
        self.duration = 0

    def run(self):
        self.halt = False
        if self.mode == "record":
            self.delay_countdown()
            if self.halt:
                self.capture_stopped_signal.emit()
                self.quit()
                return
            self.hide_app_signal.emit()
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
                    self.run_timer_signal.emit(seconds)
                if self.duration != 0 and total_time >= self.duration:
                    self.halt = True

            self.stop_capture_time = time.time()
            self.true_fps = int((float(self.capture_count) / (self.stop_capture_time-self.start_capture_time))+0.5)
            self.recording_done_signal.emit(self.current_cache_folder)
        elif self.mode == "encode":
            if self.encode_options and self.encode_options["drawover_image_path"]:
                self._drawover()
            video_file = self.encode_video()
            self.encoding_done_signal.emit(video_file)
        elif self.mode == "snapshot":
            self.delay_countdown()
            if self.halt:
                self.capture_stopped_signal.emit()
                self.quit()
                return
            self.hide_app_signal.emit()
            time.sleep(.1)
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
        for i in range(*rng):
            filename = f'{self.current_cache_folder}/pypeek_{self.UID}_{str(i).zfill(6)}.jpg'
            pixmap = QPixmap(filename)
            painter = QPainter(pixmap)
            painter.drawPixmap(pos, drawover_pixmap)
            painter.end()
            pixmap.save(filename, "jpg", 100)

    def encode_video(self):
        start_number = 0
        vframes = self.capture_count
        if self.encode_options and self.encode_options["drawover_range"]:
            start_number = self.encode_options["drawover_range"][0]
            vframes = self.encode_options["drawover_range"][1] - self.encode_options["drawover_range"][0]
        fprefix = (f'{self.current_cache_folder}/pypeek_{self.UID}_')
        vidfile = f"{self.current_cache_folder}/pypeek_{self.UID}.{self.v_ext}"
        systemcall = str(self.ffmpeg_bin)+" -r " + str(self.true_fps) + " -y"
        systemcall += " -start_number " + str(start_number)
        systemcall += " -i " + str(fprefix)+"%"+str(self.fmt)+".jpg"
        systemcall += " -vframes " + str(vframes)
        systemcall += " "+self.ffmpeg_flags[self.v_ext + self.quality]
        systemcall += " "+str(vidfile)
        try:
            subprocess.run(systemcall, shell=True, check=True)
        except subprocess.CalledProcessError as e:
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
        filename = f'{self.current_cache_folder}/pypeek_{self.UID}.jpg'
        pixmap = QPixmap(filename)
        painter = QPainter(pixmap)
        painter.drawPixmap(QPoint(), drawover_pixmap)
        painter.end()
        pixmap.save(filename, "jpg", 100)
        return filename

    def clear_cache_files(self):
        if os.path.exists(self.current_cache_folder):
            shutil.rmtree(self.current_cache_folder)
    
    def clear_cache_dir(self):
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)

    def _snapshot(self, capture_count=None):
        screenshot = QScreen.grabWindow(QApplication.instance().primaryScreen())
        if self.show_cursor:
            painter = QPainter(screenshot)
            painter.drawPixmap(QCursor.pos(), self.cursor_image)
            painter.end()
        
        pr = QScreen.devicePixelRatio(QApplication.instance().primaryScreen())
        screenshot = screenshot.scaledToWidth(int(screenshot.size().width()/pr), Qt.TransformationMode.SmoothTransformation)
        if not self.fullscreen:
            screenshot = screenshot.copy(self.pos_x, self.pos_y, self.width, self.height)

        not os.path.exists(self.current_cache_folder) and os.makedirs(self.current_cache_folder)
        file_path = (f'{self.current_cache_folder}/pypeek_{self.UID}.jpg')
        file_path = file_path[:-4] + f'_{capture_count:06d}.jpg' if capture_count != None else file_path

        screenshot.save(file_path, 'jpg', 100)
        return file_path

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
        except:
            pass
            
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


def _show():
    app = QApplication(sys.argv)
    window = PyPeek()
    app.exec()
    if window.needs_restart:
        _show()

def show():
    if len(sys.argv) > 1:
        if sys.argv[1] == "shortcut":
            create_shortcut()
            return
            
    _show()
