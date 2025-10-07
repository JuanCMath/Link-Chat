"""Peer discovery service for Link-Chat.

Provides automatic neighbor detection on a shared Ethernet segment using periodic
beacon broadcasts. Each node advertises its identity, display name, available services,
and arbitrary metadata. Peers that stop sending beacons are automatically pruned after
a configurable expiry interval.

The discovery protocol uses a simple framing:
    MAGIC (3 bytes) | VERSION (1 byte) | JSON payload (variable)

Beacons are broadcast at regular intervals and received asynchronously in dedicated
worker threads. Callbacks notify the application layer when peers appear or disappear.
"""

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from .af_packet_medium_eth_wifi import AFPacketMediumEthWifi

# Protocol constants
MAGIC = b"LCD"  # Link-Chat Discovery magic header
VERSION = 1  # Protocol version for future compatibility
BROADCAST_MAC = b"\xff" * 6  # IEEE 802.3 broadcast address


def _now() -> float:
    """Return current monotonic time for consistent interval tracking."""
    return time.monotonic()


@dataclass(slots=True)
class PeerInfo:
    """Snapshot of a discovered peer's advertised information.

    Attributes:
        mac: Hardware MAC address (6 bytes).
        node_id: Persistent node identifier (UUID hex string).
        name: Optional human-readable display name.
        last_seen: Monotonic timestamp of most recent beacon.
        services: Advertised service names (e.g., 'chat', 'file-transfer').
        metadata: Arbitrary key-value metadata for extended peer info.
    """
    mac: bytes
    node_id: str
    name: Optional[str]
    last_seen: float
    services: Set[str] = field(default_factory=set)
    metadata: Dict[str, str] = field(default_factory=dict)


