"""DDbDP papyri.info document-URI minting for the RDF export, and the harvest map.

Three dimensions (the CONTRIBUTING rule for a feature that reads external input and is a step
in a user journey):

* **correctness** — the harvest parser turns real ``git grep`` lines into ``{stem: hybrid}``
  (round-tripping through gzip), and ``to_rdf`` mints ``http://papyri.info/ddbdp/<hybrid>``
  subjects with the Trismegistos URI moved to ``rdfs:seeAlso``, for the plain, division-suffix,
  dotted-series, and empty-volume hybrid forms (real examples harvested from idp.data);
* **adversarial / degradation** — when the map asset is unavailable the export stays offline-capable:
  it falls back to Trismegistos subjects with a single warning, never an error;
* **journey** — a ``DDb <hybrid>`` note on the document is honoured over the fetched map (a rebuilt
  corpus carries the note natively), and the builder's ``_metadata`` emits that note.

No network and no optional deps: the map fetch is monkeypatched to a local gzip fixture (or made to
raise), so every test runs under a bare ``pytest`` invocation offline.
"""

from __future__ import annotations

import gzip
import json
import logging
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import aegean.data as data
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.io import to_rdf
from aegean.io.rdf import _ddbdp_hybrid, _document_uri, _is_ddbdp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_ddbdp_corpus  # noqa: E402
import build_ddbdp_uri_map as urimap  # noqa: E402

# Real stem -> hybrid pairs harvested from github.com/papyri/idp.data (every form the ddb-hybrid
# takes): a plain key, a division-suffixed key (underscore is part of the number), a dotted-series
# + empty-volume key (the ambiguous ``;;`` case), and a dotted-series-with-volume key.
_FIXTURE_MAP = {
    "bgu.1.100": "bgu;1;100",
    "aegyptus.103.69_1": "aegyptus;103;69_1",
    "p.alex.giss.47": "p.alex.giss;;47",
    "p.lond.4.1610": "p.lond;4;1610",
    "o.narm.72": "o.narm;;72",
}


# ── fixtures ────────────────────────────────────────────────────────────────────
def _ddbdp_prov() -> Provenance:
    """The DDbDP corpus provenance (what a load / subset carries), used for detection."""
    return Provenance(
        source="DDbDP — Duke Databank of Documentary Papyri (papyri.info), Greek documentary papyri",
        license="CC-BY-3.0 (DDbDP / Duke Collaboratory for Classics Computing, papyri.info)",
        url="https://github.com/papyri/idp.data",
    )


def _ddbdp_doc(doc_id: str, tm: str | None = None, notes_extra: tuple[str, ...] = ()) -> Document:
    notes = (*notes_extra, *((f"TM {tm}",) if tm else ()))
    return Document(
        id=doc_id, script_id="greek",
        tokens=[Token("λόγος", TokenKind.WORD, line_no=0, position=0)],
        lines=[[0]],
        meta=DocumentMeta(name=doc_id, notes=notes),
    )


def _ddbdp_corpus(docs: list[Document]) -> Corpus:
    return Corpus(docs, provenance=_ddbdp_prov(), script_id="greek")


@pytest.fixture
def map_asset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write the fixture map as a real gzip and make ``fetch('ddbdp-uris')`` return it."""
    gz = tmp_path / "ddbdp-uris.json.gz"
    with gzip.open(gz, "wt", encoding="utf-8") as f:
        json.dump(_FIXTURE_MAP, f, ensure_ascii=False)

    def fake_fetch(name: str, **kw: object) -> Path:
        assert name == "ddbdp-uris"
        return gz

    monkeypatch.setattr(data, "fetch", fake_fetch)
    return gz


# ── harvest: parsing + gzip round-trip ──────────────────────────────────────────
def test_parse_grep_line_extracts_stem_and_hybrid() -> None:
    line = (
        'HEAD:DDB_EpiDoc_XML/bgu/bgu.1/bgu.1.100.xml:12:'
        '            <idno type="ddb-hybrid">bgu;1;100</idno>'
    )
    assert urimap.parse_grep_line(line) == ("bgu.1.100", "bgu;1;100")


def test_parse_grep_line_unescapes_entities_and_ignores_non_hits() -> None:
    # an XML entity in the idno is unescaped; a line without a ddb-hybrid idno yields None
    amp = 'HEAD:DDB_EpiDoc_XML/x/x.1/x.1.1.xml:3:<idno type="ddb-hybrid">a&amp;b;1;1</idno>'
    assert urimap.parse_grep_line(amp) == ("x.1.1", "a&b;1;1")
    assert urimap.parse_grep_line("HEAD:DDB_EpiDoc_XML/y.xml:1:<title>y</title>") is None


def test_harvest_map_and_gzip_roundtrip(tmp_path: Path) -> None:
    grep = "\n".join(
        f'HEAD:DDB_EpiDoc_XML/a/{stem}.xml:12:<idno type="ddb-hybrid">{hybrid}</idno>'
        for stem, hybrid in _FIXTURE_MAP.items()
    )
    harvested = urimap.harvest_map(grep)
    assert harvested == _FIXTURE_MAP

    gz = tmp_path / "m.json.gz"
    with gzip.open(gz, "wt", encoding="utf-8") as f:
        json.dump(dict(sorted(harvested.items())), f, ensure_ascii=False)
    assert data.load_gzip_json(gz) == _FIXTURE_MAP  # the fetch layer's reader round-trips it


# ── detection ───────────────────────────────────────────────────────────────────
def test_is_ddbdp_detects_by_provenance() -> None:
    assert _is_ddbdp(_ddbdp_corpus([_ddbdp_doc("bgu.1.100")])) is True
    # a non-DDbDP corpus is never detected (its export never fetches the map)
    other = Corpus(
        [_ddbdp_doc("ISic000001")],
        provenance=Provenance(source="I.Sicily", license="CC-BY-4.0", url="https://ex.org"),
        script_id="greek",
    )
    assert _is_ddbdp(other) is False
    assert _is_ddbdp(Corpus([_ddbdp_doc("x")], provenance=None, script_id="greek")) is False


def test_non_ddbdp_export_never_fetches_map(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-DDbDP corpus export must not touch the network even if fetch would fail."""
    def boom(name: str, **kw: object) -> Path:
        raise AssertionError("fetch must not be called for a non-DDbDP corpus")

    monkeypatch.setattr(data, "fetch", boom)
    corpus = Corpus(
        [_ddbdp_doc("ISic000001")],
        provenance=Provenance(source="I.Sicily", license="CC-BY-4.0"),
        script_id="greek",
    )
    out = tmp_path / "isic.ttl"
    to_rdf(corpus, out, fmt="turtle")  # would raise if fetch were called
    assert "urn:aegean:ISic000001" in out.read_text(encoding="utf-8") or "sicily" in out.read_text(
        encoding="utf-8"
    )


