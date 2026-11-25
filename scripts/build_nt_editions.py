"""Build the multi-edition Greek New Testament release asset (``nt-editions.json.gz``).

Combines eight open-licensed Greek New Testament editions alongside the existing
``nt-corpus`` (Nestle 1904, CC0):

- **SBLGNT** (``morphgnt/sblgnt``, SBLGNT text CC BY 4.0, MorphGNT CC BY-SA 3.0)
- **SRGNT** — Statistical Restoration GNT (``Center-for-New-Testament-Restoration/SR``, CC BY 4.0)
- **BHP** — Bunning Heuristic Prototype GNT (``Center-for-New-Testament-Restoration/BHP``, CC BY 4.0)
- **Tischendorf 8th** — *Editio Octava Critica Maior* (``morphgnt/tischendorf-data``, Public Domain)
- **Westcott–Hort (1881)** (``byztxt/greektext-westcott-hort``, Public Domain; unaccented Unicode)
- **BYZ** — Robinson–Pierpont Byzantine Majority Text (``byztxt/byzantine-majority-text``, Public Domain)
- **Antoniades (1904)** — Ecumenical Patriarchate Edition (``byztxt/greektext-antoniades``, Public Domain; unaccented Unicode)
- **TR** — King James Textus Receptus (``Center-for-New-Testament-Restoration/KJTR``, CC BY 4.0)

Output schema (compact, NFC-normalized Greek per verse, grouped by edition & OSIS book):

    {
      "_meta": { ... },
      "editions": {
        "sblgnt":     {"_info": {...}, "books": {"Matt": {"1.1": "...", ...}, ...}},
        "srgnt":      {"_info": {...}, "books": {...}},
        "bhp":        {"_info": {...}, "books": {...}},
        "tisch":      {"_info": {...}, "books": {...}},
        "wh":         {"_info": {...}, "books": {...}},
        "byz":        {"_info": {...}, "books": {...}},
        "antoniades": {"_info": {...}, "books": {...}},
        "tr":         {"_info": {...}, "books": {...}}
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

BHP_REPO = "Center-for-New-Testament-Restoration/BHP"
BHP_COMMIT = "4c8bd59073e54ea211d5fc21a11276d491373c1c"

TISCH_REPO = "morphgnt/tischendorf-data"
TISCH_COMMIT = "795f2f4f9fe7cb98bf8736b0c5cb59c43aa9c32e"

WH_REPO = "byztxt/greektext-westcott-hort"
WH_COMMIT = "91473892d7f36f1227e5c24f8d994d1da40311ad"

BYZ_REPO = "byztxt/byzantine-majority-text"
BYZ_COMMIT = "788ffe7c909e4d9c564ebed7083e93dd13d10b7c"

ANT_REPO = "byztxt/greektext-antoniades"
ANT_COMMIT = "0ed3c1fe2eb5e983a4729e255429a141dabf11ca"

TR_REPO = "Center-for-New-Testament-Restoration/KJTR"
TR_COMMIT = "2af135d09bc1d87c0b049361256210eb312e72d1"

LICENSE = (
    "CC BY-SA 3.0 / CC BY 4.0 / Public Domain (SBLGNT CC BY 4.0 + MorphGNT CC BY-SA 3.0; "
    "CNTR SRGNT, BHP & KJTR CC BY 4.0; Tischendorf 8th, Westcott-Hort 1881, Robinson-Pierpont "
    "Byzantine Majority Text & Antoniades 1904 Patriarchal Edition Public Domain)"
)
ATTRIBUTION = (
    "Multi-edition Greek New Testament bundle: SBL Greek New Testament (Michael W. Holmes, "
    "SBL/Logos, CC BY 4.0; MorphGNT CC BY-SA 3.0); Statistical Restoration GNT, Bunning Heuristic "
    "Prototype GNT, and Textus Receptus (Alan Bunning / Center for New Testament Restoration, "
    "CC BY 4.0); Tischendorf 8th Editio Octava Critica Maior (G. Clint Yale & Ulrik "
    "Sandborg-Petersen, Public Domain); Westcott-Hort 1881, Robinson-Pierpont Byzantine Majority "
    "Textform, and Antoniades 1904 Patriarchal Edition (Maurice A. Robinson et al., Public Domain)."
)

# Canonical 27 books: (OSIS, SBL file, BYZ file, CNTR 2-digit book number 40..66, Robinson/Tisch stem)
_BOOK_TABLE: tuple[tuple[str, str, str, int, str], ...] = (
    ("Matt", "61-Mt-morphgnt.txt", "MAT.csv", 40, "MT"),
    ("Mark", "62-Mk-morphgnt.txt", "MAR.csv", 41, "MR"),
    ("Luke", "63-Lk-morphgnt.txt", "LUK.csv", 42, "LU"),
    ("John", "64-Jn-morphgnt.txt", "JOH.csv", 43, "JOH"),
    ("Acts", "65-Ac-morphgnt.txt", "ACT.csv", 44, "AC"),
    ("Rom", "66-Ro-morphgnt.txt", "ROM.csv", 45, "RO"),
    ("1Cor", "67-1Co-morphgnt.txt", "1CO.csv", 46, "1CO"),
    ("2Cor", "68-2Co-morphgnt.txt", "2CO.csv", 47, "2CO"),
    ("Gal", "69-Ga-morphgnt.txt", "GAL.csv", 48, "GA"),
    ("Eph", "70-Eph-morphgnt.txt", "EPH.csv", 49, "EPH"),
    ("Phil", "71-Php-morphgnt.txt", "PHP.csv", 50, "PHP"),
    ("Col", "72-Col-morphgnt.txt", "COL.csv", 51, "COL"),
    ("1Thess", "73-1Th-morphgnt.txt", "1TH.csv", 52, "1TH"),
    ("2Thess", "74-2Th-morphgnt.txt", "2TH.csv", 53, "2TH"),
    ("1Tim", "75-1Ti-morphgnt.txt", "1TI.csv", 54, "1TI"),
    ("2Tim", "76-2Ti-morphgnt.txt", "2TI.csv", 55, "2TI"),
    ("Titus", "77-Tit-morphgnt.txt", "TIT.csv", 56, "TIT"),
    ("Phlm", "78-Phm-morphgnt.txt", "PHM.csv", 57, "PHM"),
    ("Heb", "79-Heb-morphgnt.txt", "HEB.csv", 58, "HEB"),
    ("Jas", "80-Jas-morphgnt.txt", "JAM.csv", 59, "JAS"),
    ("1Pet", "81-1Pe-morphgnt.txt", "1PE.csv", 60, "1PE"),
    ("2Pet", "82-2Pe-morphgnt.txt", "2PE.csv", 61, "2PE"),
    ("1John", "83-1Jn-morphgnt.txt", "1JO.csv", 62, "1JO"),
    ("2John", "84-2Jn-morphgnt.txt", "2JO.csv", 63, "2JO"),
    ("3John", "85-3Jn-morphgnt.txt", "3JO.csv", 64, "3JO"),
    ("Jude", "86-Jud-morphgnt.txt", "JUD.csv", 65, "JUDE"),
    ("Rev", "87-Re-morphgnt.txt", "REV.csv", 66, "RE"),
)
_CNTR_NUM_TO_OSIS: dict[int, str] = {num: osis for osis, _, _, num, _ in _BOOK_TABLE}

# CNTR Modern column uses ¶ (paragraph), ˚ (nomen sacrum marker)
_CNTR_STRIP_RE = re.compile(r"[¶˚]")
_WS_RE = re.compile(r"\s+")
_VERSE_LINE_RE = re.compile(r"^\s*(\d+):(\d+)\s+(.*)$")
_ROBINSON_BRACKET_RE = re.compile(r"\[[^\]]*\]")

# Maurice Robinson ASCII transliteration (used by byztxt/greektext-westcott-hort) -> Unicode Greek
_ROBINSON_MAP: dict[str, str] = {
    "a": "α", "b": "β", "g": "γ", "d": "δ", "e": "ε", "z": "ζ", "h": "η", "y": "θ",
    "i": "ι", "k": "κ", "l": "λ", "m": "μ", "n": "ν", "x": "ξ", "o": "ο", "p": "π",
    "r": "ρ", "s": "σ", "v": "ς", "t": "τ", "u": "υ", "f": "φ", "c": "χ", "q": "ψ",
    "w": "ω",
    "A": "Α", "B": "Β", "G": "Γ", "D": "Δ", "E": "Ε", "Z": "Ζ", "H": "Η", "Y": "Θ",
    "I": "Ι", "K": "Κ", "L": "Λ", "M": "Μ", "N": "Ν", "X": "Ξ", "O": "Ο", "P": "Π",
    "R": "Ρ", "S": "Σ", "V": "ς", "T": "Τ", "U": "Υ", "F": "Φ", "C": "Χ", "Q": "Ψ",
    "W": "Ω",
}


def _robinson_to_unicode(text: str) -> str:
    """Convert Maurice Robinson's ASCII Greek encoding to NFC Unicode Greek."""
    out = "".join(_ROBINSON_MAP.get(ch, ch) for ch in text)
    # Normalize any word-final medial sigma to final sigma.
    out = re.sub(r"σ(?=$|[\s.,;·:])", "ς", out)
    return _WS_RE.sub(" ", unicodedata.normalize("NFC", out)).strip()


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "pyaegean-build"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        return resp.read().decode("utf-8-sig")


