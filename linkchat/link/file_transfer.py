"""File transfer module for sending and receiving files of any size.

Implements chunking, reassembly, ACK/retransmission, and progress tracking
for reliable file transfers over the link layer.
"""

import os
import time
import hashlib
import threading
from pathlib import Path
from typing import Dict, Optional, Callable, Tuple
from dataclasses import dataclass, field

from .link_layer import LinkLayer, LinkFrame, FrameType
from .adaptive_params import FileParams, file_params_from_medium


_FILE_DEFAULTS = FileParams(
    chunk_size=1400,
    ack_timeout=2.0,
    max_retries=5,
    inter_chunk_delay=0.0,
)


@dataclass
class FileTransferState:
    """State tracking for an ongoing file transfer.
    
    Attributes:
        filename: Name of the file being transferred.
        total_size: Total file size in bytes.
        total_chunks: Number of chunks the file is divided into.
        chunks: Dictionary mapping chunk_id (int) to chunk_data (bytes).
        received_size: Total bytes received so far, used for progress tracking.
        start_time: Timestamp when the transfer started.
        file_hash: SHA256 hash for integrity verification (None until computed).
    """
    filename: str
    total_size: int
    total_chunks: int
    chunks: Dict[int, bytes] = field(default_factory=dict)
    received_size: int = 0
    start_time: float = field(default_factory=time.time)
    file_hash: Optional[str] = None


