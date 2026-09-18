"""End-to-end tests against a real LibreSprite binary.

Skipped unless LIBRESPRITE_BIN points at an actual executable -- these are
not runnable on a dev machine without LibreSprite installed, and CI
provisions the binary before running this file (see .github/workflows/ci.yml).
"""

import base64
import os

import pytest

from libresprite_mcp import tools
from libresprite_mcp.client import LibreSpriteClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("LIBRESPRITE_BIN"), reason="LIBRESPRITE_BIN not set"),
]


@pytest.fixture
def client() -> LibreSpriteClient:
    return LibreSpriteClient()


def test_create_sprite_roundtrip(client, tmp_path):
    sprite_path = str(tmp_path / "sprite.ase")
    tools.create_sprite(client, sprite_path, width=8, height=8)
    assert os.path.exists(sprite_path)


def test_resize_canvas(client, tmp_path):
    sprite_path = str(tmp_path / "sprite.ase")
    tools.create_sprite(client, sprite_path, width=8, height=8)
    tools.resize_canvas(client, sprite_path, width=16, height=16)

    png_path = str(tmp_path / "out.png")
    tools.export_png(client, sprite_path, png_path)
    with open(png_path, "rb") as f:
        data = f.read()
    # PNG IHDR width/height are big-endian uint32 at fixed offsets.
    import struct

    width, height = struct.unpack(">II", data[16:24])
    assert (width, height) == (16, 16)


def test_get_png_data(client, tmp_path):
    sprite_path = str(tmp_path / "sprite.ase")
    tools.create_sprite(client, sprite_path, width=4, height=4)
    b64 = tools.get_png_data_b64(client, sprite_path)
    assert isinstance(b64, str) and len(b64) > 0


def test_pixel_roundtrip(client, tmp_path):
    sprite_path = str(tmp_path / "sprite.ase")
    tools.create_sprite(client, sprite_path, width=4, height=4)

    tools.set_pixel(client, sprite_path, x=1, y=2, r=17, g=34, b=51, a=68)
    assert tools.get_pixel(client, sprite_path, x=1, y=2) == {
        "r": 17,
        "g": 34,
        "b": 51,
        "a": 68,
    }


def test_set_pixel_rejects_invalid_channel(client, tmp_path):
    sprite_path = str(tmp_path / "sprite.ase")
    with pytest.raises(ValueError, match="r must be"):
        tools.set_pixel(client, sprite_path, x=0, y=0, r=256, g=0, b=0)


def test_set_pixels_bulk_roundtrip(client, tmp_path):
    sprite_path = str(tmp_path / "sprite.ase")
    tools.create_sprite(client, sprite_path, width=2, height=2)
    raw = bytes(
        (
            11,
            22,
            33,
            44,
            55,
            66,
            77,
            88,
            91,
            92,
            93,
            94,
            95,
            96,
            97,
            98,
        )
    )

    tools.set_pixels_bulk(client, sprite_path, base64.b64encode(raw).decode("ascii"))
    assert tools.get_pixel(client, sprite_path, x=0, y=0) == {
        "r": 11,
        "g": 22,
        "b": 33,
        "a": 44,
    }


def test_set_pixels_bulk_rejects_invalid_base64(client, tmp_path):
    with pytest.raises(ValueError, match="valid base64"):
        tools.set_pixels_bulk(client, str(tmp_path / "sprite.ase"), "not base64!")
