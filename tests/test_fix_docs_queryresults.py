"""The analysis layer accepts a query's results wherever it accepts a corpus.

`Corpus.query` returns `aegean.analysis.QueryResults`, so "query, then analyse" is the
documented way to measure a subset. Every coercer in the analysis layer therefore takes a
result set, a `Corpus`, a plain list of documents (and, where it always has, a single
`Document`) and yields the same answer for the same documents, while still refusing a
wrong argument with a ``TypeError`` that names what arrived.
"""

from __future__ import annotations

import pytest

from aegean.analysis import (
    FilterRow,
    chronology,
    dispersion,
    dispersions,
    induce_classes,
    keyness,
    seriate,
    sign_embeddings,
)
from aegean.analysis.graph import cooccurrence_graph
from aegean.analysis.seriation import _is_corpus_like
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind


def _doc(doc_id: str, words: list[str], *, site: str = "HT", period: str = "") -> Document:
    tokens = [
        Token(w, TokenKind.WORD, tuple(w.split("-")), None, 0, i) for i, w in enumerate(words)
    ]
    return Document(
        id=doc_id,
        script_id="lineara",
        tokens=tokens,
        lines=[list(range(len(tokens)))] if tokens else [],
        meta=DocumentMeta(site=site, period=period),
    )


# A corpus small enough to analyse exhaustively, with two sites so a query can
# subset it and the subset can be compared against the same documents by hand.
DOCS = [
    _doc("HT1", ["ku-ro", "pa-i-to", "da-ma-te"], site="Hagia Triada", period="15th c. BC"),
    _doc("HT2", ["ku-ro", "pa-i-to", "di-na"], site="Hagia Triada", period="15th c. BC"),
    _doc("HT3", ["ku-ro", "da-ma-te", "di-na"], site="Hagia Triada", period="LM IB"),
    _doc("ZA1", ["a-ta-i", "ku-ro", "pa-i-to"], site="Zakros", period="15th c. BC"),
]
CORPUS = Corpus(DOCS, None, None, "lineara")
HAGIA = [d for d in DOCS if d.meta.site == "Hagia Triada"]


def _hagia_results():
    """The Hagia Triada subset as `Corpus.query` returns it."""
    results = CORPUS.query([FilterRow("site-is", "Hagia Triada")])
    assert [d.id for d in results.inscriptions] == ["HT1", "HT2", "HT3"]
    return results


# ── each coercer takes a result set, and answers what the documents answer ────


def test_dispersions_over_query_results_match_the_matched_documents():
    results = _hagia_results()
    assert dispersions(results, min_frequency=1) == dispersions(HAGIA, min_frequency=1)
    # And the subset is genuinely the subset: dispersion spreads ku-ro over the three
    # queried documents, not over the whole corpus's four.
    assert dispersion(results, "ku-ro").parts == 3
    assert dispersion(CORPUS, "ku-ro").parts == 4


def test_keyness_takes_query_results_on_either_side():
    results = _hagia_results()
    expected = keyness(HAGIA, DOCS, min_target=1)
    assert keyness(results, CORPUS, min_target=1) == expected
    assert keyness(HAGIA, CORPUS, min_target=1) == expected
    assert keyness(results, DOCS, min_target=1) == expected


def test_induce_classes_over_query_results_matches_the_matched_documents():
    results = _hagia_results()
    from_query = induce_classes(results, n_classes=2)
    from_docs = induce_classes(HAGIA, n_classes=2)
    assert from_query.classes() == from_docs.classes()
    assert from_query.report == from_docs.report
    # The excluded document's sign is unattested in the subset, so it has no class.
    assert from_query.class_of("ta") == -1
    assert induce_classes(CORPUS, n_classes=2).class_of("ta") >= 0


def test_cooccurrence_graph_over_query_results_matches_the_matched_documents():
    results = _hagia_results()
    from_query = cooccurrence_graph(results, level="word", min_count=1)
    from_docs = cooccurrence_graph(HAGIA, level="word", min_count=1)
    assert [(n.id, n.frequency) for n in from_query.nodes] == [
        (n.id, n.frequency) for n in from_docs.nodes
    ]
    assert [(e.source, e.target, e.weight) for e in from_query.edges] == [
        (e.source, e.target, e.weight) for e in from_docs.edges
    ]
    # ZA1's a-ta-i belongs to the excluded document, so the subset never sees it.
    assert "a-ta-i" not in {n.id for n in from_query.nodes}
    assert "a-ta-i" in {n.id for n in cooccurrence_graph(CORPUS, level="word").nodes}


def test_sign_embeddings_over_query_results_match_the_matched_documents():
    results = _hagia_results()
    from_query = sign_embeddings(results, dim=4)
    from_docs = sign_embeddings(HAGIA, dim=4)
    assert from_query.vocab == from_docs.vocab
    assert from_query.vectors == from_docs.vectors


