"""Read and write the corpus model as EpiDoc TEI XML, both on the stdlib XML parser.

**Writing** (`to_epidoc` / `write_epidoc`): a `Document` becomes a TEI document — the header
carries the id and find-place, the body carries the transliteration as
``<w>``/``<num>``/``<g>``/``<seg>`` tokens with ``<lb/>`` line breaks and ``<unclear>``/``<supplied>``
apparatus for non-certain readings.

**Reading** (`from_epidoc` / `read_epidoc`): the inverse, and script-agnostic — it ingests any
EpiDoc edition (a single file or a directory) into a `Corpus`, taking the id and find-place from
the header and the token/line stream + editorial certainty from the ``<div type="edition">``. Token
kinds come from the carrier element (``<w>``→word, ``<num>``→numeral, ``<g>``→logogram); a logogram
that had to be carried in ``<seg>`` to hold apparatus markup reloads as a word. Both directions use
**only the stdlib XML parser**, so neither needs an extra dependency. (The Linear B-specific
`aegean.scripts.linearb.parse_epidoc` keeps its own lxml reader for DAMOS-style files, where it
re-derives Aegean token kinds from the transliteration text.)
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from ..core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind

# Characters XML 1.0 forbids in text: control chars other than tab/newline/CR, plus the
# non-character code points. Emitting them raw yields output that cannot be re-parsed.
_XML_OK_WS = frozenset((0x09, 0x0A, 0x0D))  # tab, newline, carriage return


def _xml_clean(text: str) -> str:
    """Drop XML-1.0-invalid characters so the serialized document stays well-formed."""
    return "".join(
        c
        for c in text
        if ord(c) in _XML_OK_WS
        or 0x20 <= ord(c) <= 0xD7FF
        or 0xE000 <= ord(c) <= 0xFFFD
        or ord(c) >= 0x10000
    )

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET

    from ..core.corpus import Corpus

_TEI = "http://www.tei-c.org/ns/1.0"
_XML = "http://www.w3.org/XML/1998/namespace"  # for xml:lang on the edition div

# pyaegean token kind → EpiDoc element. The reader re-classifies by text, so this is for semantic
# fidelity and interop with other EpiDoc tools; w/num/g/seg all reload to the right kind.
_TAG = {TokenKind.WORD: "w", TokenKind.NUMERAL: "num", TokenKind.LOGOGRAM: "g"}

# script id → BCP 47 xml:lang for the edition div ("und" = undetermined, for the undeciphered scripts).
_LANG = {"lineara": "und", "linearb": "gmy", "cypriot": "grc", "cyprominoan": "und", "greek": "grc"}

# non-CERTAIN reading → the EpiDoc apparatus element that wraps the token text.
# RESTORED and LOST both use <supplied> (which, unlike the empty <gap>, can carry the token
# text so it survives the round trip) and are kept distinct by @reason: an editor-supplied
# reading is reason="lost"; a non-preserved/conjectural reading is reason="undefined". Both
# @reason values are EpiDoc-recommended, so the output stays schema-valid.
_STATUS_EL = {
    ReadingStatus.UNCLEAR: ("unclear", {}),
    ReadingStatus.RESTORED: ("supplied", {"reason": "lost"}),
    ReadingStatus.LOST: ("supplied", {"reason": "undefined"}),
}


def to_epidoc(document: Document) -> str:
    """Serialize a single `Document` to an EpiDoc TEI XML string.

    The transliteration lives in a TEI ``<div type="edition">`` (EpiDoc's required edition
    division), as ``<lb/>``-delimited lines of ``<w>``/``<num>``/``<g>`` tokens. A token whose
    `aegean.ReadingStatus` is not ``CERTAIN`` is wrapped in the matching EpiDoc apparatus
    element (``<unclear>`` or ``<supplied>``), so editorial certainty survives the round trip
    through `aegean.scripts.linearb.parse_epidoc`. The output validates against the EpiDoc
    RelaxNG schema (see ``tests/test_io.py``).

    Token *text* round-trips subject to standard XML text normalization: a carriage
    return becomes a line feed, leading/trailing whitespace on a token is trimmed, and a
    token (or alternate reading) whose text is only whitespace does not survive the parse.
    Real transliteration tokens are never whitespace-only, so this affects only synthetic
    input; the transliteration content itself is preserved."""
    import xml.etree.ElementTree as ET  # lazy: keep `import aegean` free of the XML parser

    def q(tag: str) -> str:
        return f"{{{_TEI}}}{tag}"

    def sub(parent: ET.Element, tag: str, text: str | None = None) -> ET.Element:
        el = ET.SubElement(parent, q(tag))
        if text is not None:
            el.text = _xml_clean(text)
        return el

    ET.register_namespace("", _TEI)  # emit the TEI namespace as the default (xmlns="…")
    root = ET.Element(q("TEI"))
    # fileDesc requires titleStmt, publicationStmt, sourceDesc — in that order — to be TEI-valid.
    file_desc = sub(sub(root, "teiHeader"), "fileDesc")
    sub(sub(file_desc, "titleStmt"), "title", document.meta.name or document.id)
    sub(sub(file_desc, "publicationStmt"), "p", "Exported by pyaegean; redistribute under the source's terms.")
    ms = sub(sub(file_desc, "sourceDesc"), "msDesc")
    sub(sub(ms, "msIdentifier"), "idno", document.id)
    if document.meta.site:
        sub(sub(sub(ms, "history"), "origin"), "origPlace", document.meta.site)

    body = sub(sub(root, "text"), "body")
    edition = sub(body, "div")
    edition.set("type", "edition")
    edition.set(f"{{{_XML}}}lang", _LANG.get(document.script_id, "und"))
    ab = sub(edition, "ab")
    lines = document.line_tokens if document.lines else [document.tokens]
    for i, line in enumerate(lines, start=1):
        sub(ab, "lb").set("n", str(i))
        for tok in line:
            wrap = _STATUS_EL.get(tok.status)
            carrier = _TAG.get(tok.kind, "seg")
            # TEI's <g> (glyph) has a restricted content model and can't hold <unclear>/<supplied>
            # (and an <app> can't carry it inside <lem>/<rdg> meaningfully); carry the token in
            # <seg> instead (the reader re-derives its kind by text).
            if (wrap is not None or tok.alt) and carrier == "g":
                carrier = "seg"
            if tok.alt:
                # alternate readings: <app><lem><w>text</w></lem><rdg><w>alt</w></rdg>…</app>
                app = sub(ab, "app")
                el = sub(sub(app, "lem"), carrier)
                for a in tok.alt:
                    sub(sub(app, "rdg"), carrier, a)
            else:
                el = sub(ab, carrier)
            if wrap is None:
                el.text = _xml_clean(tok.text)
            else:  # editorial markup, e.g. <w><supplied reason="lost">…</supplied></w>, <seg><unclear>…</unclear></seg>
                tag, attrs = wrap
                inner = sub(el, tag, tok.text)
                for k, v in attrs.items():
                    inner.set(k, v)

    ET.indent(root)
    return "<?xml version='1.0' encoding='UTF-8'?>\n" + ET.tostring(root, encoding="unicode") + "\n"


def _safe_name(doc_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in doc_id) or "document"


def write_epidoc(obj: Corpus | Document, path: str | Path) -> None:
    """Write EpiDoc TEI XML to disk.

    A single `Document` is written to the file ``path``; a
    `Corpus` is written as one ``{id}.xml`` file per document into the
    directory ``path`` (created if needed) — the layout
    `aegean.scripts.linearb.parse_epidoc` reads back. Ids are sanitized for
    the filesystem (anything outside ``[A-Za-z0-9-_.]`` becomes ``_``), which
    can conflate distinct ids: when two ids sanitize to the same filename, the
    later ones (in id order) get a ``-2``, ``-3``, ... suffix and a warning
    names the colliding ids, so no document silently overwrites another."""
    if isinstance(obj, Document):
        Path(path).write_text(to_epidoc(obj), encoding="utf-8")
        return
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    # Sanitizing can map distinct ids to the same filename ("KN X 1" and "KN,X;1" both become
    # "KN_X_1"); group by sanitized name and disambiguate deterministically in id order.
    by_name: dict[str, list[Document]] = {}
    for doc in obj:
        by_name.setdefault(_safe_name(doc.id), []).append(doc)
    used = set(by_name)
    for name, group in by_name.items():
        group.sort(key=lambda d: d.id)
        if len(group) > 1:
            ids = ", ".join(repr(d.id) for d in group)
            warnings.warn(
                f"write_epidoc: document ids {ids} all sanitize to the filename {name!r}.xml; "
                f"keeping the first (in id order) and suffixing the rest with -2, -3, ...",
                stacklevel=2,
            )
        for i, doc in enumerate(group):
            fname = name
            if i:
                n = i + 1
                fname = f"{name}-{n}"
                while fname in used:  # a suffixed name can itself be another document's id
                    n += 1
                    fname = f"{name}-{n}"
                used.add(fname)
            (out / f"{fname}.xml").write_text(to_epidoc(doc), encoding="utf-8")


# ── reading EpiDoc TEI back into the corpus model ────────────────────────────────

_TOKEN_TAGS = frozenset({"w", "num", "g", "seg"})
_KIND_BY_TAG = {"w": TokenKind.WORD, "num": TokenKind.NUMERAL, "g": TokenKind.LOGOGRAM}


def _local(tag: object) -> str:
    """Local name of a (possibly namespaced) ElementTree tag."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _node_text(el: ET.Element) -> str:
    return "".join(el.itertext()).strip()


