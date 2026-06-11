"""Regenerate the bundled Linear B Greek-bridge lexicon (WP4 expansion).

Source: Wiktionary's Mycenaean Greek entries, via the machine-readable kaikki.org
extract (https://kaikki.org/dictionary/Mycenaean%20Greek/ — Wiktionary content,
CC BY-SA; see NOTICE). Each accepted entry has a clean syllabic romanization, an
English gloss, and an **Ancient Greek cognate/equivalent stated in its
etymology** — that equation is the bridge (`po-me → ποιμήν`).

Precedence: the hand-curated entries already in the bundled lexicon are kept
verbatim (they cite Documents in Mycenaean Greek); the extract only adds. Any
disagreement between the two layers is printed for review, never auto-resolved.

Run:  python scripts/build_linearb_lexicon.py
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

URL = "https://kaikki.org/dictionary/Mycenaean%20Greek/kaikki.org-dictionary-MycenaeanGreek.jsonl"
OUT = Path(__file__).resolve().parents[1] / "src" / "aegean" / "data" / "bundled" / "linearb" / "lexicon.json"

# the first Ancient Greek form named in the etymology — in gmy entries this is
# the direct cognate/descendant (spot-checked; the curated layer guards drift)
_GREEK_RE = re.compile(r"Ancient Greek\s+([Ͱ-Ͽἀ-῿][Ͱ-Ͽἀ-῿̀-ͅʼ’]*)")
_ROMAN_OK = re.compile(r"^[A-Z](?:[A-Z0-9*]*)(?:-[A-Z0-9*]+)*$")
_SUBSCRIPT = {"₂": "2", "₃": "3", "₄": "4"}


def _norm_roman(r: str) -> str:
    for k, v in _SUBSCRIPT.items():
        r = r.replace(k, v)
    return r.upper()


def main() -> None:
    existing: dict[str, dict[str, str]] = json.loads(OUT.read_text(encoding="utf-8"))
    print(f"hand-curated layer: {len(existing)} entries (kept verbatim)")

    with urllib.request.urlopen(URL, timeout=60) as resp:
        lines = resp.read().decode("utf-8").splitlines()
    print(f"kaikki extract: {len(lines)} Wiktionary entries")

    added: dict[str, dict[str, str]] = {}
    disagreements = 0
    skipped_no_roman = skipped_no_greek = skipped_no_gloss = 0
    for ln in lines:
        rec = json.loads(ln)
        roman = next(
            (f["form"] for f in rec.get("forms") or [] if "romanization" in (f.get("tags") or [])),
            None,
        )
        if not roman:
            skipped_no_roman += 1
            continue
        key = _norm_roman(roman.strip())
        if not _ROMAN_OK.match(key):
            skipped_no_roman += 1
            continue
        m = _GREEK_RE.search(rec.get("etymology_text") or "")
        if not m:
            skipped_no_greek += 1
            continue
        lemma = m.group(1).rstrip("ʼ’")
        glosses = [g for s in rec.get("senses") or [] for g in s.get("glosses") or []]
        if not glosses:
            skipped_no_gloss += 1
            continue
        gloss = glosses[0].strip().rstrip(".")
        if len(gloss) > 80:
            gloss = gloss[:77].rstrip() + "…"
        if key in existing:
            if existing[key]["lemma"] != lemma:
                disagreements += 1
                print(f"  note: {key}: curated {existing[key]['lemma']!r} vs extract {lemma!r} — curated kept")
            continue
        if key in added:
            continue  # first entry (usually the noun) wins
        added[key] = {"lemma": lemma, "gloss": gloss}

    merged = dict(existing)
    merged.update(added)
    out = dict(sorted(merged.items()))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(
        f"added {len(added)} extracted entries → {len(out)} total "
        f"(skipped: {skipped_no_roman} no/odd romanization, {skipped_no_greek} no Greek "
        f"equation, {skipped_no_gloss} no gloss; {disagreements} curated-vs-extract notes)"
    )

    # sanity: the canonical equations must hold whatever the extract said
    for key, lemma in (("PO-ME", "ποιμήν"), ("KA-KO", "χαλκός"), ("WA-NA-KA", "ἄναξ")):
        got = out.get(key, {}).get("lemma")
        assert got == lemma, f"sanity: {key} → {got!r}, expected {lemma!r}"
    print("sanity equations hold (PO-ME, KA-KO, WA-NA-KA)")


if __name__ == "__main__":
    main()
