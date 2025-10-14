"""Backend utility helpers for LinkChat."""

import os
import re
import tarfile
import tempfile
from typing import Dict, Optional

from ..peer_discovery import PeerRegistry

MAC_RE = re.compile(r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$")

_pending_archives: Dict[str, str] = {}


def resolve_mac(token: str, registry: PeerRegistry) -> Optional[str]:
    """Resolve a user token (MAC or name) into a normalized MAC string."""

    mac = registry.resolve(token)
    if mac:
        return mac
    if MAC_RE.match(token):
        return token.lower()
    return None


def create_directory_archive(dir_path: str) -> Optional[Dict[str, str]]:
    """Package a directory into a temporary .tar.gz archive."""

    dir_path = os.path.abspath(dir_path)

    if not os.path.isdir(dir_path):
        print(f"[senddir] directory does not exist: {dir_path}", flush=True)
        return None

    folder_name = os.path.basename(dir_path) or "folder"

    tmp_path = ""
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="linkchat-dir-", suffix=".tar.gz")
        os.close(fd)
        with tarfile.open(tmp_path, "w:gz") as archive:
            archive.add(dir_path, arcname=folder_name)
    except Exception as exc:
        print(f"[senddir] failed to package directory: {exc}", flush=True)
        try:
            if tmp_path:
                os.remove(tmp_path)
        except Exception:
            pass
        return None

    return {"archive_path": tmp_path, "folder_name": folder_name}


def track_pending_archive(sid: str, path: str) -> None:
    """Remember a temporary archive so it can be cleaned up on completion."""

    _pending_archives[sid] = path


def pop_pending_archive(sid: str) -> Optional[str]:
    """Retrieve and forget a tracked archive path for cleanup."""

    return _pending_archives.pop(sid, None)
