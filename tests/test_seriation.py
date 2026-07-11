"""Seriation + chronology: correctness (hand values, planted recovery), input handling, journey.

The module is EXPLORATORY, so the tests assert the mathematics the construction guarantees
(a hand-computed Brainerd-Robinson value, recovery of a planted battleship ordering up to
reversal, the honest unparsed count), never any chronological reading.
"""

import random

import pytest

from aegean.analysis.seriation import (
    Chronology,
    DocumentSpan,
    SeriationResult,
    brainerd_robinson,
    chronology,
    seriate,
)
from aegean.core.model import Document, DocumentMeta, Token, TokenKind


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _doc(doc_id: str, period: str, signs: list[str]) -> Document:
    tokens = [
        Token(text="-".join([s]), kind=TokenKind.WORD, signs=(s,)) for s in signs
    ]
    return Document(
        id=doc_id,
        script_id="toy",
        tokens=tokens,
        lines=[list(range(len(tokens)))],
        meta=DocumentMeta(period=period),
    )


# --------------------------------------------------------------------------- #
# Brainerd-Robinson: correctness against hand-computed values
# --------------------------------------------------------------------------- #


def test_brainerd_robinson_hand_value():
    # Both rows already sum to 100. |50-40|+|30-40|+|20-20| = 20, so BR = 200 - 20 = 180.
    sim = brainerd_robinson([[50, 30, 20], [40, 40, 20]])
    assert sim[0][1] == pytest.approx(180.0)
    assert sim[1][0] == pytest.approx(180.0)


def test_brainerd_robinson_identity_and_disjoint():
    # Identical profiles -> 200; fully disjoint types -> 0.
    sim = brainerd_robinson([[10, 0], [1, 0], [0, 5]])
    assert sim[0][0] == pytest.approx(200.0)
    assert sim[0][1] == pytest.approx(200.0)  # same proportions after rescaling
    assert sim[0][2] == pytest.approx(0.0)  # disjoint types
    # Symmetric.
    for i in range(3):
        for j in range(3):
            assert sim[i][j] == pytest.approx(sim[j][i])


def test_brainerd_robinson_rescales_to_percentages():
    # Counts of different totals but identical proportions score 200.
    sim = brainerd_robinson([[2, 1, 1], [200, 100, 100]])
    assert sim[0][1] == pytest.approx(200.0)


def test_brainerd_robinson_range_bound():
    rng = random.Random(0)
    mat = [[rng.randint(0, 20) for _ in range(6)] for _ in range(8)]
    sim = brainerd_robinson(mat)
    for row in sim:
        for v in row:
            assert -1e-9 <= v <= 200.0 + 1e-9


# --------------------------------------------------------------------------- #
# seriate: planted battleship-curve recovery (the key correctness invariant)
# --------------------------------------------------------------------------- #


def _battleship(n_assemblages: int, n_types: int, spread: float = 2.2) -> list[list[float]]:
    """A planted seriation: each type has a unimodal (battleship) peak that marches along
    the assemblage sequence, so assemblage index 0..n-1 is the true order."""
    peaks = [t * (n_assemblages - 1) / (n_types - 1) for t in range(n_types)]
    return [
        [max(0.0, 10.0 - spread * abs(a - peaks[t])) for t in range(n_types)]
        for a in range(n_assemblages)
    ]


def test_seriate_recovers_planted_order_up_to_reversal():
    planted = _battleship(12, 7)
    truth = list(range(12))
    rng = random.Random(42)
    perm = truth[:]
    rng.shuffle(perm)
    shuffled = [planted[p] for p in perm]

    result = seriate(shuffled)
    # Map the recovered row order back to the planted indices.
    recovered = [perm[i] for i in result.order]
    # Seriation has no direction: the answer is the planted order or its exact reverse.
    assert recovered == truth or recovered == truth[::-1]


def test_seriate_recovery_holds_under_multiple_shuffles():
    planted = _battleship(10, 6)
    truth = list(range(10))
    for s in range(5):
        rng = random.Random(100 + s)
        perm = truth[:]
        rng.shuffle(perm)
        recovered = [perm[i] for i in seriate([planted[p] for p in perm]).order]
        assert recovered == truth or recovered == truth[::-1]


def test_seriate_is_a_permutation():
    result = seriate(_battleship(9, 5))
    assert sorted(result.order) == list(range(9))
    assert len(result.similarity) == 9
    assert result.iterations >= 0


def test_seriate_deterministic():
    mat = _battleship(11, 6)
    a = seriate(mat)
    b = seriate(mat)
    assert a.order == b.order
    assert a.similarity == b.similarity


def test_seriate_labels_roundtrip():
    mat = _battleship(4, 3)
    labels = ["w", "x", "y", "z"]
    result = seriate(mat, labels=labels)
    ordered = result.ordered_labels()
    assert ordered is not None
    assert sorted(ordered) == sorted(labels)
    assert set(ordered) == set(labels)


