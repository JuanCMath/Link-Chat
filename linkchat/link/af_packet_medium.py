# af_packet_medium.py
# Medio de capa de enlace con AF_PACKET (Linux).
# Enviar/recibir tramas Ethernet crudas. Ideal para encapsular tu propio framing.

import socket
import struct
import os
from typing import Iterator, Tuple, Optional

ETH_P_ALL = 0x0003         # Capturar todo lo que pase por la interfaz
DEFAULT_ETHERTYPE = 0x88B5 # Elige un Ethertype "propio" para filtrar tus tramas

class AFPacketMedium:
    def __init__(self, iface: str = "eth0", ethertype: int = DEFAULT_ETHERTYPE,
                 filter_ethertype: bool = True, bufsize: int = 65535):
        """
        iface: interfaz de red (p.ej. 'eth0', 'enp3s0', 'vethXYZ', etc.)
        ethertype: usado para marcar tus tramas y filtrarlas al recibir.
        filter_ethertype: si True, el receive_iter solo entrega tramas de ese ethertype.
        """
        self.iface = iface
        self.ethertype = ethertype
        self.filter_ethertype = filter_ethertype
        self.bufsize = bufsize

        # Socket RAW a nivel de enlace
        self.sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
        self.sock.bind((self.iface, 0))
        self.src_mac = self._get_mac_bytes(self.iface)

    # -------- Utilidades MAC --------
    @staticmethod
    def _get_mac_bytes(iface: str) -> bytes:
        path = f"/sys/class/net/{iface}/address"
        with open(path, "r") as f:
            mac_txt = f.read().strip()
        return bytes(int(b, 16) for b in mac_txt.split(":"))

    @staticmethod
    def mac_str_to_bytes(mac: str) -> bytes:
        # "aa:bb:cc:dd:ee:ff" -> 6 bytes
        return bytes(int(b, 16) for b in mac.split(":"))

    @staticmethod
    def mac_bytes_to_str(mac: bytes) -> str:
        return ":".join(f"{b:02x}" for b in mac)

    # -------- Envío/recepción --------
    def send(self, dst_mac: bytes, payload: bytes, ethertype: Optional[int] = None):
        """
        Envía una trama Ethernet con payload arbitrario (tu framing).
        """
        if ethertype is None:
            ethertype = self.ethertype
        if len(dst_mac) != 6:
            raise ValueError("dst_mac debe tener 6 bytes")
        if len(self.src_mac) != 6:
            raise RuntimeError("MAC local inválida")
        eth_header = dst_mac + self.src_mac + struct.pack("!H", ethertype)
        frame = eth_header + payload
        self.sock.send(frame)

    def receive_iter(self) -> Iterator[Tuple[bytes, bytes, int, bytes]]:
        """
        Itera sobre tramas recibidas:
        yield (dst_mac, src_mac, ethertype, payload)
        """
        while True:
            frame, _ = self.sock.recvfrom(self.bufsize)
            if len(frame) < 14:
                continue
            dst = frame[0:6]
            src = frame[6:12]
            etype = struct.unpack("!H", frame[12:14])[0]
            payload = frame[14:]
            if self.filter_ethertype and etype != self.ethertype:
                continue
            yield (dst, src, etype, payload)

    def recv_once(self, timeout: float = 0.0) -> Optional[Tuple[bytes, bytes, int, bytes]]:
        """
        Recibe una trama con timeout (seg). Devuelve None si no llega nada.
        """
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            frame, _ = self.sock.recvfrom(self.bufsize)
        except socket.timeout:
            return None
        if len(frame) < 14:
            return None
        dst = frame[0:6]
        src = frame[6:12]
        etype = struct.unpack("!H", frame[12:14])[0]
        payload = frame[14:]
        if self.filter_ethertype and etype != self.ethertype:
            return None
        return (dst, src, etype, payload)
