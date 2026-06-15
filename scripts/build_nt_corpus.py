"""Build the Greek New Testament corpus asset from Nestle1904 morphology.

Source: biblicalhumanities/Nestle1904 ``morph/Nestle1904.csv`` — the Nestle 1904
Greek NT (Diego Santos's edition; base text public domain) carrying, per word, a
lemma, a Robinson-style morphological parse, a Strong's number, and a normalized
form. The morphology, lemmas, and Strong's numbers are dedicated to the public
domain under **CC0 1.0** (see ``morph/README.md`` upstream).

CC0 imposes no attribution or share-alike obligation, so — unlike the CC BY-NC-SA
DAMOS/SigLA assets — this corpus *may* be redistributed and even bundled. pyaegean
hosts the full 27-book asset as a release download (fetched to cache by
``aegean.scripts.greek.nt.load_nt``) and bundles a single book as an offline sample.

Output (``nt-corpus.json``, plain UTF-8 JSON — never gzipped: the footprint guard
rejects ``.gz`` in the wheel):

    {"_meta": {...}, "documents": [{"id": "John 1", "book": "John", "chapter": 1,
      "name": "Gospel of John 1",
      "tokens": [{"t": surface, "v": verse, "lemma": ..., "morph": ...,
                  "strongs": ..., "norm": normalized}, ...]}, ...]}

Usage:
    python scripts/build_nt_corpus.py --out nt-corpus.json
    python scripts/build_nt_corpus.py --sample John --sample-out src/aegean/data/bundled/greek/nt_sample.json
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

REPO = "biblicalhumanities/Nestle1904"
CSV_PATH = "morph/Nestle1904.csv"
SOURCE_URL = f"https://github.com/{REPO}"
LICENSE = "CC0-1.0 (morphology, lemmas, Strong's); base Greek text public domain"
ATTRIBUTION = (
    "Nestle 1904 Greek New Testament (Eberhard Nestle; digital text by Diego Santos). "
    "Morphology, lemmatization, and Strong's numbers by Ulrik Sandborg-Petersen, largely "
    "derived from Maurice A. Robinson's analysis. Dedicated to the public domain (CC0)."
)
CITE = (
    "Nestle, E. (1904). Novum Testamentum Graece (Nestle 1904). Morphology/lemmatization "
    "(CC0) via biblicalhumanities/Nestle1904."
)

# The 27 NT books in canonical order, OSIS id -> full English name (for Document.name).
BOOKS: dict[str, str] = {
    "Matt": "Matthew", "Mark": "Mark", "Luke": "Luke", "John": "John", "Acts": "Acts",
    "Rom": "Romans", "1Cor": "1 Corinthians", "2Cor": "2 Corinthians", "Gal": "Galatians",
    "Eph": "Ephesians", "Phil": "Philippians", "Col": "Colossians",
    "1Thess": "1 Thessalonians", "2Thess": "2 Thessalonians", "1Tim": "1 Timothy",
    "2Tim": "2 Timothy", "Titus": "Titus", "Phlm": "Philemon", "Heb": "Hebrews",
    "Jas": "James", "1Pet": "1 Peter", "2Pet": "2 Peter", "1John": "1 John",
    "2John": "2 John", "3John": "3 John", "Jude": "Jude", "Rev": "Revelation",
}


def _resolve_commit(ref: str) -> str:
    """Resolve a branch/tag to a commit SHA so the asset records an immutable source."""
    url = f"https://api.github.com/repos/{REPO}/commits/{ref}"
    req = urllib.request.Request(url, headers={"User-Agent": "pyaegean-build"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (trusted host)
        return str(json.load(resp)["sha"])


def _fetch_csv(commit: str) -> str:
    url = f"https://raw.githubusercontent.com/{REPO}/{commit}/{CSV_PATH}"
    req = urllib.request.Request(url, headers={"User-Agent": "pyaegean-build"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (trusted host)
        return resp.read().decode("utf-8-sig")  # utf-8-sig strips the BOM


def _parse_rows(csv_text: str) -> list[dict[str, Any]]:
    """One dict per token row. Handles CRLF, the trailing tab, and Strong's '&TVM'."""
    rows: list[dict[str, Any]] = []
    lines = csv_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for raw in lines[1:]:  # skip the header
        if not raw.strip():
            continue
        f = raw.split("\t")
        if len(f) < 7:
            continue
        bcv, surface, _func_morph, form_morph, strongs, lemma, normalized = f[:7]
        book, _, rest = bcv.partition(" ")
        chap_s, _, verse_s = rest.partition(":")
        strong = strongs.split("&", 1)[0].strip()  # drop the verb TVM suffix
        rows.append({
            "book": book,
            "chapter": int(chap_s),
            "verse": int(verse_s),
            "t": surface,
            "lemma": lemma,
            "morph": form_morph,
            "strongs": strong,
            "norm": normalized,
        })
    return rows


