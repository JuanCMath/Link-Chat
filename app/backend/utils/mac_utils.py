"""
mac_utils.py
~~~~~~~~~~~~

MAC address conversion and validation utilities.

This module provides helper functions for converting MAC addresses between
different representations (string and bytes) and validating MAC address formats.

Utilities:
    - MAC_ADDRESS_PATTERN: Regex for validating colon-separated MAC addresses
    - BROADCAST_MAC_BYTES: Constant for broadcast address (FF:FF:FF:FF:FF:FF)
    - mac_str_to_bytes(): Convert "aa:bb:cc:dd:ee:ff" to bytes
    - mac_bytes_to_str(): Convert bytes to "aa:bb:cc:dd:ee:ff"

Example:
    >>> from app.backend.utils.mac_utils import mac_str_to_bytes, mac_bytes_to_str
    >>> mac_bytes = mac_str_to_bytes("08:00:27:4a:5b:6c")
    >>> mac_str = mac_bytes_to_str(mac_bytes)
    >>> print(mac_str)
    '08:00:27:4a:5b:6c'
"""

import re

# Regex pattern for validating MAC address format (case-insensitive)
MAC_ADDRESS_PATTERN = re.compile(r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$")

# Broadcast MAC address (FF:FF:FF:FF:FF:FF)
BROADCAST_MAC_BYTES = b"\xff\xff\xff\xff\xff\xff"


def mac_str_to_bytes(mac_address: str) -> bytes:
    """
    Convert MAC address from colon-separated string to bytes.

    Args:
        mac_address: MAC in format "AA:BB:CC:DD:EE:FF" (case-insensitive).

    Returns:
        bytes: 6-byte MAC address.

    Example:
        >>> mac_str_to_bytes("08:00:27:4a:5b:6c")
        b'\\x08\\x00\\'*\\x4a\\x5b\\x6c'
    """
    return bytes(int(part, 16) for part in mac_address.split(":"))


def mac_bytes_to_str(mac_bytes: bytes) -> str:
    """
    Convert MAC address from bytes to colon-separated lowercase string.

    Args:
        mac_bytes: 6-byte MAC address.

    Returns:
        str: MAC in format "aa:bb:cc:dd:ee:ff".

    Example:
        >>> mac_bytes_to_str(b'\\x08\\x00\\'*\\x4a\\x5b\\x6c')
        '08:00:27:4a:5b:6c'
    """
    return ":".join(f"{byte:02x}" for byte in mac_bytes)
