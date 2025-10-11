"""Unit tests for transfer reliability module."""

import threading
import time
from typing import List, Tuple

import pytest

from linkchat.link.link_layer import FrameType, LinkFrame
from linkchat.link.transfer_reliability import ReliableTransfer


class _MockLinkLayer:
    """Mock LinkLayer for testing reliability mechanisms."""
    
    def __init__(self):
        self.sent: List[Tuple[bytes, FrameType, bytes]] = []
        self.send_count: int = 0
        
    def send(self, dst: bytes, typ: FrameType, payload: bytes) -> None:
        self.sent.append((dst, typ, payload))
        self.send_count += 1


class TestReliableTransfer:
    """Test ACK/retry reliability mechanisms."""
    
    def test_send_metadata_reliable_success(self):
        """send_metadata_reliable should succeed when ACK received promptly."""
        link_layer = _MockLinkLayer()
        reliable = ReliableTransfer(
            link_layer=link_layer,  # type: ignore
            ack_timeout=0.5,
            max_retries=3
        )
        
        dst = b'\xaa' * 6
        transfer_name = "test.txt"
        meta_payload = b'{"type":"file","name":"test.txt"}'
        
        # Send in background
        def sender():
            result = reliable.send_metadata_reliable(dst, transfer_name, meta_payload)
            assert result is True
        
        thread = threading.Thread(target=sender, daemon=True)
        thread.start()
        
        # Wait for send to register event
        time.sleep(0.05)
        
        # Signal ACK received
        reliable.signal_ack(dst, transfer_name, "meta")
        
        thread.join(timeout=1.0)
        assert not thread.is_alive()
        
        # Should have sent TRANSFER_META frame
        assert len(link_layer.sent) == 1
        assert link_layer.sent[0][1] == FrameType.TRANSFER_META
    
    def test_send_metadata_reliable_timeout(self):
        """send_metadata_reliable should retry on timeout."""
        link_layer = _MockLinkLayer()
        reliable = ReliableTransfer(
            link_layer=link_layer,  # type: ignore
            ack_timeout=0.1,
            max_retries=2
        )
        
        dst = b'\xbb' * 6
        result = reliable.send_metadata_reliable(dst, "test.txt", b'{}')
        
        # Should fail after retries
        assert result is False
        # Should have sent max_retries times
        assert link_layer.send_count == 2
    
    def test_send_chunk_reliable_success(self):
        """send_chunk_reliable should succeed when ACK received."""
        link_layer = _MockLinkLayer()
        reliable = ReliableTransfer(
            link_layer=link_layer,  # type: ignore
            ack_timeout=0.5,
            max_retries=3
        )
        
        dst = b'\xcc' * 6
        filename = "data.bin"
        chunk_id = 5
        chunk_data = b'chunk payload'
        
        def sender():
            result = reliable.send_chunk_reliable(dst, filename, chunk_id, chunk_data)
            assert result is True
        
        thread = threading.Thread(target=sender, daemon=True)
        thread.start()
        
        time.sleep(0.05)
        reliable.signal_ack(dst, filename, chunk_id)
        
        thread.join(timeout=1.0)
        assert not thread.is_alive()
        
        assert len(link_layer.sent) == 1
        assert link_layer.sent[0][1] == FrameType.FILE_CHUNK
    
    def test_send_chunk_reliable_retries(self):
        """send_chunk_reliable should retry on timeout."""
        link_layer = _MockLinkLayer()
        reliable = ReliableTransfer(
            link_layer=link_layer,  # type: ignore
            ack_timeout=0.05,
            max_retries=3
        )
        
        dst = b'\xdd' * 6
        result = reliable.send_chunk_reliable(dst, "file.txt", 0, b'data')
        
        assert result is False
        assert link_layer.send_count == 3
    
    def test_signal_ack_wrong_key(self):
        """signal_ack with wrong parameters should not unblock waiting thread."""
        link_layer = _MockLinkLayer()
        reliable = ReliableTransfer(
            link_layer=link_layer,  # type: ignore
            ack_timeout=0.2,
            max_retries=1
        )
        
        dst = b'\xee' * 6
        
        def sender():
            # This will timeout
            result = reliable.send_metadata_reliable(dst, "correct.txt", b'{}')
            assert result is False
        
        thread = threading.Thread(target=sender, daemon=True)
        thread.start()
        
        time.sleep(0.05)
        # Signal ACK for different file
        reliable.signal_ack(dst, "wrong.txt", "meta")
        
        thread.join(timeout=1.0)
        assert not thread.is_alive()
    
    def test_metadata_and_chunk_acks_isolated(self):
        """Metadata ACK should not affect chunk ACK and vice versa."""
        link_layer = _MockLinkLayer()
        reliable = ReliableTransfer(
            link_layer=link_layer,  # type: ignore
            ack_timeout=0.3,
            max_retries=2
        )
        
        dst = b'\xff' * 6
        filename = "test.txt"
        
        # Start metadata send (will timeout)
        def meta_sender():
            result = reliable.send_metadata_reliable(dst, filename, b'{}')
            # Will fail because we signal chunk ACK instead
            assert result is False
        
        thread = threading.Thread(target=meta_sender, daemon=True)
        thread.start()
        
        time.sleep(0.05)
        # Signal chunk ACK instead of metadata ACK
        reliable.signal_ack(dst, filename, 0)  # chunk_id=0
        
        thread.join(timeout=1.0)
        assert not thread.is_alive()
