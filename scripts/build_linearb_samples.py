"""Expand the bundled Linear B sample inscriptions (WP4) from sourced quotations.

Source: the tablet quotations embedded in Wiktionary's Mycenaean Greek entries
(via the kaikki.org extract — each quotation cites its tablet, gives the
romanized reading, and usually a translation). Every emitted sample is therefore
a published, attributed excerpt — nothing is typed from memory. The two
hand-curated samples already bundled are kept verbatim.

These remain *illustrative excerpts*, not editions: one quoted line per tablet,
chosen for clean tokenization. The bring-your-own EpiDoc path is the real-corpus
route (see the Linear B wiki page).

Run:  python scripts/build_linearb_samples.py
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

URL = "https://kaikki.org/dictionary/Mycenaean%20Greek/kaikki.org-dictionary-MycenaeanGreek.jsonl"
OUT = (
    Path(__file__).resolve().parents[1]
    / "src" / "aegean" / "data" / "bundled" / "linearb" / "sample_inscriptions.json"
)

_SITE = {"PY": "Pylos", "KN": "Knossos", "TH": "Thebes", "MY": "Mycenae", "TI": "Tiryns"}
# "PY Ta 641", "KN Ga(1) 675", "Knossos Ga(1) 675.1" … → ("KN", "Ga", "675")
_REF_RE = re.compile(
    r"\b(PY|KN|TH|MY|TI|Pylos|Knossos|Thebes|Mycenae|Tiryns)\s+"
    r"([A-Z][a-z]{1,2})\s*(?:\(\d\))?\s+(\d+)",
)
_PREFIX = {"Pylos": "PY", "Knossos": "KN", "Thebes": "TH", "Mycenae": "MY", "Tiryns": "TI"}
# a clean romanized token: syllabic word, ideogram/logogram (incl. *nn), number,
# or bracketed-uncertain reading — used to vet whole lines
_TOKEN_OK = re.compile(r"^(?:[a-z0-9*₂₃₄]+(?:-[a-z0-9*₂₃₄]+)*|[A-Z*][A-Z0-9*+]*|\d+|\[[^\]]*\])$")
_SUB = {"₂": "2", "₃": "3", "₄": "4"}


def _norm_token(t: str) -> str:
    for k, v in _SUB.items():
        t = t.replace(k, v)
    return t.upper()


def main() -> None:
    existing = json.loads(OUT.read_text(encoding="utf-8"))
    keep_ids = {rec["id"] for rec in existing}
    print(f"hand-curated samples kept verbatim: {sorted(keep_ids)}")

    with urllib.request.urlopen(URL, timeout=60) as resp:
        lines = resp.read().decode("utf-8").splitlines()

    candidates: dict[str, dict] = {}  # tablet id → sample record (best example wins)
    for ln in lines:
        rec = json.loads(ln)
        for sense in rec.get("senses") or []:
            for ex in sense.get("examples") or []:
                ref, roman = ex.get("ref") or "", ex.get("roman") or ""
                translation = (ex.get("translation") or ex.get("english") or "").strip()
                m = _REF_RE.search(ref)
                if not (m and roman and translation):
                    continue
                prefix = _PREFIX.get(m.group(1), m.group(1))
                tablet = f"{prefix} {m.group(2)} {m.group(3)}"
                toks = roman.split()
                if not (3 <= len(toks) <= 14):
                    continue  # one clean line, not a fragment or a whole tablet
                if not all(_TOKEN_OK.match(t) for t in toks):
                    continue
                words = [_norm_token(t) for t in toks]
                entry = {
                    "id": tablet,
                    "site": _SITE.get(prefix, ""),
                    "support": "Tablet",
                    "scribe": "",
                    "context": "",
                    "name": tablet,
                    "words": words,
                    "translations": [
                        f"{translation.rstrip('.')} (illustrative excerpt; "
                        f"quotation via Wiktionary, ref. {ref.strip().rstrip(':')})"
                    ],
                }
                # prefer the longest clean line per tablet
                if tablet not in candidates or len(words) > len(candidates[tablet]["words"]):
                    candidates[tablet] = entry

    new = [c for tid, c in sorted(candidates.items()) if tid not in keep_ids]
    print(f"verified one-line excerpts found: {len(candidates)} tablets ({len(new)} new)")
    merged = existing + new
    OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"sample_inscriptions.json: {len(merged)} inscriptions")
    for rec in merged:
        print(f"  {rec['id']:12s} {' '.join(rec['words'])[:64]}")


if __name__ == "__main__":
    main()
