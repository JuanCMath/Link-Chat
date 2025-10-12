"""Flexible AF_PACKET medium supporting Ethernet and Wi-Fi drivers.

This module provides an enhanced AF_PACKET socket interface that can work with
both Ethernet and Wi-Fi network interfaces. It automatically adapts to the
capabilities of the underlying network driver by selecting the appropriate
socket type and configuration.

Key Features:
    - Automatic socket type selection: Tries SOCK_RAW for native Ethernet
      frames, falls back to SOCK_DGRAM (Linux cooked packets) for Wi-Fi
      chipsets that don't support raw frame injection in managed mode.
    - Promiscuous mode support: Optionally enables promiscuous mode to receive
      peer-to-peer frames that would normally be filtered by the kernel.
    - Interface metadata queries: Provides convenient access to MAC address,
      MTU, and other interface properties via ioctl system calls.
    - Dual-mode frame parsing: Correctly parses both raw Ethernet frames and
      Linux cooked packets depending on the socket type.

Socket Types:
    - SOCK_RAW: Sends and receives complete Ethernet frames including the
      14-byte Ethernet header. Best for Ethernet interfaces and some Wi-Fi
      drivers.
    - SOCK_DGRAM: Uses Linux cooked packet format where the kernel handles
      the Ethernet header. Required for most Wi-Fi interfaces in managed mode.

This module is designed to be a drop-in replacement for the basic AFPacketMedium,
offering greater compatibility across different network interface types while
maintaining the same general API.
"""

from __future__ import annotations

import fcntl  # type: ignore[attr-defined]
import logging
import socket
import struct
from time import time, sleep
from typing import Iterator, Optional, Tuple

logger = logging.getLogger(__name__)

# Protocol constants for AF_PACKET sockets
ETH_P_ALL = 0x0003  # Receive all Ethernet protocols
AF_PACKET = getattr(socket, "AF_PACKET", 17)  # Packet socket address family

# ioctl request codes for interface configuration
SIOCGIFHWADDR = 0x8927  # Get hardware address (MAC)
SIOCGIFINDEX = 0x8933   # Get interface index
SIOCGIFFLAGS = 0x8913   # Get interface flags
SIOCSIFFLAGS = 0x8914   # Set interface flags
SIOCGIFMTU = 0x8921     # Get Maximum Transfer Unit

# Interface flag bits
IFF_PROMISC = 0x100     # Promiscuous mode enabled


def wait_interface_up(iface, timeout=5.0):
        start = time()
        while time() - start < timeout:
            try:
                with open(f"/sys/class/net/{iface}/operstate") as f:
                    if f.read().strip() not in {"down", "notpresent"}:
                        return True
            except FileNotFoundError:
                pass
            sleep(0.1)
        print(f"Interface {iface} not up, timeout of {timeout}s reached")
        raise RuntimeError(f"Interface {iface} not up after {timeout}s")


