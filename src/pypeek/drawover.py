import sys, os, tempfile
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtCore import Qt
from math import radians, cos, sin, atan2, pi
from .undo import Undo, ClearSceneCmd, AddSceneItemCmd
from .qrangeslider import QRangeSlider

if getattr(sys, 'frozen', False):
    dir_path = os.path.abspath(os.path.dirname(sys.executable))
elif __file__:
    dir_path = os.path.abspath(os.path.dirname(__file__))

class DrawOver(QDialog):
    def __init__(self, image_path=""):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        # self.setWindowModality(Qt.ApplicationModal)

        self.image_width = 800
        self.image_height = 600

        self.is_sequence = False
        self.drawover_image_path = None
        self.out_filename = "drawover.png"
        self.out_path = f'{tempfile.gettempdir()}/pypeek'
        if os.path.isdir(image_path):
            self.out_path = image_path
            image_dir = QDir(image_path)
            self.image_filenames = image_dir.entryList(['*.jpg'], QDir.Filter.Files, QDir.SortFlag.Name)
            self.is_sequence = True
            self.bg_pixmap = QPixmap(os.path.join(image_path, self.image_filenames[0]))
            self.image_width = self.bg_pixmap.width()
            self.image_height = self.bg_pixmap.height()
            self.frame_rate = 15
            self.frame_count = len(self.image_filenames) - 1
            self.duration = (float(self.frame_count) / self.frame_rate)*1000
        elif os.path.isfile(image_path):
            self.bg_pixmap = QPixmap(image_path)
            self.image_width = self.bg_pixmap.width()
            self.image_height = self.bg_pixmap.height()
            self.out_path = os.path.dirname(image_path)
        else:
            self.bg_pixmap = QPixmap(self.image_width, self.image_height)
            self.bg_pixmap.fill(Qt.white)

        # Undo/Redo
        self.undo_history = Undo()
        undo_shortcut = QShortcut(QKeySequence('Ctrl+Z'), self)
        redo_shortcut = QShortcut(QKeySequence('Shift+Ctrl+Z'), self)
        undo_shortcut.activated.connect(self.undo_history.undo)
        redo_shortcut.activated.connect(self.undo_history.redo)

        # Variables
        self.font_size = 13.0
        self.current_color = "red"
        self.dragging = False
        self.current_text_item = None
        self.current_pen = QPen(QColor(self.current_color), 2)
        self.current_brush = QBrush(QColor(self.current_color))

        self.items = []
        self.arrow_polygon = QPolygon([QPoint(0,0), QPoint(-10,5),QPoint(-10,-5)])
        
        # Toolbar
        self.toolbar = self.create_toolbar()
        # self.addToolBar(self.toolbar)

        # Canvas
        self.canvas_width = self.image_width
        self.canvas_height = self.image_height
        self.canvas_scaled_width = self.image_width
        self.canvas_scaled_height = self.image_height
        self.canvas_offset_x = 0
        self.canvas_offset_y = 0
        self.canvas_scale_factor = 1
        self.prev_pixmap = None

        self.bg_image = self.create_bg_image()
        self.canvas = self.create_canvas()
        self.text_widget = QWidget()
        self.text_widget.setAttribute(Qt.WA_TransparentForMouseEvents)

        canvas_layout = QStackedLayout()
        canvas_layout.setStackingMode(QStackedLayout.StackAll)
        canvas_layout.addWidget(self.bg_image)
        canvas_layout.addWidget(self.canvas)
        canvas_layout.addWidget(self.text_widget)

        self.canvas_widget = QWidget()
        self.canvas_widget.setLayout(canvas_layout)
        self.canvas_widget.resize(self.image_width, self.image_height)

        self.scene = QGraphicsScene(self)
        self.scene.addWidget(self.canvas_widget)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.view.viewport().setAttribute(Qt.WA_AcceptTouchEvents)

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

        save_button = QPushButton("Save", self)
        save_button.setFixedWidth(100)
        save_button.clicked.connect(self.save_drawover_file)
        cancel_button = QPushButton("Cancel", self)
        cancel_button.setFixedWidth(100)
        cancel_button.clicked.connect(self.reject)
        save_layout = QHBoxLayout()
        save_layout.setSpacing(10)
        save_layout.setContentsMargins(20,20,20,20)
        save_layout.addStretch(1)
        save_layout.addWidget(cancel_button)
        save_layout.addWidget(save_button)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.toolbar)
        main_layout.addLayout(canvas_margin_layout, 1)
        self.is_sequence and main_layout.addWidget(self.create_timeline(), 0)
        main_layout.addLayout(save_layout, 0)

        self.setLayout(main_layout)
        self.resize(self.image_width + 40, self.image_height+220 if self.is_sequence else self.image_height+130)
        self.set_tool("select")

    @Slot()
    def zoom_in(self):
        scale_tr = QTransform()
        scale_tr.scale(1.1, 1.1)

        tr = self.view.transform() * scale_tr
        self.view.setTransform(tr)

    @Slot()
    def zoom_out(self):
        scale_tr = QTransform()
        scale_tr.scale(.9, .9)

        tr = self.view.transform() * scale_tr
        self.view.setTransform(tr)
    
    @Slot()
    def reset_zoom(self):
        self.view.resetTransform()
    
    def clear_canvas(self):
        self.undo_history.push(ClearSceneCmd(self))

    def create_toolbar(self):
        # Create a toolbar and add it to the main window
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFixedHeight(30)

        tool_button_group = QActionGroup(self)

        # create grab tool
        self.select_tool = QAction(QIcon(f"{dir_path}/icon/cursor-light.png"), "", self)
        self.select_tool.setToolTip("Select Tool")
        self.select_tool.setCheckable(True)
        tool_button_group.addAction(self.select_tool)
        self.select_tool.triggered.connect(lambda: self.set_tool("select"))
        toolbar.addAction(self.select_tool)
        self.select_tool.setChecked(True)
        
        self.pen_tool = QAction(QIcon(f"{dir_path}/icon/pencil.png"), "", self)
        self.pen_tool.setToolTip("Pen Tool")
        self.pen_tool.setCheckable(True)
        tool_button_group.addAction(self.pen_tool)
        self.pen_tool.triggered.connect(lambda: self.set_tool("pen"))
        toolbar.addAction(self.pen_tool)

        self.shape_tool = self.create_shape_tool()
        self.shape_tool.setToolTip("Shape Tool")
        self.shape_tool.setCheckable(True)
        tool_button_group.addAction(self.shape_tool)
        self.shape_tool.triggered.connect(lambda: self.set_tool(self.shape_tool.shape))
        toolbar.addAction(self.shape_tool)

        self.text_tool = QAction(QIcon(f"{dir_path}/icon/fonts.png"), "", self)
        self.text_tool.setToolTip("Text Tool")
        self.text_tool.setCheckable(True)
        tool_button_group.addAction(self.text_tool)
        self.text_tool.triggered.connect(lambda: self.set_tool("text"))
        toolbar.addAction(self.text_tool)

        self.clear_tool = QAction(QIcon(f"{dir_path}/icon/broom.png"), "", self)
        self.clear_tool.setToolTip("Clear Canvas")
        toolbar.addAction(self.clear_tool)
        self.clear_tool.triggered.connect(self.clear_canvas)

        # add separator
        toolbar.addSeparator()

        # Set up the color picker
        self.color_picker = self.create_color_tool()
        self.color_picker.setToolTip("Color Picker")
        toolbar.addWidget(self.color_picker)

        # add separator
        toolbar.addSeparator()

        # add zoom tools
        self.zoom_in_tool = QAction(QIcon(f"{dir_path}/icon/zoom-in.png"), "", self)
        self.zoom_in_tool.setToolTip("Zoom In")
        self.zoom_in_tool.triggered.connect(self.zoom_in)
        toolbar.addAction(self.zoom_in_tool)

        self.zoom_out_tool = QAction(QIcon(f"{dir_path}/icon/zoom-out.png"), "", self)
        self.zoom_out_tool.setToolTip("Zoom Out")
        self.zoom_out_tool.triggered.connect(self.zoom_out)
        toolbar.addAction(self.zoom_out_tool)

        self.reset_zoom_tool = QAction(QIcon(f"{dir_path}/icon/zoom-reset.png"), "", self)
        self.reset_zoom_tool.setToolTip("Reset Zoom")
        self.reset_zoom_tool.triggered.connect(self.reset_zoom)
        toolbar.addAction(self.reset_zoom_tool)


        return toolbar
    
    def create_bg_image(self):
        bg_image = QLabel()
        bg_image.setAlignment(Qt.AlignCenter)
        bg_image.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        bg_image.setPixmap(self.bg_pixmap)

        return bg_image

    def update_bg_image(self, image_filename):
        self.bg_pixmap = QPixmap(os.path.join(self.out_path, image_filename))
        self.bg_image.setPixmap(self.bg_pixmap.scaled(self.canvas_width, self.canvas_height, Qt.KeepAspectRatio))

    def save_drawover_file(self):
        if len(self.items) > 0:
            self.drawover_image_path = os.path.join(self.out_path, self.out_filename)
            self.canvas_widget.hide()
            pixmap = QPixmap(self.canvas_width, self.canvas_height)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            self.scene.render(painter)
            painter.end()
            self.canvas_widget.show()
            pixmap.save(self.drawover_image_path, "png")

        self.accept()

    def create_canvas(self):
        canvas = QLabel()
        canvas.setAlignment(Qt.AlignCenter)
        canvas.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.pixmap = QPixmap(self.image_width, self.image_height)
        self.pixmap.fill(Qt.transparent)
        canvas.setPixmap(self.pixmap)

        self.prev_pixmap = self.pixmap
        return canvas

    def create_timeline(self):
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, self.frame_count)
        slider.valueChanged.connect(lambda x: (timeline.blockSignals(True),
                                               timeline.setCurrentTime((x - slider.minimum()) * (1000/self.frame_rate)),
                                               (timeline.stop(), timeline.resume()) if timeline.state() == QTimeLine.State.Running else None,
                                               timeline.blockSignals(False)
                                               ))

        timeline = QTimeLine(self.duration, parent=self)
        timeline.setFrameRange(0, len(self.image_filenames) - 1)
        timeline.setUpdateInterval(1000/self.frame_rate)
        timeline.setLoopCount(1)
        timeline.setEasingCurve(QEasingCurve.Linear)
        timeline.frameChanged.connect(lambda x: (
            slider.blockSignals(True),
            slider.setValue(x),
            self.update_bg_image(self.image_filenames[slider.value()]),
            slider.blockSignals(False),
            ))
        timeline.stateChanged.connect(lambda x: (
            play_button.hide() if x == QTimeLine.State.Running else play_button.show(),
            pause_button.show() if x == QTimeLine.State.Running else pause_button.hide(),
        ))

        play_button = QPushButton("")
        play_button.setFixedWidth(30)
        play_button.setIcon(QIcon(f"{dir_path}/icon/play-fill.png"))
        play_button.clicked.connect(lambda: (
            timeline.start() if slider.value() == slider.maximum() else timeline.resume(),
            play_button.hide(),
            pause_button.show()))

        pause_button = QPushButton("")
        pause_button.setFixedWidth(30)
        pause_button.setIcon(QIcon(f"{dir_path}/icon/pause.png"))
        pause_button.clicked.connect(lambda: (timeline.setPaused(True)))
        pause_button.hide()

        stop_button = QPushButton("")
        stop_button.setFixedWidth(30)
        stop_button.setIcon(QIcon(f"{dir_path}/icon/stop-fill.png"))
        stop_button.clicked.connect(lambda: (timeline.stop(), timeline.setCurrentTime(0)))

        button_layout = QHBoxLayout()
        button_layout.addWidget(play_button)
        button_layout.addWidget(pause_button)
        button_layout.addWidget(stop_button)

        range_slider = QRangeSlider()
        range_slider.setFixedHeight(30)
        range_slider.setMin(0)
        range_slider.setMax(self.frame_count)
        range_slider.setRange(0, self.frame_count)
        range_slider.startValueChanged.connect(lambda x: (
            slider.setMinimum(x),
            timeline.blockSignals(True),
            timeline.setCurrentTime((slider.value() - x) * (1000/self.frame_rate)),
            timeline.blockSignals(False),
            timeline.setFrameRange(x, range_slider.end()),
            timeline.setDuration((range_slider.end() - x) * (1000/self.frame_rate))
            ))
        range_slider.endValueChanged.connect(lambda x: (
            slider.setMaximum(x),
            timeline.setFrameRange(range_slider.start(), x),
            timeline.setDuration((x - range_slider.start()) * (1000/self.frame_rate))
            ))

        range_layout = QStackedLayout()
        range_layout.setStackingMode(QStackedLayout.StackAll)
        range_layout.addWidget(range_slider)

        slider.valueChanged.connect(lambda : self.update_bg_image(self.image_filenames[slider.value()]))

        slider_layout = QHBoxLayout()
        slider_layout.addLayout(button_layout, 0)
        slider_layout.addWidget(slider, 1)

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.addLayout(slider_layout)
        layout.addLayout(range_layout)
        timeline_widget = QWidget()
        # timeline_widget.setStyleSheet( "QWidget {background-color: #2a2a2a; border-radius: 5px; padding: 5px;}")
        timeline_widget.setLayout(layout)
        return timeline_widget

    def create_color_tool(self):
        menu = QMenu(self)
        menu.setContentsMargins(10, 5, 10, 5)

        menu_action = QPushButton("", self)
        menu_action.setStyleSheet(f"QPushButton {{background-color: {self.current_color};}} QPushButton::menu-indicator {{image: none;}}")
        menu_action.setFixedSize(20, 20)
        menu_action.setMenu(menu)

        action = QWidgetAction(menu)
        action_layout = QGridLayout()
        action_layout.setHorizontalSpacing(8)
        action_layout.setVerticalSpacing(16)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_widget = QWidget()
        action_widget.setLayout(action_layout)
        action.setDefaultWidget(action_widget)

        menu.addAction(action)

        def clicked(_color=None):
            self.pick_color(_color)
            menu_action.setStyleSheet(f"QPushButton {{background-color: {self.current_color};}} QPushButton::menu-indicator {{image: none;}}")
            menu.close()

        for i, color in enumerate(['red', 'limegreen', 'blue', 'yellow', 'cyan', 'magenta', 'white', 'black']):
            color_button = QPushButton()
            color_button.setFixedSize(14, 14)
            color_button.setStyleSheet(f"background-color: {color};")
            color_button.clicked.connect(lambda *args, _color=color: clicked(_color))
            action_layout.addWidget(color_button, int(i/3), i%3)
        
        pick_button = QPushButton(QIcon(f"{dir_path}/icon/eyedropper.png"), "")
        pick_button.setFixedSize(14, 14)
        pick_button.setIconSize(QSize(12, 12))
        pick_button.setStyleSheet(f"background-color: transparent;")
        action_layout.addWidget(pick_button, 2, 2)
        pick_button.clicked.connect(clicked)

        return menu_action
        
    def create_shape_tool(self):
        menu = QMenu(self)
        menu.setContentsMargins(0, 5, 0, 5)

        menu_action = QAction(QIcon(f"{dir_path}/icon/slash-lg.png"), "", self)
        menu_action.shape = 'line'
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
            menu_action.shape = _shape
            self.set_tool(_shape)
            menu_action.setIcon(QIcon(f"{dir_path}/icon/{_icon}.png"))
            menu_action.setChecked(True)
            menu.close()

        for shape, icon in {'line':'slash-lg', 'arrow':'arrow-up-right', 'double_arrow':'arrows-angle-expand', 'square':'square', 'circle':'circle' }.items():
            shape_button = QPushButton(QIcon(f"{dir_path}/icon/{icon}.png"), "")
            shape_button.setFixedSize(54, 34)
            shape_button.setIconSize(QSize(24, 24))
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
        elif tool == "square":
            self.set_square_tool()
        elif tool == "circle":
            self.set_circle_tool()
        elif tool == "text":
            self.set_text_tool()
        else:
            self.set_select_tool()

    def set_select_tool(self):
        self.current_tool = "select"

    def set_pen_tool(self):
        self.current_tool = "pen"

    def set_line_tool(self):
        self.current_tool = "line"
    
    def set_arrow_tool(self):
        self.current_tool = "arrow"
    
    def set_double_arrow_tool(self):
        self.current_tool = "double_arrow"
    
    def set_square_tool(self):
        self.current_tool = "square"
    
    def set_circle_tool(self):
        self.current_tool = "circle"

    def set_text_tool(self):
        self.current_tool = "text"

    def pick_color(self, color=None):
        self.current_color = color or  QColorDialog.getColor(self.current_color).name()
        self.current_pen.setColor(self.current_color)
        self.current_brush.setColor(self.current_color)

    def _mousePressEvent(self, e):
        self.start_point = e.position()
        if self.start_point.x() < 0 or self.start_point.y() < 0 or self.start_point.x() > self.canvas.width() or self.start_point.y() > self.canvas.height():
            return
        self.dragging = True
        if self.current_tool == "select":
            self.select_start_point = e.position()
            QApplication.setOverrideCursor(Qt.ClosedHandCursor)
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

            arrow_item = QGraphicsPolygonItem()
            arrow_item.setPos(self.start_point)
            arrow_item.setPen(self.current_pen)
            arrow_item.setBrush(self.current_brush)
            arrow_item.setPolygon(QPolygonF(self.arrow_polygon))

            self.current_arrow_line_item = QGraphicsItemGroup()
            self.current_arrow_line_item.addToGroup(line_item)
            self.current_arrow_line_item.addToGroup(arrow_item)

            self.scene.addItem(self.current_arrow_line_item)
        if self.current_tool == "double_arrow":
            line_item = QGraphicsLineItem()
            line_item.setPen(self.current_pen)
            line_item.setLine(self.start_point.x(), self.start_point.y(), self.start_point.x(), self.start_point.y())

            arrow_item = QGraphicsPolygonItem()
            arrow_item.setPos(self.start_point)
            arrow_item.setPen(self.current_pen)
            arrow_item.setBrush(self.current_brush)
            arrow_item.setPolygon(QPolygonF(self.arrow_polygon))

            arrow_item2 = QGraphicsPolygonItem()
            arrow_item2.setPos(self.start_point)
            arrow_item2.setPen(self.current_pen)
            arrow_item2.setBrush(self.current_brush)
            arrow_item2.setPolygon(QPolygonF(self.arrow_polygon))

            self.current_double_arrow_line_item = QGraphicsItemGroup()
            self.current_double_arrow_line_item.addToGroup(line_item)
            self.current_double_arrow_line_item.addToGroup(arrow_item)
            self.current_double_arrow_line_item.addToGroup(arrow_item2)

            self.scene.addItem(self.current_double_arrow_line_item)
        if self.current_tool == "square":
            self.current_square_item = QGraphicsRectItem()
            self.current_square_item.setPen(self.current_pen)
            self.current_square_item.setBrush(Qt.NoBrush)
            self.current_square_item.setRect(self.start_point.x(), self.start_point.y(), 0, 0)
            self.scene.addItem(self.current_square_item)
        if self.current_tool == "circle":
            self.current_circle_item = QGraphicsEllipseItem()
            self.current_circle_item.setPen(self.current_pen)
            self.current_circle_item.setBrush(Qt.NoBrush)
            self.current_circle_item.setRect(self.start_point.x(), self.start_point.y(), 0, 0)
            self.scene.addItem(self.current_circle_item)
        if self.current_tool == "text":
            if self.current_text_item:
                self.setFocus()
                self.current_text_item = None
                return
            text_input = QTextEdit()
            text_input.setUndoRedoEnabled(False)
            text_input.setUndoRedoEnabled(False)
            text_input.setFixedSize(60, 30)
            text_input.setStyleSheet(f"background-color: rgba(0,0,0,0.30); color:{self.current_color};")

            self.current_text_item = QWidget()
            self.current_text_item.setStyleSheet("background-color: transparent;")
            self.current_text_item.setFixedSize(self.image_width, self.image_height)
            text_input.setParent(self.current_text_item)
            self.scene.addWidget(self.current_text_item)

            text_input.move(self.start_point.x(), self.start_point.y())
            text_input.setFocus()

            text_input.textChanged.connect(lambda: (text_input.setFixedSize(text_input.document().idealWidth() + 20,
                                                                            text_input.document().size().height() + 10)))

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
        if self.current_tool == "square" and self.current_square_item is not None:
            self.current_square_item.setRect(self.start_point.x(), self.start_point.y(), self.end_point.x() - self.start_point.x(), self.end_point.y() - self.start_point.y())
        if self.current_tool == "circle" and self.current_circle_item is not None:
            self.current_circle_item.setRect(self.start_point.x(), self.start_point.y(), self.end_point.x() - self.start_point.x(), self.end_point.y() - self.start_point.y())
    
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
        if self.current_tool == "square" and self.current_square_item is not None:
            self.undo_history.push(AddSceneItemCmd(self, self.current_square_item))
            self.current_square_item = None
        if self.current_tool == "circle" and self.current_circle_item is not None:
            self.undo_history.push(AddSceneItemCmd(self, self.current_circle_item))
            self.current_circle_item = None
        if self.current_tool == "text" and self.current_text_item is not None:
            self.undo_history.push(AddSceneItemCmd(self, self.current_text_item))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DrawOver()
    window.show()
    app.exec()
