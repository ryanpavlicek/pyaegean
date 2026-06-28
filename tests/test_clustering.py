"""Sign-class induction by Brown clustering (analysis.clustering), EXPLORATORY.

The clustering groups signs by distribution, not by phonetic value; the tests
check that property (complementary-distribution sign sets land apart) and the
algorithm's invariants (determinism, the greedy MI-loss objective, the reported
corpus size), not any reading.
"""

from __future__ import annotations

import math

import pytest

from aegean.analysis.clustering import (
    ClusterReport,
    SignClasses,
    induce_classes,
)
from aegean.core.model import Document, DocumentMeta, Token, TokenKind


def _doc(doc_id: str, words: list[str], *, kind: TokenKind = TokenKind.WORD) -> Document:
    tokens = [
        Token(w, kind, tuple(w.split("-")), None, 0, i) for i, w in enumerate(words)
    ]
    return Document(
        id=doc_id,
        script_id="cyprominoan",
        tokens=tokens,
        lines=[list(range(len(tokens)))] if tokens else [],
        meta=DocumentMeta(),
    )


# ── the headline property: complementary distribution -> different classes ───


def _complementary_corpus() -> list[Document]:
    """Two sign sets in strict complementary distribution.

    The X-signs {X1,X2,X3} only ever appear in the first slot of a two-sign
    token; the Y-signs {Y1,Y2,Y3} only ever appear in the second. A
    distributional learner should split them: an X is always preceded by ^ and
    followed by a Y, a Y always preceded by an X and followed by $."""
    xs = ["X1", "X2", "X3"]
    ys = ["Y1", "Y2", "Y3"]
    words: list[str] = []
    for x in xs:
        for y in ys:
            words += [f"{x}-{y}"] * 4
    # Spread across a few documents so it reads like a corpus.
    return [_doc(f"D{i}", words[i::3]) for i in range(3)]


def test_complementary_sets_separate_into_two_classes():
    sc = induce_classes(_complementary_corpus(), n_classes=2)
    assert isinstance(sc, SignClasses)
    assert len(sc) == 2
    # Every X shares a class; every Y shares a class; the two classes differ.
    x_classes = {sc.class_of(s) for s in ("X1", "X2", "X3")}
    y_classes = {sc.class_of(s) for s in ("Y1", "Y2", "Y3")}
    assert len(x_classes) == 1
    assert len(y_classes) == 1
    assert x_classes != y_classes


def test_classes_partition_all_signs():
    sc = induce_classes(_complementary_corpus(), n_classes=2)
    flat = [s for cls in sc.classes() for s in cls]
    assert sorted(flat) == ["X1", "X2", "X3", "Y1", "Y2", "Y3"]
    # class_of agrees with the member lists
    for cid, members in enumerate(sc.classes()):
        for s in members:
            assert sc.class_of(s) == cid


def test_three_way_complementary_distribution():
    # Three slots, three disjoint sign sets, each set bound to one slot.
    a, b, c = ["A1", "A2"], ["B1", "B2"], ["C1", "C2"]
    words = [f"{x}-{y}-{z}" for x in a for y in b for z in c]
    docs = [_doc("D", words * 3)]
    sc = induce_classes(docs, n_classes=3)
    assert len({sc.class_of(s) for s in a}) == 1
    assert len({sc.class_of(s) for s in b}) == 1
    assert len({sc.class_of(s) for s in c}) == 1
    assert len({sc.class_of(a[0]), sc.class_of(b[0]), sc.class_of(c[0])}) == 3


# ── determinism / reproducibility ────────────────────────────────────────────


def test_deterministic():
    docs = _complementary_corpus()
    a = induce_classes(docs, n_classes=2)
    b = induce_classes(docs, n_classes=2)
    assert a.classes() == b.classes()
    assert a.report == b.report


# ── the greedy objective: MI loss is non-negative and monotone ───────────────


def test_mi_loss_nonnegative_and_fewer_classes_costs_more():
    docs = _complementary_corpus()
    fine = induce_classes(docs, n_classes=4)
    coarse = induce_classes(docs, n_classes=2)
    assert fine.report.mi_loss >= -1e-9
    assert coarse.report.mi_loss >= -1e-9
    # Merging down to fewer classes can only give up more (or equal) MI.
    assert coarse.report.mi_loss >= fine.report.mi_loss - 1e-9
    # And the surviving MI shrinks (or holds) as classes are merged.
    assert coarse.report.mutual_information <= fine.report.mutual_information + 1e-9


