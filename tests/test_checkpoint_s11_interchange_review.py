"""Focused regression tests for §11 EpiDoc, RDF, interop, and merged-tree review fixes."""

from __future__ import annotations

import csv
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import _epidoc  # noqa: E402
from aegean.core.corpus import Corpus  # noqa: E402
from aegean.core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind  # noqa: E402
from aegean.io import epidoc as io_epidoc  # noqa: E402
from aegean.io import rdf as io_rdf  # noqa: E402
from aegean.io._interop_spacy import _lossy_document as spacy_lossy_document  # noqa: E402
from aegean.io._interop_stanza import _lossy_document as stanza_lossy_document  # noqa: E402
from aegean.io.review import apply_merged, merge_review_tables, to_review_table  # noqa: E402


def test_scripts_epidoc_preserves_expan_abbr_lem_and_skips_del_surplus() -> None:
    xml = (
        '<div type="edition">'
        '<expan><abbr>Αὐρ</abbr><ex>ήλιος</ex></expan> '
        '<app><lem>λόγος</lem><rdg>λόγον</rdg></app> '
        '<subst><del>α</del><add>ε</add></subst>ν '
        '<surplus>ξ</surplus>καί'
        '</div>'
    )
    lines = _epidoc.edition_tokens(ET.fromstring(xml), choice_prefer=True)
    words = [w for line in lines for w, _st in line]
    assert words == ["Αὐρήλιος", "λόγος", "εν", "καί"]


def test_io_epidoc_skips_del_and_surplus_in_subst(tmp_path: Path) -> None:
    xml_path = tmp_path / "subst.xml"
    xml_path.write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div type="edition"><w><subst><del>α</del><add>ε</add></subst>ν</w> '
        '<w><surplus>ξ</surplus>καί</w></div>'
        '</body></text></TEI>',
        encoding="utf-8",
    )
    corpus = io_epidoc.from_epidoc(xml_path, script_id="greek")
    assert [t.text for t in corpus.documents[0].tokens] == ["εν", "καί"]


def test_rdf_coords_accepts_space_and_comma_and_rejects_out_of_range() -> None:
    assert io_rdf._coords("37.0755, 15.2866") == ("37.0755", "15.2866")
    assert io_rdf._coords("37.0755 15.2866") == ("37.0755", "15.2866")
    assert io_rdf._coords("95.0 15.2866") is None
    assert io_rdf._coords("37.0755 190.0") is None
    assert io_rdf._coords("Athens") is None


def test_spacy_lossy_unparsed_sentence_preserves_none_heads() -> None:
    # Unparsed spaCy Doc: every token is self-headed with dep_ == ""
    t0 = SimpleNamespace(i=0, text="λόγος", lemma_="λόγος", pos_="NOUN", tag_="", morph="", dep_="", is_sent_start=True)
    t1 = SimpleNamespace(i=1, text="ἐστί", lemma_="εἰμί", pos_="VERB", tag_="", morph="", dep_="", is_sent_start=False)
    t0.head = t0
    t1.head = t1

    class _FakeDoc:
        text = "λόγος ἐστί"

        def __iter__(self):
            return iter((t0, t1))

        def __getitem__(self, sl):
            return SimpleNamespace(text="λόγος ἐστί")

    interop_doc = spacy_lossy_document(_FakeDoc())
    toks = interop_doc.ud_document.sentences[0].tokens
    assert [t.head for t in toks] == [None, None]
    assert [t.deprel for t in toks] == ["_", "_"]


def test_stanza_lossy_unparsed_sentence_preserves_none_heads() -> None:
    w1 = SimpleNamespace(id=1, text="λόγος", lemma="λόγος", upos="NOUN", xpos="_", feats="_", head=None, deprel=None, deps=None, misc=None)
    w2 = SimpleNamespace(id=2, text="ἐστί", lemma="εἰμί", upos="VERB", xpos="_", feats="_", head=None, deprel=None, deps=None, misc=None)
    sent = SimpleNamespace(
        sent_id="s1",
        text="λόγος ἐστί",
        tokens=[SimpleNamespace(id=(1,), text="λόγος", words=[w1]), SimpleNamespace(id=(2,), text="ἐστί", words=[w2])],
    )
    doc = SimpleNamespace(text="λόγος ἐστί", sentences=[sent])
    interop_doc = stanza_lossy_document(doc)
    toks = interop_doc.ud_document.sentences[0].tokens
    assert [t.head for t in toks] == [None, None]


