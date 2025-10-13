# peer_discovery.py
from __future__ import annotations
import threading, time, re
from datetime import datetime, timezone
from typing import Dict, Optional, Callable, Iterable, List

from service_threads import mac_bytes_to_str
from peer_models import Peer
from peer_store import PeerStore

BEACON_PREFIX = "BEACON|"
MAC_RE = re.compile(r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$")

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class PeerRegistry:
    """Tabla thread-safe + utilidades de consulta y resolución."""
    def __init__(self, store: PeerStore):
        self._lock = threading.Lock()
        self._peers: Dict[str, Peer] = {}
        self._store = store

    # CRUD
    def upsert(self, mac: str, name: Optional[str] = None) -> Peer:
        mac = mac.lower()
        with self._lock:
            p = self._peers.get(mac) or Peer(mac=mac)
            if name is not None and name != "":
                p.name = name
            p.last_seen = now_iso()
            self._peers[mac] = p
            self._store.save(self._peers)
            return p

    def list(self) -> List[Peer]:
        with self._lock:
            return sorted(self._peers.values(), key=lambda p: p.mac)

    def get(self, mac: str) -> Optional[Peer]:
        with self._lock:
            return self._peers.get(mac.lower())

    def reset(self) -> None:
        with self._lock:
            self._peers.clear()
        self._store.reset()

    # Resolución
    def resolve(self, token: str) -> Optional[str]:
        """Devuelve MAC por token (MAC exacta o nombre exacto case-insensitive).
           Si hay varios con el mismo nombre -> None (ambigüedad).
        """
        t = token.strip()
        if MAC_RE.match(t):
            return t.lower()
        t_lc = t.lower()
        with self._lock:
            matches = [p.mac for p in self._peers.values() if p.name and p.name.lower() == t_lc]
        if len(matches) == 1:
            return matches[0]
        return None

    def matches_for_name(self, name: str) -> List[Peer]:
        name_lc = name.strip().lower()
        with self._lock:
            return [p for p in self._peers.values() if p.name and p.name.lower() == name_lc]

    # Persistencia
    def load(self) -> int:
        loaded = self._store.load()
        with self._lock:
            self._peers = loaded
        return len(self._peers)

class PeerDiscovery:
    """Beacon + integración con registro. No depende de tu CLI."""
    def __init__(
        self,
        mgr,                      # objeto con send_broadcast_payload(bytes)
        name: str,
        registry: PeerRegistry,
        interval: float = 5.0,
        on_beacon: Optional[Callable[[Peer], None]] = None,
    ) -> None:
        self.mgr = mgr
        self.name = name
        self.reg = registry
        self.interval = interval
        self._on_beacon = on_beacon

        self._stop = threading.Event()
        self._thr: Optional[threading.Thread] = None

    # ciclo de vida
    def start(self) -> None:
        if self._thr and self._thr.is_alive():
            return
        self._stop.clear()
        self._thr = threading.Thread(target=self._loop, name="discovery", daemon=True)
        self._thr.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thr and self._thr.is_alive():
            self._thr.join(timeout=1.0)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.send_beacon()
            except Exception:
                pass
            self._stop.wait(self.interval)

    def send_beacon(self) -> None:
        self.mgr.send_broadcast_payload(f"{BEACON_PREFIX}{self.name}".encode())

    # integrar con on_frame
    def handle_incoming(self, src_mac_bytes: bytes, text: str) -> None:
        mac = mac_bytes_to_str(src_mac_bytes)
        if text.startswith(BEACON_PREFIX):
            nm = text.split("|", 1)[1].strip()[:64]
            p = self.reg.upsert(mac, nm)
            if self._on_beacon:
                try:
                    self._on_beacon(p)
                except Exception:
                    pass
            return
        # aprendizaje opcional por formato "NAME: msg"
        if ":" in text:
            nm = text.split(":", 1)[0].strip()[:64]
            if nm:
                self.reg.upsert(mac, nm)
