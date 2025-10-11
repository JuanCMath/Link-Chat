"""Main window for the LinkChat PyQt6 application.

This module implements the top-level GUI that integrates with the LinkChat
backend. It provides:
- A peer list (auto-refreshed using discovery callbacks) to select a target.
- A chat panel for sending/receiving text messages.
- Actions to send individual files and folders.
- Controls to connect/disconnect from the networking backend.

How it works:
- When the user connects, a LinkChatBackend is created and started; callbacks
  update the UI when messages arrive, file transfers progress, and peers
  appear/disappear.
- Outgoing actions (send message/file/folder) call backend methods; results
  are reflected in the status bar and chat history.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QStatusBar, QToolBar,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QHBoxLayout,
    QPushButton, QInputDialog, QTabWidget
)
from PyQt6.QtGui import QAction

from linkchat.backend import LinkChatBackend
from linkchat.constants import BROADCAST_MAC
from .chat_panel import ChatPanel
from .log_handler import LogViewer, setup_gui_logging


class MainWindow(QMainWindow):
    """Top-level window orchestrating the LinkChat GUI.

    Responsibilities:
    - Manage the LinkChatBackend lifecycle (connect/disconnect).
    - Display discovered peers and allow selecting a destination.
    - Host the ChatPanel and route user actions to the backend.
    - Surface backend callbacks (messages, file events, peer events) in the UI.

    The window periodically refreshes the peer list and uses Qt signals/slots
    to decouple UI widgets from backend logic.
    """
    def __init__(self) -> None:
        """Construct the window, build UI, and start peer refresh timer."""
        super().__init__()
        self.setWindowTitle("LinkChat - PyQt6")
        self.resize(980, 600)

        # Backend initially None; user will connect providing interface name
        self.backend: LinkChatBackend | None = None
        self.current_dst: bytes | None = None

        self._build_ui()
        self._setup_logging()
        self._connect_signals()

        # Periodic UI refresh for peers
        self._peer_timer = QTimer(self)
        self._peer_timer.timeout.connect(self._refresh_peers)
        self._peer_timer.start(2000)

    # ------------------------- UI -------------------------
    def _build_ui(self) -> None:
        """Create and arrange widgets: peer list, controls, chat panel, menus.

        Left side contains peer-related controls; right side shows the chat
        panel. A toolbar and menubar expose common actions. The status bar
        is used for transient feedback.
        """
        central = QWidget()
        root = QHBoxLayout(central)

        # Left: peers and controls
        left = QVBoxLayout()
        self.lblPeer = QLabel("Peer: (sin conectar)")
        self.lstPeers = QListWidget()
        self.btnConnect = QPushButton("Conectar…")
        self.btnDisconnect = QPushButton("Desconectar")
        self.btnDisconnect.setEnabled(False)
        left.addWidget(self.lblPeer)
        left.addWidget(self.lstPeers, 1)
        left.addWidget(self.btnConnect)
        left.addWidget(self.btnDisconnect)

        # Right: tabbed interface with chat and logs
        self.tabs = QTabWidget()
        self.chat = ChatPanel()
        self.log_viewer = LogViewer()
        
        self.tabs.addTab(self.chat, "💬 Chat")
        self.tabs.addTab(self.log_viewer, "📋 Logs")
        
        root.addLayout(left, 0)
        root.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        # Status bar
        sb = QStatusBar()
        self.setStatusBar(sb)
        sb.showMessage("Listo")

        # Toolbar & Menu
        tb = QToolBar("Principal")
        self.addToolBar(tb)

        self.actSendFolder = QAction("Enviar carpeta", self)
        self.actAbout = QAction("Acerca de", self)
        self.actExit = QAction("Salir", self)

        tb.addAction(self.actSendFolder)
        tb.addSeparator()
        tb.addAction(self.actAbout)
        tb.addAction(self.actExit)

        menubar = self.menuBar()
        mArchivo = menubar.addMenu("Archivo")
        mArchivo.addAction(self.actSendFolder)
        mArchivo.addSeparator()
        mArchivo.addAction(self.actExit)

        mAyuda = menubar.addMenu("Ayuda")
        mAyuda.addAction(self.actAbout)

    def _setup_logging(self) -> None:
        """Set up GUI logging to display logs in the log viewer tab.
        
        Configures a custom Qt logging handler that routes all application
        logs (from backend and GUI) to the log viewer widget. Logs are
        color-coded by severity level for easy debugging.
        """
        setup_gui_logging(self.log_viewer, level=logging.DEBUG)
        
        # Log startup message
        logger = logging.getLogger(__name__)
        logger.info("LinkChat GUI initialized - logging system active")

    def _connect_signals(self) -> None:
        """Wire widget signals to their corresponding handlers.

        Connects ChatPanel signals, toolbar/menu actions, and list selection
        changes to methods that route operations and update the UI.
        """
        self.chat.sendMessage.connect(self._on_send_message)
        self.chat.sendFile.connect(self._on_send_file)
        self.actExit.triggered.connect(self.close)
        self.actAbout.triggered.connect(self._on_about)
        self.actSendFolder.triggered.connect(self._on_send_folder)
        self.btnConnect.clicked.connect(self._on_connect)
        self.btnDisconnect.clicked.connect(self._on_disconnect)
        self.lstPeers.itemSelectionChanged.connect(self._on_peer_selected)

    # ---------------------- Backend wiring ----------------------
    def _ensure_backend(self) -> bool:
        """Create and start the backend if not running.

        Prompts the user for a network interface (e.g., eth0/wlan0),
        instantiates LinkChatBackend, registers callbacks, and starts
        background networking threads. Returns True on success.
        """
        if self.backend and self.backend.is_running:
            return True
        # Ask for interface name (e.g., eth0, enp3s0, wlan0)
        iface, ok = QInputDialog.getText(self, "Interfaz de red", "Nombre de interfaz (eth0/wlan0):")
        if not ok or not iface.strip():
            return False
        iface = iface.strip()
        try:
            self.backend = LinkChatBackend(interface=iface)
            # Hook callbacks
            self.backend.on_message_received = self._on_message_received
            self.backend.on_file_progress = self._on_file_progress
            self.backend.on_file_complete = self._on_file_complete
            self.backend.on_peer_available = self._on_peer_available
            self.backend.on_peer_expired = self._on_peer_expired
            self.backend.start()
            self.statusBar().showMessage(f"Conectado en {iface}", 3000)
            self.lblPeer.setText(f"Interfaz: {iface} | MAC: {self.backend.local_mac_str}")
            return True
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo iniciar backend: {e}")
            return False

    def _refresh_peers(self) -> None:
        """Update the peer list from the backend's discovery snapshot.

        Called periodically by a QTimer to keep the list in sync with the
        discovery service. Each item stores the peer MAC in UserRole.
        """
        if not self.backend or not self.backend.is_running:
            return
        peers = self.backend.list_peers()
        # Rebuild list simple
        self.lstPeers.clear()
        for info in peers:
            item = QListWidgetItem(f"{info.name or info.node_id}  ({self._mac_str(info.mac)})")
            item.setData(Qt.ItemDataRole.UserRole, info.mac)
            self.lstPeers.addItem(item)

    @staticmethod
    def _peer_key(peer) -> str:
        """Return a stable key for a peer item (node_id)."""
        return peer.node_id

    @staticmethod
    def _mac_str(mac: bytes) -> str:
        """Format a MAC address as aa:bb:cc:dd:ee:ff."""
        return ":".join(f"{b:02x}" for b in mac)

    # ------------------------ Slots ------------------------
    def _on_connect(self) -> None:
        """Handle Connect: ensure backend is running and toggle controls."""
        if self._ensure_backend():
            self.btnConnect.setEnabled(False)
            self.btnDisconnect.setEnabled(True)

    def _on_disconnect(self) -> None:
        """Handle Disconnect: stop backend and reset UI state."""
        if self.backend:
            self.backend.stop()
        self.btnConnect.setEnabled(True)
        self.btnDisconnect.setEnabled(False)
        self.lblPeer.setText("Peer: (sin conectar)")
        self.lstPeers.clear()

    def _on_peer_selected(self) -> None:
        """Store currently selected peer MAC from the list widget."""
        item = self.lstPeers.currentItem()
        self.current_dst = item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_send_message(self, text: str) -> None:
        """Send a text message via backend to the selected peer or broadcast.

        Uses BROADCAST_MAC when no peer is selected so messages can be
        seen by all listening nodes.
        """
        if not self.backend or not self.backend.is_running:
            self.chat.append_system("Backend no iniciado")
            return
        dst = self.current_dst or BROADCAST_MAC
        try:
            ok = self.backend.send_message(dst, text)
            status = "ACK" if ok else "sin ACK"
            self.statusBar().showMessage(f"Mensaje enviado ({status})", 3000)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo enviar mensaje: {e}")

    def _on_send_file(self, path: str) -> None:
        """Send a single file to the selected peer using the backend API."""
        if not self.backend or not self.backend.is_running:
            self.chat.append_system("Backend no iniciado")
            return
        if not self.current_dst:
            self.chat.append_system("Selecciona un peer primero")
            return
        try:
            ok = self.backend.send_file(self.current_dst, path)
            status = "OK" if ok else "Fallo"
            self.statusBar().showMessage(f"Archivo: {status}", 4000)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo enviar archivo: {e}")

    def _on_send_folder(self) -> None:
        """Send a complete folder by emitting metadata then files sequentially.

        Opens a directory picker and uses FolderTransfer (on top of FileTransfer)
        to preserve directory structure at the receiver.
        """
        if not self.backend or not self.backend.is_running:
            self.chat.append_system("Backend no iniciado")
            return
        if not self.current_dst:
            self.chat.append_system("Selecciona un peer primero")
            return
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if not folder:
            return
        
        ok = self.backend.send_folder(self.current_dst, folder)
        status = "OK" if ok else "Fallo"
        self.statusBar().showMessage(f"Carpeta: {status}", 4000)

    def _on_about(self) -> None:
        """Display an About dialog with a brief description."""
        QMessageBox.information(self, "Acerca de", "LinkChat GUI\nPyQt6 + capa de enlace personalizada")

    # ----------------- Backend callbacks to UI -----------------
    def _on_message_received(self, src_mac: bytes, text: str) -> None:
        """Append an incoming message from backend to the chat history."""
        self.chat.append_remote(self._mac_str(src_mac), text)

    def _on_file_progress(self, filename: str, done: int, total: int) -> None:
        """Show file transfer progress in the status bar."""
        self.statusBar().showMessage(f"Archivo {filename}: {done}/{total}")

    def _on_file_complete(self, filename: str, success: bool) -> None:
        """Notify completion result of a file transfer in the chat panel."""
        self.chat.append_system(f"Archivo {filename}: {'OK' if success else 'Fallo'}")

    def _on_peer_available(self, peer) -> None:
        """Inform the user that a new peer has been discovered."""
        self.chat.append_system(f"Peer disponible: {peer.name or peer.node_id} ({self._mac_str(peer.mac)})")

    def _on_peer_expired(self, peer) -> None:
        """Inform the user that a peer has timed out and was removed."""
        self.chat.append_system(f"Peer expiró: {peer.name or peer.node_id} ({self._mac_str(peer.mac)})")
