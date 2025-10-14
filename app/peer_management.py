"""
peer_management.py
~~~~~~~~~~~~~~~~~

Automatic peer discovery and tracking via periodic beacon broadcasts.

This module implements a decentralized peer discovery protocol where each host
periodically broadcasts its identity to the local network segment. Peers maintain
a registry of all discovered hosts with automatic timestamp updates.

Discovery Protocol:
    - Each host broadcasts "BEACON|<name>" every N seconds
    - Receiving hosts register/update the sender in their peer table
    - MAC addresses serve as unique peer identifiers
    - Names are opportunistically learned from beacons and chat messages

Architecture:
    - PeerRegistry: Thread-safe in-memory peer table with persistence
    - PeerDiscovery: Beacon broadcast service with incoming frame integration

Thread Safety:
    All registry operations are protected by locks. Discovery runs in
    dedicated background thread.

Example:
    >>> registry = PeerRegistry(JSONPeerStore("/data/peers.json"))
    >>> discovery = PeerDiscovery(mgr=thread_manager, name="MyHost", registry=registry)
    >>> discovery.start()
    ... # Beacons broadcast automatically
    >>> discovery.stop()
"""
import threading
import re
from datetime import datetime, timezone
from typing import Dict, Optional, Callable, List

from .service_threads import mac_bytes_to_str
from .peer_models import Peer
from .peer_store import PeerStore
# Prefix for beacon broadcast messages
BEACON_PREFIX = "BEACON|"

