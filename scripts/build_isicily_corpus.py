"""Build the I.Sicily Greek-inscriptions corpus (repo-only; not shipped in the wheel).

I.Sicily (https://github.com/ISicily/ISicily, CC BY 4.0) is ~5,120 EpiDoc TEI inscriptions
from ancient Sicily in many languages. This script filters to the ~3,194 primary-Greek texts
(``<textLang mainLang="grc">``), extracts the running Greek reading text of each primary edition
(respecting line breaks, expanding abbreviations, resolving editorial ``<choice>`` to its
corrected/regularized member, keeping restored/uncertain letters, skipping symbols and lost gaps),
and writes a compact pyaegean ``Corpus`` JSON. That JSON is published as a
sha256-pinned release asset and fetched on demand via ``aegean.load("isicily")`` — the same
build-once / host-derived / fetch-to-cache pattern as DAMOS. CC BY permits the redistribution;
attribution + the pinned source commit are recorded in the corpus provenance and NOTICE.

Usage:
    python scripts/build_isicily_corpus.py <path-to-ISicily-clone> -o isicily-corpus.json
"""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# The shared driver + reading-text extractor (with per-token editorial ReadingStatus) are shared
# across the epigraphy corpora; I.Sicily reuses them (choice_prefer=True resolves each editorial
# <choice> to its corrected/regularized member) so a restored/damaged reading is preserved, not
# flattened, and there is one driver rather than a per-corpus copy. edition_tokens stays imported
# for the shared-extractor conformance battery (tests/test_epidoc_conformance.py), which references
# it as a module attribute.
from _epidoc import build_greek_corpus, edition_tokens  # noqa: E402,F401


def _local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


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


def _is_greek(root: ET.Element) -> bool:
    return _main_lang(root) == "grc"


def _metadata(root: ET.Element, stem: str):  # type: ignore[no-untyped-def]
    from aegean.core.model import DocumentMeta

    site, coords, pleiades = _place(root)
    notes = tuple(n for n in (f"coords: {coords}" if coords else "", pleiades) if n)
    return DocumentMeta(
        name=_first(root, "title") or stem,
        site=site,
        period=_first(root, "origDate"),
        findspot=coords,
        notes=notes,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="path to an ISicily/ISicily clone")
    ap.add_argument("-o", "--output", default="isicily-corpus.json")
    ap.add_argument("--limit", type=int, default=0, help="cap the number of Greek docs (0 = all)")
    args = ap.parse_args()

    insc = Path(args.source) / "inscriptions"
    greek, written = build_greek_corpus(
        insc,
        is_greek=_is_greek,
        metadata=_metadata,
        out=args.output,
        source="I.Sicily (ISicily/ISicily, CC BY 4.0), primary-Greek inscriptions",
        license="CC-BY-4.0 (I.Sicily; Jonathan Prag et al., University of Oxford)",
        url="https://github.com/ISicily/ISicily",
        limit=args.limit,
        choice_prefer=True,
    )
    print(f"Greek inscriptions with text: {greek}; documents written: {written}")
    print(f"wrote {args.output} ({Path(args.output).stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
