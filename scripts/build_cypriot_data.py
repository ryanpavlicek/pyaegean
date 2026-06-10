"""Generate the bundled Cypriot syllabary sign data from the Unicode Character Database.

The Cypriot syllabary (used c. 11th–4th century BC, chiefly for the Arcado-Cypriot dialect of
Greek) is deciphered, so the UCD is an authoritative, freely usable (Unicode-3.0 license) sign
list: the "Cypriot Syllabary" block (U+10800–U+1083F), whose character names carry the syllabic
value (e.g. ``CYPRIOT SYLLABLE KA``).

Run to (re)generate ``src/aegean/data/bundled/cypriot/{signs.json, phonetic_map.json}``::

    python scripts/build_cypriot_data.py

Retain the Unicode copyright notice (see NOTICE) when redistributing the generated data.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.request

UCD_URL = "https://www.unicode.org/Public/UCD/latest/ucd/UnicodeData.txt"
OUT = pathlib.Path(__file__).resolve().parent.parent / "src" / "aegean" / "data" / "bundled" / "cypriot"

_NAME = re.compile(r"^CYPRIOT SYLLABLE (.+)$")
# The x-series signs write the /ks/ cluster (ξ); every other value is just its lowercased form.
_SPECIAL = {"XA": "ksa", "XE": "kse"}


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
        value = m.group(1)
        cp = int(cols[0], 16)
        phonetic = _SPECIAL.get(value, value.lower())
        signs.append({
            "label": value, "glyph": chr(cp), "codepoint": cp, "phonetic": phonetic,
            "unicodeName": cols[1], "signClass": "syllabogram",
        })
        pmap[value] = phonetic

    OUT.mkdir(parents=True, exist_ok=True)
    objs = ",\n".join(json.dumps(s, ensure_ascii=False, separators=(",", ":")) for s in signs)
    (OUT / "signs.json").write_text(f"[\n{objs}\n]\n", encoding="utf-8")
    (OUT / "phonetic_map.json").write_text(json.dumps(pmap, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"wrote {len(signs)} Cypriot syllabograms ({len(pmap)} phonetic entries) to {OUT}")


if __name__ == "__main__":
    main()
