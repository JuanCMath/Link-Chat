"""
raw_socket.py
~~~~~~~~~~~~~

Raw Ethernet socket manager for Layer 2 network communication.

This module provides a low-level interface for sending and receiving complete
Ethernet frames directly at the data link layer, bypassing the IP/TCP stack.

Requirements:
    - Linux kernel with AF_PACKET support
    - CAP_NET_RAW capability (root or setcap)
    - Physical or virtual network interface

Typical Use:
    >>> manager = SocketManager(iface="eth0", ethertype=0x88B5)
    >>> manager.open()
    >>> manager.send_raw_frame(ethernet_frame_bytes)
    >>> frame = manager.receive_raw_frame()
    >>> manager.close()
"""
import socket
from typing import Optional


class SocketManager:
    """
    Manages raw Ethernet socket operations for Layer 2 communication.

    This class wraps AF_PACKET/SOCK_RAW sockets to enable direct Ethernet frame
    transmission and reception. It handles socket lifecycle, frame I/O, and
    provides MAC address resolution from the system.

    Attributes:
        iface: Network interface name (e.g., "eth0", "wlan0").
        ethertype: Custom EtherType identifier (0x0800-0xFFFF).
        receive_buffer_size: Maximum bytes to receive per frame.
        timeout_seconds: Socket receive timeout in seconds (None = blocking).

    Note:
        Opening the socket requires CAP_NET_RAW capability. In Docker containers,
        use --cap-add=NET_RAW --cap-add=NET_ADMIN.
    """

    def __init__(
        self,
        iface: str = "eth0",
        ethertype: int = 0x88B5,
        receive_buffer_size: int = 65535,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        """
        Initialize the socket manager with interface and protocol parameters.

        Args:
            iface: Network interface to bind to.
            ethertype: Custom EtherType for filtering frames (default: 0x88B5).
            receive_buffer_size: Maximum frame size to receive (default: 64KB).
            timeout_seconds: Receive timeout; None for blocking I/O.
        """
        self.iface = iface
        self.ethertype = ethertype
        self.receive_buffer_size = receive_buffer_size
        self.timeout_seconds = timeout_seconds
        self._socket: Optional[socket.socket] = None

    def open(self) -> None:
        """
        Open and bind the raw socket to the configured interface.

        Creates an AF_PACKET socket with SOCK_RAW type, binds it to the specified
        interface, and applies the configured timeout. The socket will only receive
        frames matching the configured EtherType.

        Raises:
            PermissionError: If CAP_NET_RAW capability is missing.
            OSError: If the interface doesn't exist or binding fails.

        Note:
            Safe to call multiple times; does nothing if already open.
        """
        if self._socket:
            return

        # Create raw packet socket filtered by EtherType
        self._socket = socket.socket(
            socket.AF_PACKET, socket.SOCK_RAW, socket.htons(self.ethertype)
        )

        # Bind to specific interface (protocol=0 means all protocols on this interface)
        self._socket.bind((self.iface, 0))

        # Apply timeout if configured
        if self.timeout_seconds is not None:
            self._socket.settimeout(self.timeout_seconds)

    def close(self) -> None:
        """
        Close the raw socket and release system resources.

        Safe to call multiple times; does nothing if already closed.
        """
        if self._socket:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def send_raw_frame(self, frame: bytes) -> int:
        """
        Send a complete Ethernet frame to the network.

        Args:
            frame: Complete Ethernet frame including destination MAC, source MAC,
                   EtherType, and payload. Minimum 60 bytes (padding applied by kernel).

        Returns:
            int: Number of bytes sent.

        Raises:
            RuntimeError: If socket is not open.
            OSError: If transmission fails.

        Example:
            >>> frame = dst_mac + src_mac + ethertype_bytes + payload
            >>> bytes_sent = manager.send_raw_frame(frame)
        """
        if not self._socket:
            raise RuntimeError("Socket not open; call open() first")
        return self._socket.sendto(frame, (self.iface, 0))

    def receive_raw_frame(self) -> Optional[bytes]:
        """
        Receive a complete Ethernet frame from the network.

        Blocks until a frame matching the configured EtherType arrives, or until
        the timeout expires (if configured). Returns the complete frame including
        all headers.

        Returns:
            Optional[bytes]: Complete Ethernet frame, or None if timeout occurred
                            or operation was interrupted.

        Raises:
            RuntimeError: If socket is not open.

        Note:
            The kernel automatically filters frames by EtherType based on the
            socket configuration from open().
        """
        if not self._socket:
            raise RuntimeError("Socket not open; call open() first")
        try:
            return self._socket.recv(self.receive_buffer_size)
        except socket.timeout:
            # Timeout is normal in non-blocking scenarios
            return None
        except InterruptedError:
            # Signal interruption (e.g., Ctrl+C) should be handled gracefully
            return None

    def get_mac_address(self) -> str:
        """
        Retrieve the MAC address of the configured network interface.

        Reads the hardware address from the Linux sysfs filesystem. This is more
        reliable than parsing ifconfig/ip output and works without additional tools.

        Returns:
            str: MAC address in lowercase colon notation (e.g., "aa:bb:cc:dd:ee:ff").
                 Returns "00:00:00:00:00:00" if the interface is invalid or inaccessible.

        Example:
            >>> manager = SocketManager(iface="eth0")
            >>> mac = manager.get_mac_address()  # "08:00:27:4a:5b:6c"
        """
        sysfs_path = f"/sys/class/net/{self.iface}/address"
        try:
            with open(sysfs_path, "r", encoding="utf-8") as file:
                return file.read().strip().lower()
        except Exception:
            # Return null MAC if interface doesn't exist or isn't accessible
            return "00:00:00:00:00:00"
        
    def change_interface(self, new_iface: str = "") -> bool:
        
        ok = False

        try:
            self.close()
            from ..utils.network_utils import is_iface_down
            self.iface = self.iface if is_iface_down(new_iface) else new_iface
            ok = (self.iface == new_iface)
        finally:
            self.open()
        
        return ok