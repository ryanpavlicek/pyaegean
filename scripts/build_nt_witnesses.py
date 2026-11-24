"""Build the Early Greek NT Manuscript Witnesses release asset (``nt-witnesses.json.gz``).

Source: ``Center-for-New-Testament-Restoration/transcriptions`` (``class 1/``,
CC BY-SA 4.0, copyright Alan Bunning / CNTR).

Includes 13 landmark early Greek New Testament manuscripts (2nd–5th century CE):
- Six major uncial codices: Sinaiticus (``01`` / ℵ), Alexandrinus (``02`` / A),
  Vaticanus (``03`` / B), Ephraemi Rescriptus (``04`` / C), Bezae (``05`` / D),
  and Washingtonianus (``032`` / W).
- Seven landmark early papyri: ``P45``, ``P46``, ``P47``, ``P52`` (Rylands),
  ``P66``, ``P72``, and ``P75``.

Preserves CNTR's Manuscript Encoding Specification (MES) diplomatic text (including
*nomina sacra* ``=ιυ``/``=χυ``/``=θσ``, original vs. corrector hands ``x{...}``/``{...}``,
line breaks ``/``, damaged/reconstructed characters ``%``/``^``, and lacunae ``~``),
which ``aegean.biblical`` renders in both diplomatic and readable/expanded forms.

Usage:
    python scripts/build_nt_witnesses.py --out nt-witnesses.json.gz
"""

from __future__ import annotations

import argparse
import gzip
import json
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CNTR_REPO = "Center-for-New-Testament-Restoration/transcriptions"
CNTR_COMMIT = "4e743a41a4b2ca010ece53229cd272aa59b1efe6"

LICENSE = "CC BY-SA 4.0 (Center for New Testament Restoration / Alan Bunning)"
ATTRIBUTION = (
    "Early Greek New Testament electronic manuscript transcriptions from the Center for "
    "New Testament Restoration (CNTR, Alan Bunning, https://greekcntr.org), licensed "
    "under CC BY-SA 4.0."
)

_CNTR_NUM_TO_OSIS: dict[int, str] = {
    40: "Matt", 41: "Mark", 42: "Luke", 43: "John", 44: "Acts",
    45: "Rom", 46: "1Cor", 47: "2Cor", 48: "Gal", 49: "Eph",
    50: "Phil", 51: "Col", 52: "1Thess", 53: "2Thess", 54: "1Tim",
    55: "2Tim", 56: "Titus", 57: "Phlm", 58: "Heb", 59: "Jas",
    60: "1Pet", 61: "2Pet", 62: "1John", 63: "2John", 64: "3John",
    65: "Jude", 66: "Rev",
}

