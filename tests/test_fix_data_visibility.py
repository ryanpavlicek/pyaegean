"""Regression tests for the data-visibility audit fixes.

Two findings, both about datasets a backend places on disk under a name that is
not ``cache_dir()/<registry-name>``:

(1) The downloaded/on-disk probe used a bare ``(cache_dir()/name).exists()``,
    so a prebuilt lexicon index (fetched, then written under its built-index
    filename ``lsj-perseus-index.json.gz`` rather than ``lsj-index``) and an
    ``agdt-derived`` member (copied out to ``agdt-postagger.json.gz`` etc.) read
    "not downloaded" even though the files were on disk. ``aegean data list`` and
    ``aegean doctor`` must instead detect every dataset's real footprint. These
    tests plant each dataset *shape* (a dir for extract, a ``.json.gz`` for an
    index, a plain file) at the actual on-disk name and assert both surfaces
    report it downloaded with the real byte size.

(2) ``versions()`` advertised the pinned sha256 next to an env-overridden URL,
    but ``fetch`` does not enforce that sha against a user's own mirror. The
    manifest must report the sha as not enforced (and blank it) when the URL is
    overridden, so the reproducibility record is honest.

Offline throughout: isolated PYAEGEAN_CACHE, on-disk artifacts planted directly
(no network), matching the test_cli_data_store / test_cli_doctor patterns."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean import data  # noqa: E402
from aegean.cli import _build_app  # noqa: E402
from aegean.data import (  # noqa: E402
    _REMOTE,
    DataSpec,
    downloaded_bytes,
    is_downloaded,
    on_disk_paths,
    versions,
)

runner = CliRunner()


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


@pytest.fixture()
def store(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """An isolated, existing data store; returns its root directory."""
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    root = tmp_path / "cache" / "pyaegean"
    root.mkdir(parents=True)
    return root


@pytest.fixture(autouse=True)
def quiet_analysis_cache(monkeypatch):  # type: ignore[no-untyped-def]
    """Deterministic analysis-cache state so doctor stays offline + order-free."""
    from aegean import cache as analysis_cache

    monkeypatch.delenv("PYAEGEAN_ANALYSIS_CACHE", raising=False)
    monkeypatch.setattr(analysis_cache, "_active", None)
    monkeypatch.setattr(analysis_cache, "_env_checked", True)


def _output(res) -> str:  # type: ignore[no-untyped-def]
    out = res.output
    try:
        out += res.stderr
    except (ValueError, AttributeError):
        pass
    return out


def _stdout(res) -> str:  # type: ignore[no-untyped-def]
    try:
        return res.stdout
    except (ValueError, AttributeError):
        return res.output


def _list_row(app, name: str) -> dict:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["data", "list", "--json"])
    assert res.exit_code == 0, _output(res)
    rows = json.loads(_stdout(res))
    return next(r for r in rows if r["name"] == name)


def _doctor_dataset(app, name: str) -> dict:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["doctor", "--json"])
    assert res.exit_code == 0, _output(res)
    report = json.loads(_stdout(res))
    return next(d for d in report["data_store"]["datasets"] if d["name"] == name)


def _plant_dir(root: Path, name: str, files: dict[str, bytes]) -> int:
    d = root / name
    d.mkdir(parents=True)
    total = 0
    for rel, blob in files.items():
        fp = d / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(blob)
        total += len(blob)
    return total


def _plant_gz(root: Path, name: str, payload: dict) -> int:
    fp = root / name
    with gzip.open(fp, "wt", encoding="utf-8") as f:
        json.dump(payload, f)
    return fp.stat().st_size


# ── (1a) the pure footprint helpers, per dataset shape ───────────────────────
def test_default_footprint_is_root_slash_name(store) -> None:  # type: ignore[no-untyped-def]
    """A spec with no on_disk override probes exactly cache_dir()/name."""
    spec = DataSpec(name="plain-thing", url="", license="x")
    assert on_disk_paths(spec, store) == [store / "plain-thing"]
    assert is_downloaded(spec, store) is False
    (store / "plain-thing").write_bytes(b"z" * 321)
    assert is_downloaded(spec, store) is True
    assert downloaded_bytes(spec, store) == 321


def test_index_dataset_detected_under_its_built_index_filename(store) -> None:  # type: ignore[no-untyped-def]
    """lsj-index lands as lsj-perseus-index.json.gz, NOT cache_dir()/lsj-index."""
    spec = _REMOTE["lsj-index"]
    # the wrong (old) probe path must be absent...
    assert not (store / "lsj-index").exists()
    assert is_downloaded(spec, store) is False
    # ...and planting the REAL filename must flip it downloaded with a real size.
    size = _plant_gz(store, "lsj-perseus-index.json.gz", {"λόγος": {"defn": "word"}})
    assert on_disk_paths(spec, store) == [store / "lsj-perseus-index.json.gz"]
    assert is_downloaded(spec, store) is True
    assert downloaded_bytes(spec, store) == size


@pytest.mark.parametrize(
    "name, filename",
    [
        ("middle-liddell-index", "middle-liddell-index.json.gz"),
        ("cunliffe-index", "cunliffe-index.json.gz"),
        ("abbott-smith-index", "abbott-smith-index.json.gz"),
    ],
)
def test_scaife_indexes_detected_under_their_real_filename(store, name, filename) -> None:  # type: ignore[no-untyped-def]
    spec = _REMOTE[name]
    assert is_downloaded(spec, store) is False
    size = _plant_gz(store, filename, {"a": 1})
    assert is_downloaded(spec, store) is True
    assert downloaded_bytes(spec, store) == size


def test_agdt_derived_detected_from_a_copied_out_member(store) -> None:  # type: ignore[no-untyped-def]
    """The bundle's members are copied out to their own filenames; any one of
    them present means the bundle is downloaded."""
    spec = _REMOTE["agdt-derived"]
    assert is_downloaded(spec, store) is False
    # only the tagger member is present (the use_tagger path), no agdt-derived/ dir
    (store / "agdt-postagger.json.gz").write_bytes(b"m" * 2048)
    assert is_downloaded(spec, store) is True
    assert downloaded_bytes(spec, store) == 2048


def test_agdt_derived_detected_from_the_extract_dir(store) -> None:  # type: ignore[no-untyped-def]
    """A direct fetch() unpacks to cache_dir()/agdt-derived; that counts too."""
    spec = _REMOTE["agdt-derived"]
    size = _plant_dir(store, "agdt-derived", {"model.json": b"x" * 500})
    assert is_downloaded(spec, store) is True
    assert downloaded_bytes(spec, store) == size


# ── (1b) end-to-end: `data list` and `doctor` agree, every shape ─────────────
def test_list_and_doctor_report_each_planted_shape_downloaded(app, store) -> None:  # type: ignore[no-untyped-def]
    # An extract dataset (directory), an index dataset (.json.gz under its real
    # name), and a plain-file dataset — the three fetch() shapes.
    dir_size = _plant_dir(store, "grc-joint", {"encoder.onnx": b"o" * 4096})  # extract
    idx_size = _plant_gz(store, "cunliffe-index.json.gz", {"μῆνις": 1})  # index
    (store / "nt-corpus").write_bytes(b"n" * 777)  # plain file

    for name, size in (
        ("grc-joint", dir_size),
        ("cunliffe-index", idx_size),
        ("nt-corpus", 777),
    ):
        row = _list_row(app, name)
        assert row["downloaded"] is True, name
        assert row["bytes"] == size, name
        doc = _doctor_dataset(app, name)
        assert doc["downloaded"] is True, name
        assert doc["bytes"] == size, name


def test_list_human_table_shows_the_index_dataset_downloaded(app, store) -> None:  # type: ignore[no-untyped-def]
    """The rendered table (not just --json) must say yes with a size."""
    _plant_gz(store, "lsj-perseus-index.json.gz", {"a": 1})
    res = runner.invoke(app, ["data", "list"])
    assert res.exit_code == 0, _output(res)
    out = _output(res)
    # the lsj-index row must carry a "yes (...)" downloaded marker
    line = next(ln for ln in out.splitlines() if "lsj-index" in ln)
    assert "yes" in line  # downloaded, where the old bare-path probe said "no"


def test_undownloaded_index_still_reads_not_downloaded(app, store) -> None:  # type: ignore[no-untyped-def]
    """No false positives: nothing planted → the index reads not downloaded."""
    row = _list_row(app, "middle-liddell-index")
    assert row["downloaded"] is False and row["bytes"] is None
    doc = _doctor_dataset(app, "middle-liddell-index")
    assert doc["downloaded"] is False and doc["bytes"] is None


def test_doctor_total_and_versions_cached_agree_with_list(app, store) -> None:  # type: ignore[no-untyped-def]
    """versions()['fetched'][name]['cached'] uses the corrected probe too."""
    _plant_gz(store, "abbott-smith-index.json.gz", {"a": 1})
    manifest = versions()
    assert manifest["fetched"]["abbott-smith-index"]["cached"] is True
    assert manifest["fetched"]["cunliffe-index"]["cached"] is False


# ── (2) versions() sha honesty under an env-override ─────────────────────────
def test_versions_blanks_and_flags_sha_when_url_is_overridden(store, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # nt-corpus is pinned with a real sha; override its URL as a user mirror.
    pinned = _REMOTE["nt-corpus"].sha256
    assert len(pinned) == 64  # precondition: it really is pinned
    monkeypatch.setenv(data._env_url_var("nt-corpus"), "file:///some/mirror.json")

    entry = versions()["fetched"]["nt-corpus"]
    # the manifest shows the mirror URL...
    assert entry["url"] == "file:///some/mirror.json"
    assert entry["url_overridden"] is True
    # ...but must NOT advertise the pinned sha that fetch() would not enforce.
    assert entry["sha256_enforced"] is False
    assert entry["sha256"] == ""
    assert entry["sha256"] != pinned


def test_versions_keeps_enforced_sha_for_a_pinned_unoverridden_dataset(store) -> None:  # type: ignore[no-untyped-def]
    entry = versions()["fetched"]["nt-corpus"]
    assert entry["url_overridden"] is False
    assert entry["sha256_enforced"] is True
    assert entry["sha256"] == _REMOTE["nt-corpus"].sha256


def test_versions_marks_a_genuinely_unpinned_dataset(store) -> None:  # type: ignore[no-untyped-def]
    # linearb-corpus has no URL and no sha: unpinned, not overridden.
    entry = versions()["fetched"]["linearb-corpus"]
    assert entry["sha256"] == ""
    assert entry["sha256_enforced"] is False
    assert entry["url_overridden"] is False


def test_versions_cli_table_flags_the_overridden_dataset(app, store, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv(data._env_url_var("nt-corpus"), "file:///some/mirror.json")
    res = runner.invoke(app, ["data", "versions"])
    assert res.exit_code == 0, _output(res)
    out = _output(res)
    line = next(ln for ln in out.splitlines() if "nt-corpus" in ln)
    assert "overridden" in line  # not the pinned sha, not "(unpinned)"
