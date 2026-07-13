"""Regression tests for the r44 data-store fixes (fold-asset visibility + versioned
load/hint honesty).

FIX 1 — fetch_text materialization visibility: the six fold DataSpecs keep the raw
``.gz`` at ``cache_dir()/<name>`` AND materialize a decompressed CoNLL-U (+ a ``.sha256``
stamp) into a subdir via ``fetch_text``. With no ``on_disk`` override those materialized
files were invisible to ``data list`` (undercounted bytes) and orphaned by ``data remove``.
Each spec now lists the raw name plus the materialized file + stamp, so accounting and
removal see the whole footprint.

FIX 2 — the ``data fetch --version`` hint only points at ``aegean.load(..., version=...)``
for corpora that actually have a versioned load path; other datasets get accurate guidance.

FIX 3 — ``aegean.load('sigla', version=...)`` no longer claims sigla "has none [kept
historical pins]" (it has v2/v3); the error names the fetch command instead. A corpus with
genuinely no pins keeps the original message.

Offline throughout: isolated PYAEGEAN_CACHE; a monkeypatched ``data.fetch`` places a gzip
raw file (no network); versioned CLI fetches use file:// historical pins."""

from __future__ import annotations

import gzip
import json

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean import data  # noqa: E402
from aegean.cli import _build_app  # noqa: E402
from aegean.data import (  # noqa: E402
    DataNotAvailableError,
    DataSpec,
    HistoricalPin,
    sha256_file,
)
from aegean.greek.dbbe import dbbe_path  # noqa: E402
from aegean.greek.papygreek import (  # noqa: E402
    papygreek_dev_path,
    papygreek_orig_path,
    papygreek_path,
)
from aegean.greek.verse_eval import verse_path  # noqa: E402

runner = CliRunner()

# (spec name, the module path function that materializes it) for the six fold assets.
_FOLDS = [
    ("papygreek-fold", lambda: papygreek_path()),
    ("papygreek-fold-orig", lambda: papygreek_orig_path()),
    ("papygreek-dev-tagging", lambda: papygreek_dev_path("tagging")),
    ("papygreek-dev-parse", lambda: papygreek_dev_path("parse")),
    ("dbbe-lingann-fold", lambda: dbbe_path()),
    ("verse-fold", lambda: verse_path()),
]

_CONLLU = b"# sent_id = 1\n1\tword\tlemma\tNOUN\t_\t_\t0\troot\t_\t_\n\n"


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


def _fake_fetch(root):  # type: ignore[no-untyped-def]
    """A stand-in for ``data.fetch`` that plants the raw ``.gz`` at cache_dir()/<name>
    (exactly where fetch() stores a fold asset) so fetch_text can materialize it."""

    def _fetch(name, **kw):  # type: ignore[no-untyped-def]
        p = root / name
        if not p.exists():
            p.write_bytes(gzip.compress(_CONLLU))
        return p

    return _fetch


def _out(res) -> str:  # type: ignore[no-untyped-def]
    out = res.output or ""
    try:
        out += res.stderr or ""
    except (ValueError, AttributeError):
        pass
    return out


# ── FIX 1: fold materialization is counted and reclaimed ─────────────────────────
def test_fold_specs_keep_raw_name_first_and_are_multi_entry() -> None:
    """The raw storage name MUST stay first and the tuple MUST have >1 entry, or fetch()'s
    single-file rename-under-on_disk special path would move the raw .gz where fetch_text
    can't find it."""
    for name, _ in _FOLDS:
        spec = data._REMOTE[name]
        assert spec.on_disk[0] == name
        assert len(spec.on_disk) == 3  # raw + materialized CoNLL-U + stamp
        assert not spec.extract


