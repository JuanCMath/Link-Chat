"""Folder transfer module for sending and receiving complete directory structures.

Implements structured metadata broadcast followed by sequential file transmission,
allowing entire folder hierarchies to be transferred while preserving their
relative paths and directory structure.
"""

import json
from pathlib import Path, PurePosixPath
from typing import Dict, List, Tuple

from .file_transfer import FileTransfer
from .link_layer import FrameType, LinkFrame, LinkLayer


class FolderTransfer:
    """Handles folder transmission and reception with directory structure preservation.
    
    Provides methods to send complete folders by:
    1. Broadcasting a FOLDER_META frame with JSON payload listing all files and structure.
    2. Using FileTransfer to send each file with a virtual path preserving hierarchy.
    3. Reconstructing the directory tree on the receiver side before files arrive.
    """
    
    def __init__(self, link_layer: LinkLayer, file_transfer: FileTransfer, download_dir: str) -> None:
        """Initialize the folder transfer manager.
        
        Args:
            link_layer: Active LinkLayer instance for metadata frame transmission.
            file_transfer: FileTransfer instance to handle individual file sends/receives.
            download_dir: Root directory where received folders will be reconstructed.
        """
        self.link_layer = link_layer
        self.file_transfer = file_transfer
        self.download_dir = Path(download_dir)
        self._incoming: Dict[Tuple[bytes, str], Path] = {}

    def send_folder(self, dst_mac: bytes, folder_path: str) -> bool:
        """Send a complete folder to the specified destination.
        
        Process:
        1. Validates the folder exists and collects all files recursively.
        2. Constructs JSON metadata: {"root": folder_name, "files": [{path, size}, ...]}.
        3. Broadcasts FOLDER_META frame so receiver can prepare directory structure.
        4. Sends each file individually using FileTransfer with virtual_path set to
           preserve the relative hierarchy (e.g., "MyFolder/subdir/file.txt").
        5. Returns early with True if folder is empty (no files to transfer).
        
        Note on reliability: FOLDER_META is sent without ACK confirmation (fire-and-forget).
        This is acceptable because FileTransfer creates parent directories automatically
        when receiving files. If FOLDER_META is lost, files still arrive correctly and
        directories get created on-demand. The worst case is slightly delayed directory
        creation (per-file instead of up-front), but the final structure is identical.
        For critical applications requiring guaranteed metadata delivery, consider
        implementing ACK handling for FOLDER_META frames.
        
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
        files = self._collect_files(base)
        root_token = self._sanitize_relative(base.name) or base.name
        if not root_token:
            raise ValueError("Folder name cannot be empty")
        metadata = {"root": root_token, "files": [{"path": rel, "size": size} for rel, size in files]}
        payload = json.dumps(metadata, separators=(",", ":")).encode("utf-8")
        self.link_layer.send(dst_mac, FrameType.FOLDER_META, payload)
        if not files:
            return True
        success = True
        for rel_path, _ in files:
            virtual_path = f"{root_token}/{rel_path}" if rel_path else root_token
            full_path = base / Path(rel_path)
            if not self.file_transfer.send_file(dst_mac, str(full_path), virtual_path=virtual_path):
                success = False
                break
        return success

    def handle_folder_meta(self, frame: LinkFrame) -> None:
        """Handle FOLDER_META frame to prepare for incoming folder transfer.
        
        Parses the JSON metadata payload and pre-creates all necessary directories
        so that when individual FILE_META/FILE_CHUNK frames arrive, the folder
        structure is already in place.
        
        Metadata format:
            {
                "root": "folder_name",
                "files": [
                    {"path": "relative/path/to/file.txt", "size": 12345},
                    ...
                ]
            }
        
        Process:
        1. Decodes JSON from payload.
        2. Extracts and sanitizes the root folder name.
        3. Creates the root directory in download_dir.
        4. For each file in metadata, creates parent directories as needed.
        5. Stores the base_path for this transfer keyed by (src_mac, root_token).
        
        Args:
            frame: Received FOLDER_META frame with JSON payload.
        """
        try:
            data = json.loads(frame.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        root_value = data.get("root")
        files_value = data.get("files", [])
        if not isinstance(root_value, str):
            return
        root_token = self._sanitize_relative(root_value) or root_value.strip()
        if not root_token:
            return
        base_path = self._compose_path(self.download_dir, root_token)
        base_path.mkdir(parents=True, exist_ok=True)
        for entry in files_value:
            if not isinstance(entry, dict):
                continue
            rel_value = entry.get("path")
            if not isinstance(rel_value, str):
                continue
            sanitized = self._sanitize_relative(rel_value)
            if not sanitized:
                continue
            target_dir = self._compose_path(base_path, sanitized).parent
            target_dir.mkdir(parents=True, exist_ok=True)
        self._incoming[(frame.src, root_token)] = base_path

    def _collect_files(self, base: Path) -> List[Tuple[str, int]]:
        """Recursively collect all files in a directory tree.
        
        Args:
            base: Root directory to scan.
        
        Returns:
            List of (relative_path, file_size) tuples for all files in the tree.
            Paths are sanitized POSIX-style with forward slashes.
        """
        collected: List[Tuple[str, int]] = []
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(base).as_posix()
                sanitized = self._sanitize_relative(rel)
                if sanitized:
                    collected.append((sanitized, path.stat().st_size))
        return collected

    def _sanitize_relative(self, value: str) -> str:
        """Sanitize a relative path to prevent directory traversal attacks.
        
        Converts backslashes to forward slashes, removes empty parts, ".", and "..",
        ensuring the path cannot escape the intended directory.
        
        Args:
            value: Relative path string (may contain backslashes or dangerous components).
        
        Returns:
            Sanitized POSIX-style path with only safe components.
        """
        normalized = value.replace("\\", "/")
        parts = [part for part in PurePosixPath(normalized).parts if part not in ("", ".", "..")]
        return "/".join(parts)

    def _compose_path(self, base: Path, relative: str) -> Path:
        """Compose a safe absolute path from a base directory and relative path.
        
        Applies sanitization to the relative path before joining with base,
        ensuring the result stays within the base directory tree.
        
        Args:
            base: Base directory path.
            relative: Relative path string to join.
        
        Returns:
            Safe absolute path within the base directory.
        """
        parts = self._sanitize_relative(relative).split("/") if relative else []
        filtered = [part for part in parts if part]
        return base.joinpath(*filtered) if filtered else base / relative
