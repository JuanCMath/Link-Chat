"""Chat panel widget for LinkChat GUI.

Provides a simple chat UI with a read-only message history, a text input line,
buttons to send text and select a file to send, and Qt signals to notify the
MainWindow about user actions.
"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QLineEdit, QPushButton,
    QFileDialog
)


class ChatPanel(QWidget):
    """A minimal chat panel with history, input box, and send actions.

    Emits Qt signals when the user submits a text message or selects a file.
    The panel itself only updates the local history UI; actual network sends
    are performed by the parent controller (e.g., MainWindow/Backend).
    """
    sendMessage = pyqtSignal(str)
    sendFile = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        """Initialize the chat panel and build the UI layout."""
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        """Create the widgets and wire local UI interactions.

        Layout:
        - QTextEdit (history) expands to show conversation log.
        - Bottom row with QLineEdit (message input) + Send and File buttons.
        """
        layout = QVBoxLayout(self)

        self.history = QTextEdit(readOnly=True)
        self.history.setPlaceholderText("(Historial de mensajes)")
        layout.addWidget(self.history, 1)

        inputRow = QHBoxLayout()
        self.inputLine = QLineEdit()
        self.inputLine.setPlaceholderText("Escribe un mensaje y Enter o 'Enviar'")
        self.btnSend = QPushButton("Enviar")
        self.btnFile = QPushButton("Archivo…")

        inputRow.addWidget(self.inputLine, 1)
        inputRow.addWidget(self.btnSend)
        inputRow.addWidget(self.btnFile)
        layout.addLayout(inputRow)

        # Connections
        self.btnSend.clicked.connect(self._on_send_clicked)
        self.inputLine.returnPressed.connect(self._on_send_clicked)
        self.btnFile.clicked.connect(self._on_file_clicked)

    # Public API used by MainWindow
    def append_local(self, text: str) -> None:
        """Append a locally-sent message to the history.

        This only affects the UI; sending over the network is handled elsewhere.
        """
        self.history.append(f"<b>Yo:</b> {text}")

    def append_remote(self, peer: str, text: str) -> None:
        """Append a message received from a remote peer to the history.

        Args:
            peer: Human-readable peer label (e.g., MAC string or name).
            text: Message text.
        """
        self.history.append(f"<b>{peer}:</b> {text}")

    def append_system(self, text: str) -> None:
        """Append a system/info line to the history in a subtle style."""
        self.history.append(f"<i style='color:gray'>{text}</i>")

    # Slots
    def _on_send_clicked(self) -> None:
        """Handle send button or Enter key: emit sendMessage if text is non-empty."""
        msg = self.inputLine.text().strip()
        if not msg:
            return
        self.inputLine.clear()
        self.append_local(msg)
        self.sendMessage.emit(msg)

    def _on_file_clicked(self) -> None:
        """Open a file picker and emit sendFile with the selected path.

        The actual file transfer logic is performed by the controller.
        """
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo a enviar")
        if path:
            self.append_system(f"Enviando archivo: {path}")
            self.sendFile.emit(path)
