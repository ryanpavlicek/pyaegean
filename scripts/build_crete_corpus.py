"""Build the Cretan Institutional Inscriptions Greek corpus (repo-only; not shipped).

*Cretan Institutional Inscriptions* (Irene Vagionakis, Università Ca' Foscari Venezia, 2016–2019;
**CC BY-NC-SA 4.0**) collects 600 EpiDoc XML editions of Archaic to Hellenistic Greek inscriptions
from Crete (7th–1st c. BCE) documenting the political institutions of Cretan city-states.
Built into a compact gzipped pyaegean ``Corpus`` JSON via ``scripts/_epidoc.py``, hosted as
``crete-corpus`` and fetched via ``aegean.load("crete")``. NonCommercial + ShareAlike obligations
from CC BY-NC-SA 4.0 pass to the user; never bundled in the Apache-2.0 wheel.

Usage:
    python scripts/build_crete_corpus.py <path-to-CretanInscriptions/webapps/ROOT/content/xml/epidoc> -o crete-corpus.json.gz
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
REPO_COMMIT = "70fc617724034433870910fe3637331d9cbf2014"


def _is_greek(root: ET.Element) -> bool:
    edition = primary_edition(root)
    if edition is None:
        return False
    lang = edition.get(f"{{{_XML}}}lang") or edition.get("lang") or ""
    # All 600 Cretan inscriptions are Greek; some editions omit xml:lang on <div type="edition">
    return lang == "" or lang.lower().startswith("grc")


def _metadata(root: ET.Element, stem: str):  # type: ignore[no-untyped-def]
    from aegean.core.model import DocumentMeta

    title = first_text(root, "title") or stem
    place = first_text(root, "origPlace", "placeName") or "Crete"
    date = first_text(root, "origDate")
    return DocumentMeta(
        name=title,
        site=place,
        period=date,
        notes=("Cretan Institutional Inscriptions (7th–1st c. BCE)",),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Build crete-corpus.json.gz from CretanInscriptions XML.")
    ap.add_argument("source", help="path to webapps/ROOT/content/xml/epidoc directory")
    ap.add_argument("-o", "--output", default="crete-corpus.json.gz")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    greek, written = build_greek_corpus(
        Path(args.source),
        is_greek=_is_greek,
        metadata=_metadata,
        out=args.output,
        source="Cretan Institutional Inscriptions — 600 Archaic–Hellenistic Greek inscriptions of Crete",
        license="CC BY-NC-SA 4.0 (Irene Vagionakis, Università Ca' Foscari Venezia, 2016–2019)",
        url=f"https://github.com/IreneVagionakis/CretanInscriptions/tree/{REPO_COMMIT}",
        limit=args.limit,
        edition_fidelity="apparatus-preserved,normalized",
        choice_prefer=True,
    )
    print(f"Greek inscriptions with text: {greek}; documents written: {written}")
    print(f"wrote {args.output} ({Path(args.output).stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
