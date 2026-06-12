"""Citation automation: Provenance.bibtex/apa, Corpus.cite, subset + query citations."""

from __future__ import annotations

import json

import pytest

from aegean.analysis.query import FilterRow
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.core.provenance import Provenance

PROV = Provenance(
    source="Example edition via example.org",
    license="CC BY-SA 4.0",
    citation="Editor, A. (1999). The Example Edition.",
    url="https://example.org/edition",
)


def _doc(doc_id: str, site: str, words: list[str]) -> Document:
    tokens = [Token(w, TokenKind.WORD, position=i) for i, w in enumerate(words)]
    return Document(
        id=doc_id, script_id="lineara", tokens=tokens,
        lines=[list(range(len(tokens)))], meta=DocumentMeta(site=site),
    )


@pytest.fixture
def corpus() -> Corpus:
    docs = [
        _doc("X1", "Alpha", ["KU-RO", "KI-RO"]),
        _doc("X2", "Alpha", ["KU-RO"]),
        _doc("X3", "Beta", ["SA-RA"]),
    ]
    return Corpus(docs, None, PROV, "lineara")


# ── Provenance formatting ────────────────────────────────────────────────────
def test_bibtex_contains_only_known_fields():
    entry = PROV.bibtex(key="example")
    assert entry.startswith("@misc{example,")
    assert "title = {Editor, A. (1999). The Example Edition.}" in entry
    assert "year = {1999}" in entry  # extracted from the citation text
    assert "url = {https://example.org/edition}" in entry
    assert "License: CC BY-SA 4.0" in entry
    assert entry.rstrip().endswith("}")


def test_bibtex_omits_year_and_url_when_unknown():
    p = Provenance(source="Somewhere")
    entry = p.bibtex()
    assert "year" not in entry and "url" not in entry
    assert "title = {Somewhere}" in entry


def test_apa_line():
    line = PROV.apa()
    assert line.startswith("Editor, A. (1999). The Example Edition. (1999).")
    assert line.endswith("https://example.org/edition")
    assert Provenance(source="Somewhere").apa() == "Somewhere. (n.d.)."


# ── Corpus.cite ──────────────────────────────────────────────────────────────
def test_corpus_cite_styles(corpus):
    assert corpus.cite() == PROV.cite()
    assert corpus.cite("bibtex").startswith("@misc{lineara-corpus,")
    assert corpus.cite("apa").startswith("Editor, A. (1999).")
    with pytest.raises(ValueError, match="style"):
        corpus.cite("chicago")


def test_corpus_without_provenance_refuses_to_cite():
    bare = Corpus([], None, None, "lineara")
    with pytest.raises(ValueError, match="no provenance"):
        bare.cite()


# ── filtered subsets are citable as the exact subset ─────────────────────────
def test_filter_records_a_subset_note(corpus):
    sub = corpus.filter(site="Alpha")
    assert len(sub) == 2
    note = sub.provenance.notes[-1]
    assert note == "subset: filter(site='Alpha') → 2 of 3 documents"
    assert "[subset: filter(site='Alpha') → 2 of 3 documents]" in sub.cite()
    assert note in sub.cite("bibtex") and note in sub.cite("apa")


def test_filter_notes_chain_and_roundtrip(corpus):
    sub = corpus.filter(site="Alpha").filter(site="Alpha")
    assert sum(n.startswith("subset:") for n in sub.provenance.notes) == 2
    again = Corpus.from_dict(json.loads(sub.to_json()))
    assert again.provenance.notes == sub.provenance.notes  # notes survive the round-trip


# ── query results are citable as the exact result set ────────────────────────
def test_query_results_cite(corpus):
    res = corpus.query([FilterRow("site-is", "Alpha")])
    assert len(res.inscriptions) == 2
    line = res.cite()
    assert line.startswith(PROV.cite())
    assert "query: Site is: Alpha → 2 inscriptions" in line
    assert "query: Site is: Alpha → 2 inscriptions" in res.cite("bibtex")


def test_query_results_word_output_cites_word_count(corpus):
    res = corpus.query([FilterRow("word-prefix", "KU")], output="words")
    assert res.words
    assert f"→ {len(res.words)} words" in res.cite()


def test_query_results_without_provenance_refuse_to_cite():
    from aegean.analysis.query import QueryResults

    with pytest.raises(ValueError, match="no provenance"):
        QueryResults([], []).cite()