# ── URI minting (fixture map) ────────────────────────────────────────────────────
def test_direct_key_mints_papyri_uri_with_tm_seealso(map_asset: Path, tmp_path: Path) -> None:
    corpus = _ddbdp_corpus([_ddbdp_doc("bgu.1.100", tm="8875")])
    out = tmp_path / "d.ttl"
    to_rdf(corpus, out, fmt="turtle")
    text = out.read_text(encoding="utf-8")
    assert "<http://papyri.info/ddbdp/bgu;1;100> rdf:type dctype:Text ;" in text
    # the hybrid + the file-stem + the TM are all identifiers; the TM URI is a see-also
    assert 'dcterms:identifier "bgu.1.100"' in text
    assert 'dcterms:identifier "bgu;1;100"' in text
    assert 'dcterms:identifier "TM 8875"' in text
    assert "rdfs:seeAlso <https://www.trismegistos.org/text/8875>" in text
    # Trismegistos is NOT the subject any more
    assert "<https://www.trismegistos.org/text/8875> rdf:type" not in text


def test_underscore_division_key_resolves_directly(map_asset: Path, tmp_path: Path) -> None:
    """A ``_N`` division suffix is part of the real file stem; it resolves via the DIRECT key
    (not the base-strip fallback), so the underscore survives into the hybrid."""
    corpus = _ddbdp_corpus([_ddbdp_doc("aegyptus.103.69_1", tm="9325")])
    out = tmp_path / "u.jsonld"
    to_rdf(corpus, out, fmt="jsonld")
    node = json.loads(out.read_text(encoding="utf-8"))["@graph"][0]
    assert node["@id"] == "http://papyri.info/ddbdp/aegyptus;103;69_1"
    assert node["rdfs:seeAlso"] == {"@id": "https://www.trismegistos.org/text/9325"}


def test_base_strip_is_a_fallback_for_a_suffix_not_in_the_map(map_asset: Path, tmp_path: Path) -> None:
    """A doc id with a trailing ``_N`` that is NOT itself a map key falls back to the base stem
    (the forward-compatible path): ``bgu.1.100_1`` -> ``bgu.1.100`` -> ``bgu;1;100``."""
    corpus = _ddbdp_corpus([_ddbdp_doc("bgu.1.100_1", tm="8875")])
    out = tmp_path / "b.ttl"
    to_rdf(corpus, out, fmt="turtle")
    text = out.read_text(encoding="utf-8")
    assert "<http://papyri.info/ddbdp/bgu;1;100> rdf:type dctype:Text ;" in text
    assert "rdfs:seeAlso <https://www.trismegistos.org/text/8875>" in text


@pytest.mark.parametrize(
    "doc_id, hybrid",
    [
        ("p.alex.giss.47", "p.alex.giss;;47"),  # dotted series + empty volume (the ;; case)
        ("p.lond.4.1610", "p.lond;4;1610"),     # dotted series with a volume
        ("o.narm.72", "o.narm;;72"),            # simple series + empty volume
    ],
)
def test_dotted_and_empty_volume_hybrids(
    map_asset: Path, tmp_path: Path, doc_id: str, hybrid: str
) -> None:
    corpus = _ddbdp_corpus([_ddbdp_doc(doc_id)])
    out = tmp_path / "e.jsonld"
    to_rdf(corpus, out, fmt="jsonld")
    node = json.loads(out.read_text(encoding="utf-8"))["@graph"][0]
    assert node["@id"] == f"http://papyri.info/ddbdp/{hybrid}"


