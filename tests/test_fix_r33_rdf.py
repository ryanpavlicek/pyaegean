"""Regression tests for four RDF-export (`aegean.io.to_rdf`) correctness fixes.

Each test verifies the actual OUTPUT (a minted subject IRI, a returned id, an escaped string,
a graph parsed by rdflib, or a raised error), not merely that a call runs.

* **base_uri IRI validation** — a ``base_uri`` with a character illegal in an IRI (a space, a
  control byte) is rejected up front with a ``ValueError`` naming the character, instead of
  silently producing a Turtle graph that escapes it and a JSON-LD graph that drops the node; a
  document id containing a space is percent-escaped to the identical subject in both formats.
* **standalone Trismegistos note** — ``_tm_id`` only accepts a note that is exactly ``TM <n>``
  (``fullmatch``), so a prose mention (``cf. TM 12345 for a parallel``) or a look-alike tail
  (``ATM 500``) never mints an authoritative Trismegistos subject from a stray substring.
* **corrupt map degrades, never raises** — a corrupt or truncated ``ddbdp-uris`` map (bad gzip,
  invalid JSON) falls back to Trismegistos subjects with one warning, honouring the
  never-raises-over-a-missing-map contract.
* **papyri.info http scheme** — DDbDP document subjects use ``http://papyri.info/ddbdp/`` (the
  scheme papyri.info's own RDF uses; RDF IRIs compare byte-exact), while the Trismegistos
  (https, www) and I.Sicily (http) subject families are unchanged, verified against each
  authority.

Stdlib-only writers, so nothing here needs an optional dep except the one rdflib cross-check
(``pytest.importorskip``). No network: the map fetch is monkeypatched to a local file.
"""

from __future__ import annotations

import gzip
import json
import logging
from pathlib import Path

import pytest

import aegean.data as data
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.io import to_rdf
from aegean.io.rdf import (
    _DDBDP_BASE,
    _ddbdp_hybrid,
    _document_uri,
    _tm_id,
    _tm_uri,
    _validate_base_uri,
)


# ── fixtures ────────────────────────────────────────────────────────────────────
def _greek_doc(doc_id: str, notes: tuple[str, ...] = ()) -> Document:
    return Document(
        id=doc_id, script_id="greek",
        tokens=[Token("λόγος", TokenKind.WORD, line_no=0, position=0)],
        lines=[[0]],
        meta=DocumentMeta(name=doc_id, notes=notes),
    )


def _greek_corpus(docs: list[Document], prov: Provenance | None = None) -> Corpus:
    prov = prov or Provenance(source="synthetic", license="CC-BY-4.0", url="https://ex.org")
    return Corpus(docs, provenance=prov, script_id="greek")


def _ddbdp_corpus(docs: list[Document]) -> Corpus:
    prov = Provenance(
        source="DDbDP — Duke Databank of Documentary Papyri (papyri.info)",
        license="CC-BY-3.0 (DDbDP / papyri.info)",
        url="https://github.com/papyri/idp.data",
    )
    return Corpus(docs, provenance=prov, script_id="greek")


def _write_gzip_json(path: Path, obj: object) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


# ── finding 1: base_uri IRI validation + identical percent-escaped subjects ──────
@pytest.mark.parametrize(
    "bad_base, needle",
    [
        ("http://ex ample.org/", "U+0020"),   # a space
        ("http://x.org/\t", "U+0009"),        # a tab (control byte)
        ("http://x.org/\x00", "U+0000"),      # NUL
        ('http://x.org/"q', "U+0022"),        # an IRIREF-forbidden character
    ],
)
def test_illegal_base_uri_raises_naming_the_char(tmp_path: Path, bad_base: str, needle: str) -> None:
    corpus = _greek_corpus([_greek_doc("D1")])
    with pytest.raises(ValueError, match="base_uri") as exc:
        to_rdf(corpus, tmp_path / "x.ttl", fmt="turtle", base_uri=bad_base)
    assert needle in str(exc.value)
    # the JSON-LD path is guarded by the same up-front check
    with pytest.raises(ValueError, match="base_uri"):
        to_rdf(corpus, tmp_path / "x.jsonld", fmt="jsonld", base_uri=bad_base)


