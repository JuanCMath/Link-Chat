# peer_models.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict

@dataclass
class Peer:
    mac: str           # "aa:bb:cc:dd:ee:ff"
    name: str = ""     # opcional
    last_seen: str = ""  # ISO-8601 UTC

    def to_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict) -> "Peer":
        return Peer(mac=d["mac"], name=d.get("name", ""), last_seen=d.get("last_seen", ""))
