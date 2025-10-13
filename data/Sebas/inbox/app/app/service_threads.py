# service_threads.py
import logging
import queue
import threading
import time
from typing import Callable, Optional, Tuple

from raw_socket import SocketManager

BROADCAST_MAC_BYTES = b"\xff\xff\xff\xff\xff\xff"

def mac_str_to_bytes(mac: str) -> bytes:
    return bytes(int(part, 16) for part in mac.split(":"))

def mac_bytes_to_str(mac: bytes) -> str:
    return ":".join(f"{b:02x}" for b in mac)

def pack_eth(dst_mac: bytes, src_mac: bytes, ethertype: int, payload: bytes) -> bytes:
    return dst_mac + src_mac + ethertype.to_bytes(2, "big") + payload

def unpack_eth(frame: bytes) -> Optional[Tuple[bytes, bytes, int, bytes]]:
    if len(frame) < 14:
        return None
    dst = frame[0:6]
    src = frame[6:12]
    et = int.from_bytes(frame[12:14], "big")
    data = frame[14:]
    return dst, src, et, data

class ThreadManager:
    """
    Administra RX/TX/Dispatch con frames Ethernet binarios exactos.
    on_frame(dst_bytes, src_bytes, payload_bytes)
    """
    def __init__(self, sock: SocketManager,
                 on_frame: Optional[Callable[[bytes, bytes, bytes], None]] = None,
                 drop_own_frames: bool = True):
        self.sock = sock
        self.on_frame = on_frame
        self.drop_own = drop_own_frames

        self._incoming: "queue.Queue[bytes]" = queue.Queue()
        self._outgoing: "queue.Queue[bytes]" = queue.Queue()
        self._stop = threading.Event()

        self._rx_t = threading.Thread(target=self._rx_loop, name="rx", daemon=True)
        self._tx_t = threading.Thread(target=self._tx_loop, name="tx", daemon=True)
        self._dp_t = threading.Thread(target=self._dispatch_loop, name="dispatch", daemon=True)

        self._my_mac_bytes: Optional[bytes] = None

    def start(self):
        self.sock.open()
        self._my_mac_bytes = mac_str_to_bytes(self.sock.get_mac_address())
        self._stop.clear()
        self._rx_t.start()
        self._tx_t.start()
        self._dp_t.start()
        logging.info("[ThreadManager] Hilos rx/tx/dispatch iniciados.")

    def stop(self):
        self._stop.set()
        try:
            self._outgoing.put_nowait(b"")
        except Exception:
            pass
        for t in (self._rx_t, self._tx_t, self._dp_t):
            t.join(timeout=1.0)
        logging.info("[ThreadManager] Hilos detenidos.")

    # -------- envío ----------
    def send_frame_bytes(self, frame: bytes):
        self._outgoing.put(frame)

    def send_unicast_payload(self, dst_mac: bytes, payload: bytes, ethertype: Optional[int] = None):
        if self._my_mac_bytes is None:
            raise RuntimeError("ThreadManager no iniciado.")
        if ethertype is None:
            ethertype = self.sock.ethertype
        frame = pack_eth(dst_mac, self._my_mac_bytes, ethertype, payload)
        self._outgoing.put(frame)

    def send_broadcast_payload(self, payload: bytes, ethertype: Optional[int] = None):
        if self._my_mac_bytes is None:
            raise RuntimeError("ThreadManager no iniciado.")
        if ethertype is None:
            ethertype = self.sock.ethertype
        frame = pack_eth(BROADCAST_MAC_BYTES, self._my_mac_bytes, ethertype, payload)
        self._outgoing.put(frame)

    # -------- loops ----------
    def _rx_loop(self):
        logging.info("[RX] hilo iniciado")
        while not self._stop.is_set():
            try:
                frame = self.sock.receive_raw_frame()
                if frame:
                    self._incoming.put(frame)
            except Exception as e:
                logging.error(f"[RX] {e}")
                time.sleep(0.2)

    def _tx_loop(self):
        logging.info("[TX] hilo iniciado")
        while not self._stop.is_set():
            try:
                frame = self._outgoing.get(timeout=0.2)
            except queue.Empty:
                continue
            if self._stop.is_set():
                break
            try:
                if frame:
                    self.sock.send_raw_frame(frame)
            except Exception as e:
                logging.error(f"[TX] {e}")

    def _dispatch_loop(self):
        logging.info("[DP] hilo iniciado")
        etype = self.sock.ethertype
        while not self._stop.is_set():
            try:
                frame = self._incoming.get(timeout=0.2)
            except queue.Empty:
                continue
            parsed = unpack_eth(frame)
            if not parsed:
                continue
            dst, src, et, payload = parsed
            if et != etype:
                continue
            if self.drop_own and self._my_mac_bytes and src == self._my_mac_bytes:
                continue
            if self.on_frame:
                try:
                    self.on_frame(dst, src, payload)  # BYTES crudos
                except Exception as e:
                    logging.error(f"[DISPATCH] on_frame error: {e}")
