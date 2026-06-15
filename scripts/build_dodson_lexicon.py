"""Build the bundled Dodson Greek lexicon (Strong's-keyed Koine glosses).

Source: biblicalhumanities/Dodson-Greek-Lexicon ``dodson.xml`` — John Jeffrey Dodson's
public-domain New Testament Greek lexicon, dedicated to the public domain under **CC0**.
Each TEI ``<entry n="lemma | NNNN">`` carries the Unicode headword (``<orth>``) and a
brief + full gloss (``<def role="...">``).

CC0 lets pyaegean bundle this small lexicon in the wheel (no fetch needed): it powers
``greek.use_dodson`` / ``greek.gloss_nt`` and self-glosses the NT corpus by Strong's number.

Output (``src/aegean/data/bundled/greek/dodson.json``, plain UTF-8 JSON):

    {"_meta": {...}, "entries": {"<strongs>": {"lemma": "<unicode>", "gloss": "<brief>",
      "definition": "<full>"}, ...}}

Usage:
    python scripts/build_dodson_lexicon.py
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

REPO = "biblicalhumanities/Dodson-Greek-Lexicon"
XML_PATH = "dodson.xml"
SOURCE_URL = f"https://github.com/{REPO}"
LICENSE = "CC0-1.0 (public domain dedication)"
ATTRIBUTION = (
    "Dodson Greek Lexicon — John Jeffrey Dodson, A Public Domain Greek-English Lexicon of "
    "the New Testament; digital edition by Ulrik Sandborg-Petersen / biblicalhumanities. CC0."
)
CITE = "Dodson, J. J. A Public Domain Greek-English Lexicon of the New Testament (CC0)."


def _resolve_commit(ref: str) -> str:
    url = f"https://api.github.com/repos/{REPO}/commits/{ref}"
    req = urllib.request.Request(url, headers={"User-Agent": "pyaegean-build"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (trusted host)
        return str(json.load(resp)["sha"])


def _fetch_xml(commit: str) -> str:
    url = f"https://raw.githubusercontent.com/{REPO}/{commit}/{XML_PATH}"
    req = urllib.request.Request(url, headers={"User-Agent": "pyaegean-build"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (trusted host)
        return resp.read().decode("utf-8")


def _local(tag: str) -> str:
    """Strip an XML namespace: ``{ns}entry`` -> ``entry`` (iter() has no ns wildcard)."""
    return tag.rsplit("}", 1)[-1]


def _parse(xml_text: str) -> dict[str, dict[str, str]]:
    root = ET.fromstring(xml_text)
    entries: dict[str, dict[str, str]] = {}
    for entry in root.iter():
        if _local(entry.tag) != "entry":
            continue
        n = entry.get("n", "")
        if "|" not in n:
            continue
        strong = n.split("|", 1)[1].strip()
        if not strong.isdigit():
            continue
        key = str(int(strong))  # drop zero-padding -> "0001" becomes "1"
        lemma = ""
        brief = full = ""
        for child in entry:
            local = _local(child.tag)
            text = " ".join("".join(child.itertext()).split())  # collapse XML indent/newlines
            if local == "orth" and not lemma:
                lemma = text.split(",", 1)[0].strip()
            elif local == "def" and child.get("role") == "brief":
                brief = text
            elif local == "def" and child.get("role") == "full":
                full = text
        rec = {"lemma": lemma, "gloss": brief or full}
        if full and full != brief:
            rec["definition"] = full
        entries[key] = rec
    return entries


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the bundled Dodson Koine lexicon.")
    ap.add_argument("--ref", default="master")
    ap.add_argument("--out", type=Path,
                    default=Path("src/aegean/data/bundled/greek/dodson.json"))
    args = ap.parse_args()

    commit = _resolve_commit(args.ref)
    print(f"{REPO}@{commit}")
    entries = _parse(_fetch_xml(commit))
    out: dict[str, Any] = {
        "_meta": {
            "name": "Dodson Greek Lexicon",
            "version": 1,
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "cite": CITE,
            "source_url": SOURCE_URL,
            "source_commit": commit,
            "generated": time.strftime("%Y-%m-%d"),
            "entry_count": len(entries),
        },
        "entries": entries,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    size = args.out.stat().st_size / 1_000_000
    print(f"wrote {args.out}  ({len(entries)} entries, {size:.2f} MB)")


if __name__ == "__main__":
    main()
