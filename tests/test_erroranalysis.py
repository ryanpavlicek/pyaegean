"""The shared error-analysis engine (aegean.greek.erroranalysis) and its per-source adapters.

Offline: PROIEL uses the local fixture, UD the sample CoNLL-U fixture, NT a synthetic corpus
with injected predictors — the same pattern as test_proiel.py / test_nt_eval.py. Verifies the
confusion matrix, per-POS accuracy, seen/unseen split, and that proiel_drift stays a faithful
view of the shared engine."""

from __future__ import annotations

import json
from pathlib import Path

from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.greek import (
    analyze_errors,
    nt_error_analysis,
    proiel_error_analysis,
    ud_error_analysis,
)
from aegean.greek.heldout import HeldoutToken
from aegean.greek.proiel import load_proiel_gold, proiel_drift

PROIEL = str(Path(__file__).parent / "fixtures" / "proiel")
UD = str(Path(__file__).parent / "fixtures" / "ud" / "sample-ud-test.conllu")


def _proiel_gold_map() -> dict[str, tuple[str, str]]:
    return {t.form: (t.lemma, t.upos) for s in load_proiel_gold(source_dir=PROIEL) for t in s}


# --- the engine, directly ---------------------------------------------------------


def _sent(*toks: tuple[str, str, str]) -> tuple[HeldoutToken, ...]:
    # (form, lemma, upos) -> a scored gold sentence; seen alternates to exercise the split
    return tuple(
        HeldoutToken(form=f, lemma=lm, upos=u, seen=(i % 2 == 0), scored=True)
        for i, (f, lm, u) in enumerate(toks)
    )


def test_perfect_tagger_has_no_errors() -> None:
    gold = [_sent(("λόγος", "λόγος", "NOUN"), ("ἦν", "εἰμί", "VERB"))]
    ea = analyze_errors(lambda forms: [{"λόγος": ("λόγος", "NOUN"), "ἦν": ("εἰμί", "VERB")}[f]
                                       for f in forms], gold)
    assert ea.pos_scored == 2 and ea.pos_errors == 0 and ea.lemma_errors == 0
    assert ea.pos_confusions == () and ea.lemma_confusions == () and ea.top_share == 0.0
    assert ea.pos_accuracy == 1.0 and ea.lemma_accuracy == 1.0
    assert all(s.pos_accuracy == 1.0 and s.lemma_accuracy == 1.0 for s in ea.per_pos)
    assert ea.n_seen + ea.n_unseen == ea.pos_scored


def test_confusion_matrix_and_per_pos() -> None:
    gold = [_sent(("λόγος", "λόγος", "NOUN"), ("ἀγαθός", "ἀγαθός", "ADJ"),
                  ("ἦν", "εἰμί", "VERB"))]
    # force every POS to VERB; lemma=form, so only ἦν misses its lemma (εἰμί)
    ea = analyze_errors(lambda forms: [(f, "VERB") for f in forms], gold)  # lemma=form
    assert ea.lemma_errors == 1  # λόγος/ἀγαθός equal their lemmas; ἦν != εἰμί
    assert ea.pos_errors == sum(c for _g, _p, c in ea.pos_confusions)
    assert all(p == "VERB" for _g, p, c in ea.pos_confusions)
    assert ea.pos_confusions == tuple(sorted(ea.pos_confusions, key=lambda t: -t[2]))
    by_pos = {s.pos: s for s in ea.per_pos}
    assert by_pos["VERB"].pos_accuracy == 1.0  # the one VERB is correct
    assert by_pos["NOUN"].pos_accuracy == 0.0 and by_pos["ADJ"].pos_accuracy == 0.0
    assert "-> VERB" in ea.summary()


def test_seen_unseen_split_is_tracked() -> None:
    gold = [_sent(("a", "a", "NOUN"), ("b", "b", "NOUN"), ("c", "c", "NOUN"))]
    # positions 0,2 are seen; 1 is unseen. Get POS right everywhere, lemma wrong only on the unseen.
    ea = analyze_errors(
        lambda forms: [(f if f != "b" else "X", "NOUN") for f in forms], gold
    )
    assert ea.n_seen == 2 and ea.n_unseen == 1
    assert ea.lemma_accuracy_seen == 1.0 and ea.lemma_accuracy_unseen == 0.0
    assert ea.pos_accuracy == 1.0


