"""The shared EpiDoc apparatus extractor (scripts/_epidoc.py) and the edition-fidelity flag.

The epigraphy corpora are built through scripts/_epidoc.py; a restored or damaged reading must be
kept as a per-token ReadingStatus, not flattened to CERTAIN (the D2 defect). Offline: synthetic
EpiDoc + a temp build dir; the real corpora are rebuilt from their pinned upstreams separately."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from aegean.core.corpus import Corpus
from aegean.core.model import ReadingStatus
from aegean.core.provenance import Provenance

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from _epidoc import build_greek_corpus, edition_lines, edition_tokens  # noqa: E402

_NS = 'xmlns="http://www.tei-c.org/ns/1.0"'


def _edition(inner: str) -> ET.Element:
    return ET.fromstring(f'<div {_NS} type="edition"><ab>{inner}</ab></div>')


def test_edition_tokens_marks_the_apparatus() -> None:
    ed = _edition(
        '<lb n="1"/>Κόμων <unclear>Μουσαίου</unclear> '
        '<supplied reason="lost">τοῦ</supplied> '
        '<supplied reason="undefined">Ἡρακλείτου</supplied>'
    )
    flat = [(w, s) for line in edition_tokens(ed) for (w, s) in line]
    status = {w: s for w, s in flat}
    assert status["Κόμων"] is ReadingStatus.CERTAIN
    assert status["Μουσαίου"] is ReadingStatus.UNCLEAR       # <unclear>
    assert status["τοῦ"] is ReadingStatus.RESTORED           # <supplied reason="lost">
    assert status["Ἡρακλείτου"] is ReadingStatus.LOST        # <supplied reason="undefined">


def test_edition_tokens_word_takes_most_severe_status() -> None:
    # a word only partly under an apparatus span rounds up to the more severe status
    ed = _edition('Μου<supplied reason="lost">σαίου</supplied>')
    (word, status), = edition_tokens(ed)[0]
    assert word == "Μουσαίου" and status is ReadingStatus.RESTORED


def test_edition_lines_text_is_unchanged_by_status_tracking() -> None:
    # the plain-text view drops status and reads exactly as before (a gap carries no token)
    ed = _edition('Κόμων <gap reason="lost"/> <supplied reason="lost">τοῦ</supplied> χαίρειν')
    assert edition_lines(ed) == ["Κόμων τοῦ χαίρειν"]


def test_break_no_joins_the_split_word() -> None:
    ed = _edition('Ἀλεξ<lb n="2" break="no"/>άνδρου')
    (word, _status), = edition_tokens(ed)[0]
    assert word == "Ἀλεξάνδρου"


def test_build_greek_corpus_sets_status_and_fidelity(tmp_path) -> None:
    doc = (
        '<?xml version="1.0"?>'
        f'<TEI {_NS}><text><body>'
        '<div type="edition" xml:lang="grc"><ab>'
        '<lb n="1"/>σωτῆρι <supplied reason="lost">θεῷ</supplied></ab></div>'
        '</body></text></TEI>'
    )
    (tmp_path / "T1.xml").write_text(doc, encoding="utf-8")
    out = tmp_path / "corpus.json"

    def _is_greek(root):
        from _epidoc import primary_edition
        ed = primary_edition(root)
        return ed is not None and ed.get("{http://www.w3.org/XML/1998/namespace}lang") == "grc"

    def _meta(root, stem):
        from aegean.core.model import DocumentMeta
        return DocumentMeta(name=stem)

    greek, written = build_greek_corpus(
        tmp_path, is_greek=_is_greek, metadata=_meta, out=out,
        source="Test", license="CC-BY-4.0", url="http://example.test",
        edition_fidelity="apparatus-preserved,normalized",
    )
    assert (greek, written) == (1, 1)
    c = Corpus.from_json(out)
    statuses = {t.text: t.status for t in c.documents[0].tokens}
    assert statuses["σωτῆρι"] is ReadingStatus.CERTAIN
    assert statuses["θεῷ"] is ReadingStatus.RESTORED
    assert c.provenance.edition_fidelity == "apparatus-preserved,normalized"


def test_edition_fidelity_round_trips_through_json() -> None:
    prov = Provenance(source="s", license="x", edition_fidelity="apparatus-preserved,epichoric")
    c = Corpus([], provenance=prov, script_id="greek")
    back = Corpus.from_json(c.to_json())
    assert back.provenance.edition_fidelity == "apparatus-preserved,epichoric"