def _first_text(root: ET.Element, *tags: str) -> str:
    """First non-empty text among the named TEI elements, searched anywhere."""
    for tag in tags:
        el = root.find(f".//{{{_TEI}}}{tag}")
        if el is not None and _node_text(el):
            return _node_text(el)
    return ""


def _reading_status(el: ET.Element) -> ReadingStatus:
    """Editorial certainty from any EpiDoc apparatus element the token contains.

    ``<supplied>`` carries two distinct statuses by its ``@reason`` (matching the writer):
    ``reason="undefined"`` (a non-preserved / conjectural reading) is ``LOST``; any other
    ``<supplied>`` (the editor-supplied ``reason="lost"``) is ``RESTORED``. A bare ``<gap>``
    (an external edition's empty lacuna marker) is also ``LOST``."""
    supplied = next((d for d in el.iter() if _local(d.tag) == "supplied"), None)
    if supplied is not None:
        if supplied.get("reason") == "undefined":
            return ReadingStatus.LOST
        return ReadingStatus.RESTORED
    inner = {_local(d.tag) for d in el.iter()}
    if "gap" in inner:
        return ReadingStatus.LOST
    if "unclear" in inner:
        return ReadingStatus.UNCLEAR
    return ReadingStatus.CERTAIN


def _kind_of(carrier: str, text: str) -> TokenKind:
    kind = _KIND_BY_TAG.get(carrier)
    if kind is not None:
        return kind
    # <seg> is the writer's fallback carrier (e.g. a logogram that had to hold apparatus
    # markup); re-derive the obvious numeral case, otherwise treat it as a word.
    return TokenKind.NUMERAL if text and all(c.isdigit() for c in text) else TokenKind.WORD


