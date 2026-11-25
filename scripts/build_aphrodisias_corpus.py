"""Build the Inscriptions of Aphrodisias (IAph2007) Greek corpus (repo-only; not shipped).

*Inscriptions of Aphrodisias 2007* (eds. Joyce Reynolds, Charlotte Roueché & Gabriel Bodard,
King's College London, 2007; **CC BY 2.5**, http://insaph.kcl.ac.uk/) is the EpiDoc corpus of
~1,500 Greek and bilingual inscriptions from Aphrodisias in Caria (Western Asia Minor, 2nd c. BCE
to Byzantine period). All Greek primary editions (``<div type="edition" lang="grc">``) are
extracted with per-token editorial ``ReadingStatus`` into a compact gzipped pyaegean ``Corpus``
JSON, hosted as ``aphrodisias-corpus`` and fetched via ``aegean.load("aphrodisias")``.

Usage:
    python scripts/build_aphrodisias_corpus.py <path-to-extracted-iaph2007-dir> -o aphrodisias-corpus.json.gz
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _epidoc import (  # noqa: E402,F401
    build_greek_corpus,
    edition_tokens,
    first_text,
    primary_edition,
)

_XML = "http://www.w3.org/XML/1998/namespace"


def _is_greek(root: ET.Element) -> bool:
    edition = primary_edition(root)
    if edition is None:
        return False
    lang = edition.get("lang") or edition.get(f"{{{_XML}}}lang") or ""
    return lang.lower().startswith("grc")


def _metadata(root: ET.Element, stem: str):  # type: ignore[no-untyped-def]
    from aegean.core.model import DocumentMeta

    title = first_text(root, "title") or stem
    date = first_text(root, "origDate", "date")
    place = first_text(root, "placeName") or "Aphrodisias"
    return DocumentMeta(
        name=title,
        site=place,
        period=date,
        notes=("Inscriptions of Aphrodisias (IAph2007)",),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Build aphrodisias-corpus.json.gz from IAph2007 XML.")
    ap.add_argument("source", help="directory containing IAph2007 EpiDoc XML files")
    ap.add_argument("-o", "--output", default="aphrodisias-corpus.json.gz")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    # IAph2007 XMLs may live directly in source or in a nested subfolder (e.g. xml/)
    src = Path(args.source)
    if not list(src.glob("*.xml")):
        subdirs = [p for p in src.rglob("*") if p.is_dir() and list(p.glob("*.xml"))]
        if subdirs:
            src = subdirs[0]

    greek, written = build_greek_corpus(
        src,
        is_greek=_is_greek,
        metadata=_metadata,
        out=args.output,
        source="Inscriptions of Aphrodisias (IAph2007) — Greek inscriptions of Aphrodisias in Caria",
        license="CC BY 2.5 (Joyce Reynolds, Charlotte Roueché & Gabriel Bodard, King's College London, 2007; http://insaph.kcl.ac.uk/)",
        url="http://insaph.kcl.ac.uk/",
        limit=args.limit,
        edition_fidelity="apparatus-preserved,normalized",
        choice_prefer=True,
    )
    print(f"Greek inscriptions with text: {greek}; documents written: {written}")
    print(f"wrote {args.output} ({Path(args.output).stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
