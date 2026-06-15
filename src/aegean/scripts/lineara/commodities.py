"""Linear A commodity logograms and the lexical-word filter.

A curated catalog of the commodity signs (ideograms) the accounting tablets
count — keyed by the logogram *head*, the part before any ligature ``+`` — plus
the helpers that classify a token as a commodity head, an undeciphered ``*NNN``
logogram, or a candidate *lexical* (syllabic) word.

Ported from the Linear A Research Workbench (``src/data/commodities.ts``).
Glosses follow the standard GORILA / Younger readings; the syllabic values of
the underlying signs are a separate question, and the ``*NNN`` numbered
logograms are genuinely undeciphered as to referent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "CommodityCategory",
    "CommodityDef",
    "COMMODITIES",
    "commodity_head",
    "is_undeciphered_logogram",
    "is_lexical_word",
]

# One of: "agricultural" | "livestock" | "people" | "material" | "vessel".
CommodityCategory = str


@dataclass(frozen=True)
class CommodityDef:
    """A commodity logogram's standard gloss and broad category."""

    gloss: str
    category: CommodityCategory


COMMODITIES: dict[str, CommodityDef] = {
    "GRA": CommodityDef("grain / wheat", "agricultural"),
    "HORD": CommodityDef("barley", "agricultural"),
    "OLE": CommodityDef("olive oil", "agricultural"),
    "OLIV": CommodityDef("olives", "agricultural"),
    "VIN": CommodityDef("wine", "agricultural"),
    "FIC": CommodityDef("figs", "agricultural"),
    "NI": CommodityDef("figs (logogram)", "agricultural"),
    "CYP": CommodityDef("cyperus (sedge / spice)", "agricultural"),
    "AROM": CommodityDef("aromatic", "agricultural"),
    "GRA_PA": CommodityDef("grain (qualified)", "agricultural"),
    "OVIS": CommodityDef("sheep", "livestock"),
    "CAP": CommodityDef("goat", "livestock"),
    "SUS": CommodityDef("pig", "livestock"),
    "BOS": CommodityDef("ox / cattle", "livestock"),
    "VIR": CommodityDef("man / person", "people"),
    "MUL": CommodityDef("woman", "people"),
    "TELA": CommodityDef("cloth", "material"),
    "LANA": CommodityDef("wool", "material"),
    "AES": CommodityDef("bronze", "material"),
    "AUR": CommodityDef("gold", "material"),
    "ARG": CommodityDef("silver", "material"),
}

_BRACKET_RE = re.compile(r"[\[\]?'\"]")
_SEX_RE = re.compile(r"[mf]$")
_STAR_RE = re.compile(r"^\*\d")
_DISQUALIFY_RE = re.compile(r"[+\[\]?]")
_STAR_NUM_RE = re.compile(r"^\*(\d+)")


def commodity_head(token: str) -> str | None:
    """The commodity head of a token, or ``None`` if it is not a known
    commodity logogram.

    Strips a ligature modifier (``OLE+U`` → ``OLE``), bracketed uncertainty
    (``VIR+[?]`` → ``VIR``) and a sex marker (``OVISm`` → ``OVIS``). A
    hyphenated token is a syllabic word, never a logogram, and returns
    ``None``."""
    if "-" in token:
        return None
    head = _BRACKET_RE.sub("", token.split("+")[0])
    if head in COMMODITIES:
        return head
    desexed = _SEX_RE.sub("", head)
    if desexed in COMMODITIES:
        return desexed
    return None


def is_undeciphered_logogram(token: str) -> bool:
    """Whether a token is an undeciphered ``*NNN`` numbered logogram."""
    return bool(_STAR_RE.match(token))


def is_lexical_word(word: str) -> bool:
    """Whether a hyphenated token is a candidate *lexical* word — a syllabic
    sign sequence — rather than a chain of logograms that merely tokenized with
    hyphens.

    Word-level analyses (graphotactic surprisal, anomaly lists) want real
    words, so ligatures (``+``), bracketed damage, commodity heads, and the
    GORILA ``*400+`` series (vessels, fractions, compound logograms — never
    word-internal syllabograms; the undeciphered syllabary candidates such as
    ``*301``/``*306`` sit below 400) all disqualify a token. A token whose every
    part is a ``*NNN`` logogram is a logogram chain too."""
    if "-" not in word:
        return False
    if _DISQUALIFY_RE.search(word):
        return False
    parts = word.split("-")
    starred = 0
    for p in parts:
        if commodity_head(p):
            return False
        m = _STAR_NUM_RE.match(p)
        if m:
            if int(m.group(1)) >= 400:
                return False
            starred += 1
    return starred < len(parts)
