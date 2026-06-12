"""Write the corpus model to EpiDoc TEI XML — the inverse of the EpiDoc reader.

A `Document` becomes a TEI document: the header carries the id and
find-place, the body carries the transliteration as ``<w>``/``<num>``/``<g>``/``<seg>`` tokens with
``<lb/>`` line breaks. Built with the stdlib XML writer (lazy-imported), so **export needs no extra
dependency** — reading EpiDoc still uses lxml via the ``[epidoc]`` extra (see
`aegean.scripts.linearb.parse_epidoc`).

It round-trips through that reader for the content EpiDoc preserves — the document id, find-place,
and the token/line stream. The reader re-derives token kinds from the text, so a written corpus
reloads with the same words, numerals, ideograms, separators, and lines.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..core.model import Document, ReadingStatus, TokenKind

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
_STATUS_EL = {
    ReadingStatus.UNCLEAR: ("unclear", {}),
    ReadingStatus.RESTORED: ("supplied", {"reason": "lost"}),
    ReadingStatus.LOST: ("supplied", {"reason": "lost"}),
}


def to_epidoc(document: Document) -> str:
    """Serialize a single `Document` to an EpiDoc TEI XML string.

    The transliteration lives in a TEI ``<div type="edition">`` (EpiDoc's required edition
    division), as ``<lb/>``-delimited lines of ``<w>``/``<num>``/``<g>`` tokens. A token whose
    `aegean.ReadingStatus` is not ``CERTAIN`` is wrapped in the matching EpiDoc apparatus
    element (``<unclear>`` or ``<supplied>``), so editorial certainty survives the round trip
    through `aegean.scripts.linearb.parse_epidoc`. The output validates against the EpiDoc
    RelaxNG schema (see ``tests/test_io.py``)."""
    import xml.etree.ElementTree as ET  # lazy: keep `import aegean` free of the XML parser

    def q(tag: str) -> str:
        return f"{{{_TEI}}}{tag}"

    def sub(parent: ET.Element, tag: str, text: str | None = None) -> ET.Element:
        el = ET.SubElement(parent, q(tag))
        if text is not None:
            el.text = text
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
                el.text = tok.text
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
    `aegean.scripts.linearb.parse_epidoc` reads back."""
    if isinstance(obj, Document):
        Path(path).write_text(to_epidoc(obj), encoding="utf-8")
        return
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    for doc in obj:
        (out / f"{_safe_name(doc.id)}.xml").write_text(to_epidoc(doc), encoding="utf-8")
