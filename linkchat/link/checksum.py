"""16-bit ones' complement checksum for frame integrity verification.

Provides checksum calculation and verification functions compatible with
standard internet checksums (RFC 1071).
"""

def checksum16_ones_complement(data: bytes) -> int:
    """Compute 16-bit ones' complement checksum.
    
    Calculates the checksum by summing 16-bit words with carry wraparound,
    then taking the ones' complement of the result. Automatically pads odd-length
    data with a zero byte.
    
    Args:
        data: Bytes to checksum.
    
    Returns:
        16-bit checksum value (0x0000-0xFFFF).
    """
    if len(data) % 2 == 1:
        data += b'\x00'
    s = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i+1]
        s += word
        s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF

def verify_checksum(data: bytes, chk_field: int) -> bool:
    """Verify data integrity using a 16-bit ones' complement checksum.
    
    Sums the data plus the checksum field. A valid checksum produces a total
    of 0xFFFF after carry wraparound.
    
    Args:
        data: Data bytes to verify.
        chk_field: Received checksum value.
    
    Returns:
        True if checksum is valid, False otherwise.
    """
    total = 0
    if len(data) % 2 == 1:
        data += b'\x00'
    for i in range(0, len(data), 2):
        total += (data[i] << 8) + data[i+1]
        total = (total & 0xFFFF) + (total >> 16)
    total += chk_field
    total = (total & 0xFFFF) + (total >> 16)
    return total == 0xFFFF
