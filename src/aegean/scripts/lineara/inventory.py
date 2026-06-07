"""Build the Linear A SignInventory from the bundled 84-sign table.

Note: the sign↔Unicode mapping is *empirical* (derived by aligning the
upstream transliterations with parsed glyph strings); each sign carries a
``confidence``. Treat the glyph mapping as evidence, not canon.
"""

from __future__ import annotations

from functools import lru_cache

from ...core.model import Sign, SignInventory
from ...data import load_bundled_json

_ATTR_KEYS = ("sharedWithLinearB", "linearAOnly", "total", "confidence", "altGlyphs")


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
