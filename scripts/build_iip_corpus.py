"""Build the IIP (Inscriptions of Israel/Palestine) Greek corpus (repo-only; not shipped).

IIP (Michael L. Satlow, ed., Brown University; github.com/Brown-University-Library/iip-texts,
CC BY-NC 4.0) is a multilingual EpiDoc corpus (Greek, Aramaic, Hebrew, Latin, Phoenician). This
filters the ~3,020 primary-Greek inscriptions (``<textLang mainLang="grc">``), extracts each
primary edition's Greek reading, and writes a compact pyaegean ``Corpus`` JSON, hosted as the
sha256-pinned ``iip-corpus`` release asset and fetched via ``aegean.load("iip")``. CC BY-NC permits
the redistribution (NonCommercial passes through; the asset is never bundled in the wheel).

Usage:  python scripts/build_iip_corpus.py <path-to-iip-texts-clone> -o iip-corpus.json
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The shared driver + reading-text extractor: build_greek_corpus(choice_prefer=True) resolves
# each editorial <choice> to its corrected/regularized member (expan>reg>corr) instead of
# fusing both alternatives. edition_tokens stays imported for the shared-extractor conformance
# battery (tests/test_epidoc_conformance.py), which references it as a module attribute.
from _epidoc import build_greek_corpus, edition_tokens, geo_coords, local, main_lang  # noqa: E402,F401


def _is_greek(root: ET.Element) -> bool:
    return main_lang(root) == "grc"


def _metadata(root: ET.Element, stem: str):  # type: ignore[no-untyped-def]
    from aegean.core.model import DocumentMeta

    settlement = region = ""
    for el in root.iter():
        lt = local(el.tag)
        if lt == "settlement" and el.text and el.text.strip():
            settlement = settlement or el.text.strip()
        elif lt == "region" and el.text and el.text.strip():
            region = region or el.text.strip()
    coords = geo_coords(root)
    site = settlement or region
    notes = tuple(
        n for n in (
            f"region: {region}" if region and settlement else "",
            f"coords: {coords}" if coords else "",
        ) if n
    )
    return DocumentMeta(name=stem, site=site, findspot=coords, notes=notes)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="path to a Brown-University-Library/iip-texts clone")
    ap.add_argument("-o", "--output", default="iip-corpus.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    insc = Path(args.source) / "epidoc-files"
    greek, written = build_greek_corpus(
        insc,
        is_greek=_is_greek,
        metadata=_metadata,
        out=args.output,
        source="Inscriptions of Israel/Palestine (IIP), primary-Greek inscriptions",
        license="CC-BY-NC-4.0 (IIP; M. L. Satlow, Brown University; NonCommercial, attribution)",
        url="https://github.com/Brown-University-Library/iip-texts",
        limit=args.limit,
        choice_prefer=True,
    )
    print(f"Greek inscriptions with text: {greek}; documents written: {written}")
    print(f"wrote {args.output} ({Path(args.output).stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
