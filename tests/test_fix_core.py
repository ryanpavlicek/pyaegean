"""Regression tests for the core-cluster fixes.

1. `Corpus.fingerprint` covers token kind, `ReadingStatus`, annotations, and the
   provenance ``data_version`` (it used to hash only script id + doc ids + token
   text, so corpora differing in any of those shared a fingerprint and the
   analysis cache could serve wrong results).
2. `Corpus.load` returns an independent `copy` of the (process-cached) bundled
   corpus, so mutating one load never corrupts later loads.
3. `load_work`/`parse_tei_work` refuse a citation range that crosses textparts
   instead of silently truncating it to the start part.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import aegean
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.scripts.greek.perseus import parse_tei_work

GREEKLIT_FIXTURE = Path(__file__).parent / "fixtures" / "greeklit" / "sample.xml"


def _one_doc_corpus(
    *,
    kind: TokenKind = TokenKind.WORD,
    status: ReadingStatus = ReadingStatus.CERTAIN,
    annotations: dict[str, str] | None = None,
    site: str = "S",
    provenance: Provenance | None = None,
) -> Corpus:
    doc = Document(
        id="d1",
        script_id="lineara",
        tokens=[Token("KU-RO", kind, position=0, status=status, annotations=annotations or {})],
        lines=[[0]],
        meta=DocumentMeta(site=site),
    )
    return Corpus([doc], None, provenance, "lineara")


# ── 1. fingerprint sensitivity ───────────────────────────────────────────────
def test_fingerprint_distinguishes_token_kind() -> None:
    """Same text, different TokenKind → different fingerprint (WORD vs LOGOGRAM
    changes what every token-level analysis sees)."""
    word = _one_doc_corpus(kind=TokenKind.WORD)
    logo = _one_doc_corpus(kind=TokenKind.LOGOGRAM)
    assert word.fingerprint() != logo.fingerprint()


def test_fingerprint_distinguishes_reading_status() -> None:
    """Same text, different editorial status → different fingerprint."""
    certain = _one_doc_corpus(status=ReadingStatus.CERTAIN)
    unclear = _one_doc_corpus(status=ReadingStatus.UNCLEAR)
    assert certain.fingerprint() != unclear.fingerprint()


def test_fingerprint_distinguishes_annotations() -> None:
    """Adding or changing a token annotation changes the fingerprint."""
    bare = _one_doc_corpus()
    annotated = _one_doc_corpus(annotations={"lemma": "kuro"})
    other_value = _one_doc_corpus(annotations={"lemma": "kiro"})
    assert bare.fingerprint() != annotated.fingerprint()
    assert annotated.fingerprint() != other_value.fingerprint()


def test_fingerprint_annotation_order_is_canonical() -> None:
    """Annotations hash as sorted items: insertion order can't change the key."""
    ab = _one_doc_corpus(annotations=dict([("lemma", "x"), ("morph", "y")]))
    ba = _one_doc_corpus(annotations=dict([("morph", "y"), ("lemma", "x")]))
    assert ab.fingerprint() == ba.fingerprint()


def test_fingerprint_annotation_key_value_boundary_is_unambiguous() -> None:
    """{'ab': 'c'} and {'a': 'bc'} concatenate identically; the hash must not."""
    a = _one_doc_corpus(annotations={"ab": "c"})
    b = _one_doc_corpus(annotations={"a": "bc"})
    assert a.fingerprint() != b.fingerprint()


def test_fingerprint_distinguishes_data_version() -> None:
    """Two builds of 'the same' corpus at different upstream data versions must
    not share a cache key."""
    v1 = _one_doc_corpus(provenance=Provenance(source="src", data_version="v1"))
    v2 = _one_doc_corpus(provenance=Provenance(source="src", data_version="v2"))
    assert v1.fingerprint() != v2.fingerprint()


def test_fingerprint_still_ignores_document_metadata() -> None:
    """Metadata-only differences (site) still leave the fingerprint unchanged."""
    assert _one_doc_corpus(site="Alpha").fingerprint() == _one_doc_corpus(site="Beta").fingerprint()


