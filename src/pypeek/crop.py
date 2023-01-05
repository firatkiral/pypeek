import sys, os
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    app_path = sys._MEIPASS
    # dir_path = os.path.abspath(os.path.dirname(sys.executable))
elif __file__:
    app_path = os.path.abspath(os.path.dirname(__file__))

class Crop(QMainWindow):
    def __init__(self):
        super().__init__()

        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda : (self.size_label.hide(), self.set_mask()))

        self.record_width = 600
        self.record_height = 400
        self.pos_x = 100
        self.pos_y = 100
        self.drag_start_position = None

        self.size_label = QLabel(f"{self.record_width} x {self.record_height}")
        self.size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.size_label.setFixedSize(100, 30)
        self.size_label.hide()
        self.size_label.setStyleSheet("QLabel { color: #eee; }")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(6)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor("#000"))

        self.size_label.setGraphicsEffect(shadow)

        self.setGraphicsEffect(shadow)

        size_layout = QVBoxLayout()
        size_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size_layout.addStretch()
        size_layout.addWidget(self.size_label)

        size_widget = QWidget()
        size_widget.setLayout(size_layout)

        self.move_label = QLabel()
        self.move_label.setPixmap(QPixmap(f"{app_path}/icon/move.png"))
        self.move_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.move_label.setFixedSize(55, 55)
        self.move_label.enterEvent = self.enter_event
        self.move_label.leaveEvent = self.leave_event
        self.move_label.mousePressEvent = self.mouse_press_event
        self.move_label.mouseMoveEvent = self.mouse_move_event
        self.move_label.mouseReleaseEvent = self.mouse_release_event


        move_layout = QVBoxLayout()
        move_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        move_layout.addWidget(self.move_label)

        self.move_widget = QWidget()
        self.move_widget.setLayout(move_layout)

        label_layout = QStackedLayout()
        label_layout.addWidget(size_widget)
        label_layout.addWidget(self.move_widget)
        label_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)

        self.record_widget = QWidget()
        self.record_widget.setLayout(label_layout)
        self.record_widget.setObjectName("record_widget")
        self.record_widget.setStyleSheet("QWidget#record_widget { border: 2px dashed rgba(220, 220, 220, .9);}")

        self.record_layout = QVBoxLayout()
        self.record_layout.setContentsMargins(0,0,0,0)
        self.record_layout.addWidget(self.record_widget)

        self.frame = QFrame(self)
        # self.frame.setFrameStyle(0)
        # self.frame.setStyleSheet("QFrame { border: 3px solid #333; border-radius: 5px;}")
        self.frame.setLayout(self.record_layout)

        self.create_grips()
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.setMinimumSize(50, 50)
        self.show()
        self.move(self.pos_x, self.pos_y)
        self.resize(self.record_width, self.record_height)
        self.set_mask()
    
    def set_mask(self):
        empty_region = QRegion(QRect(QPoint(20,20), self.frame.size() - QSize(40, 40)), QRegion.RegionType.Rectangle)
        region = QRegion(QRect(QPoint(-5,-5), self.frame.size() + QSize(10, 10)), QRegion.RegionType.Rectangle)
        mask = region - empty_region
        mask += QRegion(QRect(self.move_label.mapToParent(QPoint(0,0)), self.move_label.size()), QRegion.RegionType.Rectangle)
        if self.size_label.isVisible():
            mask += QRegion(QRect(self.size_label.mapToParent(QPoint(0,0)), self.size_label.size()), QRegion.RegionType.Rectangle)
        self.setMask( mask)
    
    def create_grips(self):
        self.grip_br = QSizeGrip(self)
        self.grip_br.setStyleSheet("background-color: rgba(220, 220, 220, .9); border-top-left-radius: 6px; border: 2px solid rgba(220, 220, 220, .9);")
        # self.grip_br.setVisible(False)
        self.grip_br.resize(10, 10)
        self.grip_br.move(self.frame.width() - 10, self.frame.height() - 10)

        self.grip_bl = QSizeGrip(self)
        self.grip_bl.setStyleSheet("background-color: rgba(220, 220, 220, .9);  border-top-right-radius: 6px; border: 2px solid rgba(220, 220, 220, .9);")
        # self.grip_bl.setVisible(False)
        self.grip_bl.resize(10, 10)
        self.grip_bl.move(0, self.frame.height() - 10)

        self.grip_tr = QSizeGrip(self)
        self.grip_tr.setStyleSheet("background-color: rgba(220, 220, 220, .9);  border-bottom-left-radius: 6px; border: 2px solid rgba(220, 220, 220, .9);")
        # self.grip_tr.setVisible(False)
        self.grip_tr.resize(10, 10)
        self.grip_tr.move(self.frame.width() - 10, 0)
        
        self.grip_tl = QSizeGrip(self)
        self.grip_tl.setStyleSheet("background-color: rgba(220, 220, 220, .9); border-bottom-right-radius: 6px; border: 2px solid rgba(220, 220, 220, .9);")
        # self.grip_tl.setVisible(False)
        self.grip_tl.resize(10, 10)
        self.grip_tl.move(0, 0)

        self.grips = [self.grip_br, self.grip_bl, self.grip_tr, self.grip_tl]
    
    def resize_grips(self):
        self.grip_br.move(self.frame.width() - 10, self.frame.height() - 10)
        self.grip_bl.move(0, self.frame.height() - 10)
        self.grip_tr.move(self.frame.width() - 10, 0)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.frame.setGeometry(0, 0, event.size().width(), event.size().height())
        self.resize_grips()
        self.set_mask()
        self.size_label.setText(f"{event.size().width()} x {event.size().height()}")
        self.size_label.show()
        self.timer.start(2000)

        return super().resizeEvent(event)

    def enter_event(self, event: QEvent) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.SizeAllCursor)
        return super().enterEvent(event)
    
    def leave_event(self, event: QEvent) -> None:
        QApplication.restoreOverrideCursor()
        return super().leaveEvent(event)
    
    def mouse_press_event(self, event: QMouseEvent) -> None:
        self.drag_start_position = event.globalPosition()
        
    def mouse_move_event(self, event: QMouseEvent) -> None:
        if not self.drag_start_position:
            return

        diff = event.globalPosition() - self.drag_start_position
    
        if self.x() + int(diff.x()) < 0:
            diff.setX(0)
        if self.y() + int(diff.y()) < 0:
            diff.setY(0)
        if self.x() + int(diff.x()) + self.width() > QApplication.primaryScreen().size().width():
            diff.setX(0)
        if self.y() + int(diff.y()) + self.height() > QApplication.primaryScreen().size().height():
            diff.setY(0)
        
        self.move(self.x() + int(diff.x()), self.y() + int(diff.y()))
        self.drag_start_position = event.globalPosition()

    def mouse_release_event(self, event: QMouseEvent) -> None:
        self.drag_start_position = None

if __name__ == "__main__":
    app = QApplication([])
    window = Crop()
    app.exec()