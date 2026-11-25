"""Build the complete Septuagint (LXX) release asset (``lxx-corpus.json.gz``).

Extracts all 55 Greek Septuagint books from Henry Barclay Swete's *The Old
Testament in Greek according to the Septuagint* (Cambridge University Press,
1887–1894, Public Domain base text) as digitized in EpiDoc TEI XML by the Open
Greek and Latin Project (``OpenGreekAndLatin/First1KGreek``, CC BY-SA 4.0) at a
pinned commit.

Marginal manuscript sigla (``<note type="marginal">``), section headings
(``<head>``), and deleted text (``<del>``, ``<surplus>``) are stripped cleanly
while preserving every Greek verse in NFC Unicode normalization.

Output schema:

    {
      "_meta": { ... },
      "books": {
        "Gen": {
          "_info": {"name": "Gen", "title": "Genesis", "work_id": "tlg0527.tlg001", "section": "Pentateuch"},
          "verses": {"1.1": "ΕΝ ΑΡΧΗ ἐποίησεν ὁ θεὸς τὸν οὐρανὸν καὶ τὴν γῆν.", ...}
        },
        ...
      }
    }

Usage:
    python scripts/build_lxx_corpus.py --out lxx-corpus.json.gz
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

FIRST1K_REPO = "OpenGreekAndLatin/First1KGreek"
FIRST1K_COMMIT = "4c9c843d80ee94b4371f52add5f7d68bbfe7ba4c"

LICENSE = (
    "CC BY-SA 4.0 (Open Greek and Latin / First1KGreek EpiDoc TEI digitization; "
    "base Greek text Henry Barclay Swete, Cambridge University Press, 1887–1894, Public Domain)"
)
ATTRIBUTION = (
    "The Old Testament in Greek according to the Septuagint, ed. Henry Barclay Swete "
    "(Cambridge University Press, 1887–1894); digital TEI XML edition by the Open Greek "
    "and Latin Project (First1KGreek, CC BY-SA 4.0)."
)

_TEI = "{http://www.tei-c.org/ns/1.0}"
_SKIP_TAGS = frozenset(
    {
        f"{_TEI}note",
        f"{_TEI}head",
        f"{_TEI}bibl",
        f"{_TEI}figDesc",
        f"{_TEI}fw",
        f"{_TEI}del",
        f"{_TEI}surplus",
    }
)
_WS_RE = re.compile(r"\s+")

# All 55 Swete Septuagint books in First1KGreek with exact XML filenames.
_LXX_FILES: tuple[tuple[str, str, str, str, str], ...] = (
    ("Gen", "Genesis", "tlg0527.tlg001", "Pentateuch", "tlg0527.tlg001.1st1K-grc1.xml"),
    ("Exod", "Exodus", "tlg0527.tlg002", "Pentateuch", "tlg0527.tlg002.1st1K-grc1.xml"),
    ("Lev", "Leviticus", "tlg0527.tlg003", "Pentateuch", "tlg0527.tlg003.1st1K-grc1.xml"),
    ("Num", "Numbers", "tlg0527.tlg004", "Pentateuch", "tlg0527.tlg004.1st1K-grc1.xml"),
    ("Deut", "Deuteronomy", "tlg0527.tlg005", "Pentateuch", "tlg0527.tlg005.1st1K-grc1.xml"),
    ("Josh", "Joshua", "tlg0527.tlg006", "History", "tlg0527.tlg006.1st1K-grc1.xml"),
    ("Judg", "Judges", "tlg0527.tlg008", "History", "tlg0527.tlg008.1st1K-grc1.xml"),
    ("Ruth", "Ruth", "tlg0527.tlg010", "History", "tlg0527.tlg010.1st1K-grc1.xml"),
    ("1Kgdms", "1 Kingdoms (1 Samuel)", "tlg0527.tlg011", "History", "tlg0527.tlg011.1st1K-grc1.xml"),
    ("2Kgdms", "2 Kingdoms (2 Samuel)", "tlg0527.tlg012", "History", "tlg0527.tlg012.1st1K-grc1.xml"),
    ("3Kgdms", "3 Kingdoms (1 Kings)", "tlg0527.tlg013", "History", "tlg0527.tlg013.1st1K-grc1.xml"),
    ("4Kgdms", "4 Kingdoms (2 Kings)", "tlg0527.tlg014", "History", "tlg0527.tlg014.1st1K-grc1.xml"),
    ("1Chr", "1 Chronicles (1 Paralipomenon)", "tlg0527.tlg015", "History", "tlg0527.tlg015.1st1K-grc1.xml"),
    ("2Chr", "2 Chronicles (2 Paralipomenon)", "tlg0527.tlg016", "History", "tlg0527.tlg016.1st1K-grc1.xml"),
    ("1Esdr", "1 Esdras", "tlg0527.tlg017", "History", "tlg0527.tlg017.1st1K-grc1.xml"),
    ("2Esdr", "2 Esdras (Ezra–Nehemiah)", "tlg0527.tlg018", "History", "tlg0527.tlg018.1st1K-grc1.xml"),
    ("Esth", "Esther", "tlg0527.tlg019", "History", "tlg0527.tlg019.1st1K-grc1.xml"),
    ("Jdt", "Judith", "tlg0527.tlg020", "Deuterocanonical", "tlg0527.tlg020.1st1K-grc1.xml"),
    ("Tob", "Tobit", "tlg0527.tlg021", "Deuterocanonical", "tlg0527.tlg021.1st1K-grc1.xml"),
    ("1Macc", "1 Maccabees", "tlg0527.tlg023", "Deuterocanonical", "tlg0527.tlg023.1st1K-grc1.xml"),
    ("2Macc", "2 Maccabees", "tlg0527.tlg024", "Deuterocanonical", "tlg0527.tlg024.1st1K-grc1.xml"),
    ("3Macc", "3 Maccabees", "tlg0527.tlg025", "Deuterocanonical", "tlg0527.tlg025.1st1K-grc1.xml"),
    ("4Macc", "4 Maccabees", "tlg0527.tlg026", "Deuterocanonical", "tlg0527.tlg026.1st1K-grc1.xml"),
    ("Ps", "Psalms", "tlg0527.tlg027", "Wisdom", "tlg0527.tlg027.1st1K-grc1.xml"),
    ("Odes", "Odes", "tlg0527.tlg028", "Wisdom", "tlg0527.tlg028.1st1K-grc1.xml"),
    ("Prov", "Proverbs", "tlg0527.tlg029", "Wisdom", "tlg0527.tlg029.1st1K-grc1.xml"),
    ("Song", "Song of Songs (Canticum)", "tlg0527.tlg031", "Wisdom", "tlg0527.tlg031.1st1K-grc1.xml"),
    ("Job", "Job", "tlg0527.tlg032", "Wisdom", "tlg0527.tlg032.1st1K-grc1.xml"),
    ("Wis", "Wisdom of Solomon", "tlg0527.tlg033", "Deuterocanonical", "tlg0527.tlg033.1st1K-grc1.xml"),
    ("Sir", "Sirach (Ecclesiasticus)", "tlg0527.tlg034", "Deuterocanonical", "tlg0527.tlg034.1st1K-grc2.xml"),
    ("PssSol", "Psalms of Solomon", "tlg0527.tlg035", "Deuterocanonical", "tlg0527.tlg035.1st1K-grc1.xml"),
    ("Hos", "Hosea", "tlg0527.tlg036", "Minor Prophets", "tlg0527.tlg036.1st1K-grc1.xml"),
    ("Amos", "Amos", "tlg0527.tlg037", "Minor Prophets", "tlg0527.tlg037.1st1K-grc1.xml"),
    ("Mic", "Micah", "tlg0527.tlg038", "Minor Prophets", "tlg0527.tlg038.1st1K-grc1.xml"),
    ("Joel", "Joel", "tlg0527.tlg039", "Minor Prophets", "tlg0527.tlg039.1st1K-grc1.xml"),
    ("Obad", "Obadiah", "tlg0527.tlg040", "Minor Prophets", "tlg0527.tlg040.1st1K-grc1.xml"),
    ("Jonah", "Jonah", "tlg0527.tlg041", "Minor Prophets", "tlg0527.tlg041.1st1K-grc1.xml"),
    ("Nah", "Nahum", "tlg0527.tlg042", "Minor Prophets", "tlg0527.tlg042.1st1K-grc1.xml"),
    ("Hab", "Habakkuk", "tlg0527.tlg043", "Minor Prophets", "tlg0527.tlg043.1st1K-grc1.xml"),
    ("Zeph", "Zephaniah", "tlg0527.tlg044", "Minor Prophets", "tlg0527.tlg044.1st1K-grc1.xml"),
    ("Hag", "Haggai", "tlg0527.tlg045", "Minor Prophets", "tlg0527.tlg045.1st1K-grc1.xml"),
    ("Zech", "Zechariah", "tlg0527.tlg046", "Minor Prophets", "tlg0527.tlg046.1st1K-grc1.xml"),
    ("Mal", "Malachi", "tlg0527.tlg047", "Minor Prophets", "tlg0527.tlg047.1st1K-grc1.xml"),
    ("Isa", "Isaiah", "tlg0527.tlg048", "Major Prophets", "tlg0527.tlg048.1st1K-grc2.xml"),
    ("Jer", "Jeremiah", "tlg0527.tlg049", "Major Prophets", "tlg0527.tlg049.1st1K-grc1.xml"),
    ("Bar", "Baruch", "tlg0527.tlg050", "Deuterocanonical", "tlg0527.tlg050.1st1K-grc1.xml"),
    ("Lam", "Lamentations", "tlg0527.tlg051", "Major Prophets", "tlg0527.tlg051.1st1K-grc1.xml"),
    ("EpJer", "Epistle of Jeremiah", "tlg0527.tlg052", "Deuterocanonical", "tlg0527.tlg052.1st1K-grc1.xml"),
    ("Ezek", "Ezekiel", "tlg0527.tlg053", "Major Prophets", "tlg0527.tlg053.1st1K-grc1.xml"),
    ("Sus-OG", "Susanna (Old Greek)", "tlg0527.tlg054", "Deuterocanonical", "tlg0527.tlg054.1st1K-grc1.xml"),
    ("Sus-Th", "Susanna (Theodotion)", "tlg0527.tlg055", "Deuterocanonical", "tlg0527.tlg055.1st1K-grc1.xml"),
    ("Dan-OG", "Daniel (Old Greek)", "tlg0527.tlg056", "Major Prophets", "tlg0527.tlg056.1st1K-grc1.xml"),
    ("Dan-Th", "Daniel (Theodotion)", "tlg0527.tlg057", "Major Prophets", "tlg0527.tlg057.1st1K-grc1.xml"),
    ("Bel-OG", "Bel and the Dragon (Old Greek)", "tlg0527.tlg058", "Deuterocanonical", "tlg0527.tlg058.1st1K-grc1.xml"),
    ("Bel-Th", "Bel and the Dragon (Theodotion)", "tlg0527.tlg059", "Deuterocanonical", "tlg0527.tlg059.1st1K-grc1.xml"),
)


def _fetch_xml(subid: str, filename: str) -> str:
    url = (
        f"https://raw.githubusercontent.com/{FIRST1K_REPO}/{FIRST1K_COMMIT}"
        f"/data/tlg0527/{subid}/{filename}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "pyaegean-build"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        return resp.read().decode("utf-8-sig")


def _extract_clean_text(elem: ET.Element) -> str:
    parts: list[str] = []

    def _walk(node: ET.Element) -> None:
        if node.tag in _SKIP_TAGS:
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            _walk(child)
            if child.tail:
                parts.append(child.tail)

    _walk(elem)
    raw = _WS_RE.sub(" ", " ".join(parts)).strip()
    return unicodedata.normalize("NFC", raw)


def _parse_lxx_xml(xml_text: str) -> dict[str, str]:
    root = ET.fromstring(xml_text)
    body = root.find(f".//{_TEI}body")
    if body is None:
        return {}
    verses: dict[str, str] = {}
    chapters = body.findall(f".//{_TEI}div[@type='textpart'][@subtype='chapter']")
    if chapters:
        for chap_el in chapters:
            chap_n = (chap_el.get("n") or "1").strip()
            verse_els = chap_el.findall(f".//{_TEI}div[@type='textpart'][@subtype='verse']")
            if verse_els:
                for v_el in verse_els:
                    v_n = (v_el.get("n") or "1").strip()
                    txt = _extract_clean_text(v_el)
                    if txt:
                        key = f"{chap_n}.{v_n}"
                        verses[key] = f"{verses[key]} {txt}" if key in verses else txt
            else:
                txt = _extract_clean_text(chap_el)
                if txt:
                    verses[f"{chap_n}.1"] = txt
    else:
        verse_els = body.findall(f".//{_TEI}div[@type='textpart'][@subtype='verse']")
        for v_el in verse_els:
            v_n = (v_el.get("n") or "1").strip()
            txt = _extract_clean_text(v_el)
            if txt:
                verses[f"1.{v_n}"] = txt
    return verses


def build(out_path: Path) -> None:
    print(f"Building Septuagint (LXX) corpus from {FIRST1K_REPO}@{FIRST1K_COMMIT[:12]} ...")
    books: dict[str, Any] = {}
    total_verses = 0
    for name, title, work_id, section, filename in _LXX_FILES:
        subid = work_id.split(".")[1]
        xml_text = _fetch_xml(subid, filename)
        verses = _parse_lxx_xml(xml_text)
        total_verses += len(verses)
        books[name] = {
            "_info": {
                "name": name,
                "title": title,
                "work_id": work_id,
                "section": section,
                "filename": filename,
            },
            "verses": verses,
        }
        print(f"  {name:8s} ({work_id}): {len(verses):4d} verses")

    payload = {
        "_meta": {
            "name": "lxx-corpus",
            "version": "1",
            "edition": "Swete Septuagint (1887–1894)",
            "source_repo": f"https://github.com/{FIRST1K_REPO}",
            "source_commit": FIRST1K_COMMIT,
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "books": len(books),
            "verses": total_verses,
        },
        "books": books,
    }
    raw_bytes = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as raw_fh:
        with gzip.GzipFile(filename="lxx-corpus.json", mode="wb", fileobj=raw_fh, compresslevel=9, mtime=0) as gz:
            gz.write(raw_bytes)
    sha = hashlib.sha256(out_path.read_bytes()).hexdigest()
    size_kb = out_path.stat().st_size / 1024.0
    print(
        f"Wrote {out_path} ({len(books)} books, {total_verses} verses, "
        f"{size_kb:,.1f} KB, sha256={sha})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("lxx-corpus.json.gz"))
    args = parser.parse_args()
    build(args.out)


if __name__ == "__main__":
    main()
