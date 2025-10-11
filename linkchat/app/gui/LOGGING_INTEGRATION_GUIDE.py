"""Example of how to integrate the log viewer into MainWindow.

This file demonstrates two approaches:
1. Simple: Add logging setup to qt_main.py (console only)
2. Advanced: Add a log viewer tab/panel to the main window
"""

# =============================================================================
# APPROACH 1: Console Logging Only (Already implemented in qt_main.py)
# =============================================================================
"""
In qt_main.py, we added:

import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

def run():
    setup_logging()  # Call before creating QApplication
    app = QApplication(sys.argv)
    ...
"""

# =============================================================================
# APPROACH 2: GUI Log Viewer (Optional - for debugging)
# =============================================================================
"""
To add a log viewer tab to your MainWindow, modify main_window.py:

1. Import the log components:
   from .log_handler import LogViewer, setup_gui_logging

2. In _build_ui(), create a QTabWidget instead of just chat panel:
   
   # Right side: tabbed interface
   self.tabs = QTabWidget()
   
   # Chat tab
   self.chat = ChatPanel()
   self.tabs.addTab(self.chat, "Chat")
   
   # Log viewer tab
   self.log_viewer = LogViewer()
   self.tabs.addTab(self.log_viewer, "Logs")
   
   root.addLayout(left, 0)
   root.addWidget(self.tabs, 1)  # Use tabs instead of self.chat

3. In __init__(), after _build_ui():
   
   # Set up GUI logging
   setup_gui_logging(self.log_viewer, level=logging.DEBUG)

Now all logs will appear in both:
- Console (from qt_main.py setup)
- GUI "Logs" tab (from log viewer setup)
"""

# =============================================================================
# HOW IT WORKS - Complete Flow
# =============================================================================
"""
1. Application starts (qt_main.py)
   └─> setup_logging() configures root logger

2. Backend creates logger
   logger = logging.getLogger(__name__)  # "linkchat.link.file_transfer"

3. Error occurs in file_transfer.py
   logger.error("Hash mismatch for %s!", filename)

4. Logging system processes:
   a) Checks level (ERROR >= INFO ✓)
   b) Formats message using configured formatter
   c) Sends to ALL registered handlers:
      - StreamHandler → prints to console
      - QtLogHandler → emits Qt signal → updates GUI

5. User sees:
   - Terminal: "14:23:45 - linkchat.link.file_transfer - ERROR - Hash mismatch for photo.jpg!"
   - GUI Logs tab: Same message in RED color

6. No GUI integration needed in backend code!
   - Backend just calls logger.error()
   - Logging system routes it automatically
   - Qt signal/slot ensures thread safety
"""

# =============================================================================
# MINIMAL INTEGRATION EXAMPLE - Add to main_window.py
# =============================================================================
"""
Here's the minimal code to add to MainWindow class:

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... existing code ...
        self._build_ui()
        
        # ADD THIS: Set up GUI logging after UI is built
        from .log_handler import setup_gui_logging
        import logging
        if hasattr(self, 'log_viewer'):
            setup_gui_logging(self.log_viewer, level=logging.DEBUG)
        
        # ... rest of __init__ ...

That's it! No changes needed to backend/link layer code.
"""
