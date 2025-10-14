"""
peer_discovery.py
~~~~~~~~~~~~~~~~~

Automatic peer discovery via periodic beacon broadcasts.

This module implements a decentralized peer discovery protocol where each host
periodically broadcasts its identity to the local network segment. The discovery
service integrates with the PeerRegistry to maintain an up-to-date table of all
discovered hosts with automatic timestamp updates.

Discovery Protocol:
    - Each host broadcasts "BEACON|<name>" every N seconds
    - Receiving hosts register/update the sender in their peer table
    - MAC addresses serve as unique peer identifiers
    - Names are opportunistically learned from beacons and chat messages

Components:
    - PeerDiscovery: Beacon broadcast service with incoming frame integration
    - BEACON_PREFIX: Constant for beacon message format ("BEACON|")

Thread Safety:
    Discovery runs in a dedicated background daemon thread. All registry
    operations are delegated to PeerRegistry which provides thread-safe access.

Example:
    >>> from app.backend.peer_management.peer_registry import PeerRegistry
    >>> from app.backend.peer_management.peer_store import JSONPeerStore
    >>> 
    >>> store = JSONPeerStore("/data/peers.json")
    >>> registry = PeerRegistry(store)
    >>> discovery = PeerDiscovery(mgr=thread_manager, name="MyHost", registry=registry)
    >>> discovery.start()
    ... # Beacons broadcast automatically
    >>> discovery.stop()
"""
import threading
import re
from typing import Optional, Callable

from ..utils.mac_utils import mac_bytes_to_str
from .peer_models import Peer
from .peer_registry import PeerRegistry

# Prefix for beacon broadcast messages
BEACON_PREFIX = "BEACON|"

# Regex pattern for validating MAC address format (case-insensitive)
MAC_ADDRESS_PATTERN = re.compile(r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$")



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
