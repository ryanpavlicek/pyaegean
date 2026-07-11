"""Tests for the PapyGreek documentary-Koine DEV fold (Phase 2a):

  * the dev build (``scripts/build_papygreek_dev.py``) — the empty-node reattachment (the
    parse track's deterministic transform), the tagging-token selection, the two-track
    builders and their leakage refilter, the document-disjointness invariant, and the
    fold-doc-id extraction;
  * the `evaluate_on_papygreek_dev` wiring (stubbed active model; skips without the cached
    evaluator), including that the tagging track forces gold-token-only scoring;
  * the `papygreek_convention_report` UPOS/XPOS decomposition — the split is checked against
    numbers known by construction, the reproduction against the official CoNLL-18 evaluator,
    and the adversarial edges.

All offline: the decomposition core runs on synthetic folds, the reproduction test uses the
cached evaluator (skipped if absent), and nothing runs the neural model."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from aegean.greek import joint, papygreek
from aegean.greek.papygreek import (
    NeuralPipelineRequiredError,
    PapyGreekConventionReport,
    _classify_xpos_error,
    _decompose_papygreek,
    papygreek_convention_report,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_papygreek_dev as bpd  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "papygreek" / "sample.conllu"

_PapyTok = tuple[str, str]  # (upos, xpos)


# --- reg-layer word helpers (as read off the PapyGreek <word> elements) -----------


def _w(i, form, lemma, postag, rel, head, *, artificial=None, insertion=None):
    return {
        "id": str(i), "form_reg": form, "lemma_reg": lemma, "postag_reg": postag,
        "relation_reg": rel, "head_reg": None if head is None else str(head),
        "artificial": artificial, "insertion_id": insertion, "lang": "grc",
    }


# A real epistolary-opening sentence (aegyptus.90.43 s1): the elided main verb is the single
# artificial node (id 9, PRED at root); its surface children (1 SBJ, 2 OBJ, 7 OBJ) point at it.
def _elliptic_opening():
    return [
        _w(1, "Περικλῆς", "Περικλέης", "n-s---mn-", "SBJ", 9),
        _w(2, "Σαραπᾶτι", "Σαραπάς", "n-s---md-", "OBJ", 9),
        _w(3, "τῷ", "ὁ", "l-s---md-", "ATR", 6),
        _w(4, "κυρίῳ", "κύριος", "a-s---md-", "ATR", 6),
        _w(5, "μου", "ἐγώ", "p1s---mg-", "ATR", 6),
        _w(6, "πατρὶ", "πατήρ", "n-s---md-", "ATR", 2),
        _w(7, "χαίρειν", "χαίρω", "v--pna---", "OBJ", 9),
        _w(8, ".", "punc1", "u--------", "AuxK", 0),
        _w(9, "[0]", "", "", "PRED", 0, artificial="elliptic", insertion="0001e"),
    ]


# --- empty-node reattachment (parse track) ----------------------------------------


def test_reattach_promotes_elided_children_to_its_head() -> None:
    real = bpd._reattach_single_artificial(_elliptic_opening())
    assert real is not None
    assert len(real) == 8  # the artificial node dropped
    assert all(not (w["artificial"] or w["insertion_id"]) for w in real)
    by_id = {w["id"]: w for w in real}
    # the elided node (id 9) had head 0; its children (1, 2, 7) are re-attached to 0
    assert by_id["1"]["head_reg"] == "0"
    assert by_id["2"]["head_reg"] == "0"
    assert by_id["7"]["head_reg"] == "0"
    # a non-child keeps its head (id 6 pointed at 2, still does)
    assert by_id["6"]["head_reg"] == "2"


def test_reattach_output_converts_to_valid_single_root_tree() -> None:
    # the reattached tokens must convert to CoNLL-U with exactly one root (the converter's
    # single-root normalization handles the promoted-to-root children)
    real = bpd._reattach_single_artificial(_elliptic_opening())
    assert real is not None
    from build_papygreek_fold import sentence_to_conllu

    block, forms = sentence_to_conllu("papygreek-dev:x@1", real)
    rows = [ln.split("\t") for ln in block.splitlines() if ln and not ln.startswith("#")]
    assert len(rows) == 8
    assert sum(1 for r in rows if r[6] == "0") == 1  # exactly one root
    assert all(0 <= int(r[6]) <= 8 for r in rows)    # heads in range
    assert forms[0] == "Περικλῆς"


def test_reattach_rejects_multiple_artificial_nodes() -> None:
    words = _elliptic_opening() + [
        _w(10, "[1]", "", "", "ExD", 0, artificial="elliptic", insertion="0002e")
    ]
    assert bpd._reattach_single_artificial(words) is None


def test_reattach_rejects_non_fully_annotated_real_token() -> None:
    words = _elliptic_opening()
    words[3]["head_reg"] = None  # a real token now lacks a head → cannot score UAS
    assert bpd._reattach_single_artificial(words) is None


# --- tagging-token selection ------------------------------------------------------


def test_tagging_annotated_requires_form_postag_lemma_and_clean_reading() -> None:
    assert bpd.tagging_annotated(_w(1, "θέλω", "ἐθέλω", "v1spia---", "PRED", 0))
    # punctuation: any non-empty reading is fine
    assert bpd.tagging_annotated(_w(1, ".", "punc1", "u--------", "AuxK", 0))
    # missing lemma / postag / form → not scoreable
    assert not bpd.tagging_annotated(_w(1, "θέλω", None, "v1spia---", "PRED", 0))
    assert not bpd.tagging_annotated(_w(1, "θέλω", "ἐθέλω", None, "PRED", 0))
    # an artificial node's reconstructed form does not reduce to clean Greek
    assert not bpd.tagging_annotated(
        _w(9, "[0]", "-", "v3s___---", "PRED", 0, artificial="elliptic")
    )
    # an unstrippable illegibility marker is not a clean reading
    assert not bpd.tagging_annotated(_w(1, "ἀπελυς_.2", "ἀπολύω", "v1spia---", "PRED", 0))


# --- the two-track builders + leakage refilter ------------------------------------


def _rec(stem, sid, words, status, leaked=False):
    return bpd.SentRec(stem, sid, words, status, leaked)


def test_build_tagging_drops_artificial_nodes_and_unannotated_tokens() -> None:
    # an artificial sentence: 8 real annotated tokens + the elided node → 8 tagging tokens
    recs = [_rec("d1", "1", _elliptic_opening(), "artificial")]
    blocks, stats = bpd.build_tagging(recs, keys=set())
    assert stats["sentences_kept"] == 1
    assert stats["tokens_kept"] == 8  # the artificial node is excluded
    rows = [ln for ln in blocks[0].splitlines() if ln and not ln.startswith("#")]
    assert len(rows) == 8


def test_build_tagging_excludes_leaked_sentence() -> None:
    recs = [_rec("d1", "1", _elliptic_opening(), "artificial")]
    # the form-tuple of the annotated surface tokens is in the training keys → excluded
    forms = ("Περικλῆς", "Σαραπᾶτι", "τῷ", "κυρίῳ", "μου", "πατρὶ", "χαίρειν", ".")
    blocks, stats = bpd.build_tagging(recs, keys={forms})
    assert stats["sentences_kept"] == 0
    assert stats["excluded"].get("leaked") == 1


def test_build_tagging_only_uses_artificial_and_partial() -> None:
    # an "ok" or "leaked" or "apparatus" sentence is not tagging-track material
    recs = [_rec("d1", "1", [_w(1, "θέλω", "ἐθέλω", "v1spia---", "PRED", 0)], "ok", leaked=True)]
    blocks, stats = bpd.build_tagging(recs, keys=set())
    assert stats["sentences_kept"] == 0
    assert stats["source_sentences"] == {}


def test_build_parse_keeps_single_artificial_and_reattaches() -> None:
    recs = [_rec("d1", "1", _elliptic_opening(), "artificial")]
    blocks, stats = bpd.build_parse(recs, keys=set())
    assert stats["sentences_kept"] == 1
    assert stats["tokens_kept"] == 8
    assert stats["source_artificial_sentences"] == 1
    rows = [ln.split("\t") for ln in blocks[0].splitlines() if ln and not ln.startswith("#")]
    assert sum(1 for r in rows if r[6] == "0") == 1


def test_build_parse_counts_multi_artificial_exclusion() -> None:
    words = _elliptic_opening() + [
        _w(10, "[1]", "", "", "ExD", 0, artificial="elliptic", insertion="0002e")
    ]
    recs = [_rec("d1", "1", words, "artificial")]
    blocks, stats = bpd.build_parse(recs, keys=set())
    assert stats["sentences_kept"] == 0
    assert stats["excluded"].get("multi_artificial") == 1


def test_build_parse_excludes_leaked() -> None:
    recs = [_rec("d1", "1", _elliptic_opening(), "artificial")]
    forms = ("Περικλῆς", "Σαραπᾶτι", "τῷ", "κυρίῳ", "μου", "πατρὶ", "χαίρειν", ".")
    blocks, stats = bpd.build_parse(recs, keys={forms})
    assert stats["sentences_kept"] == 0
    assert stats["excluded"].get("leaked") == 1


# --- document-disjointness invariant + fold-id extraction -------------------------


def test_fold_doc_ids_from_conllu_extracts_stems(tmp_path: Path) -> None:
    p = tmp_path / "fold.conllu"
    p.write_text(
        "# sent_id = papygreek:bgu.1.261@2\n1\tθέλω\tἐθέλω\tVERB\tv\t_\t0\troot\t_\t_\n\n"
        "# sent_id = papygreek:aegyptus.90.43@1\n1\tθέλω\tἐθέλω\tVERB\tv\t_\t0\troot\t_\t_\n\n",
        encoding="utf-8",
    )
    assert bpd.fold_doc_ids_from_conllu(p) == {"bgu.1.261", "aegyptus.90.43"}


def test_document_disjointness_is_the_partition() -> None:
    # the build's fold/nonfold split: a doc is a fold doc iff it has >=1 ok & non-leaked
    # sentence; the dev pool is exactly the complement — the invariant Phase 2a enforces
    recs = [
        _rec("foldA", "1", [_w(1, "θέλω", "ἐθέλω", "v1spia---", "PRED", 0)], "ok", leaked=False),
        _rec("foldA", "2", _elliptic_opening(), "artificial"),          # same doc, not dev
        _rec("devB", "1", _elliptic_opening(), "artificial"),           # non-fold → dev
        _rec("leakC", "1", [_w(1, "θέλω", "ἐθέλω", "v1spia---", "PRED", 0)], "ok", leaked=True),
    ]
    all_docs = {r.stem for r in recs}
    fold_docs = {r.stem for r in recs if r.status == "ok" and not r.leaked}
    nonfold = all_docs - fold_docs
    assert fold_docs == {"foldA"}
    assert nonfold == {"devB", "leakC"}          # a doc whose only ok sentence leaked is NOT a fold doc
    assert fold_docs & nonfold == set()           # disjoint by construction


# --- evaluate_on_papygreek_dev wiring ---------------------------------------------


class _StubModel:
    """A minimal joint model: tags every token NOUN with a single-root flat tree."""

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


def test_evaluate_dev_tagging_forces_gold_token_scoring(monkeypatch) -> None:
    _require_evaluator()
    monkeypatch.setattr(joint, "_ACTIVE", _StubModel())
    res = papygreek.evaluate_on_papygreek_dev("tagging", source=FIXTURE)
    assert res["treebank"] == "papygreek-dev" and res["split"] == "tagging"
    assert res["parsed"] is False                     # tagging track never scores UAS/LAS
    assert res["uas"] is None and res["las"] is None
    for key in ("upos", "xpos", "ufeats", "lemma"):
        assert 0.0 <= res[key] <= 1.0


def test_evaluate_dev_parse_scores_uas(monkeypatch) -> None:
    _require_evaluator()
    monkeypatch.setattr(joint, "_ACTIVE", _StubModel())
    res = papygreek.evaluate_on_papygreek_dev("parse", source=FIXTURE)
    assert res["split"] == "parse"
    assert res["parsed"] is True
    for key in ("upos", "xpos", "ufeats", "lemma", "uas", "las", "clas"):
        assert 0.0 <= res[key] <= 1.0


def test_evaluate_dev_rejects_unknown_track() -> None:
    with pytest.raises(ValueError):
        papygreek.evaluate_on_papygreek_dev("bogus", source=FIXTURE)


def test_papygreek_dev_path_rejects_unknown_track() -> None:
    with pytest.raises(ValueError):
        papygreek.papygreek_dev_path("bogus")


# --- convention decomposition: known by construction ------------------------------


def _known_fold() -> tuple[list[list[_PapyTok]], list[list[_PapyTok]]]:
    """A 6-word fold engineered so every count below is hand-verifiable."""
    gold = [
        [
            ("CCONJ", "c--------"),                 # καί
            ("NOUN", "n-s---mn-"),
            ("NUM", "m-_---__-"),                   # numeral with literal '_' slots
        ],
        [
            ("VERB", "v1spia---"),
            ("NOUN", "n-s---fn-"),                  # specific feminine
            ("ADJ", "a-s---mn-"),
        ],
    ]
    system = [
        [
            ("X", "b--------"),                      # CCONJ→X, pos-code c→b  (coordinator)
            ("NOUN", "n-s---mn-"),                   # exact
            ("NUM", "m--------"),                    # pure '_'→'-'           (underscore)
        ],
        [
            ("VERB", "v1spia---"),                   # exact
            ("NOUN", "n-s---cn-"),                   # gender f→c             (common-gender)
            ("ADJ", "a-p---mn-"),                    # number s→p             (residual real)
        ],
    ]
    return gold, system


def test_upos_convention_split_is_exact() -> None:
    r = _decompose_papygreek(*_known_fold())
    assert r.n_words == 6
    # gold upos CCONJ,NOUN,NUM,VERB,NOUN,ADJ ; sys X,NOUN,NUM,VERB,NOUN,ADJ → only CCONJ→X wrong
    assert r.upos_correct == 5
    assert r.upos_errors == 1
    assert r.upos_coordinator_errors == 1           # the CCONJ→X
    assert r.upos_other_errors == 0
    assert r.coordinator_share == pytest.approx(1.0)
    assert r.upos == pytest.approx(5 / 6)


def test_xpos_convention_split_is_exact_and_additive() -> None:
    r = _decompose_papygreek(*_known_fold())
    # xpos correct: NOUN(n-s---mn-), VERB, NOUN? no NOUN2 is n-s---fn- vs n-s---cn- (wrong).
    # correct = token2 (n-s---mn-) + token4 (verb) = 2
    assert r.xpos_correct == 2
    assert r.xpos_errors == 4
    assert r.xpos_coordinator_poscode == 1
    assert r.xpos_common_gender == 1
    assert r.xpos_underscore_encoding == 1
    assert r.xpos_residual_real == 1
    assert (
        r.xpos_coordinator_poscode + r.xpos_common_gender
        + r.xpos_underscore_encoding + r.xpos_residual_real == r.xpos_errors
    )
    # additive gap identities
    assert r.xpos_convention_pts + r.xpos_residual_pts == pytest.approx(r.xpos_gap)
    assert r.upos_coordinator_pts + r.upos_other_pts == pytest.approx(r.upos_gap)
    assert r.n_gold_xpos_underscore == 1            # only the numeral gold carries '_'
    # forgiving the three convention buckets recovers the residual-only accuracy
    assert r.xpos_forgiving_convention == pytest.approx(5 / 6)


def test_classify_xpos_error_priority_order() -> None:
    # coordinator pos-code beats everything (the whole tag is driven wrong by the label)
    assert _classify_xpos_error("c--------", "b--------") == "coordinator_poscode"
    assert _classify_xpos_error("c--------", "d--------") == "coordinator_poscode"
    # common-gender: predicted gender 'c' where gold is a specific gender
    assert _classify_xpos_error("n-s---mn-", "n-s---cn-") == "common_gender"
    # pure '_'→'-' is the encoding bucket
    assert _classify_xpos_error("m-_---__-", "m--------") == "underscore_encoding"
    # a real morphology error (case) is residual
    assert _classify_xpos_error("n-s---mn-", "n-s---ma-") == "residual_real"
    # a '_'→'-' token that ALSO has a real diff is NOT pure-encoding → residual
    assert _classify_xpos_error("n-_---mn-", "n-a---mn-") == "residual_real"


# --- convention decomposition: reproduces the official evaluator -------------------


def _emit_conllu(forms: list[list[str]], toks: list[list[_PapyTok]]) -> str:
    """A CoNLL-U string from parallel forms + (upos, xpos) tokens (flat single-root tree)."""
    out: list[str] = []
    for si, (sf, st) in enumerate(zip(forms, toks), start=1):
        out.append(f"# sent_id = s{si}")
        for i, (form, (upos, xpos)) in enumerate(zip(sf, st), start=1):
            head, deprel = ("0", "root") if i == 1 else ("1", "dep")
            out.append("\t".join((str(i), form, "_", upos, xpos, "_", head, deprel, "_", "_")))
        out.append("")
    return "\n".join(out) + "\n"


def _eval_available() -> object | None:
    from aegean.data import cache_dir
    from aegean.greek.ud import _CACHE_SUBDIR, _eval_module

    if not (cache_dir() / _CACHE_SUBDIR / "conll18_ud_eval.py").exists():
        try:
            return _eval_module()
        except Exception:
            return None
    return _eval_module()


def test_report_reproduces_official_upos_xpos(tmp_path: Path) -> None:
    """The published-row-unchanged invariant: the decomposition's upos/xpos reproduce the
    official CoNLL-18 evaluator EXACTLY on the same predictions (the 'reproduce to 4 decimals'
    faithfulness the PROIEL decomposition also pins)."""
    ev = _eval_available()
    if ev is None:
        pytest.skip("official evaluator unavailable offline")
    forms = [["καὶ", "λόγος", "θεός"], ["ἦν", "ἀρχή"]]
    gold_toks = [
        [("CCONJ", "c--------"), ("NOUN", "n-s---mn-"), ("NOUN", "n-s---fn-")],
        [("VERB", "v3siia---"), ("NOUN", "n-s---fn-")],
    ]
    pred_toks = [
        [("X", "b--------"), ("NOUN", "n-s---mn-"), ("NOUN", "n-s---cn-")],
        [("VERB", "v3siia---"), ("NOUN", "n-s---fn-")],
    ]
    gold_path = tmp_path / "gold.conllu"
    gold_path.write_text(_emit_conllu(forms, gold_toks), encoding="utf-8")
    report = papygreek_convention_report(source=gold_path, predictions=pred_toks)

    from aegean.greek.ud import _score_conllu_text

    official = _score_conllu_text(
        ev, gold_path.read_text(encoding="utf-8"), _emit_conllu(forms, pred_toks),
        ["upos", "xpos"],
    )
    assert report.upos == pytest.approx(official["upos"], abs=1e-9)
    assert report.xpos == pytest.approx(official["xpos"], abs=1e-9)
    # hand-computed: 1 UPOS error (CCONJ→X) of 5; 2 XPOS errors (c→b, f→c) of 5
    assert report.upos == pytest.approx(0.8)
    assert report.xpos == pytest.approx(0.6)
    assert report.upos_coordinator_errors == 1
    assert report.xpos_coordinator_poscode == 1 and report.xpos_common_gender == 1


def test_report_loads_gold_and_predictions_from_conllu(tmp_path: Path) -> None:
    gold_path = tmp_path / "g.conllu"
    gold_path.write_text(
        "# sent_id = s1\n"
        "1\tκαὶ\tκαί\tCCONJ\tc--------\t_\t0\troot\t_\t_\n"
        "2\tλόγος\tλόγος\tNOUN\tn-s---mn-\t_\t1\tdep\t_\t_\n\n",
        encoding="utf-8",
    )
    preds = [[("X", "b--------"), ("NOUN", "n-s---mn-")]]
    r = papygreek_convention_report(source=gold_path, predictions=preds)
    assert r.n_words == 2
    assert r.upos_coordinator_errors == 1
    assert r.xpos_coordinator_poscode == 1


# --- adversarial edges ------------------------------------------------------------


def test_report_without_pipeline_or_predictions_raises(tmp_path: Path) -> None:
    if joint.active() is not None:
        pytest.skip("neural pipeline is active in this session")
    gold_path = tmp_path / "g.conllu"
    gold_path.write_text(
        "# sent_id = s1\n1\tλόγος\tλόγος\tNOUN\tn-s---mn-\t_\t0\troot\t_\t_\n\n", encoding="utf-8"
    )
    with pytest.raises(NeuralPipelineRequiredError):
        papygreek_convention_report(source=gold_path)


def test_empty_fold_is_all_zero_no_division_error() -> None:
    r = _decompose_papygreek([], [])
    assert isinstance(r, PapyGreekConventionReport)
    assert r.n_words == 0
    assert r.upos == 0.0 and r.xpos == 0.0
    assert r.coordinator_share == 0.0 and r.xpos_convention_pts == 0.0
    assert r.xpos_forgiving_convention == 0.0
    assert r.summary() == "PapyGreek convention decomposition: no words"


def test_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        _decompose_papygreek([[("NOUN", "n--------")]], [])
    with pytest.raises(ValueError):
        _decompose_papygreek([[("NOUN", "n--------"), ("VERB", "v--------")]],
                             [[("NOUN", "n--------")]])


def test_perfect_prediction_has_no_gap() -> None:
    gold = [[("CCONJ", "c--------"), ("NOUN", "n-s---mn-")]]
    r = _decompose_papygreek(gold, gold)
    assert r.upos == pytest.approx(1.0) and r.xpos == pytest.approx(1.0)
    assert r.upos_errors == 0 and r.xpos_errors == 0
    assert r.xpos_convention_pts == 0.0 and r.coordinator_share == 0.0
