"""Build the Open Apostolic Fathers Greek corpus (``apostolic-fathers-corpus.json.gz``).

Sources all 15 twice-independently hand-corrected Greek Apostolic Fathers texts from
``jtauber/apostolic-fathers`` (edited by James Tauber & Seumas Macdonald, Zenodo
10.5281/zenodo.2555673; **CC BY-SA 4.0**):

- 1 Clement, 2 Clement
- Ignatius (Ephesians, Magnesians, Trallians, Romans, Philadelphians, Smyrnaeans, Polycarp)
- Polycarp to the Philippians, Didache, Epistle of Barnabas, Shepherd of Hermas,
  Martyrdom of Polycarp, Epistle to Diognetus

Output is a standard gzipped pyaegean ``Corpus`` JSON with one ``Document`` per work and
section/verse-aligned lines (``ref`` annotations on every token).

Usage:
    python scripts/build_apostolic_fathers_corpus.py -o apostolic-fathers-corpus.json.gz
"""

from __future__ import annotations

import argparse
import gzip
import sys
import unicodedata
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

REPO = "jtauber/apostolic-fathers"
COMMIT = "a07f9207902d2a7a88aa3e7c8fb3671d7ef6f0ff"

# (doc_id, filename, author, title, period)
WORKS: tuple[tuple[str, str, str, str, str], ...] = (
    ("1Clem", "001-i_clement.txt", "Clement of Rome", "1 Clement (First Epistle to the Corinthians)", "c. 96 CE"),
    ("2Clem", "002-ii_clement.txt", "Pseudo-Clement", "2 Clement", "2nd c. CE"),
    ("IgnEph", "003-ignatius-ephesians.txt", "Ignatius of Antioch", "Epistle to the Ephesians", "c. 110 CE"),
    ("IgnMagn", "004-ignatius-magnesians.txt", "Ignatius of Antioch", "Epistle to the Magnesians", "c. 110 CE"),
    ("IgnTrall", "005-ignatius-trallians.txt", "Ignatius of Antioch", "Epistle to the Trallians", "c. 110 CE"),
    ("IgnRom", "006-ignatius-romans.txt", "Ignatius of Antioch", "Epistle to the Romans", "c. 110 CE"),
    ("IgnPhld", "007-ignatius-philadelphians.txt", "Ignatius of Antioch", "Epistle to the Philadelphians", "c. 110 CE"),
    ("IgnSmyrn", "008-ignatius-smyrnaeans.txt", "Ignatius of Antioch", "Epistle to the Smyrnaeans", "c. 110 CE"),
    ("IgnPol", "009-ignatius-polycarp.txt", "Ignatius of Antioch", "Epistle to Polycarp", "c. 110 CE"),
    ("PolPhil", "010-polycarp-philippians.txt", "Polycarp of Smyrna", "Epistle to the Philippians", "c. 110–140 CE"),
    ("Did", "011-didache.txt", "Anonymous", "Didache (Teaching of the Twelve Apostles)", "late 1st / early 2nd c. CE"),
    ("Barn", "012-barnabas.txt", "Pseudo-Barnabas", "Epistle of Barnabas", "c. 70–132 CE"),
    ("Herm", "013-shepherd.txt", "Hermas", "The Shepherd of Hermas", "early 2nd c. CE"),
    ("MartPol", "014-martyrdom.txt", "Anonymous", "Martyrdom of Polycarp", "c. 155–160 CE"),
    ("Diogn", "015-diognetus.txt", "Anonymous", "Epistle to Diognetus", "2nd c. CE"),
)


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "pyaegean-build"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        return resp.read().decode("utf-8-sig")


def build() -> object:
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, DocumentMeta, Token, TokenKind
    from aegean.core.provenance import Provenance
    from aegean.greek.tokenize import tokenize

    docs: list[Document] = []
    for doc_id, fname, author, title, period in WORKS:
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/texts/{fname}"
        raw = _fetch_text(url)
        tokens: list[Token] = []
        lines: list[list[int]] = []
        for raw_line in raw.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            parts = stripped.split(None, 1)
            if len(parts) < 2:
                continue
            ref_str, text = parts[0], parts[1]
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
                        annotations={"ref": f"{doc_id}.{ref_str}"},
                    )
                )
                idxs.append(pos)
            if idxs:
                lines.append(idxs)
        docs.append(
            Document(
                id=doc_id,
                script_id="greek",
                tokens=tokens,
                lines=lines,
                meta=DocumentMeta(
                    name=f"{author}: {title}",
                    period=period,
                    notes=(f"Author: {author}", f"Source: texts/{fname}"),
                ),
            )
        )
        print(f"  {doc_id:10s} {len(lines):4d} sections, {len(tokens):6d} tokens")

    prov = Provenance(
        source="Open Apostolic Fathers (Tauber & Macdonald, based on Kirsopp Lake)",
        license="CC BY-SA 4.0 (James Tauber & Seumas Macdonald, Open Apostolic Fathers, Zenodo 10.5281/zenodo.2555673)",
        url=f"https://github.com/{REPO}/tree/{COMMIT}",
        citation=(
            "Tauber, J., & Macdonald, S. (2019). Open Apostolic Fathers (Version 1.0). "
            "Zenodo. https://doi.org/10.5281/zenodo.2555673"
        ),
        edition_fidelity="normalized",
    )
    return Corpus(docs, provenance=prov, script_id="greek")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build apostolic-fathers-corpus.json.gz.")
    ap.add_argument("-o", "--output", type=Path, default=Path("apostolic-fathers-corpus.json.gz"))
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