def _read_document(root: ET.Element, script_id: str, fallback_id: str) -> Document | None:
    edition = next(
        (d for d in root.iter(f"{{{_TEI}}}div") if d.get("type") == "edition"), None
    )
    region = edition if edition is not None else root.find(f".//{{{_TEI}}}body")
    if region is None:
        return None

    doc_id = _first_text(root, "idno", "title") or root.get(f"{{{_XML}}}id") or fallback_id
    name = _first_text(root, "title")
    site = _first_text(root, "origPlace", "settlement", "provenance")
    notes = tuple(
        _node_text(n) for n in root.iter()
        if _local(n.tag) in ("note", "bibl") and _node_text(n)
    )

    # stdlib ElementTree has no getparent(); a child→parent map lets us skip token
    # elements nested inside an <app> (they are consumed at the <app> itself). Stdlib
    # Element objects are identity-stable, so they are safe dict keys.
    parents = {child: parent for parent in region.iter() for child in parent}

    def inside_app(el: ET.Element) -> bool:
        p = parents.get(el)
        while p is not None:
            if _local(p.tag) == "app":
                return True
            p = parents.get(p)
        return False

    tokens: list[Token] = []
    lines: list[list[int]] = []
    cur: list[int] = []
    pos = 0
    for el in region.iter():
        tag = _local(el.tag)
        if tag == "lb":
            if cur:
                lines.append(cur)
                cur = []
        elif tag == "app":
            lem = el.find(f"{{{_TEI}}}lem")
            text = _node_text(lem) if lem is not None else ""
            if not text:
                continue
            carrier = (
                next((_local(c.tag) for c in lem.iter() if _local(c.tag) in _TOKEN_TAGS), "seg")
                if lem is not None else "seg"
            )
            alts = tuple(_node_text(r) for r in el.findall(f"{{{_TEI}}}rdg") if _node_text(r))
            tokens.append(Token(
                text=text, kind=_kind_of(carrier, text),
                status=ReadingStatus.CERTAIN if lem is None else _reading_status(lem),
                alt=alts, line_no=len(lines), position=pos,
            ))
            cur.append(pos)
            pos += 1
        elif tag in _TOKEN_TAGS:
            if inside_app(el):
                continue
            text = _node_text(el)
            if not text:
                continue
            tokens.append(Token(
                text=text, kind=_kind_of(tag, text), status=_reading_status(el),
                line_no=len(lines), position=pos,
            ))
            cur.append(pos)
            pos += 1
    if cur:
        lines.append(cur)

    meta = DocumentMeta(site=site, name=name or doc_id, notes=notes)
    return Document(id=doc_id, script_id=script_id, tokens=tokens, lines=lines, meta=meta)


