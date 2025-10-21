# app/gui_pyqt6/gui.py
from __future__ import annotations
import os
import sys
import threading
from typing import Optional, List

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QLineEdit, QLabel, QFileDialog,
    QMessageBox, QSplitter, QFormLayout, QSpinBox, QDoubleSpinBox, QComboBox, QGroupBox
)

# --- Backend (tu proyecto) ---
# Importa desde tu árbol real:
# app_facade usa todo el backend (raw sockets, FTv2, discovery, ACKs, etc.)
from app.backend.core.config import load_config, LinkChatConfig
from app.backend.app_facade import LinkChatApp
from app.backend.utils.network_utils import list_network_interfaces


# ---------- Bridge señales/encolado seguro a la GUI ----------

class AppBus(QObject):
    logLine = pyqtSignal(str)           # Mensajes de estado / logs
    peersChanged = pyqtSignal()         # Refrescar lista de peers
    progressLine = pyqtSignal(str)      # Líneas de progreso de FT
    runningChanged = pyqtSignal(bool)   # on/off backend


# Controller thin: envuelve LinkChatApp y expone métodos thread-safe
class Controller:
    def __init__(self, bus: AppBus) -> None:
        self.bus = bus
        self._app: Optional[LinkChatApp] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _emit(self, text: str) -> None:
        self.bus.logLine.emit(text)

    def _emit_progress(self, role: str, sid: str, done: int, total: int) -> None:
        pct = (100.0 * done / total) if total else 0.0
        self.bus.progressLine.emit(f"[{role} {sid}] {done}/{total} ({pct:.1f}%)")

    def start(self, preset_name: Optional[str] = None) -> None:
        with self._lock:
            if self._app:
                return
            # Cargar config desde env (IFACE, NAME, ETHERTYPE, etc.)
            cfg = load_config()
            if preset_name:
                cfg.name = preset_name  # override rápido

            # Hook de salida/log
            app = LinkChatApp(cfg, output=self._emit)
            # Sobrescribimos los callbacks de progreso/ACK ya conectados por la fachada
            # (La fachada ya emite progreso/ACK a través de on_progress/_emit_progress)
            self._app = app

        def run():
            try:
                app.start()
                self.bus.runningChanged.emit(True)
                self.bus.logLine.emit("[gui] backend started")
            except Exception as e:
                self.bus.logLine.emit(f"[err] start failed: {e}")
                with self._lock:
                    self._app = None
                self.bus.runningChanged.emit(False)
                return

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._lock:
            app = self._app
            self._app = None
        if app:
            try:
                app.stop()
                self.bus.logLine.emit("[gui] backend stopped")
            except Exception as e:
                self.bus.logLine.emit(f"[err] stop failed: {e}")
        self.bus.runningChanged.emit(False)

    # --- Pasarela de funciones de la fachada ---

    def list_peers(self):
        with self._lock:
            app = self._app
        if not app:
            return []
        return app.list_peers()  # Peer objects

    def refresh_peers(self):
        # Solo solicitar a la GUI que lea de list_peers()
        self.bus.peersChanged.emit()

    def set_active_peer(self, mac: str) -> bool:
        with self._lock:
            app = self._app
        if not app:
            self._emit("[warn] backend not running")
            return False
        ok = app.set_active_peer(mac)
        if ok:
            self._emit(f"[peer] activo = {mac}")
        return ok

    def send_chat(self, text: str) -> None:
        with self._lock:
            app = self._app
        if not app:
            self._emit("[warn] backend not running")
            return
        app.send_chat(text)  # MSG:: con ACK (:contentReference[oaicite:9]{index=9})

    def send_broadcast(self, text: str) -> None:
        with self._lock:
            app = self._app
        if not app:
            self._emit("[warn] backend not running")
            return
        app.broadcast_chat(text)  # (:contentReference[oaicite:10]{index=10})

    def send_file(self, mac: str, path: str) -> None:
        with self._lock:
            app = self._app
        if not app:
            self._emit("[warn] backend not running")
            return
        app.send_file(mac, path)  # (:contentReference[oaicite:11]{index=11})

    def send_dir(self, mac: str, path: str) -> None:
        with self._lock:
            app = self._app
        if not app:
            self._emit("[warn] backend not running")
            return
        app.send_directory(mac, path)  # (:contentReference[oaicite:12]{index=12})

    def set_config_param(self, param: str, value: str) -> str:
        with self._lock:
            app = self._app
        if not app:
            return "[warn] backend not running"
        # Aplica validación y side-effects internos (iface, name, intervals…)
        # (:contentReference[oaicite:13]{index=13})
        return app.set_config_param(param, value)

    def show_config(self) -> List[str]:
        with self._lock:
            app = self._app
        if not app:
            return []
        return app.show_config()

    def interfaces(self) -> List[str]:
        try:
            return list_network_interfaces()
        except Exception:
            return []