def test_validate_base_uri_accepts_clean_bases() -> None:
    # the default and ordinary http/urn bases must pass unchanged (no false positive)
    for good in ("urn:aegean:", "http://example.org/x/", "https://sicily.classics.ox.ac.uk/i/"):
        _validate_base_uri(good)  # must not raise


def test_doc_id_with_space_escapes_identically_in_both_serializations(tmp_path: Path) -> None:
    """A space inside a document id is percent-escaped to the SAME subject IRI in Turtle and
    JSON-LD, so neither reader drops the node (the divergence the validation prevents at the base
    level is already impossible for the id itself, which is escaped when minted)."""
    corpus = _greek_corpus([_greek_doc("doc 1")])
    ttl = tmp_path / "s.ttl"
    jl = tmp_path / "s.jsonld"
    to_rdf(corpus, ttl, fmt="turtle")
    to_rdf(corpus, jl, fmt="jsonld")

    escaped = "urn:aegean:doc%201"
    ttl_text = ttl.read_text(encoding="utf-8")
    jl_obj = json.loads(jl.read_text(encoding="utf-8"))
    assert f"<{escaped}>" in ttl_text                       # Turtle subject
    assert jl_obj["@graph"][0]["@id"] == escaped            # JSON-LD @id (identical)
    # a raw space never reaches either subject IRI
    assert "urn:aegean:doc 1" not in ttl_text


def test_doc_id_with_space_both_parse_with_rdflib(tmp_path: Path) -> None:
    rdflib = pytest.importorskip("rdflib")
    corpus = _greek_corpus([_greek_doc("doc 1")])
    subj = rdflib.URIRef("urn:aegean:doc%201")
    for fmt, name, parse_fmt in (("turtle", "p.ttl", "turtle"), ("jsonld", "p.jsonld", "json-ld")):
        out = tmp_path / name
        to_rdf(corpus, out, fmt=fmt)
        g = rdflib.Graph().parse(str(out), format=parse_fmt)
        # the escaped subject is a real node carrying triples in BOTH serializations
        assert list(g.predicate_objects(subj)), f"{parse_fmt} dropped the subject"


# ── finding 2: Trismegistos id only from a standalone TM note ────────────────────
@pytest.mark.parametrize(
    "note, expected",
    [
        ("TM 8875", "8875"),        # the canonical standalone form
        ("TM  8875", "8875"),       # tolerant of internal whitespace run
        ("TM 8875 ", "8875"),       # trailing whitespace stripped
        (" TM 8875", "8875"),       # leading whitespace stripped
        ("cf. TM 12345 for a parallel", None),  # prose mention: NOT an id
        ("ATM 500", None),          # look-alike tail: NOT an id
        ("TM number unknown", None),
        ("STM 7", None),
    ],
)
def test_tm_id_requires_standalone_note(note: str, expected: str | None) -> None:
    assert _tm_id((note,)) == expected


def test_prose_tm_note_does_not_mint_trismegistos_subject(tmp_path: Path) -> None:
    corpus = _greek_corpus([_greek_doc("P1", notes=("cf. TM 999 for a close parallel",))])
    out = tmp_path / "p.ttl"
    to_rdf(corpus, out, fmt="turtle")
    text = out.read_text(encoding="utf-8")
    assert "trismegistos.org/text/999" not in text  # no bogus authoritative subject
    assert 'dcterms:identifier "TM 999"' not in text
    assert "<urn:aegean:P1> rdf:type dctype:Text ;" in text  # falls through to the fragment URI


def test_standalone_tm_note_still_mints_trismegistos_subject(tmp_path: Path) -> None:
    corpus = _greek_corpus([_greek_doc("P2", notes=("TM 999",))])
    out = tmp_path / "q.ttl"
    to_rdf(corpus, out, fmt="turtle")
    assert "<https://www.trismegistos.org/text/999> rdf:type dctype:Text ;" in out.read_text(
        encoding="utf-8"
    )


