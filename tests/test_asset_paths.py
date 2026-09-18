import os
import subprocess
import sys
from pathlib import Path

import pytest

from libresprite_mcp.asset_paths import ASSETS_ROOT_ENV, resolve_assets_root


def test_assets_root_requires_explicit_configuration(monkeypatch):
    monkeypatch.delenv(ASSETS_ROOT_ENV, raising=False)

    with pytest.raises(ValueError, match="--assets-root or set DOWNSTREAM_ASSETS_ROOT"):
        resolve_assets_root()


def test_assets_root_accepts_generic_environment_variable(monkeypatch):
    expected = Path.cwd()
    monkeypatch.setenv(ASSETS_ROOT_ENV, str(expected))

    assert resolve_assets_root() == expected.resolve()


def test_explicit_assets_root_takes_precedence(monkeypatch):
    monkeypatch.setenv(ASSETS_ROOT_ENV, str(Path.cwd() / "does-not-exist"))

    assert resolve_assets_root(Path.cwd()) == Path.cwd().resolve()


@pytest.mark.parametrize(
    "script",
    ["scripts/create_layered_sources.py", "scripts/verify_layered_sources.py"],
)
def test_pipeline_scripts_fail_clearly_without_assets_root(script):
    environment = os.environ.copy()
    environment.pop(ASSETS_ROOT_ENV, None)
    environment["PYTHONPATH"] = str(Path.cwd() / "src")

    result = subprocess.run(
        [sys.executable, script],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "--assets-root or set DOWNSTREAM_ASSETS_ROOT" in result.stderr
