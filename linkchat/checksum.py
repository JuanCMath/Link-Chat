# ===== checksum.py =====
def checksum16_ones_complement(data: bytes) -> int:
    # pad odd
    if len(data) % 2 == 1:
        data += b'\x00'
    s = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i+1]
        s += word
        s = (s & 0xFFFF) + (s >> 16)  # carry wrap
    return (~s) & 0xFFFF

def verify_checksum(data: bytes, chk_field: int) -> bool:
    # Sum data + chk; válido si da 0xFFFF
    total = 0
    if len(data) % 2 == 1:
        data += b'\x00'
    for i in range(0, len(data), 2):
        total += (data[i] << 8) + data[i+1]
        total = (total & 0xFFFF) + (total >> 16)
    total += chk_field
    total = (total & 0xFFFF) + (total >> 16)
    return total == 0xFFFF