def _build_sblgnt() -> dict[str, dict[str, str]]:
    print(f"Fetching SBLGNT ({SBL_REPO}@{SBL_COMMIT[:10]}) ...")
    books: dict[str, dict[str, str]] = {}
    for osis, fname, _, _, _ in _BOOK_TABLE:
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
    books: dict[str, dict[str, list[str]]] = {osis: {} for osis, _, _, _, _ in _BOOK_TABLE}
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


def _build_tischendorf() -> dict[str, dict[str, str]]:
    print(f"Fetching Tischendorf 8th ({TISCH_REPO}@{TISCH_COMMIT[:10]}) ...")
    books: dict[str, dict[str, str]] = {}
    for osis, _, _, _, stem in _BOOK_TABLE:
        url = (
            f"https://raw.githubusercontent.com/{TISCH_REPO}/{TISCH_COMMIT}/"
            f"word-per-line/2.8/Unicode/{stem}.txt"
        )
        verses: dict[str, list[str]] = {}
        for line in _fetch_text(url).splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            # Format: 1JO 1:1.1 C Ὃ Ὃ R-NSN ...
            cv_pos = parts[1].split(".")[0]
            if ":" not in cv_pos:
                continue
            chap_s, verse_s = cv_pos.split(":", 1)
            if not (chap_s.isdigit() and verse_s.isdigit()):
                continue
            surface = unicodedata.normalize("NFC", parts[3])
            verses.setdefault(f"{int(chap_s)}.{int(verse_s)}", []).append(surface)
        books[osis] = {k: " ".join(v) for k, v in verses.items()}
    total = sum(len(v) for v in books.values())
    print(f"  Tischendorf 8th: {len(books)} books, {total} verses")
    return books


