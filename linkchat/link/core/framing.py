"""Frame encoding and decoding with checksums and bit stuffing.

Provides functions to encode data into frames with headers, checksums, and
bit stuffing for synchronization. Supports frame decoding with validation.
"""

from ..utils.checksum import checksum16_ones_complement, verify_checksum
from ..utils.utils_bits import bytes_to_bits, bits_to_bytes, bit_stuff, bit_unstuff

FLAG = 0x7E

def build_header(dst: bytes, src: bytes, typ: int, seq: int, payload: bytes) -> bytes:
    """Construct a frame header.
    
    Builds a header containing destination MAC, source MAC, frame type,
    sequence number, and payload length.
    
    Args:
        dst: Destination MAC address (6 bytes).
        src: Source MAC address (6 bytes).
        typ: Frame type code (1 byte).
        seq: Sequence number (0-65535).
        payload: Frame payload (used only for length calculation).
    
    Returns:
        Encoded header bytes (17 bytes total).
    
    Raises:
        AssertionError: If MAC addresses are not exactly 6 bytes.
    """
    assert len(dst) == 6 and len(src) == 6
    typ_b = bytes([typ & 0xFF])
    seq_b = seq.to_bytes(2, 'big')
    length_b = len(payload).to_bytes(2, 'big')
    return dst + src + typ_b + seq_b + length_b

def frame_encode(dst: bytes, src: bytes, typ: int, seq: int, payload: bytes) -> bytes:
    """Encode data into a complete frame with header, checksum, and bit stuffing.
    
    Constructs a frame by:
    1. Building the header (dst, src, type, seq, length).
    2. Computing a 16-bit ones' complement checksum over header + payload.
    3. Converting to bits and applying bit stuffing.
    4. Adding FLAG delimiters at both ends.
    
    Args:
        dst: Destination MAC address (6 bytes).
        src: Source MAC address (6 bytes).
        typ: Frame type code.
        seq: Sequence number.
        payload: Frame payload data.
    
    Returns:
        Encoded frame bytes ready for transmission.
    """
    
    header = build_header(dst, src, typ, seq, payload)
    chk = checksum16_ones_complement(header + payload).to_bytes(2, 'big')
    raw = header + payload + chk  # bytes before stuffing
    bits = bytes_to_bits(raw)
    stuffed = bit_stuff(bits)
    framed = bytes([FLAG]) + bits_to_bytes(stuffed) + bytes([FLAG])
    return framed

def frame_decode(frame: bytes):
    """Decode a received frame and validate its integrity.
    
    Performs the inverse of frame_encode:
    1. Strips FLAG delimiters.
    2. Removes bit stuffing.
    3. Parses header fields.
    4. Verifies checksum.
    5. Validates payload length.
    
    Args:
        frame: Received frame bytes (must start and end with FLAG).
    
    Returns:
        Tuple of (dst, src, typ, seq, payload).
    
    Raises:
        ValueError: If frame format is invalid, checksum fails, or length mismatches.
    """
    if not (frame and frame[0] == FLAG and frame[-1] == FLAG):
        raise ValueError("FLAG error")
    inner = frame[1:-1]
    bits = bytes_to_bits(inner)
    bits = bit_unstuff(bits)
    raw = bits_to_bytes(bits)

    # Minimum frame size: dst_mac(6) + src_mac(6) + type(1) + seq(2) + length(2) + checksum(2) = 19 bytes
    if len(raw) < (6+6+1+2+2+2): 
        raise ValueError("Frame too short")

    # parse header
    i = 0
    dst = raw[i:i+6]; i += 6
    src = raw[i:i+6]; i += 6
    typ = raw[i]; i += 1
    seq = int.from_bytes(raw[i:i+2], 'big'); i += 2
    length = int.from_bytes(raw[i:i+2], 'big'); i += 2
    payload = raw[i:i+length]; i += length
    chk_recv = int.from_bytes(raw[i:i+2], 'big'); i += 2
    # validate lengths
    if i != len(raw):
        raise ValueError("LEN mismatch")
    # verify checksum
    if not verify_checksum(dst+src+bytes([typ])+seq.to_bytes(2,'big')+length.to_bytes(2,'big')+payload, chk_recv):
        raise ValueError("Checksum error")
    return dst, src, typ, seq, payload