def _to_documents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group rows into one Document record per (book, chapter), in source order."""
    docs: list[dict[str, Any]] = []
    cur_key: tuple[str, int] | None = None
    cur: dict[str, Any] | None = None
    for r in rows:
        key = (r["book"], r["chapter"])
        if key != cur_key:
            book, chap = key
            cur = {
                "id": f"{book} {chap}",
                "book": book,
                "chapter": chap,
                "name": f"{BOOKS.get(book, book)} {chap}",
                "tokens": [],
            }
            docs.append(cur)
            cur_key = key
        assert cur is not None
        cur["tokens"].append({
            "t": r["t"], "v": r["verse"], "lemma": r["lemma"],
            "morph": r["morph"], "strongs": r["strongs"], "norm": r["norm"],
        })
    return docs


def _write(path: Path, documents: list[dict[str, Any]], commit: str, name: str) -> None:
    out = {
        "_meta": {
            "name": name,
            "version": 1,
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "cite": CITE,
            "source_url": SOURCE_URL,
            "source_commit": commit,
            "generated": time.strftime("%Y-%m-%d"),
            "document_count": len(documents),
            "token_count": sum(len(d["tokens"]) for d in documents),
            "note": (
                "Greek New Testament (Nestle 1904) with per-token lemma/morph/Strong's "
                "(CC0). The full corpus is fetched on demand; one book is bundled as an "
                "offline sample. Provenance and license travel with the corpus."
            ),
        },
        "documents": documents,
    }
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    size = path.stat().st_size / 1_000_000
    print(f"wrote {path}  ({len(documents)} docs, {out['_meta']['token_count']} tokens, {size:.2f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the Greek NT corpus asset from Nestle1904.")
    ap.add_argument("--ref", default="master", help="branch/tag to pin (resolved to a commit SHA)")
    ap.add_argument("--out", type=Path, default=Path("nt-corpus.json"),
                    help="full 27-book asset path")
    ap.add_argument("--sample", default="", help="OSIS book id to also emit as a bundled sample (e.g. Phlm)")
    ap.add_argument("--sample-out", type=Path,
                    default=Path("src/aegean/data/bundled/greek/nt_sample.json"))
    args = ap.parse_args()

    commit = _resolve_commit(args.ref)
    print(f"{REPO}@{commit}")
    rows = _parse_rows(_fetch_csv(commit))
    docs = _to_documents(rows)
    _write(args.out, docs, commit, "Nestle 1904 Greek New Testament")

    if args.sample:
        sample = [d for d in docs if d["book"] == args.sample]
        if not sample:
            raise SystemExit(f"--sample {args.sample!r} matched no book; valid OSIS ids: {', '.join(BOOKS)}")
        args.sample_out.parent.mkdir(parents=True, exist_ok=True)
        _write(args.sample_out, sample, commit, f"Nestle 1904 — {BOOKS.get(args.sample, args.sample)} (offline sample)")


if __name__ == "__main__":
    main()
