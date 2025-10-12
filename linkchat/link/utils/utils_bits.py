"""Helpers for working with bit-level representations.

All conversions keep the most significant bit first within each byte, which
matches how the framing module builds on top of them.
"""

from pathlib import Path
from typing import List, Union


def bytes_to_bits(data: bytes) -> List[int]:
    """Convert bytes to a list of bits (MSB first).
    
    Each byte is expanded into 8 bits, with the most significant bit (MSB) 
    appearing first in the output list. This ordering is compatible with the 
    framing module.
    
    Args:
        data: Raw bytes to convert.
    
    Returns:
        List of integers (0 or 1) representing the bit sequence.
    """
    return [(byte >> i) & 1 for byte in data for i in range(7, -1, -1)]


def bits_to_bytes(bits: List[int]) -> bytes:
    """Pack a list of bits (MSB first) into bytes.
    
    Converts a sequence of bits into bytes, treating the most significant bit 
    as the first element in each 8-bit chunk. Any trailing bits that do not 
    form a complete byte are silently discarded.
    
    Args:
        bits: List of integers (0 or 1) representing the bit sequence.
    
    Returns:
        Packed bytes formed from the input bits.
    """
    out = bytearray()
    for i in range(0, len(bits), 8):
        chunk = bits[i : i + 8]
        if len(chunk) < 8:
            break
        val = 0
        for bit in chunk:
            val = (val << 1) | bit
        out.append(val & 0xFF)
    return bytes(out)


def string_to_bits(text: str, *, encoding: str = "utf-8", errors: str = "strict") -> List[int]:
    """Encode a string and return its bit representation.
    
    The text is first encoded into bytes using the specified encoding, then 
    converted to a list of bits via bytes_to_bits.
    
    Args:
        text: The string to encode.
        encoding: Character encoding to use (default: 'utf-8').
        errors: Error handling strategy (default: 'strict').
    
    Returns:
        List of bits (0 or 1) representing the encoded string.
    """
    return bytes_to_bits(text.encode(encoding, errors))


def bits_to_string(bits: List[int], *, encoding: str = "utf-8", errors: str = "strict") -> str:
    """Decode a list of bits into a string.
    
    Converts bits to bytes (discarding any incomplete trailing byte), then 
    decodes the result into a string using the specified encoding.
    
    Args:
        bits: List of integers (0 or 1) representing the bit sequence.
        encoding: Character encoding to use for decoding (default: 'utf-8').
        errors: Error handling strategy (default: 'strict').
    
    Returns:
        The decoded string.
    """
    return bits_to_bytes(bits).decode(encoding, errors)


def file_to_bits(path: Union[str, Path]) -> List[int]:
    """Read a file and return its contents as a list of bits.
    
    Opens the file at the given path, reads all bytes, and converts them 
    into a bit sequence (MSB first).
    
    Args:
        path: File path as a string or Path object.
    
    Returns:
        List of bits (0 or 1) representing the file contents.
    """
    data = Path(path).read_bytes()
    return bytes_to_bits(data)


def bits_to_file(bits: List[int], path: Union[str, Path]) -> None:
    """Write a list of bits to a file as bytes.
    
    Converts the bit sequence into bytes (discarding any incomplete trailing 
    byte) and writes the result to the specified file path.
    
    Args:
        bits: List of integers (0 or 1) representing the bit sequence.
        path: Destination file path as a string or Path object.
    """
    Path(path).write_bytes(bits_to_bytes(bits))


def bit_stuff(bits: List[int]) -> List[int]:
    """Apply bit stuffing to prevent long runs of ones.
    
    Inserts a zero bit after every sequence of five consecutive ones. This 
    technique is commonly used in data link protocols to maintain clock 
    synchronization and to differentiate data from frame delimiters.
    
    Args:
        bits: List of integers (0 or 1) representing the original bit sequence.
    
    Returns:
        Bit-stuffed sequence with zeros inserted after runs of five ones.
    """
    out, ones = [], 0
    for b in bits:
        out.append(b)
        if b == 1:
            ones += 1
            if ones == 5:
                out.append(0)  # insert stuffed 0
                ones = 0
        else:
            ones = 0
    return out


def bit_unstuff(bits: List[int]) -> List[int]:
    """Remove bit stuffing by discarding zeros after five consecutive ones.
    
    Reverses the bit stuffing operation performed by bit_stuff. After detecting 
    five consecutive ones, the next bit (expected to be a stuffed zero) is 
    skipped, restoring the original data sequence.
    
    Args:
        bits: Bit-stuffed sequence (list of 0s and 1s).
    
    Returns:
        Original bit sequence with stuffed zeros removed.
    """
    out, ones = [], 0
    i = 0
    while i < len(bits):
        b = bits[i]
        out.append(b)
        if b == 1:
            ones += 1
            if ones == 5:
                i += 1  # skip stuffed 0
                ones = 0
        else:
            ones = 0
        i += 1
    return out
