import os, shutil, time, subprocess, tempfile, configparser, sys, static_ffmpeg
from PyQt6.QtWidgets import QMainWindow, QFrame, QVBoxLayout, \
    QBoxLayout, QMenu, QWidgetAction, QRadioButton, QHBoxLayout, \
    QStackedLayout, QWidget, QLabel, QScrollArea, QApplication, \
    QSpinBox, QCheckBox, QPushButton, QSizeGrip, QFileDialog
from PyQt6.QtCore import QObject, Qt, QSize, QPoint, QEvent, QTimer, QThread, pyqtSignal as SIGNAL, pyqtSlot as SLOT
from PyQt6.QtGui import QPixmap, QPainter, QActionGroup, QRegion, QIcon, QWindow, QCursor, QScreen, QGuiApplication

__all__ = ['run']

static_ffmpeg.add_paths()
dir_path = os.path.dirname(os.path.realpath(__file__))

class Peek(QMainWindow):
    def __init__(self):
        super().__init__()

        # Settings
        self.capture = Capture()
        self.capture.c.capturing_done_signal.connect(self.capturing_done)
        self.capture.c.countdown_signal.connect(self.countdown)
        self.capture.c.run_timer_signal.connect(self.run_timer)

        self.capture.show_cursor = True
        self.capture.fullscreen = False
        self.capture.v_ext = "gif" # gif, mp4, webm
        self.capture.fps = 15
        self.capture.quality = "hi" # md, hi
        self.capture.delay = 3
        self.record_width = 601
        self.record_height = 401
        self.pos_x = 100
        self.pos_y = 100

        # load settings from json file
        self.load_settings()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.set_mask)
        self.drag_start_position = None
        self.recording = False
        self.showing_settings = False
        self.settings_width = 600
        self.settings_height = 400
        self.minimum_header_width = 340
        self.minimum_header_height = 45
        self.minimum_body_height = 100
        self.block_resize_event = False
        self.setStyleSheet("* {font-size: 15px; color: #ddd;}")

        self.header_widget = self.create_header_widget()
        self.body_widget = self.create_body_widget()

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
        self.grip = QSizeGrip(self)
        self.grip.resize(20, 20)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("Peek")
        self.resize(self.record_width, self.record_height)
        self.move(self.pos_x, self.pos_y)
        self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
        self.show()
        self.set_mask()
    
    def load_settings(self):
        home = os.path.expanduser('~')
        config_file = os.path.join(home, '.peekconfig')
        if not os.path.exists(config_file):
            return

        config = configparser.ConfigParser()
        config.read(config_file)

        self.capture.show_cursor = config.getboolean('capture', 'show_cursor')
        self.capture.fullscreen = config.getboolean('capture', 'fullscreen')
        self.capture.v_ext = config.get('capture', 'v_ext')
        self.capture.fps = config.getint('capture', 'fps')
        self.capture.quality = config.get('capture', 'quality')
        self.capture.delay = config.getint('capture', 'delay')
        self.record_width = config.getint('capture', 'width')
        self.record_height = config.getint('capture', 'height')
        self.pos_x = config.getint('capture', 'pos_x')
        self.pos_y = config.getint('capture', 'pos_y')
    
    def save_settings(self):
        home = os.path.expanduser('~')
        config_file = os.path.join(home, '.peekconfig')
        config = configparser.ConfigParser()

        config['capture'] = {
            'show_cursor': str(self.capture.show_cursor),
            'fullscreen': str(self.capture.fullscreen),
            'v_ext': self.capture.v_ext,
            'fps': str(self.capture.fps),
            'quality': self.capture.quality,
            'delay': str(self.capture.delay),
            'width': str(self.record_width),
            'height': str(self.record_height),
            'pos_x': str(self.pos().x()),
            'pos_y': str(self.pos().y())
        }

        with open(config_file, 'w') as config_file:
            config.write(config_file)

    def reset_settings(self):
        self.capture.show_cursor = True
        self.capture.fullscreen = False
        self.capture.v_ext = "gif"
        self.capture.fps = 15
        self.capture.quality = "hi"
        self.capture.delay = 3
        self.record_width = 600
        self.record_height = 400
        self.save_settings()
        run()

    def create_header_widget(self):
        self.snapshot_button = Peek.create_button("", f"{dir_path}/icon/camera.png", "#0d6efd", "#0b5ed7", "#0a58ca" )
        self.snapshot_button.clicked.connect(self.snapshot)

        self.record_button = Peek.create_button(f"{self.capture.v_ext.upper()}", f"{dir_path}/icon/record-fill.png", "#0d6efd", "#0b5ed7", "#0a58ca" )
        self.record_button.setFixedWidth(84)
        self.record_button.clicked.connect(self.record)

        self.stop_button = Peek.create_button("0:00", f"{dir_path}/icon/stop-fill.png", "#dc3545", "#dd3d4c", "#db2f3f" )
        self.stop_button.clicked.connect(self.record)
        self.stop_button.setFixedWidth(114)
        # self.stop_button.setStyleSheet(self.stop_button.styleSheet() + "QPushButton { text-align:left; }")
        self.stop_button.hide()

        self.fullscreen_button = Peek.create_button("", f"{dir_path}/icon/fullscreen.png" )
        self.fullscreen_button.clicked.connect(lambda: self.set_fullscreen(not self.capture.fullscreen))


        self.menu_button = Peek.create_button("", "", "#0d6efd", "#0b5ed7", "#0a58ca")
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

        action3 = QWidgetAction(self.menu)
        action3.setActionGroup(group)
        self.webm_radio = QRadioButton("webm")
        self.webm_radio.setFixedHeight(25)
        action3.setDefaultWidget(self.webm_radio)
        self.menu.addAction(action3)
        self.menu.addSeparator()

        self.menu_button.setMenu(self.menu)

        self.gif_radio.toggled.connect(self.update_record_format)
        self.mp4_radio.toggled.connect(self.update_record_format)
        self.webm_radio.toggled.connect(self.update_record_format)

        # set checked radio button
        if self.capture.v_ext == "gif":
            self.gif_radio.setChecked(True)
        elif self.capture.v_ext == "mp4":
            self.mp4_radio.setChecked(True)
        elif self.capture.v_ext == "webm":
            self.webm_radio.setChecked(True)

        self.record_button_grp = Peek.make_group_button(self.record_button, self.menu_button)

        self.settings_button = Peek.create_button("", f"{dir_path}/icon/gear.png")
        # self.settings_button.setFixedSize(30, 30)
        self.settings_button.clicked.connect(lambda : self.show_settings(not self.showing_settings))

        self.close_button = Peek.create_button("", f"{dir_path}/icon/x.png")
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
        self.settings_widget = self.create_settings_widget()

        self.body_layout = QStackedLayout()
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.addWidget(self.record_area_widget)
        self.body_layout.addWidget(self.info_widget)
        self.body_layout.addWidget(self.settings_widget)
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
        self.cursor_widget = Peek.create_row_widget("Cursor", "Capture mouse cursor", Peek.create_checkbox("", self.capture.show_cursor, self.show_cursor ))
        self.framerate_widget = Peek.create_row_widget("Frame Rate", "Captured frames per second", Peek.create_spinbox(self.capture.fps, 1, 60, self.set_framerate ))
        self.quality_widget = Peek.create_row_widget("Quality", "Set the quality of the video", Peek.create_radio_button({"md":"Medium", "hi":"High"}, self.capture.quality, self.set_quality))
        self.delay_widget = Peek.create_row_widget("Delay Start", "Set the delay before the recording starts", Peek.create_spinbox(self.capture.delay, 0, 10, self.set_delay_start ))
        self.reset_widget = Peek.create_row_widget("Reset And Restart", "Reset all settings and restart the app", Peek.create_button("Reset Settings", callback = self.reset_settings))
        self.copyright_widget = Peek.create_row_widget("Peek 2.3.6", "Cross platform screen recorder", Peek.create_hyperlink("Website", "https://github.com/firatkiral/pypeek"))

        self.settings_layout = QVBoxLayout()
        self.settings_layout.setContentsMargins(20, 10, 20, 10)
        self.settings_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.settings_layout.addWidget(self.cursor_widget)
        self.settings_layout.addWidget(Peek.create_h_divider())
        self.settings_layout.addWidget(self.framerate_widget)
        self.settings_layout.addWidget(Peek.create_h_divider())
        self.settings_layout.addWidget(self.quality_widget)
        self.settings_layout.addWidget(Peek.create_h_divider())
        self.settings_layout.addWidget(self.delay_widget)
        self.settings_layout.addWidget(Peek.create_h_divider())
        self.settings_layout.addWidget(self.reset_widget)
        self.settings_layout.addWidget(Peek.create_h_divider())
        self.settings_layout.addWidget(self.copyright_widget)
        
        settings_widget = QWidget()
        settings_widget.setStyleSheet("QWidget {background-color: #3a3a3a; border: none;}")
        settings_widget.setLayout(self.settings_layout)

        scroll_area = QScrollArea()
        scroll_area.setStyleSheet("QScrollArea {background-color: #3a3a3a; border: none;}")
        scroll_area.setWidget(settings_widget)
        scroll_area.setWidgetResizable(True)

        return scroll_area

    def update_record_format(self):
        if self.gif_radio.isChecked():
            self.capture.v_ext = "gif"
        elif self.mp4_radio.isChecked():
            self.capture.v_ext = "mp4"
        elif self.webm_radio.isChecked():
            self.capture.v_ext = "webm"
        self.record_button.setText(f"{self.capture.v_ext.upper()}")

    def set_mask(self):
        self.timer.stop()
        self.hide()
        geo = self.frame.geometry()
        region = QRegion(self.frame.geometry(), QRegion.RegionType.Rectangle)
        geo = self.frame.geometry()
        geo.moveTopLeft(QPoint(8, 43))
        geo.setWidth(geo.width() - 16)
        geo.setHeight(geo.height() - 51)
        region -= QRegion(geo, QRegion.RegionType.Rectangle)
        self.setMask(region)
        if not self.showing_settings:
            self.body_layout.setCurrentIndex(0)
        self.show()

    def close_app(self):
        if self.capture.isRunning():
            self.capture.terminate()
            self.capture.clear_cache_files()
        self.save_settings()
        self.close()

    def record(self):
        if self.recording:
            self.record_button_grp.show()
            self.stop_button.hide()
            self.capture.stop()
        else:
            self.record_button_grp.hide()
            self.stop_button.show()
            self.prepare_capture()
            self.capture.start()
        
    def snapshot(self):
        self.prepare_capture()
        filepath = self.capture.snapshot()
        filename = os.path.basename(filepath)
        new_filepath = QFileDialog.getSaveFileName(self, "Save Image", os.path.expanduser("~") + "/" + filename, "Images (*.jpg)")
        
        if new_filepath[0]:
            shutil.move(filepath, new_filepath[0])
        
        self.end_capture()
    
    def prepare_capture(self):
        self.capture.pos_x, self.capture.pos_y = Peek.get_global_position(self.record_area_widget)
        self.capture.width = self.record_area_widget.width()
        self.capture.height = self.record_area_widget.height()
        self.grip.hide()
        self.snapshot_button.setDisabled(True)
        self.record_button.setDisabled(True)
        self.record_button.setIconSize(QSize(0, 0))
        self.record_button.setText("Working...")
        self.menu_button.setDisabled(True)
        self.fullscreen_button.setDisabled(True)
        self.settings_button.setDisabled(True)
        self.recording = True
        if not self.capture.fullscreen:
            self.setFixedSize(self.record_width, self.record_height)
        
    def end_capture(self):
        self.snapshot_button.setDisabled(False)
        self.record_button.setDisabled(False)
        self.record_button.setText(self.capture.v_ext.upper())
        self.record_button.setIconSize(QSize(20, 20))
        self.stop_button.setText("0:00")
        self.menu_button.setDisabled(False)
        self.fullscreen_button.setDisabled(False)
        self.settings_button.setDisabled(False)
        self.close_button.setDisabled(False)
        self.grip.show()
        self.recording = False
        if not self.capture.fullscreen:
            self.block_resize_event = True
            self.setMaximumSize(16777215, 16777215) # remove fixed height
            self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
            self.resize(self.record_width, self.record_height)
            self.block_resize_event = False
        self.capture.clear_cache_files()

    @SLOT(str, name="capturing_done")
    def capturing_done(self, filepath):
        if filepath:
            filename = os.path.basename(filepath)
            new_filepath = QFileDialog.getSaveFileName(self, "Save Video", os.path.expanduser("~") + "/" + filename, f"Videos (*.{self.capture.v_ext})")
            
            if new_filepath[0]:
                shutil.move(filepath, new_filepath[0])
        
        self.end_capture()

    @SLOT(int, name="countdown")
    def countdown(self, value):
        self.stop_button.setText(f' {value}')
        if value == 0:
            self.stop_button.setText("0:00")
    
    @SLOT(int, name="run_timer")
    def run_timer(self, value):
        minutes = value // 60
        seconds = value % 60
        self.stop_button.setText(f'{minutes:01d}:{seconds:02d}')

    def set_quality(self, value):
        self.capture.quality = value

    def set_fullscreen(self, value):
        self.block_resize_event = True
        if value:
            self.fullscreen_button.setIcon(QIcon(f"{dir_path}/icon/fullscreen-exit.png"))
            self.setFixedSize(self.minimum_header_width, self.minimum_header_height) # prevent manual resizing height
            self.clearMask()
        else:
            self.fullscreen_button.setIcon(QIcon(f"{dir_path}/icon/fullscreen.png"))
            self.setMaximumSize(16777215, 16777215) # remove fixed height
            self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
            self.resize(self.record_width, self.record_height)
            self.set_mask()
        
        self.capture.fullscreen = value
        self.block_resize_event = False

    def set_framerate(self, value):
        self.capture.fps = value
    
    def set_delay_start(self, value):
        self.capture.delay = value
    
    def show_cursor(self, value):
        self.capture.show_cursor = value

    def show_settings(self, value):
        self.block_resize_event = True
        self.timer.stop()
        if value:
            self.body_layout.setCurrentIndex(2)
            self.clearMask()
            self.settings_button.setIcon(QIcon(f"{dir_path}/icon/gear-fill.png"))
            self.record_button_grp.hide()
            self.snapshot_button.hide()
            self.fullscreen_button.hide()
            if self.capture.fullscreen:
                self.setMaximumSize(16777215, 16777215) # remove fixed height
                self.setMinimumSize(self.minimum_header_width, self.minimum_body_height)
            self.resize(self.settings_width, self.settings_height)
        else:
            self.body_layout.setCurrentIndex(0)
            self.settings_button.setIcon(QIcon(f"{dir_path}/icon/gear.png"))
            self.record_button_grp.show()
            self.snapshot_button.show()
            self.fullscreen_button.show()
            if self.capture.fullscreen:
                self.setFixedSize(self.minimum_header_width, self.minimum_header_height)
            else:
                self.resize(self.record_width, self.record_height)
            self.set_mask()
            
        self.showing_settings = value
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
        self.capture.pos_x, self.capture.pos_y = Peek.get_global_position(self.record_area_widget)

    def resizeEvent(self, event):
        self.frame.setGeometry(0, 0, event.size().width(), event.size().height())

        if self.block_resize_event:
            return

        # if event.size().height() < 100:
        #     self.resize(self.width(), 45)
        # else:
        #     self.resize(self.width(), event.size().height())
            
        if self.showing_settings:
            self.settings_height = event.size().height()
            self.settings_width = event.size().width()
        else:
            self.record_height = event.size().height()
            self.record_width = event.size().width()

            self.info_size_label.setText(f"{self.body_widget.width()}x{self.body_widget.height()}")
            self.body_layout.setCurrentIndex(1)

            self.clearMask()
            self.timer.start(1000)
        
        self.grip.move(self.frame.width() - 20, self.frame.height() - 20)

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

