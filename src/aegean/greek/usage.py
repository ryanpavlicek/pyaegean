"""Dialect and register tags for a Greek lemma, mined from its LSJ entry.

LSJ marks a word's **dialect** (Doric, Attic, Ionic, Aeolic, Epic, …) and **register**
(poetic, medical, comic, tragic, …) with standard abbreviations in the entry text. This
reads them off the active LSJ entry against a curated abbreviation map.

Heuristic: it matches the abbreviation tokens in the (flattened) entry text, so it surfaces
the tags LSJ records without resolving every nuance (an abbreviation that doubles as a
citation marker can occasionally slip through). Requires ``greek.use_lsj()``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["UsageInfo", "usage"]

# LSJ abbreviation -> tag (keys are lower-cased; matching is case-insensitive).
_DIALECTS = {
    "dor.": "doric", "att.": "attic", "ion.": "ionic", "aeol.": "aeolic", "ep.": "epic",
    "boeot.": "boeotian", "lacon.": "laconian", "cypr.": "cyprian", "cret.": "cretan",
    "arc.": "arcadian", "thess.": "thessalian", "lesb.": "lesbian", "delph.": "delphian",
    "megar.": "megarian",
}
_REGISTERS = {
    "poet.": "poetic", "medic.": "medical", "com.": "comic", "trag.": "tragic",
    "lyr.": "lyric", "rhet.": "rhetorical", "gramm.": "grammatical", "prov.": "proverbial",
    "colloq.": "colloquial",
}
_ABBR = re.compile(r"[A-Za-z]+\.")


@dataclass(frozen=True, slots=True)
class UsageInfo:
    """Dialect and register tags recorded for a lemma in LSJ."""

    dialects: tuple[str, ...]
    registers: tuple[str, ...]

    def __bool__(self) -> bool:
        return bool(self.dialects or self.registers)


def usage(word: str) -> UsageInfo:
    """Dialect and register tags for ``word`` from its LSJ entry (requires ``use_lsj``).

    Returns an empty `UsageInfo` if the word has no entry or no recognised tags. Raises
    `LexiconNotLoadedError` (via `lookup`) if the LSJ lexicon is not loaded."""
    from .lexicon import lookup

    entry = lookup(word)
    if entry is None:
        return UsageInfo((), ())
    text = " ".join([entry.lead, *(s.text for s in entry.senses)])
    dialects: list[str] = []
    registers: list[str] = []
    for tok in _ABBR.findall(text):
        key = tok.lower()
        d = _DIALECTS.get(key)
        if d and d not in dialects:
            dialects.append(d)
        r = _REGISTERS.get(key)
        if r and r not in registers:
            registers.append(r)
    return UsageInfo(tuple(dialects), tuple(registers))
