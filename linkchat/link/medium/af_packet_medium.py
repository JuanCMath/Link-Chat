"""AF_PACKET medium for raw Ethernet frame transmission (Linux only).

Provides a link-layer interface using AF_PACKET sockets to send and receive
raw Ethernet frames.
"""

import socket
import struct
import os
from typing import Iterator, Tuple, Optional

ETH_P_ALL = 0x0003
DEFAULT_ETHERTYPE = 0x88B5

class AFPacketMedium:
    """Raw Ethernet socket interface using AF_PACKET (Linux only).
    
    Provides methods to send and receive Ethernet frames at the link layer,
    with optional filtering by Ethertype. Requires root privileges or
    CAP_NET_RAW capability.
    """
    
    def __init__(self, iface: str = "eth0", ethertype: int = DEFAULT_ETHERTYPE,
                 filter_ethertype: bool = True, bufsize: int = 65535):
        """Initialize the AF_PACKET medium on a network interface.
        
        Args:
            iface: Network interface name (e.g., 'eth0', 'enp3s0', 'vethXYZ').
            ethertype: Custom Ethertype value for frame identification and filtering.
            filter_ethertype: If True, only receive frames matching the specified Ethertype.
            bufsize: Socket receive buffer size in bytes.
        """
        self.iface = iface
        self.ethertype = ethertype
        self.filter_ethertype = filter_ethertype
        self.bufsize = bufsize

        self.sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
        self.sock.bind((self.iface, 0))
        self.src_mac = self._get_mac_bytes(self.iface)

    @staticmethod
    def _get_mac_bytes(iface: str) -> bytes:
        """Read the MAC address of a network interface from sysfs.
        
        Args:
            iface: Network interface name.
        
        Returns:
            6-byte MAC address.
        """
        path = f"/sys/class/net/{iface}/address"
        with open(path, "r") as f:
            mac_txt = f.read().strip()
        return AFPacketMedium.mac_str_to_bytes(mac_txt)

    @staticmethod
    def mac_str_to_bytes(mac: str) -> bytes:
        """Convert MAC address string to bytes.
        
        Args:
            mac: MAC address in colon-separated hex format (e.g., 'aa:bb:cc:dd:ee:ff').
        
        Returns:
            6-byte MAC address.
        """
        return bytes(int(b, 16) for b in mac.split(":"))

    @staticmethod
    def mac_bytes_to_str(mac: bytes) -> str:
        """Convert MAC address bytes to colon-separated hex string.
        
        Args:
            mac: 6-byte MAC address.
        
        Returns:
            MAC address string (e.g., 'aa:bb:cc:dd:ee:ff').
        """
        return ":".join(f"{b:02x}" for b in mac)

    def send(self, dst_mac: bytes, payload: bytes, ethertype: Optional[int] = None):
        """Send an Ethernet frame with custom payload.
        
        Constructs and transmits an Ethernet frame with the specified destination
        MAC, source MAC (from this interface), Ethertype, and payload.
        
        Args:
            dst_mac: Destination MAC address (6 bytes).
            payload: Frame payload data.
            ethertype: Ethertype value, or None to use the default.
        
        Raises:
            ValueError: If dst_mac is not exactly 6 bytes.
            RuntimeError: If local MAC address is invalid.
        """
        if ethertype is None:
            ethertype = self.ethertype
        if len(dst_mac) != 6:
            raise ValueError("dst_mac must be 6 bytes")
        if len(self.src_mac) != 6:
            raise RuntimeError("Invalid local MAC address")
        eth_header = dst_mac + self.src_mac + struct.pack("!H", ethertype)
        frame = eth_header + payload
        self.sock.send(frame)

    def receive_iter(self) -> Iterator[Tuple[bytes, bytes, int, bytes]]:
        """Iterate over received Ethernet frames.
        
        Continuously receives frames from the socket, optionally filtering by
        Ethertype. Yields tuples containing frame components.
        
        Yields:
            Tuple of (dst_mac, src_mac, ethertype, payload) for each received frame.
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
        """Receive a single Ethernet frame with timeout.
        
        Args:
            timeout: Maximum time to wait in seconds (0.0 for blocking).
        
        Returns:
            Tuple of (dst_mac, src_mac, ethertype, payload) if a frame is received,
            or None if timeout expires without receiving a matching frame.
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
