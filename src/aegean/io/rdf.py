"""Export a corpus as Linked Open Data: RDF Turtle (``.ttl``) and JSON-LD (``.jsonld``).

Both writers are **stdlib only** — Turtle and JSON-LD are text formats, and the zero-dependency
core rule is absolute, so neither writer pulls in ``rdflib`` or any RDF toolkit. JSON-LD is
serialized with ``json``; Turtle is written directly with correct literal and IRI escaping.

Stable per-document URIs
------------------------
The point of an RDF export is a stable, dereferenceable name for each document, so a subject URI
is minted from the authoritative identifiers **already present in the corpus data** (or, for a
DDbDP document, from a verified stem-to-hybrid map fetched on demand), in priority order (see
`_document_uri` / `_ddbdp_hybrid`):

1. a **papyri.info DDbDP document URI**, ``http://papyri.info/ddbdp/<hybrid>``, where ``<hybrid>``
   is the ``ddb-hybrid`` key (``bgu;1;100``, semicolons literal). The corpus stores the file-stem
   id (``bgu.1.100``) and a ``TM`` note but not the hybrid, and reversing a stem is ambiguous
   (dotted series names, empty volume components), so the hybrid is taken from a ``DDb <hybrid>``
   note on the document when present, else from the ``ddbdp-uris`` map asset fetched lazily. When
   papyri.info is the subject the Trismegistos URI moves to ``rdfs:seeAlso``. Offline (the map
   asset is unavailable), the export falls back to branch 2 with a single warning;
2. a Trismegistos text id: the ``TM <number>`` note the EDH and DDbDP corpora carry in
   `aegean.core.model.DocumentMeta.notes`, ``https://www.trismegistos.org/text/<id>``;
3. an I.Sicily identifier: a document id of the form ``ISic000046``,
   ``http://sicily.classics.ox.ac.uk/inscription/ISic000046`` (the canonical URI I.Sicily's own
   EpiDoc header declares as ``<idno type="URI">``);
4. otherwise a fragment URI under ``base_uri`` (default ``urn:aegean:``, a **non-resolvable**
   identifier namespace that names the document without asserting a network location).

No URI scheme is invented that is not observed in the data. Both the ``ddb-hybrid`` key and the
``papyri.info/ddbdp/<hybrid>`` namespace come from papyri.info's own idp.data (the ``<idno
type="ddb-hybrid">`` in each DDB file, and the ``http://papyri.info/ddbdp/<series>`` collection
URIs in ``RDF/collection.rdf``); the minted document URIs use that same ``http`` scheme, the one
papyri.info's own RDF uses to identify DDbDP resources, so a subject is character-identical to the
node papyri.info publishes (RDF IRIs compare byte-exact, so ``https`` would be a disjoint node).
The ``ddbdp-uris`` map is harvested from that source by ``scripts/build_ddbdp_uri_map.py``.

Vocabularies
------------
A small, standard, individually-verifiable set:

* ``dcterms`` (``http://purl.org/dc/terms/``) — ``identifier``, ``title``, ``license``, ``source``,
  ``spatial``, ``temporal``, ``language``;
* DCMI Type (``dctype``, ``http://purl.org/dc/dcmitype/``) — every document is a ``dctype:Text``;
* ``rdf`` / ``rdfs`` — ``rdf:type``, ``rdf:value`` (the reading text), ``rdfs`` reserved for labels;
* WGS84 Geo (``geo``, ``http://www.w3.org/2003/01/geo/wgs84_pos#``) — ``geo:lat`` / ``geo:long`` on a
  ``geo:SpatialThing`` blank node when a document records find-spot coordinates.

The ``lawd`` ontology (``lawd:Inscription`` and friends) is intentionally **not** used: its terms
could not be verified against ``lawd.info`` at build time, and the project rule forbids emitting an
ontology term that has not been confirmed, so the export stays within dcterms/rdf(s)/geo. Coordinates
use plain ``geo:`` properties rather than a Linked-Places GeoJSON-LD ``Feature`` (kept simple for v1).

The reading text is emitted as a single ``rdf:value`` literal (lines joined by newlines), language-
tagged ``grc`` for the alphabetic-Greek corpora and left untagged for the syllabic scripts (whose
token text is a transliteration, not a natural language).

License pass-through
--------------------
Each document node carries the corpus license as ``dcterms:license`` (a Creative-Commons deed or
SPDX URI when the license string maps to one, else the license text verbatim). A NonCommercial
corpus therefore exports with its NC license attached; the writer never drops or softens it.

Scope for v1
------------
* The editorial apparatus (per-token `aegean.core.model.ReadingStatus`: certain / unclear /
  restored / lost) is **not** forced into RDF here — a faithful apparatus ontology is a project of
  its own, and a lossy encoding would misrepresent the edition. The reading text is exported as the
  edition presents it; the apparatus stays available through the JSON / SQLite round trip.
* **RDF is an export, not a persistence format**: ``to_rdf`` has no inverse and round-tripping is
  not claimed. `aegean.core.corpus.Corpus.to_json` / `aegean.db.to_sqlite` remain the lossless
  round-trip story.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from .._atomic import atomic_path
from .._log import get_logger

if TYPE_CHECKING:
    from ..core.corpus import Corpus
    from ..core.model import Document

_LOG = get_logger("io.rdf")

# ── namespaces ─────────────────────────────────────────────────────────────────
_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "dcterms": "http://purl.org/dc/terms/",
    "dctype": "http://purl.org/dc/dcmitype/",
    "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
}

_DEFAULT_BASE = "urn:aegean:"  # non-resolvable identifier namespace (documented)

_ISIC_RE = re.compile(r"^ISic\d+$")
_TM_RE = re.compile(r"TM\s+(\d+)")
_PLEIADES_RE = re.compile(r"https?://[^\s]*pleiades[^\s]*")
_COORD_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")

# DDbDP papyri.info document URIs. The base namespace is papyri.info's own:
# RDF/collection.rdf in github.com/papyri/idp.data declares
# ``http://papyri.info/ddbdp/<series>``; a document extends it with its
# ``ddb-hybrid`` key (``bgu;1;100``, semicolons literal). papyri.info identifies
# these resources over http (not https) in its own RDF, and RDF IRIs compare
# character-exact, so the minted subject uses http to match that node.
_DDBDP_BASE = "http://papyri.info/ddbdp/"
_DDB_NOTE_RE = re.compile(r"^DDb\s+(\S+)$")  # an explicit "DDb <hybrid>" note on a document
_N_SUFFIX_RE = re.compile(r"_\d+$")          # forward-compat division-suffix strip (fallback only)


# ── identifier / metadata extraction (from the real corpus fields) ─────────────
def _tm_id(notes: tuple[str, ...]) -> str | None:
    """The Trismegistos number from a standalone ``TM <number>`` note (EDH / DDbDP), if present.

    The whole note must be the id (``fullmatch``): the shipped EDH and DDbDP corpora carry the
    Trismegistos id as its own note, so a note that merely mentions ``TM`` in prose (``cf. TM
    12345 for a parallel``) or ends in those letters (``ATM 500``) must not be misread as an
    authoritative Trismegistos id and mint a bogus subject URI from a stray substring."""
    for note in notes:
        m = _TM_RE.fullmatch(note.strip())
        if m:
            return m.group(1)
    return None


def _pleiades_uri(notes: tuple[str, ...]) -> str | None:
    """A Pleiades place URI recorded in the notes (I.Sicily), if present."""
    for note in notes:
        m = _PLEIADES_RE.search(note)
        if m:
            return m.group(0)
    return None


def _coords(findspot: str) -> tuple[str, str] | None:
    """``(lat, long)`` decimal strings when ``findspot`` is a ``"lat, long"`` pair, else None.

    Returns the original tokens (not floats) so the exact source precision is preserved and the
    value is a syntactically valid Turtle/JSON decimal. Place-name find-spots (EDH's modern place)
    return None and are not turned into coordinates."""
    parts = [p.strip() for p in findspot.split(",")]
    if len(parts) == 2 and _COORD_RE.match(parts[0]) and _COORD_RE.match(parts[1]):
        return parts[0], parts[1]
    return None


def _tm_uri(tm: str) -> str:
    """The Trismegistos text URI for a numeric TM id."""
    return f"https://www.trismegistos.org/text/{tm}"


def _is_ddbdp(corpus: Corpus) -> bool:
    """Whether ``corpus`` is the DDbDP (papyri.info) corpus, by its provenance.

    Keyed on the provenance the DDbDP corpus (and any subset of it) carries: the
    idp.data source URL, or a ``DDbDP`` source string. A non-DDbDP corpus never
    triggers the papyri.info map fetch, so the export of any other corpus is
    unchanged and never touches the network."""
    prov = corpus.provenance
    if prov is None:
        return False
    url = prov.url or ""
    source = prov.source or ""
    return "papyri/idp.data" in url or source.strip().startswith("DDbDP")


def _load_ddbdp_map(corpus: Corpus) -> dict[str, str] | None:
    """The DDbDP stem-to-hybrid map for a DDbDP corpus, fetched lazily; else None.

    Returns None when ``corpus`` is not DDbDP (no fetch attempted), or when the
    ``ddbdp-uris`` map asset is unavailable (offline, or not hosted yet): in that
    case one warning names the fallback and the export mints Trismegistos subject
    URIs instead of papyri.info document URIs. The export therefore stays fully
    offline-capable and never raises over a missing map."""
    if not _is_ddbdp(corpus):
        return None
    from ..data import DataNotAvailableError, fetch, load_gzip_json

    try:
        path = fetch("ddbdp-uris")
        data = load_gzip_json(path)
    except (DataNotAvailableError, OSError, ValueError) as exc:
        # DataNotAvailableError: the map is not hosted / offline. OSError (which covers
        # gzip.BadGzipFile) and ValueError (which covers json.JSONDecodeError): a corrupt or
        # truncated cached/mirrored map. Either way the contract holds: one warning, fall back to
        # Trismegistos subjects, never raise over a missing or unreadable map.
        _LOG.warning(
            "DDbDP URI map ('ddbdp-uris') unavailable or unreadable (%s); falling back to "
            "Trismegistos subject URIs (no papyri.info document URIs minted)",
            exc,
        )
        return None
    return data if isinstance(data, dict) else None


def _ddbdp_hybrid(doc: Document, hybrid_map: dict[str, str] | None) -> str | None:
    """The ``ddb-hybrid`` for ``doc``: an explicit ``DDb <hybrid>`` note wins (future
    corpora carry it natively), else the ``hybrid_map`` keyed by the document id.

    The corpus id is the idp.data file stem, so the map lookup is DIRECT; a trailing
    ``_<digits>`` base-strip is a forward-compatible fallback only (every shipped
    DDbDP id resolves directly). Returns None when no hybrid is known, so the caller
    falls through to the Trismegistos / fragment branches."""
    for note in doc.meta.notes:
        m = _DDB_NOTE_RE.match(note)
        if m:
            return m.group(1)
    if hybrid_map is not None:
        hit = hybrid_map.get(doc.id)
        if hit is not None:
            return hit
        base = _N_SUFFIX_RE.sub("", doc.id)
        if base != doc.id:
            return hybrid_map.get(base)
    return None


def _document_uri(doc: Document, base: str, hybrid: str | None = None) -> str:
    """Mint the stable subject URI for ``doc`` (see the module docstring for the priority order)."""
    if hybrid:
        return _DDBDP_BASE + hybrid
    tm = _tm_id(doc.meta.notes)
    if tm:
        return _tm_uri(tm)
    if _ISIC_RE.match(doc.id):
        return f"http://sicily.classics.ox.ac.uk/inscription/{doc.id}"
    return base + quote(doc.id, safe="._-~")


def _reading_text(doc: Document) -> str:
    """The document's reading text as one string: tokens space-joined per line, lines newline-joined."""
    if doc.lines:
        lines = doc.line_tokens
    elif doc.tokens:
        lines = [doc.tokens]
    else:
        return ""
    return "\n".join(" ".join(t.text for t in line) for line in lines).strip()


# ── license string → URI (or verbatim literal) ─────────────────────────────────
_CC_RE = re.compile(r"^CC-BY(-NC)?(-SA)?(-ND)?-(\d\.\d)$")
# SPDX ids we recognise, normalized-token → canonical SPDX id (for the spdx.org URI).
_SPDX = {
    "MIT": "MIT", "APACHE-2.0": "Apache-2.0",
    "BSD-2-CLAUSE": "BSD-2-Clause", "BSD-3-CLAUSE": "BSD-3-Clause",
    "GPL-3.0": "GPL-3.0", "LGPL-3.0": "LGPL-3.0",
}


def _license_object(license_str: str) -> tuple[str, bool]:
    """Map a provenance license string to ``(value, is_iri)``.

    A recognised Creative-Commons id (``CC-BY-SA-4.0``, ``CC BY-NC-SA 4.0``, ...) becomes the
    canonical CC deed URI; ``CC0`` the public-domain-dedication URI; a known SPDX id (``MIT``,
    ``Apache-2.0``) an ``spdx.org/licenses`` URI. Anything else (free-text license notes) is
    returned verbatim as a literal, so the license text is never lost. Only the leading token
    before any ``(...)`` qualifier is inspected; NC / ND terms are preserved in the mapped URI,
    never stripped."""
    head = license_str.split("(", 1)[0].strip()
    token = re.sub(r"\s+", "-", head).upper()  # "CC BY-NC-SA 4.0" -> "CC-BY-NC-SA-4.0"
    m = _CC_RE.match(token)
    if m:
        parts = ["by"]
        if m.group(1):
            parts.append("nc")
        if m.group(2):
            parts.append("sa")
        if m.group(3):
            parts.append("nd")
        return f"https://creativecommons.org/licenses/{'-'.join(parts)}/{m.group(4)}/", True
    if token in ("CC0-1.0", "CC0"):
        return "https://creativecommons.org/publicdomain/zero/1.0/", True
    if token in _SPDX:
        return f"https://spdx.org/licenses/{_SPDX[token]}", True
    return license_str, False  # unrecognised: keep the full text as a literal


# ── Turtle escaping ────────────────────────────────────────────────────────────
def _ttl_literal(text: str) -> str:
    """Escape a string for a Turtle ``"..."`` literal, leaving no raw control byte in the output.

    ``\\`` and ``"`` are escaped; the named whitespace/control chars use ECHAR (``\\t \\b \\n
    \\r \\f``); every other C0 control char and DEL uses a ``\\uXXXX`` UCHAR escape. The result is
    a valid ``STRING_LITERAL_QUOTE`` containing only printable characters plus the escapes."""
    out: list[str] = []
    for ch in text:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o == 0x08:
            out.append("\\b")
        elif o == 0x0C:
            out.append("\\f")
        elif o < 0x20 or o == 0x7F:
            out.append(f"\\u{o:04X}")
        else:
            out.append(ch)
    return "".join(out)


# Characters an IRIREF cannot contain literally (must be UCHAR-escaped) plus anything <= 0x20.
_IRI_BAD = set('<>"{}|^`\\')


def _ttl_iri(iri: str) -> str:
    """Wrap ``iri`` as a Turtle ``<...>`` IRIREF, UCHAR-escaping any character the grammar forbids.

    Well-formed http/urn subjects pass through unchanged; a hostile ``base_uri`` (a space, a quote,
    a control char) is escaped rather than emitted raw, so the output stays parseable."""
    out: list[str] = []
    for ch in iri:
        o = ord(ch)
        if o <= 0x20 or ch in _IRI_BAD:
            out.append(f"\\u{o:04X}")
        else:
            out.append(ch)
    return "<" + "".join(out) + ">"


def _validate_base_uri(base: str) -> None:
    """Reject a ``base_uri`` that cannot appear literally in an IRI, naming the offending character.

    A subject IRI is emitted verbatim by both serializers: Turtle wraps it in ``<...>`` (and would
    UCHAR-escape an illegal character), while JSON-LD uses it as an ``@id`` string (where the same
    character makes the IRI invalid and a conforming reader silently drops the whole node). So a
    space or control character in ``base_uri`` yields a Turtle graph and a JSON-LD graph that
    disagree. Fail fast here rather than emit a subject that means different things to the two
    formats. Document ids appended under ``base_uri`` are percent-escaped when they are minted, so
    only the caller-supplied base is checked."""
    for ch in base:
        o = ord(ch)
        if o <= 0x20 or o == 0x7F or ch in _IRI_BAD:
            raise ValueError(
                f"base_uri {base!r} contains {ch!r} (U+{o:04X}), which cannot appear literally in "
                "an IRI; use only IRI-legal characters (no spaces, control characters, or any of "
                '<>"{}|^`\\)'
            )


def _lit(text: str, lang: str | None = None) -> str:
    """A Turtle literal object term: ``"escaped"`` or ``"escaped"@lang``."""
    base = f'"{_ttl_literal(text)}"'
    return f"{base}@{lang}" if lang else base


# ── per-document RDF assembly (shared shape, two serializations) ───────────────
def _document_terms(
    doc: Document,
    base: str,
    license_obj: tuple[str, bool] | None,
    source: tuple[str, bool] | None,
    hybrid: str | None = None,
) -> "list[tuple[str, str, dict[str, Any]]]":
    """Predicate/object descriptors for one document, as ``(predicate_curie, kind, payload)``.

    ``kind`` is one of ``"iri"`` (payload ``{"iri": ...}``), ``"literal"`` (``{"text":...,
    "lang":...}``), ``"decimal"`` (``{"value": ...}``), or ``"geo"`` (``{"lat":..., "long":...}``).
    Both serializers walk this one list, so the Turtle and JSON-LD outputs describe the same graph.

    ``hybrid`` (a DDbDP ``ddb-hybrid`` when the subject is a papyri.info document URI) is recorded
    as an extra ``dcterms:identifier`` and, when a Trismegistos id is also present, links the TM
    record as ``rdfs:seeAlso`` (papyri.info is the subject, so the TM URI is a see-also)."""
    lang = "grc" if doc.script_id == "greek" else None
    terms: list[tuple[str, str, dict[str, Any]]] = [
        ("rdf:type", "iri", {"iri": "dctype:Text", "curie": True}),
        ("dcterms:identifier", "literal", {"text": doc.id, "lang": None}),
    ]
    tm = _tm_id(doc.meta.notes)
    if hybrid:
        terms.append(("dcterms:identifier", "literal", {"text": hybrid, "lang": None}))
    if tm:
        terms.append(("dcterms:identifier", "literal", {"text": f"TM {tm}", "lang": None}))
        if hybrid:
            terms.append(("rdfs:seeAlso", "iri", {"iri": _tm_uri(tm)}))
    if doc.meta.name:
        terms.append(("dcterms:title", "literal", {"text": doc.meta.name, "lang": None}))
    if license_obj is not None:
        value, is_iri = license_obj
        terms.append(
            ("dcterms:license", "iri" if is_iri else "literal",
             {"iri": value} if is_iri else {"text": value, "lang": None})
        )
    if source is not None:
        value, is_iri = source
        terms.append(
            ("dcterms:source", "iri" if is_iri else "literal",
             {"iri": value} if is_iri else {"text": value, "lang": None})
        )
    if lang:
        terms.append(("dcterms:language", "literal", {"text": "grc", "lang": None}))
    if doc.meta.site:
        terms.append(("dcterms:spatial", "literal", {"text": doc.meta.site, "lang": None}))
    pleiades = _pleiades_uri(doc.meta.notes)
    if pleiades:
        terms.append(("dcterms:spatial", "iri", {"iri": pleiades}))
    coords = _coords(doc.meta.findspot)
    if coords:
        terms.append(("dcterms:spatial", "geo", {"lat": coords[0], "long": coords[1]}))
    if doc.meta.period:
        terms.append(("dcterms:temporal", "literal", {"text": doc.meta.period, "lang": None}))
    text = _reading_text(doc)
    if text:
        terms.append(("rdf:value", "literal", {"text": text, "lang": lang}))
    return terms


def _term_to_turtle(kind: str, payload: dict[str, Any]) -> str:
    if kind == "iri":
        return str(payload["iri"]) if payload.get("curie") else _ttl_iri(str(payload["iri"]))
    if kind == "literal":
        return _lit(str(payload["text"]), payload.get("lang"))
    if kind == "decimal":
        return str(payload["value"])
    if kind == "geo":
        return f"[ a geo:SpatialThing ; geo:lat {payload['lat']} ; geo:long {payload['long']} ]"
    raise ValueError(f"unknown term kind {kind!r}")  # pragma: no cover - internal guard


def _serialize_turtle(corpus: Corpus, base: str) -> str:
    license_obj = _corpus_license(corpus)
    source = _corpus_source(corpus)
    hybrid_map = _load_ddbdp_map(corpus)
    lines: list[str] = [f"@prefix {p}: <{u}> ." for p, u in _NS.items()]
    if base == _DEFAULT_BASE:
        lines.append(
            "# Subjects under urn:aegean: are identifiers, not resolvable locations."
        )
    lines.append("")
    for doc in corpus:
        hybrid = _ddbdp_hybrid(doc, hybrid_map)
        subject = _ttl_iri(_document_uri(doc, base, hybrid))
        terms = _document_terms(doc, base, license_obj, source, hybrid)
        objs = [f"{pred} {_term_to_turtle(kind, payload)}" for pred, kind, payload in terms]
        block = f"{subject} " + " ;\n    ".join(objs) + " ."
        lines.append(block)
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def _term_to_jsonld(kind: str, payload: dict[str, Any]) -> Any:
    if kind == "iri":
        return payload["iri"] if payload.get("curie") else {"@id": payload["iri"]}
    if kind == "literal":
        lang = payload.get("lang")
        return {"@value": payload["text"], "@language": lang} if lang else payload["text"]
    if kind == "decimal":
        return float(payload["value"])
    if kind == "geo":
        return {
            "@type": "geo:SpatialThing",
            "geo:lat": float(payload["lat"]),
            "geo:long": float(payload["long"]),
        }
    raise ValueError(f"unknown term kind {kind!r}")  # pragma: no cover - internal guard


def _serialize_jsonld(corpus: Corpus, base: str) -> str:
    license_obj = _corpus_license(corpus)
    source = _corpus_source(corpus)
    hybrid_map = _load_ddbdp_map(corpus)
    graph: list[dict[str, Any]] = []
    for doc in corpus:
        hybrid = _ddbdp_hybrid(doc, hybrid_map)
        node: dict[str, Any] = {"@id": _document_uri(doc, base, hybrid)}
        for pred, kind, payload in _document_terms(doc, base, license_obj, source, hybrid):
            obj = _term_to_jsonld(kind, payload)
            if pred == "rdf:type":
                node["@type"] = obj  # a CURIE string; the context expands it
                continue
            if pred in node:
                existing = node[pred]
                if isinstance(existing, list):
                    existing.append(obj)
                else:
                    node[pred] = [existing, obj]
            else:
                node[pred] = obj
        graph.append(node)
    doc_out = {"@context": dict(_NS), "@graph": graph}
    return json.dumps(doc_out, ensure_ascii=False, indent=2) + "\n"


def _corpus_license(corpus: Corpus) -> tuple[str, bool] | None:
    prov = corpus.provenance
    if prov is None or not prov.license:
        return None
    return _license_object(prov.license)


def _corpus_source(corpus: Corpus) -> tuple[str, bool] | None:
    prov = corpus.provenance
    if prov is None:
        return None
    if prov.url:
        return prov.url, True
    if prov.source:
        return prov.source, False
    return None


# ── public API ─────────────────────────────────────────────────────────────────
def to_rdf(
    corpus: Corpus,
    path: str | Path,
    *,
    fmt: str = "turtle",
    base_uri: str | None = None,
) -> None:
    """Write ``corpus`` to disk as Linked Open Data.

    ``fmt`` is ``"turtle"`` (aliases ``"ttl"``) or ``"jsonld"`` (alias ``"json-ld"``). Each
    document becomes a subject with a stable URI minted from its authoritative identifiers
    (a papyri.info DDbDP document URI, else Trismegistos / I.Sicily / a ``base_uri`` fragment;
    see the module docstring for the priority order and the DDbDP map), typed
    ``dctype:Text``, carrying its title, identifiers, the corpus license (``dcterms:license``,
    NonCommercial included), source, place / date, and its reading text as an ``rdf:value``
    literal (language-tagged ``grc`` for the Greek corpora). ``base_uri`` defaults to the
    non-resolvable ``urn:aegean:`` namespace.

    The write is atomic (temp file + ``os.replace``), so a failed or interrupted write never
    truncates a prior export. Raises ``ValueError`` for an unknown ``fmt``, or for a ``base_uri``
    that cannot appear literally in an IRI (a space, a control character, or an IRIREF-forbidden
    character) since that would make the Turtle and JSON-LD subjects disagree.

    RDF is an export only: there is no reader and no round-trip guarantee (use
    `aegean.core.corpus.Corpus.to_json` / `aegean.db.to_sqlite` for lossless persistence)."""
    fmt_norm = fmt.strip().lower()
    base = base_uri if base_uri is not None else _DEFAULT_BASE
    _validate_base_uri(base)
    if fmt_norm in ("turtle", "ttl"):
        text = _serialize_turtle(corpus, base)
    elif fmt_norm in ("jsonld", "json-ld"):
        text = _serialize_jsonld(corpus, base)
    else:
        raise ValueError(f"unknown RDF format {fmt!r}; use 'turtle' (ttl) or 'jsonld'")
    with atomic_path(path) as tmp:
        # newline="\n": deterministic LF line endings on every platform, so the file's only
        # control byte is the structural newline (all data control chars are escaped) and the
        # output is byte-identical cross-platform.
        tmp.write_text(text, encoding="utf-8", newline="\n")
