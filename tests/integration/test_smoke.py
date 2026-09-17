"""End-to-end tests against a real LibreSprite binary.

Skipped unless LIBRESPRITE_BIN points at an actual executable -- these are
not runnable on a dev machine without LibreSprite installed, and CI
provisions the binary before running this file (see .github/workflows/ci.yml).
"""

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
