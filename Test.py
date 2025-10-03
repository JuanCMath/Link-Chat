#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LinkChat GUI (PyQt6) + AF_PACKET (solo capa de enlace)
------------------------------------------------------

Requisitos:
  - Linux (AF_PACKET sólo existe en Linux)
  - Ejecutar como root (o con CAP_NET_RAW)
  - Python 3.9+
  - PyQt6: pip install PyQt6

Descripción:
  GUI mínima para enviar/recibir tramas Ethernet crudas con un Ethertype propio.
  No usa IP/UDP/TCP: todo es capa de enlace (L2). Ideal para tu proyecto "LinkChat".

  Funcionalidades:
   - Elegir interfaz (ej. eth0)
   - Elegir Ethertype (por defecto 0x88B5)
   - Introducir MAC destino (broadcast por defecto ff:ff:ff:ff:ff:ff)
   - Enviar payload (texto) como bytes crudos (UTF-8)
   - Ver frames entrantes con tu Ethertype
   - Hilo separado para escucha continua

Nota FCS: normalmente el FCS/CRC lo gestiona la NIC/driver; este ejemplo no calcula FCS.

Seguridad: esto es un ejemplo educativo. No validar todo. Ajusta para producción.
"""
from __future__ import annotations
import os
import sys
import socket
import struct
import threading
import queue
import time
from typing import Optional, Tuple

# ---------------------- Utilidades MAC/Ethernet ----------------------

def mac_str_to_bytes(mac: str) -> bytes:
    """Convierte 'aa:bb:cc:dd:ee:ff' -> 6 bytes."""
    parts = mac.split(":")
    if len(parts) != 6:
        raise ValueError("MAC inválida: formato aa:bb:cc:dd:ee:ff")
    return bytes(int(p, 16) for p in parts)


def mac_bytes_to_str(b: bytes) -> str:
    return ":".join(f"{x:02x}" for x in b)


def read_iface_mac(iface: str) -> bytes:
    """Lee la MAC de /sys/class/net/<iface>/address (Linux)."""
    path = f"/sys/class/net/{iface}/address"
    with open(path, "r") as f:
        txt = f.read().strip()
    return mac_str_to_bytes(txt)


# ---------------------- Capa de enlace AF_PACKET ----------------------

ETH_P_ALL = 0x0003  # para captura general si se quiere
DEFAULT_ETHERTYPE = 0x88B5
ETH_HEADER_FMT = "!6s6sH"  # dst(6) src(6) ethertype(2)
ETH_MTU = 1500

class AFPacketMedium:
    """Medio de capa de enlace con AF_PACKET (Linux)."""
    def __init__(self, iface: str, ethertype: int = DEFAULT_ETHERTYPE, filter_ethertype: bool = True):
        self.iface = iface
        self.ethertype = ethertype
        self.filter_ethertype = filter_ethertype
        self.tx_sock: Optional[socket.socket] = None
        self.rx_sock: Optional[socket.socket] = None
        self.src_mac: Optional[bytes] = None

    def open(self):
        # socket de envío (RAW). Enviar con protocolo ETH_P_ALL y especificar ethertype en el frame.
        self.tx_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
        self.tx_sock.bind((self.iface, 0))  # 0 -> no fija protocolo aquí

        # socket de recepción. Filtramos por ethertype para no recibir "todo".
        proto = socket.htons(self.ethertype) if self.filter_ethertype else socket.htons(ETH_P_ALL)
        self.rx_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, proto)
        self.rx_sock.bind((self.iface, 0))

        self.src_mac = read_iface_mac(self.iface)

    def close(self):
        if self.tx_sock:
            try:
                self.tx_sock.close()
            except Exception:
                pass
            self.tx_sock = None
        if self.rx_sock:
            try:
                self.rx_sock.close()
            except Exception:
                pass
            self.rx_sock = None

    def make_frame(self, dst_mac_str: str, payload: bytes) -> bytes:
        if len(payload) > ETH_MTU:
            # Nota: Ethernet II payload "normal" <= 1500. Para >1500 deberías fragmentar a nivel app.
            raise ValueError(f"Payload demasiado grande para un frame único (> {ETH_MTU} bytes)")
        if not self.src_mac:
            raise RuntimeError("Interface MAC no inicializada. Llama open() primero.")
        dst = mac_str_to_bytes(dst_mac_str)
        hdr = struct.pack(ETH_HEADER_FMT, dst, self.src_mac, self.ethertype)
        return hdr + payload

    def send(self, frame: bytes):
        if not self.tx_sock:
            raise RuntimeError("Socket TX no abierto")
        self.tx_sock.send(frame)

    def recv(self, bufsize: int = 65535) -> Tuple[bytes, Tuple[str, int]]:
        if not self.rx_sock:
            raise RuntimeError("Socket RX no abierto")
        return self.rx_sock.recvfrom(bufsize)


# ---------------------- Worker de escucha (hilo) ----------------------

class LinkListener(threading.Thread):
    """Hilo que recibe frames y los publica a una cola para la GUI."""
    def __init__(self, medium: AFPacketMedium, out_queue: "queue.Queue[str]"):
        super().__init__(daemon=True)
        self.medium = medium
        self.out_queue = out_queue
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                data, (ifname, proto) = self.medium.recv()
                # Parseo del header Ethernet (14 bytes)
                if len(data) < 14:
                    continue
                dst, src, etype = struct.unpack(ETH_HEADER_FMT, data[:14])
                payload = data[14:]
                # Si se está filtrando por protocolo, etype ya debe coincidir. Aun así, mostramos.
                msg = (
                    f"IF={ifname} src={mac_bytes_to_str(src)} dst={mac_bytes_to_str(dst)} "
                    f"etype=0x{etype:04x} len={len(payload)}\n"
                )
                # Intentar mostrar payload como UTF-8 si es plausible
                try:
                    text = payload.decode('utf-8')
                    msg += f"payload (utf-8): {text}\n"
                except UnicodeDecodeError:
                    msg += f"payload (hex): {payload[:64].hex()}...\n"
                self.out_queue.put(msg)
            except OSError:
                # sockets cerrados
                break
            except Exception as e:
                self.out_queue.put(f"[ERROR RX] {e}\n")
                time.sleep(0.05)

    def stop(self):
        self._stop.set()


# ---------------------- GUI (PyQt6) ----------------------

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QMessageBox
)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LinkChat L2 (AF_PACKET)")
        self.medium: Optional[AFPacketMedium] = None
        self.listener: Optional[LinkListener] = None
        self.rx_queue: "queue.Queue[str]" = queue.Queue()

        # Widgets
        self.iface_edit = QLineEdit("eth0")
        self.etype_edit = QLineEdit("0x88B5")
        self.dstmac_edit = QLineEdit("ff:ff:ff:ff:ff:ff")

        self.payload_edit = QTextEdit()
        self.payload_edit.setPlaceholderText("Escribe el mensaje (se enviará como UTF-8)")

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        self.btn_start = QPushButton("Iniciar")
        self.btn_stop = QPushButton("Detener")
        self.btn_send = QPushButton("Enviar")
        self.btn_clear = QPushButton("Limpiar log")

        # Layout
        top = QHBoxLayout()
        top.addWidget(QLabel("Interfaz:"))
        top.addWidget(self.iface_edit, 1)
        top.addWidget(QLabel("Ethertype:"))
        top.addWidget(self.etype_edit)
        top.addWidget(QLabel("MAC destino:"))
        top.addWidget(self.dstmac_edit)

        btns = QHBoxLayout()
        btns.addWidget(self.btn_start)
        btns.addWidget(self.btn_stop)
        btns.addStretch(1)
        btns.addWidget(self.btn_send)
        btns.addWidget(self.btn_clear)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(QLabel("Payload a enviar:"))
        root.addWidget(self.payload_edit, 1)
        root.addLayout(btns)
        root.addWidget(QLabel("Frames recibidos:"))
        root.addWidget(self.log_view, 2)

        # Conexiones
        self.btn_start.clicked.connect(self.start_medium)
        self.btn_stop.clicked.connect(self.stop_medium)
        self.btn_send.clicked.connect(self.send_payload)
        self.btn_clear.clicked.connect(self.log_view.clear)

        # Timer para drenar la cola de RX sin bloquear la GUI
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.drain_rx_queue)
        self.timer.start(50)

        self.update_buttons(running=False)

    def update_buttons(self, running: bool):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_send.setEnabled(running)

    def start_medium(self):
        if os.geteuid() != 0:
            QMessageBox.critical(self, "Permisos", "Debes ejecutar como root o con CAP_NET_RAW")
            return
        iface = self.iface_edit.text().strip()
        etype_txt = self.etype_edit.text().strip().lower()
        try:
            ethertype = int(etype_txt, 16) if etype_txt.startswith("0x") else int(etype_txt)
        except ValueError:
            QMessageBox.warning(self, "Ethertype", "Ethertype inválido (usa ej. 0x88B5)")
            return
        try:
            self.medium = AFPacketMedium(iface=iface, ethertype=ethertype, filter_ethertype=True)
            self.medium.open()
        except Exception as e:
            self.medium = None
            QMessageBox.critical(self, "AF_PACKET", f"No se pudo abrir AF_PACKET: {e}")
            return

        # Lanzar listener
        self.listener = LinkListener(self.medium, self.rx_queue)
        self.listener.start()
        self.log(f"Iniciado en {iface} con ethertype 0x{ethertype:04x}. MAC origen={mac_bytes_to_str(self.medium.src_mac)}\n")
        self.update_buttons(running=True)

    def stop_medium(self):
        if self.listener:
            try:
                self.listener.stop()
                # Darle tiempo a salir del recv
                try:
                    # Cerrar sockets para desbloquear el hilo
                    if self.medium:
                        self.medium.close()
                finally:
                    self.listener.join(timeout=0.5)
            except Exception:
                pass
            self.listener = None
        if self.medium:
            try:
                self.medium.close()
            except Exception:
                pass
            self.medium = None
        self.update_buttons(running=False)
        self.log("Detenido.\n")

    def send_payload(self):
        if not self.medium:
            QMessageBox.information(self, "No iniciado", "Primero pulsa Iniciar")
            return
        dst = self.dstmac_edit.text().strip().lower()
        text = self.payload_edit.toPlainText()
        payload = text.encode('utf-8')
        try:
            frame = self.medium.make_frame(dst, payload)
            self.medium.send(frame)
            self.log(f"Enviado a {dst} len={len(payload)} bytes.\n")
        except Exception as e:
            QMessageBox.critical(self, "Enviar", str(e))

    def log(self, s: str):
        self.log_view.moveCursor(self.log_view.textCursor().End)
        self.log_view.insertPlainText(s)
        self.log_view.moveCursor(self.log_view.textCursor().End)

    def drain_rx_queue(self):
        try:
            while True:
                msg = self.rx_queue.get_nowait()
                self.log(msg)
        except queue.Empty:
            pass

    def closeEvent(self, event):
        self.stop_medium()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(900, 650)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
