"""Versioned cache entries (`<name>@<version>` from `fetch(name, version=...)`,
the 0.38.0 kept-release path) must be visible to `data list` byte accounting and
reclaimable by `data remove` / `--all` / `--version`, not orphaned unreclaimable
disk that only `data versions` acknowledges.

Offline: every download is a file:// URL into an isolated PYAEGEAN_CACHE, and a
historical pin is injected by monkeypatching `_REMOTE` / `_REMOTE_HISTORY`, the
tests/test_versioned_data.py + tests/test_cli_data_store.py idiom."""

from __future__ import annotations

import json

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean import data  # noqa: E402
from aegean.cli import _build_app  # noqa: E402
from aegean.data import (  # noqa: E402
    DataSpec,
    HistoricalPin,
    downloaded_bytes,
    is_downloaded,
    sha256_file,
    versioned_bytes,
    versioned_entry_paths,
)

runner = CliRunner()

CURRENT = b"C" * 4096  # current pin bytes; renders as "4.1 kB"
V1 = b"v" * 1500  # a kept v1 release


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


@pytest.fixture()
def store(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """An isolated data store; returns the directory fetch() fills."""
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    return tmp_path / "cache" / "pyaegean"


def _register(monkeypatch, tmp_path, name: str, *, current: bytes | None, v1: bytes | None):
    # type: ignore[no-untyped-def]
    """Register a synthetic single-file dataset with a current pin and a v1 history pin,
    both served from local file:// sources (whichever payloads are given)."""
    url = ""
    if current is not None:
        src = tmp_path / f"{name}.current"
        src.write_bytes(current)
        url = src.as_uri()
    monkeypatch.setitem(data._REMOTE, name, DataSpec(name=name, url=url, license="x"))
    if v1 is not None:
        hsrc = tmp_path / f"{name}.v1"
        hsrc.write_bytes(v1)
        monkeypatch.setitem(
            data._REMOTE_HISTORY,
            name,
            [HistoricalPin(version="v1", url=hsrc.as_uri(), sha256=sha256_file(hsrc), superseded="v2")],
        )


def _output(res) -> str:  # type: ignore[no-untyped-def]
    out = res.output
    try:
        out += res.stderr
    except (ValueError, AttributeError):
        pass
    return out


def ok(app, *args: str) -> str:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, list(args))
    assert res.exit_code == 0, _output(res)
    return _output(res)


def err(app, *args: str) -> str:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, list(args))
    assert res.exit_code != 0, _output(res)
    return _output(res)


def _list_row(app, name: str) -> dict:  # type: ignore[no-untyped-def]
    return next(r for r in json.loads(ok(app, "data", "list", "--json")) if r["name"] == name)


# ── (A) the enumerator: exact prefix, all-versions and single-version ────────────
def test_versioned_entry_paths_matches_the_entry_and_its_siblings(store) -> None:
    store.mkdir(parents=True)
    (store / "epi@v1").write_bytes(V1)  # the entry
    (store / "epi@v1.part").write_bytes(b"p")  # download sibling
    (store / "epi@v1.sha256").write_text("deadbeef")  # extract stamp sibling
    (store / "epi").write_bytes(CURRENT)  # the CURRENT pin: NOT a versioned entry
    names = {p.name for p in versioned_entry_paths("epi", store)}
    assert names == {"epi@v1", "epi@v1.part", "epi@v1.sha256"}
    assert store / "epi" not in versioned_entry_paths("epi", store)


def test_versioned_entry_paths_never_sweeps_a_sibling_dataset(store) -> None:
    """The @-glob must anchor on the exact ``name@`` prefix."""
    store.mkdir(parents=True)
    (store / "epi@v1").write_bytes(V1)
    (store / "epi-other@v1").write_bytes(b"x")  # a DIFFERENT dataset sharing the ``epi`` stem
    got = {p.name for p in versioned_entry_paths("epi", store)}
    assert got == {"epi@v1"}  # epi-other@v1 is not swept in


def test_versioned_entry_paths_single_version_does_not_match_a_prefix_version(store) -> None:
    """``version='v1'`` must not match ``v11`` or ``v1.2`` (dotted-version safety)."""
    store.mkdir(parents=True)
    (store / "epi@v1").write_bytes(V1)
    (store / "epi@v11").write_bytes(b"y")
    (store / "epi@v1.2").write_bytes(b"z")  # would collide under a bare startswith('epi@v1')
    got = {p.name for p in versioned_entry_paths("epi", store, version="v1")}
    assert got == {"epi@v1"}


def test_versioned_bytes_sums_all_and_one_version(store) -> None:
    store.mkdir(parents=True)
    (store / "epi@v1").write_bytes(V1)
    (store / "epi@v2").write_bytes(b"2" * 200)
    assert versioned_bytes("epi", store) == len(V1) + 200
    assert versioned_bytes("epi", store, version="v1") == len(V1)
    assert versioned_bytes("epi", store, version="v9") == 0


# ── (B) downloaded_bytes now folds in the versioned footprint ───────────────────
def test_downloaded_bytes_includes_versioned_entries(store) -> None:
    store.mkdir(parents=True)
    spec = DataSpec(name="epi", url="", license="x")
    (store / "epi").write_bytes(CURRENT)  # current pin
    (store / "epi@v1").write_bytes(V1)  # kept version alongside
    assert is_downloaded(spec, store) is True  # is_downloaded stays current-pin only
    # the footprint reflects both current and versioned bytes (reclaimable disk)
    assert downloaded_bytes(spec, store) == len(CURRENT) + len(V1)


