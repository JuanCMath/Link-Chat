"""Message protocol layer for reliable text messaging over LinkLayer.

Provides a higher-level messaging abstraction on top of the link layer that
handles message fragmentation, reassembly, acknowledgments, and retransmission.
Messages are automatically split into chunks, transmitted with sequence tracking,
and reassembled on the receiver side.

The protocol uses MESSAGE frames for data transmission and ACK frames for
confirmation. Each message is assigned a unique ID and can be fragmented across
multiple parts if it exceeds the configured payload size.
"""
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

from .link_layer import FrameType, LinkFrame, LinkLayer

# Message header format: message_id(2) + total_parts(2) + part_index(2) = 6 bytes
_MESSAGE_HEADER_BYTES = 6
# Default maximum payload size for messages before fragmentation
_MESSAGE_DEFAULT_PAYLOAD = 1024
# ACK frame prefix byte to distinguish message ACKs from file transfer ACKs
_MESSAGE_ACK_PREFIX = 0x4D  # 'M'
# Time in seconds to wait for ACK before considering transmission failed
_MESSAGE_ACK_TIMEOUT = 2.0
# Maximum number of transmission attempts before giving up
_MESSAGE_MAX_RETRIES = 5
# Delay between sending message parts to avoid overwhelming the medium
_MESSAGE_INTER_PART_DELAY = 0.005
# Size of the acknowlegment message: Prefix (1 byte) + message_id (2 bytes)
_MESSAGE_ACK_SIZE = 3


