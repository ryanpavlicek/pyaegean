"""Build the multi-edition Greek New Testament release asset (``nt-editions.json.gz``).

Combines four open-licensed Greek New Testament editions alongside the existing
``nt-corpus`` (Nestle 1904, CC0):

- **SBLGNT** (``morphgnt/sblgnt``, SBLGNT text CC BY 4.0, MorphGNT CC BY-SA 3.0)
- **SRGNT** — Statistical Restoration GNT (``Center-for-New-Testament-Restoration/SR``, CC BY 4.0)
- **TR** — King James Textus Receptus (``Center-for-New-Testament-Restoration/KJTR``, CC BY 4.0)
- **BYZ** — Robinson–Pierpont Byzantine Majority Text (``byztxt/byzantine-majority-text``, Public Domain)

Output schema (compact, NFC-normalized Greek per verse, grouped by edition & OSIS book):

    {
      "_meta": { ... },
      "editions": {
        "sblgnt": {"_info": {...}, "books": {"Matt": {"1.1": "...", ...}, ...}},
        "srgnt":  {"_info": {...}, "books": {...}},
        "byz":    {"_info": {...}, "books": {...}},
        "tr":     {"_info": {...}, "books": {...}}
      }
    }

Usage:
    python scripts/build_nt_editions.py --out nt-editions.json.gz
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any

SBL_REPO = "morphgnt/sblgnt"
SBL_COMMIT = "aaed91e57c8e4a8dc9a2383e129ca5e75fe6393d"

SR_REPO = "Center-for-New-Testament-Restoration/SR"
SR_COMMIT = "4be18e67c6870388d317d38d2b10a70e8b5e8775"

TR_REPO = "Center-for-New-Testament-Restoration/KJTR"
TR_COMMIT = "2af135d09bc1d87c0b049361256210eb312e72d1"

BYZ_REPO = "byztxt/byzantine-majority-text"
BYZ_COMMIT = "788ffe7c909e4d9c564ebed7083e93dd13d10b7c"

LICENSE = (
    "CC BY-SA 3.0 / CC BY 4.0 / Public Domain (SBLGNT CC BY 4.0 + MorphGNT CC BY-SA 3.0; "
    "CNTR Statistical Restoration GNT & KJTR CC BY 4.0; Robinson-Pierpont Byzantine Majority "
    "Text Public Domain)"
)
ATTRIBUTION = (
    "Multi-edition Greek New Testament bundle: SBL Greek New Testament (Michael W. Holmes, "
    "SBL/Logos, CC BY 4.0; MorphGNT CC BY-SA 3.0); Statistical Restoration Greek New Testament "
    "and Textus Receptus (Alan Bunning / Center for New Testament Restoration, CC BY 4.0); "
    "Robinson-Pierpont Byzantine Majority Textform (Public Domain)."
)

# Canonical 27 books: (OSIS, SBL file, BYZ file, CNTR 2-digit book number 40..66)
_BOOK_TABLE: tuple[tuple[str, str, str, int], ...] = (
    ("Matt", "61-Mt-morphgnt.txt", "MAT.csv", 40),
    ("Mark", "62-Mk-morphgnt.txt", "MAR.csv", 41),
    ("Luke", "63-Lk-morphgnt.txt", "LUK.csv", 42),
    ("John", "64-Jn-morphgnt.txt", "JOH.csv", 43),
    ("Acts", "65-Ac-morphgnt.txt", "ACT.csv", 44),
    ("Rom", "66-Ro-morphgnt.txt", "ROM.csv", 45),
    ("1Cor", "67-1Co-morphgnt.txt", "1CO.csv", 46),
    ("2Cor", "68-2Co-morphgnt.txt", "2CO.csv", 47),
    ("Gal", "69-Ga-morphgnt.txt", "GAL.csv", 48),
    ("Eph", "70-Eph-morphgnt.txt", "EPH.csv", 49),
    ("Phil", "71-Php-morphgnt.txt", "PHP.csv", 50),
    ("Col", "72-Col-morphgnt.txt", "COL.csv", 51),
    ("1Thess", "73-1Th-morphgnt.txt", "1TH.csv", 52),
    ("2Thess", "74-2Th-morphgnt.txt", "2TH.csv", 53),
    ("1Tim", "75-1Ti-morphgnt.txt", "1TI.csv", 54),
    ("2Tim", "76-2Ti-morphgnt.txt", "2TI.csv", 55),
    ("Titus", "77-Tit-morphgnt.txt", "TIT.csv", 56),
    ("Phlm", "78-Phm-morphgnt.txt", "PHM.csv", 57),
    ("Heb", "79-Heb-morphgnt.txt", "HEB.csv", 58),
    ("Jas", "80-Jas-morphgnt.txt", "JAM.csv", 59),
    ("1Pet", "81-1Pe-morphgnt.txt", "1PE.csv", 60),
    ("2Pet", "82-2Pe-morphgnt.txt", "2PE.csv", 61),
    ("1John", "83-1Jn-morphgnt.txt", "1JO.csv", 62),
    ("2John", "84-2Jn-morphgnt.txt", "2JO.csv", 63),
    ("3John", "85-3Jn-morphgnt.txt", "3JO.csv", 64),
    ("Jude", "86-Jud-morphgnt.txt", "JUD.csv", 65),
    ("Rev", "87-Re-morphgnt.txt", "REV.csv", 66),
)
_CNTR_NUM_TO_OSIS: dict[int, str] = {num: osis for osis, _, _, num in _BOOK_TABLE}

# CNTR Modern column uses ¶ (paragraph), ˚ (nomen sacrum marker), and occasionally []/•
_CNTR_STRIP_RE = re.compile(r"[¶˚]")
_WS_RE = re.compile(r"\s+")


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "pyaegean-build"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        return resp.read().decode("utf-8-sig")


def _build_sblgnt() -> dict[str, dict[str, str]]:
    print(f"Fetching SBLGNT ({SBL_REPO}@{SBL_COMMIT[:10]}) ...")
    books: dict[str, dict[str, str]] = {}
    for osis, fname, _, _ in _BOOK_TABLE:
        url = f"https://raw.githubusercontent.com/{SBL_REPO}/{SBL_COMMIT}/{fname}"
        verses: dict[str, list[str]] = {}
        for line in _fetch_text(url).splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            bcv = parts[0]
            chap = int(bcv[2:4])
            verse = int(bcv[4:6])
            surface = unicodedata.normalize("NFC", parts[3])
            verses.setdefault(f"{chap}.{verse}", []).append(surface)
        books[osis] = {k: " ".join(v) for k, v in verses.items()}
    total = sum(len(v) for v in books.values())
    print(f"  SBLGNT: {len(books)} books, {total} verses")
    return books


def _build_cntr_tsv(repo: str, commit: str, filename: str, label: str) -> dict[str, dict[str, str]]:
    print(f"Fetching {label} ({repo}@{commit[:10]}) ...")
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{filename}"
    text = _fetch_text(url)
    books: dict[str, dict[str, list[str]]] = {osis: {} for osis, _, _, _ in _BOOK_TABLE}
    for i, line in enumerate(text.splitlines()):
        if i == 0 or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        vcode = parts[0].strip()
        if len(vcode) < 8 or not vcode[:8].isdigit():
            continue
        bnum = int(vcode[0:2])
        chap = int(vcode[2:5])
        verse = int(vcode[5:8])
        osis = _CNTR_NUM_TO_OSIS.get(bnum)
        if osis is None:
            continue
        tok = _CNTR_STRIP_RE.sub("", parts[1]).strip()
        if not tok:
            continue
        books[osis].setdefault(f"{chap}.{verse}", []).append(unicodedata.normalize("NFC", tok))
    out = {osis: {k: " ".join(v) for k, v in vd.items()} for osis, vd in books.items()}
    total = sum(len(v) for v in out.values())
    print(f"  {label}: {len(out)} books, {total} verses")
    return out


def _build_byz() -> dict[str, dict[str, str]]:
    print(f"Fetching Byzantine Majority Text ({BYZ_REPO}@{BYZ_COMMIT[:10]}) ...")
    books: dict[str, dict[str, str]] = {}
    for osis, _, fname, _ in _BOOK_TABLE:
        url = (
            f"https://raw.githubusercontent.com/{BYZ_REPO}/{BYZ_COMMIT}/"
            f"csv-unicode/ccat/no-variants/{fname}"
        )
        reader = csv.DictReader(io.StringIO(_fetch_text(url)))
        verses: dict[str, str] = {}
        for row in reader:
            chap = int(row["chapter"])
            verse = int(row["verse"])
            txt = _WS_RE.sub(" ", unicodedata.normalize("NFC", row["text"].strip()))
            verses[f"{chap}.{verse}"] = txt
        books[osis] = verses
    total = sum(len(v) for v in books.values())
    print(f"  BYZ: {len(books)} books, {total} verses")
    return books


def build() -> dict[str, Any]:
    sbl = _build_sblgnt()
    sr = _build_cntr_tsv(SR_REPO, SR_COMMIT, "SR.tsv", "SRGNT")
    byz = _build_byz()
    tr = _build_cntr_tsv(TR_REPO, TR_COMMIT, "KJTR.tsv", "TR")

    editions = {
        "sblgnt": {
            "_info": {
                "name": "SBL Greek New Testament (2010)",
                "editor": "Michael W. Holmes (SBL / Logos)",
                "license": "CC BY 4.0 (SBLGNT text); CC BY-SA 3.0 (MorphGNT)",
                "source": f"https://github.com/{SBL_REPO}@{SBL_COMMIT}",
            },
            "books": sbl,
        },
        "srgnt": {
            "_info": {
                "name": "Statistical Restoration Greek New Testament",
                "editor": "Alan Bunning (Center for New Testament Restoration)",
                "license": "CC BY 4.0",
                "source": f"https://github.com/{SR_REPO}@{SR_COMMIT}",
            },
            "books": sr,
        },
        "byz": {
            "_info": {
                "name": "Robinson–Pierpont Byzantine Majority Textform",
                "editor": "Maurice A. Robinson & William G. Pierpont",
                "license": "Public Domain",
                "source": f"https://github.com/{BYZ_REPO}@{BYZ_COMMIT}",
            },
            "books": byz,
        },
        "tr": {
            "_info": {
                "name": "Textus Receptus (King James Greek Underlying Text)",
                "editor": "Center for New Testament Restoration (KJTR)",
                "license": "CC BY 4.0",
                "source": f"https://github.com/{TR_REPO}@{TR_COMMIT}",
            },
            "books": tr,
        },
    }
    return {
        "_meta": {
            "name": "Multi-Edition Greek New Testament (SBLGNT, SRGNT, Byzantine, Textus Receptus)",
            "version": 1,
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "edition_ids": list(editions),
            "verse_counts": {
                eid: sum(len(b) for b in ed["books"].values())
                for eid, ed in editions.items()
            },
        },
        "editions": editions,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build nt-editions.json.gz release asset.")
    ap.add_argument("--out", type=Path, default=Path("nt-editions.json.gz"))
    args = ap.parse_args()
    payload = build()
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with args.out.open("wb") as raw_f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_f, compresslevel=9, mtime=0) as f:
            f.write(raw)
    mb = args.out.stat().st_size / 1_000_000
    print(f"wrote {args.out} ({payload['_meta']['verse_counts']}, {mb:.2f} MB gz)")


if __name__ == "__main__":
    main()