@pytest.mark.parametrize(("name", "path_fn"), _FOLDS)
def test_on_disk_covers_raw_and_materialized(name, path_fn, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    root = data.cache_dir()
    monkeypatch.setattr(data, "fetch", _fake_fetch(root))

    mat = path_fn()
    stamp = mat.with_name(mat.name + ".sha256")
    raw = root / name
    spec = data._REMOTE[name]
    odp = data.on_disk_paths(spec, root)

    # the declared on_disk paths match what fetch_text actually wrote
    assert odp[0] == raw
    assert mat in odp and stamp in odp
    assert set(data.present_paths(spec, root)) == {raw, mat, stamp}
    assert data.is_downloaded(spec, root) is True
    assert (
        data.downloaded_bytes(spec, root)
        == raw.stat().st_size + mat.stat().st_size + stamp.stat().st_size
    )


def test_data_list_counts_materialized_bytes(app, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    root = data.cache_dir()
    monkeypatch.setattr(data, "fetch", _fake_fetch(root))
    mat = papygreek_path()
    stamp = mat.with_name(mat.name + ".sha256")
    raw = root / "papygreek-fold"
    expected = raw.stat().st_size + mat.stat().st_size + stamp.stat().st_size

    res = runner.invoke(app, ["data", "list", "--json"])
    assert res.exit_code == 0, _out(res)
    row = next(r for r in json.loads(res.output) if r["name"] == "papygreek-fold")
    assert row["downloaded"] is True
    assert row["bytes"] == expected  # the pre-fix value was the raw .gz alone


def test_data_remove_reclaims_raw_materialized_and_stamp(app, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    root = data.cache_dir()
    monkeypatch.setattr(data, "fetch", _fake_fetch(root))
    mat = papygreek_path()
    stamp = mat.with_name(mat.name + ".sha256")
    raw = root / "papygreek-fold"
    subdir = mat.parent
    expected = raw.stat().st_size + mat.stat().st_size + stamp.stat().st_size

    res = runner.invoke(app, ["data", "remove", "papygreek-fold", "--json"])
    assert res.exit_code == 0, _out(res)
    payload = json.loads(res.output)
    assert payload["reclaimed_bytes"] == expected

    assert not raw.exists() and not mat.exists() and not stamp.exists()
    assert not subdir.exists()  # the now-empty materialization subdir is pruned
    # no payload is orphaned; a persistent unlocked lock sentinel is store metadata
    assert [p for p in root.rglob("*") if p.is_file() and not p.name.endswith(".lock")] == []


def test_remove_one_fold_leaves_a_sibling_in_the_shared_subdir(app, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """papygreek-fold and papygreek-fold-orig materialize into the SAME papygreek-grc/
    subdir; removing one must not touch the other, and the shared subdir survives."""
    root = data.cache_dir()
    monkeypatch.setattr(data, "fetch", _fake_fetch(root))
    fold = papygreek_path()
    orig = papygreek_orig_path()
    assert fold.parent == orig.parent  # shared subdir

    res = runner.invoke(app, ["data", "remove", "papygreek-fold", "--json"])
    assert res.exit_code == 0, _out(res)

    assert not fold.exists() and not (root / "papygreek-fold").exists()
    assert orig.exists() and (root / "papygreek-fold-orig").exists()
    assert orig.parent.exists()  # shared subdir NOT pruned (still holds orig)


# ── FIX 2: the versioned-fetch load hint ─────────────────────────────────────────
def _pin_history(monkeypatch, name, tmp_path):  # type: ignore[no-untyped-def]
    """Register `name` (current, url-less) + a v1 historical pin at a file:// source."""
    src = tmp_path / f"{name}-v1.json"
    src.write_bytes(b"historical-bytes")
    monkeypatch.setitem(data._REMOTE, name, DataSpec(name=name, url="", license="x"))
    monkeypatch.setitem(
        data._REMOTE_HISTORY,
        name,
        [HistoricalPin(version="v1", url=src.as_uri(), sha256=sha256_file(src), superseded="v2")],
    )


def test_versioned_fetch_hint_points_at_load_for_a_loadable_corpus(app, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    _pin_history(monkeypatch, "isicily-corpus", tmp_path)
    res = runner.invoke(app, ["data", "fetch", "isicily", "--version", "v1"])
    assert res.exit_code == 0, _out(res)
    assert "aegean.load('isicily', version='v1')" in _out(res)


def test_versioned_fetch_hint_guides_for_a_nonloadable_dataset(app, monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """sigla keeps historical pins but has no aegean.load(version=): the hint must NOT
    print a load command that would error."""
    _pin_history(monkeypatch, "sigla-corpus", tmp_path)
    res = runner.invoke(app, ["data", "fetch", "sigla", "--version", "v1"])
    assert res.exit_code == 0, _out(res)
    out = _out(res)
    assert "no versioned aegean.load()" in out
    assert "aegean.load('sigla', version=" not in out  # the broken hint is gone


# ── FIX 3: aegean.load(id, version=...) error honesty ────────────────────────────
def test_corpus_dataset_name_resolves_stems() -> None:
    assert data._corpus_dataset_name("sigla") == "sigla-corpus"
    assert data._corpus_dataset_name("damos") == "damos-corpus"
    assert data._corpus_dataset_name("lineara") is None  # bundled, no registered dataset


def test_load_version_sigla_names_the_fetch_command() -> None:
    """sigla-corpus HAS kept pins (v2/v3); the error must point at fetching them, not the
    false 'has none'."""
    with pytest.raises(DataNotAvailableError) as ei:
        data.load_corpus_version("sigla", "v2")
    msg = str(ei.value)
    assert "versioned load is not supported for 'sigla'" in msg
    assert "aegean data fetch sigla-corpus --version" in msg
    assert "has none" not in msg


def test_load_version_bundled_corpus_keeps_current_message() -> None:
    """A corpus with no backing dataset (lineara is bundled) keeps the original wording."""
    with pytest.raises(DataNotAvailableError) as ei:
        data.load_corpus_version("lineara", "v1")
    msg = str(ei.value)
    assert "kept historical pins" in msg and "has none" in msg


def test_load_version_dataset_without_pins_keeps_current_message() -> None:
    """damos-corpus is registered but keeps no historical pins: the original message stands
    (the split reports pins accurately, not merely dataset existence)."""
    with pytest.raises(DataNotAvailableError) as ei:
        data.load_corpus_version("damos", "v1")
    assert "has none" in str(ei.value)