@dataclass
class _InboundMessage:
    """State tracking for an incoming multi-part message.
    
    Attributes:
        total_parts: Expected number of parts in the complete message.
        parts: Dictionary mapping part_index to received data bytes.
        created_at: Timestamp when this message state was first created,
            used for expiring stale incomplete messages.
    """
    total_parts: int
    parts: Dict[int, bytes] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class MessageProtocol:
    """High-level messaging protocol with fragmentation and reliability.
    
    Provides reliable text message transmission over the link layer by handling:
    - Automatic message fragmentation for large messages
    - Message reassembly from received parts
    - ACK-based confirmation with retransmission
    - Duplicate detection and handling
    - Stale message cleanup
    
    Messages are identified by unique message IDs and can be split into multiple
    parts. The protocol ensures delivery through ACK/retry mechanisms similar to
    stop-and-wait ARQ.
    """
    
    def __init__(
        self,
        link_layer: LinkLayer,
        on_message: Optional[Callable[[bytes, str], None]] = None,
        max_payload: int = _MESSAGE_DEFAULT_PAYLOAD,
        ack_timeout: float = _MESSAGE_ACK_TIMEOUT,
        max_retries: int = _MESSAGE_MAX_RETRIES,
        inter_part_delay: float = _MESSAGE_INTER_PART_DELAY,
    ) -> None:
        """Initialize the message protocol layer.
        
        Sets up the messaging system with configurable fragmentation, timeout,
        and retry parameters. The protocol is ready to send and receive messages
        immediately after initialization.
        
        Args:
            link_layer: Active LinkLayer instance for frame transmission.
            on_message: Optional callback(src_mac, text) invoked when a complete
                message is received and decoded.
            max_payload: Maximum payload size before fragmentation (minimum 7 bytes).
            ack_timeout: Seconds to wait for ACK before retry.
            max_retries: Maximum transmission attempts before giving up.
            inter_part_delay: Delay in seconds between sending message parts.
        """
        self.link_layer = link_layer
        self.on_message = on_message
        self.ack_timeout = ack_timeout
        self.max_retries = max_retries
        self.inter_part_delay = inter_part_delay

        self._lock = threading.Lock()
        self._message_id = 0
        self._pending_acks: Dict[Tuple[bytes, int], threading.Event] = {}
        self._inbound: Dict[Tuple[bytes, int], _InboundMessage] = {}
        self._delivered: Dict[Tuple[bytes, int], float] = {}

        max_payload = max(_MESSAGE_HEADER_BYTES + 1, max_payload)
        self._part_payload = max_payload - _MESSAGE_HEADER_BYTES

    def send_message(self, dst_mac: bytes, text: str) -> bool:
        """Send a text message to the specified destination.
        
        Encodes the text as UTF-8, fragments it into parts if necessary, and
        transmits all parts using MESSAGE frames. Waits for acknowledgment with
        retry logic. The message is sent as a single atomic unit - all parts
        are transmitted before waiting for the ACK.
        
        Process:
        1. Encode text to UTF-8 bytes.
        2. Split into parts based on max_payload size.
        3. Generate unique message_id.
        4. For each retry attempt:
           a. Send all message parts with delay between them.
           b. Wait for ACK with timeout.
           c. Return True if ACK received, retry if timeout.
        5. Return False if all retries exhausted.
        
        Args:
            dst_mac: Destination MAC address (6 bytes).
            text: Message text to send (will be UTF-8 encoded).
        
        Returns:
            True if message was acknowledged, False after max retries.
        """
        data = text.encode("utf-8")
        if not data:
            parts = [b""]
        else:
            parts = [data[i : i + self._part_payload] for i in range(0, len(data), self._part_payload)]
        total_parts = len(parts)

        with self._lock:
            message_id = self._message_id = (self._message_id + 1) & 0xFFFF

        ack_key = (dst_mac, message_id)
        header_prefix = message_id.to_bytes(2, "big") + total_parts.to_bytes(2, "big")

        for attempt in range(self.max_retries):
            event = threading.Event()
            with self._lock:
                self._pending_acks[ack_key] = event

            for index, chunk in enumerate(parts):
                header = header_prefix + index.to_bytes(2, "big")
                payload = header + chunk
                self.link_layer.send(dst_mac, FrameType.MESSAGE, payload)
                if self.inter_part_delay:
                    time.sleep(self.inter_part_delay)

            if event.wait(self.ack_timeout):
                with self._lock:
                    self._pending_acks.pop(ack_key, None)
                return True

            with self._lock:
                self._pending_acks.pop(ack_key, None)

        return False

    def handle_frame(self, frame: LinkFrame) -> None:
        """Process incoming frames related to messaging.
        
        Routes frames to appropriate handlers based on frame type:
        - MESSAGE: Assembles multi-part messages and triggers callback.
        - ACK: Signals waiting send thread that message was received.
        
        This method should be called from the link layer's on_frame callback
        or from a dispatcher that routes different frame types.
        
        Args:
            frame: Received LinkFrame to process.
        """
        if frame.typ == FrameType.MESSAGE:
            self._handle_message_frame(frame)
        elif frame.typ == FrameType.ACK:
            self._handle_ack_frame(frame)

    def _handle_message_frame(self, frame: LinkFrame) -> None:
        """Handle incoming MESSAGE frame and manage reassembly.
        
        Processes a received message part:
        1. Extracts message_id, total_parts, part_index from header.
        2. Validates part_index is within expected range.
        3. Checks if message was already delivered (sends ACK again).
        4. Creates or updates message reassembly state.
        5. Stores the part data (handles duplicates gracefully).
        6. If all parts received:
           a. Reassembles parts in order.
           b. Decodes UTF-8 text.
           c. Invokes on_message callback.
           d. Marks message as delivered.
        7. Sends ACK to sender.
        
        Args:
            frame: Received MESSAGE frame with payload containing header + data.
        """
        payload = frame.payload
        if len(payload) < _MESSAGE_HEADER_BYTES:
            return

        message_id = int.from_bytes(payload[0:2], "big")
        total_parts = int.from_bytes(payload[2:4], "big")
        part_index = int.from_bytes(payload[4:6], "big")
        part_data = payload[6:]

        if total_parts <= 0 or part_index >= total_parts:
            return

        key = (frame.src, message_id)

        with self._lock:
            if key in self._delivered:
                self._send_ack(frame.src, message_id)
                return

            state = self._inbound.get(key)
            if state is None:
                state = _InboundMessage(total_parts=total_parts)
                self._inbound[key] = state
            elif state.total_parts != total_parts:
                # Reset inconsistent state
                state.total_parts = total_parts
                state.parts.clear()

            if part_index not in state.parts:
                state.parts[part_index] = part_data
            elif state.parts[part_index] != part_data:
                state.parts[part_index] = part_data
            
            # Checks if the message is complete
            if len(state.parts) != state.total_parts:
                return

            ordered_parts = [state.parts[i] for i in range(state.total_parts)]
            message_bytes = b"".join(ordered_parts)
            try:
                text = message_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = message_bytes.decode("utf-8", errors="replace")

            self._delivered[key] = time.time()
            self._inbound.pop(key, None)

        if self.on_message:
            self.on_message(frame.src, text)

        self._send_ack(frame.src, message_id)

    def _handle_ack_frame(self, frame: LinkFrame) -> None:
        """Handle incoming ACK frame to unblock waiting sender.
        
        Extracts the message_id from the ACK payload (which must start with
        the MESSAGE_ACK_PREFIX byte) and sets the corresponding threading.Event
        to unblock the waiting send_message() call.
        
        Args:
            frame: Received ACK frame with message acknowledgment.
        """
        payload = frame.payload
        if len(payload) < _MESSAGE_ACK_SIZE or payload[0] != _MESSAGE_ACK_PREFIX:
            return

        message_id = int.from_bytes(payload[1:_MESSAGE_ACK_SIZE], "big")
        key = (frame.src, message_id)

        with self._lock:
            event = self._pending_acks.pop(key, None)

        if event:
            event.set()

    def _send_ack(self, dst_mac: bytes, message_id: int) -> None:
        """Send an acknowledgment for a received message.
        
        Constructs an ACK frame with the MESSAGE_ACK_PREFIX byte followed by
        the 2-byte message_id and transmits it to the sender.
        
        Args:
            dst_mac: Destination MAC address (original sender).
            message_id: Message ID to acknowledge (0-65535).
        """
        ack_payload = bytes([_MESSAGE_ACK_PREFIX]) + message_id.to_bytes(2, "big")
        self.link_layer.send(dst_mac, FrameType.ACK, ack_payload)

    def expire_inbound(self, older_than: float = 30.0) -> None:
        """Remove stale incomplete messages and delivered message records.
        
        Cleans up internal state by removing:
        1. Incomplete messages that were started but never finished (partial
           parts received but full message never arrived).
        2. Delivered message records that prevent re-delivery of duplicates.
        
        This method should be called periodically (e.g., every 30-60 seconds)
        to prevent unbounded memory growth from incomplete or duplicate messages.
        
        Args:
            older_than: Age threshold in seconds. Messages/records older than
                this will be removed.
        """
        cutoff = time.time() - older_than
        with self._lock:
            stale_keys = [key for key, state in self._inbound.items() if state.created_at < cutoff]
            for key in stale_keys:
                self._inbound.pop(key, None)

            delivered_keys = [key for key, timestamp in self._delivered.items() if timestamp < cutoff]
            for key in delivered_keys:
                self._delivered.pop(key, None)
