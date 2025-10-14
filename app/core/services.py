"""
services.py
~~~~~~~~~~~

Backend utility services for LinkChat application.

This module provides helper functions used across the application for:
    - Peer resolution (MAC address lookup by name or address)
    - Directory packaging (creating tarball archives for transfer)
    - Temporary archive tracking (cleanup management)

Key Functions:
    - resolve_mac: Resolve user input to MAC address
    - create_directory_archive: Package directory as .tar.gz
    - track_pending_archive/pop_pending_archive: Archive lifecycle management

Note:
    The archive tracking uses a module-level dictionary for simplicity.
    This is sufficient for single-instance deployments but would need
    refactoring for multi-threaded archive creation scenarios.
"""

import os
import re
import tarfile
import tempfile
from typing import Dict, Optional

from ..peer_discovery import PeerRegistry

# Regex pattern for validating MAC address format
MAC_ADDRESS_PATTERN = re.compile(r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$")

# Module-level tracking of temporary archives pending cleanup
# Maps session ID -> temporary file path
_pending_archives: Dict[str, str] = {}


def resolve_mac(token: str, registry: PeerRegistry) -> Optional[str]:
    """
    Resolve user input to a MAC address using registry or pattern matching.

    Attempts resolution in two ways:
    1. Query the peer registry for exact name match
    2. Validate and normalize if input is already a MAC address

    This allows users to specify peers by either their registered name
    (e.g., "Server1") or directly by MAC address (e.g., "aa:bb:cc:dd:ee:ff").

    Args:
        token: User input - either a peer name or MAC address.
        registry: PeerRegistry instance to query for name resolution.

    Returns:
        Optional[str]: Normalized MAC address (lowercase with colons) if
                      resolution succeeds, None otherwise.

    Example:
        >>> registry = PeerRegistry(store)
        >>> registry.upsert("aa:bb:cc:dd:ee:ff", "Server1")
        >>> resolve_mac("Server1", registry)
        'aa:bb:cc:dd:ee:ff'
        >>> resolve_mac("AA:BB:CC:DD:EE:FF", registry)
        'aa:bb:cc:dd:ee:ff'
        >>> resolve_mac("Unknown", registry)
        None
    """
    # First, try registry lookup (handles name resolution)
    mac_from_registry = registry.resolve(token)
    if mac_from_registry:
        return mac_from_registry

    # Fallback: check if token is already a valid MAC address
    if MAC_ADDRESS_PATTERN.match(token):
        return token.lower()

    return None


def create_directory_archive(directory_path: str) -> Optional[Dict[str, str]]:
    """
    Package a directory into a temporary .tar.gz archive for transfer.

    Creates a compressed tarball of the specified directory in a temporary
    location. The archive uses the directory's basename as the root entry
    name (e.g., "mydir/" contains all the directory's contents).

    Args:
        directory_path: Absolute or relative path to the directory to package.

    Returns:
        Optional[Dict[str, str]]: Dictionary with keys:
            - 'archive_path': Absolute path to the temporary .tar.gz file
            - 'folder_name': Basename of the original directory
        Returns None if directory doesn't exist or packaging fails.

    Cleanup:
        Caller is responsible for deleting the temporary archive after use.
        Use track_pending_archive() for automatic cleanup on transfer completion.

    Example:
        >>> package = create_directory_archive("/path/to/mydir")
        >>> if package:
        ...     print(f"Archive: {package['archive_path']}")
        ...     print(f"Folder: {package['folder_name']}")
        ...     # Send archive, then:
        ...     os.remove(package['archive_path'])

    Note:
        - Hidden files and directories are included
        - Symlinks are preserved (not followed)
        - Permissions are maintained in the archive
    """
    # Normalize to absolute path
    directory_path = os.path.abspath(directory_path)

    # Validate directory exists
    if not os.path.isdir(directory_path):
        print(f"[senddir] Directory does not exist: {directory_path}", flush=True)
        return None

    # Extract directory name (fallback to "folder" if root)
    folder_name = os.path.basename(directory_path) or "folder"

    tmp_archive_path = ""
    try:
        # Create temporary file for archive
        fd, tmp_archive_path = tempfile.mkstemp(
            prefix="linkchat-dir-", suffix=".tar.gz"
        )
        os.close(fd)  # Close file descriptor, tarfile will reopen

        # Create gzip-compressed tarball
        with tarfile.open(tmp_archive_path, "w:gz") as archive:
            # Add directory with its basename as archive root
            archive.add(directory_path, arcname=folder_name)

    except Exception as exc:
        print(f"[senddir] Failed to package directory: {exc}", flush=True)
        # Cleanup partial archive on failure
        try:
            if tmp_archive_path:
                os.remove(tmp_archive_path)
        except Exception:
            pass  # Ignore cleanup errors
        return None

    return {"archive_path": tmp_archive_path, "folder_name": folder_name}


def track_pending_archive(session_id: str, archive_path: str) -> None:
    """
    Register a temporary archive for cleanup after transfer completion.

    Stores the mapping of transfer session ID to temporary file path.
    Use pop_pending_archive() to retrieve and remove the tracking entry
    when the transfer completes (successfully or not).

    Args:
        session_id: Unique file transfer session identifier.
        archive_path: Absolute path to the temporary archive file.

    Example:
        >>> package = create_directory_archive("/mydir")
        >>> sid = start_transfer(package['archive_path'])
        >>> track_pending_archive(sid, package['archive_path'])
        ... # Transfer completes
        >>> path = pop_pending_archive(sid)
        >>> os.remove(path)

    Note:
        This function is NOT thread-safe. Callers must synchronize
        access if multiple threads create archives simultaneously.
    """
    _pending_archives[session_id] = archive_path


def pop_pending_archive(session_id: str) -> Optional[str]:
    """
    Retrieve and remove tracked archive path for cleanup.

    Removes the session from tracking and returns the associated
    temporary file path so it can be deleted. Safe to call even
    if session was never tracked.

    Args:
        session_id: File transfer session identifier.

    Returns:
        Optional[str]: Temporary archive path if session was tracked,
                      None otherwise.

    Example:
        >>> track_pending_archive("sid123", "/tmp/archive.tar.gz")
        >>> path = pop_pending_archive("sid123")
        >>> path
        '/tmp/archive.tar.gz'
        >>> pop_pending_archive("sid123")  # Already removed
        None

    Typical Usage:
        >>> # In transfer completion callback:
        >>> archive_path = pop_pending_archive(session_id)
        >>> if archive_path:
        ...     try:
        ...         os.remove(archive_path)
        ...     except OSError:
        ...         pass  # Ignore cleanup errors
    """
    return _pending_archives.pop(session_id, None)
