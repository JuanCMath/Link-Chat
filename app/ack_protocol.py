"""
ack_protocol.py
~~~~~~~~~~~~~~~

Acknowledgement (ACK) protocol for reliable transfers.

This module provides utilities for:
- Building and decoding ACK frames with CRC validation.
- Centralized retry management via AckRetryManager.
- Support for multiple ACK types (messages, file data chunks).

Supported ACK types:
- ACK_KIND_MSG: Chat message acknowledgment.
- ACK_KIND_DATA: File transfer chunk acknowledgment.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from .frame_helper import encode_frame, decode_frame, CRCError, FramingError

# Frame type for ACK packets
TYPE_ACK = 0x12

# Supported acknowledgment kinds
ACK_KIND_MSG = "msg"
ACK_KIND_DATA = "data"


def build_ack_frame(obj: Dict[str, Any], seq: int = 0) -> bytes:
    """
    Build a binary ACK frame from a dictionary payload.

    Args:
        obj: Dictionary with ACK payload (must include 'kind' field).
        seq: Sequence number of the frame (0-255).

    Returns:
        bytes: Complete binary frame with CRC and byte stuffing applied.

    Example:
        >>> frame = build_ack_frame({"kind": "msg", "msg_id": "abc123"})
    """
    raw = json.dumps(obj, ensure_ascii=False).encode()
    return encode_frame(raw, TYPE_ACK, seq)


def try_decode_ack(frame: bytes) -> Tuple[int, Dict[str, Any]]:
    """
    Attempt to decode an ACK frame with full validation.

    Args:
        frame: Raw binary frame including flags and CRC.

    Returns:
        Tuple[int, Dict[str, Any]]: Sequence number and payload dictionary.

    Raises:
        ValueError: If frame is not a valid ACK (bad CRC, wrong type, or invalid JSON).
    """
    try:
        ftype, seq, payload = decode_frame(frame)
    except (CRCError, FramingError) as exc:
        raise ValueError("invalid ack frame") from exc
    if ftype != TYPE_ACK:
        raise ValueError("not an ack frame")
    try:
        data = json.loads(payload.decode("utf-8", "ignore"))
    except Exception as exc:
        raise ValueError("ack payload is not JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("ack payload must be a JSON object")
    return seq, data


def decode_ack_payload(raw_payload: bytes) -> Dict[str, Any]:
    """
    Decode a JSON payload already extracted from an ACK frame.

    Args:
        raw_payload: Raw bytes containing JSON data.

    Returns:
        Dict[str, Any]: Parsed dictionary, or empty dict if parsing fails.
    """
    try:
        data = json.loads(raw_payload.decode("utf-8", "ignore"))
    except Exception:
        return {}
    if isinstance(data, dict):
        return data
    return {}


class AckRetryManager:
    """
    Generic manager for ACK-based retransmissions.

    This class tracks pending operations (messages, file chunks) and
    automatically retries them at configurable intervals until an ACK
    is received or the maximum attempt count is reached.

    Usage:
        1. Create and start the manager:
           >>> mgr = AckRetryManager("my-service", interval=2.0, max_attempts=5)
           >>> mgr.start()

        2. Register a task with a unique key:
           >>> mgr.add("msg-123", send_function, fail_fn=on_timeout, meta={"text": "hello"})

        3. Acknowledge when response arrives:
           >>> meta = mgr.ack("msg-123")  # Returns metadata and stops retrying

        4. Cleanup on shutdown:
           >>> mgr.stop()

    Attributes:
        name: Human-readable identifier for this manager instance.
        interval: Seconds between retry attempts.
        max_attempts: Maximum number of send attempts before calling fail_fn.
    """

    def __init__(
        self,
        name: str,
        interval: float = 3.0,
        max_attempts: int = 3,
    ) -> None:
        """
        Initialize the retry manager.

        Args:
            name: Identifier for logging and thread naming.
            interval: Seconds between retries (minimum 0.5).
            max_attempts: Maximum retry attempts (minimum 1).
        """
        self.name = name
        self.interval = max(0.5, float(interval))
        self.max_attempts = max(1, int(max_attempts))
        self._lock = threading.Lock()
        self._items: Dict[Any, Dict[str, Any]] = {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # Lifecycle methods -----------------------------------------------

    def start(self) -> None:
        """
        Start the background retry thread.

        Safe to call multiple times; does nothing if already running.
        """
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name=f"{self.name}-ack-retry",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """
        Stop the retry thread and clear all pending items.

        Blocks for up to 1 second waiting for thread termination.
        """
        if not self._thread:
            with self._lock:
                self._items.clear()
            return
        self._stop.set()
        self._thread.join(timeout=1.0)
        self._thread = None
        with self._lock:
            self._items.clear()

    # Registration API ------------------------------------------------

    def add(
        self,
        key: Any,
        send_fn: Callable[[], None],
        *,
        fail_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
        meta: Optional[Dict[str, Any]] = None,
        immediate: bool = True,
        error_fn: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Register a new item for ACK-based retry.

        Args:
            key: Unique identifier for this item (e.g., "msg-id" or "sid:seq").
            send_fn: Callable invoked to send/resend the item.
            fail_fn: Optional callback invoked when max_attempts is reached.
                     Receives the metadata dict as argument.
            meta: Optional metadata dict stored with the item and returned on ack().
            immediate: If True, calls send_fn immediately; otherwise waits for first interval.
            error_fn: Optional callback for exceptions raised by send_fn.
        """
        item = {
            "send": send_fn,
            "fail": fail_fn,
            "meta": meta or {},
            "attempts": 0,
            "last_sent": 0.0,
            "error": error_fn,
        }
        with self._lock:
            self._items[key] = item
        if immediate:
            self._send_item(key, item)

    def ack(self, key: Any) -> Optional[Dict[str, Any]]:
        """
        Acknowledge receipt of an item, stopping retries.

        Args:
            key: The unique identifier of the item being acknowledged.

        Returns:
            Optional[Dict[str, Any]]: Metadata dict if key was found, None otherwise.
        """
        with self._lock:
            item = self._items.pop(key, None)
        if item:
            return item.get("meta")
        return None

    def cancel(self, key: Any) -> None:
        """
        Cancel retries for an item without invoking fail_fn.

        Args:
            key: The unique identifier to cancel.
        """
        with self._lock:
            self._items.pop(key, None)

    # Internal retry loop ---------------------------------------------

    def _loop(self) -> None:
        """Background thread that schedules retries and failures."""
        while not self._stop.wait(0.5):
            now = time.time()
            to_retry: list[Tuple[Any, Dict[str, Any]]] = []
            to_fail: list[Tuple[Any, Dict[str, Any]]] = []
            with self._lock:
                for key, item in list(self._items.items()):
                    if item["attempts"] >= self.max_attempts:
                        to_fail.append((key, item))
                        continue
                    if now - item["last_sent"] >= self.interval:
                        to_retry.append((key, item))
            for key, item in to_retry:
                self._send_item(key, item)
            for key, item in to_fail:
                self._fail_item(key, item)

    def _send_item(self, key: Any, item: Dict[str, Any]) -> None:
        """Execute send_fn and update attempt tracking."""
        try:
            item["send"]()
        except Exception as exc:
            handler = item.get("error")
            if handler:
                try:
                    handler(exc)
                except Exception:
                    pass
        finally:
            item["attempts"] += 1
            item["last_sent"] = time.time()

    def _fail_item(self, key: Any, item: Dict[str, Any]) -> None:
        """Remove item from tracking and invoke fail_fn if present."""
        with self._lock:
            stored = self._items.pop(key, None)
        if not stored:
            return
        fail_fn = stored.get("fail")
        if fail_fn:
            try:
                fail_fn(stored.get("meta", {}))
            except Exception:
                pass
