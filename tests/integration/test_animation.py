import json
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


@pytest.fixture
def animation_api(client, workdir):
    """Skip animation tests when CI provisions an upstream binary without C9 bindings."""
    probe = workdir / "animation-api-probe.png"
    probe.write_bytes(blank_png(1, 1, (0, 0, 0, 255)))
    result = client.run_script(
        f"""
        var doc=app.open({json.dumps(str(probe.resolve()))});
        if(!doc) throw new Error("could not open animation API probe");
        var sprite=doc.sprite;
        console.log("animation_api_available=" + (
            typeof sprite.newLayer === "function" &&
            typeof sprite.addEmptyFrame === "function" &&
            typeof sprite.removeFrame === "function" &&
            typeof sprite.removeLayer === "function" &&
            typeof sprite.setFrameDuration === "function" &&
            typeof sprite.addTag === "function"
        ));
        """
    )
    if "animation_api_available=true" not in result:
        pytest.skip("configured LibreSprite binary does not expose the C9 animation bindings")


def test_assemble_animation_roundtrip(client, workdir, animation_api):
    frames = []
    for index, color in enumerate(((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255))):
        frame = workdir / f"frame-{index}.png"
        frame.write_bytes(blank_png(4, 4, color))
        frames.append(frame)

    output = workdir / "animation.ase"
    assemble_animation(client, frames, output, [80, 100, 120], tag_name="walk")
    assert output.is_file()


def test_duplicate_cel_failure_is_reported(client, workdir, animation_api):
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
