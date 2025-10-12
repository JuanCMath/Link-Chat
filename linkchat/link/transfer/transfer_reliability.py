"""Reliability layer for file transfers with ACK/retry mechanisms.

Provides reliable transmission primitives for metadata and chunk frames
with automatic retransmission on timeout.
"""

import threading
from typing import Dict, Tuple, Union

from ..core.link_layer import LinkLayer, FrameType


class ReliableTransfer:
    """Handles ACK-based reliable transmission with retry logic."""
    
    def __init__(
        self,
        link_layer: LinkLayer,
        ack_timeout: float,
        max_retries: int
    ):
        """Initialize the reliability layer.
        
        Args:
            link_layer: Active LinkLayer instance for frame transmission.
            ack_timeout: Maximum time to wait for ACK before retry (seconds).
            max_retries: Maximum number of retransmission attempts.
        """
        self.link_layer = link_layer
        self.ack_timeout = ack_timeout
        self.max_retries = max_retries
        
        # ACK events keyed by (dst_mac, identifier, chunk_id or "meta")
        # identifier is filename for chunks, transfer_name for metadata
        self._ack_events: Dict[Tuple[bytes, str, Union[int, str]], threading.Event] = {}
        self._lock = threading.Lock()
    
    def send_metadata_reliable(
        self,
        dst_mac: bytes,
        transfer_name: str,
        meta_payload: bytes
    ) -> bool:
        """Send TRANSFER_META frame and wait for ACK confirmation.
        
        Implements reliable metadata transmission:
        1. Creates threading.Event keyed by (dst_mac, transfer_name, "meta").
        2. Sends TRANSFER_META frame with JSON payload.
        3. Waits for metadata ACK using configured ack_timeout.
        4. Retries up to max_retries if no ACK received.
        5. Returns True if ACK received, False if all retries exhausted.
        
        This ensures the receiver has successfully parsed and prepared for the
        incoming transfer before any chunk data is sent.
        
        Args:
            dst_mac: Destination MAC address (6 bytes).
            transfer_name: Name of the transfer (filename for files, folder name for folders).
            meta_payload: JSON-encoded metadata bytes.
        
        Returns:
            True if metadata was acknowledged, False after max retries.
        """
        ack_key = (dst_mac, transfer_name, "meta")
        
        for attempt in range(self.max_retries):
            with self._lock:
                self._ack_events[ack_key] = threading.Event()
            
            self.link_layer.send(dst_mac, FrameType.TRANSFER_META, meta_payload)
            
            ack_received = self._ack_events[ack_key].wait(timeout=self.ack_timeout)
            
            with self._lock:
                self._ack_events.pop(ack_key, None)
            
            if ack_received:
                return True
        
        return False
    
    def send_chunk_reliable(
        self,
        dst_mac: bytes,
        filename: str,
        chunk_id: int,
        chunk_data: bytes
    ) -> bool:
        """Send a single chunk with retransmission logic.

        Implements reliable transmission using ACKs and retries:
        1. Creates a threading.Event keyed by (dst_mac, filename, chunk_id).
        2. Sends FILE_CHUNK frame with payload: chunk_id(4 bytes) + filename + '|' + data.
        3. Waits for ACK using the configured ack_timeout.
        4. If ACK received, returns True.
        5. If timeout, retries up to the configured max_retries.
        6. Returns False if all retries exhausted.

        The ACK is received asynchronously in signal_ack() which sets the Event,
        unblocking the wait() call. The filename is included in the ACK key to ensure
        ACKs for different files (even with the same chunk_id) are properly isolated,
        preventing cross-file ACK interference when multiple files are in flight.

        Args:
            dst_mac: Destination MAC address (6 bytes).
            filename: Name of file being sent (for payload identification and ACK isolation).
            chunk_id: Chunk sequence number (0 to total_chunks-1).
            chunk_data: Chunk data bytes (up to configured chunk_size).

        Returns:
            True if chunk was acknowledged within timeout, False after max retries.
        """
        payload = chunk_id.to_bytes(4, 'big') + filename.encode('utf-8') + b'|' + chunk_data
        ack_key = (dst_mac, filename, chunk_id)

        for attempt in range(self.max_retries):
            with self._lock:
                self._ack_events[ack_key] = threading.Event()

            self.link_layer.send(dst_mac, FrameType.FILE_CHUNK, payload)

            ack_received = self._ack_events[ack_key].wait(timeout=self.ack_timeout)

            with self._lock:
                self._ack_events.pop(ack_key, None)

            if ack_received:
                return True

        return False
    
    def signal_ack(self, src_mac: bytes, identifier: str, chunk_id_or_meta: Union[int, str]) -> None:
        """Signal that an ACK has been received.
        
        Called by the frame handler when an ACK frame is received. Sets the
        corresponding threading.Event to unblock the waiting send thread.
        
        Args:
            src_mac: Source MAC address that sent the ACK.
            identifier: Filename for chunk ACKs, transfer_name for metadata ACKs.
            chunk_id_or_meta: Chunk ID (int) for chunk ACKs, "meta" for metadata ACKs.
        """
        ack_key = (src_mac, identifier, chunk_id_or_meta)
        
        with self._lock:
            if ack_key in self._ack_events:
                self._ack_events[ack_key].set()
