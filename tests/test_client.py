import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from libresprite_mcp.client import LibreSpriteClient, LibreSpriteError


def _completed(returncode: int, *, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["libresprite.exe"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


@pytest.fixture
def workdir():
    path = Path.cwd() / ".tmp" / f"test-client-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_preflight_reports_missing_runtime_dll(monkeypatch, workdir):
    binary = workdir / "libresprite.exe"
    binary.write_bytes(b"placeholder")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _completed(0xC0000135),
    )

    with pytest.raises(LibreSpriteError, match="STATUS_DLL_NOT_FOUND") as error:
        LibreSpriteClient(str(binary))

    message = str(error.value)
    assert "process never started" in message
    assert "runtime DLLs" in message


def test_run_script_decodes_native_exit_and_passes_explicit_environment(monkeypatch, workdir):
    binary = workdir / "libresprite.exe"
    binary.write_bytes(b"placeholder")
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 1:
            return _completed(0, stdout="LibreSprite 1.3.0\n")
        return _completed(0xC0000005)

    monkeypatch.setattr(subprocess, "run", fake_run)

    profile = workdir / "profile"
    client = LibreSpriteClient(
        str(binary),
        environment={"APPDATA": str(profile), "LOCALAPPDATA": str(profile)},
    )
    with pytest.raises(LibreSpriteError, match="STATUS_ACCESS_VIOLATION"):
        client.run_script("console.log('test');")

    assert len(calls) == 2
    for _, kwargs in calls:
        assert kwargs["env"]["APPDATA"] == str(profile)
        assert kwargs["env"]["LOCALAPPDATA"] == str(profile)
