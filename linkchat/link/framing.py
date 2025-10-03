from checksum import checksum16_ones_complement, verify_checksum
from utils_bits import bytes_to_bits, bits_to_bytes, bit_stuff, bit_unstuff
import utils_bits

# ===== framing.py =====
FLAG = 0x7E

def build_header(dst: bytes, src: bytes, typ: int, seq: int, payload: bytes) -> bytes:
    assert len(dst) == 6 and len(src) == 6
    typ_b = bytes([typ & 0xFF])
    seq_b = seq.to_bytes(2, 'big')
    length_b = len(payload).to_bytes(2, 'big')
    return dst + src + typ_b + seq_b + length_b

def frame_encode(dst: bytes, src: bytes, typ: int, seq: int, payload: bytes) -> bytes:
    
    header = build_header(dst, src, typ, seq, payload)
    chk = checksum16_ones_complement(header + payload).to_bytes(2, 'big')
    raw = header + payload + chk  # bytes before stuffing
    bits = bytes_to_bits(raw)
    stuffed = bit_stuff(bits)
    framed = bytes([FLAG]) + bits_to_bytes(stuffed) + bytes([FLAG])
    return framed

def frame_decode(frame: bytes):
    # strip FLAGS
    if not (frame and frame[0] == FLAG and frame[-1] == FLAG):
        raise ValueError("FLAG error")
    inner = frame[1:-1]
    bits = bytes_to_bits(inner)
    bits = bit_unstuff(bits)
    raw = bits_to_bytes(bits)
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
