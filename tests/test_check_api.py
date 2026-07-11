"""scripts/check_api.py catches real API breaks and passes the live repo clean.

The checker is exercised end to end on a synthetic mini package (snapshot, mutate,
re-check) so each failure mode is verified by exit code AND report text: a removed
public function, a renamed parameter, a lost default (now-required parameter), and
a new required parameter all exit 1; pure additions stay informational at exit 0.
The shipped baseline (scripts/api-baseline.json) must load, be non-trivially large,
and reproduce cleanly against the current source.
"""

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
BASELINE = ROOT / "scripts" / "api-baseline.json"

_MINI = '''\
"""Synthetic mini package for the API-checker tests."""

__all__ = ["Greeter", "farewell", "greet"]


def greet(name, punct="!"):
    return name + punct


def farewell(name):
    return "bye " + name


class Greeter:
    def __init__(self, prefix="hi"):
        self.prefix = prefix

    def hail(self, name, *, loud=False):
        return name
'''


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONUTF8": "1"}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=env,
    )


def _write_mini(tmp_path: Path, body: str) -> None:
    (tmp_path / "mini").mkdir(exist_ok=True)
    (tmp_path / "mini" / "__init__.py").write_text(body, encoding="utf-8")


def _snapshot(tmp_path: Path) -> Path:
    _write_mini(tmp_path, _MINI)
    baseline = tmp_path / "baseline.json"
    r = _run(
        "--snapshot",
        "--package", "mini",
        "--search-path", str(tmp_path),
        "--baseline", str(baseline),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return baseline


def _check(tmp_path: Path, baseline: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        "--package", "mini",
        "--search-path", str(tmp_path),
        "--baseline", str(baseline),
    )


def test_unchanged_package_checks_clean(tmp_path: Path) -> None:
    baseline = _snapshot(tmp_path)
    r = _check(tmp_path, baseline)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK  public-api" in r.stdout


def test_removed_function_fails(tmp_path: Path) -> None:
    baseline = _snapshot(tmp_path)
    mutated = _MINI.replace('"Greeter", "farewell", "greet"', '"Greeter", "greet"').replace(
        'def farewell(name):\n    return "bye " + name\n', ""
    )
    assert "farewell" not in mutated
    _write_mini(tmp_path, mutated)
    r = _check(tmp_path, baseline)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "mini.farewell: removed" in r.stdout
    assert "FAIL public-api" in r.stdout


def test_renamed_parameter_fails(tmp_path: Path) -> None:
    baseline = _snapshot(tmp_path)
    mutated = _MINI.replace(
        'def greet(name, punct="!"):\n    return name + punct',
        'def greet(who, punct="!"):\n    return who + punct',
    )
    _write_mini(tmp_path, mutated)
    r = _check(tmp_path, baseline)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "mini.greet: parameter 'name' renamed to 'who'" in r.stdout


def test_lost_default_fails(tmp_path: Path) -> None:
    baseline = _snapshot(tmp_path)
    mutated = _MINI.replace('def greet(name, punct="!"):', "def greet(name, punct):")
    _write_mini(tmp_path, mutated)
    r = _check(tmp_path, baseline)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "mini.greet: parameter 'punct' lost its default (now required)" in r.stdout


def test_new_required_parameter_fails(tmp_path: Path) -> None:
    baseline = _snapshot(tmp_path)
    mutated = _MINI.replace(
        'def greet(name, punct="!"):', 'def greet(name, sep, punct="!"):'
    )
    _write_mini(tmp_path, mutated)
    r = _check(tmp_path, baseline)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "mini.greet: new required parameter 'sep'" in r.stdout


def test_additions_are_informational(tmp_path: Path) -> None:
    baseline = _snapshot(tmp_path)
    mutated = _MINI.replace(
        '__all__ = ["Greeter", "farewell", "greet"]',
        '__all__ = ["Greeter", "farewell", "greet", "wave"]',
    ) + '\n\ndef wave(times=1):\n    return "wave" * times\n'
    _write_mini(tmp_path, mutated)
    r = _check(tmp_path, baseline)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "mini.wave: added (function)" in r.stdout
    assert "OK  public-api" in r.stdout


def test_missing_baseline_is_a_clean_error(tmp_path: Path) -> None:
    _write_mini(tmp_path, _MINI)
    r = _check(tmp_path, tmp_path / "nowhere.json")
    assert r.returncode == 1
    assert "no baseline" in r.stdout + r.stderr
    assert "--snapshot" in r.stdout + r.stderr


def test_shipped_baseline_is_loadable_and_nontrivial() -> None:
    payload = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert payload["format"] == 1
    assert payload["package"] == "aegean"
    names = payload["names"]
    assert len(names) > 1000, f"baseline suspiciously small: {len(names)} names"
    entry = names["aegean.load"]
    assert entry["kind"] == "function"
    assert [p["name"] for p in entry["params"]] == ["script_id", "version"]
    assert names["aegean.greek"]["kind"] == "module"


def test_live_repo_checks_clean_against_shipped_baseline() -> None:
    r = _run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK  public-api" in r.stdout
