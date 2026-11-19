"""Generate the Ghost Foreman app icons (pure Python, no dependencies): ui/m/icon-180.png, icon-192.png, icon-512.png.

    python scripts/make_icons.py
"""

from __future__ import annotations

import math
import os
import struct
import zlib

OUT = os.path.join(os.path.dirname(__file__), "..", "ui", "m")
SS = 3  # supersampling for smooth edges


def render(size: int) -> bytes:
    n = size * SS
    s = n / 512.0  # design space is 512x512
    rows = []
    for py in range(size):
        row = bytearray()
        for px in range(size):
            acc = [0.0, 0.0, 0.0]
            for sy in range(SS):
                for sx in range(SS):
                    x = (px * SS + sx + 0.5) / s
                    y = (py * SS + sy + 0.5) / s
                    c = shade(x, y)
                    acc[0] += c[0]
                    acc[1] += c[1]
                    acc[2] += c[2]
            k = SS * SS
            row += bytes((int(acc[0] / k), int(acc[1] / k), int(acc[2] / k)))
        rows.append(bytes(row))
    return b"".join(b"\x00" + r for r in rows)


def inside_ghost(x: float, y: float) -> bool:
    if (x - 256) ** 2 + (y - 226) ** 2 <= 128**2:  # head
        return True
    if 128 <= x <= 384 and 226 <= y <= 396:  # body
        return True
    for cx in (170.7, 256.0, 341.3):  # scalloped hem
        if (x - cx) ** 2 + (y - 396) ** 2 <= 42.7**2:
            return True
    return False


def shade(x: float, y: float):
    # night-violet background with a soft glow behind the ghost
    d = math.hypot(x - 256, y - 250) / 330.0
    glow = max(0.0, 1.0 - d)
    bg = (13 + 70 * glow * glow, 11 + 40 * glow * glow, 24 + 120 * glow * glow)
    if inside_ghost(x, y):
        # eyes and mouth
        if ((x - 212) / 17) ** 2 + ((y - 236) / 26) ** 2 <= 1 or ((x - 300) / 17) ** 2 + ((y - 236) / 26) ** 2 <= 1:
            return (24, 18, 48)
        if ((x - 256) / 20) ** 2 + ((y - 302) / 24) ** 2 <= 1 and y > 296:
            return (60, 40, 110)
        shade_v = 255 - int(26 * max(0.0, (y - 226) / 200.0))
        return (shade_v, shade_v, 255)
    return bg


def png(size: int) -> bytes:
    raw = render(size)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    # RGB, opaque: iOS fills transparency with black, so the icon carries its own background
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for size in (180, 192, 512):
        path = os.path.join(OUT, f"icon-{size}.png")
        with open(path, "wb") as f:
            f.write(png(size))
        print("wrote", os.path.normpath(path), os.path.getsize(path), "bytes")
