from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QLineEdit, QPushButton,
    QFileDialog
)

class ChatPanel(QWidget):
    sendMessage = pyqtSignal(str)
    sendFile = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        self.history = QTextEdit(readOnly=True)
        self.history.setPlaceholderText("(Historial de mensajes)")
        layout.addWidget(self.history, 1)

        inputRow = QHBoxLayout()
        self.inputLine = QLineEdit()
        self.inputLine.setPlaceholderText("Escribe un mensaje y presiona Enter o 'Enviar'")
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

    # Public API (to be used later by networking layer)
    def append_local(self, text: str):
        self.history.append(f"<b>Yo:</b> {text}")

    def append_remote(self, peer: str, text: str):
        self.history.append(f"<b>{peer}:</b> {text}")

    def append_system(self, text: str):
        self.history.append(f"<i style='color:gray'>{text}</i>")

    # Slots
    def _on_send_clicked(self):
        msg = self.inputLine.text().strip()
        if not msg:
            return
        self.inputLine.clear()
        self.append_local(msg)
        self.sendMessage.emit(msg)

    def _on_file_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo a enviar")
        if path:
            self.append_system(f"Enviando archivo: {path}")
            self.sendFile.emit(path)
