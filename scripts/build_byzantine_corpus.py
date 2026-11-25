"""Build the Byzantine & Early Modern Vernacular Greek corpus (``byzantine-corpus.json.gz``).

Sources the 12 medieval and early modern vernacular Greek literary texts (~191,000 words,
12th–17th centuries) from ``open-greek/byzantine-early-modern-corpus`` (compiled by
Francisco Riordan; individual texts **Public Domain / CC BY-SA 3.0** via Wikisource &
Kalonaros 1940 edition):

*Digenes Akritas* (Escorial MS excerpt & folk ballads), *Ptochoprodromika*, *Chronicle of Moreas*,
*Poulologos*, *Paidiophrastos Diegesis*, *Porikologos*, *Tale of the Donkey, Wolf and Fox*,
*Apokopos* (Bergadis, two editions), *Peri Gerontos*, and *Erotokritos* (Kornaros).

Usage:
    python scripts/build_byzantine_corpus.py -o byzantine-corpus.json.gz
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import unicodedata
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

REPO = "open-greek/byzantine-early-modern-corpus"
COMMIT = "0178600ad7d7b19b04cc4ff21f6ec5b1088ca65f"


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "pyaegean-build"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        return resp.read().decode("utf-8-sig")


def build() -> object:
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, DocumentMeta, Token, TokenKind
    from aegean.core.provenance import Provenance
    from aegean.greek.tokenize import tokenize

    manifest_url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/texts/manifest.json"
    manifest = json.loads(_fetch_text(manifest_url))

    docs: list[Document] = []
    for entry in manifest:
        fname = entry["file"]
        doc_id = Path(fname).stem
        text_url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/texts/{fname}"
        raw = _fetch_text(text_url)
        tokens: list[Token] = []
        lines: list[list[int]] = []
        for raw_line in raw.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            line_no = len(lines)
            idxs: list[int] = []
            for tok in tokenize(stripped):
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
                    )
                )
                idxs.append(pos)
            if idxs:
                lines.append(idxs)
        if not tokens:
            continue
        notes = [f"Register: {entry.get('register', '')}", f"License: {entry.get('license', '')}"]
        if entry.get("title_el"):
            notes.insert(0, f"Greek title: {entry['title_el']}")
        docs.append(
            Document(
                id=doc_id,
                script_id="greek",
                tokens=tokens,
                lines=lines,
                meta=DocumentMeta(
                    name=entry.get("title", doc_id),
                    period=entry.get("date", "Byzantine / Early Modern"),
                    notes=tuple(n for n in notes if n),
                ),
            )
        )
        print(f"  {doc_id:28s} {len(lines):5d} lines, {len(tokens):6d} tokens")

    prov = Provenance(
        source="Byzantine and Early Modern Vernacular Greek Corpus (12th–17th c.)",
        license="Public Domain / CC BY-SA 3.0 (Wikisource & Kalonaros 1940; compilation metadata MIT, Francisco Riordan)",
        url=f"https://github.com/{REPO}/tree/{COMMIT}",
        edition_fidelity="normalized",
    )
    return Corpus(docs, provenance=prov, script_id="greek")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build byzantine-corpus.json.gz.")
    ap.add_argument("-o", "--output", type=Path, default=Path("byzantine-corpus.json.gz"))
    args = ap.parse_args()
    corpus = build()
    payload = corpus.to_json().encode("utf-8")  # type: ignore[attr-defined]
    with args.output.open("wb") as raw_f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_f, compresslevel=9, mtime=0) as gz:
            gz.write(payload)
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
