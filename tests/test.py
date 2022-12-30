import sys, os
sys.path.insert(0, os.getcwd() + "/src")
from PySide6.QtWidgets import QApplication

import pypeek as pypeek

# pypeek.show()
QApplication(sys.argv)
drawover = pypeek.DrawOver("/Users/firatkiral/Desktop/draw/img/peek_desktop.jpg")
drawover.show()
QApplication.instance().exec()