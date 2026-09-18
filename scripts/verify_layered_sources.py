"""Verify layer names on the generated production .ase sources."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from libresprite_mcp.asset_paths import resolve_assets_root
from libresprite_mcp.client import LibreSpriteClient

CATEGORIES = ("ui", "terrain", "resources", "buildings", "units", "fx")
VERSIONED = re.compile(r"_v\d+\.\d+\.\d+(_f\d\d)?\.ase$")


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
        for path in (root / category).glob("*.ase")
        if VERSIONED.search(path.name)
    ]
    client = LibreSpriteClient()
    expected_base = ["base", "outline", "shade", "highlight"]
    checked = 0
    for path in sorted(files):
        script = (
            f"var doc=app.open({json.dumps(str(path))});"
            'if(!doc) throw new Error("open failed");'
            "var names=[];"
            "for(var i=0;i<doc.sprite.layerCount;i++) names.push(doc.sprite.layer(i).name);"
            "console.log(JSON.stringify(names));"
        )
        output = client.run_script(script).strip().splitlines()[-1]
        names = json.loads(output)
        if names[:4] != expected_base:
            raise RuntimeError(f"{path}: unexpected layers {names}")
        if path.parent.name == "units" or path.name.startswith("town_hall_"):
            if names[-1] != "accent":
                raise RuntimeError(f"{path}: missing accent layer {names}")
        checked += 1
    print(f"layered_sources_checked={checked}")


if __name__ == "__main__":
    main()
