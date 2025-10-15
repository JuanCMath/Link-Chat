"""
peer_registry.py
~~~~~~~~~~~~~~~~

Thread-safe in-memory registry for discovered peers.

This module provides the PeerRegistry class, which maintains a synchronized
in-memory database of all discovered peers with automatic persistence to
disk storage. It supports both MAC address and name-based lookups.

Key Features:
    - Thread-safe operations with internal locking
    - Automatic JSON persistence on every update
    - MAC address and name-based peer resolution
    - Duplicate name detection (ambiguity handling)
    - Peer removal and cleanup operations

Example:
    >>> from app.backend.peer_management.peer_store import JSONPeerStore
    >>> store = JSONPeerStore("/data/peers.json")
    >>> registry = PeerRegistry(store)
    >>> 
    >>> # Add/update peer
    >>> peer = registry.upsert("aa:bb:cc:dd:ee:ff", "Server1")
    >>> 
    >>> # Resolve by name
    >>> mac = registry.resolve("Server1")
    >>> print(mac)  # 'aa:bb:cc:dd:ee:ff'
"""

import threading
import re
from datetime import datetime, timezone
from time import sleep
from typing import Dict, Optional, List

from .peer_models import Peer
from .peer_store import PeerStore
from ..utils.mac_utils import MAC_ADDRESS_PATTERN


# Time Interval for checking for possible peers to prune
PRUNING_INTERVAL = 15.0


def get_current_utc_timestamp() -> str:
    """
    Get current UTC timestamp in ISO-8601 format.

    Returns:
        str: ISO-8601 timestamp with timezone info (e.g., "2025-10-13T14:30:00.123456+00:00").

    Example:
        >>> timestamp = get_current_utc_timestamp()
        >>> '2025' in timestamp
        True
    """
    return datetime.now(timezone.utc).isoformat()


