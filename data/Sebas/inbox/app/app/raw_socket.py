# raw_socket.py
import socket
from typing import Optional

class SocketManager:
    """
    Socket RAW Ethernet (AF_PACKET/ SOCK_RAW). Envía y recibe tramas completas.
    Requiere capacidades NET_RAW (y normalmente NET_ADMIN en Docker).
    """
    def __init__(self, iface: str = "eth0", ethertype: int = 0x88B5,
                 recv_buf: int = 65535, timeout: Optional[float] = None):
        self.iface = iface
        self.ethertype = ethertype
        self.recv_buf = recv_buf
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None

    def open(self) -> None:
        if self._sock:
            return
        self._sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW,
                                   socket.htons(self.ethertype))
        self._sock.bind((self.iface, 0))
        if self.timeout is not None:
            self._sock.settimeout(self.timeout)

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def send_raw_frame(self, frame: bytes) -> int:
        if not self._sock:
            raise RuntimeError("Socket no abierto")
        return self._sock.sendto(frame, (self.iface, 0))

    def receive_raw_frame(self) -> Optional[bytes]:
        if not self._sock:
            raise RuntimeError("Socket no abierto")
        try:
            return self._sock.recv(self.recv_buf)
        except socket.timeout:
            return None
        except InterruptedError:
            return None

    def get_mac_address(self) -> str:
        path = f"/sys/class/net/{self.iface}/address"
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip().lower()
        except Exception:
            return "00:00:00:00:00:00"
