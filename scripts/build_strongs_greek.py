"""Build the Extended Strong's Greek Lexicon release asset (``strongs-greek.json.gz``).

Combines two open-licensed sources:

1. **STEPBible TBESG** (*Translators Brief Lexicon of Extended Strongs for Greek*,
   ``STEPBible/STEPBible-Data``, CC BY 4.0) — covers the New Testament, Septuagint
   (LXX), Apocrypha, and Apostolic Fathers (G0001–G9979), with Greek headwords,
   transliterations, morphological codes, brief glosses, Abbott-Smith / Middle
   Liddell definitions, and Hebrew Strong's cross-references (``H####``).
2. **OpenScriptures Strong's Greek Dictionary** (``openscriptures/strongs``,
   CC BY-SA, derived from James Strong 1890) — provides classic Strong's
   derivations/etymologies (parsed into structured root Strong's numbers for
   word-family trees), Strong's definitions, and KJV usage summaries.

Because CC BY-SA applies to the combined derived asset, it is hosted as a
SHA-256-pinned GitHub Release asset (fetched to cache on demand) and never
bundled into the Apache-2.0 PyPI wheel.

Usage:
    python scripts/build_strongs_greek.py --out strongs-greek.json.gz
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

STEP_REPO = "STEPBible/STEPBible-Data"
STEP_COMMIT = "5de0a47f35f0fc13dfe1430d104e5db8a4285f9c"
STEP_PATH = "Lexicons/TBESG - Translators Brief lexicon of Extended Strongs for Greek - STEPBible.org CC BY.txt"

OS_REPO = "openscriptures/strongs"
OS_COMMIT = "0acd2f251c2d35ff8db2dece4e0593979d3ac223"
OS_PATH = "greek/strongs-greek-dictionary.js"

LICENSE = (
    "CC BY-SA 4.0 (combined derived lexicon: STEPBible TBESG CC BY 4.0 + "
    "OpenScriptures Strong's Greek Dictionary CC BY-SA)"
)
ATTRIBUTION = (
    "Extended Strong's Greek Lexicon combining STEPBible TBESG "
    "(STEPBible.org / Tyndale House, Cambridge, CC BY 4.0) and "
    "OpenScriptures Strong's Greek Dictionary (James Strong 1890, XML by Ulrik Petersen, "
    "JSON by Open Scriptures, CC BY-SA)."
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_ROOT_RE = re.compile(r"\b([GH]\d{1,5})\b")
_BR_RE = re.compile(r"<BR\s*/?>", re.IGNORECASE)


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "pyaegean-build"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        return resp.read().decode("utf-8-sig")


def _clean_html(raw: str) -> str:
    text = _BR_RE.sub(" ", raw)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    return unicodedata.normalize("NFC", text)


def _norm_strongs_id(raw: str) -> str:
    """Normalize Strong's ID like 'G0001' or 'G1' or 'G0001G' -> 'G0001' / 'G0001G'."""
    s = raw.strip().split(" ", 1)[0].upper()
    m = re.match(r"^([GH])(\d+)([A-Z]?)$", s)
    if not m:
        return s
    prefix, num, suffix = m.groups()
    return f"{prefix}{int(num):04d}{suffix}"


def _extract_roots(derivation: str, self_id: str) -> list[str]:
    roots: list[str] = []
    seen: set[str] = {self_id}
    for m in _ROOT_RE.finditer(derivation):
        code = _norm_strongs_id(m.group(1))
        if code not in seen:
            seen.add(code)
            roots.append(code)
    return roots


def _parse_openscriptures(js_text: str) -> dict[str, dict[str, Any]]:
    idx = js_text.find("{")
    end = js_text.rfind("}")
    if idx < 0 or end < 0:
        raise RuntimeError("Could not locate JSON object in strongs-greek-dictionary.js")
    raw = json.loads(js_text[idx : end + 1])
    out: dict[str, dict[str, Any]] = {}
    for k, rec in raw.items():
        sid = _norm_strongs_id(k)
        deriv = unicodedata.normalize("NFC", str(rec.get("derivation", "")).strip())
        out[sid] = {
            "lemma": unicodedata.normalize("NFC", str(rec.get("lemma", "")).strip()),
            "translit": unicodedata.normalize("NFC", str(rec.get("translit", "")).strip()),
            "strongs_def": unicodedata.normalize("NFC", str(rec.get("strongs_def", "")).strip()),
            "kjv_def": unicodedata.normalize("NFC", str(rec.get("kjv_def", "")).strip()),
            "derivation": deriv,
            "roots": _extract_roots(deriv, sid),
        }
    return out


