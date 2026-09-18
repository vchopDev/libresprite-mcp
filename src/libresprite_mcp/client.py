"""Subprocess wrapper around ``libresprite -b --script <file>``.

LibreSprite exits 0 even when the JS script throws (confirmed empirically:
an uncaught ``ReferenceError`` still produces exit code 0, with the error
text only on stderr). Callers must not rely on the return code alone --
``run_script`` scans stderr for LibreSprite's own error markers and raises.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path

DEFAULT_TIMEOUT = 30.0
_ERROR_MARKERS = (
    "ReferenceError",
    "TypeError",
    "SyntaxError",
    "InternalError",
    "Error:",
    "Error: [",
)
_WINDOWS_ERROR_MODE = 0x8001  # SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX
_NATIVE_EXIT_CODES = {
    0xC0000135: (
        "STATUS_DLL_NOT_FOUND",
        "the process never started because Windows could not load a required DLL; "
        "deploy the LibreSprite runtime DLLs beside the executable",
    ),
    0xC0000005: (
        "STATUS_ACCESS_VIOLATION",
        "LibreSprite reached native code and crashed with an access violation",
    ),
    0xC0000015: (
        "STATUS_NONEXISTENT_SECTOR",
        "the executable appears broken or incomplete",
    ),
}


class LibreSpriteError(RuntimeError):
    """Raised when the LibreSprite subprocess fails or the script throws."""


def _suppress_windows_crash_dialog() -> None:
    """Prevent native LibreSprite crashes from opening a blocking Windows dialog."""
    if os.name == "nt":
        ctypes.windll.kernel32.SetErrorMode(_WINDOWS_ERROR_MODE)


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


def _unsigned_status(returncode: int) -> int:
    """Normalize signed and unsigned Windows process status values."""
    return returncode & 0xFFFFFFFF


def _format_process_failure(returncode: int, stderr: str) -> str:
    """Turn a subprocess exit into an actionable LibreSprite error."""
    status = _unsigned_status(returncode)
    hex_status = f"0x{status:08X}"
    native = _NATIVE_EXIT_CODES.get(status)
    detail = stderr.strip()
    if native:
        name, explanation = native
        message = f"LibreSprite exited {returncode} ({hex_status}, {name}): {explanation}."
        if detail:
            message += f" Native stderr: {detail}"
        return message
    message = f"LibreSprite exited {returncode} ({hex_status})."
    if detail:
        message += f" Stderr: {detail}"
    return message


class LibreSpriteClient:
    def __init__(
        self,
        binary: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        environment: Mapping[str, str] | None = None,
    ):
        self.binary = resolve_binary(binary)
        self.timeout = timeout
        self.environment = self._build_environment(environment)
        self._preflight()

    @staticmethod
    def _build_environment(overrides: Mapping[str, str] | None) -> dict[str, str]:
        """Build the explicit environment used by every LibreSprite process.

        The caller can provide APPDATA/LOCALAPPDATA explicitly (the MCP host
        does this for its project-local profile). For direct terminal usage,
        default both locations to a repository-local profile so batch mode
        cannot try to write the user's GUI profile.
        """
        environment = os.environ.copy()
        if overrides:
            environment.update(overrides)
        appdata = environment.get("APPDATA") or environment.get("LIBRESPRITE_APPDATA")
        if not appdata:
            appdata = str(Path.cwd() / ".libresprite-appdata")
        environment.setdefault("APPDATA", appdata)
        environment.setdefault("LOCALAPPDATA", appdata)
        return environment

    def _run_process(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run LibreSprite with the same explicit environment every time."""
        try:
            return subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=self.environment,
            )
        except FileNotFoundError as exc:
            raise LibreSpriteError(
                f"LibreSprite binary cannot be launched: {self.binary}. "
                "Check LIBRESPRITE_BIN and deploy the runtime DLLs beside it."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise LibreSpriteError(
                f"LibreSprite did not finish within {self.timeout:g}s during startup "
                "or script execution."
            ) from exc

    def _preflight(self) -> None:
        """Fail once, early, if the configured executable cannot start."""
        result = self._run_process([self.binary, "--version"])
        if result.returncode != 0:
            raise LibreSpriteError(
                "LibreSprite binary found but cannot launch. "
                + _format_process_failure(result.returncode, result.stderr)
            )

    def run_script(self, script: str) -> str:
        """Run `script` (JS source) headlessly and return stdout."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", delete=False, encoding="utf-8"
        ) as f:
            f.write(script)
            script_path = f.name

        try:
            _suppress_windows_crash_dialog()
            result = self._run_process([self.binary, "-b", "--script", script_path])
        finally:
            Path(script_path).unlink(missing_ok=True)

        if result.returncode != 0:
            raise LibreSpriteError(_format_process_failure(result.returncode, result.stderr))
        diagnostics = "\n".join(part for part in (result.stderr, result.stdout) if part)
        if any(marker in diagnostics for marker in _ERROR_MARKERS):
            raise LibreSpriteError(f"Script error: {diagnostics.strip()}")

        return result.stdout
