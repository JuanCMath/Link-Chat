"""Entry point for the PyQt6 GUI (development).
Run: python -m linkchat.app.qt_main
"""
from PyQt6.QtWidgets import QApplication
import sys

from .gui.main_window import MainWindow

def run():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(run())