def _parse_tbesg(tsv_text: str) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    started = False
    for line in tsv_text.splitlines():
        if not started:
            if line.startswith("====="):
                started = True
            continue
        if not line.strip() or line.startswith("$"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        estrong_raw, dstrong_raw, ustrong_raw, greek, translit, morph, gloss = parts[:7]
        meaning = parts[7] if len(parts) > 7 else ""
        estrong = _norm_strongs_id(estrong_raw)
        if not estrong.startswith("G"):
            continue
        dstrong = _norm_strongs_id(dstrong_raw)
        ustrong = _norm_strongs_id(ustrong_raw) if ustrong_raw.strip() else ""
        hebrew: list[str] = []
        if ustrong.startswith("H"):
            hebrew.append(ustrong)
        lemma = unicodedata.normalize("NFC", greek.strip())
        rec: dict[str, Any] = {
            "strongs": dstrong or estrong,
            "base_strongs": estrong,
            "lemma": lemma,
            "translit": unicodedata.normalize("NFC", translit.strip()),
            "morph": morph.strip(),
            "gloss": unicodedata.normalize("NFC", gloss.strip()),
            "definition": _clean_html(meaning),
        }
        if hebrew:
            rec["hebrew"] = hebrew

        # Store under disambiguated key if distinct, AND ensure base eStrong exists.
        if dstrong and dstrong != estrong:
            entries[dstrong] = rec
            if estrong not in entries:
                primary = dict(rec)
                primary["strongs"] = estrong
                primary["variants"] = [dstrong]
                entries[estrong] = primary
            else:
                variants = entries[estrong].setdefault("variants", [])
                if dstrong not in variants:
                    variants.append(dstrong)
                if hebrew:
                    existing_h = entries[estrong].setdefault("hebrew", [])
                    for h in hebrew:
                        if h not in existing_h:
                            existing_h.append(h)
        else:
            existing = entries.get(estrong)
            if existing is None:
                entries[estrong] = rec
            else:
                # Preserve any already-attached variants list
                if "variants" in existing:
                    rec["variants"] = existing["variants"]
                entries[estrong] = rec
    return entries


def build() -> dict[str, Any]:
    step_url = (
        f"https://raw.githubusercontent.com/{STEP_REPO}/{STEP_COMMIT}/"
        + urllib.parse.quote(STEP_PATH)
    )
    os_url = f"https://raw.githubusercontent.com/{OS_REPO}/{OS_COMMIT}/{OS_PATH}"
    print(f"Fetching {STEP_REPO}@{STEP_COMMIT[:10]} ...")
    tbesg = _parse_tbesg(_fetch_text(step_url))
    print(f"  parsed {len(tbesg)} TBESG entries")
    print(f"Fetching {OS_REPO}@{OS_COMMIT[:10]} ...")
    os_dict = _parse_openscriptures(_fetch_text(os_url))
    print(f"  parsed {len(os_dict)} OpenScriptures Strong's entries")

    # Merge OpenScriptures derivations, roots, strongs_def, kjv_def into TBESG entries
    for sid, orec in os_dict.items():
        target = tbesg.get(sid)
        if target is None:
            tbesg[sid] = {
                "strongs": sid,
                "base_strongs": sid,
                "lemma": orec["lemma"],
                "translit": orec["translit"],
                "morph": "",
                "gloss": orec["kjv_def"].split(",", 1)[0].strip() or orec["strongs_def"],
                "definition": orec["strongs_def"],
                "strongs_def": orec["strongs_def"],
                "kjv_def": orec["kjv_def"],
                "derivation": orec["derivation"],
                "roots": orec["roots"],
            }
        else:
            if orec["derivation"]:
                target["derivation"] = orec["derivation"]
            if orec["roots"]:
                target["roots"] = orec["roots"]
            if orec["strongs_def"]:
                target["strongs_def"] = orec["strongs_def"]
            if orec["kjv_def"]:
                target["kjv_def"] = orec["kjv_def"]
            if not target.get("lemma") and orec["lemma"]:
                target["lemma"] = orec["lemma"]
            if not target.get("translit") and orec["translit"]:
                target["translit"] = orec["translit"]

    sorted_entries = dict(sorted(tbesg.items()))
    return {
        "_meta": {
            "name": "Extended Strong's Greek Lexicon (NT + LXX + Apocrypha + Apostolic Fathers)",
            "version": 1,
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "sources": {
                "stepbible_tbesg": f"https://github.com/{STEP_REPO}@{STEP_COMMIT}",
                "openscriptures_strongs": f"https://github.com/{OS_REPO}@{OS_COMMIT}",
            },
            "entry_count": len(sorted_entries),
            "roots_count": sum(1 for e in sorted_entries.values() if e.get("roots")),
        },
        "entries": sorted_entries,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build strongs-greek.json.gz release asset.")
    ap.add_argument("--out", type=Path, default=Path("strongs-greek.json.gz"))
    args = ap.parse_args()
    payload = build()
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with args.out.open("wb") as raw_f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_f, compresslevel=9, mtime=0) as f:
            f.write(raw)
    mb = args.out.stat().st_size / 1_000_000
    print(
        f"wrote {args.out} ({payload['_meta']['entry_count']} entries, "
        f"{payload['_meta']['roots_count']} with roots, {mb:.2f} MB gz)"
    )


if __name__ == "__main__":
    main()
