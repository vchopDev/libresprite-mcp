"""Blank RGBA PNG generation.

LibreSprite's scripting API has no headless equivalent of "new sprite" (the
`NewFile` command, like every other `app.command.*` call, is a no-op in
batch mode -- see docs/Design-Notes in the project history). Instead we
write a minimal PNG ourselves and hand it to `app.open()`, which does work
headlessly. No image library dependency: a flat-color RGBA PNG is a few
dozen bytes of stdlib zlib/struct.
"""

from __future__ import annotations

import struct
import zlib


def _chunk(tag: bytes, data: bytes) -> bytes:
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def blank_png(width: int, height: int, rgba: tuple[int, int, int, int] = (0, 0, 0, 0)) -> bytes:
    """Return PNG bytes for a `width`x`height` image filled with `rgba`."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")

    r, g, b, a = rgba
    row = bytes([0]) + bytes((r, g, b, a)) * width
    raw = row * height

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(raw, level=6)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")
