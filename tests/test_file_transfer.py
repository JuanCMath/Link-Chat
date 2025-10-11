"""Unit tests for the file transfer module."""

import json
import time
import threading
from pathlib import Path

import pytest

from linkchat.link.file_transfer import FileTransfer
from linkchat.link.link_layer import FrameType, LinkFrame


# Default chunk size for testing (matches default in FileTransfer)
DEFAULT_CHUNK_SIZE = 1400


class _AutoAckLinkLayer:
    """LinkLayer stub that automatically acknowledges TRANSFER_META and FILE_CHUNK frames."""

    def __init__(self, mac: bytes | None = None) -> None:
        self.sent = []
        self.transfer: FileTransfer | None = None
        self.mac = mac or bytes.fromhex("aa bb cc dd ee ff")

    def send(self, dst: bytes, typ: FrameType, payload: bytes) -> None:  # pragma: no cover - simple stub
        self.sent.append((dst, typ, payload))
        
        # Auto-ACK metadata frames
        if typ == FrameType.TRANSFER_META and self.transfer is not None:
            try:
                data = json.loads(payload.decode('utf-8'))
                transfer_name = data.get("name") or data.get("root", "")
                ack_payload = b"\x4D" + transfer_name.encode('utf-8')
                ack_frame = LinkFrame(
                    dst=self.mac,
                    src=dst,
                    typ=FrameType.ACK,
                    seq=0,
                    payload=ack_payload,
                )
                self.transfer.handle_received_frame(ack_frame)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        
        # Auto-ACK chunk frames
        if typ == FrameType.FILE_CHUNK and self.transfer is not None:
            chunk_id = int.from_bytes(payload[:4], "big")
            separator = payload.find(b"|", 4)
            assert separator != -1, "Chunk payload must contain a filename separator"
            filename = payload[4:separator].decode("utf-8")
            ack_payload = chunk_id.to_bytes(4, "big") + filename.encode("utf-8")
            ack_frame = LinkFrame(
                dst=self.mac,
                src=dst,
                typ=FrameType.ACK,
                seq=0,
                payload=ack_payload,
            )
            self.transfer.handle_received_frame(ack_frame)


class _RecordingLinkLayer:
    """LinkLayer stub that records frames without side effects."""

    def __init__(self) -> None:
        self.sent = []

    def send(self, dst: bytes, typ: FrameType, payload: bytes) -> None:  # pragma: no cover - simple stub
        self.sent.append((dst, typ, payload))


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """Create a sample file slightly larger than one chunk."""
    data = b"A" * (DEFAULT_CHUNK_SIZE + 200)
    path = tmp_path / "sample.bin"
    path.write_bytes(data)
    return path


def test_send_file_success(tmp_path: Path, sample_file: Path) -> None:
    """send_file should transmit the file and report progress/completion."""
    link_layer = _AutoAckLinkLayer()
    progress_reports: list[tuple[str, int, int]] = []
    completion: list[tuple[str, bool]] = []

    def on_progress(filename: str, done: int, total: int) -> None:
        progress_reports.append((filename, done, total))

    def on_complete(filename: str, success: bool) -> None:
        completion.append((filename, success))

    transfer = FileTransfer(
        link_layer=link_layer,  # type: ignore[arg-type]
        download_dir=str(tmp_path / "downloads"),
        on_progress=on_progress,
        on_complete=on_complete,
    )
    link_layer.transfer = transfer

    dst = bytes.fromhex("bb bb bb bb bb bb")
    assert transfer.send_file(dst, str(sample_file)) is True

    expected_first = ("sample.bin", DEFAULT_CHUNK_SIZE, sample_file.stat().st_size)
    expected_second = ("sample.bin", sample_file.stat().st_size, sample_file.stat().st_size)
    assert progress_reports == [expected_first, expected_second]
    assert completion == [("sample.bin", True)]


