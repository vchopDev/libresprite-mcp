"""Create revision-friendly layered .ase sources from production PNGs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from libresprite_mcp.asset_paths import resolve_assets_root
from libresprite_mcp.client import LibreSpriteClient

CATEGORIES = ("ui", "terrain", "resources", "buildings", "units", "fx")
VERSIONED = re.compile(r"_v\d+\.\d+\.\d+(_f\d\d)?\.png$")


def js_string(value: str) -> str:
    return json.dumps(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--assets-root",
        type=Path,
        help="Downstream assets/art directory (or set DOWNSTREAM_ASSETS_ROOT).",
    )
    args = parser.parse_args()
    try:
        root = resolve_assets_root(args.assets_root)
    except ValueError as exc:
        parser.error(str(exc))
    files = [
        path
        for category in CATEGORIES
        for path in (root / category).glob("*.png")
        if VERSIONED.search(path.name)
    ]
    client = LibreSpriteClient()
    created = 0
    for path in sorted(files):
        layer_names = ["base", "outline", "shade", "highlight"]
        if path.parent.name == "units" or path.name.startswith("town_hall_"):
            layer_names.append("accent")
        new_layers = "".join(f"spr.newLayer({js_string(name)});" for name in layer_names[1:])
        output = path.with_suffix(".ase")
        script = (
            f"var doc=app.open({js_string(str(path))});"
            'if(!doc) throw new Error("open failed");'
            "var spr=doc.sprite;"
            'spr.layer(0).name="base";'
            f"{new_layers}"
            f"spr.saveAs({js_string(str(output))}, true);"
            'console.log("OK");'
        )
        client.run_script(script)
        created += 1
    print(f"layered_sources={created}")


if __name__ == "__main__":
    main()
