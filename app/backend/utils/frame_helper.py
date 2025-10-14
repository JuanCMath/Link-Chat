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
from typing import List, Tuple, Optional
import os, binascii, struct
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

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


_NONCE_LEN = 12
_key_hex = os.getenv("LINKCHAT_PSK", "")
_key = binascii.unhexlify(_key_hex) if _key_hex else b"\x00"*32  # <-- cambia en prod
if len(_key) != 32: raise ValueError("LINKCHAT_PSK debe ser hex de 32 bytes (64 chars).")
_AEAD = ChaCha20Poly1305(_key)
# ------------------------------------------------------



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
    Encode a payload into a framed format with AEAD encryption, CRC validation, and bit stuffing.
    This function takes a raw payload and encodes it into a secure frame format by:
    1. Encrypting the payload using AEAD (Authenticated Encryption with Associated Data)
    2. Adding CRC validation for integrity checking
    3. Applying bit stuffing to prevent flag byte conflicts
    4. Wrapping the result with flag bytes for frame delineation
    Args:
        payload (bytes): The raw data to be encoded and transmitted
        frame_type (int, optional): Type identifier for the frame (0-255). Defaults to 1.
        seq (int, optional): Sequence number for the frame (0-255). Defaults to 0.
    Returns:
        bytes: The complete encoded frame ready for transmission, including:
               - Leading flag byte
               - Bit-stuffed encrypted payload with CRC
               - Trailing flag byte
    Note:
        - Uses a random nonce for each encryption operation
        - Frame type and sequence number are used as Additional Authenticated Data (AAD)
        - The encrypted payload includes both ciphertext and authentication tag
        - Bit stuffing prevents accidental flag byte occurrences in the data
    """

    # --- NUEVO: cifrado AEAD ---
    nonce = os.urandom(_NONCE_LEN)
    aad = struct.pack("!BB", frame_type & 0xFF, seq & 0xFF)
    ct_and_tag = _AEAD.encrypt(nonce, payload, aad)
    enc_payload = nonce + ct_and_tag

    # Build section con CRC como siempre (sobre datos cifrados)
    section = _build_payload_section(frame_type, seq, enc_payload)

    # Bit stuffing y flags como antes
    bits = bytes_to_bits(section)
    stuffed_bits = bit_stuff(bits)
    stuffed_bytes = bits_to_bytes(stuffed_bits)
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
    Decode a framed message from a byte stream with AEAD decryption.
    This function processes a byte stream to extract and decode framed messages.
    It performs the following operations:
    1. Locates frame boundaries using FLAG bytes
    2. Performs bit unstuffing to recover the original frame
    3. Parses the frame header (type, sequence, payload length)
    4. Decrypts the payload using AEAD (Authenticated Encryption with Associated Data)
       - Extracts nonce (first 12 bytes) and ciphertext+tag from encrypted payload
       - Uses frame type and sequence number as Additional Authenticated Data (AAD)
    Args:
        stream (bytes): Raw byte stream containing one or more framed messages
    Returns:
        Tuple[int, int, bytes]: A tuple containing:
            - frame_type (int): Type identifier of the decoded frame
            - seq (int): Sequence number of the frame
            - payload (bytes): Decrypted payload data
    Raises:
        FramingError: When no frame boundaries are found in the stream or
                     no valid frame can be decoded
        FrameError: When bit unstuffing fails or encrypted payload is too short
                   (minimum 28 bytes: 12 bytes nonce + 16 bytes tag)
    Note:
        The function attempts to decode multiple potential frames in the stream
        and returns the first successfully decoded frame. If all attempts fail,
        it raises the last encountered exception.
    """
    boundary_pairs = _find_flag_boundaries(stream)
    if not boundary_pairs:
        raise FramingError("No frame boundaries (FLAG bytes) found in stream")

    last_exception = None

    for start_index, end_index in boundary_pairs:
        stuffed_segment = stream[start_index : end_index + 1]

        try:
            stuffed_bits = bytes_to_bits(stuffed_segment)
            unstuffed_bits = bit_unstuff(stuffed_bits)
        except FrameError as error:
            last_exception = error
            continue

        raw_bytes = bits_to_bytes(unstuffed_bits)

        # Recorte inteligente basado en LENGTH
        if len(raw_bytes) >= 4:
            try:
                ftype_tmp, seq_tmp, payload_length = struct.unpack("!BBH", raw_bytes[0:4])
                expected_section_length = 4 + payload_length + 2
                if len(raw_bytes) >= expected_section_length:
                    raw_bytes = raw_bytes[:expected_section_length]
            except Exception:
                pass

        try:
            frame_type, seq, enc_payload = _parse_payload_section(raw_bytes)

            # --- NUEVO: descifrado AEAD ---
            if len(enc_payload) < _NONCE_LEN + 16:  # 16B = tag
                raise FrameError("Encrypted payload too short")
            nonce = enc_payload[:_NONCE_LEN]
            ct_and_tag = enc_payload[_NONCE_LEN:]
            aad = struct.pack("!BB", frame_type & 0xFF, seq & 0xFF)
            payload = _AEAD.decrypt(nonce, ct_and_tag, aad)

            return frame_type, seq, payload

        except Exception as error:
            last_exception = error
            continue

    if last_exception:
        raise last_exception
    raise FramingError("No valid frame decoded from stream")