def test_turtle_semicolon_iri_is_unescaped_and_legal(map_asset: Path, tmp_path: Path) -> None:
    """Semicolons are legal in a Turtle IRIREF (``<...>``); they must appear literally, not
    percent- or UCHAR-escaped."""
    corpus = _ddbdp_corpus([_ddbdp_doc("p.alex.giss.47")])
    out = tmp_path / "s.ttl"
    to_rdf(corpus, out, fmt="turtle")
    text = out.read_text(encoding="utf-8")
    assert "<http://papyri.info/ddbdp/p.alex.giss;;47>" in text
    assert "%3B" not in text and "\\u003B" not in text and "\\u003b" not in text


# ── the "DDb <hybrid>" note is preferred over the map ─────────────────────────────
def test_ddb_note_preferred_over_map(map_asset: Path, tmp_path: Path) -> None:
    """A ``DDb <hybrid>`` note on the document wins over the fetched map (future corpora carry
    the note natively). Here the note disagrees with the map for the same id."""
    doc = _ddbdp_doc("bgu.1.100", tm="8875", notes_extra=("DDb sb;9;9999",))
    out = tmp_path / "n.ttl"
    to_rdf(_ddbdp_corpus([doc]), out, fmt="turtle")
    text = out.read_text(encoding="utf-8")
    assert "<http://papyri.info/ddbdp/sb;9;9999> rdf:type dctype:Text ;" in text
    assert "papyri.info/ddbdp/bgu;1;100" not in text  # the map hybrid was overridden


def test_ddb_note_works_without_the_map() -> None:
    """The note path needs no map at all (a corpus that is not detected as DDbDP still gets a
    papyri.info URI from its own note)."""
    doc = _ddbdp_doc("whatever", notes_extra=("DDb p.oxy;1;1",))
    assert _document_uri(doc, "urn:aegean:", _ddbdp_hybrid(doc, None)) == (
        "http://papyri.info/ddbdp/p.oxy;1;1"
    )


# ── offline degradation: map unavailable → Trismegistos subject + one warning ─────
def test_offline_fallback_to_trismegistos_with_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def unavailable(name: str, **kw: object) -> Path:
        raise data.DataNotAvailableError("no pinned url")

    monkeypatch.setattr(data, "fetch", unavailable)
    corpus = _ddbdp_corpus([_ddbdp_doc("bgu.1.100", tm="8875")])
    out = tmp_path / "off.ttl"
    with caplog.at_level(logging.WARNING, logger="aegean.io.rdf"):
        to_rdf(corpus, out, fmt="turtle")
    text = out.read_text(encoding="utf-8")
    # Trismegistos is the subject again (the documented fallback); no papyri.info URI
    assert "<https://www.trismegistos.org/text/8875> rdf:type dctype:Text ;" in text
    assert "papyri.info/ddbdp/" not in text
    # exactly one warning naming the fallback
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "ddbdp-uris" in warnings[0].getMessage()
    assert "Trismegistos" in warnings[0].getMessage()


# ── the builder-note change (build_ddbdp_corpus._metadata) ────────────────────────
def _synthetic_ddb_root(hybrid: str = "bgu;1;100", tm: str = "8875") -> ET.Element:
    """A minimal DDB EpiDoc TEI header carrying a ddb-hybrid + TM idno."""
    tei = "http://www.tei-c.org/ns/1.0"
    xml = (
        f'<TEI xmlns="{tei}"><teiHeader><fileDesc><publicationStmt>'
        f'<idno type="ddb-hybrid">{hybrid}</idno>'
        f'<idno type="TM">{tm}</idno>'
        f'</publicationStmt></fileDesc></teiHeader></TEI>'
    )
    return ET.fromstring(xml)


def test_builder_metadata_emits_ddb_note() -> None:
    meta = build_ddbdp_corpus._metadata(_synthetic_ddb_root(), "bgu.1.100")
    assert "DDb bgu;1;100" in meta.notes
    assert "TM 8875" in meta.notes
    # the DDb note precedes the TM note (additive, first in the tuple)
    assert meta.notes.index("DDb bgu;1;100") < meta.notes.index("TM 8875")


def test_builder_metadata_no_hybrid_no_ddb_note() -> None:
    tei = "http://www.tei-c.org/ns/1.0"
    root = ET.fromstring(
        f'<TEI xmlns="{tei}"><teiHeader><fileDesc><publicationStmt>'
        f'<idno type="TM">42</idno></publicationStmt></fileDesc></teiHeader></TEI>'
    )
    meta = build_ddbdp_corpus._metadata(root, "x.1.1")
    assert not any(n.startswith("DDb ") for n in meta.notes)
    assert "TM 42" in meta.notes
