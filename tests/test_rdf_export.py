"""Linked-Open-Data export (`aegean.io.to_rdf`): Turtle + JSON-LD, stdlib only.

Three dimensions (the CONTRIBUTING rule for an external-facing feature):

* **correctness** — export the bundled Linear A sample and a synthetic Greek corpus (with a fake
  Trismegistos id), re-read the Turtle line-by-line and the JSON-LD with ``json.loads`` and assert
  the minted subject URIs, the license triple, and the language-tagged Greek literal; a real EDH
  document's URI uses its actual Trismegistos id (skipped when the corpus is not cached);
* **adversarial** — quotes / newlines / backslashes / control bytes in text and metadata escape to
  valid output with no raw control byte; empty corpus and a metadata-less document degrade cleanly;
* **journey** — export → re-read the file → content-assert, and the ``aegean export -f ttl|jsonld``
  CLI path with ``-o``.

The writers are stdlib-only, so nothing here needs ``pytest.importorskip`` except the CLI (``typer``)
and the optional external-validation pass (``rdflib``, skipped where absent). All tests pass under a
bare ``pytest`` invocation offline (the bundled ``lineara`` corpus needs no fetch).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import aegean
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.io import to_rdf
from aegean.io.rdf import _license_object

# control bytes that must never appear raw in the output (LF is the sole allowed structural byte)
_FORBIDDEN = frozenset(b for b in range(0x20) if b != 0x0A) | {0x7F}


# ── fixtures ────────────────────────────────────────────────────────────────────
def _greek_corpus_with_tm(tm: str = "888777") -> Corpus:
    """A one-document Greek corpus whose only note is a (fake) Trismegistos id, single-line text."""
    toks = [
        Token("ὁ", TokenKind.WORD, line_no=0, position=0),
        Token("λόγος", TokenKind.WORD, line_no=0, position=1),
    ]
    doc = Document(
        id="G1", script_id="greek", tokens=toks, lines=[[0, 1]],
        meta=DocumentMeta(name="Test line", site="Athens", period="I BCE", notes=(f"TM {tm}",)),
    )
    prov = Provenance(
        source="synthetic", license="CC-BY-SA-4.0 (test)", url="https://example.org/src",
    )
    return Corpus([doc], provenance=prov, script_id="greek")


def _isicily_like_corpus() -> Corpus:
    """A document whose id is an ISic identifier and whose findspot carries coordinates."""
    doc = Document(
        id="ISic099999", script_id="greek",
        tokens=[Token("δῆμος", TokenKind.WORD, line_no=0, position=0)],
        lines=[[0]],
        meta=DocumentMeta(
            name="Test ISic", site="Syracusae", findspot="37.08415, 15.27628",
            notes=("http://pleiades.stoa.org/places/462503",),
        ),
    )
    prov = Provenance(source="synthetic isicily", license="CC-BY-4.0 (test)", url="https://ex.org")
    return Corpus([doc], provenance=prov, script_id="greek")


# ── correctness: Turtle ───────────────────────────────────────────────────────
def test_turtle_lineara_sample_subjects_and_license(tmp_path: Path) -> None:
    """The bundled Linear A sample exports: every subject URI is present, the corpus license
    (Apache-2.0) rides on each document, and the transliteration literal is NOT language-tagged."""
    sample = aegean.load("lineara").subset(["HT1", "HT2", "HT3"])
    out = tmp_path / "lineara.ttl"
    to_rdf(sample, out, fmt="turtle")
    text = out.read_text(encoding="utf-8")

    assert "@prefix dcterms: <http://purl.org/dc/terms/> ." in text
    for doc in sample:
        assert f"<urn:aegean:{doc.id}>" in text  # fragment URIs (no TM / ISic id)
        assert f'dcterms:identifier "{doc.id}"' in text
    assert "a dctype:Text" not in text  # CURIE form is `rdf:type dctype:Text`, not `a`
    assert "rdf:type dctype:Text" in text
    # license present on every document, as the SPDX URI
    assert text.count("dcterms:license <https://spdx.org/licenses/Apache-2.0>") == len(sample)
    # Linear A transliteration is not natural-language Greek → no @grc tag anywhere
    assert "@grc" not in text


def test_turtle_greek_trismegistos_uri_and_lang_literal(tmp_path: Path) -> None:
    """A Greek doc with a TM note mints the Trismegistos subject URI and a @grc reading literal."""
    out = tmp_path / "greek.ttl"
    to_rdf(_greek_corpus_with_tm("888777"), out, fmt="turtle")
    text = out.read_text(encoding="utf-8")

    assert "<https://www.trismegistos.org/text/888777> rdf:type dctype:Text ;" in text
    # the reading text is one language-tagged literal, intact
    assert 'rdf:value "ὁ λόγος"@grc .' in text
    # both the local id and the TM id are recorded as identifiers
    assert 'dcterms:identifier "G1"' in text
    assert 'dcterms:identifier "TM 888777"' in text
    # license triple present, mapped to the CC deed URI
    assert "dcterms:license <https://creativecommons.org/licenses/by-sa/4.0/>" in text


def test_turtle_isicily_uri_geo_and_pleiades(tmp_path: Path) -> None:
    """An ISic-id document mints the canonical I.Sicily URI, a WGS84 geo node, and a Pleiades link."""
    out = tmp_path / "isic.ttl"
    to_rdf(_isicily_like_corpus(), out, fmt="turtle")
    text = out.read_text(encoding="utf-8")

    assert "<http://sicily.classics.ox.ac.uk/inscription/ISic099999>" in text
    assert "geo:lat 37.08415" in text and "geo:long 15.27628" in text
    assert "a geo:SpatialThing" in text
    assert "dcterms:spatial <http://pleiades.stoa.org/places/462503>" in text


# ── correctness: JSON-LD ──────────────────────────────────────────────────────
def test_jsonld_structure(tmp_path: Path) -> None:
    """JSON-LD parses and carries the expected @context, subject @id, type, license, and literal."""
    out = tmp_path / "greek.jsonld"
    to_rdf(_greek_corpus_with_tm("42"), out, fmt="jsonld")
    obj = json.loads(out.read_text(encoding="utf-8"))

    ctx = obj["@context"]
    assert ctx["dcterms"] == "http://purl.org/dc/terms/"
    assert ctx["geo"] == "http://www.w3.org/2003/01/geo/wgs84_pos#"
    assert isinstance(obj["@graph"], list) and len(obj["@graph"]) == 1
    node = obj["@graph"][0]
    assert node["@id"] == "https://www.trismegistos.org/text/42"
    assert node["@type"] == "dctype:Text"
    assert node["dcterms:license"] == {"@id": "https://creativecommons.org/licenses/by-sa/4.0/"}
    assert node["dcterms:identifier"] == ["G1", "TM 42"]
    assert node["rdf:value"] == {"@value": "ὁ λόγος", "@language": "grc"}


def test_jsonld_geo_blank_node(tmp_path: Path) -> None:
    """Coordinates become a geo:SpatialThing object nested under dcterms:spatial in JSON-LD."""
    out = tmp_path / "isic.jsonld"
    to_rdf(_isicily_like_corpus(), out, fmt="jsonld")
    node = json.loads(out.read_text(encoding="utf-8"))["@graph"][0]
    assert node["@id"] == "http://sicily.classics.ox.ac.uk/inscription/ISic099999"
    spatial = node["dcterms:spatial"]
    geo = next(s for s in spatial if isinstance(s, dict) and s.get("@type") == "geo:SpatialThing")
    assert geo["geo:lat"] == 37.08415 and geo["geo:long"] == 15.27628
    assert {"@id": "http://pleiades.stoa.org/places/462503"} in spatial


# ── correctness: license mapping (NonCommercial is never stripped) ─────────────
@pytest.mark.parametrize(
    "license_str, expected, is_iri",
    [
        ("CC-BY-SA-4.0 (Heidelberg)", "https://creativecommons.org/licenses/by-sa/4.0/", True),
        # spaced SPDX form, NonCommercial — the NC term MUST survive
        ("CC BY-NC-SA 4.0 (DAMOS)", "https://creativecommons.org/licenses/by-nc-sa/4.0/", True),
        ("CC-BY-NC-SA-4.0 (IGCyr)", "https://creativecommons.org/licenses/by-nc-sa/4.0/", True),
        ("CC-BY-3.0 (DDbDP)", "https://creativecommons.org/licenses/by/3.0/", True),
        ("Apache-2.0 (corpus JSON); imagery not redistributed", "https://spdx.org/licenses/Apache-2.0", True),
        ("CC0-1.0 (Nestle 1904)", "https://creativecommons.org/publicdomain/zero/1.0/", True),
        ("user-supplied", "user-supplied", False),  # free text kept verbatim as a literal
    ],
)
def test_license_object_mapping(license_str: str, expected: str, is_iri: bool) -> None:
    assert _license_object(license_str) == (expected, is_iri)


def test_noncommercial_license_survives_to_turtle(tmp_path: Path) -> None:
    """An NC corpus exports with its NC license attached — the writer never drops or softens it."""
    doc = Document("d1", "greek", [Token("x", TokenKind.WORD, line_no=0, position=0)], [[0]])
    prov = Provenance(source="s", license="CC-BY-NC-SA-4.0 (test)")
    out = tmp_path / "nc.ttl"
    to_rdf(Corpus([doc], provenance=prov, script_id="greek"), out, fmt="turtle")
    assert "creativecommons.org/licenses/by-nc-sa/4.0/" in out.read_text(encoding="utf-8")


# ── correctness: a real EDH document (skipped when not cached / offline) ────────
def test_edh_real_document_uri_uses_its_trismegistos_id(tmp_path: Path) -> None:
    try:
        edh = aegean.load("edh")
    except Exception as exc:  # not fetched / offline — the correctness of the mapping is covered above
        pytest.skip(f"edh corpus not available: {exc}")
    # find a real document that carries a TM note and check its minted URI matches that id
    doc = next((d for d in edh if any(n.startswith("TM ") for n in d.meta.notes)), None)
    assert doc is not None, "expected EDH documents to carry Trismegistos ids"
    tm = next(n.split()[1] for n in doc.meta.notes if n.startswith("TM "))
    out = tmp_path / "edh.ttl"
    to_rdf(edh.subset([doc.id]), out, fmt="turtle")
    assert f"<https://www.trismegistos.org/text/{tm}> rdf:type dctype:Text" in out.read_text(
        encoding="utf-8"
    )


# ── adversarial: hostile strings escape validly, no raw control bytes ──────────
def _hostile_corpus() -> tuple[Corpus, str]:
    hostile = 'a"b\\c\nd\te' + "\x00\x07\x1f" + "f"  # quote, backslash, LF, tab, NUL, BEL, US
    doc = Document(
        id="EVIL 1/x", script_id="greek",
        tokens=[Token(hostile, TokenKind.WORD, line_no=0, position=0)],
        lines=[[0]],
        meta=DocumentMeta(name='ti"tle\x00', site="s", notes=("TM 999",)),
    )
    prov = Provenance(source="x", license="CC-BY-4.0 (t)", url="https://ex.org")
    return Corpus([doc], provenance=prov, script_id="greek"), hostile


def test_turtle_hostile_text_has_no_raw_control_bytes(tmp_path: Path) -> None:
    corpus, _hostile = _hostile_corpus()
    out = tmp_path / "evil.ttl"
    to_rdf(corpus, out, fmt="turtle")
    raw = out.read_bytes()
    assert not (_FORBIDDEN & set(raw)), "raw control byte leaked into the Turtle output"
    text = out.read_text(encoding="utf-8")
    # the escapes are present: quote, backslash, newline, tab, and UCHAR for NUL/BEL/US
    for esc in ('\\"', "\\\\", "\\n", "\\t", "\\u0000", "\\u0007", "\\u001F"):
        assert esc in text, f"missing escape {esc!r}"


def test_jsonld_hostile_text_roundtrips_via_json(tmp_path: Path) -> None:
    corpus, hostile = _hostile_corpus()
    out = tmp_path / "evil.jsonld"
    to_rdf(corpus, out, fmt="jsonld")
    node = json.loads(out.read_text(encoding="utf-8"))["@graph"][0]
    # json.loads restores the exact hostile string byte-for-byte
    assert node["rdf:value"] == {"@value": hostile, "@language": "grc"}


def test_empty_corpus(tmp_path: Path) -> None:
    prov = Provenance(source="s", license="CC-BY-4.0")
    empty = Corpus([], provenance=prov, script_id="greek")
    ttl = tmp_path / "e.ttl"
    to_rdf(empty, ttl, fmt="turtle")
    text = ttl.read_text(encoding="utf-8")
    assert "@prefix dcterms:" in text  # header present
    assert "dctype:Text" not in text  # no subjects
    jl = tmp_path / "e.jsonld"
    to_rdf(empty, jl, fmt="jsonld")
    assert json.loads(jl.read_text(encoding="utf-8"))["@graph"] == []


def test_document_with_no_metadata(tmp_path: Path) -> None:
    """A metadata-less, provenance-less document exports id + type only, without crashing."""
    doc = Document(id="bare", script_id="lineara", tokens=[], lines=[], meta=DocumentMeta())
    corpus = Corpus([doc], provenance=None, script_id="lineara")
    out = tmp_path / "bare.ttl"
    to_rdf(corpus, out, fmt="turtle")
    text = out.read_text(encoding="utf-8")
    assert "<urn:aegean:bare> rdf:type dctype:Text ;" in text
    assert 'dcterms:identifier "bare"' in text
    assert "dcterms:license" not in text  # no provenance → no license triple
    jl = tmp_path / "bare.jsonld"
    to_rdf(corpus, jl, fmt="jsonld")
    node = json.loads(jl.read_text(encoding="utf-8"))["@graph"][0]
    assert node == {"@id": "urn:aegean:bare", "@type": "dctype:Text", "dcterms:identifier": "bare"}


def test_unknown_format_raises(tmp_path: Path) -> None:
    doc = Document("d", "greek", [], [])
    with pytest.raises(ValueError, match="unknown RDF format"):
        to_rdf(Corpus([doc], script_id="greek"), tmp_path / "x.rdf", fmt="rdfxml")


def test_custom_base_uri(tmp_path: Path) -> None:
    doc = Document("doc 1", "lineara", [Token("KU", TokenKind.WORD, line_no=0, position=0)], [[0]])
    corpus = Corpus([doc], provenance=Provenance(source="s"), script_id="lineara")
    out = tmp_path / "b.ttl"
    to_rdf(corpus, out, fmt="turtle", base_uri="https://example.org/x/")
    # the id's space is percent-encoded into a valid IRI fragment under the caller's base
    assert "<https://example.org/x/doc%201>" in out.read_text(encoding="utf-8")


# ── journey: export → re-read → assert; and the CLI path ──────────────────────
def test_journey_turtle_reread_all_subjects(tmp_path: Path) -> None:
    corpus = aegean.load("lineara").subset(["HT1", "HT2", "HT3", "HT6a"])
    out = tmp_path / "j.ttl"
    to_rdf(corpus, out, fmt="turtle")
    text = out.read_text(encoding="utf-8")
    minted = {f"<urn:aegean:{d.id}>" for d in corpus}
    assert all(uri in text for uri in minted)
    assert text.count("rdf:type dctype:Text") == len(corpus)


@pytest.fixture(scope="module")
def cli_app():  # type: ignore[no-untyped-def]
    pytest.importorskip("typer")
    from aegean.cli import _build_app

    return _build_app()


def test_cli_export_ttl(cli_app, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    out = tmp_path / "out.ttl"
    res = CliRunner().invoke(
        cli_app, ["export", "lineara", "--site", "Haghia Triada", "-f", "ttl", "-o", str(out)]
    )
    assert res.exit_code == 0, res.output
    subset = aegean.load("lineara").filter(site="Haghia Triada")
    text = out.read_text(encoding="utf-8")
    assert "@prefix dcterms:" in text
    assert text.count("rdf:type dctype:Text") == len(subset)
    assert "dcterms:license" in text
    # each filtered document has its fragment subject URI
    for d in list(subset)[:20]:
        assert f"<urn:aegean:{d.id}>" in text


def test_cli_export_jsonld(cli_app, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    out = tmp_path / "out.jsonld"
    res = CliRunner().invoke(
        cli_app, ["export", "lineara", "--site", "Haghia Triada", "-f", "jsonld", "-o", str(out)]
    )
    assert res.exit_code == 0, res.output
    obj = json.loads(out.read_text(encoding="utf-8"))
    subset = aegean.load("lineara").filter(site="Haghia Triada")
    assert len(obj["@graph"]) == len(subset)


def test_cli_export_ttl_base_uri(cli_app, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    out = tmp_path / "based.ttl"
    res = CliRunner().invoke(
        cli_app,
        ["export", "lineara", "--site", "Haghia Triada", "-f", "ttl",
         "--base-uri", "https://example.org/isic/", "-o", str(out)],
    )
    assert res.exit_code == 0, res.output
    assert "<https://example.org/isic/HT1>" in out.read_text(encoding="utf-8")


# ── external validation with rdflib (skipped where the optional dep is absent) ──
def test_rdflib_parses_the_output(tmp_path: Path) -> None:
    """When rdflib is installed, both serializations parse and yield the expected core triples.

    Skipped in the zero-dep environment (and bare CI); asserts real syntax validity where present.
    Elsewhere, syntax validity is asserted structurally by the checks above."""
    rdflib = pytest.importorskip("rdflib")

    corpus = _greek_corpus_with_tm("12345")
    ttl = tmp_path / "v.ttl"
    jl = tmp_path / "v.jsonld"
    to_rdf(corpus, ttl, fmt="turtle")
    to_rdf(corpus, jl, fmt="jsonld")

    subj = rdflib.URIRef("https://www.trismegistos.org/text/12345")
    rdf_value = rdflib.URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#value")
    for path, fmt in ((ttl, "turtle"), (jl, "json-ld")):
        g = rdflib.Graph().parse(str(path), format=fmt)
        assert len(g) > 0
        vals = list(g.objects(subj, rdf_value))
        assert vals and str(vals[0]) == "ὁ λόγος"
        assert vals[0].language == "grc"