# ---------- Ventana principal ----------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Link-Chat (PyQt6)")
        self.resize(1100, 720)

        self.bus = AppBus()
        self.ctrl = Controller(self.bus)

        # UI
        self._build_ui()
        self._wire_signals()

        # Autostart backend con NAME si viene del entorno
        preset = os.environ.get("NAME") or None
        self.ctrl.start(preset_name=preset)

        # Refresco periódico de peers
        self._peer_timer = QTimer(self)
        self._peer_timer.timeout.connect(self.ctrl.refresh_peers)
        self._peer_timer.start(1500)

    # ----- UI Layouts -----
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main = QHBoxLayout(central)
        # Izquierda: Peers + Acciones
        left = QVBoxLayout()
        peers_lbl = QLabel("Peers (MAC → Nombre)")
        self.peers = QListWidget()
        self.btnRefresh = QPushButton("Refrescar")
        self.btnSetActive = QPushButton("Usar como activo")
        self.btnSendFile = QPushButton("Enviar archivo…")
        self.btnSendDir = QPushButton("Enviar carpeta…")

        left.addWidget(peers_lbl)
        left.addWidget(self.peers, 1)
        hl = QHBoxLayout()
        hl.addWidget(self.btnRefresh)
        hl.addWidget(self.btnSetActive)
        left.addLayout(hl)
        hl2 = QHBoxLayout()
        hl2.addWidget(self.btnSendFile)
        hl2.addWidget(self.btnSendDir)
        left.addLayout(hl2)

        # Centro: Chat
        center = QVBoxLayout()
        self.chatView = QTextEdit()
        self.chatView.setReadOnly(True)
        self.chatInput = QLineEdit()
        self.chatInput.setPlaceholderText("Mensaje a peer activo… Enter para enviar")
        self.btnBroadcast = QPushButton("Broadcast")
        center.addWidget(self.chatView, 1)
        row = QHBoxLayout()
        row.addWidget(self.chatInput, 1)
        row.addWidget(self.btnBroadcast)
        center.addLayout(row)

        # Derecha: Config + Logs
        right = QVBoxLayout()
        cfgGroup = QGroupBox("Configuración en vivo")
        cfgForm = QFormLayout(cfgGroup)

        self.cmbIface = QComboBox()
        self.cmbIface.addItems(self.ctrl.interfaces())
        self.cmbIface.setEditable(False)

        self.txtName = QLineEdit()
        self.spinMsgRetry = QDoubleSpinBox(); self.spinMsgRetry.setRange(0.5, 30.0); self.spinMsgRetry.setDecimals(1)
        self.spinMsgMax = QSpinBox(); self.spinMsgMax.setRange(1, 20)
        self.spinFileRetry = QDoubleSpinBox(); self.spinFileRetry.setRange(0.5, 60.0); self.spinFileRetry.setDecimals(1)
        self.spinFileMax = QSpinBox(); self.spinFileMax.setRange(1, 50)
        self.spinBeacon = QDoubleSpinBox(); self.spinBeacon.setRange(1.0, 60.0); self.spinBeacon.setDecimals(1)

        cfgForm.addRow("Iface:", self.cmbIface)
        cfgForm.addRow("Nombre:", self.txtName)
        cfgForm.addRow("Msg retry (s):", self.spinMsgRetry)
        cfgForm.addRow("Msg max:", self.spinMsgMax)
        cfgForm.addRow("File retry (s):", self.spinFileRetry)
        cfgForm.addRow("File max:", self.spinFileMax)
        cfgForm.addRow("Beacon (s):", self.spinBeacon)
        self.btnApplyCfg = QPushButton("Aplicar cambios")
        cfgForm.addRow(self.btnApplyCfg)

        self.btnStart = QPushButton("Start")
        self.btnStop = QPushButton("Stop")
        self.btnStop.setEnabled(False)

        right.addWidget(cfgGroup)
        row2 = QHBoxLayout()
        row2.addWidget(self.btnStart)
        row2.addWidget(self.btnStop)
        right.addLayout(row2)

        self.logView = QTextEdit()
        self.logView.setReadOnly(True)
        right.addWidget(QLabel("Logs"))
        right.addWidget(self.logView, 1)

        # Splitters
        split = QSplitter(Qt.Orientation.Horizontal)
        leftW = QWidget(); leftW.setLayout(left)
        centerW = QWidget(); centerW.setLayout(center)
        rightW = QWidget(); rightW.setLayout(right)
        split.addWidget(leftW); split.addWidget(centerW); split.addWidget(rightW)
        split.setStretchFactor(0, 2); split.setStretchFactor(1, 3); split.setStretchFactor(2, 3)

        main.addWidget(split)

        # Precarga vals de config actuales
        self._load_current_config_fields()

    # ----- Señales / slots -----
    def _wire_signals(self):
        self.bus.logLine.connect(self._append_log)
        self.bus.progressLine.connect(self._append_log)
        self.bus.peersChanged.connect(self._reload_peers)
        self.bus.runningChanged.connect(self._on_running_changed)

        self.btnRefresh.clicked.connect(self._reload_peers)
        self.btnSetActive.clicked.connect(self._set_active_from_list)
        self.btnSendFile.clicked.connect(self._pick_and_send_file)
        self.btnSendDir.clicked.connect(self._pick_and_send_dir)
        self.chatInput.returnPressed.connect(self._send_chat_line)
        self.btnBroadcast.clicked.connect(self._send_broadcast)
        self.btnApplyCfg.clicked.connect(self._apply_cfg)
        self.btnStart.clicked.connect(lambda: self.ctrl.start())
        self.btnStop.clicked.connect(self.ctrl.stop)

    # ----- Helpers GUI -----
    def _append_log(self, line: str):
        if line:
            self.logView.append(line)
            if line.startswith("[rx ") or line.startswith("[tx "):
                self.chatView.append(line)

    def _reload_peers(self):
        self.peers.clear()
        peers = self.ctrl.list_peers()
        # Peer(mac, name, last_seen) (:contentReference[oaicite:14]{index=14})
        for p in peers:
            label = f"{p.mac} → {p.name or '(sin nombre)'}"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, p.mac)
            self.peers.addItem(it)

    def _set_active_from_list(self):
        it = self.peers.currentItem()
        if not it:
            return
        mac = it.data(Qt.ItemDataRole.UserRole)
        ok = self.ctrl.set_active_peer(mac)
        if not ok:
            QMessageBox.warning(self, "Peer", "MAC inválida o backend no iniciado")

    def _pick_and_send_file(self):
        it = self.peers.currentItem()
        if not it:
            QMessageBox.information(self, "Archivo", "Selecciona primero un peer")
            return
        mac = it.data(Qt.ItemDataRole.UserRole)
        path, _ = QFileDialog.getOpenFileName(self, "Selecciona archivo")
        if path:
            self.ctrl.send_file(mac, path)

    def _pick_and_send_dir(self):
        it = self.peers.currentItem()
        if not it:
            QMessageBox.information(self, "Carpeta", "Selecciona primero un peer")
            return
        mac = it.data(Qt.ItemDataRole.UserRole)
        path = QFileDialog.getExistingDirectory(self, "Selecciona carpeta")
        if path:
            self.ctrl.send_dir(mac, path)

    def _send_chat_line(self):
        text = self.chatInput.text().strip()
        if text:
            self.ctrl.send_chat(text)
            self.chatInput.clear()

    def _send_broadcast(self):
        text = self.chatInput.text().strip()
        if text:
            self.ctrl.send_broadcast(text)
            self.chatInput.clear()

    def _load_current_config_fields(self):
        cfg_lines = self.ctrl.show_config()  # "<key>: <value>" (:contentReference[oaicite:15]{index=15})
        kv = {}
        for line in cfg_lines:
            if ": " in line:
                k, v = line.split(": ", 1)
                kv[k] = v
        # Rellenar campos si están disponibles
        if "name" in kv:
            self.txtName.setText(kv["name"])
        if "beacon_interval" in kv:
            try: self.spinBeacon.setValue(float(kv["beacon_interval"]))
            except: pass
        if "msg_retry_interval" in kv:
            try: self.spinMsgRetry.setValue(float(kv["msg_retry_interval"]))
            except: pass
        if "msg_max_retries" in kv:
            try: self.spinMsgMax.setValue(int(kv["msg_max_retries"]))
            except: pass
        if "file_retry_interval" in kv:
            try: self.spinFileRetry.setValue(float(kv["file_retry_interval"]))
            except: pass
        if "file_max_retries" in kv:
            try: self.spinFileMax.setValue(int(kv["file_max_retries"]))
            except: pass

    def _apply_cfg(self):
        msgs = []
        # iface
        iface = self.cmbIface.currentText().strip()
        if iface:
            msgs.append(self.ctrl.set_config_param("iface", iface))  # cambia hilos/registro (:contentReference[oaicite:16]{index=16})
        # name
        name = self.txtName.text().strip()
        if name:
            msgs.append(self.ctrl.set_config_param("name", name))
        # intervals / retries
        msgs.append(self.ctrl.set_config_param("msg_retry_interval", str(self.spinMsgRetry.value())))
        msgs.append(self.ctrl.set_config_param("msg_max_retries", str(self.spinMsgMax.value())))
        msgs.append(self.ctrl.set_config_param("file_retry_interval", str(self.spinFileRetry.value())))
        msgs.append(self.ctrl.set_config_param("file_max_retries", str(self.spinFileMax.value())))
        msgs.append(self.ctrl.set_config_param("beacon_interval", str(self.spinBeacon.value())))
        self._append_log("\n".join(msgs))

    def _on_running_changed(self, running: bool):
        self.btnStart.setEnabled(not running)
        self.btnStop.setEnabled(running)

# ---- entrypoint ----
def main():
    # PSK opcional: LINKCHAT_PSK=64 hex (ChaCha20-Poly1305 en tu framing) (:contentReference[oaicite:17]{index=17})
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
