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
from _epidoc import edition_tokens, geo_coords, local, main_lang, primary_edition  # noqa: E402


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
    greek, written = _build_choice_corpus(
        insc,
        is_greek=_is_greek,
        metadata=_metadata,
        out=args.output,
        source="Inscriptions of Israel/Palestine (IIP), primary-Greek inscriptions",
        license="CC-BY-NC-4.0 (IIP; M. L. Satlow, Brown University; NonCommercial, attribution)",
        url="https://github.com/Brown-University-Library/iip-texts",
        limit=args.limit,
    )
    print(f"Greek inscriptions with text: {greek}; documents written: {written}")
    print(f"wrote {args.output} ({Path(args.output).stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