def test_duplicate_chunk_does_not_double_count(tmp_path: Path) -> None:
    """Receiving the same chunk twice should not inflate progress or byte counters."""
    link_layer = _RecordingLinkLayer()
    progress_reports: list[tuple[str, int, int]] = []

    def on_progress(filename: str, done: int, total: int) -> None:
        progress_reports.append((filename, done, total))

    transfer = FileTransfer(
        link_layer=link_layer,  # type: ignore[arg-type]
        download_dir=str(tmp_path / "downloads"),
        on_progress=on_progress,
    )

    sender_mac = bytes.fromhex("cc cc cc cc cc cc")
    filename = "notes.txt"
    chunk_data = b"hello-world"
    total_chunks = 2
    total_size = len(chunk_data) * total_chunks
    
    # Build JSON metadata for file transfer
    metadata = {
        "type": "file",
        "name": filename,
        "size": total_size,
        "chunks": total_chunks,
        "hash": "deadbeef"
    }
    meta_payload = json.dumps(metadata, separators=(",", ":")).encode('utf-8')
    
    meta_frame = LinkFrame(dst=transfer.link_layer.mac if hasattr(transfer.link_layer, "mac") else b"\x00" * 6,
                           src=sender_mac,
                           typ=FrameType.TRANSFER_META,
                           seq=1,
                           payload=meta_payload)
    transfer.handle_received_frame(meta_frame)

    payload = (0).to_bytes(4, "big") + filename.encode("utf-8") + b"|" + chunk_data
    chunk_frame = LinkFrame(dst=b"\x00" * 6, src=sender_mac, typ=FrameType.FILE_CHUNK, seq=2, payload=payload)
    transfer.handle_received_frame(chunk_frame)
    transfer.handle_received_frame(chunk_frame)  # duplicate chunk

    transfer_state = transfer.active_receives[(sender_mac, filename)]
    assert transfer_state.received_size == len(chunk_data)
    assert len(transfer_state.chunks) == 1
    assert progress_reports == [(filename, len(chunk_data), total_size)]
    assert len(link_layer.sent) == 2  # ACK sent for each reception


def test_ack_is_file_specific(tmp_path: Path) -> None:
    """ACK for one file must not release another file's pending chunk."""
    link_layer = _RecordingLinkLayer()
    transfer = FileTransfer(
        link_layer=link_layer,  # type: ignore[arg-type]
        download_dir=str(tmp_path / "downloads"),
    )

    dst = bytes.fromhex("dd dd dd dd dd dd")
    results: list[tuple[str, bool]] = []

    def worker(filename: str) -> None:
        # Use the reliable transfer layer directly
        outcome = transfer._reliable.send_chunk_reliable(dst, filename, 0, b"payload")
        results.append((filename, outcome))

    thread_one = threading.Thread(target=worker, args=("alpha.txt",), daemon=True)
    thread_one.start()

    def _wait_for_event(filename: str, timeout: float = 1.0) -> None:
        deadline = time.time() + timeout
        key = (dst, filename, 0)
        while time.time() < deadline:
            with transfer._reliable._lock:
                if key in transfer._reliable._ack_events:
                    return
            time.sleep(0.01)
        raise AssertionError("ACK event was not registered in time")

    _wait_for_event("alpha.txt")
    ack_alpha = LinkFrame(
        dst=b"\x00" * 6,
        src=dst,
        typ=FrameType.ACK,
        seq=0,
        payload=(0).to_bytes(4, "big") + "alpha.txt".encode("utf-8"),
    )
    transfer.handle_received_frame(ack_alpha)
    thread_one.join(timeout=1.0)
    assert ("alpha.txt", True) in results

    thread_two = threading.Thread(target=worker, args=("beta.txt",), daemon=True)
    thread_two.start()
    _wait_for_event("beta.txt")
    # Replaying alpha ACK should not release beta transfer
    transfer.handle_received_frame(ack_alpha)
    time.sleep(0.1)
    assert thread_two.is_alive()

    ack_beta = LinkFrame(
        dst=b"\x00" * 6,
        src=dst,
        typ=FrameType.ACK,
        seq=0,
        payload=(0).to_bytes(4, "big") + "beta.txt".encode("utf-8"),
    )
    transfer.handle_received_frame(ack_beta)
    thread_two.join(timeout=1.0)
    assert ("beta.txt", True) in results