class PeerDiscoveryService:
    """Automatic peer discovery and tracking service.

    Periodically broadcasts presence beacons and listens for beacons from other
    nodes on the same Ethernet segment. Maintains a live registry of discovered
    peers, invoking callbacks when peers appear or time out.

    Thread-safe and suitable for long-running background operation.
    """

    def __init__(
        self,
        interface: str,
        ethertype: int,
        identity: Optional[str] = None,
        display_name: Optional[str] = None,
        beacon_interval: float = 5.0,
        expiry_interval: float = 15.0,
        on_peer_available: Optional[Callable[[PeerInfo], None]] = None,
        on_peer_expired: Optional[Callable[[PeerInfo], None]] = None,
    ) -> None:
        """Initialize the peer discovery service.

        Args:
            interface: Network interface name (e.g., 'eth0', 'wlan0').
            ethertype: EtherType for discovery frames (should be distinct from data traffic).
            identity: Stable node identifier; auto-generated UUID hex if None.
            display_name: Human-friendly name to advertise; None for anonymous.
            beacon_interval: Seconds between beacon transmissions.
            expiry_interval: Seconds of silence before a peer is considered gone.
            on_peer_available: Callback invoked when a new peer is first seen.
            on_peer_expired: Callback invoked when a peer times out.
        """
        self.interface = interface
        self.ethertype = ethertype
        self.identity = identity or uuid.uuid4().hex
        self.display_name = display_name
        self.beacon_interval = beacon_interval
        self.expiry_interval = expiry_interval
        self.on_peer_available = on_peer_available
        self.on_peer_expired = on_peer_expired
        self._metadata: Dict[str, str] = {}
        self._services: Set[str] = set()
        self._medium: Optional[AFPacketMediumEthWifi] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._tx_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._peers: Dict[bytes, PeerInfo] = {}
        self._last_broadcast = 0.0

    def add_service(self, name: str) -> None:
        """Advertise an additional service in future beacons.

        Args:
            name: Service identifier (e.g., 'chat', 'file-transfer').
        """
        with self._lock:
            self._services.add(name)

    def remove_service(self, name: str) -> None:
        """Stop advertising a service in future beacons.

        Args:
            name: Service identifier to remove.
        """
        with self._lock:
            self._services.discard(name)

    def set_metadata(self, key: str, value: str) -> None:
        """Set or update a metadata key-value pair advertised in beacons.

        Args:
            key: Metadata key.
            value: Metadata value.
        """
        with self._lock:
            self._metadata[key] = value

    def clear_metadata(self, key: str) -> None:
        """Remove a metadata key from future beacon advertisements.

        Args:
            key: Metadata key to remove.
        """
        with self._lock:
            self._metadata.pop(key, None)

    def list_peers(self) -> List[PeerInfo]:
        """Return a snapshot of all currently known peers.

        Returns:
            List of PeerInfo objects; safe to use outside the lock.
        """
        with self._lock:
            return [PeerInfo(**vars(peer)) for peer in self._peers.values()]

    def start(self) -> None:
        """Start the discovery service.

        Spawns background threads for beacon transmission and reception. Idempotent
        if already running.
        """
        if self._medium is not None:
            return
        self._stop.clear()
        # Create raw packet medium in promiscuous mode to see all discovery traffic
        self._medium = AFPacketMediumEthWifi(
            iface=self.interface,
            ethertype=self.ethertype,
            filter_ethertype=True,
            enable_promiscuous=True,
        )
        # Launch sender and receiver worker threads
        self._tx_thread = threading.Thread(target=self._beacon_loop, daemon=True)
        self._rx_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._tx_thread.start()
        self._rx_thread.start()

    def stop(self) -> None:
        """Stop the discovery service and release resources.

        Signals worker threads to exit, closes the medium, and fires expiry callbacks
        for all remaining peers.
        """
        self._stop.set()
        # Wait for worker threads to terminate
        if self._tx_thread:
            self._tx_thread.join(timeout=1.5)
            self._tx_thread = None
        if self._rx_thread:
            self._rx_thread.join(timeout=1.5)
            self._rx_thread = None
        # Close the medium and clear peer table
        medium, self._medium = self._medium, None
        if medium:
            medium.close()
        with self._lock:
            expired = list(self._peers.values())
            self._peers.clear()
        # Notify application that all peers are now gone
        if self.on_peer_expired:
            for peer in expired:
                self.on_peer_expired(peer)

    def _build_payload(self) -> bytes:
        """Construct a complete beacon frame with header and JSON body.

        Returns:
            Framed payload: MAGIC | VERSION | JSON
        """
        with self._lock:
            payload = {
                "id": self.identity,
                "name": self.display_name,
                "ts": time.time(),  # Wall-clock time for diagnostics
                "services": sorted(self._services),
                "meta": dict(self._metadata),
            }
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return MAGIC + bytes([VERSION]) + body

    def _beacon_loop(self) -> None:
        """Worker thread: periodically send beacons and prune stale peers."""
        while not self._stop.is_set():
            start = _now()
            self._send_beacon()
            self._prune()
            # Adaptive delay to maintain consistent beacon interval
            elapsed = _now() - start
            delay = max(0.1, self.beacon_interval - elapsed)
            self._stop.wait(delay)

    def _send_beacon(self) -> None:
        """Broadcast a single presence beacon to all nodes on the link."""
        medium = self._medium
        if medium is None:
            return
        payload = self._build_payload()
        try:
            medium.send(BROADCAST_MAC, payload)
            self._last_broadcast = _now()
        except OSError:
            pass  # Ignore transient send failures

    def _receive_loop(self) -> None:
        """Worker thread: receive and decode beacon frames from other peers."""
        while not self._stop.is_set():
            medium = self._medium
            if medium is None:
                break
            try:
                packet = medium.recv_once(timeout=0.5)
            except OSError:
                continue
            if packet is None:
                continue
            dst, src, _, payload = packet
            # Ignore our own beacons
            if src == medium.src_mac:
                continue
            # Validate protocol framing
            if not payload.startswith(MAGIC) or len(payload) <= len(MAGIC):
                continue
            version = payload[len(MAGIC)]
            if version != VERSION:
                continue
            # Decode JSON payload
            body = payload[len(MAGIC) + 1 :]
            try:
                decoded = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if not isinstance(decoded, dict) or "id" not in decoded:
                continue
            # Update peer registry
            self._update_peer(src, decoded)

    def _update_peer(self, mac: bytes, payload: Dict[str, object]) -> None:
        """Update or create a peer entry from a received beacon.

        Args:
            mac: Source MAC address of the beacon.
            payload: Decoded JSON payload.
        """
        now = _now()
        identity = str(payload.get("id", ""))
        name = payload.get("name")
        services = payload.get("services")
        meta = payload.get("meta")
        if not identity:
            return  # Reject beacons without a valid node ID
        if not isinstance(services, (list, tuple)):
            services = []
        if not isinstance(meta, dict):
            meta = {}
        with self._lock:
            peer = self._peers.get(mac)
            first_seen = peer is None
            if peer is None:
                peer = PeerInfo(mac=mac, node_id=identity, name=None, last_seen=now)
                self._peers[mac] = peer
            # Update peer record with latest advertised info
            peer.node_id = identity
            peer.name = str(name) if name is not None else None
            peer.services = {str(s) for s in services}
            peer.metadata = {str(k): str(v) for k, v in meta.items()}
            peer.last_seen = now
        # Fire callback only on first appearance
        if first_seen and self.on_peer_available:
            self.on_peer_available(peer)

    def _prune(self) -> None:
        """Remove peers that have not sent a beacon within the expiry interval."""
        cutoff = _now() - self.expiry_interval
        expired: List[PeerInfo] = []
        with self._lock:
            for mac in list(self._peers.keys()):
                peer = self._peers[mac]
                if peer.last_seen < cutoff:
                    expired.append(peer)
                    self._peers.pop(mac, None)
        # Notify application about each expired peer
        if self.on_peer_expired:
            for peer in expired:
                self.on_peer_expired(peer)

    def summary(self) -> List[Tuple[str, str, float]]:
        """Return a lightweight summary of known peers sorted by recency.

        Returns:
            List of (node_id, name, last_seen) tuples, most recent first.
        """
        with self._lock:
            return [
                (peer.node_id, peer.name or "", peer.last_seen)
                for peer in sorted(self._peers.values(), key=lambda p: p.last_seen, reverse=True)
            ]
