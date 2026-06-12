"""Build the Cypro-Minoan SignInventory from the bundled sign table.

Generated from the Unicode Character Database (``scripts/build_cyprominoan_data.py``). Cypro-Minoan
is **undeciphered**, so each sign carries only its conventional number (``CM001`` …) and glyph — no
phonetic value. Treat the inventory as a catalogue of distinct signs, not a syllabary with sounds.
"""

from __future__ import annotations

from functools import lru_cache

from ...core.model import Sign, SignInventory
from ...data import load_bundled_json

_ATTR_KEYS = ("unicodeName", "signClass")


@lru_cache(maxsize=1)
def cyprominoan_inventory() -> SignInventory:
    raw = load_bundled_json("cyprominoan", "signs.json")
    signs = [
        Sign(
            label=s["label"],
            glyph=s.get("glyph") or None,
            codepoint=s.get("codepoint"),
            phonetic=s.get("phonetic"),  # always None — the script is undeciphered
            script_id="cyprominoan",
            attrs={k: s[k] for k in _ATTR_KEYS if k in s},
        )
        for s in raw
    ]
    return SignInventory(signs, "cyprominoan")
