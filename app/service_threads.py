"""
service_threads.py
~~~~~~~~~~~~~~~~~~

Multithreaded Ethernet frame management for concurrent RX/TX/Dispatch operations.

This module orchestrates background threads for receiving, transmitting, and
dispatching Ethernet frames, providing a high-level interface for payload-based
communication over raw sockets.

Architecture:
    - RX Thread: Continuously receives frames from socket and queues them
    - TX Thread: Dequeues outgoing frames and sends them via socket
    - Dispatch Thread: Processes incoming frames and invokes application callback

Key Components:
    - ThreadManager: Coordinates all threading operations
    - Helper functions: MAC address conversion and Ethernet frame packing/unpacking

Threading Model:
    All threads are daemon threads that gracefully shutdown on stop() call.
    Communication between threads uses thread-safe queues.
"""
import logging
import queue
import threading
import time
from typing import Callable, Optional, Tuple

from .raw_socket import SocketManager

# Broadcast MAC address (FF:FF:FF:FF:FF:FF)
BROADCAST_MAC_BYTES = b"\xff\xff\xff\xff\xff\xff"


def mac_str_to_bytes(mac_address: str) -> bytes:
    """
    Convert MAC address from colon-separated string to bytes.

    Args:
        mac_address: MAC in format "AA:BB:CC:DD:EE:FF" (case-insensitive).

    Returns:
        bytes: 6-byte MAC address.

    Example:
        >>> mac_str_to_bytes("08:00:27:4a:5b:6c")
        b'\\x08\\x00\\'*\\x4a\\x5b\\x6c'
    """
    return bytes(int(part, 16) for part in mac_address.split(":"))


def mac_bytes_to_str(mac_bytes: bytes) -> str:
    """
    Convert MAC address from bytes to colon-separated lowercase string.

    Args:
        mac_bytes: 6-byte MAC address.

    Returns:
        str: MAC in format "aa:bb:cc:dd:ee:ff".

    Example:
        >>> mac_bytes_to_str(b'\\x08\\x00\\'*\\x4a\\x5b\\x6c')
        '08:00:27:4a:5b:6c'
    """
    return ":".join(f"{byte:02x}" for byte in mac_bytes)


def pack_ethernet_frame(
    dst_mac: bytes, src_mac: bytes, ethertype: int, payload: bytes
) -> bytes:
    """
    Construct a complete Ethernet frame from components.

    Builds the standard Ethernet II frame format:
    [DST_MAC(6)] [SRC_MAC(6)] [ETHERTYPE(2)] [PAYLOAD(variable)]

    Args:
        dst_mac: Destination MAC address (6 bytes).
        src_mac: Source MAC address (6 bytes).
        ethertype: EtherType field (0x0800-0xFFFF).
        payload: Frame payload data.

    Returns:
        bytes: Complete Ethernet frame ready for transmission.

    Example:
        >>> frame = pack_ethernet_frame(
        ...     b'\\xff\\xff\\xff\\xff\\xff\\xff',  # broadcast
        ...     b'\\x08\\x00\\'*\\x4a\\x5b\\x6c',
        ...     0x88B5,
        ...     b'Hello'
        ... )
    """
    return dst_mac + src_mac + ethertype.to_bytes(2, "big") + payload


def unpack_ethernet_frame(frame: bytes) -> Optional[Tuple[bytes, bytes, int, bytes]]:
    """
    Parse an Ethernet frame into its constituent parts.

    Extracts fields from Ethernet II format:
    [DST_MAC(6)] [SRC_MAC(6)] [ETHERTYPE(2)] [PAYLOAD(variable)]

    Args:
        frame: Complete Ethernet frame bytes.

    Returns:
        Optional[Tuple[bytes, bytes, int, bytes]]: Tuple of (dst_mac, src_mac,
            ethertype, payload), or None if frame is too short.

    Example:
        >>> dst, src, etype, payload = unpack_ethernet_frame(frame)
        >>> mac_bytes_to_str(src)
        '08:00:27:4a:5b:6c'
    """
    if len(frame) < 14:  # Minimum Ethernet frame header size
        return None

    dst_mac = frame[0:6]
    src_mac = frame[6:12]
    ethertype = int.from_bytes(frame[12:14], "big")
    payload = frame[14:]

    return dst_mac, src_mac, ethertype, payload

