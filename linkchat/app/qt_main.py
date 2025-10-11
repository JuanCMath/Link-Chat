"""Entry point for the PyQt6 GUI.
Run with: python -m linkchat.app.qt_main
"""
from PyQt6.QtWidgets import QApplication
import sys

from .gui.main_window import MainWindow


def run() -> int:
    """Start the LinkChat GUI application.

    Creates a QApplication instance, constructs and shows the MainWindow,
    then enters the Qt event loop. Returns the application's exit code
    when the event loop terminates.
    """
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
