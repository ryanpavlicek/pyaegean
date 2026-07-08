"""fetch() of a single-file dataset with an ``on_disk`` override stores the artifact
under the on_disk (built-index) name — the same end state the backends'
``fetch_prebuilt`` produces — so fetch, list, doctor, and remove all agree.

The fixed defect (the lexicon-index class: ``abbott-smith-index`` and siblings):
``aegean data fetch abbott-smith-index`` left the raw dataset-named file, ``data
list`` probed only the on_disk name and reported NOT downloaded right after a
successful fetch, and a raw-named stray from an older fetch was invisible to
``data remove``. Uses the isolated PYAEGEAN_CACHE + PYAEGEAN_<NAME>_URL file://
override pattern of test_cli_data_store.py.
"""

from __future__ import annotations

import hashlib
import json

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean import data  # noqa: E402
from aegean.cli import _build_app  # noqa: E402

runner = CliRunner()

PAYLOAD = b"g" * 2048
NAME = "idx-test"
ON_DISK = "idx-test.json.gz"


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


@pytest.fixture()
def store(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    return tmp_path / "cache" / "pyaegean"


def _register_index(monkeypatch, tmp_path, payload: bytes = PAYLOAD):  # type: ignore[no-untyped-def]
    """A registered single-file dataset whose on_disk name differs (the index class)."""
    src = tmp_path / f"{NAME}.src"
    src.write_bytes(payload)
    monkeypatch.setitem(
        data._REMOTE, NAME, data.DataSpec(name=NAME, url="", license="x", on_disk=(ON_DISK,))
    )
    monkeypatch.setenv(data._env_url_var(NAME), src.as_uri())
    return src


def _break_source(monkeypatch, tmp_path) -> None:
    """Point the dataset's URL at a nonexistent file, so any download attempt fails."""
    monkeypatch.setenv(data._env_url_var(NAME), (tmp_path / "gone.src").as_uri())


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


def test_fetch_stores_under_the_on_disk_name(store, tmp_path, monkeypatch) -> None:
    _register_index(monkeypatch, tmp_path)
    got = data.fetch(NAME)
    assert got == store / ON_DISK and got.read_bytes() == PAYLOAD
    assert not (store / NAME).exists()  # no raw-named copy left behind
    # the exact probe `data list` / `doctor` / the TUI use now agrees with fetch
    assert data.is_downloaded(data._REMOTE[NAME], store) is True


def test_cli_fetch_then_list_agree(app, store, tmp_path, monkeypatch) -> None:
    _register_index(monkeypatch, tmp_path)
    out = ok(app, "data", "fetch", NAME)
    assert ON_DISK in out  # the printed destination is the real stored artifact
    row = next(
        r for r in json.loads(ok(app, "data", "list", "--json")) if r["name"] == NAME
    )
    assert row["downloaded"] is True and row["bytes"] == len(PAYLOAD)


def test_second_fetch_is_a_noop_from_the_on_disk_name(store, tmp_path, monkeypatch) -> None:
    _register_index(monkeypatch, tmp_path)
    first = data.fetch(NAME)
    _break_source(monkeypatch, tmp_path)  # a re-download would now fail loudly
    assert data.fetch(NAME) == first and first.read_bytes() == PAYLOAD


def test_fetch_adopts_a_legacy_raw_copy_without_redownload(store, tmp_path, monkeypatch) -> None:
    """A raw-named file from a pre-fix fetch is moved into place, not re-downloaded."""
    _register_index(monkeypatch, tmp_path)
    store.mkdir(parents=True, exist_ok=True)
    (store / NAME).write_bytes(PAYLOAD)  # the pre-fix on-disk state
    _break_source(monkeypatch, tmp_path)  # proves no network is needed to heal
    got = data.fetch(NAME)
    assert got == store / ON_DISK and got.read_bytes() == PAYLOAD
    assert not (store / NAME).exists()


def test_stale_raw_copy_is_dropped_when_canonical_exists(store, tmp_path, monkeypatch) -> None:
    _register_index(monkeypatch, tmp_path)
    data.fetch(NAME)
    (store / NAME).write_bytes(b"older duplicate")  # a redundant raw-named leftover
    _break_source(monkeypatch, tmp_path)
    got = data.fetch(NAME)
    assert got.read_bytes() == PAYLOAD  # the canonical copy wins
    assert not (store / NAME).exists()  # the duplicate is cleaned up


def test_corrupt_raw_copy_is_replaced_by_a_fresh_download(store, tmp_path, monkeypatch) -> None:
    """With a pinned sha256, a raw copy that fails verification is not adopted."""
    src = tmp_path / f"{NAME}.src"
    src.write_bytes(PAYLOAD)
    monkeypatch.setitem(
        data._REMOTE,
        NAME,
        data.DataSpec(
            name=NAME,
            url=src.as_uri(),  # pinned URL (no env override), so the sha IS enforced
            license="x",
            sha256=hashlib.sha256(PAYLOAD).hexdigest(),
            on_disk=(ON_DISK,),
        ),
    )
    store.mkdir(parents=True, exist_ok=True)
    (store / NAME).write_bytes(b"corrupt bytes")
    got = data.fetch(NAME)
    assert got == store / ON_DISK and got.read_bytes() == PAYLOAD
    assert not (store / NAME).exists()


def test_remove_deletes_a_raw_named_stray(app, store, tmp_path, monkeypatch) -> None:
    """`data remove` also sees the raw-named artifact an older fetch left behind."""
    _register_index(monkeypatch, tmp_path)
    store.mkdir(parents=True, exist_ok=True)
    (store / NAME).write_bytes(PAYLOAD)  # pre-fix state: raw name only
    ok(app, "data", "remove", NAME)
    assert not (store / NAME).exists() and not (store / ON_DISK).exists()


def test_the_real_index_specs_are_in_the_normalized_class() -> None:
    """Pins the four real lexicon indexes to the single-file on_disk shape the
    normalization applies to, so a spec change that silently drops one out of
    the class fails here."""
    for name in ("lsj-index", "middle-liddell-index", "cunliffe-index", "abbott-smith-index"):
        spec = data._REMOTE[name]
        assert len(spec.on_disk) == 1 and spec.on_disk[0] != name and not spec.extract, name
