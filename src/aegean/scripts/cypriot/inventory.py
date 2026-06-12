"""Build the Cypriot syllabary SignInventory from the bundled sign table.

Generated from the Unicode Character Database (``scripts/build_cypriot_data.py``). The Cypriot
syllabary is deciphered, so the glyph↔value mapping is canonical and every sign carries a settled
phonetic value.
"""

from __future__ import annotations

from functools import lru_cache

from ...core.model import Sign, SignInventory
from ...data import load_bundled_json

_ATTR_KEYS = ("unicodeName", "signClass")


@lru_cache(maxsize=1)
def cypriot_inventory() -> SignInventory:
    raw = load_bundled_json("cypriot", "signs.json")
    signs = [
        Sign(
            label=s["label"],
            glyph=s.get("glyph") or None,
            codepoint=s.get("codepoint"),
            phonetic=s.get("phonetic"),
            script_id="cypriot",
            attrs={k: s[k] for k in _ATTR_KEYS if k in s},
        )
        for s in raw
    ]
    return SignInventory(signs, "cypriot")
