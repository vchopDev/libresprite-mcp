import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from libresprite_mcp.client import LibreSpriteClient, LibreSpriteError
from libresprite_mcp.seed import blank_png
from scripts.assemble_animation import assemble_animation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("LIBRESPRITE_BIN"), reason="LIBRESPRITE_BIN not set"),
]


@pytest.fixture
def workdir():
    path = Path.cwd() / ".tmp" / f"integration-animation-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def client() -> LibreSpriteClient:
    return LibreSpriteClient()


def test_assemble_animation_roundtrip(client, workdir):
    frames = []
    for index, color in enumerate(((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255))):
        frame = workdir / f"frame-{index}.png"
        frame.write_bytes(blank_png(4, 4, color))
        frames.append(frame)

    output = workdir / "animation.ase"
    assemble_animation(client, frames, output, [80, 100, 120], tag_name="walk")
    assert output.is_file()


def test_duplicate_cel_failure_is_reported(client, workdir):
    frame = workdir / "frame.png"
    frame.write_bytes(blank_png(4, 4, (1, 2, 3, 255)))
    script = f"""
    var doc=app.open({frame.as_posix()!r});
    var sprite=doc.sprite;
    sprite.addEmptyFrame(1);
    var layer=sprite.newLayer("duplicate-test");
    sprite.removeLayer(sprite.layer(0));
    layer=sprite.layer(0);
    layer.addCel(0);
    layer.addCel(0);
    """

    with pytest.raises(LibreSpriteError, match="cel"):
        client.run_script(script)
