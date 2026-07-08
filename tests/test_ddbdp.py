"""The DDbDP Greek documentary-papyri loader (offline — a synthetic SQLite fixture, fetch patched).

``aegean.load("ddbdp")`` fetches the project-hosted ``ddbdp-corpus`` release asset (a SQLite corpus
built from the CC BY papyri.info data) and reads it back; ``ddbdp_db()`` exposes the SQLite path for
the memory-friendly ``aegean.db.search`` / ``stream`` access. The network fetch is monkeypatched to a
local fixture so the loader path is exercised offline. A separate test pins the papyrological reading
extractor (``scripts/build_ddbdp_corpus.py``) — the apparatus resolution that is DDbDP-specific.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import aegean
import aegean.data as data
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.db import search, stream, to_sqlite

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def _fixture(tmp_path):
    """A one-document SQLite corpus in a directory, as ``fetch("ddbdp-corpus")`` (extract=True) returns."""
    doc = Document(
        id="bgu.1.100",
        script_id="greek",
        tokens=[
            Token(text="ὁμολογῶ", kind=TokenKind.WORD, line_no=0, position=0),
            Token(text="πεπρακέναι", kind=TokenKind.WORD, line_no=0, position=1),
        ],
        lines=[[0, 1]],
        meta=DocumentMeta(name="BGU 1 100", site="Arsinoite", period="AD 159", notes=("TM 8875", "HGV 8875")),
    )
    corpus = Corpus(
        [doc],
        provenance=Provenance(
            source="DDbDP — Duke Databank of Documentary Papyri (papyri.info), Greek documentary papyri",
            license="CC-BY-3.0 (DDbDP / Duke Collaboratory for Classics Computing, papyri.info)",
            url="https://github.com/papyri/idp.data",
        ),
        script_id="greek",
    )
    d = tmp_path / "ddbdp"
    d.mkdir()
    to_sqlite(corpus, d / "ddbdp.sqlite", fts=True)
    return d


def test_load_ddbdp_reads_the_fetched_sqlite_corpus(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(data, "fetch", lambda name, **k: fixture)

    c = aegean.load("ddbdp")
    assert c.script_id == "greek"
    assert len(c.documents) == 1
    d = c.documents[0]
    assert d.id == "bgu.1.100" and d.meta.name == "BGU 1 100"
    assert [t.text for t in d.tokens] == ["ὁμολογῶ", "πεπρακέναι"]
    assert "TM 8875" in d.meta.notes
    assert "CC-BY-3.0" in c.provenance.license and "DDbDP" in c.provenance.source


def test_ddbdp_db_exposes_fts_and_streaming(tmp_path, monkeypatch):
    """The memory-friendly path: ddbdp_db() -> a SQLite file that search()/stream() read directly."""
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(data, "fetch", lambda name, **k: fixture)

    from aegean.scripts.greek import ddbdp_db

    p = ddbdp_db()
    assert p.name == "ddbdp.sqlite" and p.exists()
    hits = list(search(p, "πεπρακέναι"))
    assert any("πεπρακέναι" in text for _doc, _pos, text in hits)
    assert [d.id for d in stream(p)] == ["bgu.1.100"]


def test_ddbdp_is_a_registered_fetchable_dataset():
    from aegean.data import _REMOTE

    spec = _REMOTE["ddbdp-corpus"]
    assert "CC-BY-3.0" in spec.license
    assert spec.extract is True  # a SQLite DB packed as a tar.gz, unpacked on fetch
    assert spec.url.endswith("ddbdp-corpus.tar.gz") and spec.sha256


def test_papyrological_apparatus_picks_the_preferred_reading():
    """The DDbDP extractor must resolve the apparatus: <reg> over <orig>, <lem> over <rdg>, <add>
    over <del>, and keep abbreviation expansions whole. This is the DDbDP-specific correctness."""
    from build_ddbdp_corpus import edition_lines

    ns = 'xmlns="http://www.tei-c.org/ns/1.0"'
    xml = (
        f'<div {ns} type="edition"><ab>'
        '<choice><reg>πυρράν</reg><orig>φυρα</orig></choice> '
        '<app><lem>δραχμάς</lem><rdg>δραχμαι</rdg></app> '
        '<subst><add>πεπρακέναι</add><del>επρακεν</del></subst> '
        'ἀργυρίου <expan><abbr>δρ</abbr><ex>αχμάς</ex></expan>'
        '</ab></div>'
    )
    text = " ".join(edition_lines(ET.fromstring(xml)))
    assert "πυρράν" in text and "φυρα" not in text          # reg over orig
    assert "δραχμάς" in text and "δραχμαι" not in text        # lem over rdg
    assert "πεπρακέναι" in text and "επρακεν" not in text     # add over del
    assert "δραχμάς" in text                                  # expansion kept whole (δρ + αχμάς)
