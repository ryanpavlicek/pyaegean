"""Command-line contract for the benchmark drift checker."""

from __future__ import annotations

import builtins
import importlib.util
import pathlib
import subprocess
import sys
from types import ModuleType

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_benchmarks.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_benchmarks", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_help_exits_before_importing_or_measuring(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    module = _load_script()
    original_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "aegean" or name.startswith("aegean."):
            raise AssertionError("--help must not import the package or start evaluation")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(SystemExit) as exc_info:
        module.main(["--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "usage:" in captured.out
    assert "network-backed offline" in captured.out
    assert "benchmark remeasurement" in captured.out
    assert captured.err == ""


def test_help_works_as_a_subprocess() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "measured" not in result.stdout
    assert result.stderr == ""


def test_unknown_option_fails_without_starting_evaluation() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--not-an-option"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 2
    assert "unrecognized arguments: --not-an-option" in result.stderr
    assert "measured" not in result.stdout
