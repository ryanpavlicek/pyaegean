"""Build the Linear B SignInventory from the bundled sign table.

The table is generated from the Unicode Character Database (``scripts/build_linearb_data.py``).
Linear B is deciphered, so the glyph↔value mapping is canonical (Unicode-assigned) and every
syllabogram carries a settled phonetic value — there is no empirical-confidence caveat as in
Linear A. Each sign keeps its Bennett number and Unicode name.
"""

from __future__ import annotations

from functools import lru_cache

from ...core.model import Sign, SignInventory
from ...data import load_bundled_json

_ATTR_KEYS = ("bennett", "unicodeName", "signClass", "commodity")


@lru_cache(maxsize=1)
def linear_b_inventory() -> SignInventory:
    raw = load_bundled_json("linearb", "signs.json")
    signs = [
        Sign(
            label=s["label"],
            glyph=s.get("glyph") or None,
            codepoint=s.get("codepoint"),
            phonetic=s.get("phonetic"),
            script_id="linearb",
            attrs={k: s[k] for k in _ATTR_KEYS if k in s},
        )
        for s in raw
    ]
    return SignInventory(signs, "linearb")