WITNESS_SPECS: tuple[dict[str, str], ...] = (
    {
        "siglum": "01",
        "alias": "ℵ",
        "name": "Codex Sinaiticus",
        "century": "4th c. CE",
        "kind": "uncial",
        "text_type": "Alexandrian (Western in John 1:1–8:38)",
        "repository": "British Library (London) / Leipzig / St. Petersburg / Sinai",
    },
    {
        "siglum": "02",
        "alias": "A",
        "name": "Codex Alexandrinus",
        "century": "5th c. CE",
        "kind": "uncial",
        "text_type": "Byzantine in Gospels; Alexandrian in Acts–Revelation",
        "repository": "British Library (London)",
    },
    {
        "siglum": "03",
        "alias": "B",
        "name": "Codex Vaticanus",
        "century": "4th c. CE",
        "kind": "uncial",
        "text_type": "Alexandrian",
        "repository": "Biblioteca Apostolica Vaticana (Rome)",
    },
    {
        "siglum": "04",
        "alias": "C",
        "name": "Codex Ephraemi Rescriptus",
        "century": "5th c. CE",
        "kind": "uncial",
        "text_type": "Mixed / Alexandrian–Byzantine palimpsest",
        "repository": "Bibliothèque nationale de France (Paris)",
    },
    {
        "siglum": "05",
        "alias": "D",
        "name": "Codex Bezae Cantabrigiensis",
        "century": "5th c. CE",
        "kind": "uncial",
        "text_type": "Western (Greek–Latin bilingual)",
        "repository": "Cambridge University Library",
    },
    {
        "siglum": "032",
        "alias": "W",
        "name": "Codex Washingtonianus (Freer Gospels)",
        "century": "4th/5th c. CE",
        "kind": "uncial",
        "text_type": "Block-mixed (Alexandrian, Western, Byzantine, Caesarean)",
        "repository": "Smithsonian Institution, Freer Gallery of Art (Washington, DC)",
    },
    {
        "siglum": "P45",
        "alias": "𝔓45",
        "name": "Papyrus 45 (Chester Beatty I)",
        "century": "3rd c. CE",
        "kind": "papyrus",
        "text_type": "Early Alexandrian / Caesarean-leaning (Gospels & Acts)",
        "repository": "Chester Beatty Library (Dublin) / ÖNB (Vienna)",
    },
    {
        "siglum": "P46",
        "alias": "𝔓46",
        "name": "Papyrus 46 (Chester Beatty II)",
        "century": "c. 200 CE",
        "kind": "papyrus",
        "text_type": "Early Alexandrian (Pauline Epistles & Hebrews)",
        "repository": "Chester Beatty Library (Dublin) / Univ. of Michigan",
    },
    {
        "siglum": "P47",
        "alias": "𝔓47",
        "name": "Papyrus 47 (Chester Beatty III)",
        "century": "3rd c. CE",
        "kind": "papyrus",
        "text_type": "Early Alexandrian (Revelation 9–17)",
        "repository": "Chester Beatty Library (Dublin)",
    },
    {
        "siglum": "P52",
        "alias": "𝔓52",
        "name": "Papyrus 52 (Rylands Library Papyrus P52)",
        "century": "2nd c. CE",
        "kind": "papyrus",
        "text_type": "Earliest extant NT fragment (John 18:31–33, 37–38)",
        "repository": "John Rylands Library (Manchester)",
    },
    {
        "siglum": "P66",
        "alias": "𝔓66",
        "name": "Papyrus 66 (Bodmer II)",
        "century": "c. 200 CE",
        "kind": "papyrus",
        "text_type": "Early Alexandrian with Western readings (Gospel of John)",
        "repository": "Fondation Martin Bodmer (Cologny)",
    },
    {
        "siglum": "P72",
        "alias": "𝔓72",
        "name": "Papyrus 72 (Bodmer VII–VIII)",
        "century": "3rd/4th c. CE",
        "kind": "papyrus",
        "text_type": "Early Alexandrian (1–2 Peter & Jude)",
        "repository": "Biblioteca Apostolica Vaticana (Rome)",
    },
    {
        "siglum": "P75",
        "alias": "𝔓75",
        "name": "Papyrus 75 (Bodmer XIV–XV)",
        "century": "early 3rd c. CE",
        "kind": "papyrus",
        "text_type": "Strict Alexandrian, close to Codex Vaticanus (Luke & John)",
        "repository": "Biblioteca Apostolica Vaticana (Rome)",
    },
)


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "pyaegean-build"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        return resp.read().decode("utf-8-sig")


def _parse_witness(text: str) -> dict[str, dict[str, str]]:
    books: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        code, _, body = line.partition(" ")
        if len(code) < 8 or not code[:8].isdigit():
            continue
        bnum = int(code[0:2])
        chap = int(code[2:5])
        verse = int(code[5:8])
        osis = _CNTR_NUM_TO_OSIS.get(bnum)
        if osis is None:
            continue
        body = unicodedata.normalize("NFC", body.strip())
        if not body:
            continue
        books.setdefault(osis, {})[f"{chap}.{verse}"] = body
    return books


def build() -> dict[str, Any]:
    witnesses: dict[str, dict[str, Any]] = {}
    for spec in WITNESS_SPECS:
        siglum = spec["siglum"]
        rel = urllib.parse.quote(f"class 1/{siglum}.txt")
        url = f"https://raw.githubusercontent.com/{CNTR_REPO}/{CNTR_COMMIT}/{rel}"
        print(f"Fetching {siglum} ({spec['name']}) ...")
        books = _parse_witness(_fetch_text(url))
        verse_count = sum(len(v) for v in books.values())
        print(f"  {siglum}: {len(books)} books, {verse_count} verses")
        witnesses[siglum] = {
            "_info": {
                **spec,
                "books": list(books),
                "verse_count": verse_count,
            },
            "books": books,
        }
    return {
        "_meta": {
            "name": "Early Greek New Testament Manuscript Witnesses (CNTR Class 1)",
            "version": 1,
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "source_url": f"https://github.com/{CNTR_REPO}",
            "source_commit": CNTR_COMMIT,
            "witness_count": len(witnesses),
            "verse_counts": {s: w["_info"]["verse_count"] for s, w in witnesses.items()},
        },
        "witnesses": witnesses,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build nt-witnesses.json.gz release asset.")
    ap.add_argument("--out", type=Path, default=Path("nt-witnesses.json.gz"))
    args = ap.parse_args()
    payload = build()
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with args.out.open("wb") as raw_f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_f, compresslevel=9, mtime=0) as f:
            f.write(raw)
    mb = args.out.stat().st_size / 1_000_000
    print(f"wrote {args.out} ({len(payload['witnesses'])} witnesses, {mb:.2f} MB gz)")


if __name__ == "__main__":
    main()
