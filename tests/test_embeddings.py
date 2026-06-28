"""Distributional sign embeddings: shared-context signs are nearest neighbours.

The module is EXPLORATORY (vectors are distributional, not phonetic/semantic), so the
tests assert the *geometry* the construction guarantees, not any reading.
"""

import math

import pytest

from aegean.analysis.embeddings import SignEmbeddings, sign_embeddings
from aegean.core.model import Document, Token, TokenKind


def _word(signs: list[str]) -> Token:
    """A multi-sign WORD token, e.g. ['A', 'XA', 'B'] -> 'A-XA-B'."""
    return Token(text="-".join(signs), kind=TokenKind.WORD, signs=tuple(signs))


def _doc(words: list[list[str]]) -> Document:
    tokens = [_word(w) for w in words]
    return Document(
        id="X",
        script_id="toy",
        tokens=tokens,
        lines=[list(range(len(tokens)))],
    )


def _shared_context_corpus() -> Document:
    # XA and XB occur in exactly the same neighbour contexts; the other signs do not.
    return _doc(
        [
            ["A", "XA", "B"],
            ["A", "XB", "B"],
            ["C", "XA", "D"],
            ["C", "XB", "D"],
            ["A", "XA", "D"],
            ["A", "XB", "D"],
        ]
    )


def test_shared_context_signs_are_nearest_neighbours():
    emb = sign_embeddings(_shared_context_corpus(), dim=10, window=1)
    assert "XA" in emb.vocab and "XB" in emb.vocab
    # XA's closest sign is XB (and vice versa): identical context profiles.
    assert emb.neighbours("XA", k=1)[0][0] == "XB"
    assert emb.neighbours("XB", k=1)[0][0] == "XA"


def test_neighbour_score_is_high_for_shared_context_pair():
    emb = sign_embeddings(_shared_context_corpus(), dim=10, window=1)
    score = emb.neighbours("XA", k=1)[0][1]
    # Identical context distribution -> near-collinear PPMI rows -> cosine near 1.
    assert score > 0.99


def test_vectors_are_l2_normalized():
    emb = sign_embeddings(_shared_context_corpus(), dim=10, window=1)
    for vec in emb.vectors:
        assert math.isclose(math.sqrt(sum(x * x for x in vec)), 1.0, abs_tol=1e-6)


def test_vector_lookup_and_alignment():
    emb = sign_embeddings(_shared_context_corpus(), dim=10, window=1)
    assert isinstance(emb, SignEmbeddings)
    assert len(emb.vocab) == len(emb.vectors)
    assert all(len(v) == emb.dim for v in emb.vectors)
    v = emb.vector("XA")
    assert v == emb.vectors[emb.vocab.index("XA")]


def test_unknown_sign_raises_keyerror():
    emb = sign_embeddings(_shared_context_corpus(), dim=10, window=1)
    with pytest.raises(KeyError):
        emb.vector("NOPE")
    with pytest.raises(KeyError):
        emb.neighbours("NOPE")


def test_neighbours_excludes_self_and_respects_k():
    emb = sign_embeddings(_shared_context_corpus(), dim=10, window=1)
    nbrs = emb.neighbours("XA", k=3)
    assert "XA" not in [s for s, _ in nbrs]
    assert len(nbrs) == 3
    assert emb.neighbours("XA", k=0) == []


def test_determinism():
    a = sign_embeddings(_shared_context_corpus(), dim=10, window=1)
    b = sign_embeddings(_shared_context_corpus(), dim=10, window=1)
    assert a.vectors == b.vectors
    assert a.vocab == b.vocab


def test_window_widens_context():
    # With window=2, a sign two positions away becomes a context too.
    corpus = _doc([["A", "M", "XA", "B"], ["A", "N", "XB", "B"]])
    emb = sign_embeddings(corpus, dim=10, window=2)
    assert emb.window == 2
    # Sanity: every multi-sign sign is in the vocabulary.
    for s in ("A", "M", "N", "XA", "XB", "B"):
        assert s in emb.vocab


def test_accepts_plain_document_iterable():
    docs = [_doc([["A", "XA", "B"]]), _doc([["A", "XB", "B"]])]
    emb = sign_embeddings(docs, dim=5, window=1)
    assert emb.neighbours("XA", k=1)[0][0] == "XB"


def test_single_sign_words_are_ignored():
    # Only multi-sign words carry internal adjacency; a corpus of singletons fails.
    only_singletons = Document(
        id="S",
        script_id="toy",
        tokens=[Token(text="A", kind=TokenKind.WORD, signs=("A",))],
        lines=[[0]],
    )
    with pytest.raises(ValueError):
        sign_embeddings(only_singletons)


def test_bad_arguments_raise():
    corpus = _shared_context_corpus()
    with pytest.raises(ValueError):
        sign_embeddings(corpus, dim=0)
    with pytest.raises(ValueError):
        sign_embeddings(corpus, window=0)


def test_dim_capped_by_context_vocabulary():
    # Requesting more dimensions than the data supports yields a shorter vector.
    emb = sign_embeddings(_shared_context_corpus(), dim=500, window=1)
    assert 0 < emb.dim <= len(emb.vocab) + 50


def test_rejects_non_document_input():
    with pytest.raises(TypeError):
        sign_embeddings(["not", "documents"])