class ThreadManager:
    """
    Manages concurrent Ethernet frame reception, transmission, and dispatching.

    This class coordinates three background daemon threads:
    1. RX Thread: Continuously receives frames from the raw socket
    2. TX Thread: Sends queued frames to the network
    3. Dispatch Thread: Processes received frames and invokes callbacks

    The manager provides high-level methods for sending unicast and broadcast
    payloads while handling Ethernet frame construction automatically.

    Attributes:
        sock: SocketManager instance for raw network I/O.
        on_frame: Callback invoked for each received frame with signature:
                  (dst_mac: bytes, src_mac: bytes, payload: bytes) -> None
        drop_own_frames: If True, silently drops frames sent by this host.

    Thread Safety:
        All public methods are thread-safe. Internal queues handle synchronization.

    Example:
        >>> socket_mgr = SocketManager(iface="eth0")
        >>> def handle_frame(dst, src, payload):
        ...     print(f"From {mac_bytes_to_str(src)}: {payload}")
        >>> mgr = ThreadManager(socket_mgr, on_frame=handle_frame)
        >>> mgr.start()
        >>> mgr.send_broadcast_payload(b"Hello network!")
        >>> mgr.stop()
    """

    def __init__(
        self,
        sock: SocketManager,
        on_frame: Optional[Callable[[bytes, bytes, bytes], None]] = None,
        drop_own_frames: bool = True,
    ) -> None:
        """
        Initialize the thread manager with socket and frame handler.

        Args:
            sock: Configured SocketManager instance (will be opened on start).
            on_frame: Optional callback for processing received frames.
            drop_own_frames: Whether to filter out frames sent by this host.
        """
        self.sock = sock
        self.on_frame = on_frame
        self.drop_own_frames = drop_own_frames

        # Thread-safe queues for inter-thread communication
        self._incoming_queue: "queue.Queue[bytes]" = queue.Queue()
        self._outgoing_queue: "queue.Queue[bytes]" = queue.Queue()

        # Shutdown coordination
        self._stop_event = threading.Event()

        # Worker threads (created as daemons for clean shutdown)
        self._rx_thread = threading.Thread(
            target=self._rx_loop, name="rx", daemon=True
        )
        self._tx_thread = threading.Thread(
            target=self._tx_loop, name="tx", daemon=True
        )
        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop, name="dispatch", daemon=True
        )

        # Cached local MAC address (set during start())
        self._local_mac_bytes: Optional[bytes] = None

    def start(self) -> None:
        """
        Open socket and start all background threads.

        This method:
        1. Opens the raw socket for network I/O
        2. Retrieves and caches the local MAC address
        3. Starts RX, TX, and Dispatch threads

        Raises:
            PermissionError: If socket cannot be opened (CAP_NET_RAW required).
            OSError: If network interface doesn't exist.

        Note:
            Safe to call multiple times; subsequent calls are no-ops.
        """
        self.sock.open()
        self._local_mac_bytes = mac_str_to_bytes(self.sock.get_mac_address())
        self._stop_event.clear()

        self._rx_thread.start()
        self._tx_thread.start()
        self._dispatch_thread.start()

        logging.info("[ThreadManager] RX/TX/Dispatch threads started")

    def stop(self) -> None:
        """
        Signal shutdown and wait for all threads to terminate gracefully.

        This method:
        1. Sets the stop event to signal all threads
        2. Injects empty frame to unblock TX thread
        3. Waits up to 1 second for each thread to finish
        4. Logs completion

        Note:
            Safe to call multiple times or when already stopped.
        """
        self._stop_event.set()

        # Unblock TX thread if waiting on empty queue
        try:
            self._outgoing_queue.put_nowait(b"")
        except Exception:
            pass

        # Wait for threads to finish
        for thread in (self._rx_thread, self._tx_thread, self._dispatch_thread):
            thread.join(timeout=1.0)

        logging.info("[ThreadManager] All threads stopped")

    # Sending Methods -------------------------------------------------------

    def send_frame_bytes(self, frame: bytes) -> None:
        """
        Queue a complete Ethernet frame for transmission.

        Use this method when you have a pre-constructed frame. For most use
        cases, prefer send_unicast_payload() or send_broadcast_payload().

        Args:
            frame: Complete Ethernet frame including all headers.

        Note:
            Frame is queued asynchronously; actual transmission happens in TX thread.
        """
        self._outgoing_queue.put(frame)

    def send_unicast_payload(
        self, dst_mac: bytes, payload: bytes, ethertype: Optional[int] = None
    ) -> None:
        """
        Send payload to a specific MAC address.

        Automatically constructs the Ethernet frame with local MAC as source.

        Args:
            dst_mac: Destination MAC address (6 bytes).
            payload: Data to transmit.
            ethertype: Optional EtherType override (uses socket default if None).

        Raises:
            RuntimeError: If called before start().

        Example:
            >>> dst = mac_str_to_bytes("aa:bb:cc:dd:ee:ff")
            >>> mgr.send_unicast_payload(dst, b"Hello peer!")
        """
        if self._local_mac_bytes is None:
            raise RuntimeError("ThreadManager not started; call start() first")

        if ethertype is None:
            ethertype = self.sock.ethertype

        frame = pack_ethernet_frame(dst_mac, self._local_mac_bytes, ethertype, payload)
        self._outgoing_queue.put(frame)

    def send_broadcast_payload(
        self, payload: bytes, ethertype: Optional[int] = None
    ) -> None:
        """
        Broadcast payload to all hosts on the local network segment.

        Constructs Ethernet frame with destination FF:FF:FF:FF:FF:FF.

        Args:
            payload: Data to broadcast.
            ethertype: Optional EtherType override (uses socket default if None).

        Raises:
            RuntimeError: If called before start().

        Example:
            >>> mgr.send_broadcast_payload(b"BEACON|MyHost")
        """
        if self._local_mac_bytes is None:
            raise RuntimeError("ThreadManager not started; call start() first")

        if ethertype is None:
            ethertype = self.sock.ethertype

        frame = pack_ethernet_frame(
            BROADCAST_MAC_BYTES, self._local_mac_bytes, ethertype, payload
        )
        self._outgoing_queue.put(frame)

    # Background Thread Loops -----------------------------------------------

    def _rx_loop(self) -> None:
        """
        Background thread: continuously receive frames from socket.

        Runs until stop_event is set. Frames are queued for the dispatch thread.
        Errors are logged but don't stop the loop (resilient to transient issues).
        """
        logging.info("[RX] Thread started")

        while not self._stop_event.is_set():
            try:
                frame = self.sock.receive_raw_frame()
                if frame:
                    self._incoming_queue.put(frame)
            except Exception as error:
                logging.error(f"[RX] Error receiving frame: {error}")
                # Brief pause to prevent tight error loop
                time.sleep(0.2)

    def _tx_loop(self) -> None:
        """
        Background thread: continuously transmit queued frames.

        Runs until stop_event is set. Dequeues frames with timeout to allow
        periodic stop checks. Errors are logged but don't stop the loop.
        """
        logging.info("[TX] Thread started")

        while not self._stop_event.is_set():
            try:
                # Timeout allows checking stop_event periodically
                frame = self._outgoing_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            # Double-check stop event (might have been set while waiting)
            if self._stop_event.is_set():
                break

            try:
                if frame:  # Ignore empty frames (used for shutdown signaling)
                    self.sock.send_raw_frame(frame)
            except Exception as error:
                logging.error(f"[TX] Error sending frame: {error}")

    def _dispatch_loop(self) -> None:
        """
        Background thread: process received frames and invoke callbacks.

        Runs until stop_event is set. Unpacks frames, filters by EtherType,
        optionally drops own frames, and invokes the on_frame callback.

        Errors in callback are caught and logged to prevent thread termination.
        """
        logging.info("[Dispatch] Thread started")

        configured_ethertype = self.sock.ethertype

        while not self._stop_event.is_set():
            try:
                # Timeout allows checking stop_event periodically
                frame = self._incoming_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            # Parse Ethernet frame
            parsed = unpack_ethernet_frame(frame)
            if not parsed:
                continue  # Malformed frame (too short)

            dst_mac, src_mac, ethertype, payload = parsed

            # Filter by configured EtherType
            if ethertype != configured_ethertype:
                continue

            # Optionally filter out frames from this host (loop prevention)
            if (
                self.drop_own_frames
                and self._local_mac_bytes
                and src_mac == self._local_mac_bytes
            ):
                continue

            # Invoke application callback
            if self.on_frame:
                try:
                    self.on_frame(dst_mac, src_mac, payload)
                except Exception as error:
                    logging.error(f"[Dispatch] Callback error: {error}")
