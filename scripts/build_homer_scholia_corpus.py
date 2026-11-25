"""Build the Homer Multitext Venetus A Iliad & Homeric Scholia corpus (``homer-scholia-corpus.json.gz``).

Extracts the normalized Venetus A (10th c., Marcianus Graecus Z. 454) *Iliad* (24 books,
15,645 lines) and Homeric *scholia* (Venetus A main, interlinear, intermarginal, interior,
exterior scholia, plus Venetus B and Escorial Upsilon 1.1 scholia) from the official
*Homer Multitext Project* release ``hmt-2026a.cex`` (``homermultitext/hmt-archive``;
**CC BY-NC 4.0**).

NonCommercial obligations from CC BY-NC 4.0 pass to the user; fetched on demand via
``aegean.load("homer-scholia")`` and never bundled in the Apache-2.0 wheel.

Usage:
    python scripts/build_homer_scholia_corpus.py <path-to-hmt-2026a.cex> -o homer-scholia-corpus.json.gz
"""

from __future__ import annotations

import argparse
import gzip
import re
import sys
import unicodedata
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

REPO = "homermultitext/hmt-archive"
COMMIT = "cd09f8bcf8a88854557b02dc25f14a711ef16617"
RELEASE_NAME = "hmt-2026a"

_GREEK_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")

# CTS URN prefixes to include (normalized editions for clean Greek tokenization)
_COLLECTIONS: dict[str, tuple[str, str, str]] = {
    "urn:cts:greekLit:tlg0012.tlg001.msA.normalized": ("Iliad.msA", "Homer, Iliad (Venetus A, normalized)", "10th c. MS (Archaic epic)"),
    "urn:cts:greekLit:tlg5026.msA.hmt.normalized": ("Scholia.msA", "Venetus A Main Scholia on the Iliad", "10th c. MS (Alexandrian/Byzantine scholia)"),
    "urn:cts:greekLit:tlg5026.msAil.hmt.normalized": ("Scholia.msAil", "Venetus A Interlinear Scholia", "10th c. MS (scholia)"),
    "urn:cts:greekLit:tlg5026.msAim.hmt.normalized": ("Scholia.msAim", "Venetus A Intermarginal Scholia", "10th c. MS (scholia)"),
    "urn:cts:greekLit:tlg5026.msAint.hmt.normalized": ("Scholia.msAint", "Venetus A Interior Scholia", "10th c. MS (scholia)"),
    "urn:cts:greekLit:tlg5026.msAext.hmt.normalized": ("Scholia.msAext", "Venetus A Exterior Scholia", "10th c. MS (scholia)"),
    "urn:cts:greekLit:tlg5026.msB.hmt.normalized": ("Scholia.msB", "Venetus B Scholia on the Iliad", "11th c. MS (scholia)"),
    "urn:cts:greekLit:tlg5026.e3.hmt.normalized": ("Scholia.e3", "Escorial Upsilon 1.1 Scholia on the Iliad", "11th c. MS (scholia)"),
}


def build(cex_path: Path) -> object:
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, DocumentMeta, Token, TokenKind
    from aegean.core.provenance import Provenance
    from aegean.greek.tokenize import tokenize

    # Group lines by (doc_id, title, period)
    grouped: OrderedDict[str, tuple[str, str, list[tuple[str, str]]]] = OrderedDict()

    in_cts = False
    for raw_line in cex_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw_line.startswith("#!"):
            in_cts = raw_line.strip() == "#!ctsdata"
            continue
        if not in_cts or "|" not in raw_line:
            continue
        urn, text = raw_line.split("|", 1)
        base, _, passage = urn.rpartition(":")
        spec = _COLLECTIONS.get(base)
        if spec is None:
            continue
        text = text.strip()
        if not text or not _GREEK_RE.search(text):
            continue
        prefix, label, period = spec
        # Split the huge Iliad and Venetus A main scholia by book (1..24)
        book = passage.split(".", 1)[0]
        if prefix in ("Iliad.msA", "Scholia.msA") and book.isdigit():
            doc_id = f"{prefix}.{int(book):02d}"
            title = f"{label}, Book {int(book)}"
        else:
            doc_id = prefix
            title = label
        if doc_id not in grouped:
            grouped[doc_id] = (title, period, [])
        grouped[doc_id][2].append((passage, text))

    docs: list[Document] = []
    for doc_id, (title, period, entries) in grouped.items():
        tokens: list[Token] = []
        lines: list[list[int]] = []
        for passage, text in entries:
            line_no = len(lines)
            idxs: list[int] = []
            for tok in tokenize(text):
                if not any(ch.isalpha() for ch in tok.text):
                    continue
                word = unicodedata.normalize("NFC", tok.text)
                pos = len(tokens)
                tokens.append(
                    Token(
                        text=word,
                        kind=TokenKind.WORD,
                        glyphs=word,
                        line_no=line_no,
                        position=pos,
                        annotations={"ref": passage},
                    )
                )
                idxs.append(pos)
            if idxs:
                lines.append(idxs)
        if not tokens:
            continue
        docs.append(
            Document(
                id=doc_id,
                script_id="greek",
                tokens=tokens,
                lines=lines,
                meta=DocumentMeta(name=title, period=period, notes=(f"HMT release {RELEASE_NAME}",)),
            )
        )
        print(f"  {doc_id:18s} {len(lines):5d} passages, {len(tokens):6d} tokens — {title}")

    prov = Provenance(
        source=f"Homer Multitext Project ({RELEASE_NAME}): Venetus A Iliad & Homeric Scholia",
        license="CC BY-NC 4.0 (Homer Multitext Project, Center for Hellenic Studies; NonCommercial, never bundled)",
        url=f"https://github.com/{REPO}/blob/{COMMIT}/releases-cex/{RELEASE_NAME}.cex",
        citation="Homer Multitext Project (2026a). Center for Hellenic Studies, Harvard University. CC BY-NC 4.0.",
        edition_fidelity="normalized",
    )
    return Corpus(docs, provenance=prov, script_id="greek")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build homer-scholia-corpus.json.gz from HMT CEX.")
    ap.add_argument("source", type=Path, help="path to hmt-2026a.cex")
    ap.add_argument("-o", "--output", type=Path, default=Path("homer-scholia-corpus.json.gz"))
    args = ap.parse_args()
    corpus = build(args.source)
    payload = corpus.to_json().encode("utf-8")  # type: ignore[attr-defined]
    with args.output.open("wb") as raw_f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_f, compresslevel=9, mtime=0) as gz:
            gz.write(payload)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