def test_merge_review_tables_catches_combined_cycle_and_cleans_rolled_back_notes(tmp_path: Path) -> None:
    # Two-token sentence with valid initial tree: tok 0 (head 0, root), tok 1 (head 1, obj)
    tokens = (
        Token(
            text="εἶπε", kind=TokenKind.WORD, line_no=1, position=0, status=ReadingStatus.CERTAIN,
            annotations={
                "lemma": "λέγω", "upos": "VERB", "head": "0", "deprel": "root",
                "dependency_sentence_id": "s1", "dependency_index": "1",
            },
        ),
        Token(
            text="λόγον", kind=TokenKind.WORD, line_no=1, position=1, status=ReadingStatus.CERTAIN,
            annotations={
                "lemma": "λόγος", "upos": "NOUN", "head": "1", "deprel": "obj",
                "dependency_sentence_id": "s1", "dependency_index": "2",
            },
        ),
    )
    doc = Document(id="d1", script_id="greek", tokens=tokens, lines=("εἶπε λόγον",), meta=DocumentMeta())
    corpus = Corpus([doc], script_id="greek")

    base_csv = tmp_path / "base.csv"
    to_review_table(corpus, base_csv, selection="all", fields=("lemma", "head", "deprel"))

    with base_csv.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2

    # Reviewer A changes tok 0 head -> 2 (still valid alone? No, wait: A makes tok 0 head=2,
    # deprel=advcl AND tok 1 head=0, deprel=root? Even simpler: A changes tok 0 head=2,
    # B keeps tok 1 head=1 via explicit accept -> combined tree has 0 roots and cycle 1<->2!).
    rev_a = tmp_path / "rev_a.csv"
    rev_b = tmp_path / "rev_b.csv"
    fieldnames = list(rows[0].keys())

    rows_a = [dict(r) for r in rows]
    rows_a[0]["decision_head"] = "correct"
    rows_a[0]["correct_head"] = "2"
    rows_a[0]["decision_deprel"] = "correct"
    rows_a[0]["correct_deprel"] = "advcl"
    rows_a[0]["reviewer"] = "Alice"
    rows_a[0]["reviewer_note"] = "Alice cycle head edit"
    with rev_a.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_a)

    rows_b = [dict(r) for r in rows]
    rows_b[1]["decision_head"] = "accept"
    rows_b[1]["decision_lemma"] = "accept"
    rows_b[1]["reviewer"] = "Bob"
    rows_b[1]["reviewer_note"] = "Bob lemma+head note"
    with rev_b.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_b)

    merged = merge_review_tables([rev_a, rev_b], corpus=corpus, on_conflict="report")
    # Combined cycle (head=[2, 1]) must be surfaced as a conflict at merge time and rolled back
    assert merged.conflicts
    assert merged.conflicts[0].field == "head"
    # Alice's rolled-back dependency note must NOT remain on row 0
    row0 = next(r for r in merged.rows if r["position"] == "0")
    assert row0["correct_head"] == ""
    assert row0["decision_head"] == ""
    assert row0["reviewer"] == ""
    assert row0["reviewer_note"] == ""
    # Bob's clean lemma decision on row 1 survives and applies cleanly!
    row1 = next(r for r in merged.rows if r["position"] == "1")
    assert row1["decision_lemma"] == "accept"
    assert row1["decision_head"] == ""
    assert row1["reviewer"] == "Bob"
    applied = apply_merged(merged, corpus)
    assert applied.documents[0].tokens[1].annotations["lemma_verified"] == "true"

    with pytest.raises(ValueError, match="conflict"):
        merge_review_tables([rev_a, rev_b], corpus=corpus, on_conflict="error")
