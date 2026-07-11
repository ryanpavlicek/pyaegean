"""Regression tests for the PapyGreek fold fixes (r33 fix wave):

1. the build converter's lemma cleaning strips PapyGreek's inline numeral-value
   annotation (``β|num:2|`` -> ``β``) and a bare trailing ``|`` (``δύο|`` -> ``δύο``),
   which otherwise ship as malformed gold lemma cells (guaranteed misses);
2. ``aegean.greek.papygreek`` decompresses the fetched fold atomically (temp +
   ``os.replace``, so an interrupted decompress never leaves a truncated ``.conllu``
   served forever) and caps the in-memory read against a decompression bomb.
"""

from __future__ import annotations

import gzip
import sys
import unicodedata
from pathlib import Path

import pytest

from aegean.data import DataNotAvailableError
from aegean import data
from aegean.greek import papygreek

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_papygreek_fold as bpf  # noqa: E402


# --- (1) lemma cleaning in the build converter -----------------------------------


def _w(i: int, form: str, lemma: str, postag: str, rel: str, head: int) -> dict:
    return {
        "id": str(i), "form_reg": form, "lemma_reg": lemma, "postag_reg": postag,
        "relation_reg": rel, "head_reg": str(head), "artificial": None,
        "insertion_id": None, "lang": "grc",
    }


def _lemma_col(block: str) -> dict[int, str]:
    rows = [ln.split("\t") for ln in block.splitlines() if ln and not ln.startswith("#")]
    return {int(r[0]): r[2] for r in rows}


def test_clean_lemma_strips_numeral_value_annotation() -> None:
    # the five malformed cells that shipped in the v1 fold, plus other attested numerals
    assert bpf.clean_lemma("β|num:2|") == "β"
    assert bpf.clean_lemma("ια|num:11|") == "ια"
    assert bpf.clean_lemma("ιζ|num:17|") == "ιζ"
    assert bpf.clean_lemma("δύο|") == "δύο"
    assert bpf.clean_lemma("Γ|num:3000|") == "Γ"
    assert bpf.clean_lemma("τρεῖς|num:3|") == "τρεῖς"
    assert bpf.clean_lemma("σν|num:250|") == "σν"


def test_clean_lemma_preserves_ordinary_lemmas() -> None:
    # a real lemma is unchanged
    assert bpf.clean_lemma("γιγνώσκω") == "γιγνώσκω"
    # Perseus homonym numbering is still folded (delegates to the shared _clean_lemma)
    assert bpf.clean_lemma("μένω1") == "μένω"
    # None / empty -> "" (no crash)
    assert bpf.clean_lemma(None) == ""
    assert bpf.clean_lemma("") == ""
    # a real lemma that merely contains a digit-less body is untouched
    assert bpf.clean_lemma("λόγος") == "λόγος"


def test_clean_lemma_result_is_nfc() -> None:
    decomposed = "ά"  # alpha + combining acute
    assert bpf.clean_lemma(decomposed + "|num:1|") == unicodedata.normalize("NFC", decomposed)


def test_sentence_to_conllu_numeral_lemma_is_clean() -> None:
    # a numeral token whose reg lemma carries the |num:N| annotation must emit a clean
    # LEMMA cell (the fold gold the evaluator compares against)
    words = [
        _w(1, "δραχμὰς", "δραχμή", "n-p---fa-", "PRED", 0),
        _w(2, "β", "β|num:2|", "m--------", "ATR", 1),
    ]
    block, _forms = bpf.sentence_to_conllu("x@1", words)
    lemmas = _lemma_col(block)
    assert lemmas[2] == "β"
    assert "|" not in lemmas[2]  # no apparatus residue in the numeral lemma

    # the bare-trailing-pipe case (δύο|) also cleans
    words2 = [_w(1, "δύο", "δύο|", "m-d---na-", "PRED", 0)]
    block2, _ = bpf.sentence_to_conllu("x@2", words2)
    assert _lemma_col(block2)[1] == "δύο"


# --- (2) atomic + capped decompression of the fetched fold ------------------------

_SAMPLE = (
    "# sent_id = a\n"
    "1\tβ\tβ\tNUM\tm--------\t_\t0\troot\t_\t_\n"
    "\n"
)


