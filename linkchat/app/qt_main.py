"""Entry point for the PyQt6 GUI.
Run with: python -m linkchat.app.qt_main
"""
import logging
import sys

from PyQt6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def setup_logging() -> None:
    """Configure logging for the entire application.
    
    Sets up a basic console logger that captures all levels (DEBUG and above)
    from the linkchat package. Logs include timestamp, logger name, level,
    and message.
    """
    logging.basicConfig(
        level=logging.INFO,  # Change to DEBUG for more verbose output
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)  # Print to console
        ]
    )
    
    # Set specific levels for different modules if needed
    # logging.getLogger('linkchat.link').setLevel(logging.DEBUG)
    # logging.getLogger('linkchat.app').setLevel(logging.INFO)


def run() -> int:
    """Start the LinkChat GUI application.

    Creates a QApplication instance, constructs and shows the MainWindow,
    then enters the Qt event loop. Returns the application's exit code
    when the event loop terminates.
    """
    # Configure logging before anything else
    setup_logging()
    
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