class Communicate(QObject):
    capturing_done_signal = SIGNAL(str)
    countdown_signal = SIGNAL(int)
    run_timer_signal = SIGNAL(int)

class Capture(QThread):
    def __init__(self):
        QThread.__init__(self)
        self.fullscreen = False
        self.show_cursor = True
        self.arrow = QPixmap(f"{dir_path}/icon/cursor.png")
        self.pos_x = 0
        self.pos_y = 0
        self.width = 0
        self.height = 0
        self.UID = ""
        self.capture_count = 0
        self.halt = False
        self.cache_folder = f'{tempfile.gettempdir()}/peekcache/{time.strftime("%H%M%S")}' # different folder for each capture
        self.start_capture_time = 0
        self.start_capture_time = 0
        self.v_ext = "gif"
        self.ffmpeg_bin = "static_ffmpeg"
        self.quality = "md" # md or hi
        self.ffmpeg_flags = {"gifmd": '-quality 50 -loop 0',
                             "gifhi": '-vf "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" -quality 100 -loop 0',
                             "mp4md": '-vf scale="trunc(iw/2)*2:trunc(ih/2)*2" -crf 32',
                             "mp4hi": '-vf scale="trunc(iw/2)*2:trunc(ih/2)*2" -crf 18',
                             "webmmd": '-crf 32 -b:v 0',
                             "webmhi": '-crf 18 -b:v 0'}
        self.fmt = "06d"
        self.fps = 15
        self.delay = 0

        self.c = Communicate()

    def run(self):
        self.halt = False
        if self.delay > 0:
            delay = self.delay
            st = time.time()
            self.c.countdown_signal.emit(delay)
            while delay > 0 and not self.halt:
                passed = time.time()-st
                if passed >= 1:
                    delay -= 1
                    self.c.countdown_signal.emit(delay)
                    st = time.time()
            
        if self.halt:
            self.c.capturing_done_signal.emit(None)
            self.quit()
            return
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
                self.c.run_timer_signal.emit(seconds)

        self.stop_capture_time = time.time()
        video_file = self.encode_video()
        self.c.capturing_done_signal.emit(video_file)
        self.quit()

    def encode_video(self):
        fprefix = (f'{self.cache_folder}/peek_{self.UID}_')
        fps = int((float(self.capture_count) / (self.stop_capture_time-self.start_capture_time))+0.5)
        vidfile = f"{self.cache_folder}/peek_{self.UID}.{self.v_ext}"
        systemcall = str(self.ffmpeg_bin)+" -r " + str(fps) + " -y"
        systemcall += " -i " + str(fprefix)+"%"+str(self.fmt)+".jpg"
        systemcall += " "+self.ffmpeg_flags[self.v_ext + self.quality]
        systemcall += " "+str(vidfile)
        print(systemcall)
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
        return self._snapshot()

    def clear_cache_files(self):
        if os.path.exists(self.cache_folder):
            shutil.rmtree(self.cache_folder)

    def _snapshot(self, capture_count=None):
        screenshot = QScreen.grabWindow(app.primaryScreen())
        if self.show_cursor:
            painter = QPainter(screenshot)
            painter.drawPixmap(QCursor.pos(), self.arrow)
            painter.end()
        
        pr = QScreen.devicePixelRatio(app.primaryScreen())
        screenshot = screenshot.scaledToWidth(int(screenshot.size().width()/pr), Qt.TransformationMode.SmoothTransformation)
        if not self.fullscreen:
            screenshot = screenshot.copy(self.pos_x, self.pos_y, self.width, self.height)

        not os.path.exists(self.cache_folder) and os.makedirs(self.cache_folder)
        file_path = (f'{self.cache_folder}/peek_{self.UID}.jpg')
        file_path = file_path[:-4] + f'_{capture_count:06d}.jpg' if capture_count != None else file_path

        screenshot.save(file_path, 'jpg')
        return file_path

window = app = None
def run():
    global window, app

    if window:
        window.destroy()

    if app == None:
        app = QApplication(sys.argv)
    
    window = Peek()
    app.exec()