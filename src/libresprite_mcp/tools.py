"""Sprite operations, each a thin JS script handed to LibreSprite headlessly.

Architecture note: every LibreSprite invocation is a fresh subprocess (see
`client.py`) -- there is no persistent "active document" across tool calls,
only across statements within a single script. So every tool here is
path-in/path-out: open the file, mutate it, save it, return. Callers treat
a sprite as a file on disk, not a session handle.

`create_sprite` and `resize_canvas` use the sprite/document object model
directly (confirmed working headlessly). `get_pixel`/`set_pixel` are NOT
implemented yet -- they need `pixelColor`'s packing helpers (see
`pixelcolor_script.cpp` upstream) to convert between (r, g, b, a) and
LibreSprite's native `color_t`, which hasn't been spiked yet. Track that
work under the "pixel read/write" issue before filling these in.
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from libresprite_mcp.client import LibreSpriteClient
from libresprite_mcp.seed import blank_png


def _js_string(value: str) -> str:
    """Escape a Python string for embedding as a JS string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def create_sprite(client: LibreSpriteClient, path: str, width: int, height: int) -> str:
    """Create a new blank sprite at `path` (extension picked by caller, e.g. .ase/.png)."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(blank_png(width, height))
        seed_path = f.name

    try:
        script = f"""
        var doc = app.open({_js_string(seed_path)});
        if (!doc) throw new Error("app.open() returned no document");
        doc.sprite.saveAs({_js_string(path)}, false);
        console.log("OK");
        """
        client.run_script(script)
    finally:
        Path(seed_path).unlink(missing_ok=True)

    return path


def resize_canvas(client: LibreSpriteClient, path: str, width: int, height: int) -> str:
    """Resize `path`'s sprite in place."""
    script = f"""
    var doc = app.open({_js_string(path)});
    if (!doc) throw new Error("app.open() returned no document");
    doc.sprite.resize({width}, {height});
    doc.sprite.saveAs({_js_string(path)}, false);
    console.log("OK");
    """
    client.run_script(script)
    return path


def export_png(client: LibreSpriteClient, path: str, out_path: str) -> str:
    """Flatten and export `path` to `out_path` (PNG) via pure CLI conversion.

    Deliberately not scripted: LibreSprite's `-b <in> --save-as <out>` batch
    conversion flattens all visible layers correctly without us having to
    reimplement layer compositing over the `image` script API.
    """
    import subprocess

    result = subprocess.run(
        [client.binary, "-b", path, "--save-as", out_path],
        capture_output=True,
        text=True,
        timeout=client.timeout,
    )
    if result.returncode != 0:
        from libresprite_mcp.client import LibreSpriteError

        raise LibreSpriteError(f"export failed ({result.returncode}): {result.stderr.strip()}")
    return out_path


def get_png_data_b64(client: LibreSpriteClient, path: str, layer: int = 0, frame: int = 0) -> str:
    """Return base64 PNG data (no data-URI prefix) for one layer/frame's image."""
    script = f"""
    var doc = app.open({_js_string(path)});
    if (!doc) throw new Error("app.open() returned no document");
    var cel = doc.sprite.layer({layer}).cel({frame});
    if (!cel) throw new Error("no cel at layer {layer}, frame {frame}");
    console.log(cel.image.getPNGData());
    """
    output = client.run_script(script)
    line = output.strip().splitlines()[-1]
    prefix = "data:image/png;base64,"
    if not line.startswith(prefix):
        from libresprite_mcp.client import LibreSpriteError

        raise LibreSpriteError(f"unexpected getPNGData() output: {line[:80]!r}")
    return line[len(prefix) :]


def get_png_bytes(client: LibreSpriteClient, path: str, layer: int = 0, frame: int = 0) -> bytes:
    return base64.b64decode(get_png_data_b64(client, path, layer=layer, frame=frame))


def get_pixel(client: LibreSpriteClient, path: str, x: int, y: int, layer: int = 0, frame: int = 0):
    raise NotImplementedError(
        "Needs pixelColor packing/unpacking -- see the 'pixel read/write' issue."
    )


def set_pixel(
    client: LibreSpriteClient,
    path: str,
    x: int,
    y: int,
    r: int,
    g: int,
    b: int,
    a: int = 255,
    layer: int = 0,
    frame: int = 0,
) -> str:
    raise NotImplementedError(
        "Needs pixelColor packing/unpacking -- see the 'pixel read/write' issue."
    )
