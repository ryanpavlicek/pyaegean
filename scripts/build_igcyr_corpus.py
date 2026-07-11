"""Build the IGCyr/GVCyr (Greek inscriptions of Cyrenaica) corpus (repo-only; not shipped).

IGCyr² + GVCyr² (eds. C. Dobias-Lalou et al., Università di Bologna, 2024; AMS Acta eprint 7796,
**CC BY-NC-SA 4.0**) is the EpiDoc corpus of the Greek inscriptions of ancient Cyrenaica — including
the archaic epichoric **Doric** dialect and the GVCyr metrical/**verse** subset. All 1,014
inscriptions are Greek (the edition div is ``xml:lang="grc"``). This extracts each edition's Greek
reading + find-place / date / title into a compact ``Corpus`` JSON, hosted as ``igcyr-corpus`` and
fetched via ``aegean.load("igcyr")``. The text preserves epichoric letterforms (e.g. ``ō``/``ē`` for
long o/e), i.e. it is NON-normalized epichoric Greek, not standard polytonic Koine.

Usage:  python scripts/build_igcyr_corpus.py <path-to-IGCyr2-GVCyr2-inscriptions dir> -o igcyr-corpus.json
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
from _epidoc import (  # noqa: E402,F401
    build_greek_corpus,
    edition_tokens,
    first_text,
    geo_coords,
    primary_edition,
)

_XML = "http://www.w3.org/XML/1998/namespace"


def _is_greek(root: ET.Element) -> bool:
    edition = primary_edition(root)
    return edition is not None and edition.get(f"{{{_XML}}}lang") == "grc"


def _metadata(root: ET.Element, stem: str):  # type: ignore[no-untyped-def]
    from aegean.core.model import DocumentMeta

    coords = geo_coords(root)
    notes = tuple(n for n in (f"coords: {coords}" if coords else "",) if n)
    return DocumentMeta(
        name=first_text(root, "title") or stem,
        site=first_text(root, "placeName"),
        period=first_text(root, "origDate"),
        findspot=coords,
        notes=notes,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="path to the IGCyr2-GVCyr2-inscriptions directory")
    ap.add_argument("-o", "--output", default="igcyr-corpus.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    greek, written = build_greek_corpus(
        Path(args.source),
        is_greek=_is_greek,
        metadata=_metadata,
        out=args.output,
        source="IGCyr²/GVCyr² — Greek inscriptions of Cyrenaica (incl. Doric and verse)",
        license="CC-BY-NC-SA-4.0 (IGCyr2/GVCyr2, C. Dobias-Lalou et al., Univ. di Bologna, 2024)",
        url="https://doi.org/10.6092/unibo/amsacta/7796",
        limit=args.limit,
        # IGCyr keeps the epichoric letterforms (ō/ē for long o/e), so the text is NOT normalized
        edition_fidelity="apparatus-preserved,epichoric",
        choice_prefer=True,
    )
    print(f"Greek inscriptions with text: {greek}; documents written: {written}")
    print(f"wrote {args.output} ({Path(args.output).stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
