"""
peer_models.py
~~~~~~~~~~~~~~

Data models for peer discovery and tracking.

This module defines the core data structures used throughout the LinkChat
peer discovery system. Peers represent remote hosts discovered on the local
network segment via beacon broadcasts.

Key Concepts:
    - Each peer is uniquely identified by its MAC address
    - Peers may have human-readable names
    - Last-seen timestamps enable stale peer detection

Serialization:
    The Peer class provides bidirectional JSON conversion for persistence.
"""
from dataclasses import dataclass, asdict
from typing import Dict


@dataclass
class Peer:
    """
    Represents a discovered network peer with identity and tracking metadata.

    Peers are discovered through periodic beacon broadcasts on the local network.
    Each peer is uniquely identified by its MAC address, which serves as the
    immutable key for all peer operations.

    Attributes:
        mac: MAC address in colon-separated lowercase format (e.g., "aa:bb:cc:dd:ee:ff").
             This is the primary identifier and must be unique per peer.

        name: Human-readable identifier provided by the peer (e.g., "Alice's Laptop").
              May be empty if peer hasn't broadcast a beacon yet. Names are not
              guaranteed to be unique across peers.

        last_seen: ISO-8601 UTC timestamp of the most recent interaction with this peer.
                   Format: "2025-10-13T14:30:00.123456+00:00"
                   Empty string indicates peer has never been seen.

    Example:
        >>> peer = Peer(
        ...     mac="08:00:27:4a:5b:6c",
        ...     name="DevServer",
        ...     last_seen="2025-10-13T14:30:00+00:00"
        ... )
        >>> data = peer.to_dict()
        >>> restored = Peer.from_dict(data)
    """

    mac: str
    name: str = ""
    last_seen: str = ""

    def to_dict(self) -> Dict:
        """
        Convert peer to dictionary for JSON serialization.

        Returns:
            Dict: Dictionary with keys 'mac', 'name', 'last_seen'.

        Example:
            >>> peer = Peer(mac="aa:bb:cc:dd:ee:ff", name="Host1")
            >>> peer.to_dict()
            {'mac': 'aa:bb:cc:dd:ee:ff', 'name': 'Host1', 'last_seen': ''}
        """
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict) -> "Peer":
        """
        Reconstruct peer from dictionary (deserialization).

        Args:
            data: Dictionary containing at minimum a 'mac' key.
                  'name' and 'last_seen' are optional (default to empty strings).

        Returns:
            Peer: New peer instance populated from dictionary.

        Raises:
            KeyError: If 'mac' key is missing from data.

        Example:
            >>> data = {'mac': 'aa:bb:cc:dd:ee:ff', 'name': 'Server'}
            >>> peer = Peer.from_dict(data)
            >>> peer.name
            'Server'
        """
        return Peer(
            mac=data["mac"],
            name=data.get("name", ""),
            last_seen=data.get("last_seen", ""),
        )
