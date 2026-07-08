"""Build the I.Sicily Greek-inscriptions corpus (repo-only; not shipped in the wheel).

I.Sicily (https://github.com/ISicily/ISicily, CC BY 4.0) is ~5,120 EpiDoc TEI inscriptions
from ancient Sicily in many languages. This script filters to the ~3,194 primary-Greek texts
(``<textLang mainLang="grc">``), extracts the running Greek reading text of each primary edition
(respecting line breaks, expanding abbreviations, keeping restored/uncertain letters, skipping
symbols and lost gaps), and writes a compact pyaegean ``Corpus`` JSON. That JSON is published as a
sha256-pinned release asset and fetched on demand via ``aegean.load("isicily")`` — the same
build-once / host-derived / fetch-to-cache pattern as DAMOS. CC BY permits the redistribution;
attribution + the pinned source commit are recorded in the corpus provenance and NOTICE.

Usage:
    python scripts/build_isicily_corpus.py <path-to-ISicily-clone> -o isicily-corpus.json
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_TEI = "http://www.tei-c.org/ns/1.0"
_XML = "http://www.w3.org/XML/1998/namespace"

# Elements whose textual content is NOT part of the running reading text: editorial symbols
# (<g> palm/christogram/etc.), lost gaps, spaces/milestones, and apparatus/notes.
_SKIP = {"g", "gap", "space", "milestone", "note", "certainty", "lem", "rdg", "app", "abbr"}
# Within <choice>/<expan> keep the resolved/expanded form (<ex>, <reg>, <corr>), drop the raw
# (<abbr>, <orig>, <sic>) — <abbr> is already in _SKIP; <expan> keeps <ex> and drops <abbr>.


def _local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _edition_lines(edition: ET.Element) -> list[str]:
    """The primary edition's reading text as a list of physical lines (Greek running text).

    ``<lb break="no"/>`` marks a word split across a line with no word boundary, so the text that
    follows must attach with no space (Ἀ|λεξάνδρου -> Ἀλεξάνδρου); a plain ``<lb/>`` starts a new
    physical line. Inter-word spaces come from the literal text nodes between tokens."""
    lines: list[str] = [""]
    join_next = [False]  # the next text fragment continues a word (strip its leading space)

    def add(text: str | None) -> None:
        if not text:
            return
        if join_next[0]:
            text = text.lstrip()
            join_next[0] = False
        lines[-1] += text

    def walk(el: ET.Element) -> None:
        tag = _local(el.tag)
        if tag == "lb":
            if el.get("break") == "no":
                lines[-1] = lines[-1].rstrip()  # continuation attaches with no space
                join_next[0] = True
            else:
                lines.append("")
            return
        if tag in _SKIP:
            return  # element content dropped; the caller still adds the element's tail
        add(el.text)
        for child in el:
            walk(child)
            add(child.tail)

    for child in edition:  # walk the <ab>(s) under the edition div
        walk(child)
        add(child.tail)

    out: list[str] = []
    for raw in lines:
        text = re.sub(r"\s+", " ", raw).strip()
        if text:
            out.append(text)
    return out


def _first(root: ET.Element, *locals_: str) -> str:
    for want in locals_:
        for el in root.iter():
            if _local(el.tag) == want:
                text = re.sub(r"\s+", " ", "".join(el.itertext())).strip()
                if text:
                    return text
    return ""


def _place(root: ET.Element) -> tuple[str, str, str]:
    """(site, coords, pleiades_ref) — the ancient find-place name, its lat/long, Pleiades id."""
    for el in root.iter():
        if _local(el.tag) != "origPlace":
            continue
        ancient = modern = region = coords = pleiades = ""
        for sub in el.iter():
            lt = _local(sub.tag)
            name = (sub.text or "").strip()
            if lt == "placeName" and name:
                if sub.get("type") == "ancient":
                    ancient = ancient or name
                    if "pleiades" in sub.get("ref", ""):
                        pleiades = sub.get("ref", "")
                elif sub.get("type") == "modern":
                    modern = modern or name
            elif lt == "region" and name:
                region = name
            elif lt == "geo" and name:
                coords = name.replace("\n", " ")
        return (ancient or modern or region, coords, pleiades)
    return ("", "", "")


def _main_lang(root: ET.Element) -> str:
    for el in root.iter():
        if _local(el.tag) == "textLang":
            return el.get("mainLang", "")
    return ""


def _primary_edition(root: ET.Element) -> ET.Element | None:
    editions = [d for d in root.iter(f"{{{_TEI}}}div") if d.get("type") == "edition"]
    for d in editions:
        if d.get("subtype") == "primary":
            return d
    return editions[0] if editions else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="path to an ISicily/ISicily clone")
    ap.add_argument("-o", "--output", default="isicily-corpus.json")
    ap.add_argument("--limit", type=int, default=0, help="cap the number of Greek docs (0 = all)")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, DocumentMeta, Token, TokenKind
    from aegean.core.provenance import Provenance

    insc = Path(args.source) / "inscriptions"
    files = sorted(insc.glob("*.xml"))
    docs: list[Document] = []
    greek = 0
    for f in files:
        try:
            root = ET.parse(str(f)).getroot()
        except ET.ParseError:
            continue
        if _main_lang(root) != "grc":
            continue
        edition = _primary_edition(root)
        if edition is None:
            continue
        lines_text = _edition_lines(edition)
        if not lines_text:
            continue  # no readable Greek text (fragment/uninscribed)
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
        site, coords, pleiades = _place(root)
        notes = tuple(n for n in (f"coords: {coords}" if coords else "",
                                  pleiades) if n)
        meta = DocumentMeta(
            name=_first(root, "title") or f.stem,
            site=site,
            period=_first(root, "origDate"),
            findspot=coords,
            notes=notes,
        )
        docs.append(Document(id=f.stem, script_id="greek", tokens=tokens, lines=lines, meta=meta))
        if args.limit and len(docs) >= args.limit:
            break

    prov = Provenance(
        source="I.Sicily (ISicily/ISicily, CC BY 4.0), primary-Greek inscriptions",
        license="CC-BY-4.0 (I.Sicily; Jonathan Prag et al., University of Oxford)",
        url="https://github.com/ISicily/ISicily",
    )
    corpus = Corpus(docs, provenance=prov, script_id="greek")
    Path(args.output).write_text(corpus.to_json(), encoding="utf-8")
    print(f"Greek inscriptions with text: {greek}; documents written: {len(docs)}")
    print(f"wrote {args.output} ({Path(args.output).stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
