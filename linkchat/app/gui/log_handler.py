"""Custom logging handler for displaying logs in the Qt GUI.

Provides a QTextEdit-based log viewer that can be embedded in the main window
to display application logs in real-time. This is useful for debugging and
monitoring network activity without needing a terminal.
"""
import logging
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QTextCursor, QColor


class QtLogHandler(logging.Handler, QObject):
    """Custom logging handler that emits Qt signals for thread-safe GUI updates.
    
    This handler bridges Python's logging system with Qt's signal/slot mechanism,
    ensuring log messages can be safely displayed in GUI widgets even when
    emitted from background threads.
    
    Attributes:
        log_signal: Qt signal emitted for each log record with formatted message.
    """
    log_signal = pyqtSignal(str, str)  # (level, message)
    
    def __init__(self):
        """Initialize both logging.Handler and QObject."""
        logging.Handler.__init__(self)
        QObject.__init__(self)
    
    def emit(self, record: logging.LogRecord) -> None:
        """Process a log record and emit it as a Qt signal.
        
        Args:
            record: The log record to process.
        """
        try:
            msg = self.format(record)
            level = record.levelname
            self.log_signal.emit(level, msg)
        except Exception:
            self.handleError(record)


class LogViewer(QTextEdit):
    """Read-only text widget for displaying application logs with color coding.
    
    Displays log messages with different colors based on severity level:
    - DEBUG: Gray
    - INFO: Black
    - WARNING: Orange
    - ERROR/CRITICAL: Red
    """
    
    # Color mapping for log levels
    COLORS = {
        'DEBUG': QColor(128, 128, 128),      # Gray
        'INFO': QColor(0, 0, 0),              # Black
        'WARNING': QColor(255, 140, 0),       # Orange
        'ERROR': QColor(255, 0, 0),           # Red
        'CRITICAL': QColor(139, 0, 0),        # Dark Red
    }
    
    def __init__(self, parent=None):
        """Initialize the log viewer widget.
        
        Args:
            parent: Parent widget (optional).
        """
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(1000)  # Limit to last 1000 log lines
        
    def append_log(self, level: str, message: str) -> None:
        """Append a log message with appropriate color coding.
        
        Args:
            level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            message: The formatted log message to display.
        """
        color = self.COLORS.get(level, self.COLORS['INFO'])
        self.setTextColor(color)
        self.append(message)
        
        # Auto-scroll to bottom
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)


def setup_gui_logging(log_viewer: LogViewer, level: int = logging.INFO) -> QtLogHandler:
    """Configure logging to display in a GUI log viewer widget.
    
    This function sets up a custom Qt logging handler that routes all
    application logs to the provided LogViewer widget. It should be called
    during application initialization.
    
    Args:
        log_viewer: The LogViewer widget to receive log messages.
        level: Minimum logging level to display (default: INFO).
        
    Returns:
        The configured QtLogHandler instance.
        
    Example:
        >>> log_viewer = LogViewer()
        >>> handler = setup_gui_logging(log_viewer, logging.DEBUG)
        >>> # Now all logs will appear in log_viewer
    """
    # Create and configure the handler
    handler = QtLogHandler()
    handler.setLevel(level)
    
    # Format: timestamp - module - level - message
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # Connect handler signal to log viewer
    handler.log_signal.connect(log_viewer.append_log)
    
    # Add handler to root logger (catches all loggers)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(level)
    
    return handler
