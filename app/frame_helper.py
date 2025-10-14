"""
frame_helper.py
~~~~~~~~~~~~~~~

Ethernet frame encoding/decoding with CRC validation and bit stuffing.

This module implements a robust framing protocol for binary data transmission
over raw Ethernet. It provides:
    - CRC16-CCITT error detection
    - Flag-based frame delimitation (0x7E)
    - Bit stuffing to prevent flag conflicts in payload
    - Frame type and sequence number support

Frame Structure:
    [FLAG] [stuffed(TYPE|SEQ|LENGTH|PAYLOAD|CRC)] [FLAG]
    
    Unstuffed payload section:
    - TYPE (1 byte): Frame type identifier
    - SEQ (1 byte): Sequence number (0-255)
    - LENGTH (2 bytes): Payload length in bytes
    - PAYLOAD (variable): Actual data
    - CRC (2 bytes): CRC16-CCITT checksum of TYPE through PAYLOAD

Bit Stuffing Rule:
    After 5 consecutive 1-bits, insert a 0-bit. Receiver removes these stuffed bits.
    This ensures FLAG (0x7E = 01111110) never appears in the payload.

Typical Usage:
    >>> frame = encode_frame(b"Hello", frame_type=0x10, seq=42)
    >>> frame_type, seq, payload = decode_frame(frame)
"""

import struct
from typing import List, Tuple

# Frame delimiter byte (01111110 binary)
FLAG_BYTE = 0x7E


class FrameError(Exception):
    """Base exception for all frame processing errors."""

    pass


class FramingError(FrameError):
    """Raised when frame structure is invalid (missing flags, bad stuffing, etc.)."""

    pass


class CRCError(FrameError):
    """Raised when CRC validation fails, indicating corrupted data."""

    pass


def crc16_ccitt_checksum(data: bytes, polynomial: int = 0x1021, initial_value: int = 0xFFFF) -> int:
    """
    Compute CRC-16-CCITT checksum for error detection.

    Implements the CCITT polynomial (0x1021) with standard initial value (0xFFFF).
    This is a widely-used CRC variant for telecommunications.

    Args:
        data: Input bytes to checksum.
        polynomial: CRC polynomial (default: 0x1021).
        initial_value: Starting CRC register value (default: 0xFFFF).

    Returns:
        int: 16-bit CRC value (0x0000-0xFFFF).

    Example:
        >>> crc = crc16_ccitt(b"Hello")
        >>> hex(crc)
        '0x...'
    """
    crc = initial_value
    for byte_val in data:
        crc ^= byte_val << 8  # XOR byte into high byte of CRC
        for _ in range(8):
            if (crc & 0x8000) != 0:  # If MSB is set
                crc = ((crc << 1) & 0xFFFF) ^ polynomial
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def bytes_to_bits(data: bytes) -> List[int]:
    """
    Convert byte sequence to list of individual bits (MSB first).

    Args:
        data: Input bytes.

    Returns:
        List[int]: Bits as 0/1 integers, MSB first for each byte.

    Example:
        >>> bytes_to_bits(b'\\x7E')
        [0, 1, 1, 1, 1, 1, 1, 0]
    """
    bits: List[int] = []
    for byte_val in data:
        for bit_index in range(7, -1, -1):  # MSB to LSB
            bits.append((byte_val >> bit_index) & 1)
    return bits


def bits_to_bytes(bits: List[int]) -> bytes:
    """
    Convert list of bits back to bytes (MSB first).

    Automatically pads with zeros if bit count is not a multiple of 8.

    Args:
        bits: List of 0/1 integers.

    Returns:
        bytes: Converted byte sequence.

    Example:
        >>> bits_to_bytes([0, 1, 1, 1, 1, 1, 1, 0])
        b'~'
    """
    # Pad to multiple of 8 bits
    padding = (-len(bits)) % 8
    if padding:
        bits = bits + [0] * padding

    output = bytearray()
    for byte_start in range(0, len(bits), 8):
        byte_val = 0
        for bit_offset in range(8):
            byte_val = (byte_val << 1) | (bits[byte_start + bit_offset] & 1)
        output.append(byte_val)
    return bytes(output)


def bit_stuff(bits: List[int]) -> List[int]:
    """
    Apply bit stuffing: insert 0 after every 5 consecutive 1-bits.

    This prevents the FLAG pattern (0x7E = 01111110) from appearing in the payload,
    ensuring frame boundaries remain unambiguous.

    Args:
        bits: Input bit sequence.

    Returns:
        List[int]: Stuffed bit sequence with inserted zeros.

    Example:
        >>> bit_stuff([1,1,1,1,1,0])  # 5 ones followed by 0
        [1,1,1,1,1,0,0]  # 0 inserted after 5th one
    """
    output: List[int] = []
    consecutive_ones = 0

    for bit in bits:
        output.append(bit)
        if bit == 1:
            consecutive_ones += 1
            if consecutive_ones == 5:
                # Insert stuffed zero
                output.append(0)
                consecutive_ones = 0
        else:
            consecutive_ones = 0

    return output