# ── finding 3: a corrupt map degrades to Trismegistos, never raises ──────────────
def _corrupt_gzip(tmp_path: Path) -> Path:
    p = tmp_path / "bad.json.gz"
    p.write_bytes(b"this is not a gzip stream at all")  # gzip.open(...).read() -> BadGzipFile
    return p


def _valid_gzip_bad_json(tmp_path: Path) -> Path:
    p = tmp_path / "badjson.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write("{ not valid json ]")  # json.loads -> JSONDecodeError (ValueError)
    return p


@pytest.mark.parametrize("maker", [_corrupt_gzip, _valid_gzip_bad_json])
def test_corrupt_ddbdp_map_falls_back_with_one_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, maker
) -> None:  # type: ignore[no-untyped-def]
    bad = maker(tmp_path)

    def fake_fetch(name: str, **kw: object) -> Path:
        assert name == "ddbdp-uris"
        return bad

    monkeypatch.setattr(data, "fetch", fake_fetch)
    corpus = _ddbdp_corpus([_greek_doc("bgu.1.100", notes=("TM 8875",))])
    out = tmp_path / "off.ttl"
    with caplog.at_level(logging.WARNING, logger="aegean.io.rdf"):
        to_rdf(corpus, out, fmt="turtle")  # must NOT raise over the corrupt map
    text = out.read_text(encoding="utf-8")
    # documented fallback: Trismegistos is the subject, no papyri.info document URI is minted
    assert "<https://www.trismegistos.org/text/8875> rdf:type dctype:Text ;" in text
    assert "papyri.info/ddbdp/" not in text
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    msg = warnings[0].getMessage()
    assert "ddbdp-uris" in msg and "Trismegistos" in msg


# ── finding 4: papyri.info http scheme; TM (https/www) and I.Sicily (http) unchanged ──
def test_ddbdp_base_is_http() -> None:
    assert _DDBDP_BASE == "http://papyri.info/ddbdp/"


def test_ddbdp_subject_uses_http_scheme_via_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_gzip_json(tmp_path / "map.json.gz", {"bgu.1.100": "bgu;1;100"})

    def fake_fetch(name: str, **kw: object) -> Path:
        return tmp_path / "map.json.gz"

    monkeypatch.setattr(data, "fetch", fake_fetch)
    corpus = _ddbdp_corpus([_greek_doc("bgu.1.100", notes=("TM 8875",))])
    out = tmp_path / "d.ttl"
    to_rdf(corpus, out, fmt="turtle")
    text = out.read_text(encoding="utf-8")
    # the document subject is the http papyri.info node papyri.info's own RDF uses
    assert "<http://papyri.info/ddbdp/bgu;1;100> rdf:type dctype:Text ;" in text
    assert "https://papyri.info/ddbdp/" not in text
    # the Trismegistos cross-link stays https + www, moved to rdfs:seeAlso
    assert "rdfs:seeAlso <https://www.trismegistos.org/text/8875>" in text


def test_ddbdp_note_path_mints_http_subject() -> None:
    doc = _greek_doc("whatever", notes=("DDb p.oxy;1;1",))
    uri = _document_uri(doc, "urn:aegean:", _ddbdp_hybrid(doc, None))
    assert uri == "http://papyri.info/ddbdp/p.oxy;1;1"


def test_isicily_subject_stays_http() -> None:
    # authority: the I.Sicily EpiDoc <idno type="URI"> is http://sicily.classics.ox.ac.uk/...
    doc = _greek_doc("ISic000046")
    assert _document_uri(doc, "urn:aegean:") == (
        "http://sicily.classics.ox.ac.uk/inscription/ISic000046"
    )


def test_trismegistos_subject_stays_https_www() -> None:
    # authority: trismegistos.org serves and cites www.trismegistos.org/text/N over https
    assert _tm_uri("42") == "https://www.trismegistos.org/text/42"
