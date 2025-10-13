"""Link layer integration module.

This module provides a unified API that combines AF_PACKET raw socket communication,
CSMA/CD medium access control, and frame encoding/decoding. It exposes a high-level
interface for sending and receiving link-layer frames with automatic sequence numbering,
collision avoidance, and background reception.
"""

import enum
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from .medium.af_packet_medium import AFPacketMedium
from .csma_persistent import CSMAPersistent
from .framing import frame_decode, frame_encode


class FrameType(enum.IntEnum):
    """Frame type codes for link-layer protocol messages.
    
    Defines the type field values used in frame headers to distinguish between
    different kinds of protocol messages.
    
    Attributes:
        MESSAGE: Text message frame (0x01).
        TRANSFER_META: Transfer metadata frame for files and folders (0x02).
        FILE_CHUNK: File data chunk frame (0x03).
        ACK: Acknowledgment frame (0x04).
    """
    MESSAGE = 0x01
    TRANSFER_META = 0x02
    FILE_CHUNK = 0x03
    ACK = 0x04


@dataclass(slots=True)
class LinkFrame:
    """Decoded link-layer frame.
    
    Represents a received or to-be-sent frame after framing logic has been applied.
    Contains all header fields and the payload data.
    
    Attributes:
        dst: Destination MAC address (6 bytes).
        src: Source MAC address (6 bytes).
        typ: Frame type indicator (2 bytes).
        seq: Sequence number (0-65535).
        payload: Frame payload data (variable length bytes).
    """
    dst: bytes
    src: bytes
    typ: FrameType
    seq: int
    payload: bytes


class LinkLayer:
    """High-level link-layer communication interface.
    
    Integrates AF_PACKET raw sockets, CSMA/CD medium access control, and frame
    encoding/decoding into a unified API. Manages automatic sequence numbering,
    collision avoidance, and background frame reception.
    """
    
    def __init__(
        self,
        iface: str,
        ethertype: int,
        on_frame: Callable[[LinkFrame], None],
        sense_timeout: float = 0.01,
        filter_ethertype: bool = True,
    ) -> None:
        """Initialize the link layer on a network interface.
        
        Sets up the AF_PACKET medium, CSMA controller, and receive thread infrastructure.
        The layer is ready to send frames immediately, but requires calling start_listening()
        to begin receiving.
        
        Args:
            iface: Network interface name (e.g., 'eth0', 'enp3s0').
            ethertype: Custom Ethertype value for filtering frames (e.g., 0x88B5).
            on_frame: Callback invoked for each valid received frame.
            sense_timeout: CSMA carrier sense duration in seconds (default: 0.01).
            filter_ethertype: If True, only receive frames with matching ethertype.
        """
        self.medium = AFPacketMedium(
            iface=iface,
            ethertype=ethertype,
            filter_ethertype=filter_ethertype,
        )
        self.on_frame = on_frame

        self._seq = 0
        self._lock = threading.Lock()
        self._tx_dst: Optional[bytes] = None
        self._stop_rx = threading.Event()
        self._rx_thread: Optional[threading.Thread] = None

        self.csma = CSMAPersistent(
            sense_func=CSMAPersistent.make_sense_with_recv_once(self.medium.recv_once),
            send_func=self._csma_send,
            difs=sense_timeout,
        ) #cual es la funcion de cada una de las propiedades definidas en la clase?

    @property
    def mac(self) -> bytes:
        """Get the local MAC address of the network interface.
        
        Returns:
            6-byte MAC address of this link layer instance.
        """
        return self.medium.src_mac

    def next_seq(self) -> int:
        """Generate the next sequence number for outgoing frames.
        
        Thread-safe increment with wraparound at 65535. Used internally by send()
        when no explicit sequence number is provided.
        
        Returns:
            Next sequence number (0-65535).
        """
        with self._lock:
            self._seq = (self._seq + 1) & 0xFFFF
            return self._seq

    def send(self, dst: bytes, typ: FrameType, payload: bytes, seq: Optional[int] = None) -> None:
        """Send a frame to the specified destination MAC address.
        
        Encodes the frame with header, checksum, and bit stuffing, then transmits
        using CSMA/CD to avoid collisions. Blocks until the medium is free and the
        frame is sent.
        
        Args:
            dst: Destination MAC address (6 bytes).
            typ: Frame type code.
            payload: Frame payload data.
            seq: Explicit sequence number, or None to auto-generate.
        """
        if seq is None:
            seq = self.next_seq()
        frame = frame_encode(dst, self.mac, typ, seq, payload)

        with self._lock:
            self._tx_dst = dst
            try:
                self.csma.send(frame)
            finally:
                self._tx_dst = None

    def _csma_send(self, data: bytes) -> None:
        """Internal callback for CSMA controller to transmit frame data.
        
        Invoked by the CSMA controller after determining the medium is free.
        Uses the destination MAC stored by send() to dispatch the frame.
        
        Args:
            data: Encoded frame bytes to transmit.
        
        Raises:
            RuntimeError: If destination MAC was not set before CSMA invocation.
        """
        dst = self._tx_dst
        if dst is None:
            raise RuntimeError("CSMA send invoked without destination MAC")
        self.medium.send(dst_mac=dst, payload=data)

    def start_listening(self) -> None:
        """Start the background receive loop.
        
        Spawns a daemon thread that continuously polls for incoming frames and
        invokes the on_frame callback for each valid decoded frame. Safe to call
        multiple times; does nothing if already listening.
        """
        if self._rx_thread and self._rx_thread.is_alive():
            return
        self._stop_rx.clear()
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()

    def stop(self) -> None:
        """Stop the link layer and release resources.
        
        Signals the receive thread to terminate, waits up to 1 second for it to exit,
        and closes the underlying raw socket. Should be called before destroying the
        LinkLayer instance to ensure clean shutdown.
        """
        self._stop_rx.set()
        if self._rx_thread:
            self._rx_thread.join(timeout=1.0)
            self._rx_thread = None
        close_fn = getattr(self.medium, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:
                pass

    def _rx_loop(self) -> None:
        """Background thread loop for receiving and processing frames.
        
        Continuously polls the medium for incoming packets, filters out self-originated
        frames, decodes valid frames, and invokes the on_frame callback. Silently discards
        malformed frames or unsupported frame types. Runs until stop() sets the termination
        event.
        """
        while not self._stop_rx.is_set():
            packet = self.medium.recv_once(timeout=0.2)
            if packet is None:
                continue
            dst, src, etype, payload = packet
            if src == self.mac:
                continue
            try:
                decoded = frame_decode(payload)
            except ValueError:
                continue
            try:
                frame_type = FrameType(decoded[2])
            except ValueError:
                continue
            link_frame = LinkFrame(
                dst=decoded[0],
                src=decoded[1],
                typ=frame_type,
                seq=decoded[3],
                payload=decoded[4],
            )
            self.on_frame(link_frame)