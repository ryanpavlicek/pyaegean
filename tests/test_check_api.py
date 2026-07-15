"""Current-facade validation for scripts/check_api.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("griffe")

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_api.py"
MANIFEST = ROOT / "scripts" / "api-manifest.json"

_MINI = """\
__all__ = ["greet"]


def greet(name: str = "world") -> str:
    return f"hello {name}"
"""


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1"},
    )


def _write_package(tmp_path: Path, body: str = _MINI) -> None:
    package = tmp_path / "mini"
    package.mkdir(exist_ok=True)
    (package / "__init__.py").write_text(body, encoding="utf-8")


def _write_manifest(
    tmp_path: Path,
    *,
    package: str = "mini",
    modules: list[str] | None = None,
    symbols: list[str] | None = None,
) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "format": 1,
                "package": package,
                "modules": modules or [package],
                "symbols": symbols or [],
            }
        ),
        encoding="utf-8",
    )
    return path


def _check_mini(tmp_path: Path, manifest: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--manifest",
        str(manifest),
    )


def test_live_reviewed_facade_resolves() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["package"] == "aegean"
    assert len(payload["modules"]) >= 20
    assert payload["symbols"] == ["aegean.cli.main", "aegean.tui.run_tui"]

    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK  public-api:" in result.stdout
    assert "current facade names resolve" in result.stdout


def test_custom_package_requires_explicit_manifest(tmp_path: Path) -> None:
    _write_package(tmp_path)
    result = _run("--package", "mini", "--search-path", str(tmp_path))
    assert result.returncode != 0
    assert "--manifest is required for a custom package" in result.stdout + result.stderr


def test_selected_module_and_symbol_resolve(tmp_path: Path) -> None:
    _write_package(tmp_path)
    manifest = _write_manifest(tmp_path, symbols=["mini.greet"])
    result = _check_mini(tmp_path, manifest)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 modules, 1 explicit symbols" in result.stdout


def test_missing_selected_symbol_fails(tmp_path: Path) -> None:
    _write_package(tmp_path, "__all__ = []\n")
    manifest = _write_manifest(tmp_path, symbols=["mini.greet"])
    result = _check_mini(tmp_path, manifest)
    assert result.returncode != 0
    assert "mini.greet: selected symbol is not explicitly exported" in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"format": 1, "package": "other", "modules": ["other"], "symbols": []},
            "manifest package",
        ),
        (
            {"format": 1, "package": "mini", "modules": ["mini", "mini"], "symbols": []},
            "contains duplicates",
        ),
        (
            {
                "format": 1,
                "package": "mini",
                "modules": ["mini._internal"],
                "symbols": [],
            },
            "private/empty segment",
        ),
        (
            {"format": 1, "package": "mini", "modules": ["outside"], "symbols": []},
            "outside package",
        ),
    ],
)
def test_malformed_manifest_fails(
    tmp_path: Path, payload: dict[str, object], message: str
) -> None:
    _write_package(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    result = _check_mini(tmp_path, manifest)
    assert result.returncode != 0
    assert message in result.stdout + result.stderr


def test_manifest_module_must_resolve(tmp_path: Path) -> None:
    _write_package(tmp_path)
    manifest = _write_manifest(tmp_path, modules=["mini.missing"])
    result = _check_mini(tmp_path, manifest)
    assert result.returncode != 0
    assert "no such member" in result.stdout + result.stderr
