"""
linkchat.py
~~~~~~~~~~~

LinkChat - Raw Ethernet P2P chat with file transfer.

A peer-to-peer chat application over raw Ethernet frames featuring:
- Peer discovery via periodic beacons
- Unicast text messaging with ACK confirmation
- Reliable file transfer with automatic retries
- No IP/TCP required - works directly at layer 2

Environment Variables:
    IFACE: Network interface (default: eth0)
    ETHERTYPE: Custom EtherType (default: 0x88B5)
    NAME: Local peer name
    BEACON_INTERVAL: Seconds between discovery beacons
    PEERS_FILE: JSON file for persisting peer list
    INBOX_DIR: Directory for received files
    MSG_RETRY_INTERVAL: Seconds between message retries
    MSG_MAX_RETRIES: Maximum message retry attempts
    FILE_RETRY_INTERVAL: Seconds between chunk retries
    FILE_MAX_RETRIES: Maximum chunk retry attempts
"""
import logging
import os
import re
import sys
import time
import uuid
from typing import Dict, Optional

from raw_socket import SocketManager
from service_threads import ThreadManager, mac_bytes_to_str, mac_str_to_bytes

from peer_models import Peer
from peer_store import JSONPeerStore
from peer_discovery import PeerRegistry, PeerDiscovery

from ack_protocol import ACK_KIND_MSG, ACK_KIND_DATA, AckRetryManager
from file_transfer import FTv2

logging.basicConfig(level=logging.INFO, format="%(message)s")

# Configuration from environment
IFACE = os.environ.get("IFACE", "eth0")
ETHERTYPE = int(os.environ.get("ETHERTYPE", "0x88B5"), 0)
NAME = os.environ.get("NAME", "node")
BEACON_INTERVAL = float(os.environ.get("BEACON_INTERVAL", "5.0"))
PEERS_FILE = os.environ.get("PEERS_FILE", "/data/peers.json")
RESET_PEERS_ON_START = os.environ.get("RESET_PEERS_ON_START", "1") == "1"
INBOX_DIR = os.environ.get("INBOX_DIR", "/data/inbox")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "1300"))
MSG_RETRY_INTERVAL = float(os.environ.get("MSG_RETRY_INTERVAL", "3.0"))
MSG_MAX_RETRIES = int(os.environ.get("MSG_MAX_RETRIES", "3"))
FILE_RETRY_INTERVAL = float(
    os.environ.get("FILE_RETRY_INTERVAL", str(MSG_RETRY_INTERVAL))
)
FILE_MAX_RETRIES = int(os.environ.get("FILE_MAX_RETRIES", "3"))

# Global state
active_peer: Optional[bytes] = None
registry: PeerRegistry
discovery: PeerDiscovery
ft: FTv2
msg_ack_mgr: Optional[AckRetryManager] = None

