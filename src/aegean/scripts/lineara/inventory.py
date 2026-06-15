"""Build the Linear A SignInventory from the bundled sign table.

Coverage is the full Unicode Linear A block — the complete attested repertoire. The 47 signs
with an assigned **sound value** (``phonetic``) come from aligning the upstream transliterations
with parsed glyph strings: an *empirical* mapping, each carrying a ``confidence`` — treat it as
evidence, not canon. The rest are carried from the Unicode Character Database (``source="ucd"``)
with no sound value, since Linear A is undeciphered and most of its repertoire has no agreed
reading. Filter by ``phonetic`` (or ``attrs["source"]``) to work with just the read signs.
"""

from __future__ import annotations

from functools import lru_cache

from ...core.model import Sign, SignInventory
from ...data import load_bundled_json

_ATTR_KEYS = ("sharedWithLinearB", "linearAOnly", "total", "confidence", "altGlyphs", "source")


@lru_cache(maxsize=1)
def linear_a_inventory() -> SignInventory:
    raw = load_bundled_json("lineara", "signs.json")
    signs = [
        Sign(
            label=s["label"],
            glyph=s.get("glyph") or None,
            codepoint=s.get("codepoint"),
            phonetic=s.get("phonetic"),
            script_id="lineara",
            attrs={k: s[k] for k in _ATTR_KEYS if k in s},
        )
        for s in raw
    ]
    return SignInventory(signs, "lineara")