# --------------------------------------------------------------------------- #
# seriate: adversarial / bad input
# --------------------------------------------------------------------------- #


def test_seriate_rejects_empty_matrix():
    with pytest.raises(ValueError):
        seriate([])


def test_seriate_rejects_ragged_matrix():
    with pytest.raises(ValueError):
        seriate([[1, 2, 3], [1, 2]])


def test_seriate_rejects_negative_counts():
    with pytest.raises(ValueError):
        seriate([[1, -2], [3, 4]])


def test_seriate_rejects_bad_max_iter():
    with pytest.raises(ValueError):
        seriate([[1, 2], [3, 4]], max_iter=0)


def test_seriate_rejects_labels_length_mismatch():
    with pytest.raises(ValueError):
        seriate([[1, 2], [3, 4]], labels=["only-one"])


def test_seriate_handles_all_zero_row():
    # A blank assemblage must not crash (its similarities are all zero).
    result = seriate([[0, 0, 0], [1, 2, 3], [3, 2, 1]])
    assert sorted(result.order) == [0, 1, 2]


def test_seriate_tiny_matrix():
    # Two rows: ordering is trivial but must be a valid permutation.
    result = seriate([[1, 0], [0, 1]])
    assert sorted(result.order) == [0, 1]


# --------------------------------------------------------------------------- #
# chronology: correctness + honest unparsed accounting
# --------------------------------------------------------------------------- #


def test_chronology_parses_and_counts_unparsed():
    docs = [
        _doc("a", "480—450 BCE", ["A"]),
        _doc("b", "Third century BC", ["A"]),
        _doc("c", "Hellenistic", ["A"]),  # unparseable
        _doc("d", "", ["A"]),  # unparseable
    ]
    ch = chronology(docs)
    assert isinstance(ch, Chronology)
    assert ch.total == 4
    assert ch.parsed == 2
    assert ch.unparsed == 2
    assert ch.unparsed_fraction == pytest.approx(0.5)


def test_chronology_span_values_match_parse_period():
    ch = chronology([_doc("a", "480—450 BCE", ["A"])])
    span = ch.spans[0]
    assert isinstance(span, DocumentSpan)
    assert span.parsed
    assert (span.start, span.end) == (-480, -450)
    assert span.midpoint == pytest.approx(-465.0)


def test_chronology_unparsed_span_is_none():
    ch = chronology([_doc("a", "Hellenistic", ["A"])])
    span = ch.spans[0]
    assert not span.parsed
    assert span.start is None and span.end is None
    assert span.midpoint is None
    assert ch.parsed_spans() == []


def test_chronology_preserves_order_and_never_drops():
    docs = [_doc(str(i), "" if i % 2 else "II century CE", ["A"]) for i in range(6)]
    ch = chronology(docs)
    assert [s.doc_id for s in ch.spans] == [str(i) for i in range(6)]
    assert ch.total == 6  # none dropped


def test_chronology_empty_corpus():
    ch = chronology([])
    assert ch.total == 0
    assert ch.unparsed_fraction == 0.0


# --------------------------------------------------------------------------- #
# journey: corpus -> chronology + seriate -> read the result
# --------------------------------------------------------------------------- #


def test_journey_seriate_a_corpus_end_to_end():
    # A tiny corpus with a planted signal: docs early/late share sign vocabularies.
    docs = [
        _doc("early-1", "", ["A", "A", "B"]),
        _doc("early-2", "", ["A", "B", "B"]),
        _doc("late-1", "", ["Y", "Z", "Z"]),
        _doc("late-2", "", ["Y", "Y", "Z"]),
    ]
    result = seriate(docs)
    assert isinstance(result, SeriationResult)
    ordered = result.ordered_labels()
    assert ordered is not None
    # The two early docs sit together and the two late docs sit together (either end).
    early = {"early-1", "early-2"}
    assert set(ordered[:2]) == early or set(ordered[2:]) == early


def test_journey_chronology_then_filter_parsed():
    docs = [
        _doc("dated", "II century CE", ["A"]),
        _doc("undated", "somewhere", ["A"]),
    ]
    ch = chronology(docs)
    parsed = ch.parsed_spans()
    assert [s.doc_id for s in parsed] == ["dated"]
    assert parsed[0].start == 101 and parsed[0].end == 200


def test_seriate_accepts_single_document():
    doc = _doc("solo", "", ["A", "B", "A", "C"])
    result = seriate(doc)
    assert result.labels == ("solo",)
    assert result.order == (0,)


def test_seriate_corpus_with_no_signs_raises():
    empty = Document(id="e", script_id="toy", tokens=[], lines=[])
    with pytest.raises(ValueError):
        seriate(empty)
