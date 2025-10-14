"""
Peer Management Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Peer discovery, tracking, and persistence modules.

This package handles all aspects of peer management in the LinkChat network,
including automatic discovery via beacons, thread-safe in-memory registry,
and JSON-based persistence.

Modules:
    peer_models: Dataclass definitions for Peer objects
    peer_store: Persistence layer with Protocol pattern (JSON implementation)
    peer_registry: Thread-safe in-memory peer database with MAC/name resolution
    peer_discovery: Automatic beacon-based peer discovery service

Features:
    - Automatic peer discovery via periodic "BEACON|<name>" broadcasts
    - Thread-safe registry operations with locks
    - MAC address and name-based peer lookups
    - Opportunistic name learning from chat messages
    - JSON persistence with atomic updates
    - Duplicate name detection

Example:
    >>> from app.backend.peer_management.peer_store import JSONPeerStore
    >>> from app.backend.peer_management.peer_registry import PeerRegistry
    >>> from app.backend.peer_management.peer_discovery import PeerDiscovery
    >>> 
    >>> store = JSONPeerStore("/data/peers.json")
    >>> registry = PeerRegistry(store)
    >>> discovery = PeerDiscovery(mgr, "MyHost", registry, interval=5.0)
    >>> discovery.start()
"""