MAC_RE = re.compile(r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$")


def resolve_mac(token: str) -> Optional[str]:
    """
    Resolve a token to a MAC address.

    Args:
        token: Either a MAC address string or a peer name.

    Returns:
        Optional[str]: MAC address in lowercase colon format, or None if not found.
    """
    mac = registry.resolve(token)
    if mac:
        return mac
    if MAC_RE.match(token):
        return token.lower()
    return None


def on_frame(dst: bytes, src: bytes, payload: bytes) -> None:
    """
    Handle incoming Ethernet frames.

    Routes frames to file transfer, peer discovery, or chat message handlers.

    Args:
        dst: Destination MAC address.
        src: Source MAC address.
        payload: Frame payload bytes.
    """
    # 1) Try file-transfer protocol (binary frames)
    if ft.handle_payload(src, payload):
        return

    # 2) If frame has flags but wasn't handled by FT, debug it
    if len(payload) >= 2 and (payload[0] == 0x7E or payload[-1] == 0x7E):
        from file_transfer import debug_inspect_frame

        debug_inspect_frame(payload)
        print(
            f"[warn] 0x7E frame not handled by FT (len={len(payload)})", flush=True
        )
        return

    # 3) Otherwise: discovery + chat messages
    text = payload.decode(errors="ignore")
    display = text
    msg_id: Optional[str] = None

    if text.startswith("MSG::"):
        parts = text.split("::", 2)
        if len(parts) == 3:
            msg_id = parts[1]
            display = parts[2]

    discovery.handle_incoming(src, display)
    print(
        f"[rx {mac_bytes_to_str(src)} → {mac_bytes_to_str(dst)}] {display}", flush=True
    )

    if msg_id:
        ft.send_ack(src, {"kind": ACK_KIND_MSG, "id": msg_id})


def print_help() -> None:
    """Print available commands."""
    print(
        """Commands:
  /me                       -> show your MAC
  /peers                    -> list peers (MAC, name, last_seen)
  /peers reset              -> clear peer table and file
  /peer <MAC|Name>          -> set active peer by MAC or Name
  /discover on|off          -> start or stop beacons
  /sendfile <MAC|Name> </path/to/file>   -> send file
  <free text>               -> send UNICAST to active peer
  /help                     -> this help
""",
        flush=True,
    )


def handle_ack(kind: str, src_mac: bytes, data: Dict) -> None:
    """
    Handle ACK frames for messages and file chunks.

    Args:
        kind: ACK type (ACK_KIND_MSG or ACK_KIND_DATA).
        src_mac: Source MAC address.
        data: ACK payload dictionary.
    """
    global msg_ack_mgr
    mac = mac_bytes_to_str(src_mac)

    if kind == ACK_KIND_MSG:
        mid = data.get("id")
        if mid and msg_ack_mgr:
            info = msg_ack_mgr.ack(mid)
            if info:
                text = info.get("text", "")
                print(f"[ack {mac}] message confirmed ({text})", flush=True)

    elif kind == ACK_KIND_DATA:
        sid = data.get("sid")
        seq = data.get("seq")
        if sid is not None and seq is not None:
            print(f"[ack {mac}] data sid={sid} seq={seq}", flush=True)


def main() -> None:
    """Main entry point for LinkChat."""
    global active_peer, registry, discovery, ft, msg_ack_mgr

    sock = SocketManager(IFACE, ETHERTYPE)
    mgr = ThreadManager(sock, on_frame=on_frame, drop_own_frames=True)
    mgr.start()

    store = JSONPeerStore(PEERS_FILE)
    registry = PeerRegistry(store)
    if RESET_PEERS_ON_START:
        registry.reset()
        print(f"[init] peers reset ({PEERS_FILE})", flush=True)
    else:
        n = registry.load()
        print(f"[init] peers loaded: {n}", flush=True)

    discovery = PeerDiscovery(
        mgr=mgr,
        name=NAME,
        registry=registry,
        interval=BEACON_INTERVAL,
        on_beacon=lambda p: print(f"[beacon rx] {p.mac} -> {p.name}", flush=True),
    )
    discovery.start()

    ft = FTv2(
        mgr=mgr,
        my_name=NAME,
        inbox_dir=INBOX_DIR,
        chunk_size=CHUNK_SIZE,
        on_info=lambda m: print(m, flush=True),
        on_progress=lambda role, sid, done, total: print(
            f"[{role} {sid}] {done}/{total} bytes ({(done/total*100 if total else 0):.1f}%)",
            flush=True,
        ),
        on_complete=lambda role, sid, ok: print(
            f"[{role} {sid}] {'OK' if ok else 'FAIL'}", flush=True
        ),
        on_ack=handle_ack,
        data_retry_interval=FILE_RETRY_INTERVAL,
        data_max_retries=FILE_MAX_RETRIES,
    )

    msg_ack_mgr = AckRetryManager("msg", MSG_RETRY_INTERVAL, MSG_MAX_RETRIES)
    msg_ack_mgr.start()

    print(
        f"[up] iface={IFACE} mac={sock.get_mac_address()} ethertype={hex(ETHERTYPE)} name={NAME}"
    )
    print_help()
    print(
        "Tip: /sendfile <MAC|Name> </local/path> (saved in /data/inbox on receiver)"
    )

    try:
        if sys.stdin.isatty():
            while True:
                try:
                    line = input("> ").strip()
                except EOFError:
                    print("[info] STDIN closed; receive-only mode.")
                    while True:
                        time.sleep(1)
                if not line:
                    continue

                if line == "/help":
                    print_help()
                    continue

                if line == "/me":
                    print(f"[me] {sock.get_mac_address()} ({NAME})", flush=True)
                    continue

                if line == "/peers":
                    rows = registry.list()
                    if not rows:
                        print("[peers] (empty)", flush=True)
                    else:
                        for p in rows:
                            print(
                                f"  {p.mac}\t{p.name or '(?)'}\t{p.last_seen}",
                                flush=True,
                            )
                    continue

                if line == "/peers reset":
                    registry.reset()
                    print("[peers] table and file cleared.", flush=True)
                    continue

                if line.startswith("/peer "):
                    token = line.split(" ", 1)[1].strip()
                    mac_str = resolve_mac(token)
                    if not mac_str:
                        print(
                            f"[peer] Not found '{token}'. Use /peers.", flush=True
                        )
                        continue
                    active_peer = mac_str_to_bytes(mac_str)
                    print(f"[peer] active destination = {mac_str}", flush=True)
                    continue

                if line.startswith("/discover "):
                    arg = line.split(" ", 1)[1].strip().lower()
                    if arg == "off":
                        discovery.stop()
                        print("[discover] Beacon stopped.", flush=True)
                    elif arg == "on":
                        discovery.start()
                        print("[discover] Beacon started.", flush=True)
                    else:
                        print("[discover] Use: /discover on | /discover off", flush=True)
                    continue

                if line.startswith("/sendfile "):
                    parts = line.split(" ", 2)
                    if len(parts) != 3:
                        print(
                            "[sendfile] usage: /sendfile <MAC|Name> </local/path>",
                            flush=True,
                        )
                        continue
                    token, path = parts[1], parts[2]
                    mac_str = resolve_mac(token)
                    if not mac_str:
                        print(
                            f"[sendfile] peer '{token}' not found. Use /peers.",
                            flush=True,
                        )
                        continue
                    try:
                        dst_mac = mac_str_to_bytes(mac_str)
                    except Exception:
                        print("[sendfile] Invalid MAC.", flush=True)
                        continue
                    ft.send_file(dst_mac, path)
                    continue

                # Send chat message to active peer
                if not active_peer:
                    print(
                        "[warn] No active peer. Use: /peer <MAC|Name>", flush=True
                    )
                    continue

                msg_id = uuid.uuid4().hex[:8]
                text = f"{NAME}: {line}"
                payload = f"MSG::{msg_id}::{text}".encode()
                dst_bytes = active_peer
                meta = {"text": text, "peer": mac_bytes_to_str(dst_bytes)}


                if msg_ack_mgr:

                    def send_once(dst=dst_bytes, data=payload) -> None:
                        mgr.send_unicast_payload(dst, data)

                    def fail_once(info: Dict) -> None:
                        label = info.get("text", text)
                        print(
                            f"[fail] no ACK after {MSG_MAX_RETRIES} attempts ({label})",
                            flush=True,
                        )

                    def error_once(exc: Exception) -> None:
                        print(f"[retry] error resending {msg_id}: {exc}", flush=True)

                    msg_ack_mgr.add(
                        msg_id,
                        send_once,
                        fail_fn=fail_once,
                        meta=meta,
                        error_fn=error_once,
                    )
                else:
                    try:
                        mgr.send_unicast_payload(dst_bytes, payload)
                    except Exception as exc:
                        print(f"[err] send failed ({exc})", flush=True)
                        continue

                print(f"[tx → {mac_bytes_to_str(dst_bytes)}] {line}", flush=True)
        else:
            print(
                "[info] No TTY; receive-only mode (discovery and file-transfer active)."
            )
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        if msg_ack_mgr:
            msg_ack_mgr.stop()
            msg_ack_mgr = None
        ft.shutdown()
        discovery.stop()
        mgr.stop()


if __name__ == "__main__":
    main()