def test_freq_bands_when_a_frequency_is_supplied() -> None:
    gold = [_sent(("rare", "rare", "NOUN"), ("common", "common", "NOUN"))]
    freq = {"rare": 1, "common": 200}
    ea = analyze_errors(lambda forms: [(f, "NOUN") for f in forms], gold, freq=freq.get)  # type: ignore[arg-type]
    bands = {b: (n, pc, lc) for b, n, pc, lc in ea.freq_bands}
    assert bands["1"][0] == 1 and bands["51+"][0] == 1  # one hapax, one high-frequency


def test_as_dict_is_json_serializable() -> None:
    gold = [_sent(("λόγος", "λόγος", "NOUN"))]
    ea = analyze_errors(lambda forms: [("x", "VERB") for _ in forms], gold)
    d = ea.as_dict()
    assert json.loads(json.dumps(d))  # round-trips
    assert d["pos_scored"] == 1 and d["pos_confusions"] == [["NOUN", "VERB", 1]]
    assert "per_pos" in d and "lemma_confusions" in d


# --- adapters ---------------------------------------------------------------------


def test_proiel_adapter_perfect_tagger() -> None:
    gold = _proiel_gold_map()
    ea = proiel_error_analysis(lambda forms: [gold[f] for f in forms], source_dir=PROIEL)
    assert ea.pos_errors == 0 and ea.lemma_errors == 0
    assert ea.pos_scored > 0 and ea.n_unseen == ea.pos_scored  # PROIEL is wholly unseen


def test_ud_adapter_on_the_conllu_fixture() -> None:
    gold = {}
    # a perfect tagger built from the fixture's own gold (form -> lemma, canon-POS)
    from aegean.greek.proiel import _canon_pos
    from aegean.greek.ud import load_conllu

    for sent in load_conllu(UD):
        for t in sent.tokens:
            gold[t.form] = (t.lemma, _canon_pos(t.upos))
    ea = ud_error_analysis(lambda forms: [gold[f] for f in forms], source=UD)
    assert ea.pos_scored == 7 and ea.pos_errors == 0  # 7 non-PUNCT tokens, all correct
    assert ea.lemma_errors == 0


def test_nt_adapter_reconciles_propn(monkeypatch) -> None:
    toks = [
        Token(text="Ἰησοῦς", kind=TokenKind.WORD, line_no=1, position=0,
              annotations={"lemma": "Ἰησοῦς", "upos": "PROPN", "normalized": "Ἰησοῦς"}),
        Token(text="ἦν", kind=TokenKind.WORD, line_no=1, position=1,
              annotations={"lemma": "εἰμί", "upos": "VERB", "normalized": "ἦν"}),
    ]
    corpus = Corpus([Document(id="v", script_id="greek", tokens=toks, lines=[[0, 1]])],
                    script_id="greek")
    # a perfect predictor (PROPN emitted; both sides reconcile PROPN->NOUN)
    ea = nt_error_analysis(lambda forms: [("Ἰησοῦς", "PROPN"), ("εἰμί", "VERB")][: len(forms)],
                           corpus=corpus)
    assert ea.pos_scored == 2 and ea.pos_errors == 0  # PROPN gold vs PROPN pred, both -> NOUN
    assert {s.pos for s in ea.per_pos} == {"NOUN", "VERB"}  # gold PROPN reconciled to NOUN


# --- proiel_drift is a faithful view of the shared engine -------------------------


def test_proiel_drift_matches_the_shared_engine() -> None:
    tagger = lambda forms: [(f, "VERB") for f in forms]  # noqa: E731
    drift = proiel_drift(tagger, source_dir=PROIEL)
    ea = proiel_error_analysis(tagger, source_dir=PROIEL)
    assert drift.pos_confusions == ea.pos_confusions
    assert drift.lemma_mismatches == ea.lemma_mismatches
    assert (drift.pos_scored, drift.pos_errors, drift.lemma_errors) == (
        ea.pos_scored, ea.pos_errors, ea.lemma_errors
    )


def test_cli_eval_drift_emits_the_error_analysis(monkeypatch) -> None:
    """`aegean greek eval ud --drift --json` renders the ErrorAnalysis as JSON (the CLI
    wiring; the engine itself is tested above, so the eval gold is stubbed)."""
    import typer.testing

    from aegean import greek
    from aegean.cli import _build_app

    canned = analyze_errors(
        lambda forms: [(f, "VERB") for f in forms],
        [_sent(("λόγος", "λόγος", "NOUN"))],
    )
    monkeypatch.setattr(greek, "ud_error_analysis", lambda **k: canned)
    res = typer.testing.CliRunner().invoke(_build_app(), ["greek", "eval", "ud", "--drift", "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["pos_scored"] == 1 and payload["pos_confusions"] == [["NOUN", "VERB", 1]]