def _write_gz(path: Path, text: str) -> None:
    with gzip.open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def test_papygreek_path_caps_oversized_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the decompression cap survives the move onto the shared data.fetch_text helper
    gz = tmp_path / "big.gz"
    _write_gz(gz, "x" * 5000)
    monkeypatch.setattr(papygreek, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(data, "fetch", lambda name, **kw: gz)
    monkeypatch.setattr(papygreek, "_MAX_FOLD_BYTES", 100)
    with pytest.raises(DataNotAvailableError):
        papygreek.papygreek_path()


def test_papygreek_path_writes_full_fold_and_leaves_no_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gz = tmp_path / "asset.gz"
    _write_gz(gz, _SAMPLE)
    cache = tmp_path / "cache"
    monkeypatch.setattr(papygreek, "cache_dir", lambda: cache)
    monkeypatch.setattr(data, "fetch", lambda name, **kw: gz)

    dest = papygreek.papygreek_path()
    assert dest.read_text(encoding="utf-8") == _SAMPLE
    # atomic write cleans up after itself: only the fold and its provenance stamp remain
    leftovers = sorted(p.name for p in dest.parent.iterdir() if p.name != dest.name)
    assert leftovers == [dest.name + ".sha256"]


def test_papygreek_path_repinned_asset_refreshes_stale_decompress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A re-pinned fold archive must re-decompress; the stale copy is never served.

    The v1->v2 fold re-pin surfaced this live: the decompressed ``.conllu`` predated the
    stamp and was returned verbatim, so an evaluation silently scored the old gold."""
    gz = tmp_path / "asset.gz"
    _write_gz(gz, _SAMPLE)
    cache = tmp_path / "cache"
    monkeypatch.setattr(papygreek, "cache_dir", lambda: cache)
    monkeypatch.setattr(data, "fetch", lambda name, **kw: gz)

    dest = papygreek.papygreek_path()
    assert dest.read_text(encoding="utf-8") == _SAMPLE

    # the asset is re-pinned: same cache, new archive content
    updated = _SAMPLE.replace("nummod", "obl")
    _write_gz(gz, updated)
    assert papygreek.papygreek_path().read_text(encoding="utf-8") == updated

    # a legacy cache without a stamp (pre-stamp decompress) is refreshed, not trusted
    stamp = dest.with_name(dest.name + ".sha256")
    stamp.unlink()
    dest.write_text("stale legacy copy", encoding="utf-8")
    assert papygreek.papygreek_path().read_text(encoding="utf-8") == updated
    assert stamp.exists()


def test_papygreek_path_interrupted_write_leaves_no_partial_then_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gz = tmp_path / "asset.gz"
    _write_gz(gz, _SAMPLE)
    cache = tmp_path / "cache"
    monkeypatch.setattr(papygreek, "cache_dir", lambda: cache)
    monkeypatch.setattr(data, "fetch", lambda name, **kw: gz)

    import aegean._atomic as atomic

    real_replace = atomic.os.replace
    calls = {"n": 0}

    def flaky(src: object, dst: object) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("simulated crash mid-swap")
        real_replace(src, dst)

    monkeypatch.setattr(atomic.os, "replace", flaky)

    dest = cache / papygreek._CACHE_SUBDIR / papygreek._FOLD_NAME
    with pytest.raises(OSError):
        papygreek.papygreek_path()
    # the interrupted decompress left NO truncated file to be served on the next call
    assert not dest.exists()
    # and no temp file leaked into the destination directory
    if dest.parent.exists():
        assert list(dest.parent.iterdir()) == []

    # a subsequent call lands the full fold atomically
    result = papygreek.papygreek_path()
    assert result == dest
    assert result.read_text(encoding="utf-8") == _SAMPLE


def test_papygreek_path_corrupt_gz_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # a .gz-named source that is not gzip is a corrupt or swapped archive: refused
    # cleanly (never materialized as the fold), and no partial file remains
    bad = tmp_path / "asset.gz"
    bad.write_bytes(b"not gzip data at all")
    monkeypatch.setattr(papygreek, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(data, "fetch", lambda name, **kw: bad)
    with pytest.raises(DataNotAvailableError):
        papygreek.papygreek_path()
    dest = (tmp_path / "cache") / papygreek._CACHE_SUBDIR / papygreek._FOLD_NAME
    assert not dest.exists()
