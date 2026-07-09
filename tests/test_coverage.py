"""Correctness tests for `greek.missing_forms` (the unresolved-form contribution surface).

Offline, over tiny hand-built corpora. Verifies that a known unresolved form appears with
the right count and representative attestation, that a resolvable (seed-table) form does
NOT appear, that non-word tokens are ignored, that rows are sorted by descending count,
that ``limit`` truncates, and that ``example_position`` falls back to the token index when
``Token.position`` is unset. The fixture forms' evidence classes are asserted first so a
future lemmatizer change fails here loudly instead of silently voiding the test."""

from __future__ import annotations

from aegean import greek
from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.greek import MissingForm, missing_forms

# Nonsense Greek-letter strings the offline cascade cannot resolve (UNRESOLVED), and real
# seed-table words it resolves without review. Guarded by test_fixture_evidence_classes.
UNRESOLVED_A = "ασδφγ"
UNRESOLVED_B = "βλιτκ"
RESOLVED_A = "θεός"
RESOLVED_B = "λόγος"


def _word(text: str, position: int | None) -> Token:
    return Token(text=text, kind=TokenKind.WORD, position=position)


def _corpus(docs: list[Document]) -> Corpus:
    return Corpus(docs, script_id="greek")


def test_fixture_evidence_classes() -> None:
    """Precondition: the fixtures are classified as this test assumes (offline baseline)."""
    for w in (UNRESOLVED_A, UNRESOLVED_B):
        _, src = greek.lemmatize_sourced(w)
        assert greek.needs_review(src), f"{w!r} should be unresolved but was {src.value}"
    for w in (RESOLVED_A, RESOLVED_B):
        _, src = greek.lemmatize_sourced(w)
        assert not greek.needs_review(src), f"{w!r} should resolve but was {src.value}"


def test_unresolved_form_appears_with_count_and_example() -> None:
    d1 = Document(
        id="d1",
        script_id="greek",
        tokens=[
            _word(UNRESOLVED_A, 0),
            Token(text=",", kind=TokenKind.PUNCT, position=1),
            _word(RESOLVED_A, 2),
            _word(UNRESOLVED_A, 3),
        ],
        lines=[[0, 1, 2, 3]],
    )
    d2 = Document(
        id="d2",
        script_id="greek",
        tokens=[
            _word(UNRESOLVED_B, 0),
            _word(RESOLVED_B, 1),
            _word(UNRESOLVED_A, 2),
        ],
        lines=[[0, 1, 2]],
    )
    rows = missing_forms(_corpus([d1, d2]))

    by_form = {r.form: r for r in rows}
    # The two nonsense forms are present; both seed-table words are absent.
    assert set(by_form) == {UNRESOLVED_A, UNRESOLVED_B}
    assert RESOLVED_A not in by_form and RESOLVED_B not in by_form

    # UNRESOLVED_A: 3 WORD occurrences across both docs; first seen at d1 position 0.
    a = by_form[UNRESOLVED_A]
    assert a == MissingForm(form=UNRESOLVED_A, count=3, example_doc_id="d1", example_position=0)
    # UNRESOLVED_B: 1 occurrence; first seen at d2 position 0.
    b = by_form[UNRESOLVED_B]
    assert b == MissingForm(form=UNRESOLVED_B, count=1, example_doc_id="d2", example_position=0)


def test_resolvable_form_never_appears() -> None:
    doc = Document(
        id="only-seed",
        script_id="greek",
        tokens=[_word(RESOLVED_A, 0), _word(RESOLVED_B, 1)],
        lines=[[0, 1]],
    )
    assert missing_forms(_corpus([doc])) == []


def test_sorted_by_count_desc_then_form() -> None:
    # UNRESOLVED_B x3, UNRESOLVED_A x1: the more frequent form ranks first.
    doc = Document(
        id="d",
        script_id="greek",
        tokens=[
            _word(UNRESOLVED_A, 0),
            _word(UNRESOLVED_B, 1),
            _word(UNRESOLVED_B, 2),
            _word(UNRESOLVED_B, 3),
        ],
        lines=[[0, 1, 2, 3]],
    )
    rows = missing_forms(_corpus([doc]))
    assert [(r.form, r.count) for r in rows] == [(UNRESOLVED_B, 3), (UNRESOLVED_A, 1)]


def test_limit_truncates_to_the_top_rows() -> None:
    doc = Document(
        id="d",
        script_id="greek",
        tokens=[
            _word(UNRESOLVED_A, 0),
            _word(UNRESOLVED_A, 1),
            _word(UNRESOLVED_B, 2),
        ],
        lines=[[0, 1, 2]],
    )
    full = missing_forms(_corpus([doc]))
    assert len(full) == 2
    top1 = missing_forms(_corpus([doc]), limit=1)
    assert [r.form for r in top1] == [UNRESOLVED_A]  # the count-2 form only
    # limit=0 is unlimited.
    assert missing_forms(_corpus([doc]), limit=0) == full


def test_non_word_tokens_are_ignored() -> None:
    # A NUMERAL / SEPARATOR whose text would itself be unresolved must not be counted.
    doc = Document(
        id="d",
        script_id="greek",
        tokens=[
            Token(text=UNRESOLVED_A, kind=TokenKind.NUMERAL, position=0),
            Token(text=UNRESOLVED_B, kind=TokenKind.SEPARATOR, position=1),
            _word(UNRESOLVED_A, 2),
        ],
        lines=[[0, 1, 2]],
    )
    rows = missing_forms(_corpus([doc]))
    # Only the single WORD occurrence of UNRESOLVED_A counts.
    assert rows == [MissingForm(form=UNRESOLVED_A, count=1, example_doc_id="d", example_position=2)]


def test_example_position_falls_back_to_token_index() -> None:
    # position=None on the tokens: example_position is the enumerate index within the doc.
    doc = Document(
        id="d",
        script_id="greek",
        tokens=[
            Token(text=".", kind=TokenKind.PUNCT, position=None),
            _word(UNRESOLVED_A, None),
        ],
        lines=[[0, 1]],
    )
    rows = missing_forms(_corpus([doc]))
    assert rows == [MissingForm(form=UNRESOLVED_A, count=1, example_doc_id="d", example_position=1)]