class PeerRegistry:
    """
    Thread-safe registry for discovered peers with resolution and persistence.

    This class maintains an in-memory table of all discovered peers, synchronized
    to persistent storage on every update. It provides atomic operations for peer
    management and supports both MAC address and name-based lookups.

    Key Features:
        - Thread-safe access via internal locking
        - Automatic persistence on updates
        - MAC and name-based peer resolution
        - Ambiguity detection for duplicate names

    Attributes:
        _lock: Threading lock protecting all registry operations.
        _peers: In-memory dictionary mapping MAC -> Peer.
        _store: Persistent storage backend.

    Example:
        >>> store = JSONPeerStore("/data/peers.json")
        >>> registry = PeerRegistry(store)
        >>> peer = registry.upsert("aa:bb:cc:dd:ee:ff", "Host1")
        >>> registry.resolve("Host1")
        'aa:bb:cc:dd:ee:ff'
    """

    def __init__(self, store: PeerStore, max_age: float) -> None:
        """
        Initialize registry with persistent storage backend.

        Args:
            store: PeerStore implementation for persistence.
        """
        self._lock = threading.Lock()
        self._peers: Dict[str, Peer] = {}
        self._store = store
        self._max_age = max_age
        self._pruner : Optional[threading.Thread] = threading.Thread(target=self._prune_stale, name="pruner", daemon=True)
        self._pruner.start()
        self._stop_pruner = threading.Event()
        self._stop_pruner.clear()

    def close(self) -> None:
        self._stop_pruner.set()
        if self._pruner: 
            self._pruner.join(timeout=1.0)
            self._pruner = None
        self._peers.clear()

    # CRUD Operations -------------------------------------------------------

    def upsert(self, mac: str, name: Optional[str] = None, save: bool = True) -> Peer:
        """
        Insert or update a peer in the registry.

        Creates a new peer if MAC doesn't exist, otherwise updates the existing
        peer. Always updates last_seen timestamp. Automatically persists changes.

        Args:
            mac: MAC address of the peer (will be normalized to lowercase).
            name: Optional human-readable name. If provided and non-empty,
                  updates the peer's name. Empty string or None leaves name unchanged.
            save: Make operation persistent

        Returns:
            Peer: The created or updated peer object.

        Thread Safety:
            Atomic operation protected by internal lock.

        Example:
            >>> registry = PeerRegistry(store)
            >>> peer = registry.upsert("AA:BB:CC:DD:EE:FF", "Server1")
            >>> peer.mac
            'aa:bb:cc:dd:ee:ff'
        """
        mac = mac.lower()  # Normalize to lowercase for consistency

        with self._lock:
            # Get existing peer or create new one
            peer = self._peers.get(mac) or Peer(mac=mac)

            # Update name if provided and non-empty
            if name is not None and name != "":
                peer.name = name

            # Always update last seen timestamp
            peer.last_seen = get_current_utc_timestamp()

            # Store in registry
            self._peers[mac] = peer

            # Persist to storage
            if save: self._store.save(self._peers)

            return peer

    def list(self) -> List[Peer]:
        """
        Get sorted list of all known peers.

        Returns:
            List[Peer]: Peers sorted by MAC address (lowercase).

        Thread Safety:
            Returns a snapshot; modifications won't affect registry.

        Example:
            >>> peers = registry.list()
            >>> for peer in peers:
            ...     print(f"{peer.name} ({peer.mac})")
        """
        with self._lock:
            return sorted(self._peers.values(), key=lambda p: p.mac)

    def get(self, mac: str) -> Optional[Peer]:
        """
        Retrieve a specific peer by MAC address.

        Args:
            mac: MAC address to look up (case-insensitive).

        Returns:
            Optional[Peer]: The peer if found, None otherwise.

        Example:
            >>> peer = registry.get("aa:bb:cc:dd:ee:ff")
            >>> if peer:
            ...     print(peer.name)
        """
        with self._lock:
            return self._peers.get(mac.lower())

    def reset(self) -> None:
        """
        Clear all peers from registry and persistent storage.

        This operation is atomic and irreversible.

        Thread Safety:
            Protected by internal lock.

        Example:
            >>> registry.reset()
            >>> registry.list()
            []
        """
        with self._lock:
            self._peers.clear()
        self._store.reset()

    def remove_peer(self, mac: str, save: bool = True) -> bool:
        """Remove peer from storage

        Args:
            mac (str): Peer's MAC address
            save (bool): Make operation persistent

        Returns:
            bool: The peer was removed (True) or didn't exist (False)
        """
        with self._lock:
            if mac.lower() in self._peers:
                self._peers.pop(mac.lower())
                if save: self._store.save(self._peers)
                return True
        
        return False



    # Resolution ------------------------------------------------------------

    def resolve(self, token: str) -> Optional[str]:
        """
        Resolve a token to a MAC address.

        Supports two resolution modes:
        1. MAC address: Returns normalized MAC if format is valid
        2. Name: Returns MAC if exactly one peer has this name (case-insensitive)

        Args:
            token: Either a MAC address or peer name.

        Returns:
            Optional[str]: MAC address if resolution succeeds, None if:
                - Token is a name but no peer found
                - Token is a name and multiple peers match (ambiguous)
                - Token is invalid format

        Example:
            >>> registry.resolve("aa:bb:cc:dd:ee:ff")
            'aa:bb:cc:dd:ee:ff'
            >>> registry.resolve("Server1")  # If unique
            'aa:bb:cc:dd:ee:ff'
            >>> registry.resolve("Server1")  # If duplicate
            None  # Ambiguous
        """
        token = token.strip()

        # Check if token is a MAC address
        if MAC_ADDRESS_PATTERN.match(token):
            return token.lower()

        # Otherwise, try name-based lookup
        token_lower = token.lower()
        with self._lock:
            matches = [
                peer.mac
                for peer in self._peers.values()
                if peer.name and peer.name.lower() == token_lower
            ]

        # Return MAC only if exactly one match (unambiguous)
        if len(matches) == 1:
            return matches[0]

        return None  # No match or ambiguous

    def find_by_name(self, name: str) -> List[Peer]:
        """
        Find all peers with a given name (case-insensitive).

        Useful for detecting name collisions or listing all matches
        before resolution.

        Args:
            name: Peer name to search for.

        Returns:
            List[Peer]: All peers with matching name (may be empty or multiple).

        Example:
            >>> matches = registry.find_by_name("Server")
            >>> if len(matches) > 1:
            ...     print("Warning: Name collision detected!")
        """
        name_lower = name.strip().lower()
        with self._lock:
            return [
                peer
                for peer in self._peers.values()
                if peer.name and peer.name.lower() == name_lower
            ]

    # Persistence -----------------------------------------------------------

    def load(self) -> int:
        """
        Load peers from persistent storage into registry.

        Replaces the current in-memory registry with stored data.
        Useful during application startup.

        Returns:
            int: Number of peers loaded.

        Thread Safety:
            Protected by internal lock.

        Example:
            >>> count = registry.load()
            >>> print(f"Loaded {count} peers from storage")
        """
        loaded_peers = self._store.load()
        with self._lock:
            self._peers = loaded_peers
        return len(self._peers)
    
    def _prune_stale(self) -> None:


        while not self._stop_pruner.is_set():
                       
            with self._lock:
                # Peers discovered
                if len(self._peers)>=0:
                    start_time = datetime.now()
                    initial_len = len(self._peers)

                    for peer in self._peers.values():
                        delta = start_time - datetime.fromisoformat(peer.last_seen)
                        if(delta.total_seconds() >= self._max_age):
                            self.remove_peer(peer.mac, save = False)

                    if(initial_len > len(self._peers)): 
                        self._store.save(self._peers)
                    
            sleep(PRUNING_INTERVAL)


        