def bit_unstuff(bits: List[int]) -> List[int]:
    """
    Remove bit stuffing: delete 0-bit after every 5 consecutive 1-bits.

    Reverses the bit_stuff operation. Raises FramingError if stuffing is malformed.

    Args:
        bits: Stuffed bit sequence.

    Returns:
        List[int]: Original bit sequence with stuffed bits removed.

    Raises:
        FramingError: If expected stuffed 0-bit is missing or incorrect.

    Example:
        >>> bit_unstuff([1,1,1,1,1,0,0])  # 5 ones, stuffed 0, data 0
        [1,1,1,1,1,0]
    """
    output: List[int] = []
    consecutive_ones = 0
    index = 0
    length = len(bits)

    while index < length:
        bit = bits[index]
        output.append(bit)

        if bit == 1:
            consecutive_ones += 1
            if consecutive_ones == 5:
                # Next bit must be stuffed zero
                index += 1
                if index >= length:
                    raise FramingError(
                        "Bit unstuffing failed: expected stuffed bit but reached end of stream"
                    )
                stuffed_bit = bits[index]
                if stuffed_bit != 0:
                    raise FramingError(
                        "Bit unstuffing failed: stuffed bit was not 0"
                    )
                consecutive_ones = 0
        else:
            consecutive_ones = 0

        index += 1

    return output


def _build_payload_section(frame_type: int, seq: int, payload: bytes) -> bytes:
    """
    Build the complete payload section with header and CRC.

    Internal helper that constructs: [TYPE|SEQ|LENGTH|PAYLOAD|CRC]

    Args:
        frame_type: Frame type identifier (0-255).
        seq: Sequence number (0-255).
        payload: Data bytes to frame.

    Returns:
        bytes: Complete section ready for bit stuffing.

    Raises:
        ValueError: If parameters are out of valid range.
    """
    if not (0 <= frame_type <= 0xFF):
        raise ValueError("frame_type must be 0-255")
    if not (0 <= seq <= 0xFF):
        raise ValueError("seq must be 0-255")
    if len(payload) > 0xFFFF:
        raise ValueError("payload exceeds maximum length (65535 bytes)")

    # Pack header: TYPE(1) + SEQ(1) + LENGTH(2)
    header = struct.pack("!BBH", frame_type & 0xFF, seq & 0xFF, len(payload))
    body = header + payload

    # Calculate CRC over header + payload
    crc = crc16_ccitt_checksum(body)
    crc_bytes = struct.pack("!H", crc)

    return body + crc_bytes


def _parse_payload_section(data: bytes) -> Tuple[int, int, bytes]:
    """
    Parse and validate a payload section, verifying CRC.

    Internal helper that extracts: TYPE, SEQ, PAYLOAD from [TYPE|SEQ|LENGTH|PAYLOAD|CRC]

    Args:
        data: Complete section bytes (header + payload + CRC).

    Returns:
        Tuple[int, int, bytes]: (frame_type, seq, payload)

    Raises:
        FramingError: If section structure is invalid.
        CRCError: If CRC validation fails.
    """
    if len(data) < 6:  # Minimum: 1+1+2+0+2 = 6 bytes
        raise FramingError("Payload section too small (< 6 bytes)")

    # Unpack header
    frame_type, seq, payload_length = struct.unpack("!BBH", data[0:4])

    # Validate total length
    expected_total_length = 4 + payload_length + 2  # header + payload + CRC
    if len(data) != expected_total_length:
        raise FramingError(
            f"Length mismatch: got {len(data)} bytes, expected {expected_total_length}"
        )

    # Extract payload
    payload = data[4 : 4 + payload_length]

    # Extract and verify CRC
    received_crc = struct.unpack("!H", data[4 + payload_length : 4 + payload_length + 2])[0]
    calculated_crc = crc16_ccitt_checksum(data[0 : 4 + payload_length])

    if received_crc != calculated_crc:
        raise CRCError(
            f"CRC validation failed: received=0x{received_crc:04x}, "
            f"calculated=0x{calculated_crc:04x}"
        )

    return frame_type, seq, payload


