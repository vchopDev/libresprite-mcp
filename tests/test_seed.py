import struct
import zlib

import pytest

from libresprite_mcp.seed import blank_png


def _decode_ihdr(png: bytes) -> tuple[int, int]:
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    length = struct.unpack(">I", png[8:12])[0]
    assert png[12:16] == b"IHDR"
    width, height = struct.unpack(">II", png[16:24])
    assert length == 13
    return width, height


def test_blank_png_dimensions():
    png = blank_png(8, 4)
    assert _decode_ihdr(png) == (8, 4)


def test_blank_png_is_valid_zlib_stream():
    png = blank_png(2, 2, rgba=(10, 20, 30, 255))
    idat_start = png.index(b"IDAT") + 4
    idat_len = struct.unpack(">I", png[idat_start - 8 : idat_start - 4])[0]
    idat = png[idat_start : idat_start + idat_len]
    raw = zlib.decompress(idat)
    # 2 rows, each: 1 filter byte + 2 pixels * 4 channels
    assert len(raw) == 2 * (1 + 2 * 4)
    first_pixel = raw[1:5]
    assert first_pixel == bytes((10, 20, 30, 255))


def test_blank_png_rejects_non_positive_size():
    with pytest.raises(ValueError):
        blank_png(0, 4)
