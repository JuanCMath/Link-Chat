"""
Utility Functions
~~~~~~~~~~~~~~~~~

Helper utilities for frame processing, MAC handling, and file operations.

This package contains reusable utility functions that support the core
networking and peer management modules.

Modules:
    frame_helper: Frame encoding/decoding with CRC16-CCITT and bit stuffing
    mac_utils: MAC address conversion (bytes ↔ string) and validation
    services: Archive creation for directory transfers and MAC resolution

Features:
    - CRC16-CCITT checksum calculation for error detection
    - Bit stuffing/unstuffing for frame delimitation (0x7E flags)
    - MAC address format validation with regex
    - Tar.gz archive creation for directory transfers
    - Temporary file cleanup tracking

Example:
    >>> from app.backend.utils.mac_utils import mac_str_to_bytes, mac_bytes_to_str
    >>> from app.backend.utils.frame_helper import encode_frame, decode_frame
    >>> 
    >>> mac_bytes = mac_str_to_bytes("aa:bb:cc:dd:ee:ff")
    >>> frame = encode_frame(b"Hello", frame_type=0x01, sequence=0)
"""
