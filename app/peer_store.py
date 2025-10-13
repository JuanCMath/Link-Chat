# peer_store.py
from __future__ import annotations
import os, json
from typing import Dict, Iterable, Protocol
from peer_models import Peer

class PeerStore(Protocol):
    def load(self) -> Dict[str, Peer]: ...
    def save(self, peers: Dict[str, Peer]) -> None: ...
    def reset(self) -> None: ...

class JSONPeerStore:
    """Persistencia a un JSON plano."""
    def __init__(self, path: str = "/data/peers.json") -> None:
        self.path = path
        self.dir = os.path.dirname(path) or "."

    def load(self) -> Dict[str, Peer]:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        out: Dict[str, Peer] = {}
        for mac, info in raw.items():
            info["mac"] = mac
            out[mac] = Peer.from_dict(info)
        return out

    def save(self, peers: Dict[str, Peer]) -> None:
        os.makedirs(self.dir, exist_ok=True)
        data = {mac: p.to_dict() for mac, p in peers.items()}
        # redundante pero útil: dejamos la MAC como clave y en el objeto
        for mac in data:
            data[mac]["mac"] = mac
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def reset(self) -> None:
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except OSError:
            pass
