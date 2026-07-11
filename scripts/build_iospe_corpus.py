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
# The shared driver + reading-text extractor: build_greek_corpus(choice_prefer=True) resolves
# each editorial <choice> to its corrected/regularized member (expan>reg>corr) instead of
# fusing both alternatives. edition_tokens stays imported for the shared-extractor conformance
# battery (tests/test_epidoc_conformance.py), which references it as a module attribute.
from _epidoc import (  # noqa: E402,F401
    build_greek_corpus,
    edition_tokens,
    first_text,
    geo_coords,
    primary_edition,
)

_XML = "http://www.w3.org/XML/1998/namespace"
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")


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
    greek, written = build_greek_corpus(
        insc,
        is_greek=_is_greek,
        metadata=_metadata,
        out=args.output,
        source="IOSPE — Ancient Inscriptions of the Northern Black Sea, Greek inscriptions",
        license="CC-BY-4.0 (IOSPE III, King's College London; attribution; repo code is MIT)",
        url="https://github.com/kingsdigitallab/iospe",
        limit=args.limit,
        choice_prefer=True,
    )
    print(f"Greek inscriptions with text: {greek}; documents written: {written}")
    print(f"wrote {args.output} ({Path(args.output).stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
