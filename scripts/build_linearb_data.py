"""Generate the bundled Linear B sign data from the Unicode Character Database.

Linear B is deciphered, so the UCD is an authoritative, freely usable (Unicode-3.0 license)
machine-readable sign list. The "Linear B Syllabary" (U+10000–U+1007F) and "Linear B Ideograms"
(U+10080–U+100FF) blocks each encode the Bennett sign number and the syllabic value or commodity
right in the character name — e.g. ``LINEAR B SYLLABLE B008 A``, ``LINEAR B IDEOGRAM B131 WINE``.

Run to (re)generate ``src/aegean/data/bundled/linearb/{signs.json, phonetic_map.json}``::

    python scripts/build_linearb_data.py

Retain the Unicode copyright notice (see NOTICE) when redistributing the generated data.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.request

UCD_URL = "https://www.unicode.org/Public/UCD/latest/ucd/UnicodeData.txt"
OUT = pathlib.Path(__file__).resolve().parent.parent / "src" / "aegean" / "data" / "bundled" / "linearb"

_NAME = re.compile(r"^LINEAR B (SYLLABLE|SYMBOL|IDEOGRAM|MONOGRAM) (.+)$")
_BENNETT = re.compile(r"^(B\d+\w*)(?: (.+))?$")
_CLASS = {"SYLLABLE": "syllabogram", "SYMBOL": "symbol", "IDEOGRAM": "ideogram", "MONOGRAM": "monogram"}
# Phonetic values that differ from the lowercased transliteration (labiovelars, affricates) —
# the same convention as the Linear A phonetic map.
_SPECIAL = {"QA": "kwa", "QE": "kwe", "QI": "kwi", "QO": "kwo", "ZA": "dza", "ZE": "dze", "ZO": "dzo"}


def _ucd_text() -> str:
    if len(sys.argv) > 1:  # a local UnicodeData.txt path, to avoid the network
        return pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
    return urllib.request.urlopen(UCD_URL).read().decode("utf-8")  # noqa: S310 - fixed Unicode URL


def main() -> None:
    signs: list[dict[str, object]] = []
    pmap: dict[str, str] = {}
    for row in _ucd_text().splitlines():
        cols = row.split(";")
        if len(cols) < 2:
            continue
        m = _NAME.match(cols[1])
        if not m:
            continue
        kind, rest = m.group(1), m.group(2)
        bm = _BENNETT.match(rest)
        bennett, value = (bm.group(1), bm.group(2)) if bm else (None, rest)
        cp = int(cols[0], 16)
        is_syllable = kind == "SYLLABLE"
        label = value if value else (bennett or cols[1])
        phonetic = _SPECIAL.get(value, value.lower()) if (is_syllable and value) else None
        signs.append({
            "label": label,
            "glyph": chr(cp),
            "codepoint": cp,
            "phonetic": phonetic,
            "bennett": bennett,
            "unicodeName": cols[1],
            "signClass": _CLASS[kind],
            "commodity": value if (kind in ("IDEOGRAM", "MONOGRAM") and value) else None,
        })
        if phonetic is not None:
            pmap[label] = phonetic

    OUT.mkdir(parents=True, exist_ok=True)
    objs = ",\n".join(json.dumps(s, ensure_ascii=False, separators=(",", ":")) for s in signs)
    (OUT / "signs.json").write_text(f"[\n{objs}\n]\n", encoding="utf-8")
    (OUT / "phonetic_map.json").write_text(json.dumps(pmap, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    n_syl = sum(1 for s in signs if s["signClass"] == "syllabogram")
    print(f"wrote {len(signs)} signs ({n_syl} syllabograms, {len(pmap)} with phonetic values) to {OUT}")


if __name__ == "__main__":
    main()
