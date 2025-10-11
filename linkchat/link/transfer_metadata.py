"""Metadata handling for file and folder transfers.

Provides JSON construction, parsing, validation, and ACK payload generation
for the unified TRANSFER_META protocol.
"""

import json
from typing import Dict, List, Tuple, Optional
from pathlib import Path


class TransferMetadata:
    """Utilities for building and parsing transfer metadata."""
    
    @staticmethod
    def build_file_metadata(name: str, size: int, chunks: int, file_hash: str) -> bytes:
        """Build JSON metadata payload for file transfer.
        
        Args:
            name: File name or virtual path (e.g., "MyFolder/subdir/file.txt").
            size: Total file size in bytes.
            chunks: Number of chunks the file is divided into.
            file_hash: SHA256 hash of the file (hex string).
        
        Returns:
            JSON-encoded metadata bytes ready for TRANSFER_META frame.
        """
        metadata = {
            "type": "file",
            "name": name,
            "size": size,
            "chunks": chunks,
            "hash": file_hash
        }
        return json.dumps(metadata, separators=(",", ":")).encode('utf-8')
    
    @staticmethod
    def build_folder_metadata(root: str, files: List[Tuple[str, int]]) -> bytes:
        """Build JSON metadata payload for folder transfer.
        
        Args:
            root: Root folder name (sanitized).
            files: List of (relative_path, size) tuples for all files in folder.
        
        Returns:
            JSON-encoded metadata bytes ready for TRANSFER_META frame.
        """
        metadata = {
            "type": "folder",
            "root": root,
            "files": [{"path": rel, "size": size} for rel, size in files]
        }
        return json.dumps(metadata, separators=(",", ":")).encode('utf-8')
    
    @staticmethod
    def parse_metadata(payload: bytes) -> Optional[Dict]:
        """Parse JSON metadata from TRANSFER_META frame payload.
        
        Args:
            payload: Raw frame payload bytes.
        
        Returns:
            Parsed metadata dictionary, or None if parsing fails.
        """
        try:
            return json.loads(payload.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
    
    @staticmethod
    def validate_file_metadata(data: Dict) -> bool:
        """Validate that file metadata contains all required fields.
        
        Args:
            data: Parsed metadata dictionary.
        
        Returns:
            True if valid file metadata, False otherwise.
        """
        if data.get("type") != "file":
            return False
        
        name = data.get("name", "")
        size = data.get("size", 0)
        chunks = data.get("chunks", 0)
        file_hash = data.get("hash", "")
        
        return bool(
            name and
            isinstance(size, int) and
            isinstance(chunks, int) and
            file_hash
        )
    
    @staticmethod
    def validate_folder_metadata(data: Dict) -> bool:
        """Validate that folder metadata contains all required fields.
        
        Args:
            data: Parsed metadata dictionary.
        
        Returns:
            True if valid folder metadata, False otherwise.
        """
        if data.get("type") != "folder":
            return False
        
        root = data.get("root")
        files = data.get("files", [])
        
        return isinstance(root, str) and isinstance(files, list)


class ACKPayload:
    """Utilities for constructing ACK payloads."""
    
    # Metadata ACK marker byte (0x4D = 'M')
    META_ACK_MARKER = 0x4D
    
    @staticmethod
    def build_metadata_ack(transfer_name: str) -> bytes:
        """Build ACK payload for metadata confirmation.
        
        Args:
            transfer_name: Name of transfer (filename or folder root).
        
        Returns:
            ACK payload bytes: 0x4D + transfer_name (UTF-8).
        """
        return bytes([ACKPayload.META_ACK_MARKER]) + transfer_name.encode('utf-8')
    
    @staticmethod
    def build_chunk_ack(chunk_id: int, filename: str) -> bytes:
        """Build ACK payload for chunk confirmation.
        
        Args:
            chunk_id: Chunk sequence number.
            filename: Name of file being transferred.
        
        Returns:
            ACK payload bytes: chunk_id (4 bytes, big-endian) + filename (UTF-8).
        """
        return chunk_id.to_bytes(4, 'big') + filename.encode('utf-8')
    
    @staticmethod
    def parse_ack(payload: bytes) -> Optional[Tuple[str, int | str]]:
        """Parse ACK payload to determine type and extract information.
        
        Args:
            payload: ACK frame payload bytes.
        
        Returns:
            Tuple of (filename/transfer_name, chunk_id or "meta"), or None if invalid.
        """
        if len(payload) == 0:
            return None
        
        # Check for metadata ACK
        if payload[0] == ACKPayload.META_ACK_MARKER:
            if len(payload) > 1:
                try:
                    transfer_name = payload[1:].decode('utf-8')
                    return (transfer_name, "meta")
                except UnicodeDecodeError:
                    return None
            return None
        
        # Otherwise, treat as chunk ACK
        if len(payload) >= 4:
            try:
                chunk_id = int.from_bytes(payload[:4], 'big')
                filename = payload[4:].decode('utf-8') if len(payload) > 4 else ""
                return (filename, chunk_id)
            except (ValueError, UnicodeDecodeError):
                return None
        
        return None
