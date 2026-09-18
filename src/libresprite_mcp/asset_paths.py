"""Resolve downstream asset roots without assuming a consuming project."""

from __future__ import annotations

import os
from pathlib import Path

ASSETS_ROOT_ENV = "DOWNSTREAM_ASSETS_ROOT"


def resolve_assets_root(explicit: Path | None = None) -> Path:
    """Return a configured downstream asset root or raise an actionable error."""
    configured = explicit or os.environ.get(ASSETS_ROOT_ENV)
    if not configured:
        raise ValueError(f"an asset root is required: pass --assets-root or set {ASSETS_ROOT_ENV}")

    root = Path(configured).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"asset root does not exist or is not a directory: {root}")
    return root
