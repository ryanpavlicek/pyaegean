"""Build the IOSPE Greek corpus (repo-only; not shipped).

IOSPE³ — Ancient Inscriptions of the Northern Black Sea (King's College London;
github.com/kingsdigitallab/iospe). The repo is MIT-licensed and the project publishes the data
under CC BY; pyaegean attributes IOSPE and treats the data as CC BY (attribution). This filters the
~1,542 Greek inscriptions (the primary edition div is ``xml:lang="grc"``), extracts each edition's
Greek reading, and writes a compact ``Corpus`` JSON, hosted as ``iospe-corpus`` and fetched via
``aegean.load("iospe")``. IOSPE metadata is bilingual (Russian + English); the English/Latin part is
taken for the find-place, date, and title.

Usage:  python scripts/build_iospe_corpus.py <path-to-iospe-clone> -o iospe-corpus.json
  (the inscriptions live under kiln/webapps/ROOT/content/xml/tei/inscriptions/)
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _epidoc import edition_tokens, first_text, geo_coords, primary_edition  # noqa: E402

_XML = "http://www.w3.org/XML/1998/namespace"
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def _build_choice_corpus(  # type: ignore[no-untyped-def]
    insc_dir,
    *,
    is_greek,
    metadata,
    out,
    source,
    license,
    url,
    script_id="greek",
    limit=0,
    edition_fidelity="apparatus-preserved,normalized",
):
    """Mirror of ``_epidoc.build_greek_corpus`` that resolves each editorial ``<choice>`` to its
    corrected/regularized member (``edition_tokens(choice_prefer=True)``) instead of concatenating
    both alternatives into one garbled token. Inlined because ``build_greek_corpus`` does not expose
    the flag; EDH/DDbDP already resolve choices this way (expan>reg>corr, lem>rdg)."""
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, Token, TokenKind
    from aegean.core.provenance import Provenance

    files = sorted(Path(insc_dir).glob("*.xml"))
    docs: list = []
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
        token_lines = edition_tokens(edition, choice_prefer=True)
        if not token_lines:
            continue
        greek += 1
        tokens: list = []
        lines: list = []
        pos = 0
        for tl in token_lines:
            idxs: list = []
            for word, status in tl:
                if not word:
                    continue
                tokens.append(
                    Token(text=word, kind=TokenKind.WORD, line_no=len(lines), position=pos, status=status)
                )
                idxs.append(pos)
                pos += 1
            if idxs:
                lines.append(idxs)
        if not tokens:
            continue
        docs.append(
            Document(id=f.stem, script_id=script_id, tokens=tokens, lines=lines, meta=metadata(root, f.stem))
        )
        if limit and len(docs) >= limit:
            break

    prov = Provenance(source=source, license=license, url=url, edition_fidelity=edition_fidelity)
    corpus = Corpus(docs, provenance=prov, script_id=script_id)
    Path(out).write_text(corpus.to_json(), encoding="utf-8")
    return greek, len(docs)


def _english_tail(text: str) -> str:
    """IOSPE fields read 'Russian. English.'; return the English/Latin tail after the last
    Cyrillic character (empty-safe: falls back to the whole string when there is no English part)."""
    matches = list(_CYRILLIC.finditer(text))
    if matches:
        tail = text[matches[-1].end():].strip(" .;,")
        if tail:
            return tail
    return text.strip()


def _is_greek(root: ET.Element) -> bool:
    edition = primary_edition(root)
    return edition is not None and edition.get(f"{{{_XML}}}lang") == "grc"


def _metadata(root: ET.Element, stem: str):  # type: ignore[no-untyped-def]
    from aegean.core.model import DocumentMeta

    coords = geo_coords(root)
    site = _english_tail(first_text(root, "origPlace"))
    period = _english_tail(first_text(root, "origDate"))
    name = _english_tail(first_text(root, "title")) or stem
    notes = tuple(n for n in (f"coords: {coords}" if coords else "",) if n)
    return DocumentMeta(name=name, site=site, period=period, findspot=coords, notes=notes)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="path to a kingsdigitallab/iospe clone")
    ap.add_argument("-o", "--output", default="iospe-corpus.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    insc = Path(args.source) / "kiln" / "webapps" / "ROOT" / "content" / "xml" / "tei" / "inscriptions"
    greek, written = _build_choice_corpus(
        insc,
        is_greek=_is_greek,
        metadata=_metadata,
        out=args.output,
        source="IOSPE — Ancient Inscriptions of the Northern Black Sea, Greek inscriptions",
        license="CC-BY-4.0 (IOSPE III, King's College London; attribution; repo code is MIT)",
        url="https://github.com/kingsdigitallab/iospe",
        limit=args.limit,
    )
    print(f"Greek inscriptions with text: {greek}; documents written: {written}")
    print(f"wrote {args.output} ({Path(args.output).stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