class FileTransfer:
    """Handles file transmission and reception with chunking and reliability.
    
    Provides methods to send files of any size by fragmenting them into chunks,
    tracking acknowledgments, handling retransmissions, and reassembling received
    chunks into complete files.
    """
    
    def __init__(
        self,
        link_layer: LinkLayer,
        download_dir: str = "./downloads",
        on_progress: Optional[Callable[[str, int, int], None]] = None,
        on_complete: Optional[Callable[[str, bool], None]] = None,
        chunk_size: Optional[int] = None,
        ack_timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        inter_chunk_delay: Optional[float] = None,
    ):
        """Initialize the file transfer manager.
        
        Sets up the file transfer system with chunking, ACK tracking, and progress
        callbacks. Creates the download directory if it doesn't exist and initializes
        internal state dictionaries for tracking active transfers.
        
        Args:
            link_layer: Active LinkLayer instance for frame transmission.
            download_dir: Directory to save received files (created if needed).
            on_progress: Optional callback(filename, bytes_done, total_bytes) invoked
                after each chunk is sent or received to report progress.
            on_complete: Optional callback(filename, success) invoked when a file
                transfer completes, with success=True if hash matches.
            chunk_size: Optional override for chunk size in bytes. If None, an
                adaptive value is derived from the link layer's medium.
            ack_timeout: Optional override for ACK wait timeout. If None, an
                adaptive value is derived from the medium.
            max_retries: Optional override for number of retransmission attempts.
                If None, an adaptive value is used.
            inter_chunk_delay: Optional delay between sending chunks to reduce
                congestion. If None, an adaptive value is used.
        """
        try:
            medium = link_layer.medium  # type: ignore[attr-defined]
        except AttributeError:
            medium = None

        adaptive_params: FileParams = _FILE_DEFAULTS
        if medium is not None:
            adaptive_params = file_params_from_medium(medium)

        self.chunk_size = chunk_size if chunk_size is not None else adaptive_params.chunk_size
        self.ack_timeout = ack_timeout if ack_timeout is not None else adaptive_params.ack_timeout
        self.max_retries = max_retries if max_retries is not None else adaptive_params.max_retries
        self.inter_chunk_delay = (
            inter_chunk_delay if inter_chunk_delay is not None else adaptive_params.inter_chunk_delay
        )

        self.link_layer = link_layer
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.on_progress = on_progress
        self.on_complete = on_complete
        
        self.active_sends: Dict[Tuple[bytes, str], FileTransferState] = {}
        self.active_receives: Dict[Tuple[bytes, str], FileTransferState] = {}
        
        self._ack_events: Dict[Tuple[bytes, str, int], threading.Event] = {}
        self._lock = threading.Lock()
    
    def send_file(self, dst_mac: bytes, filepath: str) -> bool:
        """Send a file to the specified destination.
        
        Process:
        1. Computes file metadata (size, total chunks, SHA256 hash).
        2. Sends FILE_META frame with metadata to initialize receiver.
        3. Reads file in adaptive chunk_size increments.
        4. For each chunk, calls _send_chunk_reliable() which:
           - Sends FILE_CHUNK frame
           - Waits for ACK using the configured ack_timeout
           - Retries up to configured max_retries times
        5. Updates progress after each successful chunk.
        6. Applies optional inter_chunk_delay to avoid congestion.
        7. Cleans up transfer state in finally block.
        
        Args:
            dst_mac: Destination MAC address (6 bytes).
            filepath: Path to the file to send.
        
        Returns:
            True if all chunks were acknowledged successfully, False if any chunk
            failed after maximum retries.
            
        Raises:
            FileNotFoundError: If the specified file does not exist.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        file_size = os.path.getsize(filepath)
        filename = os.path.basename(filepath)
        total_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        
        file_hash = self._compute_file_hash(filepath)
        
        transfer_key = (dst_mac, filename)
        self.active_sends[transfer_key] = FileTransferState(
            filename=filename,
            total_size=file_size,
            total_chunks=total_chunks,
            file_hash=file_hash
        )
        
        try:
            meta_payload = f"{filename}|{file_size}|{total_chunks}|{file_hash}".encode('utf-8')
            self.link_layer.send(dst_mac, FrameType.FILE_META, meta_payload)
            time.sleep(0.1)
            
            with open(filepath, 'rb') as f:
                for chunk_id in range(total_chunks):
                    chunk_data = f.read(self.chunk_size)
                    success = self._send_chunk_reliable(dst_mac, filename, chunk_id, chunk_data)
                    
                    if not success:
                        if self.on_complete:
                            self.on_complete(filename, False)
                        return False
                    
                    bytes_sent = min((chunk_id + 1) * self.chunk_size, file_size)
                    if self.on_progress:
                        self.on_progress(filename, bytes_sent, file_size)

                    if self.inter_chunk_delay:
                        time.sleep(self.inter_chunk_delay)
            
            if self.on_complete:
                self.on_complete(filename, True)
            return True
            
        finally:
            with self._lock:
                self.active_sends.pop(transfer_key, None)
    
    def _send_chunk_reliable(self, dst_mac: bytes, filename: str, chunk_id: int, data: bytes) -> bool:
        """Send a single chunk with retransmission logic.

    Implements reliable transmission using ACKs and retries:
    1. Creates a threading.Event keyed by (dst_mac, filename, chunk_id).
    2. Sends FILE_CHUNK frame with payload: chunk_id(4 bytes) + filename + '|' + data.
    3. Waits for ACK using the configured ack_timeout.
    4. If ACK received, returns True.
    5. If timeout, retries up to the configured max_retries.
    6. Returns False if all retries exhausted.

        The ACK is received asynchronously in _handle_ack() which sets the Event,
        unblocking the wait() call.

        Args:
            dst_mac: Destination MAC address (6 bytes).
            filename: Name of file being sent (for payload identification).
            chunk_id: Chunk sequence number (0 to total_chunks-1).
            data: Chunk data bytes (up to configured chunk_size).

        Returns:
            True if chunk was acknowledged within timeout, False after max retries.
        """
        payload = chunk_id.to_bytes(4, 'big') + filename.encode('utf-8') + b'|' + data
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
    
    def handle_received_frame(self, frame: LinkFrame):
        """Process incoming frames related to file transfers.
        
        Routes frames to appropriate handlers based on frame type:
        - FILE_META: Initializes new file reception state.
        - FILE_CHUNK: Stores chunk and sends ACK.
        - ACK: Signals waiting send thread that chunk was received.
        
        This method should be called from the link layer's on_frame callback
        to handle all file transfer protocol frames.
        
        Args:
            frame: Received LinkFrame to process.
        """
        if frame.typ == FrameType.FILE_META:
            self._handle_file_meta(frame)
        
        elif frame.typ == FrameType.FILE_CHUNK:
            self._handle_file_chunk(frame)
        
        elif frame.typ == FrameType.ACK:
            self._handle_ack(frame)
    
    def _handle_file_meta(self, frame: LinkFrame):
        """Handle FILE_META frame to initialize a new file reception.
        
        Parses the metadata payload format: "filename|size|chunks|hash"
        and creates a FileTransferState entry in active_receives to track
        incoming chunks. This must be received before any FILE_CHUNK frames.
        
        Args:
            frame: Received metadata frame with FILE_META type.
        """
        try:
            parts = frame.payload.decode('utf-8').split('|')
            if len(parts) != 4:
                raise ValueError("FILE_META payload must contain filename|size|chunks|hash")
            filename, size_str, chunks_str, file_hash = parts
            
            transfer_key = (frame.src, filename)
            self.active_receives[transfer_key] = FileTransferState(
                filename=filename,
                total_size=int(size_str),
                total_chunks=int(chunks_str),
                file_hash=file_hash
            )
        except (ValueError, UnicodeDecodeError) as e:
            print(f"Invalid FILE_META: {e}")
    
    def _handle_file_chunk(self, frame: LinkFrame):
        """Handle FILE_CHUNK frame and send ACK.
        
        Processes a received file chunk:
        1. Extracts chunk_id from first 4 bytes.
        2. Parses filename and chunk data separated by '|'.
        3. Stores chunk in transfer state dictionary.
        4. Immediately sends ACK frame to sender.
        5. Updates progress via callback when a new chunk is accepted or size changes.
        6. If all chunks received, calls _finalize_file_reception().
        
        Args:
            frame: Received chunk frame with FILE_CHUNK type.
        """
        try:
            chunk_id = int.from_bytes(frame.payload[:4], 'big')
            
            separator_idx = frame.payload.find(b'|', 4)
            if separator_idx == -1:
                return
            
            filename = frame.payload[4:separator_idx].decode('utf-8')
            chunk_data = frame.payload[separator_idx + 1:]
            
            transfer_key = (frame.src, filename)
            if transfer_key not in self.active_receives:
                return
            
            transfer = self.active_receives[transfer_key]
            is_new_chunk = chunk_id not in transfer.chunks
            progress_refresh_needed = False
            if is_new_chunk:
                transfer.chunks[chunk_id] = chunk_data
                transfer.received_size += len(chunk_data)
                progress_refresh_needed = True
            else:
                existing_chunk = transfer.chunks[chunk_id]
                if existing_chunk != chunk_data:
                    transfer.chunks[chunk_id] = chunk_data
                    delta = len(chunk_data) - len(existing_chunk)
                    if delta:
                        transfer.received_size += delta
                        progress_refresh_needed = True
            
            ack_payload = chunk_id.to_bytes(4, 'big') + filename.encode('utf-8')
            self.link_layer.send(frame.src, FrameType.ACK, ack_payload)
            
            if self.on_progress and (is_new_chunk or progress_refresh_needed):
                self.on_progress(filename, transfer.received_size, transfer.total_size)
            
            if len(transfer.chunks) == transfer.total_chunks:
                self._finalize_file_reception(frame.src, filename)
        
        except (ValueError, UnicodeDecodeError) as e:
            print(f"Invalid FILE_CHUNK: {e}")
    
    def _handle_ack(self, frame: LinkFrame):
        """Handle ACK frame to signal chunk receipt.
        
        Extracts the chunk_id and filename from the ACK payload and sets the
        corresponding threading.Event to unblock the waiting send thread in
        _send_chunk_reliable(). This allows the sender to proceed to the next chunk
        even when multiple files are in flight to the same destination.
        
        Args:
            frame: Received ACK frame with chunk acknowledgment.
        """
        try:
            chunk_id = int.from_bytes(frame.payload[:4], 'big')
            filename = frame.payload[4:].decode('utf-8') if len(frame.payload) > 4 else ""
            ack_key = (frame.src, filename, chunk_id)
            
            with self._lock:
                if ack_key in self._ack_events:
                    self._ack_events[ack_key].set()
        
        except (ValueError, UnicodeDecodeError):
            pass
    
    def _finalize_file_reception(self, src_mac: bytes, filename: str):
        """Reassemble chunks and save the complete file.
        
        Called when all chunks have been received. Performs:
        1. Sorts chunks by chunk_id to ensure correct order.
        2. Writes chunks sequentially to reconstruct the file.
        3. Computes SHA256 hash of reconstructed file.
        4. Compares with hash from FILE_META to verify integrity.
        5. Invokes on_complete callback with success status.
        6. Cleans up transfer state.
        
        Args:
            src_mac: Source MAC address of sender (6 bytes).
            filename: Name of received file.
        """
        transfer_key = (src_mac, filename)
        transfer = self.active_receives.get(transfer_key)
        if not transfer:
            return
        
        try:
            output_path = self.download_dir / filename
            
            with open(output_path, 'wb') as f:
                for chunk_id in sorted(transfer.chunks.keys()):
                    f.write(transfer.chunks[chunk_id])
            
            received_hash = self._compute_file_hash(str(output_path))
            success = (received_hash == transfer.file_hash)
            
            if not success:
                print(f"Hash mismatch for {filename}! Expected {transfer.file_hash}, got {received_hash}")
            
            if self.on_complete:
                self.on_complete(filename, success)
            
            self.active_receives.pop(transfer_key, None)
        
        except Exception as e:
            print(f"Error finalizing {filename}: {e}")
            if self.on_complete:
                self.on_complete(filename, False)
    
    @staticmethod
    def _compute_file_hash(filepath: str) -> str:
        """Compute SHA256 hash of a file.
        
        Reads the file in 8192-byte chunks to avoid loading large files
        entirely into memory. Used for integrity verification to detect
        corruption during transmission.
        
        Args:
            filepath: Path to file to hash.
        
        Returns:
            SHA256 hash as hexadecimal string (64 characters).
        """
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
