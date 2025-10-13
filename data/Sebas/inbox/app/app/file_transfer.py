"""
file_transfer.py
~~~~~~~~~~~~~~~~

Binary file transfer protocol with CRC validation and automatic retries.

This module implements FTv2, a reliable file transfer protocol over raw Ethernet
frames using:
- Control handshake: REQ/ACPT/BUSY/RJCT/DONE/ABRT messages
- Sequenced data chunks with CRC16-CCITT validation
- Automatic chunk retransmission via AckRetryManager
- Single active incoming transfer (exclusive RX lock)

Frame Types:
- TYPE_CTRL (0x10): Control messages (JSON payloads)
- TYPE_DATA (0x11): File data chunks
- TYPE_ACK (0x12): Acknowledgments (handled by ack_protocol)

Transfer Flow:
    Sender                          Receiver
    ------                          --------
    REQ(sid, filename, size) -->
                            <--     ACPT(sid) or BUSY/RJCT
    DATA(sid, seq, chunk)    -->
                            <--     ACK(sid, seq)
    ...repeat until done...
    DONE(sid)                -->
                            <--     DONE(sid)
"""
from __future__ import annotations

import json
import os
import shutil
import tarfile
import threading
import uuid
from typing import Any, Callable, Dict, Optional

from frame_helper import CRCError, FramingError, decode_frame, encode_frame
from ack_protocol import (
    TYPE_ACK,
    ACK_KIND_DATA,
    AckRetryManager,
    build_ack_frame,
    decode_ack_payload,
)

# Frame type identifiers
TYPE_CTRL = 0x10
TYPE_DATA = 0x11


