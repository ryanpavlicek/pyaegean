"""The uniform apparatus surface: ``alt_readings`` + ``apparatus_summary``.

Correctness numbers are pinned on the BUNDLED lineara + cypriot corpora (offline,
no fetch). ``alt_readings`` is exercised both on constructed tokens and through a
real EpiDoc loader path (the ``<app>/<rdg>`` variants that populate ``Token.alt``).
"""

from __future__ import annotations

import json

import pytest

import aegean
from aegean.core.apparatus import (
    AltReading,
    ApparatusSummary,
    alt_readings,
    apparatus_summary,
)
from aegean.core.corpus import Corpus
from aegean.core.model import Document, ReadingStatus, Token, TokenKind


def _corpus_with_alts():
    toks = [
        Token("KU-RO", TokenKind.WORD, ("KU", "RO"), alt=("KU-RA", "TO-SO"), position=0),
        Token("DA", TokenKind.WORD, ("DA",), position=1),
        Token("PA-I-TO", TokenKind.WORD, ("PA", "I", "TO"),
              status=ReadingStatus.UNCLEAR, alt=("PA-I-TE",), position=2),
    ]
    doc = Document("T1", "linearb", toks, [[0, 1, 2]])
    return Corpus([doc], script_id="linearb")


# ── alt_readings ────────────────────────────────────────────────────────────
def test_alt_readings_uniform_shape():
    ars = alt_readings(_corpus_with_alts())
    assert [a.text for a in ars] == ["KU-RO", "PA-I-TO"]     # only tokens with alt
    first = ars[0]
    assert isinstance(first, AltReading)
    assert first.doc_id == "T1" and first.position == 0
    assert first.kind == "word" and first.status == "certain"
    assert first.alternates == ("KU-RA", "TO-SO")
    # the UNCLEAR token surfaces its status alongside its single variant
    assert ars[1].status == "unclear" and ars[1].alternates == ("PA-I-TE",)


def test_alt_readings_accepts_document_and_iterable():
    corp = _corpus_with_alts()
    doc = corp.documents[0]
    assert len(alt_readings(doc)) == 2            # a single Document
    assert len(alt_readings([doc])) == 2          # an iterable of Documents
    assert len(alt_readings(corp)) == 2           # a Corpus


def test_alt_readings_empty_when_no_apparatus():
    assert alt_readings(aegean.load("cypriot")) == []   # bundled corpus carries no <rdg>


def test_alt_readings_from_real_epidoc_loader(tmp_path):
    """The EpiDoc reader populates Token.alt from <app>/<rdg>; alt_readings surfaces
    it identically to constructed tokens (the uniform-shape contract across loaders)."""
    from aegean.io import from_epidoc

    xml = (
        '<?xml version="1.0"?>'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc>'
        "<publicationStmt><idno>PY-1</idno></publicationStmt>"
        "<titleStmt><title>t</title></titleStmt><sourceDesc><p>x</p></sourceDesc>"
        "</fileDesc></teiHeader><text><body><ab>"
        "<app><lem><w>KU-RO</w></lem><rdg><w>KU-RA</w></rdg><rdg><w>TO-SO</w></rdg></app>"
        "<w>DA</w></ab></body></text></TEI>"
    )
    f = tmp_path / "t.xml"
    f.write_text(xml, encoding="utf-8")
    ars = alt_readings(from_epidoc(str(f), script_id="linearb"))
    assert len(ars) == 1
    assert ars[0].doc_id == "PY-1" and ars[0].text == "KU-RO"
    assert ars[0].alternates == ("KU-RA", "TO-SO")


def test_alt_readings_rejects_bad_input():
    for bad in (42, "not-a-corpus", 3.14):
        with pytest.raises(TypeError):
            alt_readings(bad)
    with pytest.raises(TypeError):          # an iterable, but not of Documents
        alt_readings([1, 2, 3])


def test_altreading_to_dict_roundtrips():
    a = AltReading("d", 5, "KU-RO", "word", "unclear", ("KU-RA",))
    assert json.loads(json.dumps(a.to_dict())) == {
        "doc_id": "d", "position": 5, "text": "KU-RO",
        "kind": "word", "status": "unclear", "alternates": ["KU-RA"],
    }


# ── apparatus_summary: real bundled-corpus numbers ──────────────────────────
def test_summary_lineara_pins_real_counts():
    s = apparatus_summary(aegean.load("lineara"))
    assert isinstance(s, ApparatusSummary)
    assert (s.script_id, s.n_documents, s.n_tokens) == ("lineara", 1721, 6406)
    assert s.status_counts == {"certain": 5734, "unclear": 120, "restored": 0, "lost": 552}
    assert s.documents_with_apparatus == 366
    assert s.non_certain == 672 == s.unclear + s.restored + s.lost
    assert s.alt_reading_tokens == 0 and s.alt_reading_examples == ()
    # marker_notes legend only the statuses that occur (unclear + lost, no restored)
    joined = " ".join(s.marker_notes)
    assert "unclear:" in joined and "lost:" in joined and "restored:" not in joined


def test_summary_cypriot_pins_real_counts():
    s = apparatus_summary(aegean.load("cypriot"))
    assert (s.n_documents, s.n_tokens) == (180, 628)
    assert s.status_counts == {"certain": 370, "unclear": 188, "restored": 51, "lost": 19}
    assert s.documents_with_apparatus == 130
    # all four apparatus statuses occur, so all three legend lines are present
    joined = " ".join(s.marker_notes)
    assert all(k in joined for k in ("unclear:", "restored:", "lost:"))


def test_summary_counts_alt_readings_and_notes():
    s = apparatus_summary(_corpus_with_alts())
    assert s.alt_reading_tokens == 2
    assert len(s.alt_reading_examples) == 2
    assert s.alt_reading_examples[0].alternates == ("KU-RA", "TO-SO")
    assert any("alt:" in n for n in s.marker_notes)


def test_summary_empty_corpus():
    s = apparatus_summary(Corpus([], script_id="x"))
    assert s.n_documents == 0 and s.n_tokens == 0
    assert s.status_counts == {"certain": 0, "unclear": 0, "restored": 0, "lost": 0}
    assert s.documents_with_apparatus == 0 and s.marker_notes == ()


def test_summary_rejects_bad_input():
    with pytest.raises(TypeError):
        apparatus_summary(object())


# ── journey: corpus → summary → dict → re-read ──────────────────────────────
def test_journey_summary_to_dict_reread():
    """Load a corpus, summarise it, serialise the summary to a plain dict, round-trip
    it through JSON, and re-read the reconstructed values — the shareable-report path."""
    s = apparatus_summary(aegean.load("cypriot"))
    d = s.to_dict()
    reread = json.loads(json.dumps(d))          # survives a real serialise/deserialise
    assert reread == d
    assert reread["status_counts"] == s.status_counts
    assert reread["tokens"] == 628 and reread["documents"] == 180
    assert reread["non_certain"] == s.non_certain
    assert set(d) == {
        "script_id", "source", "documents", "tokens", "status_counts", "non_certain",
        "documents_with_apparatus", "alt_reading_tokens", "alt_reading_examples",
        "marker_notes",
    }


def test_journey_alt_examples_survive_to_dict():
    d = apparatus_summary(_corpus_with_alts()).to_dict()
    ex = json.loads(json.dumps(d))["alt_reading_examples"]
    assert ex[0]["text"] == "KU-RO" and ex[0]["alternates"] == ["KU-RA", "TO-SO"]