def test_chronology_over_query_results_matches_the_matched_documents():
    results = _hagia_results()
    from_query = chronology(results)
    assert from_query.spans == chronology(HAGIA).spans
    # Hand-checked: HT1 and HT2 carry a readable date, HT3's relative phase is not.
    assert (from_query.total, from_query.parsed, from_query.unparsed) == (3, 2, 1)


def test_seriate_over_query_results_matches_the_matched_documents():
    results = _hagia_results()
    from_query = seriate(results)
    from_docs = seriate(HAGIA)
    assert from_query.order == from_docs.order
    assert from_query.labels == from_docs.labels == ("HT1", "HT2", "HT3")
    assert from_query.components == from_docs.components


# ── the inputs that already worked keep working ──────────────────────────────


def test_corpus_and_document_list_are_unchanged():
    assert dispersions(CORPUS, min_frequency=1) == dispersions(DOCS, min_frequency=1)
    assert chronology(CORPUS).spans == chronology(DOCS).spans
    assert seriate(CORPUS).labels == seriate(DOCS).labels == ("HT1", "HT2", "HT3", "ZA1")
    assert sign_embeddings(CORPUS, dim=4).vocab == sign_embeddings(DOCS, dim=4).vocab
    assert (
        induce_classes(CORPUS, n_classes=2).classes()
        == induce_classes(DOCS, n_classes=2).classes()
    )
    assert [n.id for n in cooccurrence_graph(CORPUS).nodes] == [
        n.id for n in cooccurrence_graph(DOCS).nodes
    ]


def test_single_document_still_works_where_it_did():
    # Seriation and embeddings have always taken one document as a corpus of one.
    assert chronology(DOCS[0]).total == 1
    assert sign_embeddings(DOCS[0], dim=4).vocab == sign_embeddings([DOCS[0]], dim=4).vocab


def test_words_only_results_behave_like_no_documents():
    # ``output="words"`` produces a result set with no matched inscriptions; it must
    # read as an empty document list, not as an unusable argument.
    words = CORPUS.query([FilterRow("word-contains", "ku")], output="words")
    assert words.words and not words.inscriptions
    assert chronology(words).total == chronology([]).total == 0
    assert cooccurrence_graph(words).nodes == cooccurrence_graph([]).nodes == ()
    # Where no documents is an error, it is the same error either way.
    for empty in (words, []):
        with pytest.raises(ValueError, match="no countable items"):
            dispersions(empty)
        with pytest.raises(ValueError, match="matrix has no rows"):
            seriate(empty)


# ── a wrong argument still fails cleanly, naming what arrived ────────────────


@pytest.mark.parametrize(
    "call",
    [
        lambda arg: dispersions(arg),
        lambda arg: dispersion(arg, "ku-ro"),
        lambda arg: keyness(arg, CORPUS),
        lambda arg: keyness(CORPUS, arg),
        lambda arg: induce_classes(arg, n_classes=2),
        lambda arg: cooccurrence_graph(arg),
        lambda arg: sign_embeddings(arg),
        lambda arg: chronology(arg),
    ],
)
def test_non_iterable_argument_raises_typeerror_naming_it(call):
    with pytest.raises(TypeError, match="corpus or documents, got int"):
        call(7)


@pytest.mark.parametrize(
    "call",
    [
        lambda arg: dispersions(arg),
        lambda arg: dispersion(arg, "ku-ro"),
        lambda arg: keyness(arg, CORPUS),
        lambda arg: keyness(CORPUS, arg),
        lambda arg: induce_classes(arg, n_classes=2),
        lambda arg: cooccurrence_graph(arg),
        lambda arg: sign_embeddings(arg),
        lambda arg: chronology(arg),
    ],
)
def test_list_of_non_documents_raises_typeerror_naming_the_element(call):
    with pytest.raises(TypeError, match="corpus or documents, got str"):
        call(["not", "a", "document"])


def test_seriation_classifier_recognizes_every_corpus_shape():
    # ``seriate`` reads either an abundance table or a corpus, so its classifier decides
    # which. A query's results are a corpus shape; a table of numbers is not.
    assert _is_corpus_like(DOCS[0])
    assert _is_corpus_like(CORPUS)
    assert _is_corpus_like(DOCS)
    assert _is_corpus_like(_hagia_results())
    assert not _is_corpus_like([[2.0, 0.0], [0.0, 2.0]])
    assert not _is_corpus_like(7)


def test_seriate_still_reads_a_bare_matrix_and_rejects_a_wrong_one():
    result = seriate([[2, 0], [1, 1], [0, 2]])
    assert sorted(result.order) == [0, 1, 2]
    assert result.labels is None
    with pytest.raises(ValueError, match="same number of columns"):
        seriate([[1, 2], [3]])
