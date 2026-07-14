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


def _manifest(tmp_path: Path, package: str = "mini", *, modules: list[str] | None = None) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "format": 1,
                "package": package,
                "modules": modules or [package],
                "symbols": [],
            }
        ),
        encoding="utf-8",
    )
    return path


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


def test_manifest_selected_snapshot_ignores_unlisted_internal_addition(tmp_path: Path) -> None:
    body = '''\
__all__ = ["greet"]
from . import hidden

def greet(name):
    return name
'''
    _write_mini(tmp_path, body)
    (tmp_path / "mini" / "hidden.py").write_text(
        "def old_internal():\n    return 1\n", encoding="utf-8"
    )
    manifest = _manifest(tmp_path)
    baseline = tmp_path / "baseline.json"
    # An initial compatibility snapshot (without a manifest) grandfathered
    # the imported internal module and its old public definition.
    r = _run(
        "--snapshot",
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--baseline",
        str(baseline),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    names = json.loads(baseline.read_text(encoding="utf-8"))["names"]
    assert "mini.greet" in names
    assert "mini.hidden.old_internal" in names

    (tmp_path / "mini" / "hidden.py").write_text(
        "def old_internal():\n    return 1\n\ndef new_internal():\n    return 2\n",
        encoding="utf-8",
    )
    r = _run(
        "--snapshot",
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--baseline",
        str(baseline),
        "--manifest",
        str(manifest),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    names = json.loads(baseline.read_text(encoding="utf-8"))["names"]
    assert "mini.hidden.old_internal" in names
    assert "mini.hidden.new_internal" not in names

    check = _run(
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--baseline",
        str(baseline),
        "--manifest",
        str(manifest),
    )
    assert check.returncode == 0, check.stdout + check.stderr

    (tmp_path / "mini" / "hidden.py").write_text(
        "def new_internal():\n    return 2\n", encoding="utf-8"
    )
    before = baseline.read_text(encoding="utf-8")
    check = _run(
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--baseline",
        str(baseline),
        "--manifest",
        str(manifest),
    )
    assert check.returncode == 1, check.stdout + check.stderr
    assert "mini.hidden.old_internal: removed" in check.stdout
    snap = _run(
        "--snapshot",
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--baseline",
        str(baseline),
        "--manifest",
        str(manifest),
    )
    assert snap.returncode == 1, snap.stdout + snap.stderr
    assert "snapshot refused" in snap.stdout
    assert baseline.read_text(encoding="utf-8") == before


def test_snapshot_refuses_grandfathered_removal(tmp_path: Path) -> None:
    baseline = _snapshot(tmp_path)
    before = baseline.read_text(encoding="utf-8")
    _write_mini(tmp_path, _MINI.replace('"Greeter", "farewell", "greet"', '"Greeter", "greet"').replace(
        'def farewell(name):\n    return "bye " + name\n', ""
    ))
    r = _run(
        "--snapshot",
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--baseline",
        str(baseline),
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "snapshot refused" in r.stdout
    assert baseline.read_text(encoding="utf-8") == before


def test_explicit_breaking_snapshot_retires_only_after_review_flag(tmp_path: Path) -> None:
    baseline = _snapshot(tmp_path)
    _write_mini(
        tmp_path,
        _MINI.replace(
            '"Greeter", "farewell", "greet"', '"Greeter", "greet"'
        ).replace('def farewell(name):\n    return "bye " + name\n', ""),
    )
    accepted = _run(
        "--snapshot",
        "--accept-breaking-snapshot",
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--baseline",
        str(baseline),
    )
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "accepted breaking snapshot" in accepted.stdout
    names = json.loads(baseline.read_text(encoding="utf-8"))["names"]
    assert "mini.farewell" not in names
    assert _check(tmp_path, baseline).returncode == 0


def test_breaking_snapshot_flag_requires_snapshot_mode(tmp_path: Path) -> None:
    baseline = _snapshot(tmp_path)
    result = _run(
        "--accept-breaking-snapshot",
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--baseline",
        str(baseline),
    )
    assert result.returncode == 2
    assert "requires --snapshot" in result.stderr


def test_manifest_package_mismatch_is_a_clean_error(tmp_path: Path) -> None:
    baseline = _snapshot(tmp_path)
    manifest = _manifest(tmp_path, package="other")
    r = _run(
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--baseline",
        str(baseline),
        "--manifest",
        str(manifest),
    )
    assert r.returncode == 1
    assert "manifest package" in r.stdout + r.stderr


def test_snapshot_baseline_package_mismatch_is_a_clean_error(tmp_path: Path) -> None:
    baseline = _snapshot(tmp_path)
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    payload["package"] = "other"
    baseline.write_text(json.dumps(payload), encoding="utf-8")
    r = _run(
        "--snapshot",
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--baseline",
        str(baseline),
    )
    assert r.returncode == 1
    assert "baseline package" in r.stdout + r.stderr


def test_malformed_manifest_is_a_clean_error(tmp_path: Path) -> None:
    _write_mini(tmp_path, _MINI)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"format": 1, "package": "mini", "modules": "mini"}),
        encoding="utf-8",
    )
    r = _run(
        "--snapshot",
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--baseline",
        str(tmp_path / "baseline.json"),
        "--manifest",
        str(manifest),
    )
    assert r.returncode == 1
    assert "manifest 'modules'" in r.stdout + r.stderr


def test_malformed_explicit_all_is_a_clean_error(tmp_path: Path) -> None:
    _write_mini(tmp_path, '__all__ = ["missing"]\n')
    manifest = _manifest(tmp_path)
    r = _run(
        "--snapshot",
        "--package",
        "mini",
        "--search-path",
        str(tmp_path),
        "--baseline",
        str(tmp_path / "baseline.json"),
        "--manifest",
        str(manifest),
    )
    assert r.returncode == 1
    assert "__all__ names" in r.stdout + r.stderr


def test_mcp_documented_tools_are_explicit_exports() -> None:
    from aegean import mcp_server

    expected = {
        "TOOLS",
        "build_server",
        "main",
        "list_corpora",
        "corpus_info",
        "show_document",
        "search_signs",
        "balance_accounts",
        "query_corpus",
        "cite_corpus",
        "geo_sites",
        "data_status",
        "greek_pipeline",
        "greek_explain",
        "greek_scan",
        "greek_catalog",
        "greek_work",
        "greek_gloss",
        "koine_gloss",
        "corpus_diagnose",
    }
    assert expected <= set(mcp_server.__all__)
    assert expected - {"TOOLS", "build_server", "main"} == {
        fn.__name__ for fn in mcp_server.TOOLS
    }


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