def debug_inspect_frame(payload: bytes) -> None:
    """
    Debug helper to inspect frame structure.

    Prints detailed breakdown of: TYPE, SEQ, LEN, CRC received vs calculated.

    Args:
        payload: Raw frame bytes including 0x7E flags.
    """
    

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
    crc_calc = crc16_ccitt_checksum(raw[0 : 4 + length])
    print(
        f"[ft/dbg] TYPE=0x{typ:02x} SEQ={seq} LEN={length} CRC recv=0x{crc_recv:04x} calc=0x{crc_calc:04x}",
        flush=True,
    )

    
def pack_ethernet_frame(
    dst_mac: bytes, src_mac: bytes, ethertype: int, payload: bytes
) -> bytes:
    """
    Construct a complete Ethernet frame from components.

    Builds the standard Ethernet II frame format:
    [DST_MAC(6)] [SRC_MAC(6)] [ETHERTYPE(2)] [PAYLOAD(variable)]

    Args:
        dst_mac: Destination MAC address (6 bytes).
        src_mac: Source MAC address (6 bytes).
        ethertype: EtherType field (0x0800-0xFFFF).
        payload: Frame payload data.

    Returns:
        bytes: Complete Ethernet frame ready for transmission.

    Example:
        >>> frame = pack_ethernet_frame(
        ...     b'\\xff\\xff\\xff\\xff\\xff\\xff',  # broadcast
        ...     b'\\x08\\x00\\'*\\x4a\\x5b\\x6c',
        ...     0x88B5,
        ...     b'Hello'
        ... )
    """
    return dst_mac + src_mac + ethertype.to_bytes(2, "big") + payload


def unpack_ethernet_frame(frame: bytes) -> Optional[Tuple[bytes, bytes, int, bytes]]:
    """
    Parse an Ethernet frame into its constituent parts.

    Extracts fields from Ethernet II format:
    [DST_MAC(6)] [SRC_MAC(6)] [ETHERTYPE(2)] [PAYLOAD(variable)]

    Args:
        frame: Complete Ethernet frame bytes.

    Returns:
        Optional[Tuple[bytes, bytes, int, bytes]]: Tuple of (dst_mac, src_mac,
            ethertype, payload), or None if frame is too short.

    Example:
        >>> dst, src, etype, payload = unpack_ethernet_frame(frame)
        >>> mac_bytes_to_str(src)
        '08:00:27:4a:5b:6c'
    """
    if len(frame) < 14:  # Minimum Ethernet frame header size
        return None

    dst_mac = frame[0:6]
    src_mac = frame[6:12]
    ethertype = int.from_bytes(frame[12:14], "big")
    payload = frame[14:]

    return dst_mac, src_mac, ethertype, payload