def test_is_downloaded_ignores_a_versioned_only_store(store) -> None:
    """A store holding only ``<name>@v1`` (no current pin) reads not downloaded."""
    store.mkdir(parents=True)
    spec = DataSpec(name="epi", url="", license="x")
    (store / "epi@v1").write_bytes(V1)
    assert is_downloaded(spec, store) is False
    assert versioned_bytes("epi", store) == len(V1)


# ── (C) data list counts versioned bytes (additive --json keys, visible column) ──
def test_data_list_counts_versioned_bytes_when_current_present(app, store, tmp_path, monkeypatch):
    # type: ignore[no-untyped-def]
    _register(monkeypatch, tmp_path, "epi", current=CURRENT, v1=V1)
    ok(app, "data", "fetch", "epi")  # current pin
    ok(app, "data", "fetch", "epi", "--version", "v1")  # kept version
    assert (store / "epi").exists() and (store / "epi@v1").exists()

    row = _list_row(app, "epi")
    assert row["downloaded"] is True
    # existing key: the footprint (now inclusive of the versioned entry)
    assert row["bytes"] == len(CURRENT) + len(V1)
    # additive keys: the versioned footprint split out, with a per-version breakdown
    assert row["versioned_bytes"] == len(V1)
    assert row["versioned"] == [{"version": "v1", "bytes": len(V1)}]


def test_data_list_surfaces_a_versioned_only_dataset(app, store, tmp_path, monkeypatch):
    # type: ignore[no-untyped-def]
    """When only a kept version is on disk, its bytes are still visible, not lost."""
    _register(monkeypatch, tmp_path, "epi", current=CURRENT, v1=V1)
    ok(app, "data", "fetch", "epi", "--version", "v1")  # ONLY the kept version
    assert not (store / "epi").exists()

    row = _list_row(app, "epi")
    assert row["downloaded"] is False  # the current pin is not present
    assert row["bytes"] == len(V1)  # but the versioned bytes are surfaced
    assert row["versioned_bytes"] == len(V1)


def test_data_list_human_table_shows_versioned(app, store, tmp_path, monkeypatch):
    # type: ignore[no-untyped-def]
    _register(monkeypatch, tmp_path, "epi", current=CURRENT, v1=V1)
    ok(app, "data", "fetch", "epi")
    ok(app, "data", "fetch", "epi", "--version", "v1")
    out = ok(app, "data", "list")
    # only epi has versioned entries in this isolated store, so the word is unique to
    # its size cell (rich wraps rather than truncates, so it survives any column squeeze)
    assert "versioned" in out


# ── (D) data remove reclaims the versioned entries ──────────────────────────────
def test_remove_reclaims_current_and_versioned(app, store, tmp_path, monkeypatch):
    # type: ignore[no-untyped-def]
    _register(monkeypatch, tmp_path, "epi", current=CURRENT, v1=V1)
    ok(app, "data", "fetch", "epi")
    ok(app, "data", "fetch", "epi", "--version", "v1")

    payload = json.loads(ok(app, "data", "remove", "epi", "--json"))
    assert payload["reclaimed_bytes"] == len(CURRENT) + len(V1)  # both reclaimed
    assert not (store / "epi").exists() and not (store / "epi@v1").exists()
    # and data versions no longer reports the kept version cached
    assert data.versions()["fetched"]["epi"]["history"][0]["cached"] is False


def test_remove_all_sweeps_versioned_entries(app, store, tmp_path, monkeypatch):
    # type: ignore[no-untyped-def]
    _register(monkeypatch, tmp_path, "epi", current=None, v1=V1)  # BYO current slot
    ok(app, "data", "fetch", "epi", "--version", "v1")  # only the kept version on disk
    assert (store / "epi@v1").exists()

    out = ok(app, "data", "remove", "--all")
    assert "reclaimed" in out
    assert not (store / "epi@v1").exists()  # --all swept the orphaned versioned entry


# ── (E) surgical single-version removal ─────────────────────────────────────────
def test_remove_version_deletes_only_the_named_release(app, store, tmp_path, monkeypatch):
    # type: ignore[no-untyped-def]
    _register(monkeypatch, tmp_path, "epi", current=CURRENT, v1=V1)
    # a second kept version planted directly (v2), to prove only v1 is removed
    ok(app, "data", "fetch", "epi")
    ok(app, "data", "fetch", "epi", "--version", "v1")
    (store / "epi@v2").write_bytes(b"2" * 300)

    payload = json.loads(ok(app, "data", "remove", "epi", "--version", "v1", "--json"))
    assert payload["reclaimed_bytes"] == len(V1)
    assert payload["removed"] == [
        {"name": "epi@v1", "path": str(store / "epi@v1"), "bytes": len(V1)}
    ]
    # the current pin and the other kept version are untouched
    assert (store / "epi").read_bytes() == CURRENT
    assert (store / "epi@v2").exists()
    assert not (store / "epi@v1").exists()


def test_remove_version_not_downloaded_is_a_clean_error(app, store, tmp_path, monkeypatch):
    # type: ignore[no-untyped-def]
    _register(monkeypatch, tmp_path, "epi", current=CURRENT, v1=V1)
    ok(app, "data", "fetch", "epi")  # current present, v1 never fetched
    out = err(app, "data", "remove", "epi", "--version", "v1")
    assert "version 'v1'" in out and "not downloaded" in out
    assert (store / "epi").read_bytes() == CURRENT  # the current copy is left alone


def test_remove_version_with_all_is_rejected(app, store) -> None:
    out = err(app, "data", "remove", "epi", "--version", "v1", "--all")
    assert "--all" in out


def test_remove_version_without_a_name_is_rejected(app, store) -> None:
    out = err(app, "data", "remove", "--version", "v1")
    assert "name a dataset" in out