def encode_frame(payload: bytes, frame_type: int = 1, seq: int = 0) -> bytes:
    """
    Encode payload into a complete frame with flags, stuffing, and CRC.

    This is the main encoding function. It:
    1. Builds the payload section with CRC
    2. Converts to bits and applies bit stuffing
    3. Wraps with FLAG bytes

    Args:
        payload: Data to transmit.
        frame_type: Frame type identifier (default: 1).
        seq: Sequence number (default: 0).

    Returns:
        bytes: Complete frame ready for transmission: [FLAG][stuffed data][FLAG]

    Example:
        >>> frame = encode_frame(b"Hello World", frame_type=0x10, seq=5)
        >>> frame[0] == 0x7E and frame[-1] == 0x7E
        True
    """
    # Build section with CRC
    section = _build_payload_section(frame_type, seq, payload)

    # Convert to bits and apply stuffing
    bits = bytes_to_bits(section)
    stuffed_bits = bit_stuff(bits)
    stuffed_bytes = bits_to_bytes(stuffed_bits)

    # Wrap with flags
    return bytes([FLAG_BYTE]) + stuffed_bytes + bytes([FLAG_BYTE])


def _find_flag_boundaries(stream: bytes) -> List[Tuple[int, int]]:
    """
    Locate all valid frame boundaries marked by FLAG bytes.

    Internal helper that finds pairs of FLAG bytes with content between them.

    Args:
        stream: Raw byte stream potentially containing multiple frames.

    Returns:
        List[Tuple[int, int]]: List of (start, end) indices for content between flags.
                               Indices exclude the FLAG bytes themselves.

    Example:
        >>> stream = b'\\x7E\\x01\\x02\\x7E\\x7E\\x03\\x04\\x7E'
        >>> _find_flag_boundaries(stream)
        [(1, 2), (5, 6)]  # Two frames found
    """
    flag_indices = [i for i, byte_val in enumerate(stream) if byte_val == FLAG_BYTE]
    boundary_pairs = []

    if len(flag_indices) < 2:
        return boundary_pairs

    for i in range(len(flag_indices) - 1):
        start_flag, end_flag = flag_indices[i], flag_indices[i + 1]

        # Skip consecutive flags (no content between them)
        if end_flag - start_flag <= 1:
            continue

        # Content is between the flags (exclusive)
        boundary_pairs.append((start_flag + 1, end_flag - 1))

    return boundary_pairs


def decode_frame(stream: bytes) -> Tuple[int, int, bytes]:
    """
    Decode a frame from a byte stream, validating CRC and unstuffing.

    This is the main decoding function. It:
    1. Finds FLAG-delimited frame boundaries
    2. Attempts to unstuff each candidate frame
    3. Validates CRC and extracts payload
    4. Returns the first valid frame found

    Args:
        stream: Raw bytes containing one or more frames.

    Returns:
        Tuple[int, int, bytes]: (frame_type, seq, payload) of first valid frame.

    Raises:
        FramingError: If no valid frame boundaries found or all frames invalid.
        CRCError: If all candidate frames fail CRC validation.

    Note:
        Automatically handles padding added during bit-to-byte conversion by
        trimming to expected length based on the LENGTH field.

    Example:
        >>> frame = encode_frame(b"Test", frame_type=0x10, seq=3)
        >>> frame_type, seq, payload = decode_frame(frame)
        >>> payload
        b'Test'
    """
    boundary_pairs = _find_flag_boundaries(stream)
    if not boundary_pairs:
        raise FramingError("No frame boundaries (FLAG bytes) found in stream")

    last_exception = None

    # Try each potential frame
    for start_index, end_index in boundary_pairs:
        stuffed_segment = stream[start_index : end_index + 1]

        # Attempt to unstuff
        try:
            stuffed_bits = bytes_to_bits(stuffed_segment)
            unstuffed_bits = bit_unstuff(stuffed_bits)
        except FrameError as error:
            last_exception = error
            continue

        raw_bytes = bits_to_bytes(unstuffed_bits)

        # Smart trimming: remove padding based on LENGTH field
        # This handles padding added during bits_to_bytes conversion
        if len(raw_bytes) >= 4:
            try:
                frame_type, seq, payload_length = struct.unpack("!BBH", raw_bytes[0:4])
                expected_section_length = 4 + payload_length + 2  # header + payload + CRC

                if len(raw_bytes) >= expected_section_length:
                    # Trim to exact expected length, removing padding
                    raw_bytes = raw_bytes[:expected_section_length]
            except Exception:
                # If header parsing fails, let _parse_payload_section handle it
                pass

        # Attempt to parse and validate
        try:
            return _parse_payload_section(raw_bytes)
        except FrameError as error:
            last_exception = error
            continue

    # If we get here, no valid frame was decoded
    if last_exception:
        raise last_exception
    raise FramingError("No valid frame decoded from stream")
