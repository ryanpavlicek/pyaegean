"""The evaluation progress hook: `progress(done, total)` on the long-running evaluators.

The whole-NT run is ~1 h on plain CPU with, previously, zero feedback; `heldout.score`
and `ud.pipeline_conllu` now report per-sentence completion so the CLI (and any caller)
can show the run moving. Correctness: the callback sequence is exact and the scores are
byte-identical with or without it. Adversarial: no callback means no calls, empty input
means no calls, and a raising callback aborts loudly rather than being swallowed."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegean.greek.heldout import HeldoutSplit, HeldoutToken, score
from aegean.greek.ud import load_conllu, pipeline_conllu

CONLLU = Path(__file__).parent / "fixtures" / "ud" / "sample-ud-test.conllu"


def _split(n_sentences: int) -> HeldoutSplit:
    sents = tuple(
        (HeldoutToken(form=f"λόγος{i}", lemma=f"λόγος{i}", upos="NOUN", seen=False, scored=True),)
        for i in range(n_sentences)
    )
    return HeldoutSplit(sentences=sents, train_forms=frozenset(), train_lemma={}, train_pos={})


def _echo_tagger(forms: list[str]) -> list[tuple[str, str]]:
    return [(f, "NOUN") for f in forms]


def test_score_progress_sequence_is_exact_and_result_unchanged() -> None:
    calls: list[tuple[int, int]] = []
    with_cb = score(_echo_tagger, split=_split(5), progress=lambda d, t: calls.append((d, t)))
    without = score(_echo_tagger, split=_split(5))
    assert calls == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]  # every sentence, in order
    assert with_cb == without  # the hook never changes the measurement


def test_score_no_callback_and_empty_split_make_no_calls() -> None:
    calls: list[tuple[int, int]] = []
    score(_echo_tagger, split=_split(0), progress=lambda d, t: calls.append((d, t)))
    assert calls == []  # nothing to report on an empty split
    # and the default is no callback at all: just runs (result already covered above)
    assert score(_echo_tagger, split=_split(2))["n_all"] == 2


def test_score_raising_callback_aborts_loudly() -> None:
    def boom(done: int, total: int) -> None:
        raise RuntimeError("observer failed")

    with pytest.raises(RuntimeError, match="observer failed"):
        score(_echo_tagger, split=_split(3), progress=boom)


def test_pipeline_conllu_progress_covers_every_sentence() -> None:
    sentences = load_conllu(CONLLU)  # the 2-sentence offline UD fixture
    calls: list[tuple[int, int]] = []
    with_cb = pipeline_conllu(sentences, parse=False, progress=lambda d, t: calls.append((d, t)))
    without = pipeline_conllu(sentences, parse=False)
    assert calls == [(1, 2), (2, 2)]
    assert with_cb == without  # identical CoNLL-U output

    calls.clear()
    assert pipeline_conllu([], progress=lambda d, t: calls.append((d, t))) == "\n"
    assert calls == []  # an empty fold reports nothing


def test_evaluate_on_nt_threads_progress_to_the_verse_loop() -> None:
    """End to end: the NT evaluator reports one call per gold verse of the corpus."""
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, Token, TokenKind
    from aegean.greek.nt_eval import evaluate_on_nt

    def tok(text: str, verse: int, pos: int) -> Token:
        return Token(
            text=text, kind=TokenKind.WORD, line_no=verse, position=pos,
            annotations={"lemma": text, "upos": "NOUN"},
        )

    doc = Document(
        id="TestB", script_id="greek",
        tokens=[tok("λόγος", 1, 0), tok("θεός", 2, 1), tok("φῶς", 3, 2)],
        lines=[[0], [1], [2]],
    )
    corpus = Corpus([doc], script_id="greek")
    calls: list[tuple[int, int]] = []
    res = evaluate_on_nt(
        _echo_tagger, corpus=corpus, progress=lambda d, t: calls.append((d, t))
    )
    assert calls == [(1, 3), (2, 3), (3, 3)]  # one per verse
    assert res["n"] == 3 and res["lemma"] == 1.0  # the echo tagger matches the echo gold