class AFPacketMediumEthWifi:
    """Enhanced AF_PACKET medium with automatic Ethernet/Wi-Fi adaptation.
    
    Provides layer-2 frame transmission and reception with automatic socket
    type selection to support both Ethernet and Wi-Fi interfaces. Handles
    the differences between SOCK_RAW (complete Ethernet frames) and SOCK_DGRAM
    (Linux cooked packets) transparently.
    
    Attributes:
        iface: Network interface name (e.g., "eth0", "wlan0").
        ethertype: EtherType value for filtering and transmission.
        filter_ethertype: Whether to filter received frames by EtherType.
        bufsize: Receive buffer size in bytes.
        mode: Socket type selection mode ("auto", "raw", or "cooked").
        enable_promiscuous: Whether to enable promiscuous mode.
        ifindex: Kernel interface index for this interface.
        hwaddr: Interface hardware (MAC) address.
        hatype: Hardware address type (e.g., 1 for Ethernet).
        src_mac: Source MAC address (same as hwaddr).
        mtu: Maximum Transmission Unit for this interface.
        sock_type: Selected socket type (SOCK_RAW or SOCK_DGRAM).
        sock: Active AF_PACKET socket for frame I/O.
    """
    
    def __init__(
        self,
        iface: str,
        ethertype: int,
        filter_ethertype: bool = True,
        bufsize: int = 65535,
        mode: str = "auto",
        enable_promiscuous: bool = False,
    ) -> None:
        """Initialize the AF_PACKET medium with automatic configuration.
        
        Queries interface metadata, selects appropriate socket type, creates
        the socket, and optionally enables promiscuous mode. The initialization
        process automatically adapts to the capabilities of the underlying
        network driver.
        
        Process:
        1. Query interface index via if_nametoindex().
        2. Query MAC address and hardware type via sysfs.
        3. Query MTU via sysfs.
        4. Decide socket type based on mode parameter and driver capabilities.
        5. Create and bind AF_PACKET socket.
        6. Optionally enable promiscuous mode via ioctl.
        
        Args:
            iface: Network interface name (must exist and be accessible).
            ethertype: EtherType value for frame filtering and transmission
                (e.g., 0x88B5 for custom protocol).
            filter_ethertype: If True, only receive frames matching ethertype.
                If False, receive all frames (use ETH_P_ALL).
            bufsize: Socket receive buffer size in bytes (default 65535).
            mode: Socket type selection strategy:
                - "auto": Try SOCK_RAW first, fall back to SOCK_DGRAM.
                - "raw": Force SOCK_RAW (fails on incompatible drivers).
                - "cooked": Force SOCK_DGRAM (Linux cooked packets).
            enable_promiscuous: If True, enable promiscuous mode to receive
                all frames on the network segment.
        
        Raises:
            OSError: If interface doesn't exist, permissions are insufficient,
                or socket creation fails.
            RuntimeError: If socket type selection fails after trying all
                configured options.
        """

        wait_interface_up(iface)
        self.iface = iface
        self.ethertype = ethertype
        self.filter_ethertype = filter_ethertype
        self.bufsize = bufsize
        self.mode = mode.lower()
        self.enable_promiscuous = enable_promiscuous

        self._control_sock: Optional[socket.socket] = None

        self.ifindex = socket.if_nametoindex(iface)
        self.hwaddr, self.hatype = self._query_hwaddr()
        self.src_mac = self.hwaddr
        self.mtu = self._query_mtu()

        self.sock_type = self._decide_socket_type()
        self.sock = self._open_socket(self.sock_type)

        if self.enable_promiscuous:
            self._set_promiscuous(True)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def close(self) -> None:
        """Close the socket and clean up resources.
        
        Disables promiscuous mode if it was enabled, closes the main AF_PACKET
        socket, and closes the control socket used for ioctl operations.
        This method should be called when the medium is no longer needed to
        properly release system resources.
        
        Suppresses any OSError exceptions that occur during cleanup to ensure
        all cleanup steps are attempted even if some fail.
        """
        if self.enable_promiscuous:
            try:
                self._set_promiscuous(False)
            except OSError as e:
                logger.warning("Failed to disable promiscuous mode: %s", e)
        try:
            self.sock.close()
        except OSError as e:
            logger.warning("Failed to close main socket: %s", e)
        if self._control_sock is not None:
            try:
                self._control_sock.close()
            except OSError as e:
                logger.warning("Failed to close control socket: %s", e)
            self._control_sock = None

    def send(self, dst_mac: bytes, payload: bytes, ethertype: Optional[int] = None) -> None:
        """Send a frame to the specified destination MAC address.
        
        Constructs and transmits a layer-2 frame using the appropriate format
        for the current socket type:
        - SOCK_RAW: Builds complete Ethernet frame with 14-byte header.
        - SOCK_DGRAM: Uses sendto() with sockaddr_ll structure, kernel adds header.
        
        Args:
            dst_mac: Destination MAC address (must be exactly 6 bytes).
            payload: Frame payload data (does not include Ethernet header).
            ethertype: Optional EtherType value for this frame. If None, uses
                the instance's configured ethertype.
        
        Raises:
            ValueError: If dst_mac is not exactly 6 bytes.
            OSError: If socket send operation fails.
        """
        if ethertype is None:
            ethertype = self.ethertype
        if len(dst_mac) != 6:
            raise ValueError("dst_mac must be 6 bytes")

        if self.sock_type == socket.SOCK_RAW:
            header = dst_mac + self.src_mac + struct.pack("!H", ethertype)
            frame = header + payload
            self.sock.send(frame)
            return

        sockaddr_ll = struct.pack(
            "!HHIHH8s",
            AF_PACKET,
            socket.htons(ethertype),
            self.ifindex,
            self.hatype,
            0,
            dst_mac + b"\x00" * 2,
        )
        self.sock.sendto(payload, sockaddr_ll)

    def receive_iter(self) -> Iterator[Tuple[bytes, bytes, int, bytes]]:
        """Infinite iterator yielding received frames.
        
        Continuously receives frames from the socket, parses them according to
        the socket type, and yields frames that pass EtherType filtering (if
        enabled). This method blocks indefinitely waiting for frames.
        
        Yields:
            Tuple of (dst_mac, src_mac, ethertype, payload) for each received
            frame that passes filtering. Frames that fail parsing or filtering
            are silently discarded.
        
        Note:
            This is a blocking infinite loop. Use recv_once() if you need
            timeout or single-frame semantics.
        """
        while True:
            frame, _ = self.sock.recvfrom(self.bufsize)
            parsed = self._parse_frame(frame)
            if parsed is None:
                continue
            dst, src, etype, payload = parsed
            if self.filter_ethertype and etype != self.ethertype:
                continue
            yield parsed

    def recv_once(self, timeout: float = 0.0) -> Optional[Tuple[bytes, bytes, int, bytes]]:
        """Receive a single frame with optional timeout.
        
        Waits for one frame from the socket, parses it, and returns it if it
        passes EtherType filtering. Returns None if timeout expires or frame
        is filtered out.
        
        Args:
            timeout: Maximum time in seconds to wait for a frame. If 0.0,
                uses socket's default (may block indefinitely). If None,
                non-blocking mode.
        
        Returns:
            Tuple of (dst_mac, src_mac, ethertype, payload) if a matching frame
            is received, None if timeout expires or frame doesn't pass filtering.
        
        Raises:
            OSError: If socket receive operation fails (except timeout).
        """
        try:
            for _ in range(3):
                with open(f"/sys/class/net/{self.iface}/operstate") as f:
                    state = f.read().strip().lower()
                if state not in {"down", "notpresent"}:
                    break
                sleep(0.2)
            else:
                raise OSError(100, f"Network is down (state: {state})")

        except FileNotFoundError:
            raise OSError(100, f"Interface {self.iface} no longer exists")
        

        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            frame, _ = self.sock.recvfrom(self.bufsize)
        except socket.timeout:
            return None
        except OSError as e:
            if e.errno == 100:
                logger.warning("Network down, attempting recovery...")
                self._reopen_socket()
                return None  # Skip this receive cycle
            raise
        
        parsed = self._parse_frame(frame)
        if parsed is None:
            return None
        dst, src, etype, payload = parsed
        if self.filter_ethertype and etype != self.ethertype:
            return None
        return parsed


    def _reopen_socket(self):
        """Reopen socket if interface went down."""
        try:
            if self.sock:
                self.sock.close()
            self.sock = self._open_socket(self.sock_type)
            if self.enable_promiscuous:
                self._set_promiscuous(True)
            logger.info(f"Socket reopened on {self.iface}")
        except Exception as e:
            logger.error(f"Failed to reopen socket: {e}")
            raise


    # ------------------------------------------------------------------
    # Interface / ioctl helpers
    # ------------------------------------------------------------------
    def _control_socket(self) -> socket.socket:
        """Get or create the control socket for ioctl operations.
        
        Creates an AF_PACKET socket on first call and caches it for subsequent
        ioctl operations. This socket is separate from the main AF_PACKET socket
        and is used only for interface configuration queries.
        
        Returns:
            AF_PACKET SOCK_DGRAM socket for ioctl operations.
        """
        if self._control_sock is None:
            # Use AF_PACKET with SOCK_DGRAM for ioctl operations
            self._control_sock = socket.socket(AF_PACKET, socket.SOCK_DGRAM, 0)
        return self._control_sock

    def _query_hwaddr(self) -> Tuple[bytes, int]:
        """Query the interface's hardware address and type via sysfs.
        
        Reads MAC address from /sys/class/net/{iface}/address and hardware type
        from /sys/class/net/{iface}/type using the sysfs filesystem interface.
        
        Returns:
            Tuple of (mac_address, hardware_type) where mac_address is 6 bytes
            and hardware_type is an integer (1 for Ethernet/802.3).
        
        Raises:
            OSError: If interface doesn't exist or files cannot be read.
        """
        # Read MAC address from sysfs
        mac_path = f"/sys/class/net/{self.iface}/address"
        with open(mac_path, "r") as f:
            mac_str = f.read().strip()
        mac = bytes(int(part, 16) for part in mac_str.split(":"))
        
        # Read hardware type from sysfs (1 = Ethernet, 801 = WLAN)
        type_path = f"/sys/class/net/{self.iface}/type"
        try:
            with open(type_path, "r") as f:
                hatype = int(f.read().strip())
        except (OSError, ValueError):
            hatype = 1  # Default to Ethernet
        
        return mac, hatype

    def _query_mtu(self) -> int:
        """Query the interface's Maximum Transmission Unit via sysfs.
        
        Reads MTU from /sys/class/net/{iface}/mtu using the sysfs filesystem
        interface. Falls back to 1500 bytes (standard Ethernet MTU) if the
        query fails.
        
        Returns:
            MTU size in bytes, or 1500 if query fails.
        """
        mtu_path = f"/sys/class/net/{self.iface}/mtu"
        try:
            with open(mtu_path, "r") as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return 1500

    def _set_promiscuous(self, enable: bool) -> None:
        """Enable or disable promiscuous mode for the interface.
        
        Uses SIOCGIFFLAGS and SIOCSIFFLAGS ioctls to modify the interface's
        IFF_PROMISC flag. Promiscuous mode allows the interface to receive
        frames not addressed to its MAC address.
        
        Process:
        1. Read current interface flags via SIOCGIFFLAGS.
        2. Modify IFF_PROMISC bit according to enable parameter.
        3. Write modified flags back via SIOCSIFFLAGS.
        
        Args:
            enable: True to enable promiscuous mode, False to disable.
        
        Raises:
            OSError: If ioctl operations fail (usually requires root/CAP_NET_ADMIN).
        
        Note:
            Enabling promiscuous mode typically requires elevated privileges.
        """
        ifreq = struct.pack("256s", self.iface.encode())
        flags_buf = fcntl.ioctl(self._control_socket(), SIOCGIFFLAGS, ifreq)  # type: ignore[attr-defined]
        flags = struct.unpack_from("H", flags_buf, 16)[0]
        if enable:
            flags |= IFF_PROMISC
        else:
            flags &= ~IFF_PROMISC
        ifreq_flags = struct.pack("256sH", self.iface.encode(), flags) + b"\x00" * 14
        fcntl.ioctl(self._control_socket(), SIOCSIFFLAGS, ifreq_flags)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Socket creation
    # ------------------------------------------------------------------
    def _decide_socket_type(self) -> int:
        """Determine the appropriate socket type for this interface.
        
        Attempts to create sockets with different types based on the configured
        mode, testing each option to see which works with the underlying driver.
        This allows automatic adaptation to driver capabilities.
        
        Strategy by mode:
        - "raw": Only try SOCK_RAW (fail if not supported).
        - "cooked": Only try SOCK_DGRAM (fail if not supported).
        - "auto": Try SOCK_RAW first, fall back to SOCK_DGRAM.
        
        Returns:
            socket.SOCK_RAW or socket.SOCK_DGRAM, whichever works.
        
        Raises:
            RuntimeError: If all configured socket types fail to create.
        """
        requested = self.mode
        choices = []
        if requested == "raw":
            choices = [socket.SOCK_RAW]
        elif requested == "cooked":
            choices = [socket.SOCK_DGRAM]
        else:
            choices = [socket.SOCK_RAW, socket.SOCK_DGRAM]

        last_error: Optional[Exception] = None
        for candidate in choices:
            try:
                probe = self._open_socket(candidate, test_only=True)
            except OSError as exc:
                last_error = exc
            else:
                probe.close()
                return candidate
        raise RuntimeError(
            f"Unable to open AF_PACKET socket on {self.iface}: {last_error}" if last_error else "Failed to open AF_PACKET socket"
        )

    def _open_socket(self, sock_type: int, test_only: bool = False) -> socket.socket:
        """Create and bind an AF_PACKET socket of the specified type.
        
        Creates a socket with the given socket type (SOCK_RAW or SOCK_DGRAM),
        binds it to the interface, and optionally configures the receive buffer.
        
        Args:
            sock_type: socket.SOCK_RAW or socket.SOCK_DGRAM.
            test_only: If True, skip buffer configuration (used for testing
                socket type compatibility). If False, configure for production use.
        
        Returns:
            Bound AF_PACKET socket ready for frame I/O.
        
        Raises:
            OSError: If socket creation or bind fails.
        """
        protocol = ETH_P_ALL if not self.filter_ethertype else self.ethertype
        sock = socket.socket(AF_PACKET, sock_type, socket.htons(protocol))
        try:
            sock.bind((self.iface, 0))
        except OSError:
            sock.close()
            raise
        if test_only:
            return sock
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.bufsize)
        return sock

    # ------------------------------------------------------------------
    # Frame parsing helpers
    # ------------------------------------------------------------------
    def _parse_frame(self, frame: bytes) -> Optional[Tuple[bytes, bytes, int, bytes]]:
        """Parse received frame based on socket type.
        
        Handles two different frame formats:
        - SOCK_RAW: Raw Ethernet frame with 14-byte header (dst+src+type).
        - SOCK_DGRAM: Linux cooked packet with 16-byte SLL header.
        
        SOCK_RAW format (Ethernet II):
            Bytes 0-5:   Destination MAC
            Bytes 6-11:  Source MAC
            Bytes 12-13: EtherType (big-endian)
            Bytes 14+:   Payload
        
        SOCK_DGRAM format (Linux cooked):
            Bytes 0-1:   Packet type
            Bytes 2-3:   Hardware address type
            Bytes 4-5:   Hardware address length
            Bytes 6-13:  Source address (padded)
            Bytes 14-15: Protocol (EtherType)
            Bytes 16+:   Payload
        
        Args:
            frame: Raw bytes received from socket.
        
        Returns:
            Tuple of (dst_mac, src_mac, ethertype, payload) if frame is valid,
            None if frame is malformed or too short.
        
        Note:
            For SOCK_DGRAM, dst_mac is set to this interface's MAC since the
            kernel doesn't provide destination address in cooked packets.
        """
        if self.sock_type == socket.SOCK_RAW:
            if len(frame) < 14:
                return None
            dst = frame[0:6]
            src = frame[6:12]
            etype = struct.unpack("!H", frame[12:14])[0]
            payload = frame[14:]
            return dst, src, etype, payload

        if len(frame) < 16:
            return None
        header = frame[:16]
        _, hatype, halen = struct.unpack("!HHH", header[:6])
        addr = header[6:14]
        etype = struct.unpack("!H", header[14:16])[0]
        src = addr[:halen].ljust(6, b"\x00")
        dst = self.src_mac
        payload = frame[16:]
        return dst, src, etype, payload

    # ------------------------------------------------------------------
    # Utility converters
    # ------------------------------------------------------------------
    @staticmethod
    def mac_str_to_bytes(mac: str) -> bytes:
        """Convert MAC address string to bytes.
        
        Args:
            mac: MAC address string in format "aa:bb:cc:dd:ee:ff".
        
        Returns:
            6-byte MAC address.
        
        Raises:
            ValueError: If MAC string format is invalid.
        """
        return bytes(int(part, 16) for part in mac.split(":"))

    @staticmethod
    def mac_bytes_to_str(mac: bytes) -> str:
        """Convert MAC address bytes to string.
        
        Args:
            mac: MAC address as bytes (typically 6 bytes).
        
        Returns:
            MAC address string in format "aa:bb:cc:dd:ee:ff".
        """
        return ":".join(f"{b:02x}" for b in mac)
