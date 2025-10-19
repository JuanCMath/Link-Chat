"""
peer_store.py
~~~~~~~~~~~~~

Persistence layer for discovered peer information.

This module provides interfaces and implementations for storing and retrieving
peer data across application restarts. The protocol-based design allows for
different storage backends (JSON, SQL, etc.) while maintaining a consistent API.

Architecture:
    - PeerStore: Protocol defining the storage interface
    - JSONPeerStore: JSON file-based implementation

Storage Format (JSON):
    {
      "aa:bb:cc:dd:ee:ff": {
        "mac": "aa:bb:cc:dd:ee:ff",
        "name": "Host1",
        "last_seen": "2025-10-13T14:30:00+00:00"
      },
      ...
    }

Thread Safety:
    Implementations are NOT thread-safe. Callers must synchronize access.
"""
import os
import json
from typing import Dict, Protocol
from .peer_models import Peer


class PeerStore(Protocol):
    """
    Protocol defining the interface for peer persistence.

    This protocol allows different storage backends to be used interchangeably.
    Implementations must provide methods for loading, saving, and resetting
    the peer database.

    Methods:
        load: Retrieve all stored peers
        save: Persist current peer set
        reset: Clear all stored data
    """

    def load(self) -> Dict[str, Peer]:
        """
        Load all peers from persistent storage.

        Returns:
            Dict[str, Peer]: Dictionary mapping MAC addresses to Peer objects.
                            Returns empty dict if storage is empty or doesn't exist.
        """
        ...

    def save(self, peers: Dict[str, Peer]) -> None:
        """
        Save peer dictionary to persistent storage.

        Args:
            peers: Dictionary mapping MAC addresses to Peer objects.

        Note:
            This operation should be atomic where possible to prevent corruption.
        """
        ...

    def reset(self) -> None:
        """
        Delete all stored peer data.

        This operation is idempotent; calling on empty storage is safe.
        """
        ...


class JSONPeerStore:
    """
    JSON file-based implementation of PeerStore.

    Stores peers in a human-readable JSON file with automatic directory creation
    and graceful handling of missing files. The JSON format maintains MAC addresses
    both as keys and within each peer object for redundancy.

    File Format:
        Pretty-printed JSON with 2-space indentation and UTF-8 encoding.
        MAC addresses are used as top-level keys for efficient lookup.

    Attributes:
        path: Absolute path to the JSON file.
        directory: Parent directory of the JSON file.

    Example:
        >>> store = JSONPeerStore("/data/peers.json")
        >>> peers = store.load()
        >>> peers["aa:bb:cc:dd:ee:ff"] = Peer(mac="aa:bb:cc:dd:ee:ff", name="Host1")
        >>> store.save(peers)
    """

    def __init__(self, path: str = "/data/peers.json") -> None:
        """
        Initialize JSON peer store with file path.

        Args:
            path: Absolute path to JSON file. Parent directory will be created
                  automatically on first save.

        Note:
            The file doesn't need to exist; load() returns empty dict if missing.
        """
        self.path = path
        self.directory = os.path.dirname(path) or "."

        # Creates dir if doesn't esxist
        os.makedirs(self.directory, exist_ok=True)

    def load(self) -> Dict[str, Peer]:
        """
        Load peers from JSON file.

        Reads the JSON file and deserializes each entry into a Peer object.
        Missing files are treated as empty peer sets.

        Returns:
            Dict[str, Peer]: Peer dictionary keyed by MAC address.

        Raises:
            JSONDecodeError: If file exists but contains invalid JSON.
            KeyError: If any peer entry is missing required 'mac' field.

        Example:
            >>> store = JSONPeerStore("/data/peers.json")
            >>> peers = store.load()
            >>> len(peers)
            5
        """
        # Return empty dict if file doesn't exist yet
        if not os.path.exists(self.path):
            return {}

        with open(self.path, "r", encoding="utf-8") as file:
            raw_data = json.load(file)

        # Deserialize each peer entry
        peers: Dict[str, Peer] = {}
        for mac_address, peer_data in raw_data.items():
            # Ensure MAC is present in data (redundant but safe)
            peer_data["mac"] = mac_address
            peers[mac_address] = Peer.from_dict(peer_data)

        return peers

    def save(self, peers: Dict[str, Peer]) -> None:
        """
        Save peer dictionary to JSON file.

        Serializes all peers to JSON with pretty formatting. Creates parent
        directory if it doesn't exist. The MAC address is stored both as the
        dictionary key and within each peer object for redundancy.

        Args:
            peers: Peer dictionary to persist.

        Raises:
            OSError: If directory creation or file writing fails.

        Example:
            >>> peers = {
            ...     "aa:bb:cc:dd:ee:ff": Peer(mac="aa:bb:cc:dd:ee:ff", name="Host1")
            ... }
            >>> store.save(peers)
        """
        # Ensure directory exists
        os.makedirs(self.directory, exist_ok=True)

        # Convert peers to dictionaries
        data = {mac: peer.to_dict() for mac, peer in peers.items()}

        # Add MAC to each peer object for redundancy
        # (useful if entries are processed independently)
        for mac_address in data:
            data[mac_address]["mac"] = mac_address

        # Write with formatting for readability
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

    def reset(self) -> None:
        """
        Delete the JSON file, clearing all peer data.

        This operation is idempotent and safe to call even if the file
        doesn't exist. Errors during deletion are silently ignored.

        Example:
            >>> store = JSONPeerStore("/data/peers.json")
            >>> store.reset()  # File deleted
            >>> store.reset()  # Safe to call again
        """
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except OSError:
            # Silently ignore deletion errors (file may be locked, etc.)
            pass
