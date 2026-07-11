"""Rebuild SigLA's JSON database from its published web-app payload.

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


_SUBSCRIPT = {str(d): chr(0x2080 + d) for d in range(10)}  # '2' → '₂' (U+2082)


def _subscript(digits: str) -> str:
    """Homophone index as Unicode subscript digits (``2`` → ``₂``), matching the
    bundled GORILA lineara corpus's sign-label convention (RA₂, PU₂, TA₂)."""
    return "".join(_SUBSCRIPT.get(c, c) for c in digits)


def _find_pair(v: Any, depth: int = 0) -> Block | None:
    """The (base, option) transliteration pair: an OCaml tuple block whose first
    field is the base string. field[2] wraps it as ``Some (base, option)``
    (``B0[B0['ra', option]]``), so this descends past the option wrapper."""
    if isinstance(v, Block):
        if len(v.fields) >= 2 and isinstance(v.fields[0], str):
            return v
        if depth < 6:
            for f in v.fields:
                hit = _find_pair(f, depth + 1)
                if hit is not None:
                    return hit
    return None


def _option_string(opt: Any) -> str:
    """The homophone option component (OCaml ``string option``): ``0`` = None (no
    homophone index), ``B0[x]`` = Some x. SigLA encodes RA₂/PU₂/TA₂ as the base
    ``'ra'``/``'pu'``/``'ta'`` with option ``Some '2'``; plain RA/PU/TA carry
    ``None``."""
    if isinstance(opt, Block) and opt.tag == 0 and len(opt.fields) == 1:
        inner = opt.fields[0]
        return inner if isinstance(inner, str) else _first_string(inner)
    return ""


def _transliteration(f2: Any) -> str:
    """The sign's transliteration from field[2] = ``Some (base, option)``: the
    base syllabogram value with its homophone index appended as a Unicode
    subscript. SigLA stores homophones as a (base, option) pair, e.g.
    AB76 = ``('ra', Some '2')`` → ``ra₂``; the option is absent (``None``) on the
    plain signs AB60 ``ra`` / AB50 ``pu`` / AB59 ``ta``. Dropping the option
    collapses distinct signs (RA₂ ≠ RA), so it is preserved here."""
    pair = _find_pair(f2)
    if pair is None:
        return _first_string(f2)
    base = pair.fields[0]
    if not isinstance(base, str):
        return _first_string(f2)
    option = _option_string(pair.fields[1])
    return base + _subscript(option) if option else base


def _triple(rec: Block) -> tuple[str, str, str]:
    """(series, transliteration, representative drawing ref) — the content key.

    The ``data`` and ``signs`` payloads are separate Marshal values, so their
    sign records are copies, not shared objects; this triple joins them (the
    representative ref, e.g. ``KH 5/5``, is unique per sign). The transliteration
    keeps its homophone subscript (RA₂, PU₂, TA₂; `_transliteration`); the ref is
    a plain string."""
    return str(rec.fields[0]), _transliteration(rec.fields[2]), _first_string(rec.fields[3])


def _display(series: str, number: int | None, value: str) -> str:
    """The sign as pyaegean's corpus writes it: transliteration for the
    deciphered-convention AB signs, ``*NNN`` for the Linear-A-only signs."""
    if value:
        return value.upper()
    if number is not None:
        return f"*{number}"
    return ""


def _logogram(rec: Block) -> str:
    """The commodity/ideogram name: field[4] = Some 'VIN', or the composite
    field[8] = Some '*100+*77' (e.g. VIR+KA). Empty for a plain syllabogram."""
    for idx in (4, 8):
        f = rec.fields[idx]
        if isinstance(f, Block) and f.tag == 0 and len(f.fields) == 1 and isinstance(f.fields[0], str):
            name = f.fields[0]
            if name and name != "num":  # 'num' marks a numeral sign, not a logogram name
                return name
    return ""


def _is_fraction(rec: Block) -> bool:
    """A Linear A fraction sign (field[7] = Some ('Fraction sign.', …))."""
    f7 = rec.fields[7]
    return isinstance(f7, Block) and "Fraction" in _first_string(f7)


def _word_index(att: Block) -> int | None:
    """SigLA encodes word membership in field[3]: an in-word sign carries the
    nested ``B0(2)[B0(2)[position, word], 0]``; a standalone sign/logogram/
    fraction carries a flat pair. Returns the word index, or ``None`` for a
    standalone item — this is what lets the sign stream be grouped into words."""
    if not (isinstance(att, Block) and len(att.fields) > 3):
        return None
    f3 = att.fields[3]
    if isinstance(f3, Block) and len(f3.fields) == 2 and isinstance(f3.fields[0], Block):
        inner = f3.fields[0]
        if len(inner.fields) == 2 and all(isinstance(x, int) for x in inner.fields):
            return int(inner.fields[1])
    return None