def test_one_class_per_sign_loses_no_mi():
    docs = _complementary_corpus()
    n_signs = 6
    sc = induce_classes(docs, n_classes=n_signs)
    assert len(sc) == n_signs
    assert sc.report.mi_loss == pytest.approx(0.0, abs=1e-9)


def test_greedy_loss_matches_recomputed_mi():
    # Independently recompute the MI of the induced classing from scratch and
    # confirm the report's mutual_information / mi_loss agree: this validates the
    # incremental merge-loss arithmetic against a from-counts computation.
    docs = _complementary_corpus()
    sc = induce_classes(docs, n_classes=3)
    recomputed = _mi_of_classing(docs, sc)
    assert sc.report.mutual_information == pytest.approx(recomputed, abs=1e-9)


# ── report content ───────────────────────────────────────────────────────────


def test_report_records_corpus_size():
    docs = _complementary_corpus()
    sc = induce_classes(docs, n_classes=2)
    r = sc.report
    assert isinstance(r, ClusterReport)
    assert r.n_signs == 6
    assert r.n_classes == 2
    # 36 two-sign tokens => 72 sign tokens across the corpus.
    assert r.corpus_signs == 72
    assert r.corpus_bigrams > 0
    assert r.perplexity >= 1.0
    assert "EXPLORATORY" not in str(r)  # the caveat lives in the docstrings
    assert "classes" in str(r)


# ── edges ────────────────────────────────────────────────────────────────────


def test_target_exceeding_vocab_clamps_to_one_per_sign():
    docs = [_doc("D", ["A-B", "B-A"])]
    sc = induce_classes(docs, n_classes=99)
    assert len(sc) == 2  # only A and B exist


def test_unattested_sign_is_class_minus_one():
    sc = induce_classes(_complementary_corpus(), n_classes=2)
    assert sc.class_of("NEVER-SEEN") == -1
    assert sc.class_of("ZZ") == -1


def test_accepts_corpus_like_object_with_documents_attribute():
    class _FakeCorpus:
        def __init__(self, docs: list[Document]) -> None:
            self.documents = docs

    sc = induce_classes(_FakeCorpus(_complementary_corpus()), n_classes=2)
    assert len(sc) == 2


def test_signs_from_token_signs_field_when_present():
    # Token.signs (not text.split) is the source of truth for sign decomposition.
    docs = [
        _doc("D", ["FOO"] * 4),  # but give them real multi-sign decompositions
    ]
    docs[0].tokens = [
        Token("w", TokenKind.WORD, ("P", "Q"), None, 0, 0),
        Token("w", TokenKind.WORD, ("R", "S"), None, 0, 1),
        Token("w", TokenKind.WORD, ("P", "Q"), None, 0, 2),
        Token("w", TokenKind.WORD, ("R", "S"), None, 0, 3),
    ]
    sc = induce_classes(docs, n_classes=2)
    assert sorted(s for cls in sc.classes() for s in cls) == ["P", "Q", "R", "S"]


def test_empty_corpus_raises():
    with pytest.raises(ValueError, match="no signs"):
        induce_classes([_doc("D", [])], n_classes=2)


def test_bad_n_classes_raises():
    with pytest.raises(ValueError, match="at least 1"):
        induce_classes(_complementary_corpus(), n_classes=0)


# ── independent MI recomputation (test-only oracle) ──────────────────────────


def _mi_of_classing(docs: list[Document], sc: SignClasses) -> float:
    """Average mutual information (bits) of the class-bigram model implied by
    ``sc``, recomputed from the corpus from scratch as an oracle."""
    start, end = "\x02", "\x03"

    def class_id(sym: str) -> str:
        if sym in (start, end):
            return sym
        return f"c{sc.class_of(sym)}"

    pair: dict[tuple[str, str], int] = {}
    left: dict[str, int] = {}
    right: dict[str, int] = {}
    total = 0
    for d in docs:
        for t in d.tokens:
            if t.kind not in (TokenKind.WORD, TokenKind.LOGOGRAM, TokenKind.UNKNOWN):
                continue
            signs = list(t.signs) if t.signs else (
                t.text.split("-") if "-" in t.text else [t.text]
            )
            if not signs:
                continue
            seq = [start, *signs, end]
            for x, y in zip(seq, seq[1:], strict=False):
                cx, cy = class_id(x), class_id(y)
                pair[(cx, cy)] = pair.get((cx, cy), 0) + 1
                left[cx] = left.get(cx, 0) + 1
                right[cy] = right.get(cy, 0) + 1
                total += 1
    mi = 0.0
    for (cx, cy), n in pair.items():
        p = n / total
        mi += p * math.log2(p * total * total / (left[cx] * right[cy]))
    return mi