def _parse_verse_wrapped_text(raw: str, *, robinson: bool = False) -> dict[str, str]:
    """Parse ``C:V text...`` with continuation lines into ``{'C.V': text}``."""
    verses: dict[str, list[str]] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        m = _VERSE_LINE_RE.match(line)
        if m:
            chap, verse, rest = int(m.group(1)), int(m.group(2)), m.group(3).strip()
            current_key = f"{chap}.{verse}"
            verses.setdefault(current_key, [])
            if rest:
                verses[current_key].append(rest)
        elif current_key is not None:
            stripped = line.strip()
            if stripped:
                verses[current_key].append(stripped)
    out: dict[str, str] = {}
    for key, chunks in verses.items():
        joined = " ".join(chunks)
        if robinson:
            # Strip Robinson textual-variant brackets such as ``[VAR ...]`` or keep words clean
            joined = _ROBINSON_BRACKET_RE.sub("", joined)
            joined = _robinson_to_unicode(joined)
        else:
            joined = _WS_RE.sub(" ", unicodedata.normalize("NFC", joined)).strip()
        if joined:
            out[key] = joined
    return out


def _build_wh() -> dict[str, dict[str, str]]:
    print(f"Fetching Westcott-Hort 1881 ({WH_REPO}@{WH_COMMIT[:10]}) ...")
    books: dict[str, dict[str, str]] = {}
    for osis, _, _, _, stem in _BOOK_TABLE:
        url = f"https://raw.githubusercontent.com/{WH_REPO}/{WH_COMMIT}/textonly/{stem}.WH"
        books[osis] = _parse_verse_wrapped_text(_fetch_text(url), robinson=True)
    total = sum(len(v) for v in books.values())
    print(f"  Westcott-Hort: {len(books)} books, {total} verses")
    return books