# Regex pattern for validating MAC address format (case-insensitive)
MAC_ADDRESS_PATTERN = re.compile(r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$")


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

    def __init__(self, store: PeerStore) -> None:
        """
        Initialize registry with persistent storage backend.

        Args:
            store: PeerStore implementation for persistence.
        """
        self._lock = threading.Lock()
        self._peers: Dict[str, Peer] = {}
        self._store = store

    # CRUD Operations -------------------------------------------------------

    def upsert(self, mac: str, name: Optional[str] = None) -> Peer:
        """
        Insert or update a peer in the registry.

        Creates a new peer if MAC doesn't exist, otherwise updates the existing
        peer. Always updates last_seen timestamp. Automatically persists changes.

        Args:
            mac: MAC address of the peer (will be normalized to lowercase).
            name: Optional human-readable name. If provided and non-empty,
                  updates the peer's name. Empty string or None leaves name unchanged.

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
            self._store.save(self._peers)

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

    def remove_peer(self, mac: str) -> bool:
        """Remove peer from storage

        Args:
            mac (str): Peer's MAC address

        Returns:
            bool: The peer was removed (True) or didn't exist (False)
        """
        with self._lock:
            if mac.lower() in self._peers:
                self._peers.pop(mac.lower())
                self._store.save(self._peers)
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


class PeerDiscovery:
    """
    Periodic beacon broadcaster for automatic peer discovery.

    This class runs a background thread that periodically broadcasts the local
    host's identity to the network. It also integrates with incoming frame
    processing to detect beacons from remote peers and update the registry.

    Beacon Format:
        "BEACON|<hostname>"
        Example: "BEACON|Alice-Laptop"

    Opportunistic Learning:
        In addition to beacons, peer names are learned from chat messages
        with the format "NAME: message". This allows discovering peers even
        if their beacon thread hasn't run yet.

    Attributes:
        manager: ThreadManager instance with send_broadcast_payload() method.
        local_name: This host's identifier to broadcast.
        registry: PeerRegistry for tracking discovered peers.
        broadcast_interval: Seconds between beacon transmissions.

    Example:
        >>> registry = PeerRegistry(store)
        >>> discovery = PeerDiscovery(
        ...     mgr=thread_manager,
        ...     name="MyHost",
        ...     registry=registry,
        ...     interval=5.0
        ... )
        >>> discovery.start()
        ... # Broadcasts "BEACON|MyHost" every 5 seconds
        >>> discovery.stop()
    """

    def __init__(
        self,
        mgr,  # ThreadManager with send_broadcast_payload(bytes) method
        name: str,
        registry: PeerRegistry,
        interval: float = 5.0,
        on_beacon: Optional[Callable[[Peer], None]] = None,
    ) -> None:
        """
        Initialize discovery service with broadcast parameters.

        Args:
            mgr: ThreadManager instance for sending broadcast frames.
            name: Local host identifier to broadcast (max 64 chars recommended).
            registry: PeerRegistry for storing discovered peers.
            interval: Seconds between beacon broadcasts (default: 5.0).
            on_beacon: Optional callback invoked when beacon received from peer.
                      Signature: (peer: Peer) -> None

        Example:
            >>> def on_peer_found(peer: Peer):
            ...     print(f"Discovered: {peer.name} ({peer.mac})")
            >>> discovery = PeerDiscovery(mgr, "Host1", registry, on_beacon=on_peer_found)
        """
        self.manager = mgr
        self.local_name = name
        self.registry = registry
        self.broadcast_interval = interval
        self._beacon_callback = on_beacon

        self._stop_event = threading.Event()
        self._broadcast_thread: Optional[threading.Thread] = None

    # Lifecycle -------------------------------------------------------------

    def start(self) -> None:
        """
        Start the beacon broadcast thread.

        Begins periodic broadcast of local identity. Safe to call multiple
        times; subsequent calls are no-ops if already running.

        Example:
            >>> discovery.start()
            >>> # Beacons now broadcasting every 5 seconds
        """
        if self._broadcast_thread and self._broadcast_thread.is_alive():
            return  # Already running

        self._stop_event.clear()
        self._broadcast_thread = threading.Thread(
            target=self._broadcast_loop, name="discovery", daemon=True
        )
        self._broadcast_thread.start()

    def stop(self) -> None:
        """
        Stop the beacon broadcast thread.

        Signals the thread to stop and waits up to 1 second for termination.
        Safe to call even if not running.

        Example:
            >>> discovery.stop()
            >>> # No more beacons transmitted
        """
        self._stop_event.set()
        if self._broadcast_thread and self._broadcast_thread.is_alive():
            self._broadcast_thread.join(timeout=1.0)

    def _broadcast_loop(self) -> None:
        """
        Background thread: broadcast beacon up to 5 times with 5-second intervals.

        Runs until stop_event is set or 5 broadcasts have been sent. Broadcasts 
        local identity and sleeps for 5 seconds between transmissions. Exceptions 
        during broadcast are silently ignored to keep the loop running.
        """
        broadcast_count = 0
        max_broadcasts = 5
        
        while not self._stop_event.is_set() and broadcast_count < max_broadcasts:
            try:
                self.send_beacon()
                broadcast_count += 1
            except Exception:
                # Silently ignore broadcast errors (network down, etc.)
                pass

            # Sleep for 5 seconds until next broadcast (or stop signal)
            if broadcast_count < max_broadcasts:
                self._stop_event.wait(self.broadcast_interval)

    def send_beacon(self) -> None:
        """
        Send a single beacon broadcast to the network.

        Constructs and broadcasts a message with format "BEACON|<local_name>".
        Can be called manually for immediate beacon transmission.

        Example:
            >>> discovery.send_beacon()  # Immediate broadcast
        """
        beacon_message = f"{BEACON_PREFIX}{self.local_name}".encode()
        self.manager.send_broadcast_payload(beacon_message)

    # Frame Integration -----------------------------------------------------

    def handle_incoming(self, src_mac_bytes: bytes, text: str) -> None:
        """
        Process incoming frame for peer discovery.

        Integrates with ThreadManager's on_frame callback. Detects beacon
        messages and chat messages to learn peer identities. Updates registry
        and invokes callbacks as appropriate.

        Discovery Logic:
            1. If message starts with "BEACON|", extract name and register peer
            2. If message contains ":", assume format "NAME: message" and
               opportunistically learn the name

        Args:
            src_mac_bytes: Source MAC address from Ethernet frame (6 bytes).
            text: Decoded payload text from the frame.

        Callback:
            If a beacon is detected and on_beacon callback is configured,
            it is invoked with the updated Peer object.

        Example:
            >>> # In ThreadManager callback:
            >>> def on_frame(dst, src, payload):
            ...     text = payload.decode('utf-8', errors='ignore')
            ...     discovery.handle_incoming(src, text)

        Note:
            Name learning is opportunistic and best-effort. Names are
            truncated to 64 characters to prevent abuse.
        """
        mac_address = mac_bytes_to_str(src_mac_bytes)

        # Handle explicit beacon messages
        if text.startswith(BEACON_PREFIX):
            # Extract name after "BEACON|" prefix
            name = text.split("|", 1)[1].strip()[:64]  # Limit to 64 chars

            # Register/update peer
            peer = self.registry.upsert(mac_address, name)

            # Invoke callback if configured
            if self._beacon_callback:
                try:
                    self._beacon_callback(peer)
                except Exception:
                    # Don't let callback errors break discovery
                    pass

            return

        # Opportunistic name learning from chat messages
        # Format: "NAME: message content"
        if ":" in text:
            potential_name = text.split(":", 1)[0].strip()[:64]

            # Only register if name is non-empty
            if potential_name:
                self.registry.upsert(mac_address, potential_name)
