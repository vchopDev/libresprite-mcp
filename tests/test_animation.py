import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from libresprite_mcp.client import LibreSpriteError
from scripts.assemble_animation import assemble_animation, parse_durations


@pytest.fixture
def workdir():
    path = Path.cwd() / ".tmp" / f"test-animation-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_parse_durations_requires_one_value_per_frame():
    with pytest.raises(ValueError, match="expected 3 durations"):
        parse_durations("100,200", 3, 100)


def test_parse_durations_rejects_out_of_range_values():
    with pytest.raises(ValueError, match="between 1 and 65535"):
        parse_durations("0,100", 2, 100)


def test_assembly_propagates_add_cel_failure(workdir):
    frame = workdir / "frame.png"
    frame.write_bytes(b"fixture")
    output = workdir / "animation.ase"

    class DuplicateCelClient:
        def run_script(self, script: str) -> str:
            assert "targetLayer.addCel(frameIndex)" in script
            raise LibreSpriteError("addCel: layer already has a cel at that frame")

    with pytest.raises(LibreSpriteError, match="already has a cel"):
        assemble_animation(DuplicateCelClient(), [frame], output, [100])
