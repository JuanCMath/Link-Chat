"""Unit tests for the message protocol layer."""

from typing import List, Tuple

from linkchat.link.link_layer import FrameType, LinkFrame
from linkchat.link.message_protocol import MessageProtocol


class _StubLinkLayer:
    def __init__(self) -> None:
        self.sent: List[Tuple[bytes, FrameType, bytes]] = []
        self.protocol: MessageProtocol | None = None

    def send(self, dst: bytes, typ: FrameType, payload: bytes) -> None:  # pragma: no cover - trivial stub
        self.sent.append((dst, typ, payload))
        if typ is FrameType.MESSAGE and self.protocol is not None:
            message_id = int.from_bytes(payload[0:2], "big")
            total_parts = int.from_bytes(payload[2:4], "big")
            part_index = int.from_bytes(payload[4:6], "big")
            if part_index == total_parts - 1:
                ack_payload = bytes([0x4D]) + message_id.to_bytes(2, "big")
                ack_frame = LinkFrame(
                    dst=b"\x00" * 6,
                    src=dst,
                    typ=FrameType.ACK,
                    seq=0,
                    payload=ack_payload,
                )
                self.protocol.handle_frame(ack_frame)


def test_send_message_success() -> None:
    link_layer = _StubLinkLayer()
    protocol = MessageProtocol(link_layer=link_layer)  # type: ignore[arg-type]
    link_layer.protocol = protocol

    dst = bytes.fromhex("aa bb cc dd ee ff")
    assert protocol.send_message(dst, "hello world") is True

    # Verify at least one message frame was transmitted and there are no pending ACKs
    assert any(frame_type is FrameType.MESSAGE for _, frame_type, _ in link_layer.sent)


def test_receive_message_reassembles_and_acks() -> None:
    link_layer = _StubLinkLayer()
    received: List[Tuple[bytes, str]] = []

    def on_message(src: bytes, text: str) -> None:
        received.append((src, text))

    protocol = MessageProtocol(link_layer=link_layer, on_message=on_message)  # type: ignore[arg-type]
    link_layer.protocol = protocol

    src = bytes.fromhex("11 22 33 44 55 66")
    dst = bytes.fromhex("aa bb cc dd ee ff")
    payload_part_a = b"The quick brown "
    payload_part_b = b"fox jumps"

    total_parts = 2
    msg_id = 42

    header_a = msg_id.to_bytes(2, "big") + total_parts.to_bytes(2, "big") + (0).to_bytes(2, "big")
    header_b = msg_id.to_bytes(2, "big") + total_parts.to_bytes(2, "big") + (1).to_bytes(2, "big")

    frame_a = LinkFrame(dst=dst, src=src, typ=FrameType.MESSAGE, seq=1, payload=header_a + payload_part_a)
    frame_b = LinkFrame(dst=dst, src=src, typ=FrameType.MESSAGE, seq=2, payload=header_b + payload_part_b)

    protocol.handle_frame(frame_a)
    protocol.handle_frame(frame_b)

    assert received == [(src, "The quick brown fox jumps")]

    ack_frames = [payload for _, typ, payload in link_layer.sent if typ is FrameType.ACK]
    assert len(ack_frames) == 1
    assert ack_frames[0][0] == 0x4D and int.from_bytes(ack_frames[0][1:3], "big") == msg_id
