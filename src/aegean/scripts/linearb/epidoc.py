"""Parse DAMOS-style EpiDoc TEI XML (a user-supplied Linear B corpus) into the corpus model.

This is the bring-your-own path for users with their own licensed export — e.g. a DAMOS EpiDoc
download or another edition (the ``[epidoc]`` extra provides lxml; for the generic, stdlib-only
EpiDoc reader use ``aegean.io.from_epidoc``); for the ready-made full
corpus use ``aegean.load("damos")`` instead. pyaegean parses your files locally and never
re-hosts them. The reader is tolerant of EpiDoc variation — it takes the tablet id and
provenance from the header and the transliteration (words, numerals, ideograms) line by line,
splitting at ``<lb>`` markers.

Set ``PYAEGEAN_LINEARB_CORPUS`` to a file or directory of EpiDoc XML and ``Corpus.load("linearb")``
returns it instead of the bundled sample; or call `load_epidoc_corpus` directly.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from ...core.model import Document, DocumentMeta, ReadingStatus, Token
from ...core.model import TokenKind
from .loader import classify

if TYPE_CHECKING:
    from ...core.corpus import Corpus

_TEI = "{http://www.tei-c.org/ns/1.0}"
_TOKEN_TAGS = {"w", "num", "seg", "g", "pc"}
_QUALIFIER_RE = re.compile(r"^([^:;]+)([:;])([mfx])([^:;]*)$", re.IGNORECASE)


def _normalize_token(text: str) -> str:
    """Uppercase Linear B EpiDoc text while preserving lowercase ideogram
    qualifiers such as ``OVIS:m``, ``CAP:f``, and ``BOS:x``."""
    m = _QUALIFIER_RE.match(text)
    if m is not None:
        head, sep, qual, tail = m.groups()
        return f"{head.upper()}{sep}{qual.lower()}{tail.upper()}"
    return text.upper()


def _text(el: Any) -> str:
    return "".join(el.itertext()).strip()


def _first(root: Any, *tags: str) -> str:
    for tag in tags:
        el = root.find(f".//{_TEI}{tag}")
        if el is not None and _text(el):
            return _text(el)
    return ""


def _status_of(el: Any) -> ReadingStatus:
    """Editorial status of a token from any EpiDoc apparatus element it contains.

    ``<supplied>`` carries two distinct statuses by its ``@reason`` (matching the writer):
    ``reason="undefined"`` (a non-preserved / conjectural reading) is ``LOST``; any other
    ``<supplied>`` (the editor-supplied ``reason="lost"``) is ``RESTORED``. A bare ``<gap>``
    (an external edition's empty lacuna marker) is also ``LOST``."""
    supplied = next(
        (c for c in el.iter() if isinstance(c.tag, str) and c.tag.replace(_TEI, "") == "supplied"),
        None,
    )
    if supplied is not None:
        if supplied.get("reason") == "undefined":
            return ReadingStatus.LOST
        return ReadingStatus.RESTORED
    tags = {c.tag.replace(_TEI, "") for c in el.iter() if isinstance(c.tag, str)}
    if "unclear" in tags:
        return ReadingStatus.UNCLEAR
    if "gap" in tags:
        return ReadingStatus.LOST
    return ReadingStatus.CERTAIN


def _document(root: Any) -> Document | None:
    body = root.find(f".//{_TEI}body")
    if body is None:
        return None
    doc_id = _first(root, "idno", "title") or "linearb-doc"
    site = _first(root, "origPlace", "settlement", "provenance")
    tokens: list[Token] = []
    lines: list[list[int]] = []
    cur: list[int] = []
    pos = 0

    def inside_consumed_parent(el: Any) -> bool:
        # Token elements under <app> belong to the apparatus, and nested token
        # elements (e.g. <w>wa-<g>na</g>-ka</w>) are already included in their
        # enclosing carrier's itertext(). Walk ancestors rather than using id()
        # because lxml element proxies are not identity-stable.
        parent = el.getparent() if hasattr(el, "getparent") else None
        while parent is not None and parent is not body:
            ptag = parent.tag.replace(_TEI, "") if isinstance(parent.tag, str) else ""
            if ptag == "app" or ptag in _TOKEN_TAGS:
                return True
            parent = parent.getparent()
        return False

    for el in body.iter():
        tag = el.tag.replace(_TEI, "") if isinstance(el.tag, str) else ""
        if tag == "lb":
            if cur:
                lines.append(cur)
                cur = []
        elif tag == "app":
            # one token with alternate readings: <app><lem>…</lem><rdg>…</rdg>…</app>
            lem = el.find(f"{_TEI}lem")
            rdgs = tuple(
                _normalize_token(_text(r)) for r in el.findall(f"{_TEI}rdg") if _text(r)
            )
            text = _text(lem) if lem is not None else ""
            if text:
                tok = classify(_normalize_token(text), len(lines), pos)
                tok = replace(tok, status=_status_of(lem), alt=rdgs)
                tokens.append(tok)
                cur.append(pos)
                pos += 1
            elif rdgs:
                # a fully-uncertain word: variant <rdg> readings but no editor-preferred
                # <lem>. Keep it (reading the first variant, flagged UNCLEAR, the rest as
                # alts) rather than dropping the token and losing the word entirely.
                tok = classify(rdgs[0], len(lines), pos)
                tok = replace(tok, status=ReadingStatus.UNCLEAR, alt=rdgs[1:])
                tokens.append(tok)
                cur.append(pos)
                pos += 1
        elif tag in _TOKEN_TAGS:
            if inside_consumed_parent(el):
                continue
            text = _text(el)
            if text:
                # EpiDoc transliterations are lowercase; pyaegean's token convention (and the
                # accounting markers / lexicon) is uppercase, preserving lowercase qualifiers
                # like OVIS:m / CAP:f.
                tok = classify(_normalize_token(text), len(lines), pos)
                if tag == "pc":
                    # <pc> states the kind outright, so it outranks the text heuristic.
                    tok = replace(tok, text=text, kind=TokenKind.PUNCT)
                status = _status_of(el)
                if status is not ReadingStatus.CERTAIN:
                    tok = replace(tok, status=status)
                tokens.append(tok)
                cur.append(pos)
                pos += 1
    if cur:
        lines.append(cur)
    meta = DocumentMeta(site=site, support="Tablet", scribe="", findspot="", period="", name=doc_id)
    return Document(
        id=doc_id, script_id="linearb", tokens=tokens, lines=lines,
        glyphs="", transcription="", translations=[], meta=meta,
    )


def parse_epidoc(source: str | pathlib.Path) -> list[Document]:
    """Parse a DAMOS-style EpiDoc file, or a directory of them, into Documents."""
    try:
        from lxml import etree
    except ModuleNotFoundError as e:  # pragma: no cover - import guard
        raise ImportError(
            "EpiDoc parsing needs the optional dependency: pip install 'pyaegean[epidoc]'"
        ) from e
    path = pathlib.Path(source)
    files = sorted(path.glob("*.xml")) if path.is_dir() else [path]
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        huge_tree=False,
    )
    docs: list[Document] = []
    for f in files:
        doc = _document(etree.parse(str(f), parser=parser).getroot())
        if doc is not None:
            docs.append(doc)
    return docs


def load_epidoc_corpus(source: str | pathlib.Path) -> Corpus:
    """Load a user-supplied EpiDoc Linear B corpus into a `Corpus`."""
    from ...core.corpus import Corpus
    from ...core.provenance import Provenance
    from .inventory import linear_b_inventory

    provenance = Provenance(
        # basename only: the full path would leak the user's directory layout into a shared export
        source=f"User-supplied Linear B EpiDoc corpus: {pathlib.Path(source).name}",
        license="User-supplied (e.g. DAMOS, CC BY-NC-SA 4.0) — parsed locally, not redistributed by pyaegean",
        citation="Aurora, F. DAMOS — Database of Mycenaean at Oslo (if applicable).",
        url="",
    )
    return Corpus(
        parse_epidoc(source), sign_inventory=linear_b_inventory(),
        provenance=provenance, script_id="linearb",
    )
