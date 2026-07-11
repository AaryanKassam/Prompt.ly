"""Generate solid-color PNG icons for the Prompt Report extension."""
import struct
import zlib
import os


def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
    raw = chunk_type + data
    return struct.pack('>I', len(data)) + raw + struct.pack('>I', zlib.crc32(raw) & 0xFFFFFFFF)


def create_png(width: int, height: int, r: int, g: int, b: int) -> bytes:
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = make_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    rows = b''.join(b'\x00' + bytes([r, g, b] * width) for _ in range(height))
    idat = make_chunk(b'IDAT', zlib.compress(rows, 9))
    iend = make_chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


os.makedirs('icons', exist_ok=True)

# Brand color: #2a78d6 (blue slot-1 from the dataviz palette)
R, G, B = 0x2A, 0x78, 0xD6

for size in (16, 48, 128):
    path = f'icons/icon{size}.png'
    with open(path, 'wb') as f:
        f.write(create_png(size, size, R, G, B))
    print(f'Created {path}')
