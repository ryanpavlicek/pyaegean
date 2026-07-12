"""R44 eval-surface fixes for the verse / PapyGreek / DBBE register folds.

FIX 1 (empty-fold crash): a track/source that matches zero sentences after filtering must
refuse with a clean ValueError naming the track/source, not the misleading conll18
``UDError`` "There are multiple roots in a sentence" that an empty fold provoked (an empty
gold + the lone "\\n" system output misparse). Covered for the verse entrance and the shared
`papygreek._score_fold` path (PapyGreek + DBBE).

FIX 2 (track set): the verse fold is tragedy-only. ``track`` validates against
``{"tragedy", "all"}`` (plus ``None``); ``"hexameter"`` is rejected with a message that names
the removed Maximus prose-paraphrase sliver; ``"all"`` applies no filter and scores whatever
the fetched fold holds.

FIX 3 (docstring): `evaluate_on_papygreek_dev` returns the same keys as
`evaluate_on_papygreek` EXCEPT ``"layer"`` (only the main evaluator carries the orig variant).

FIX 4 (register wording): the DBBE fold's documented scope is 7th-15th c., not 9th-15th c.

The empty-fold guards fire before any evaluator use, so those tests need neither a model nor
the cached conll18 evaluator; the happy-path / key-set tests stub the model and skip when the
official evaluator is not cached (offline), following the test_papygreek / test_fix_dbbe_eval
pattern."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegean.greek import dbbe, joint, papygreek, verse_eval

VERSE_FIXTURE = Path(__file__).parent / "fixtures" / "verse" / "sample.conllu"
PAPY_FIXTURE = Path(__file__).parent / "fixtures" / "papygreek" / "sample.conllu"


class _StubModel:
    """A minimal joint model: tags every token NOUN, a single-root flat tree."""

    def analyze(self, forms: list[str]) -> joint.SentenceAnalysis:
        n = len(forms)
        return joint.SentenceAnalysis(
            tokens=tuple(forms),
            upos=tuple("NOUN" for _ in forms),
            xpos=tuple("n--------" for _ in forms),
            feats=tuple("_" for _ in forms),
            head=tuple(0 if i == 0 else 1 for i in range(n)),
            deprel=tuple("root" if i == 0 else "dep" for i in range(n)),
            lemma=tuple(forms),
        )


def _require_evaluator() -> None:
    from aegean.data import cache_dir
    from aegean.greek.ud import _CACHE_SUBDIR, _eval_module

    if not (cache_dir() / _CACHE_SUBDIR / "conll18_ud_eval.py").exists():
        try:
            _eval_module()
        except Exception as exc:  # pragma: no cover - offline
            pytest.skip(f"official evaluator unavailable offline: {exc}")


_TRAGEDY_ONLY = (
    "# sent_id = verse:tragedy:x@1\n"
    "1\tθέλω\tἐθέλω\tVERB\tv1spia---\t_\t0\troot\t_\t_\n"
    "\n"
)
_HEXAMETER_ONLY = (
    "# sent_id = verse:hexameter:x@1\n"
    "1\tγίνεται\tγίγνομαι\tVERB\tv3spie---\t_\t0\troot\t_\t_\n"
    "\n"
)


# --- FIX 1: empty-fold crash -> clean ValueError, never the UDError -----------------


def test_verse_empty_after_filter_raises_clean_valueerror(tmp_path: Path) -> None:
    # track='tragedy' against a hexameter-only source selects zero sentences: the guard fires
    # BEFORE the evaluator, so no model/evaluator is needed, and it must be a plain ValueError
    # (not the misleading conll18 "multiple roots" UDError).
    src = tmp_path / "hexonly.conllu"
    src.write_text(_HEXAMETER_ONLY, encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        verse_eval.evaluate_on_verse(track="tragedy", source=src)
    msg = str(excinfo.value)
    assert "tragedy" in msg and str(src) in msg  # names the track + the source
    assert "multiple roots" not in msg  # the misleading UDError is gone
    assert type(excinfo.value).__name__ == "ValueError"  # not a UDError subclass


def test_verse_empty_fold_no_track_raises_clean_valueerror(tmp_path: Path) -> None:
    # an entirely empty fold with no track filter names "the fold", not a track.
    src = tmp_path / "empty.conllu"
    src.write_text("", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        verse_eval.evaluate_on_verse(source=src)
    msg = str(excinfo.value)
    assert "the fold" in msg and str(src) in msg
    assert "multiple roots" not in msg


def test_dbbe_empty_source_raises_clean_valueerror(tmp_path: Path) -> None:
    # the empty-source crash class through papygreek._score_fold, via evaluate_on_dbbe.
    src = tmp_path / "empty.conllu"
    src.write_text("", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        dbbe.evaluate_on_dbbe(source=src)
    msg = str(excinfo.value)
    assert "dbbe" in msg and str(src) in msg
    assert "multiple roots" not in msg
    assert type(excinfo.value).__name__ == "ValueError"


def test_papygreek_empty_source_raises_clean_valueerror(tmp_path: Path) -> None:
    # the same _score_fold guard covers the PapyGreek entrance too.
    src = tmp_path / "empty.conllu"
    src.write_text("", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        papygreek.evaluate_on_papygreek(source=src)
    msg = str(excinfo.value)
    assert "papygreek" in msg and str(src) in msg
    assert "multiple roots" not in msg


# --- FIX 2: tragedy-only track set -------------------------------------------------


def test_verse_hexameter_track_rejected_with_sliver_reason(tmp_path: Path) -> None:
    # the removed hexameter filter value must name the Maximus prose paraphrase + the doc.
    src = tmp_path / "hexonly.conllu"
    src.write_text(_HEXAMETER_ONLY, encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        verse_eval.evaluate_on_verse(track="hexameter", source=src)
    msg = str(excinfo.value)
    assert "hexameter" in msg
    assert "Maximus" in msg and "prose" in msg  # the reason it was dropped
    assert "docs/benchmarks.md" in msg


def test_verse_unknown_track_rejected(tmp_path: Path) -> None:
    src = tmp_path / "trag.conllu"
    src.write_text(_TRAGEDY_ONLY, encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        verse_eval.evaluate_on_verse(track="epic", source=src)
    assert "tragedy" in str(excinfo.value)  # names the valid values


def test_verse_track_all_applies_no_filter(monkeypatch) -> None:
    # 'all' must score whatever the fold holds (the fixture carries tragedy + hexameter
    # sentences): byte-identical to the default (None) invocation, and NOT a hexameter filter.
    _require_evaluator()
    monkeypatch.setattr(joint, "_ACTIVE", _StubModel())
    all_res = verse_eval.evaluate_on_verse(track="all", source=VERSE_FIXTURE)
    none_res = verse_eval.evaluate_on_verse(source=VERSE_FIXTURE)
    from aegean.greek.ud import load_conllu

    every = load_conllu(VERSE_FIXTURE)
    assert all_res["track"] == "all"
    assert all_res["n_sentences"] == none_res["n_sentences"] == len(every) == 3
    assert all_res["n_words"] == none_res["n_words"] == sum(len(s.tokens) for s in every)


# --- FIX 3: dev key set == main key set - {"layer"} --------------------------------


def test_dev_key_set_is_main_minus_layer(monkeypatch) -> None:
    _require_evaluator()
    monkeypatch.setattr(joint, "_ACTIVE", _StubModel())
    main = papygreek.evaluate_on_papygreek(source=PAPY_FIXTURE)
    dev = papygreek.evaluate_on_papygreek_dev(source=PAPY_FIXTURE)
    assert "layer" in main and "layer" not in dev
    assert set(dev) == set(main) - {"layer"}
    # the docstring records exactly this contract
    assert "layer" in (papygreek.evaluate_on_papygreek_dev.__doc__ or "")


# --- FIX 4: DBBE register wording (7th-15th c.) ------------------------------------


def test_dbbe_documented_scope_is_7th_15th() -> None:
    doc = dbbe.__doc__ or ""
    assert "7th-15th c." in doc
    assert "9th-15th c." not in doc
