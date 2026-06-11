"""Rebuild SigLA's JSON database from its published web-app payload (WP4).

SigLA's paper describes an import pipeline producing "a JSON database"; the
deployed site packs that data as OCaml-Marshal payloads inside ``database.js``.
This script reverses the packing with `aegean.scripts.lineara.sigla`'s reader
and emits a clean, versioned ``sigla-corpus.json`` — the dataset the paper
invites others to use "outside the interface", in the form it describes.

License: the SigLA dataset is published **CC BY-NC-SA 4.0** (Salgarella &
Castellan), and the paper states copies of SigLA "can be easily hosted". The
emitted file is therefore CC BY-NC-SA 4.0 with attribution baked into its
``_meta`` — distribute it only as a clearly-labeled release asset, never inside
the Apache-2.0 wheel.

Mapping policy: fields whose meaning is *verified* get names; everything else
is preserved raw (``raw_flags``) so no information is lost and semantics can be
layered later without re-decoding. Cross-validation against pyaegean's bundled
GORILA corpus (sign-sequence agreement on shared documents) is printed and must
be checked before publishing.

Run:  python scripts/build_sigla_corpus.py [path-to-database.js]
      (downloads https://sigla.phis.me/database.js when no path is given)
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aegean.scripts.lineara.sigla import Block, parse_database_js  # noqa: E402

URL = "https://sigla.phis.me/database.js"
OUT = Path(__file__).resolve().parents[1] / "sigla-corpus.json"


def map_items(node: Any) -> Any:
    """In-order items of an OCaml Map (Empty = int 0; Node = [l, k, v, r, h])."""
    if isinstance(node, int):
        return
    left, key, val, right, _h = node.fields
    yield from map_items(left)
    yield key, val
    yield from map_items(right)


def opt(v: Any) -> Any:
    """OCaml option: 0 = None; Block(0, [x]) = Some x."""
    if isinstance(v, Block) and v.tag == 0 and len(v.fields) == 1:
        return v.fields[0]
    return None if v == 0 else v


def _find_sign_record(v: Any, depth: int = 0) -> Block | None:
    """Locate the 9-field sign record: fields[0] is the series string (AB/A/N)."""
    if isinstance(v, Block):
        if len(v.fields) == 9 and isinstance(v.fields[0], str):
            return v
        if depth < 5:
            for f in v.fields:
                hit = _find_sign_record(f, depth + 1)
                if hit is not None:
                    return hit
    return None


def _first_string(v: Any, depth: int = 0) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, Block) and depth < 5:
        for f in v.fields:
            s = _first_string(f, depth + 1)
            if s:
                return s
    return ""


def _triple(rec: Block) -> tuple[str, str, str]:
    """(series, transliteration, representative drawing ref) — the content key.

    The ``data`` and ``signs`` payloads are separate Marshal values, so their
    sign records are copies, not shared objects; this triple joins them (the
    representative ref, e.g. ``KH 5/5``, is unique per sign)."""
    return str(rec.fields[0]), _first_string(rec.fields[2]), _first_string(rec.fields[3])


def _display(series: str, number: int | None, value: str) -> str:
    """The sign as pyaegean's corpus writes it: transliteration for the
    deciphered-convention AB signs, ``*NNN`` for the Linear-A-only signs."""
    if value:
        return value.upper()
    if number is not None:
        return f"*{number}"
    return ""


def _attestation(att: Any, by_triple: dict[tuple[str, str, str], int]) -> dict[str, Any]:
    """One attestation block → conservative record; unresolved data kept raw."""
    raw = [f for f in att.fields if isinstance(f, int)] if isinstance(att, Block) else []
    rec = _find_sign_record(att) if isinstance(att, Block) else None
    if rec is None:
        return {"sign": "", "series": "", "number": None, "raw_flags": raw}
    series, value, ref = _triple(rec)
    number = by_triple.get((series, value, ref))
    return {
        "sign": _display(series, number, value),
        "series": series,
        "number": number,
        "raw_flags": raw,
    }


def main() -> None:
    if len(sys.argv) > 1:
        text = Path(sys.argv[1]).read_text(encoding="utf-8")
        source = sys.argv[1]
    else:
        with urllib.request.urlopen(URL, timeout=120) as resp:
            text = resp.read().decode("utf-8")
        source = URL
    src_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    db = parse_database_js(text)

    # the signs payload: integer transnumeration → record; build the content-key
    # join table and the published sign list in one pass
    signs = []
    by_triple: dict[tuple[str, str, str], int] = {}
    for number, rec in map_items(db["signs"].fields[0]):
        found = _find_sign_record(rec)
        if found is None:
            signs.append({"number": number, "series": "", "value": "", "ref": ""})
            continue
        series, value, ref = _triple(found)
        by_triple[(series, value, ref)] = number
        signs.append(
            {
                "number": number,
                "series": series,
                "value": value,
                "ref": ref,
                "display": _display(series, number, value),
            }
        )
    print(f"signs: {len(signs)} ({len(by_triple)} joinable); series: "
          f"{sorted({s['series'] for s in signs if s['series']})}")

    documents = []
    for doc_id, wrapper in map_items(db["data"].fields[0]):
        doc = wrapper.fields[0]
        meta, image_path = doc.fields[0], doc.fields[1]
        dims = opt(meta.fields[6])
        atts_block = doc.fields[4]
        atts = []
        if isinstance(atts_block, Block):
            for att in atts_block.fields:
                atts.append(_attestation(att, by_triple))
        documents.append(
            {
                "id": doc_id,
                "typology": meta.fields[0],
                "site": meta.fields[2],
                "dimensions_cm": list(dims.fields) if isinstance(dims, Block) else None,
                "period": opt(meta.fields[7]),
                "reference_url": opt(meta.fields[8]),
                "image_path": image_path,
                "attestations": atts,
            }
        )

    out = {
        "_meta": {
            "title": "SigLA dataset (decoded) — The Signs of Linear A: a palæographical database",
            "license": "CC BY-NC-SA 4.0",
            "attribution": "Ester Salgarella and Simon Castellan, https://sigla.phis.me "
                           "(dataset and drawings published CC BY-NC-SA 4.0; the SigLA paper "
                           "notes that copies can be hosted and the data used outside the interface)",
            "cite": "Salgarella, E. & Castellan, S. (2020). SigLA. The Signs of Linear A: "
                    "a palæographical database. https://sigla.phis.me",
            "source": source,
            "source_sha256": src_sha,
            "generated": str(date.today()),
            "generator": "pyaegean scripts/build_sigla_corpus.py (OCaml-Marshal decode)",
            "note": "Field mapping is conservative: named fields are verified; raw_flags "
                    "preserve undecoded attestation integers. This version captures the "
                    "simple-sign (AB-series) attestations; complex signs, logograms, and "
                    "fraction signs use a different record shape and are not yet extracted. "
                    "Drawings are NOT included — they remain on sigla.phis.me.",
        },
        "documents": documents,
        "signs": signs,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n_att = sum(len(d["attestations"]) for d in documents)
    print(f"sigla-corpus.json: {len(documents)} documents, {n_att} attestations, {len(signs)} signs")
    print(f"source sha256: {src_sha[:16]}…")

    # ── cross-validation against the bundled GORILA corpus ──────────────────
    import aegean

    # bundled ids have no space ("HT13"); SigLA's do ("HT 13") — match on both
    bundled = {d.id.replace(" ", ""): d for d in aegean.load("lineara")}
    norm = lambda s: re.sub(r"[^A-Z0-9*]", "", s.upper())  # noqa: E731

    def sequences() -> Any:
        for d in documents:
            b = bundled.get(str(d["id"]).replace(" ", ""))
            if b is None or not d["attestations"]:
                continue
            sig_seq = [norm(a["sign"]) for a in d["attestations"] if a["sign"]]
            our_signs = [
                norm(s) for t in b.tokens for s in (t.signs if t.signs else (t.text,))
                if norm(s) and not norm(s).isdigit()
            ]
            if sig_seq:
                yield d["id"], sig_seq, our_signs

    def score(equiv: dict[str, str]) -> tuple[int, int, list[str]]:
        checked = agree = 0
        residue: list[str] = []
        for doc_id, sig_seq, our_signs in sequences():
            checked += 1
            ours_set = set(our_signs)
            overlap = sum(1 for s in sig_seq if s in ours_set or equiv.get(s) in ours_set)
            if overlap / len(sig_seq) >= 0.6:
                agree += 1
            elif len(residue) < 6:
                residue.append(f"{doc_id}: sigla {sig_seq[:6]} vs ours {our_signs[:6]}")
        return agree, checked, residue

    strict_agree, checked, _ = score({})
    # data-derived notation table: positionally align same-length documents and
    # harvest consistent (SigLA transnumeration ↔ lineara.xyz name) pairs — the
    # equivalences come from the two datasets themselves, not from memory
    from collections import Counter

    pair_counts: Counter[tuple[str, str]] = Counter()
    for _doc_id, sig_seq, our_signs in sequences():
        if len(sig_seq) == len(our_signs):
            for a, o in zip(sig_seq, our_signs):
                if a != o:
                    pair_counts[(a, o)] += 1
    equiv: dict[str, str] = {}
    for (a, o), n in pair_counts.most_common():
        if n >= 3 and a not in equiv:
            equiv[a] = o
    loose_agree, _, residue = score(equiv)
    print(f"cross-validation: strict {strict_agree}/{checked} documents at ≥60% sign overlap;")
    print(f"  with the {len(equiv)} data-derived notation equivalences "
          f"(e.g. *120↔GRA, *302↔OLE): {loose_agree}/{checked}")
    for d_ in residue:
        print("  ?", d_)


if __name__ == "__main__":
    main()
