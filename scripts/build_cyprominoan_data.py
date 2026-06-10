"""Generate the bundled Cypro-Minoan sign data from the Unicode Character Database.

Cypro-Minoan (Bronze Age Cyprus, c. 1550–1050 BC) is **undeciphered**: its signs have no settled
phonetic values, so — unlike the Cypriot syllabary or Linear B — there is no phonetic map to build.
The UCD's "Cypro-Minoan" block (U+12F90–U+12FF2) is an authoritative, freely usable (Unicode-3.0
license) sign list, whose character names carry only the conventional sign number (e.g.
``CYPRO-MINOAN SIGN CM001``).

Run to (re)generate ``src/aegean/data/bundled/cyprominoan/signs.json``::

    python scripts/build_cyprominoan_data.py

Retain the Unicode copyright notice (see NOTICE) when redistributing the generated data.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.request

UCD_URL = "https://www.unicode.org/Public/UCD/latest/ucd/UnicodeData.txt"
OUT = pathlib.Path(__file__).resolve().parent.parent / "src" / "aegean" / "data" / "bundled" / "cyprominoan"

_NAME = re.compile(r"^CYPRO-MINOAN SIGN (.+)$")


def _ucd_text() -> str:
    if len(sys.argv) > 1:  # a local UnicodeData.txt path, to avoid the network
        return pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
    return urllib.request.urlopen(UCD_URL).read().decode("utf-8")  # noqa: S310 - fixed Unicode URL


def main() -> None:
    signs: list[dict[str, object]] = []
    for row in _ucd_text().splitlines():
        cols = row.split(";")
        if len(cols) < 2:
            continue
        m = _NAME.match(cols[1])
        if not m:
            continue
        cp = int(cols[0], 16)
        signs.append({
            "label": m.group(1),  # the conventional sign number, e.g. "CM001"
            "glyph": chr(cp), "codepoint": cp, "phonetic": None,  # undeciphered: no settled value
            "unicodeName": cols[1], "signClass": "sign",
        })

    OUT.mkdir(parents=True, exist_ok=True)
    objs = ",\n".join(json.dumps(s, ensure_ascii=False, separators=(",", ":")) for s in signs)
    (OUT / "signs.json").write_text(f"[\n{objs}\n]\n", encoding="utf-8")
    print(f"wrote {len(signs)} Cypro-Minoan signs to {OUT}")


if __name__ == "__main__":
    main()
