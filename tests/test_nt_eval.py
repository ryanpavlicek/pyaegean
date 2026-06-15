"""The Koine/NT evaluation fold (aegean.greek.nt_eval.evaluate_on_nt).

Offline: a synthetic gold corpus + injected predictors (no neural model needed),
mirroring tests/test_proiel.py — perfect -> 1.0, wrong -> 0.0, and tagset reconciliation."""

from __future__ import annotations

import pytest

from aegean import greek
from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.greek.joint import NeuralPipelineNotLoadedError


def _tok(text: str, lemma: str, upos: str, verse: int, pos: int) -> Token:
    return Token(
        text=text, kind=TokenKind.WORD, line_no=verse, position=pos,
        annotations={"lemma": lemma, "upos": upos, "normalized": text},
    )


def _corpus() -> Corpus:
    toks = [
        _tok("Ἐν", "ἐν", "ADP", 1, 0),
        _tok("ἀρχῇ", "ἀρχή", "NOUN", 1, 1),
        _tok("ἦν", "εἰμί", "VERB", 1, 2),
        _tok("Ἰησοῦς", "Ἰησοῦς", "PROPN", 2, 3),   # PROPN -> canon NOUN
    ]
    doc = Document(id="John 1", script_id="greek", tokens=toks, lines=[[0, 1, 2], [3]])
    return Corpus([doc], script_id="greek")


_GOLD = {"Ἐν": ("ἐν", "ADP"), "ἀρχῇ": ("ἀρχή", "NOUN"),
         "ἦν": ("εἰμί", "VERB"), "Ἰησοῦς": ("Ἰησοῦς", "PROPN")}


def _perfect(forms: list[str]) -> list[tuple[str, str]]:
    return [_GOLD[f] for f in forms]


def test_perfect_predictor_scores_one() -> None:
    r = greek.evaluate_on_nt(_perfect, corpus=_corpus())
    assert r["lemma"] == 1.0 and r["upos"] == 1.0
    assert r["n"] == 4


def test_wrong_predictor_scores_zero() -> None:
    r = greek.evaluate_on_nt(lambda forms: [("zzz", "INTJ") for _ in forms], corpus=_corpus())
    assert r["lemma"] == 0.0 and r["upos"] == 0.0


def test_pos_reconciliation() -> None:
    # predict bare UD NOUN for the proper noun; gold PROPN reconciles to NOUN -> still correct
    def tag(forms: list[str]) -> list[tuple[str, str]]:
        return [(_GOLD[f][0], "NOUN" if f == "Ἰησοῦς" else _GOLD[f][1]) for f in forms]

    assert greek.evaluate_on_nt(tag, corpus=_corpus())["upos"] == 1.0


def test_defaults_to_neural_and_errors_without_it() -> None:
    # No predictor + no neural model loaded (the model is never fetched in tests) -> clear error
    from aegean.greek import joint

    if joint.active() is None:
        with pytest.raises(NeuralPipelineNotLoadedError):
            greek.evaluate_on_nt(corpus=_corpus())
