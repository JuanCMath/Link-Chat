"""File and folder transfer module for sending and receiving transfers of any size.

Implements chunking, reassembly, and progress tracking for reliable file and 
folder transfers over the link layer. Coordinates metadata handling and 
reliability layers to provide a complete transfer solution.
"""

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Optional, Tuple

from ..mac.adaptive_params import FileParams, file_params_from_medium
from ..core.link_layer import FrameType, LinkFrame, LinkLayer
from .transfer_metadata import ACKPayload, TransferMetadata
from .transfer_reliability import ReliableTransfer

logger = logging.getLogger(__name__)


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
        
        # Initialize reliability layer for ACK/retry handling
        self._reliable = ReliableTransfer(
            link_layer=link_layer,
            ack_timeout=self.ack_timeout,
            max_retries=self.max_retries
        )
        
        self.active_sends: Dict[Tuple[bytes, str], FileTransferState] = {}
        self.active_receives: Dict[Tuple[bytes, str], FileTransferState] = {}
    
    def send_file(self, dst_mac: bytes, filepath: str, virtual_path: Optional[str] = None) -> bool:
        """Send a file to the specified destination.
        
        Process:
        1. Computes file metadata (size, total chunks, SHA256 hash).
        2. Sends TRANSFER_META frame with JSON metadata to initialize receiver.
        3. Waits for metadata ACK confirmation before proceeding.
        4. Reads file in adaptive chunk_size increments.
        5. For each chunk, calls _send_chunk_reliable() which:
           - Sends FILE_CHUNK frame
           - Waits for ACK using the configured ack_timeout
           - Retries up to configured max_retries times
        6. Updates progress after each successful chunk.
        7. Applies optional inter_chunk_delay to avoid congestion.
        8. Cleans up transfer state in finally block.
        
        Args:
            dst_mac: Destination MAC address (6 bytes).
            filepath: Path to the file to send.
            virtual_path: Optional relative path advertised to receiver instead of
                the actual filename. Used by send_folder to preserve directory
                structure (e.g., "MyFolder/subdir/file.txt").
        
        Returns:
            True if all chunks were acknowledged successfully, False if any chunk
            failed after maximum retries.
            
        Raises:
            FileNotFoundError: If the specified file does not exist.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        file_size = os.path.getsize(filepath)
        transfer_name = self._determine_transfer_name(filepath, virtual_path)
        total_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        
        file_hash = self._compute_file_hash(filepath)
        
        transfer_key = (dst_mac, transfer_name)
        self.active_sends[transfer_key] = FileTransferState(
            filename=transfer_name,
            total_size=file_size,
            total_chunks=total_chunks,
            file_hash=file_hash
        )
        
        try:
            # Build unified JSON metadata for file transfer
            meta_payload = TransferMetadata.build_file_metadata(
                name=transfer_name,
                size=file_size,
                chunks=total_chunks,
                file_hash=file_hash
            )
            
            # Send metadata and wait for ACK
            if not self._reliable.send_metadata_reliable(dst_mac, transfer_name, meta_payload):
                if self.on_complete:
                    self.on_complete(transfer_name, False)
                return False
            
            time.sleep(0.1)
            
            with open(filepath, 'rb') as f:
                for chunk_id in range(total_chunks):
                    chunk_data = f.read(self.chunk_size)
                    success = self._reliable.send_chunk_reliable(
                        dst_mac, transfer_name, chunk_id, chunk_data
                    )
                    
                    if not success:
                        if self.on_complete:
                            self.on_complete(transfer_name, False)
                        return False
                    
                    bytes_sent = min((chunk_id + 1) * self.chunk_size, file_size)
                    if self.on_progress:
                        self.on_progress(transfer_name, bytes_sent, file_size)

                    if self.inter_chunk_delay:
                        time.sleep(self.inter_chunk_delay)
            
            if self.on_complete:
                self.on_complete(transfer_name, True)
            return True
            
        finally:
            self.active_sends.pop(transfer_key, None)
    
    def send_folder(self, dst_mac: bytes, folder_path: str) -> bool:
        """Send a complete folder with all its contents to the destination.
        
        Process:
        1. Validates folder exists and recursively collects all files.
        2. Constructs JSON metadata: {"type": "folder", "root": folder_name, "files": [{path, size}, ...]}.
        3. Sends TRANSFER_META frame with metadata and waits for ACK.
        4. Sends each file individually using send_file() with virtual_path to preserve hierarchy.
        5. Returns True if folder is empty (no files to transfer).
        
        The unified metadata approach ensures the receiver can prepare the directory
        structure before any files arrive, with reliable ACK confirmation that the
        metadata was received. Each file is then sent with its own metadata and ACKs,
        providing full end-to-end reliability for the entire folder transfer.
        
        Args:
            dst_mac: Destination MAC address (6 bytes).
            folder_path: Path to the folder to send.
        
        Returns:
            True if all files were successfully transferred, False if any file failed.
        
        Raises:
            NotADirectoryError: If folder_path is not a directory.
            ValueError: If the folder name cannot be sanitized (empty after cleanup).
        """
        base = Path(folder_path)
        if not base.is_dir():
            raise NotADirectoryError(f"Folder not found: {folder_path}")
        
        # Collect all files recursively
        files = self._collect_files(base)
        
        # Sanitize root folder name
        root_token = self._sanitize_transfer_name(base.name)
        if not root_token:
            raise ValueError("Folder name cannot be empty")
        
        # Build unified JSON metadata for folder transfer
        meta_payload = TransferMetadata.build_folder_metadata(root_token, files)
        
        # Send metadata and wait for ACK
        if not self._reliable.send_metadata_reliable(dst_mac, root_token, meta_payload):
            return False
        
        # If no files, transfer is complete
        if not files:
            return True
        
        # Send each file with virtual path to preserve structure
        success = True
        for rel_path, _ in files:
            virtual_path = f"{root_token}/{rel_path}" if rel_path else root_token
            full_path = base / Path(rel_path)
            if not self.send_file(dst_mac, str(full_path), virtual_path=virtual_path):
                success = False
                break
        
        return success
    
    def handle_received_frame(self, frame: LinkFrame):
        """Process incoming frames related to file and folder transfers.
        
        Routes frames to appropriate handlers based on frame type:
        - TRANSFER_META: Initializes new file or folder reception state.
        - FILE_CHUNK: Stores chunk and sends ACK.
        - ACK: Signals waiting send thread that chunk or metadata was received.
        
        This method should be called from the link layer's on_frame callback
        to handle all transfer protocol frames.
        
        Args:
            frame: Received LinkFrame to process.
        """
        if frame.typ == FrameType.TRANSFER_META:
            self._handle_transfer_meta(frame)
        
        elif frame.typ == FrameType.FILE_CHUNK:
            self._handle_file_chunk(frame)
        
        elif frame.typ == FrameType.ACK:
            self._handle_ack(frame)
    
    def _handle_transfer_meta(self, frame: LinkFrame):
        """Handle TRANSFER_META frame to initialize a new transfer reception.
        
        Parses the JSON metadata payload which can represent either:
        - File transfer: {"type": "file", "name": ..., "size": ..., "chunks": ..., "hash": ...}
        - Folder transfer: {"type": "folder", "root": ..., "files": [{path, size}, ...]}
        
        For file transfers:
        - Creates FileTransferState entry in active_receives to track incoming chunks.
        - Sanitizes filename to prevent directory traversal attacks.
        - Sends ACK to confirm metadata receipt.
        
        For folder transfers:
        - Creates root directory and all subdirectories based on files list.
        - Sends ACK to confirm metadata receipt.
        - Actual files will arrive as individual file transfers with virtual paths.
        
        Args:
            frame: Received metadata frame with TRANSFER_META type.
        """
        data = TransferMetadata.parse_metadata(frame.payload)
        if data is None:
            logger.warning("Invalid TRANSFER_META: failed to parse JSON")
            return
        
        transfer_type = data.get("type")
        
        if transfer_type == "file":
            self._handle_file_metadata(frame, data)
        elif transfer_type == "folder":
            self._handle_folder_metadata(frame, data)
        else:
            logger.warning("Unknown transfer type: %s", transfer_type)
    
    def _handle_file_metadata(self, frame: LinkFrame, data: dict):
        """Handle file-specific metadata from TRANSFER_META frame.
        
        Extracts file metadata and prepares for chunk reception.
        
        Args:
            frame: Received frame containing the metadata.
            data: Parsed JSON dictionary with file metadata.
        """
        filename_raw = data.get("name", "")
        size_val = data.get("size", 0)
        chunks_val = data.get("chunks", 0)
        hash_val = data.get("hash", "")
        
        if not all([filename_raw, isinstance(size_val, int), isinstance(chunks_val, int), hash_val]):
            logger.warning("Invalid file metadata: missing required fields")
            return
        
        transfer_name = self._sanitize_transfer_name(filename_raw)
        if not transfer_name:
            fallback_name = Path(filename_raw).name
            sanitized_fallback = self._sanitize_transfer_name(fallback_name)
            transfer_name = sanitized_fallback if sanitized_fallback else fallback_name
        
        transfer_key = (frame.src, transfer_name)
        self.active_receives[transfer_key] = FileTransferState(
            filename=transfer_name,
            total_size=size_val,
            total_chunks=chunks_val,
            file_hash=hash_val
        )
        
        # Send metadata ACK
        ack_payload = ACKPayload.build_metadata_ack(transfer_name)
        self.link_layer.send(frame.src, FrameType.ACK, ack_payload)
    
    def _handle_folder_metadata(self, frame: LinkFrame, data: dict):
        """Handle folder-specific metadata from TRANSFER_META frame.
        
        Creates the complete directory structure based on the files list
        in the metadata. Individual files will arrive as separate file transfers.
        
        Args:
            frame: Received frame containing the metadata.
            data: Parsed JSON dictionary with folder metadata.
        """
        root_value = data.get("root")
        files_value = data.get("files", [])
        
        if not isinstance(root_value, str):
            logger.warning("Invalid folder metadata: root must be a string")
            return
        
        root_token = self._sanitize_transfer_name(root_value)
        if not root_token:
            logger.warning("Invalid folder metadata: root name cannot be empty")
            return
        
        # Create root directory
        base_path = self.download_dir / root_token
        base_path.mkdir(parents=True, exist_ok=True)
        
        # Create all subdirectories based on files list
        for entry in files_value:
            if not isinstance(entry, dict):
                continue
            rel_value = entry.get("path")
            if not isinstance(rel_value, str):
                continue
            sanitized = self._sanitize_transfer_name(rel_value)
            if not sanitized:
                continue
            # Create parent directory for this file
            file_path = base_path / sanitized
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Send metadata ACK
        ack_payload = ACKPayload.build_metadata_ack(root_token)
        self.link_layer.send(frame.src, FrameType.ACK, ack_payload)
    
    def _handle_file_chunk(self, frame: LinkFrame):
        """Handle FILE_CHUNK frame and send ACK.
        
        Processes a received file chunk:
        1. Extracts chunk_id from first 4 bytes.
        2. Parses filename and chunk data separated by '|'.
        3. Checks if chunk is new or a duplicate:
           - New chunks: stored and received_size incremented.
           - Duplicate chunks with identical data: silently ignored (no size change).
           - Duplicate chunks with different data: replaced and size adjusted by delta.
        4. Immediately sends ACK frame to sender.
        5. Updates progress via callback only when size actually changes.
        6. If all chunks received, calls _finalize_file_reception().
        
        The duplicate handling ensures that progress counters remain accurate even
        if the same chunk is retransmitted multiple times, preventing inflated
        byte counts or incorrect completion detection.
        
        Args:
            frame: Received chunk frame with FILE_CHUNK type.
        """
        try:
            chunk_id = int.from_bytes(frame.payload[:4], 'big')
            
            separator_idx = frame.payload.find(b'|', 4)
            if separator_idx == -1:
                return
            
            filename_raw = frame.payload[4:separator_idx].decode('utf-8')
            transfer_name = self._sanitize_transfer_name(filename_raw)
            if not transfer_name:
                fallback_name = Path(filename_raw).name
                sanitized_fallback = self._sanitize_transfer_name(fallback_name)
                transfer_name = sanitized_fallback if sanitized_fallback else fallback_name
            chunk_data = frame.payload[separator_idx + 1:]
            
            transfer_key = (frame.src, transfer_name)
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
            
            # Send chunk ACK
            ack_payload = ACKPayload.build_chunk_ack(chunk_id, transfer.filename)
            self.link_layer.send(frame.src, FrameType.ACK, ack_payload)
            
            if self.on_progress and (is_new_chunk or progress_refresh_needed):
                self.on_progress(transfer.filename, transfer.received_size, transfer.total_size)
            
            if len(transfer.chunks) == transfer.total_chunks:
                self._finalize_file_reception(frame.src, transfer.filename)
        
        except (ValueError, UnicodeDecodeError) as e:
            logger.warning("Invalid FILE_CHUNK: %s", e)
    
    def _handle_ack(self, frame: LinkFrame):
        """Handle ACK frame to signal chunk or metadata receipt.
        
        Parses ACK payload and signals the reliability layer to unblock
        waiting send threads. Supports both metadata ACKs and chunk ACKs.
        
        Args:
            frame: Received ACK frame with acknowledgment.
        """
        parsed = ACKPayload.parse_ack(frame.payload)
        if parsed is None:
            return
        
        identifier, chunk_id_or_meta = parsed
        self._reliable.signal_ack(frame.src, identifier, chunk_id_or_meta)
    
    def _finalize_file_reception(self, src_mac: bytes, filename: str):
        """Reassemble chunks and save the complete file.
        
        Called when all chunks have been received. Performs:
        1. Sorts chunks by chunk_id to ensure correct order.
        2. Writes chunks sequentially to reconstruct the file.
        3. Computes SHA256 hash of reconstructed file.
        4. Compares with hash from TRANSFER_META to verify integrity.
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
            output_path = self._resolve_output_path(filename)

            with open(output_path, 'wb') as f:
                for chunk_id in sorted(transfer.chunks.keys()):
                    f.write(transfer.chunks[chunk_id])
            
            received_hash = self._compute_file_hash(str(output_path))
            success = (received_hash == transfer.file_hash)
            
            if not success:
                logger.error("Hash mismatch for %s! Expected %s, got %s", 
                             filename, transfer.file_hash, received_hash)
            
            if self.on_complete:
                self.on_complete(filename, success)
            
            self.active_receives.pop(transfer_key, None)
        
        except Exception as e:
            logger.error("Error finalizing %s: %s", filename, e)
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

    def _determine_transfer_name(self, filepath: str, virtual_path: Optional[str]) -> str:
        """Determine the advertised transfer name for a file send.
        
        If virtual_path is provided (e.g., by FolderTransfer), it takes precedence
        over the actual filename. This allows preserving directory structure when
        sending files as part of a folder transfer.
        
        Args:
            filepath: Actual file path on disk.
            virtual_path: Optional virtual path to advertise instead.
        
        Returns:
            Sanitized transfer name to use in FILE_META and FILE_CHUNK frames.
        """
        candidate = virtual_path if virtual_path else Path(filepath).name
        sanitized = self._sanitize_transfer_name(candidate)
        if sanitized:
            return sanitized
        fallback = self._sanitize_transfer_name(Path(filepath).name)
        return fallback if fallback else Path(filepath).name

    def _sanitize_transfer_name(self, value: str) -> str:
        """Sanitize a transfer name to prevent directory traversal attacks.
        
        Removes path components like "..", ".", and empty strings to ensure
        the transfer name cannot escape the download directory.
        
        Args:
            value: Transfer name to sanitize (may contain path separators).
        
        Returns:
            Sanitized path using forward slashes, safe for cross-platform use.
        """
        normalized = value.replace("\\", "/")
        parts = [part for part in PurePosixPath(normalized).parts if part not in ("", ".", "..")]
        return "/".join(parts)

    def _resolve_output_path(self, transfer_name: str) -> Path:
        """Resolve the output path for a received file transfer.
        
        Applies sanitization and constructs the full output path within the
        download directory. For nested paths (e.g., "folder/subdir/file.txt"),
        creates parent directories as needed.
        
        Args:
            transfer_name: Sanitized transfer name from TRANSFER_META.
        
        Returns:
            Absolute path where the file should be saved.
        
        Raises:
            ValueError: If the sanitized path resolves to the download directory itself.
        """
        sanitized = self._sanitize_transfer_name(transfer_name)
        parts = sanitized.split("/") if sanitized else []
        path = self.download_dir.joinpath(*parts) if parts else self.download_dir / Path(transfer_name).name
        if path == self.download_dir:
            raise ValueError("Invalid transfer path")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    
    def _collect_files(self, base: Path) -> List[Tuple[str, int]]:
        """Recursively collect all files in a directory tree.
        
        Scans the directory recursively and builds a list of all files with
        their relative paths and sizes. Paths are sanitized to prevent directory
        traversal attacks and normalized to POSIX-style forward slashes for
        cross-platform compatibility.
        
        Args:
            base: Root directory to scan.
        
        Returns:
            List of (relative_path, file_size) tuples for all files in the tree.
            Relative paths use forward slashes and are sanitized.
        """
        collected: List[Tuple[str, int]] = []
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(base).as_posix()
                sanitized = self._sanitize_transfer_name(rel)
                if sanitized:
                    collected.append((sanitized, path.stat().st_size))
        return collected
