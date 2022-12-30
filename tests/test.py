import sys, os
sys.path.insert(0, os.getcwd() + "/src")
from PySide6.QtWidgets import *

import pypeek as pypeek

class Window(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        self.button = QPushButton('Show Dialog', self)
        self.button.clicked.connect(self.handleButton)
        layout.addWidget(self.button)
        self.setCentralWidget(widget)

    def handleButton(self):
        dialog = pypeek.DrawOver("/Users/firatkiral/Desktop/draw/img")
        if dialog.exec() == QDialog.Accepted:
            print("Accepted")
        else:
            print('Cancelled')
        dialog.deleteLater()

# pypeek.show()
QApplication(sys.argv)
# drawover = pypeek.DrawOver("/Users/firatkiral/Desktop/draw/img")

window = Window()
window.setGeometry(500, 300, 200, 100)
window.show()
QApplication.instance().exec()