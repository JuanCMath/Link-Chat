"""Simple test to demonstrate the logging system working.

Run this to see how logs from backend appear in both console and GUI.
"""
import logging
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QTabWidget
from linkchat.app.gui.log_handler import LogViewer, setup_gui_logging


def test_logging_system():
    """Test that logging works across different modules."""
    
    # Create test loggers for different modules
    backend_logger = logging.getLogger('linkchat.backend')
    file_logger = logging.getLogger('linkchat.link.file_transfer')
    gui_logger = logging.getLogger('linkchat.app.gui.main_window')
    
    # Test different log levels
    backend_logger.debug("Backend DEBUG: Starting connection")
    backend_logger.info("Backend INFO: Connected to interface eth0")
    
    file_logger.info("File Transfer INFO: Starting file send")
    file_logger.warning("File Transfer WARNING: Retrying chunk 5")
    file_logger.error("File Transfer ERROR: Hash mismatch detected!")
    
    gui_logger.info("GUI INFO: User clicked send button")
    gui_logger.critical("GUI CRITICAL: Backend crashed!")
    
    print("\n✅ Logging test complete! Check the Logs tab in the window above.")


class TestWindow(QMainWindow):
    """Simple test window to demonstrate logging."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LinkChat Logging Test")
        self.resize(800, 600)
        
        # Create central widget with tabs
        central = QWidget()
        layout = QVBoxLayout(central)
        
        # Create tabs
        tabs = QTabWidget()
        
        # Add log viewer tab
        log_viewer = LogViewer()
        tabs.addTab(log_viewer, "📋 Logs")
        
        # Add test button
        test_btn = QPushButton("🧪 Run Logging Test")
        test_btn.clicked.connect(test_logging_system)
        
        layout.addWidget(tabs)
        layout.addWidget(test_btn)
        self.setCentralWidget(central)
        
        # Set up logging
        setup_gui_logging(log_viewer, level=logging.DEBUG)
        
        # Log startup
        logger = logging.getLogger(__name__)
        logger.info("Test window initialized - click button to test logging!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