def _attestation(
    att: Any,
    by_triple: dict[tuple[str, str, str], int],
    by_number: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """One attestation → a record carrying the resolved sign, its **kind**
    (``syllable`` / ``logogram`` / ``fraction`` / ``blank``) and its **word
    index** (None = standalone), so the loader can rebuild words and ideograms.
    Anything not interpreted is preserved in ``raw_flags``."""
    raw = [f for f in att.fields if isinstance(f, int)] if isinstance(att, Block) else []
    word = _word_index(att) if isinstance(att, Block) else None
    rec = _find_sign_record(att) if isinstance(att, Block) else None
    if rec is None:
        return {"sign": "", "kind": "blank", "word": word, "series": "", "number": None,
                "raw_flags": raw}
    series, value, ref = _triple(rec)
    number = by_triple.get((series, value, ref))
    num = rec.fields[1] if isinstance(rec.fields[1], int) else number

    # A sign *inside a word* (word index set) is a syllabogram — never read it as
    # the homograph logogram (e.g. word-internal NI is the syllable, not the fig
    # ideogram). Standalone signs may be logograms or fractions.
    if word is None:
        if _is_fraction(rec):
            return {"sign": "", "kind": "fraction", "word": word, "series": series,
                    "number": num, "raw_flags": raw}
        logo = _logogram(rec)
        if logo:
            return {"sign": logo, "kind": "logogram", "word": word, "series": series,
                    "number": number, "raw_flags": raw}
    if value:
        return {"sign": value.upper(), "kind": "syllable", "word": word, "series": series,
                "number": number, "raw_flags": raw}
    # value absent on this attestation copy — resolve via the signs table by its
    # transnumeration (recovers KU-ZU-NI-style internal gaps and *NNN A-signs)
    resolved = by_number.get(num) if num is not None else None
    if resolved and resolved["display"]:
        kind = "syllable" if word is not None else resolved["kind"]
        return {"sign": resolved["display"], "kind": kind, "word": word,
                "series": resolved["series"], "number": num, "raw_flags": raw}
    return {"sign": "", "kind": "blank", "word": word, "series": series,
            "number": num, "raw_flags": raw}


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
    # join table, the reverse number→resolution map (for blank attestations), and
    # the published sign list in one pass
    signs = []
    by_triple: dict[tuple[str, str, str], int] = {}
    by_number: dict[int, dict[str, Any]] = {}
    for number, rec in map_items(db["signs"].fields[0]):
        found = _find_sign_record(rec)
        if found is None:
            signs.append({"number": number, "series": "", "value": "", "ref": ""})
            continue
        series, value, ref = _triple(found)
        by_triple[(series, value, ref)] = number
        logo = _logogram(found)
        if value:
            kind, disp = "syllable", value.upper()
        elif logo:
            kind, disp = "logogram", logo
        elif _is_fraction(found):
            kind, disp = "fraction", ""
        else:
            kind, disp = ("syllable" if series == "A" else "blank"), _display(series, number, value)
        by_number[number] = {"display": disp, "kind": kind, "series": series}
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
                atts.append(_attestation(att, by_triple, by_number))
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

    n_words = sum(
        1 for d in documents
        for w in {a["word"] for a in d["attestations"] if a.get("word") is not None}
    )
    n_logo = sum(1 for d in documents for a in d["attestations"] if a.get("kind") == "logogram")
    out = {
        "_meta": {
            "title": "SigLA dataset (decoded) — The Signs of Linear A: a palæographical database",
            "version": 2,
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
                    "preserve undecoded attestation integers. v2 adds, per attestation, the "
                    "SigLA word grouping (`word` index; None = standalone) and a `kind` "
                    "(syllable / logogram / fraction / blank), with blank syllabogram values "
                    "resolved via the signs-table transnumeration. SigLA is a PALAEOGRAPHIC "
                    "sign database: it records sign occurrences and word division, NOT the "
                    "cardinal-number quantities of the accounts, so no numeral values are "
                    "emitted. Word division and complex-sign notation are SigLA's own and "
                    "differ editorially from GORILA. Drawings are NOT included — they remain "
                    "on sigla.phis.me.",
        },
        "documents": documents,
        "signs": signs,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n_att = sum(len(d["attestations"]) for d in documents)
    print(f"sigla-corpus.json: {len(documents)} documents, {n_att} attestations, "
          f"{n_words} words, {n_logo} logograms, {len(signs)} signs")
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