class FTv2:
    """
    File transfer protocol version 2 with automatic retries.

    Manages bidirectional file transfers over binary frames with CRC
    validation and automatic retransmission of unacknowledged chunks.

    Attributes:
        mgr: ThreadManager instance for sending frames.
        name: Local peer name for identification.
        inbox: Directory path for received files.
        chunk: Maximum chunk size in bytes.
        rx: Current incoming transfer session (exclusive, only one at a time).
        tx: Dictionary of active outgoing transfer sessions keyed by session ID.
    """

    def __init__(
        self,
        mgr,  # ThreadManager with send_unicast_payload(dst, bytes)
        my_name: str,
        inbox_dir: str = "/data/inbox",
        chunk_size: int = 1300,
        on_info: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[str, str, int, int], None]] = None,
        on_complete: Optional[Callable[[str, str, bool], None]] = None,
        on_ack: Optional[Callable[[str, bytes, Dict], None]] = None,
        data_retry_interval: float = 3.0,
        data_max_retries: int = 3,
        ack_retry_mgr: Optional[AckRetryManager] = None,
    ):
        """
        Initialize the file transfer manager.

        Args:
            mgr: ThreadManager for sending frames.
            my_name: Local peer identifier.
            inbox_dir: Directory for storing received files.
            chunk_size: Maximum bytes per data chunk.
            on_info: Optional callback for informational messages.
            on_progress: Optional callback for transfer progress: (role, sid, done, total).
            on_complete: Optional callback when transfer finishes: (role, sid, success).
            on_ack: Optional callback for received ACKs: (kind, src_mac, data).
            data_retry_interval: Seconds between chunk retransmission attempts.
            data_max_retries: Maximum retry attempts before aborting.
            ack_retry_mgr: Optional shared AckRetryManager; creates internal one if None.
        """
        self.mgr = mgr
        self.name = my_name
        self.inbox = inbox_dir
        self.chunk = chunk_size

        self.on_info = on_info or (lambda m: None)
        self.on_progress = on_progress or (lambda a, b, c, d: None)
        self.on_complete = on_complete or (lambda a, b, c: None)
        self._ack_cb = on_ack

        # Setup retry manager (shared or internal)
        if ack_retry_mgr is None:
            self._data_retry = AckRetryManager(
                "file", interval=data_retry_interval, max_attempts=data_max_retries
            )
            self._own_retry_mgr = True
        else:
            self._data_retry = ack_retry_mgr
            self._own_retry_mgr = False
        self._data_retry.start()

        os.makedirs(self.inbox, exist_ok=True)

        # Transfer state
        self.rx: Optional[Dict] = None  # {'sid','f','sz','recv','src','path'}
        self.tx: Dict[str, Dict] = {}  # sid -> session dict
        self._tx_lock = threading.Lock()

    # Public API ------------------------------------------------------

    def send_file(
        self,
        dst_mac: bytes,
        local_path: str,
        *,
        display_name: Optional[str] = None,
        kind: str = "file",
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Initiate a file transfer to a remote peer.

        Args:
            dst_mac: Destination MAC address (6 bytes).
            local_path: Absolute path to the local file to send.
            display_name: Optional filename advertised to the receiver.
            kind: Logical payload type ("file" or "dir").
            meta: Additional metadata to deliver in the REQ control frame.

        Note:
            If the file doesn't exist, logs an error and returns without sending.

        Returns:
            Optional[str]: Session identifier if transfer started, otherwise None.
        """
        if not os.path.isfile(local_path):
            self.on_info(f"[ft] file does not exist: {local_path}")
            return None

        sid = uuid.uuid4().hex[:12]
        fn = display_name or os.path.basename(local_path)
        sz = os.path.getsize(local_path)

        session = {
            "dst": dst_mac,
            "path": local_path,
            "sz": sz,
            "fn": fn,
            "acked": 0,
            "next_seq": 0,
            "next_offset": 0,
            "pending_id": None,
            "fh": None,
            "kind": kind,
            "meta": meta or {},
        }

        with self._tx_lock:
            self.tx[sid] = session

        self._send_ctrl(
            dst_mac,
            {
                "op": "REQ",
                "sid": sid,
                "name": self.name,
                "fn": fn,
                "sz": sz,
                "kind": kind,
                "meta": meta or {},
            },
        )
        self.on_info(f"[ft] REQ sid={sid} -> {fn} ({sz} bytes)")
        return sid

    def handle_payload(self, src_mac: bytes, payload: bytes) -> bool:
        """
        Process an incoming frame if it belongs to this protocol.

        Args:
            src_mac: Source MAC address.
            payload: Raw frame bytes (must start and end with 0x7E flag).

        Returns:
            bool: True if the frame was recognized and processed, False otherwise.
        """
        # Only process frames with proper flag boundaries
        if len(payload) < 2 or payload[0] != 0x7E or payload[-1] != 0x7E:
            return False

        try:
            ftype, seq, pl = decode_frame(payload)
        except (CRCError, FramingError):
            return False

        if ftype == TYPE_CTRL:
            self._on_ctrl(src_mac, pl)

            return True
        if ftype == TYPE_DATA:
            self._on_data(src_mac, seq, pl)
            return True
        if ftype == TYPE_ACK:
            self._on_ack(src_mac, pl)
            return True
        return False

    def shutdown(self) -> None:
        """
        Stop the transfer manager and clean up all resources.

        Closes all active sessions and stops the internal retry manager if owned.
        """
        if self._own_retry_mgr:
            self._data_retry.stop()
        for sid in list(self.tx.keys()):
            self._drop_tx_session(sid)
        if self.rx:
            try:
                self.rx["f"].close()
            except Exception:
                pass
            self.rx = None

    def send_ack(self, dst_mac: bytes, payload: dict, seq: int = 0) -> None:
        """
        Send an ACK frame to acknowledge received data.

        Args:
            dst_mac: Destination MAC address.
            payload: ACK payload dictionary (must include 'kind' field).
            seq: Sequence number (default 0).
        """
        frame = build_ack_frame(payload, seq)
        self.mgr.send_unicast_payload(dst_mac, frame)

    # Internal helpers ------------------------------------------------

    def _send_ctrl(self, dst_mac: bytes, obj: dict, seq: int = 0) -> None:
        """Send a control message frame."""
        raw = json.dumps(obj, ensure_ascii=False).encode()
        frame = encode_frame(raw, TYPE_CTRL, seq)
        self.mgr.send_unicast_payload(dst_mac, frame)

    def _send_data(self, dst_mac: bytes, chunk: bytes, seq: int) -> None:
        """Send a data chunk frame with the specified sequence number."""
        frame = encode_frame(chunk, TYPE_DATA, seq)
        self.mgr.send_unicast_payload(dst_mac, frame)

    @staticmethod
    def _mac2s(mac: bytes) -> str:
        """Convert MAC address bytes to colon-separated hex string."""
        return ":".join(f"{b:02x}" for b in mac)

    def _on_ctrl(self, src_mac: bytes, raw: bytes) -> None:
        """
        Handle incoming control messages.

        Processes: REQ, ACPT, BUSY, RJCT, DONE, ABRT operations.
        """
        try:
            c = json.loads(raw.decode("utf-8", "ignore"))
        except Exception:
            return
        op = c.get("op")
        sid = c.get("sid")

        if op == "REQ":
            fn = c.get("fn", "file.bin")
            sz = int(c.get("sz", 0))
            kind = c.get("kind", "file")
            meta = c.get("meta") if isinstance(c.get("meta"), dict) else {}
            if self.rx is not None:
                self._send_ctrl(src_mac, {"op": "BUSY", "sid": sid})
                self.on_info(f"[ft] REQ from {self._mac2s(src_mac)} rejected (BUSY)")
                return
            try:
                target = os.path.join(self.inbox, fn)
                f = open(target, "wb")
            except OSError as e:
                self._send_ctrl(src_mac, {"op": "RJCT", "sid": sid})
                self.on_info(f"[ft] cannot open destination: {e}")
                return
            self.rx = {
                "sid": sid,
                "f": f,
                "sz": sz,
                "recv": 0,
                "src": self._mac2s(src_mac),
                "path": target,
                "fn": fn,
                "kind": kind,
                "meta": meta,
            }
            self._send_ctrl(src_mac, {"op": "ACPT", "sid": sid})
            self.on_info(f"[ft] ACPT sid={sid} {fn} ({sz} bytes)")
            return

        if op == "ACPT":
            with self._tx_lock:
                session = self.tx.get(sid)
            if not session:
                return
            if session.get("fh") is None:
                try:
                    fh = open(session["path"], "rb")
                except OSError as exc:
                    self._send_ctrl(session["dst"], {"op": "ABRT", "sid": sid})
                    self.on_info(f"[ft] TX error sid={sid}: {exc}")
                    self.on_complete("tx", sid, False)
                    self._drop_tx_session(sid)
                    return
                with self._tx_lock:
                    current = self.tx.get(sid)
                    if not current:
                        fh.close()
                        return
                    current["fh"] = fh
                    session = current
            self.on_info(f"[ft] ACPT sid={sid} {session['fn']} ({session['sz']} bytes)")
            self._send_next_chunk(sid)
            return

        if op == "BUSY":
            self.on_info(f"[ft] peer busy sid={sid}")
            self.on_complete("tx", sid, False)
            self._drop_tx_session(sid)
            return

        if op == "RJCT":
            self.on_info(f"[ft] peer rejected sid={sid}")
            self.on_complete("tx", sid, False)
            self._drop_tx_session(sid)
            return

        if op == "DONE":
            self.on_info(f"[ft] RX peer confirmed DONE sid={sid}")
            self.on_complete("tx", sid, True)
            self._drop_tx_session(sid)
            return

        if op == "ABRT":
            if self.rx and self.rx["sid"] == sid:
                try:
                    self.rx["f"].close()
                except Exception:
                    pass
                self.rx = None
                self.on_complete("rx", sid, False)
            return

    def _on_data(self, src_mac: bytes, seq: int, chunk: bytes) -> None:
        """
        Handle incoming data chunk.

        Writes chunk to active RX session file and sends ACK.
        Completes transfer if all bytes received.
        """
        if not self.rx:
            return
        if self._mac2s(src_mac) != self.rx["src"]:
            return

        try:
            self.rx["f"].write(chunk)
            self.rx["recv"] += len(chunk)
        except Exception:
            try:
                self.rx["f"].close()
            except Exception:
                pass
            self._send_ctrl(src_mac, {"op": "ABRT", "sid": self.rx["sid"]})
            self.on_complete("rx", self.rx["sid"], False)
            self.rx = None
            return

        self.send_ack(
            src_mac, {"kind": ACK_KIND_DATA, "sid": self.rx["sid"], "seq": seq}
        )
        self.on_progress("rx", self.rx["sid"], self.rx["recv"], self.rx["sz"])

        if self.rx["recv"] >= self.rx["sz"]:
            session = self.rx
            try:
                session["f"].close()
            except Exception:
                pass

            sid = session["sid"]
            success = True

            if session.get("kind") == "dir":
                success = self._finalize_directory_transfer(session)

            if success:
                self._send_ctrl(src_mac, {"op": "DONE", "sid": sid})
                self.on_info(f"[ft] RX DONE sid={sid} -> {session['path']}")
                self.on_complete("rx", sid, True)
            else:
                self._send_ctrl(src_mac, {"op": "ABRT", "sid": sid})
                self.on_complete("rx", sid, False)

            self.rx = None

    def _drop_tx_session(self, sid: str) -> Optional[Dict]:
        """
        Remove a TX session and clean up resources.

        Args:
            sid: Session ID to drop.

        Returns:
            Optional[Dict]: Session data if it existed, None otherwise.
        """
        with self._tx_lock:
            session = self.tx.pop(sid, None)
        if not session:
            return None

        pending_id = session.get("pending_id")
        if pending_id:
            self._data_retry.cancel(pending_id)

        fh = session.get("fh")
        if fh:
            try:
                fh.close()
            except Exception:
                pass
        return session

    def _send_next_chunk(self, sid: str) -> None:
        """
        Send the next file chunk for a TX session.

        Reads the next chunk from the file, registers it with the retry manager,
        and schedules automatic retransmissions until ACK is received.

        Args:
            sid: Session ID of the active transfer.
        """
        task: Optional[Dict[str, Any]] = None
        drop_kind: Optional[str] = None
        drop_exc: Optional[Exception] = None

        with self._tx_lock:
            session = self.tx.get(sid)
            if not session or session.get("pending_id"):
                return
            dst = session["dst"]
            total = session["sz"]
            if total == 0:
                drop_kind = "done"
            else:
                fh = session.get("fh")
                if fh is None:
                    try:
                        fh = open(session["path"], "rb")
                        session["fh"] = fh
                    except OSError as exc:
                        drop_kind = "fail"
                        drop_exc = exc
                if drop_kind is None:
                    fh = session.get("fh")
                    if fh is None:
                        drop_kind = "fail"
                        drop_exc = RuntimeError("failed to open file for reading")
                    else:
                        offset = session.get("next_offset", 0)
                        fh.seek(offset)
                        chunk = fh.read(self.chunk)
                        if chunk:
                            seq = session.get("next_seq", 0)
                            key = f"{sid}:{seq}"
                            meta = {
                                "sid": sid,
                                "seq": seq,
                                "len": len(chunk),
                                "fn": session["fn"],
                                "attempt": 0,
                                "dst": dst,
                            }
                            session["pending_id"] = key
                            session["next_seq"] = (seq + 1) & 0xFF
                            session["next_offset"] = offset + len(chunk)
                            task = {
                                "dst": dst,
                                "chunk": chunk,
                                "seq": seq,
                                "key": key,
                                "meta": meta,
                            }
                        else:
                            if session.get("acked", 0) >= total:
                                drop_kind = "done"
                            else:
                                drop_kind = "fail"
                                drop_exc = RuntimeError(
                                    "insufficient data to complete file"
                                )

        # Handle session completion or failure
        if drop_kind:
            stored = self._drop_tx_session(sid)
            if not stored:
                return
            dst = stored["dst"]
            fn = stored["fn"]
            if drop_kind == "done":
                self._send_ctrl(dst, {"op": "DONE", "sid": sid})
                self.on_info(f"[ft] TX DONE sid={sid} {fn}")
                self.on_complete("tx", sid, True)
            else:
                self.on_info(f"[ft] TX error sid={sid}: {drop_exc}")
                self._send_ctrl(dst, {"op": "ABRT", "sid": sid})
                self.on_complete("tx", sid, False)
            return

        if not task:
            return

        # Register chunk with retry manager
        dst = task["dst"]
        chunk = task["chunk"]
        seq = task["seq"]
        key = task["key"]
        meta = task["meta"]

        def send_once() -> None:
            """Send or retry this specific chunk."""
            meta["attempt"] = meta.get("attempt", 0) + 1
            self._send_data(dst, chunk, seq)
            if meta["attempt"] == 1:
                self.on_info(f"[ft] TX data sid={sid} seq={seq} len={len(chunk)}")
            else:
                self.on_info(
                    f"[ft] retry sid={sid} seq={seq} attempt={meta['attempt']}"
                )

        def fail_fn(info: Dict[str, Any]) -> None:
            """Called when max retries exceeded."""
            attempts = info.get("attempt", 0)
            self.on_info(f"[ft] no ACK sid={sid} seq={seq} after {attempts} attempts")
            self._handle_chunk_failure(sid, info)

        def error_fn(exc: Exception) -> None:
            """Called if send_once raises an exception."""
            self.on_info(f"[ft] error resending sid={sid} seq={seq}: {exc}")

        self._data_retry.add(
            key,
            send_once,
            fail_fn=fail_fn,
            meta=meta,
            error_fn=error_fn,
        )

    def _handle_chunk_failure(self, sid: str, meta: Dict[str, Any]) -> None:
        """
        Handle chunk timeout by aborting the transfer.

        Args:
            sid: Session ID.
            meta: Metadata from the failed retry item.
        """
        stored = self._drop_tx_session(sid)
        dst = meta.get("dst")
        if not dst and stored:
            dst = stored.get("dst")
        if stored:
            fn = stored.get("fn", "?")
            self.on_info(f"[ft] ABRT sid={sid} {fn} due to timeout")
        if dst:
            self._send_ctrl(dst, {"op": "ABRT", "sid": sid})
        self.on_complete("tx", sid, False)

    def _finalize_directory_transfer(self, session: Dict[str, Any]) -> bool:
        """Extract a received archive into the inbox, replacing any existing folder."""

        archive_path = session.get("path")
        if not isinstance(archive_path, str):
            self.on_info("[ft] missing archive path for directory transfer")
            return False
        meta = session.get("meta") or {}
        folder_hint = meta.get("dir_name") or os.path.splitext(session.get("fn", "folder"))[0]
        folder_name = os.path.basename(folder_hint) or "folder"
        target_dir = os.path.join(self.inbox, folder_name)

        inbox_root = os.path.abspath(self.inbox)
        target_dir_abs = os.path.abspath(target_dir)
        inbox_prefix = inbox_root + os.sep
        if not (target_dir_abs == inbox_root or target_dir_abs.startswith(inbox_prefix)):
            self.on_info(f"[ft] invalid folder target outside inbox: {folder_name}")
            return False

        try:
            shutil.rmtree(target_dir)
        except FileNotFoundError:
            pass
        except Exception as exc:
            self.on_info(f"[ft] failed to remove existing folder {target_dir}: {exc}")
            return False

        try:
            os.makedirs(target_dir, exist_ok=True)
            with tarfile.open(archive_path, "r:*") as tar:
                prefix = target_dir_abs + os.sep
                for member in tar.getmembers():
                    member_path = os.path.abspath(os.path.join(target_dir, member.name))
                    if not (member_path == target_dir_abs or member_path.startswith(prefix)):
                        raise ValueError("archive member escapes target directory")
                tar.extractall(target_dir)
        except Exception as exc:
            self.on_info(f"[ft] failed to extract directory archive: {exc}")
            try:
                shutil.rmtree(target_dir)
            except Exception:
                pass
            try:
                os.remove(archive_path)
            except OSError:
                pass
            return False

        try:
            os.remove(archive_path)
        except OSError:
            pass

        session["path"] = target_dir
        self.on_info(f"[ft] extracted folder to {target_dir}")
        return True

    def _on_ack(self, src_mac: bytes, raw: bytes) -> None:
        """
        Handle incoming ACK frames.

        Stops retry for acknowledged chunks and advances transfer or completes it.
        """
        data = decode_ack_payload(raw)
        kind = data.get("kind", "")
        if kind == ACK_KIND_DATA:
            sid = data.get("sid")
            seq = data.get("seq")
            ack_value = None
            if isinstance(seq, int):
                ack_value = seq
            elif isinstance(seq, str):
                try:
                    ack_value = int(seq)
                except ValueError:
                    ack_value = None
            if sid and ack_value is not None:
                key = f"{sid}:{ack_value}"
                meta = self._data_retry.ack(key)
                if meta:
                    attempts = meta.get("attempt", 0)
                    ack_len = int(meta.get("len") or 0)
                    self.on_info(
                        f"[ft] ACK data sid={sid} seq={ack_value} from {self._mac2s(src_mac)} (attempt={attempts})"
                    )
                    acked = 0
                    total = 0
                    fn = ""
                    dst_mac: Optional[bytes] = None
                    session_ref = None
                    with self._tx_lock:
                        session = self.tx.get(sid)
                        if session and session.get("pending_id") == key:
                            session["pending_id"] = None
                            session["acked"] = session.get("acked", 0) + ack_len
                            acked = session["acked"]
                            total = session["sz"]
                            dst_mac = session["dst"]
                            fn = session["fn"]
                            session_ref = session
                    if session_ref:
                        self.on_progress("tx", sid, acked, total)
                        if acked >= total and dst_mac is not None:
                            self._send_ctrl(dst_mac, {"op": "DONE", "sid": sid})
                            self.on_info(f"[ft] TX DONE sid={sid} {fn}")
                            self.on_complete("tx", sid, True)
                            self._drop_tx_session(sid)
                        else:
                            self._send_next_chunk(sid)
                else:
                    self.on_info(
                        f"[ft] ACK data without session sid={sid} seq={ack_value} from {self._mac2s(src_mac)}"
                    )
            else:
                self.on_info(f"[ft] ACK data invalid: {data}")
        if self._ack_cb:
            try:
                self._ack_cb(kind, src_mac, data)
            except Exception:
                pass


# Debug utilities -----------------------------------------------------


def debug_inspect_frame(payload: bytes) -> None:
    """
    Debug helper to inspect frame structure.

    Prints detailed breakdown of: TYPE, SEQ, LEN, CRC received vs calculated.

    Args:
        payload: Raw frame bytes including 0x7E flags.
    """
    from frame_helper import bytes_to_bits, bit_unstuff, bits_to_bytes, crc16_ccitt
    import struct

    if not (payload and payload[0] == 0x7E and payload[-1] == 0x7E):
        print("[ft/dbg] no 0x7E flags at boundaries", flush=True)
        return

    segment = payload[1:-1]
    try:
        bits = bytes_to_bits(segment)
        unstuff = bit_unstuff(bits)
    except Exception as e:
        print(f"[ft/dbg] bit_unstuff failed: {e}", flush=True)
        return

    raw = bits_to_bytes(unstuff)
    print(f"[ft/dbg] raw_len={len(raw)} raw_prefix={raw[:8].hex()}", flush=True)

    if len(raw) < 6:
        print("[ft/dbg] raw too short", flush=True)
        return

    typ, seq, length = struct.unpack("!BBH", raw[0:4])
    if len(raw) != 4 + length + 2:
        print(
            f"[ft/dbg] length mismatch raw={len(raw)} expected={4+length+2}",
            flush=True,
        )
        return

    crc_recv = int.from_bytes(raw[4 + length : 4 + length + 2], "big")
    crc_calc = crc16_ccitt(raw[0 : 4 + length])
    print(
        f"[ft/dbg] TYPE=0x{typ:02x} SEQ={seq} LEN={length} CRC recv=0x{crc_recv:04x} calc=0x{crc_calc:04x}",
        flush=True,
    )
