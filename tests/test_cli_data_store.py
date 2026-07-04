"""The `aegean data` store-management surface, exercised offline through
CliRunner: `list` reports downloaded status with real on-disk sizes
(directory-recursive for extracted datasets), `remove` deletes entries and
reports the reclaimed space (one name or `--all`), and a stored dataset is
never re-downloaded (proven against a URL that would fail if hit). Uses the
isolated PYAEGEAN_CACHE + PYAEGEAN_<NAME>_URL file:// override pattern of
test_data_resume.py / test_fix_security.py."""

from __future__ import annotations

import io
import json
import tarfile

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean import data  # noqa: E402
from aegean.cli import _build_app  # noqa: E402

runner = CliRunner()

PAYLOAD = b"a" * 4096  # a real, known size: 4096 B renders as "4.1 kB"
MEMBERS = {"inner/one.bin": b"x" * 1000, "inner/two.bin": b"y" * 500}


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


@pytest.fixture()
def store(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """An isolated data store; returns the directory fetch() will fill."""
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    return tmp_path / "cache" / "pyaegean"


def _output(res) -> str:  # type: ignore[no-untyped-def]
    """stdout plus stderr, across click versions that do or don't mix them."""
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


def _register_file(monkeypatch, tmp_path, name: str, payload: bytes = PAYLOAD) -> None:
    """A registered single-file dataset served from a local file:// source."""
    src = tmp_path / f"{name}.src"
    src.write_bytes(payload)
    monkeypatch.setitem(data._REMOTE, name, data.DataSpec(name=name, url="", license="x"))
    monkeypatch.setenv(data._env_url_var(name), src.as_uri())


def _register_archive(monkeypatch, tmp_path, name: str) -> None:
    """A registered extract=True dataset: a tar.gz that unpacks to a directory."""
    src = tmp_path / f"{name}.src.tar.gz"
    with tarfile.open(src, "w:gz") as tf:
        for member, blob in MEMBERS.items():
            info = tarfile.TarInfo(member)
            info.size = len(blob)
            tf.addfile(info, io.BytesIO(blob))
    monkeypatch.setitem(
        data._REMOTE, name, data.DataSpec(name=name, url="", license="x", extract=True)
    )
    monkeypatch.setenv(data._env_url_var(name), src.as_uri())


def _list_row(app, name: str) -> dict:  # type: ignore[no-untyped-def]
    rows = json.loads(ok(app, "data", "list", "--json"))
    return next(r for r in rows if r["name"] == name)


# ── (a) list: downloaded status with a real size ─────────────────────────────
def test_list_marks_a_fetched_dataset_downloaded_with_its_real_size(
    app, store, tmp_path, monkeypatch
):
    _register_file(monkeypatch, tmp_path, "blob")
    before = _list_row(app, "blob")
    assert before["downloaded"] is False and before["bytes"] is None

    out = ok(app, "data", "fetch", "blob")
    assert str(store / "blob") in out  # fetch prints the stored path
    assert (store / "blob").read_bytes() == PAYLOAD

    after = _list_row(app, "blob")
    assert after["downloaded"] is True
    assert after["bytes"] == len(PAYLOAD)  # the actual on-disk size, not the note


def test_list_sizes_an_extracted_dataset_directory_recursively(
    app, store, tmp_path, monkeypatch
):
    _register_archive(monkeypatch, tmp_path, "arch")
    ok(app, "data", "fetch", "arch")
    assert (store / "arch").is_dir()
    row = _list_row(app, "arch")
    assert row["downloaded"] is True
    assert row["bytes"] == sum(len(b) for b in MEMBERS.values())  # 1500: files only


# ── (b) remove: deletes and reports the reclaimed size ──────────────────────
def test_remove_deletes_the_entry_and_reports_what_and_how_much(
    app, store, tmp_path, monkeypatch
):
    _register_file(monkeypatch, tmp_path, "blob")
    ok(app, "data", "fetch", "blob")

    out = ok(app, "data", "remove", "blob")
    assert "removed blob" in out
    assert str(store / "blob") in out  # states exactly what was deleted
    assert "4.1 kB reclaimed" in out  # 4096 B, the real size
    assert not (store / "blob").exists()

    row = _list_row(app, "blob")
    assert row["downloaded"] is False and row["bytes"] is None


def test_remove_json_reports_exact_reclaimed_bytes(app, store, tmp_path, monkeypatch):
    _register_file(monkeypatch, tmp_path, "blob")
    ok(app, "data", "fetch", "blob")
    payload = json.loads(ok(app, "data", "remove", "blob", "--json"))
    assert payload["reclaimed_bytes"] == len(PAYLOAD)
    assert payload["removed"] == [
        {"name": "blob", "path": str(store / "blob"), "bytes": len(PAYLOAD)}
    ]


def test_remove_of_an_extracted_dataset_deletes_the_directory(
    app, store, tmp_path, monkeypatch
):
    _register_archive(monkeypatch, tmp_path, "arch")
    ok(app, "data", "fetch", "arch")
    payload = json.loads(ok(app, "data", "remove", "arch", "--json"))
    assert payload["reclaimed_bytes"] == sum(len(b) for b in MEMBERS.values())
    assert not (store / "arch").exists()


def test_remove_deletes_an_on_disk_dataset_and_agrees_with_list(
    app, store, tmp_path, monkeypatch
):
    """Regression (0.19.10): a dataset whose real artifact lands under a different
    filename (a prebuilt lexicon index, an agdt-derived member; DataSpec.on_disk)
    must be removable, and ``list`` and ``remove`` must agree it is downloaded.
    0.19.1 made list/doctor on_disk-aware but left ``remove`` probing only
    root/name, so ``list`` reported the index downloaded while ``remove`` refused
    it as "not downloaded" and its disk space was never reclaimable."""
    monkeypatch.setitem(
        data._REMOTE, "idx", data.DataSpec(name="idx", url="", license="x",
                                           on_disk=("idx-built.json.gz",))
    )
    store.mkdir(parents=True, exist_ok=True)
    (store / "idx-built.json.gz").write_bytes(PAYLOAD)

    assert _list_row(app, "idx")["downloaded"] is True  # list sees the on_disk artifact
    payload = json.loads(ok(app, "data", "remove", "idx", "--json"))
    assert payload["reclaimed_bytes"] == len(PAYLOAD)  # remove finds and deletes it
    assert not (store / "idx-built.json.gz").exists()
    assert _list_row(app, "idx")["downloaded"] is False  # and now both agree it is gone


# ── (c) remove errors ────────────────────────────────────────────────────────
def test_remove_unknown_name_exits_nonzero_naming_data_list(app, store):
    out = err(app, "data", "remove", "definitely-not-a-dataset")
    assert "unknown dataset" in out and "data list" in out


def test_remove_not_downloaded_exits_nonzero_naming_data_list(
    app, store, tmp_path, monkeypatch
):
    _register_file(monkeypatch, tmp_path, "blob")  # registered but never fetched
    out = err(app, "data", "remove", "blob")
    assert "not downloaded" in out and "data list" in out
    assert (store / "blob").exists() is False


def test_remove_without_a_name_or_all_exits_nonzero(app, store):
    out = err(app, "data", "remove")
    assert "--all" in out  # a single-word token: safe from help-width wrapping


# ── (d) remove --all ─────────────────────────────────────────────────────────
def test_remove_all_clears_every_downloaded_dataset_and_prints_each(
    app, store, tmp_path, monkeypatch
):
    _register_file(monkeypatch, tmp_path, "blob")
    _register_archive(monkeypatch, tmp_path, "arch")
    ok(app, "data", "fetch", "blob")
    ok(app, "data", "fetch", "arch")

    out = ok(app, "data", "remove", "--all")
    assert "removed blob" in out and "removed arch" in out  # each entry printed
    assert "across 2 datasets" in out
    assert not (store / "blob").exists() and not (store / "arch").exists()
    rows = json.loads(ok(app, "data", "list", "--json"))
    assert all(r["downloaded"] is False for r in rows)

    again = ok(app, "data", "remove", "--all")  # idempotent: an empty store is fine
    assert "nothing to remove" in again


# ── (e) permanence: a stored dataset is never re-downloaded ─────────────────
def test_second_fetch_of_a_stored_dataset_performs_no_download(
    app, store, tmp_path, monkeypatch
):
    _register_file(monkeypatch, tmp_path, "blob")
    ok(app, "data", "fetch", "blob")

    # Point the dataset's URL at a source that cannot be fetched. If the second
    # fetch touched the network path at all, it would fail; it must instead be
    # a no-op returning the stored copy.
    dead = tmp_path / "no-such-dir" / "gone.bin"
    monkeypatch.setenv(data._env_url_var("blob"), dead.as_uri())
    out = ok(app, "data", "fetch", "blob")
    assert str(store / "blob") in out
    assert (store / "blob").read_bytes() == PAYLOAD  # untouched, byte-identical

    # Control: the dead URL really does fail when a download is forced, and the
    # stored copy survives the failed attempt.
    err(app, "data", "fetch", "blob", "--force")
    assert (store / "blob").read_bytes() == PAYLOAD


def test_remove_reclaims_an_orphaned_partial_download(app, tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    # An interrupted FIRST fetch leaves only .part/.part.info files (no main
    # entry); remove must still find and reclaim them.
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    from aegean.data import cache_dir

    root = cache_dir()
    (root / "nt-corpus.part").write_bytes(b"x" * 2048)
    (root / "nt-corpus.part.info").write_text("{}", encoding="utf-8")
    res = runner.invoke(app, ["data", "remove", "nt-corpus"])
    assert res.exit_code == 0, res.output
    assert "removed nt-corpus" in res.output
    assert not (root / "nt-corpus.part").exists()
    assert not (root / "nt-corpus.part.info").exists()
