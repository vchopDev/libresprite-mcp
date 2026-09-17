"""Subprocess wrapper around `libresprite -b --script <file>`.

LibreSprite exits 0 even when the JS script throws (confirmed empirically:
an uncaught `ReferenceError` still produces exit code 0, with the error
text only on stderr). Callers must not rely on the return code alone --
`run_script` scans stderr for LibreSprite's own error markers and raises.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT = 30.0
_ERROR_MARKERS = ("ReferenceError", "TypeError", "SyntaxError", "Error: [")


class LibreSpriteError(RuntimeError):
    """Raised when the LibreSprite subprocess fails or the script throws."""


def resolve_binary(explicit: str | None = None) -> str:
    """Find the LibreSprite executable.

    Resolution order: explicit argument, `LIBRESPRITE_BIN` env var, `PATH`.
    """
    candidate = explicit or os.environ.get("LIBRESPRITE_BIN")
    if candidate:
        if not Path(candidate).exists():
            raise LibreSpriteError(f"LIBRESPRITE_BIN does not exist: {candidate}")
        return candidate

    found = shutil.which("libresprite") or shutil.which("libresprite.exe")
    if not found:
        raise LibreSpriteError(
            "Could not find a LibreSprite binary. Set LIBRESPRITE_BIN or add it to PATH."
        )
    return found


class LibreSpriteClient:
    def __init__(self, binary: str | None = None, timeout: float = DEFAULT_TIMEOUT):
        self.binary = resolve_binary(binary)
        self.timeout = timeout

    def run_script(self, script: str) -> str:
        """Run `script` (JS source) headlessly and return stdout."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", delete=False, encoding="utf-8"
        ) as f:
            f.write(script)
            script_path = f.name

        try:
            result = subprocess.run(
                [self.binary, "-b", "--script", script_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        finally:
            Path(script_path).unlink(missing_ok=True)

        if result.returncode != 0:
            raise LibreSpriteError(
                f"LibreSprite exited {result.returncode}: {result.stderr.strip()}"
            )
        if any(marker in result.stderr for marker in _ERROR_MARKERS):
            raise LibreSpriteError(f"Script error: {result.stderr.strip()}")

        return result.stdout