def _build_antoniades() -> dict[str, dict[str, str]]:
    print(f"Fetching Antoniades 1904 ({ANT_REPO}@{ANT_COMMIT[:10]}) ...")
    books: dict[str, dict[str, str]] = {}
    for osis, _, _, _, stem in _BOOK_TABLE:
        url = f"https://raw.githubusercontent.com/{ANT_REPO}/{ANT_COMMIT}/textonly/unicode/{stem}.txt"
        books[osis] = _parse_verse_wrapped_text(_fetch_text(url), robinson=False)
    total = sum(len(v) for v in books.values())
    print(f"  Antoniades 1904: {len(books)} books, {total} verses")
    return books


def _build_byz() -> dict[str, dict[str, str]]:
    print(f"Fetching Byzantine Majority Text ({BYZ_REPO}@{BYZ_COMMIT[:10]}) ...")
    books: dict[str, dict[str, str]] = {}
    for osis, _, fname, _, _ in _BOOK_TABLE:
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
    bhp = _build_cntr_tsv(BHP_REPO, BHP_COMMIT, "BHP.tsv", "BHP")
    tisch = _build_tischendorf()
    wh = _build_wh()
    byz = _build_byz()
    ant = _build_antoniades()
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
        "bhp": {
            "_info": {
                "name": "Bunning Heuristic Prototype Greek New Testament",
                "editor": "Alan Bunning (Center for New Testament Restoration)",
                "license": "CC BY 4.0",
                "source": f"https://github.com/{BHP_REPO}@{BHP_COMMIT}",
            },
            "books": bhp,
        },
        "tisch": {
            "_info": {
                "name": "Tischendorf 8th Edition (Editio Octava Critica Maior, 1869–1872)",
                "editor": "Constantin von Tischendorf (digital text G. Clint Yale & Ulrik Sandborg-Petersen)",
                "license": "Public Domain",
                "source": f"https://github.com/{TISCH_REPO}@{TISCH_COMMIT}",
            },
            "books": tisch,
        },
        "wh": {
            "_info": {
                "name": "Westcott–Hort Greek New Testament (1881, unaccented Unicode)",
                "editor": "Brooke Foss Westcott & Fenton John Anthony Hort (digital text Maurice A. Robinson)",
                "license": "Public Domain",
                "source": f"https://github.com/{WH_REPO}@{WH_COMMIT}",
            },
            "books": wh,
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
        "antoniades": {
            "_info": {
                "name": "Antoniades 1904 Patriarchal Edition (Ecumenical Patriarchate, unaccented Unicode)",
                "editor": "Basileios Antoniades (digital text Maurice A. Robinson et al.)",
                "license": "Public Domain",
                "source": f"https://github.com/{ANT_REPO}@{ANT_COMMIT}",
            },
            "books": ant,
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
            "name": (
                "Multi-Edition Greek New Testament (SBLGNT, SRGNT, BHP, Tischendorf 8th, "
                "Westcott–Hort 1881, Byzantine Majority, Antoniades 1904, Textus Receptus)"
            ),
            "version": 2,
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
