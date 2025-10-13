# frame_helper.py
from __future__ import annotations
from typing import List, Tuple
import struct

FLAG = 0x7E

class FrameError(Exception): ...
class FramingError(FrameError): ...
class CRCError(FrameError): ...

def crc16_ccitt(data: bytes, poly: int = 0x1021, init: int = 0xFFFF) -> int:
    crc = init
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if (crc & 0x8000) != 0:
                crc = ((crc << 1) & 0xFFFF) ^ poly
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF

def bytes_to_bits(b: bytes) -> List[int]:
    bits: List[int] = []
    for byte in b:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits

def bits_to_bytes(bits: List[int]) -> bytes:
    pad = (-len(bits)) % 8
    if pad:
        bits = bits + [0]*pad
    out = bytearray()
    for i in range(0, len(bits), 8):
        val = 0
        for j in range(8):
            val = (val << 1) | (bits[i+j] & 1)
        out.append(val)
    return bytes(out)

def bit_stuff(bits: List[int]) -> List[int]:
    out: List[int] = []
    ones = 0
    for bit in bits:
        out.append(bit)
        if bit == 1:
            ones += 1
            if ones == 5:
                out.append(0)
                ones = 0
        else:
            ones = 0
    return out

def bit_unstuff(bits: List[int]) -> List[int]:
    out: List[int] = []
    ones = 0
    i = 0
    n = len(bits)
    while i < n:
        bit = bits[i]
        out.append(bit)
        if bit == 1:
            ones += 1
            if ones == 5:
                i += 1
                if i >= n:
                    raise FramingError("Bit-unstuff: stuffed bit esperado pero fin de stream")
                stuffed = bits[i]
                if stuffed != 0:
                    raise FramingError("Bit-unstuff: stuffed bit no era 0")
                ones = 0
        else:
            ones = 0
        i += 1
    return out

def _build_payload_section(frame_type: int, seq: int, payload: bytes) -> bytes:
    if not (0 <= frame_type <= 0xFF): raise ValueError("frame_type 0..255")
    if not (0 <= seq <= 0xFF): raise ValueError("seq 0..255")
    if len(payload) > 0xFFFF: raise ValueError("payload > 65535")
    header = struct.pack("!BBH", frame_type & 0xFF, seq & 0xFF, len(payload))
    body = header + payload
    crc = crc16_ccitt(body)
    tail = struct.pack("!H", crc)
    return body + tail

def _parse_payload_section(data: bytes) -> Tuple[int,int,bytes]:
    if len(data) < 6:
        raise FramingError("payload section too small")
    frame_type, seq, length = struct.unpack("!BBH", data[0:4])
    expected_len = 4 + length + 2
    if len(data) != expected_len:
        raise FramingError(f"length mismatch {len(data)} != {expected_len}")
    payload = data[4:4+length]
    crc_recv = struct.unpack("!H", data[4+length:4+length+2])[0]
    crc_calc = crc16_ccitt(data[0:4+length])
    if crc_recv != crc_calc:
        raise CRCError(f"CRC mismatch recv=0x{crc_recv:04x} calc=0x{crc_calc:04x}")
    return frame_type, seq, payload

def encode_frame(payload: bytes, frame_type: int = 1, seq: int = 0) -> bytes:
    section = _build_payload_section(frame_type, seq, payload)
    bits = bytes_to_bits(section)
    stuffed = bit_stuff(bits)
    stuffed_bytes = bits_to_bytes(stuffed)
    return bytes([FLAG]) + stuffed_bytes + bytes([FLAG])

def _find_flag_boundaries(stream: bytes):
    idx = [i for i,b in enumerate(stream) if b == FLAG]
    pairs = []
    if len(idx) < 2: return pairs
    for i in range(len(idx)-1):
        a, b = idx[i], idx[i+1]
        if b - a <= 1:
            continue
        pairs.append((a+1, b-1))
    return pairs

def decode_frame(stream: bytes) -> Tuple[int,int,bytes]:
    pairs = _find_flag_boundaries(stream)
    if not pairs:
        raise FramingError("no flag boundaries found")
    last_exc = None
    for (start, end) in pairs:
        segment = stream[start:end+1]  # bytes entre banderas (stuffed)
        try:
            unstuffed_bits = bytes_to_bits(segment)
            unstuffed = bit_unstuff(unstuffed_bits)
        except FrameError as e:
            last_exc = e
            continue

        raw = bits_to_bytes(unstuffed)

        # 🔽🔽🔽 NOVEDAD: recorte “inteligente” según header (por si quedó padding)
        if len(raw) >= 4:
            try:
                frame_type, seq, length = struct.unpack("!BBH", raw[0:4])
                expected_len = 4 + length + 2  # header + payload + crc
                if len(raw) >= expected_len:
                    raw = raw[:expected_len]    # recorta padding sobrante
            except Exception as e:
                # si por alguna razón falla el unpack, dejamos que _parse decida
                pass
        # 🔼🔼🔼

        try:
            return _parse_payload_section(raw)
        except FrameError as e:
            last_exc = e
            continue
    if last_exc:
        raise last_exc
    raise FramingError("no valid frame decoded")

