from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QStatusBar, QToolBar,
    QFileDialog, QMessageBox
)
from PyQt6.QtGui import QAction

from .chat_panel import ChatPanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LinkChat - PyQt6")
        self.resize(820, 560)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        # Central
        central = QWidget()
        lay = QVBoxLayout(central)

        self.lblPeer = QLabel("Peer: (sin conectar)")
        self.lblPeer.setObjectName("lblPeer")

        self.chat = ChatPanel()

        lay.addWidget(self.lblPeer)
        lay.addWidget(self.chat, 1)
        self.setCentralWidget(central)

        # Status bar
        sb = QStatusBar()
        self.setStatusBar(sb)
        sb.showMessage("Listo")

        # Toolbar & Menu
        tb = QToolBar("Principal")
        self.addToolBar(tb)

        self.actConnect = QAction("Conectar", self)
        self.actDisconnect = QAction("Desconectar", self)
        self.actDisconnect.setEnabled(False)
        self.actSendFolder = QAction("Enviar carpeta", self)
        self.actAbout = QAction("Acerca de", self)
        self.actExit = QAction("Salir", self)

        for a in (self.actConnect, self.actDisconnect, self.actSendFolder, self.actAbout, self.actExit):
            tb.addAction(a)

        menubar = self.menuBar()
        mArchivo = menubar.addMenu("Archivo")
        mArchivo.addAction(self.actConnect)
        mArchivo.addAction(self.actDisconnect)
        mArchivo.addSeparator()
        mArchivo.addAction(self.actSendFolder)
        mArchivo.addSeparator()
        mArchivo.addAction(self.actExit)

        mAyuda = menubar.addMenu("Ayuda")
        mAyuda.addAction(self.actAbout)

    def _connect_signals(self):
        self.chat.sendMessage.connect(self._on_send_message)
        self.chat.sendFile.connect(self._on_send_file)
        self.actExit.triggered.connect(self.close)
        self.actAbout.triggered.connect(self._on_about)
        self.actConnect.triggered.connect(self._on_connect)
        self.actDisconnect.triggered.connect(self._on_disconnect)
        self.actSendFolder.triggered.connect(self._on_send_folder)

    # Placeholder handlers (to be wired with real networking logic later)
    def _on_send_message(self, text: str):
        # TODO: integrate transport/link layer send operation
        self.statusBar().showMessage(f"Mensaje saliente ({len(text)} bytes)", 3000)

    def _on_send_file(self, path: str):
        # TODO: file transfer logic
        self.statusBar().showMessage(f"Archivo solicitado: {path}", 4000)

    def _on_connect(self):
        # TODO: show connection dialog / auto-discovery
        self.chat.append_system("[Simulación] Conectado al peer 192.168.0.42")
        self.lblPeer.setText("Peer: 192.168.0.42")
        self.actConnect.setEnabled(False)
        self.actDisconnect.setEnabled(True)

    def _on_disconnect(self):
        self.chat.append_system("[Simulación] Desconectado")
        self.lblPeer.setText("Peer: (sin conectar)")
        self.actConnect.setEnabled(True)
        self.actDisconnect.setEnabled(False)

    def _on_send_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if folder:
            # TODO: iterate and send each file
            self.chat.append_system(f"[Simulación] Carpeta en cola: {folder}")

    def _on_about(self):
        QMessageBox.information(self, "Acerca de", "LinkChat GUI\nBoceto inicial PyQt6")

    # Optional: close event stub for cleanup
    def closeEvent(self, event):  # noqa: N802
        # TODO: graceful shutdown of sockets/threads
        super().closeEvent(event)