def read_epidoc(source: str | Path, *, script_id: str = "greek") -> list[Document]:
    """Parse an EpiDoc TEI file — or a directory of ``*.xml`` files — into Documents.

    ``script_id`` labels the result: EpiDoc's ``xml:lang`` can't disambiguate (say) Linear A
    from Cypro-Minoan, so the caller names the script. Uses the stdlib XML parser only."""
    import xml.etree.ElementTree as ET

    path = Path(source)
    files = sorted(path.glob("*.xml")) if path.is_dir() else [path]
    out: list[Document] = []
    for f in files:
        doc = _read_document(ET.parse(str(f)).getroot(), script_id, f.stem)
        if doc is not None:
            out.append(doc)
    return out


def from_epidoc(source: str | Path, *, script_id: str = "greek") -> Corpus:
    """Load EpiDoc TEI (a file or a directory of ``*.xml``) into a `Corpus`.

    The inverse of `write_epidoc`: round-trips the id, find-place, token/line stream,
    editorial certainty, and alternate readings. ``script_id`` labels the corpus
    (default ``"greek"``). pyaegean parses your files locally and never re-hosts them."""
    from ..core.corpus import Corpus
    from ..core.provenance import Provenance

    docs = read_epidoc(source, script_id=script_id)
    provenance = Provenance(
        source=f"EpiDoc TEI import: {source}",
        license="Parsed locally from your EpiDoc; redistribute under the source's terms.",
    )
    return Corpus(docs, provenance=provenance, script_id=script_id)
