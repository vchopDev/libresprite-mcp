"""Sprite operations, each a thin JS script handed to LibreSprite headlessly.

Architecture note: every LibreSprite invocation is a fresh subprocess (see
`client.py`) -- there is no persistent "active document" across tool calls,
only across statements within a single script. So every tool here is
path-in/path-out: open the file, mutate it, save it, return. Callers treat
a sprite as a file on disk, not a session handle.

`create_sprite` and `resize_canvas` use the sprite/document object model
directly (confirmed working headlessly). Pixel colors use LibreSprite's
native RGBA packing helpers through `app.pixelColor` (see the design notes
for the older binary compatibility detail).
"""

from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path

from libresprite_mcp.client import LibreSpriteClient, LibreSpriteError
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


def get_pixel(
    client: LibreSpriteClient,
    path: str,
    x: int,
    y: int,
    layer: int = 0,
    frame: int = 0,
) -> dict[str, int]:
    """Read one pixel as an RGBA mapping from a layer/frame."""
    if layer < 0 or frame < 0:
        raise ValueError("layer and frame must be non-negative")

    script = f"""
    var doc = app.open({_js_string(path)});
    if (!doc) throw new Error("app.open() returned no document");
    var cel = doc.sprite.layer({layer}).cel({frame});
    if (!cel) throw new Error("no cel at layer {layer}, frame {frame}");
    var image = cel.image;
    if ({x} < 0 || {y} < 0 || {x} >= image.width || {y} >= image.height)
        throw new Error("pixel coordinates out of bounds");
    var pc = app.pixelColor;
    if (!pc && typeof pixelColor !== "undefined") pc = pixelColor;
    if (!pc) throw new Error("pixelColor API unavailable");
    var color = image.getPixel({x}, {y});
    console.log(JSON.stringify({{
        r: pc.rgbaR(color), g: pc.rgbaG(color), b: pc.rgbaB(color), a: pc.rgbaA(color)
    }}));
    """
    output = client.run_script(script)
    try:
        result = json.loads(output.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise LibreSpriteError(f"unexpected getPixel() output: {output[-120:]!r}") from exc
    return {channel: int(result[channel]) for channel in ("r", "g", "b", "a")}


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
    """Write one RGBA pixel to a layer/frame and save the sprite in place."""
    if layer < 0 or frame < 0:
        raise ValueError("layer and frame must be non-negative")
    for name, value in (("r", r), ("g", g), ("b", b), ("a", a)):
        if not isinstance(value, int) or not 0 <= value <= 255:
            raise ValueError(f"{name} must be an integer from 0 to 255")

    script = f"""
    var doc = app.open({_js_string(path)});
    if (!doc) throw new Error("app.open() returned no document");
    var cel = doc.sprite.layer({layer}).cel({frame});
    if (!cel) throw new Error("no cel at layer {layer}, frame {frame}");
    var image = cel.image;
    if ({x} < 0 || {y} < 0 || {x} >= image.width || {y} >= image.height)
        throw new Error("pixel coordinates out of bounds");
    var pc = app.pixelColor;
    if (!pc && typeof pixelColor !== "undefined") pc = pixelColor;
    if (!pc) throw new Error("pixelColor API unavailable");
    image.putPixel({x}, {y}, pc.rgba({r}, {g}, {b}, {a}));
    doc.sprite.saveAs({_js_string(path)}, false);
    console.log("OK");
    """
    client.run_script(script)
    return path


def set_pixels_bulk(
    client: LibreSpriteClient,
    path: str,
    data_b64: str,
    layer: int = 0,
    frame: int = 0,
) -> str:
    """Write one layer/frame's raw image buffer from base64-encoded bytes."""
    if layer < 0 or frame < 0:
        raise ValueError("layer and frame must be non-negative")
    try:
        base64.b64decode(data_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("data_b64 must be valid base64") from exc

    script = f"""
    var doc = app.open({_js_string(path)});
    if (!doc) throw new Error("app.open() returned no document");
    var cel = doc.sprite.layer({layer}).cel({frame});
    if (!cel) throw new Error("no cel at layer {layer}, frame {frame}");
    var image = cel.image;
    var encoded = {_js_string(data_b64)};
    var alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    var bytes = [];
    var buffer = 0;
    var bits = 0;
    for (var i = 0; i < encoded.length; i++) {{
        var ch = encoded.charAt(i);
        if (ch === "=") break;
        var value = alphabet.indexOf(ch);
        if (value < 0) throw new Error("invalid base64 data");
        buffer = (buffer << 6) | value;
        bits += 6;
        if (bits >= 8) {{
            bits -= 8;
            bytes.push((buffer >> bits) & 255);
        }}
    }}
    var data = new Uint8Array(bytes);
    var expected = image.stride * image.height;
    if (data.length !== expected)
        throw new Error("data length must equal image stride * height");
    image.putImageData(data);
    doc.sprite.saveAs({_js_string(path)}, false);
    console.log("OK");
    """
    client.run_script(script)
    return path
