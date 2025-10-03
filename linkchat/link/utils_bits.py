# ===== utils_bits.py =====
def bytes_to_bits(b: bytes) -> list[int]:
    return [(byte >> i) & 1 for byte in b for i in range(7, -1, -1)]

def bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits), 8):
        chunk = bits[i:i+8]
        if len(chunk) < 8: break
        val = 0
        for bit in chunk:
            val = (val << 1) | bit
        out.append(val & 0xFF)
    return bytes(out)

def bit_stuff(bits: list[int]) -> list[int]:
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

def bit_unstuff(bits: list[int]) -> list[int]:
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