# ── 2. Corpus.copy / load isolation ─────────────────────────────────────────
def test_copy_is_structurally_independent_and_content_equal() -> None:
    c = aegean.load("lineara")
    c2 = c.copy()
    assert c2 is not c
    assert c2.documents is not c.documents
    assert len(c2) == len(c)
    assert c2.fingerprint() == c.fingerprint()
    d, d2 = c.documents[0], c2.documents[0]
    assert d2 is not d
    assert d2.tokens is not d.tokens and d2.tokens == d.tokens
    assert d2.lines is not d.lines and d2.lines == d.lines
    assert all(a is not b for a, b in zip(d2.lines, d.lines))  # nested lists fresh too
    assert d2.translations is not d.translations
    # A Token is rebuilt with an independent annotations dict (so a per-token annotation
    # edit stays isolated) — equal in content, but not the same object.
    assert d2.tokens[0] is not d.tokens[0] and d2.tokens[0] == d.tokens[0]
    assert d2.tokens[0].annotations is not d.tokens[0].annotations
    # DocumentMeta and Provenance carry no mutable per-element state, so they stay shared.
    assert d2.meta is d.meta
    assert c2.provenance is c.provenance
    # the id lookup works on the copy and resolves to the copy's document
    assert c2.get(d.id) is d2


def test_copy_sign_inventory_is_independent_but_equivalent() -> None:
    c = aegean.load("lineara")
    c2 = c.copy()
    assert c2.sign_inventory is not None and c.sign_inventory is not None
    assert c2.sign_inventory is not c.sign_inventory
    assert c2.sign_inventory.signs is not c.sign_inventory.signs
    assert len(c2.sign_inventory) == len(c.sign_inventory)
    label = c.sign_inventory.signs[0].label
    # A Sign is rebuilt with an independent attrs dict — equal in content, not the same object.
    s2, s1 = c2.sign_inventory.by_label(label), c.sign_inventory.by_label(label)
    assert s2 is not s1 and s2 == s1
    assert s2 is not None and s1 is not None and s2.attrs is not s1.attrs


def test_load_returns_isolated_corpus_documents() -> None:
    """Clearing one load's document list must not corrupt the next load."""
    n = len(aegean.load("lineara"))
    assert n == 1721
    mutated = aegean.load("lineara")
    mutated.documents.clear()
    assert len(aegean.load("lineara")) == n


def test_load_returns_isolated_document_containers() -> None:
    """In-place edits to a loaded document's tokens/lines must not leak into
    later loads of the same bundled corpus."""
    fresh = aegean.load("lineara")
    doc_id = fresh.documents[0].id
    n_tokens = len(fresh.documents[0].tokens)
    assert n_tokens > 0
    victim = aegean.load("lineara")
    victim.documents[0].tokens.clear()
    victim.documents[0].lines.clear()
    again = aegean.load("lineara").get(doc_id)
    assert again is not None
    assert len(again.tokens) == n_tokens
    assert again.lines  # line structure intact


# ── 3. load_work: no silent cross-textpart truncation ────────────────────────
def test_ref_range_crossing_textparts_raises_and_names_both_parts() -> None:
    """'1.1-2.1' spans book 1 → chapter 2: it used to return book-1 lines only,
    labeled with the full range. It must refuse instead."""
    with pytest.raises(ValueError, match="crosses textparts") as exc:
        parse_tei_work(GREEKLIT_FIXTURE.read_bytes(), "w", ref="1.1-2.1")
    msg = str(exc.value)
    assert "textpart 1" in msg and "textpart 2" in msg


def test_ref_whole_part_range_crossing_textparts_raises() -> None:
    """'1-2' (whole textparts, no line numbers) is also a cross-part range."""
    with pytest.raises(ValueError, match="crosses textparts"):
        parse_tei_work(GREEKLIT_FIXTURE.read_bytes(), "w", ref="1-2")


def test_ref_range_end_resolving_nowhere_raises() -> None:
    """A range whose end names a nonexistent textpart can't quietly become a
    within-part line range."""
    with pytest.raises(ValueError, match="no matching textpart"):
        parse_tei_work(GREEKLIT_FIXTURE.read_bytes(), "w", ref="1.1-99.2")


def test_ref_range_within_one_textpart_still_works() -> None:
    """The guard must not over-refuse: a range inside one textpart still loads,
    with the id naming exactly what was returned."""
    _, _, docs = parse_tei_work(GREEKLIT_FIXTURE.read_bytes(), "w", ref="1.1-1.2")
    assert len(docs) == 1
    assert docs[0].id == "w:1.1-1.2"
    assert len(docs[0].lines) == 2
