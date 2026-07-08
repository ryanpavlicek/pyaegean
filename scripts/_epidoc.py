"""Shared EpiDoc → pyaegean-Corpus build helpers (repo-only; used by the corpus build scripts).

The hard part — turning an EpiDoc ``<div type="edition">`` into clean running Greek text — is one
function, `edition_lines`, reused across every epigraphic corpus (I.Sicily, IIP, IOSPE, Cyrenaica,
EDH). Each corpus script supplies only its own Greek filter and metadata mapping and calls
`build_greek_corpus`. All licences permit redistributing the derived corpus as a separate,
self-licensed release asset (never bundled in the Apache-2.0 wheel), so pyaegean can mirror them.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

_TEI = "http://www.tei-c.org/ns/1.0"
_XML = "http://www.w3.org/XML/1998/namespace"

# Elements whose textual content is NOT part of the running reading text: editorial symbols
# (<g> palm/christogram/etc.), lost gaps, spaces/milestones, apparatus/notes, a section <head>
# label (EDH editions open with <head>Text</head>), and abbreviations (the <ex> expansion inside
# <expan> is kept; the raw <abbr> is dropped).
_SKIP = {"g", "gap", "space", "milestone", "note", "certainty", "lem", "rdg", "app", "abbr", "head"}


def local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def edition_lines(edition: ET.Element) -> list[str]:
    """The edition's reading text as a list of physical lines (running Greek text).

    ``<lb break="no"/>`` marks a word split across a line with no word boundary, so the following
    text attaches with no space (Ἀ|λεξάνδρου → Ἀλεξάνδρου); a plain ``<lb/>`` starts a new line.
    Inter-word spaces come from the literal text nodes between tokens."""
    lines: list[str] = [""]
    join_next = [False]

    def add(text: str | None) -> None:
        if not text:
            return
        if join_next[0]:
            text = text.lstrip()
            join_next[0] = False
        lines[-1] += text

    def walk(el: ET.Element) -> None:
        tag = local(el.tag)
        if tag == "lb":
            if el.get("break") == "no":
                lines[-1] = lines[-1].rstrip()
                join_next[0] = True
            else:
                lines.append("")
            return
        if tag in _SKIP:
            return
        add(el.text)
        for child in el:
            walk(child)
            add(child.tail)

    for child in edition:
        walk(child)
        add(child.tail)

    out: list[str] = []
    for raw in lines:
        text = re.sub(r"\s+", " ", raw).strip()
        if text:
            out.append(text)
    return out


def primary_edition(root: ET.Element) -> ET.Element | None:
    """The primary edition div (``subtype="primary"`` if present, else the first edition)."""
    editions = [d for d in root.iter(f"{{{_TEI}}}div") if d.get("type") == "edition"]
    for d in editions:
        if d.get("subtype") == "primary":
            return d
    return editions[0] if editions else None


def first_text(root: ET.Element, *locals_: str) -> str:
    for want in locals_:
        for el in root.iter():
            if local(el.tag) == want:
                text = re.sub(r"\s+", " ", "".join(el.itertext())).strip()
                if text:
                    return text
    return ""


def main_lang(root: ET.Element) -> str:
    for el in root.iter():
        if local(el.tag) == "textLang":
            return el.get("mainLang", "")
    return ""


def geo_coords(root: ET.Element) -> str:
    for el in root.iter():
        if local(el.tag) == "geo" and el.text and el.text.strip():
            return el.text.strip().replace("\n", " ")
    return ""


def build_greek_corpus(
    insc_dir: str | Path,
    *,
    is_greek: Callable[[ET.Element], bool],
    metadata: Callable[[ET.Element, str], Any],
    out: str | Path,
    source: str,
    license: str,
    url: str,
    script_id: str = "greek",
    limit: int = 0,
) -> tuple[int, int]:
    """Filter the Greek inscriptions of an EpiDoc directory, extract each primary edition's Greek
    reading, and write a compact pyaegean ``Corpus`` JSON. Returns (greek_with_text, documents)."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, Token, TokenKind
    from aegean.core.provenance import Provenance

    files = sorted(Path(insc_dir).glob("*.xml"))
    docs: list[Document] = []
    greek = 0
    for f in files:
        try:
            root = ET.parse(str(f)).getroot()
        except ET.ParseError:
            continue
        if not is_greek(root):
            continue
        edition = primary_edition(root)
        if edition is None:
            continue
        lines_text = edition_lines(edition)
        if not lines_text:
            continue
        greek += 1
        tokens: list[Token] = []
        lines: list[list[int]] = []
        pos = 0
        for lt in lines_text:
            idxs: list[int] = []
            for word in lt.split(" "):
                if not word:
                    continue
                tokens.append(Token(text=word, kind=TokenKind.WORD, line_no=len(lines), position=pos))
                idxs.append(pos)
                pos += 1
            if idxs:
                lines.append(idxs)
        if not tokens:
            continue
        docs.append(Document(id=f.stem, script_id=script_id, tokens=tokens, lines=lines, meta=metadata(root, f.stem)))
        if limit and len(docs) >= limit:
            break

    corpus = Corpus(docs, provenance=Provenance(source=source, license=license, url=url), script_id=script_id)
    Path(out).write_text(corpus.to_json(), encoding="utf-8")
    return greek, len(docs)
