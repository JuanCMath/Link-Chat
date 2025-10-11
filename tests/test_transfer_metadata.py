"""Unit tests for transfer metadata module."""

import json
import pytest

from linkchat.link.transfer_metadata import TransferMetadata, ACKPayload


class TestTransferMetadata:
    """Test metadata construction and parsing."""
    
    def test_build_file_metadata(self):
        """build_file_metadata should create valid JSON with type discriminator."""
        payload = TransferMetadata.build_file_metadata(
            name="test.txt",
            size=1024,
            chunks=5,
            file_hash="abc123"
        )
        
        data = json.loads(payload.decode('utf-8'))
        assert data["type"] == "file"
        assert data["name"] == "test.txt"
        assert data["size"] == 1024
        assert data["chunks"] == 5
        assert data["hash"] == "abc123"
    
    def test_build_folder_metadata(self):
        """build_folder_metadata should create valid JSON with files list."""
        files = [("file1.txt", 100), ("subdir/file2.dat", 200)]
        payload = TransferMetadata.build_folder_metadata(root="MyFolder", files=files)
        
        data = json.loads(payload.decode('utf-8'))
        assert data["type"] == "folder"
        assert data["root"] == "MyFolder"
        assert len(data["files"]) == 2
        assert data["files"][0] == {"path": "file1.txt", "size": 100}
        assert data["files"][1] == {"path": "subdir/file2.dat", "size": 200}
    
    def test_parse_metadata_valid(self):
        """parse_metadata should decode valid JSON."""
        payload = b'{"type":"file","name":"test.txt"}'
        result = TransferMetadata.parse_metadata(payload)
        
        assert result is not None
        assert result["type"] == "file"
        assert result["name"] == "test.txt"
    
    def test_parse_metadata_invalid(self):
        """parse_metadata should return None for invalid data."""
        assert TransferMetadata.parse_metadata(b'\xff\xfe invalid') is None
        assert TransferMetadata.parse_metadata(b'not json') is None
    
    def test_validate_file_metadata_valid(self):
        """validate_file_metadata should accept complete file metadata."""
        data = {
            "type": "file",
            "name": "document.pdf",
            "size": 5000,
            "chunks": 4,
            "hash": "deadbeef"
        }
        assert TransferMetadata.validate_file_metadata(data) is True
    
    def test_validate_file_metadata_missing_fields(self):
        """validate_file_metadata should reject incomplete metadata."""
        assert TransferMetadata.validate_file_metadata({"type": "file"}) is False
        assert TransferMetadata.validate_file_metadata({
            "type": "file",
            "name": "test.txt",
            "size": 100
            # missing chunks and hash
        }) is False
    
    def test_validate_file_metadata_wrong_type(self):
        """validate_file_metadata should reject folder metadata."""
        data = {"type": "folder", "root": "Test"}
        assert TransferMetadata.validate_file_metadata(data) is False
    
    def test_validate_folder_metadata_valid(self):
        """validate_folder_metadata should accept complete folder metadata."""
        data = {
            "type": "folder",
            "root": "MyFolder",
            "files": [{"path": "a.txt", "size": 10}]
        }
        assert TransferMetadata.validate_folder_metadata(data) is True
    
    def test_validate_folder_metadata_invalid(self):
        """validate_folder_metadata should reject invalid metadata."""
        assert TransferMetadata.validate_folder_metadata({"type": "folder"}) is False
        assert TransferMetadata.validate_folder_metadata({
            "type": "folder",
            "root": 123,  # should be string
            "files": []
        }) is False


class TestACKPayload:
    """Test ACK payload construction and parsing."""
    
    def test_build_metadata_ack(self):
        """build_metadata_ack should prefix name with 0x4D marker."""
        payload = ACKPayload.build_metadata_ack("test.txt")
        
        assert payload[0] == 0x4D
        assert payload[1:].decode('utf-8') == "test.txt"
    
    def test_build_chunk_ack(self):
        """build_chunk_ack should encode chunk_id and filename."""
        payload = ACKPayload.build_chunk_ack(chunk_id=42, filename="data.bin")
        
        chunk_id = int.from_bytes(payload[:4], 'big')
        filename = payload[4:].decode('utf-8')
        
        assert chunk_id == 42
        assert filename == "data.bin"
    
    def test_parse_ack_metadata(self):
        """parse_ack should identify metadata ACKs."""
        payload = b'\x4D' + b'test.txt'
        result = ACKPayload.parse_ack(payload)
        
        assert result is not None
        identifier, chunk_id_or_meta = result
        assert identifier == "test.txt"
        assert chunk_id_or_meta == "meta"
    
    def test_parse_ack_chunk(self):
        """parse_ack should identify chunk ACKs."""
        payload = (7).to_bytes(4, 'big') + b'file.dat'
        result = ACKPayload.parse_ack(payload)
        
        assert result is not None
        identifier, chunk_id_or_meta = result
        assert identifier == "file.dat"
        assert chunk_id_or_meta == 7
    
    def test_parse_ack_empty(self):
        """parse_ack should return None for empty payload."""
        assert ACKPayload.parse_ack(b'') is None
    
    def test_parse_ack_invalid_utf8(self):
        """parse_ack should return None for invalid UTF-8."""
        payload = b'\x4D' + b'\xff\xfe'
        assert ACKPayload.parse_ack(payload) is None
    
    def test_parse_ack_chunk_no_filename(self):
        """parse_ack should handle chunk ACK without filename."""
        payload = (99).to_bytes(4, 'big')
        result = ACKPayload.parse_ack(payload)
        
        assert result is not None
        identifier, chunk_id_or_meta = result
        assert identifier == ""
        assert chunk_id_or_meta == 99
