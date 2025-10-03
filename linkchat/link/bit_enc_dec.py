#archivo -> bit
def file_to_bits(path: str) -> list[int]:
    with open(path, "rb") as f:
        data = f.read()          # lee todo el archivo en bytes
    bits = [(byte >> i) & 1 for byte in data for i in range(7, -1, -1)]
    return bits


#string -> bit
def string_to_bits(s: str) -> list[int]:
    data = s.encode("utf-8")
    return [(byte >> i) & 1 for byte in data for i in range(7, -1, -1)]


#bit -> X
def bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits), 8):
        chunk = bits[i:i+8]
        if len(chunk) < 8:
            break
        val = 0
        for bit in chunk:
            val = (val << 1) | bit
        out.append(val)
    return bytes(out)

# Guardar otra vez en archivo
bits = file_to_bits("ejemplo.pdf")
data = bits_to_bytes(bits)
with open("recuperado.pdf", "wb") as f:
    f.write(data)



