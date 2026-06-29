"""Greek metrical scansion — fit a verse line to a quantitative template.

This is the step beyond per-syllable `aegean.greek.prosody`: it resolves
syllable quantities **across word boundaries** and fits the whole line to a
metrical pattern (dactylic hexameter, elegiac pentameter), recovering the feet,
the resolved long/short sequence, and the main caesura.

Method
------
1. Lay the line out as a single phoneme stream (apostrophes treated as elision,
   so the bare consonant joins the following onset). Word boundaries are kept so
   *correptio epica* can apply.
2. For each vowel nucleus, derive the **set of quantities it may carry**, not a
   single value:

   - **closed by position** (two or more consonants — or a double consonant
     ζ/ξ/ψ — before the next nucleus): heavy. A short vowel before a *muta cum
     liquida* (stop + liquid/nasal) cluster is *common* (heavy **or** light).
   - **open**: heavy if the nucleus is long (η, ω, circumflex, iota-subscript,
     or a diphthong); light if short (ε, ο); common for a *dichronon* (α, ι, υ),
     whose length is not fixed by spelling.
   - **correptio epica**: a word-final long vowel/diphthong in hiatus (directly
     before a vowel-initial word) may also scan short.
3. Fit the option sequence to the template by backtracking; the meter resolves
   the open ambiguities (dichrona, muta-cum-liquida, correptio). The first valid
   scansion is returned; ``ambiguous`` flags when more than one fits.

Limitations
-----------
- **Synizesis** (two written vowels read as one syllable, e.g. ``Πηληϊάδεω``)
  is **lexical**, not spelling-predictable, so it is never *inferred*. A curated
  ``_SYNIZESIS`` lexicon (contribution-friendly, test-enforced) lists the words
  where it is standard; a line needing synizesis on a word **not** in the lexicon
  still raises `ScansionError` rather than guessing.
- **Vowel length by nature** of a *dichronon* (α, ι, υ) is not recoverable from
  the spelling, so it too is **lexical**: a curated ``_LONG_BY_NATURE`` lexicon
  (contribution-friendly, test-enforced) records the words where a written α/ι/υ
  is long, which resolves lines (e.g. ψῡ- in ``ψυχάς``, Il. 1.3) the rules would
  otherwise leave genuinely ambiguous. A dichronon not in the lexicon stays
  common (heavy or light), never guessed in one direction.
- Diaeresis (e.g. ``ϊ``) correctly blocks diphthong formation.
- Meters: dactylic hexameter, elegiac pentameter, **iambic trimeter** (with
  resolution), and the **aeolic lyric lines** (glyconic, pherecratean, the sapphic
  and alcaic line types) as fixed quantity templates. Dactylo-epitrite and free
  astrophic lyric remain future work.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

HEAVY = "heavy"
LIGHT = "light"
ANCEPS = "anceps"

# Glyphs for the conventional notation.
_GLYPH = {HEAVY: "—", LIGHT: "⏑", ANCEPS: "×"}  # — ⏑ ×

_LONG_VOWELS = set("ηω")
_SHORT_VOWELS = set("εο")
_DICHRONA = set("αιυ")
_VOWELS = _LONG_VOWELS | _SHORT_VOWELS | _DICHRONA
_STOPS = set("πβφτδθκγχ")
_LIQUIDS_NASALS = set("λρμν")
_DOUBLE = set("ζξψ")  # count as two consonants ("long by position")
_DIPHTHONGS = {"αι", "ει", "οι", "υι", "αυ", "ευ", "ου", "ηυ", "ωυ"}

_CIRCUMFLEX = "͂"
_IOTA_SUBSCRIPT = "ͅ"
_DIAERESIS = "̈"
_APOSTROPHES = "'’ʼ᾽"
_GREEK_WORD = re.compile(r"[Ͱ-Ͽἀ-῿]+")

# Synizesis lexicon: words where two written vowels are standardly read as ONE
# metrical syllable. Keyed on the accent/diacritic-stripped lowercase word; the
# value is the adjacent vowel bigram that coalesces (its first occurrence). This
# is lexical knowledge, not a rule — each entry must be required by a real verse
# line that otherwise fails to scan, and is enforced by the test suite. Add a
# word here the way you would add a syllabification exception.
# Each value is the *two* written vowels that coalesce; entries needing a
# three-vowel coalescence (e.g. θεούς /θjuːs/) are out of this bigram model.
_SYNIZESIS: dict[str, str] = {
    "πηληιαδεω": "εω",   # Πηληϊάδεω (Il. 1.1) — the genitive ending -εω is one syllable
    "πολεως": "εω",      # πόλεως — Attic genitive, frequent in tragic trimeter
    "χρυσεω": "εω",      # χρυσέῳ and the like — adjectival -εω / -εῳ
    "θεους": "εου",      # θεούς — the three written vowels εου coalesce to one syllable
}


def _synizesis_bigram(word_match: str) -> str:
    """The vowel bigram that coalesces in ``word_match`` by synizesis, or ``""``."""
    return _SYNIZESIS.get(_strip_combining(word_match).lower(), "")


# Heavy-by-nature lexicon: words with a *dichronon* (α, ι, υ) that is long by
# nature here and so cannot be derived from the spelling. Without this knowledge
# such a vowel reads as `common` (heavy OR light), which leaves an otherwise
# determinate line genuinely ambiguous and lets the greedy dactyl-first fit pick
# a non-canonical (wrong) reading rather than the one the line actually has.
# Keyed on the accent/diacritic-stripped lowercase word; the value is the set of
# plain base vowels that are long at *every* occurrence in that word (so the
# override is sound applied to all of them). This is lexical knowledge, not a
# rule (like `_SYNIZESIS`): each entry must be required by a real verse line that
# otherwise mis-scans, and is enforced by the test suite. Add a word here the way
# you would add a syllabification exception.
_LONG_BY_NATURE: dict[str, frozenset[str]] = {
    # ψυχάς (Il. 1.3) — ψῡχή has a long υ by nature, and the first-declension
    # accusative-plural ending -ᾱς is long; both fix the line's third foot.
    "ψυχας": frozenset("υα"),
}


def _long_by_nature(word_match: str, base_vowel: str) -> bool:
    """Whether ``base_vowel`` is long by nature in ``word_match`` (lexical)."""
    return base_vowel in _LONG_BY_NATURE.get(_strip_combining(word_match).lower(), frozenset())


def _quantity_is_forced_long(word: str, base_vowel: str) -> bool:
    """Whether ``base_vowel`` is a *dichronon* that ``word`` actually contains, so
    the `_LONG_BY_NATURE` override genuinely changes the open-syllable reading from
    common to long (a dead entry would not). Used to test the lexicon."""
    return (
        base_vowel in _DICHRONA
        and base_vowel in _strip_combining(word).lower()
        and _long_by_nature(word, base_vowel)
    )


class ScansionError(ValueError):
    """Raised when a line cannot be fit to the requested meter."""


@dataclass(frozen=True, slots=True)
class Foot:
    """One metrical foot: its name and the syllables/quantities it spans."""

    name: str                          # dactyl | spondee | longum | biceps | final
    syllables: tuple[str, ...]
    quantities: tuple[str, ...]

    def __str__(self) -> str:
        return "".join(_GLYPH[q] for q in self.quantities)


@dataclass(frozen=True, slots=True)
class LineScansion:
    """The scansion of one verse line."""

    line: str
    meter: str
    feet: tuple[Foot, ...]
    syllables: tuple[str, ...]
    quantities: tuple[str, ...]
    caesura: str | None                # e.g. "penthemimeral" | "trochaic" | …
    caesura_index: int | None          # syllable index the caesura precedes
    ambiguous: bool                    # more than one scansion fit the template

    @property
    def pattern(self) -> str:
        """The classic glyph pattern, feet separated by ``|``."""
        return "|".join(str(f) for f in self.feet)

    def __str__(self) -> str:
        return self.pattern

    def _repr_html_(self) -> str:
        """Rich rendering in Jupyter/Colab (plain ``repr`` everywhere else)."""
        from ..core._html import card, esc, table

        sub = esc(self.meter)
        if self.caesura:
            sub += f" · {esc(self.caesura)} caesura"
        if self.ambiguous:
            sub += " · ambiguous"
        foot_rows = [(f.name, str(f), " ".join(f.syllables)) for f in self.feet]
        body = (
            f"<div style='margin-bottom:4px'>{esc(self.line)}</div>"
            f"<div style='font-size:1.4em;font-family:monospace;letter-spacing:2px'>"
            f"{esc(self.pattern)}</div>"
            f"<div style='color:#666;font-size:0.85em;margin:4px 0'>{sub}</div>"
            + table(["foot", "metre", "syllables"], foot_rows)
        )
        return card("Scansion", body)


# --- syllable analysis (line level) ------------------------------------------


@dataclass(frozen=True, slots=True)
class _Syllable:
    text: str
    options: frozenset[str]            # subset of {HEAVY, LIGHT}
    word_start: bool


def _strip_combining(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))


def _nucleus_category(vowels: str) -> str:
    """``"long"`` / ``"short"`` / ``"common"`` for a nucleus (vowel chars, NFC)."""
    nfd = unicodedata.normalize("NFD", vowels)
    if _CIRCUMFLEX in nfd or _IOTA_SUBSCRIPT in nfd:
        return "long"
    base = [c.lower() for c in nfd if not unicodedata.combining(c)]
    plain = "".join(c for c in base if c in _VOWELS)
    if len(plain) == 2:
        return "long"  # diphthong
    if plain in _LONG_VOWELS:
        return "long"
    if plain in _SHORT_VOWELS:
        return "short"
    return "common"


def _is_diphthong(first: str, second: str) -> bool:
    """Whether two adjacent vowels share a nucleus. A diaeresis on the second
    vowel (ϊ, ϋ) blocks it."""
    if _DIAERESIS in unicodedata.normalize("NFD", second):
        return False
    pair = _strip_combining(first).lower() + _strip_combining(second).lower()
    return pair in _DIPHTHONGS


@dataclass(frozen=True, slots=True)
class _Item:
    """A phoneme-stream item: a vowel nucleus or a single consonant."""

    is_vowel: bool
    text: str                          # original char(s)
    base: str                          # diacritic-stripped lowercase
    word_idx: int
    word_start: bool                   # first letter of its word


def _items(line: str) -> list[_Item]:
    """The line as an ordered phoneme stream, merging diphthongs. Apostrophes are
    dropped (elision), so the bare consonants flow into the following word."""
    nfc = unicodedata.normalize("NFC", line)
    for ap in _APOSTROPHES:
        nfc = nfc.replace(ap, "")
    items: list[_Item] = []
    for word_idx, match in enumerate(_GREEK_WORD.findall(nfc)):
        chars = list(match)
        syn = _synizesis_bigram(match)   # the vowel pair to coalesce, or ""
        syn_used = False
        i = 0
        first = True
        while i < len(chars):
            ch = chars[i]
            base = _strip_combining(ch).lower()
            if base in _VOWELS:
                text = ch
                nxt1 = _strip_combining(chars[i + 1]).lower() if i + 1 < len(chars) else ""
                nxt2 = _strip_combining(chars[i + 2]).lower() if i + 2 < len(chars) else ""
                if (
                    not syn_used and len(syn) == 3 and nxt1 in _VOWELS and nxt2 in _VOWELS
                    and base + nxt1 + nxt2 == syn
                ):
                    # this word's one synizesis trigram (e.g. θεούς: εου → one nucleus)
                    text += chars[i + 1] + chars[i + 2]
                    i += 2
                    syn_used = True
                elif nxt1 in _VOWELS:
                    nxt = chars[i + 1]
                    pair = base + nxt1
                    if _is_diphthong(ch, nxt) or (not syn_used and len(syn) == 2 and pair == syn):
                        # natural diphthong, or this word's one synizesis bigram
                        text += nxt
                        i += 1
                        if len(syn) == 2 and pair == syn:
                            syn_used = True
                items.append(_Item(True, text, base, word_idx, first))
            else:
                items.append(_Item(False, ch, base, word_idx, first))
            first = False
            i += 1
    return items


def _word_texts(line: str) -> list[str]:
    """The line's Greek words in order (NFC, apostrophes dropped) — the same word
    stream `_items` indexes by ``word_idx``."""
    nfc = unicodedata.normalize("NFC", line)
    for ap in _APOSTROPHES:
        nfc = nfc.replace(ap, "")
    return _GREEK_WORD.findall(nfc)


def _consonant_weight(cons: list[_Item]) -> int:
    """Effective consonant count for position (ζ/ξ/ψ count double)."""
    return sum(2 if c.base in _DOUBLE else 1 for c in cons)


def _is_muta_cum_liquida(cons: list[_Item]) -> bool:
    """A two-consonant cluster of stop + liquid/nasal (position is optional)."""
    return (
        len(cons) == 2
        and cons[0].base in _STOPS
        and cons[1].base in _LIQUIDS_NASALS
        and cons[0].base not in _DOUBLE
    )


def _analyze(line: str) -> list[_Syllable]:
    """Split the line into syllables, each with its set of possible quantities.

    Quantities use cross-word position; the written text of each syllable keeps
    its consonants within their own word (a word-final consonant codas the
    earlier syllable, a word-initial consonant onsets the later one), and an
    internal cluster splits by the largest valid Greek onset."""
    items = _items(line)
    nuclei = [k for k, it in enumerate(items) if it.is_vowel]
    if not nuclei:
        return []
    word_texts = _word_texts(line)
    texts = _partition_text(items, nuclei)
    syllables: list[_Syllable] = []
    for ni, pos in enumerate(nuclei):
        nucleus = items[pos]
        is_last = ni == len(nuclei) - 1
        following = items[pos + 1: nuclei[ni + 1]] if not is_last else items[pos + 1:]
        weight = _consonant_weight(following)
        category = _nucleus_category(nucleus.text)
        # Lexical override: a dichronon that is long by nature in this word reads
        # long, resolving an ambiguity the spelling cannot (e.g. ψῡ- in ψυχάς).
        if category == "common" and _long_by_nature(word_texts[nucleus.word_idx], nucleus.base):
            category = "long"

        if weight >= 2 and not _is_muta_cum_liquida(following):
            options = {HEAVY}                       # closed → long by position
        elif _is_muta_cum_liquida(following):
            options = {HEAVY} if category == "long" else {HEAVY, LIGHT}
        elif category == "long":
            options = {HEAVY}
        elif category == "short":
            options = {LIGHT}
        else:
            options = {HEAVY, LIGHT}                 # open dichronon

        # A syllable is word-initial when its nucleus opens a new word (the
        # word may begin with consonants, so test the word index, not the glyph).
        word_start = ni == 0 or items[nuclei[ni - 1]].word_idx != nucleus.word_idx
        next_word_start = (not is_last) and (
            items[nuclei[ni + 1]].word_idx != nucleus.word_idx
        )
        # Correptio epica: a word-final long vowel/diphthong in hiatus may shorten.
        if category == "long" and weight == 0 and next_word_start:
            options = options | {LIGHT}

        syllables.append(_Syllable(texts[ni], frozenset(options), word_start))
    return syllables


def _partition_text(items: list[_Item], nuclei: list[int]) -> list[str]:
    """Assign every item to exactly one syllable and rebuild each syllable's
    written text (no consonant is shared between two syllables)."""
    assign = [0] * len(items)
    for si, pos in enumerate(nuclei):
        assign[pos] = si
    for k in range(nuclei[0]):                       # leading consonants → first
        assign[k] = 0
    for k in range(nuclei[-1] + 1, len(items)):      # trailing consonants → last
        assign[k] = len(nuclei) - 1
    for si in range(len(nuclei) - 1):
        a, b = nuclei[si], nuclei[si + 1]
        run = list(range(a + 1, b))
        if not run:
            continue
        if items[b].word_idx == items[a].word_idx:   # internal cluster
            onset_len = _onset_length([items[k] for k in run])
            split = len(run) - onset_len
            for k in run[:split]:
                assign[k] = si
            for k in run[split:]:
                assign[k] = si + 1
        else:                                        # across a word boundary
            for k in run:
                assign[k] = si if items[k].word_idx == items[a].word_idx else si + 1
    texts = [""] * len(nuclei)
    for k, it in enumerate(items):
        texts[assign[k]] += it.text
    return texts


def _onset_length(cluster: list[_Item]) -> int:
    """How many trailing consonants of an internal cluster open the next
    syllable (mirrors `aegean.greek.syllabify`)."""
    n = len(cluster)
    if n <= 1:
        return n
    a, b = cluster[-2].base, cluster[-1].base
    if a != b and a in _STOPS and b in _LIQUIDS_NASALS:
        return 2
    valid = {
        "στ", "σπ", "σκ", "σφ", "σθ", "σχ", "σμ", "σβ",
        "πτ", "κτ", "φθ", "χθ", "πν", "κν", "γν", "δμ", "τμ", "θν", "πς",
        "βδ", "γδ",
    }
    return 2 if (a != b and a + b in valid) else 1


# --- template fitting --------------------------------------------------------


def _fits(option: frozenset[str], required: str) -> bool:
    return required in option


def _scan_dactylic(
    syllables: list[_Syllable], n_feet: int
) -> list[tuple[str, list[str]]] | None:
    """Fit a run of dactyls/spondees (``n_feet`` of them) followed by a final
    foot ``— ×``, returning ``[(foot_name, [quantities…]), …]`` or ``None``.

    Each of the ``n_feet`` feet is a dactyl (heavy + light + light) or spondee
    (heavy + heavy); the closing foot is one heavy plus an anceps."""
    opts = [s.options for s in syllables]
    n = len(opts)
    result: list[tuple[str, list[str]]] = []

    def rec(i: int, foot: int) -> bool:
        if foot == n_feet:
            # Closing foot: heavy + anceps, must end the line exactly.
            if i + 2 == n and _fits(opts[i], HEAVY):
                result.append(("final", [HEAVY, ANCEPS]))
                return True
            return False
        # Dactyl first (the unmarked Homeric foot), then spondee.
        if i + 3 <= n and _fits(opts[i], HEAVY) and _fits(opts[i + 1], LIGHT) and _fits(opts[i + 2], LIGHT):
            result.append(("dactyl", [HEAVY, LIGHT, LIGHT]))
            if rec(i + 3, foot + 1):
                return True
            result.pop()
        if i + 2 <= n and _fits(opts[i], HEAVY) and _fits(opts[i + 1], HEAVY):
            result.append(("spondee", [HEAVY, HEAVY]))
            if rec(i + 2, foot + 1):
                return True
            result.pop()
        return False

    return result if rec(0, 0) else None


def _count_dactylic(syllables: list[_Syllable], n_feet: int) -> int:
    """How many distinct dactylic scansions fit (capped at 2 — we only need to
    know whether it is ambiguous)."""
    opts = [s.options for s in syllables]
    n = len(opts)
    found = 0

    def rec(i: int, foot: int) -> None:
        nonlocal found
        if found >= 2:
            return
        if foot == n_feet:
            if i + 2 == n and _fits(opts[i], HEAVY):
                found += 1
            return
        if i + 3 <= n and _fits(opts[i], HEAVY) and _fits(opts[i + 1], LIGHT) and _fits(opts[i + 2], LIGHT):
            rec(i + 3, foot + 1)
        if i + 2 <= n and _fits(opts[i], HEAVY) and _fits(opts[i + 1], HEAVY):
            rec(i + 2, foot + 1)

    rec(0, 0)
    return found


def _assemble(
    line: str, meter: str, syllables: list[_Syllable], plan: list[tuple[str, list[str]]],
    ambiguous: bool, detect_caesura: bool,
) -> LineScansion:
    feet: list[Foot] = []
    quantities: list[str] = []
    foot_of_syll: list[int] = []
    idx = 0
    for fi, (name, quants) in enumerate(plan):
        span = syllables[idx:idx + len(quants)]
        feet.append(Foot(name, tuple(s.text for s in span), tuple(quants)))
        quantities.extend(quants)
        foot_of_syll.extend(fi for _ in quants)
        idx += len(quants)
    caesura, caesura_index = (None, None)
    if detect_caesura:
        caesura, caesura_index = _caesura(syllables, plan)
    return LineScansion(
        line=line,
        meter=meter,
        feet=tuple(feet),
        syllables=tuple(s.text for s in syllables),
        quantities=tuple(quantities),
        caesura=caesura,
        caesura_index=caesura_index,
        ambiguous=ambiguous,
    )


def _foot_starts(plan: list[tuple[str, list[str]]]) -> list[int]:
    """Syllable index at which each foot begins."""
    starts: list[int] = []
    idx = 0
    for _, quants in plan:
        starts.append(idx)
        idx += len(quants)
    return starts


def _caesura(
    syllables: list[_Syllable], plan: list[tuple[str, list[str]]]
) -> tuple[str | None, int | None]:
    """Locate the main caesura: a word break in the third foot — penthemimeral
    (after its long) or trochaic (after the first short of its biceps); failing
    that, a hephthemimeral break (after the long of the fourth foot)."""
    starts = _foot_starts(plan)
    if len(starts) < 4:
        return (None, None)
    third = starts[2]
    fourth = starts[3]
    # Penthemimeral: word break right after the longum of foot 3.
    if third + 1 < len(syllables) and syllables[third + 1].word_start:
        return ("penthemimeral", third + 1)
    # Trochaic: foot 3 is a dactyl and the break falls after its first short.
    if plan[2][0] == "dactyl" and third + 2 < len(syllables) and syllables[third + 2].word_start:
        return ("trochaic", third + 2)
    # Hephthemimeral: word break after the longum of foot 4.
    if fourth + 1 < len(syllables) and syllables[fourth + 1].word_start:
        return ("hephthemimeral", fourth + 1)
    return (None, None)


# --- public API --------------------------------------------------------------


def scan_hexameter(line: str) -> LineScansion:
    """Scan a line of **dactylic hexameter** (six feet; feet 1–5 dactyl or
    spondee, foot 6 ``— ×``), resolving quantities and the main caesura.

    Raises `ScansionError` if the line does not fit (e.g. it needs
    synizesis, which is not inferred)."""
    syllables = _analyze(line)
    plan = _scan_dactylic(syllables, n_feet=5)
    if plan is None:
        raise ScansionError(
            f"line does not scan as dactylic hexameter "
            f"({len(syllables)} syllables): {line!r}"
        )
    ambiguous = _count_dactylic(syllables, n_feet=5) > 1
    return _assemble(line, "hexameter", syllables, plan, ambiguous, detect_caesura=True)


def scan_pentameter(line: str) -> LineScansion:
    """Scan a line of **elegiac pentameter**: two dactyls-or-spondees, a longum,
    the central diaeresis, then two obligatory dactyls and a final longum
    (``— ⏑⏑ — ⏑⏑ — ‖ — ⏑⏑ — ⏑⏑ —``).

    Raises `ScansionError` if the line does not fit."""
    syllables = _analyze(line)
    plan = _scan_pentameter(syllables)
    if plan is None:
        raise ScansionError(
            f"line does not scan as elegiac pentameter "
            f"({len(syllables)} syllables): {line!r}"
        )
    ambiguous = _count_pentameter(syllables) > 1
    return _assemble(line, "pentameter", syllables, plan, ambiguous, detect_caesura=False)


def _scan_pentameter(syllables: list[_Syllable]) -> list[tuple[str, list[str]]] | None:
    opts = [s.options for s in syllables]
    n = len(opts)
    result: list[tuple[str, list[str]]] = []

    def first_half(i: int, foot: int) -> int | None:
        """Two dactyl/spondee feet then a single longum (the hemiepes). Returns
        the index after the longum, or ``None``."""
        if foot == 2:
            if i < n and _fits(opts[i], HEAVY):
                result.append(("longum", [HEAVY]))
                return i + 1
            return None
        if i + 3 <= n and _fits(opts[i], HEAVY) and _fits(opts[i + 1], LIGHT) and _fits(opts[i + 2], LIGHT):
            result.append(("dactyl", [HEAVY, LIGHT, LIGHT]))
            nxt = first_half(i + 3, foot + 1)
            if nxt is not None:
                return nxt
            result.pop()
        if i + 2 <= n and _fits(opts[i], HEAVY) and _fits(opts[i + 1], HEAVY):
            result.append(("spondee", [HEAVY, HEAVY]))
            nxt = first_half(i + 2, foot + 1)
            if nxt is not None:
                return nxt
            result.pop()
        return None

    mid = first_half(0, 0)
    if mid is None:
        return None
    # Second hemiepes: two obligatory dactyls + a final anceps longum.
    if mid + 7 != n:
        return None
    for d in range(2):
        base = mid + d * 3
        if not (_fits(opts[base], HEAVY) and _fits(opts[base + 1], LIGHT) and _fits(opts[base + 2], LIGHT)):
            return None
        result.append(("dactyl", [HEAVY, LIGHT, LIGHT]))
    if not _fits(opts[mid + 6], HEAVY):
        return None
    result.append(("longum", [ANCEPS]))
    return result


def _count_pentameter(syllables: list[_Syllable]) -> int:
    """Distinct pentameter fits (capped at 2)."""
    opts = [s.options for s in syllables]
    n = len(opts)
    found = 0

    def first_half(i: int, foot: int) -> None:
        nonlocal found
        if found >= 2:
            return
        if foot == 2:
            if i < n and _fits(opts[i], HEAVY):
                _second_half(i + 1)
            return
        if i + 3 <= n and _fits(opts[i], HEAVY) and _fits(opts[i + 1], LIGHT) and _fits(opts[i + 2], LIGHT):
            first_half(i + 3, foot + 1)
        if i + 2 <= n and _fits(opts[i], HEAVY) and _fits(opts[i + 1], HEAVY):
            first_half(i + 2, foot + 1)

    def _second_half(mid: int) -> None:
        nonlocal found
        if mid + 7 != n:
            return
        for d in range(2):
            base = mid + d * 3
            if not (_fits(opts[base], HEAVY) and _fits(opts[base + 1], LIGHT) and _fits(opts[base + 2], LIGHT)):
                return
        if _fits(opts[mid + 6], HEAVY):
            found += 1

    first_half(0, 0)
    return found


# --- iambic trimeter ---------------------------------------------------------

# The twelve elements of the iambic trimeter — three metra of ``x – ⏑ –``, with
# the final element anceps (brevis in longo). ``resolvable`` marks a longum that
# tragic/comic practice may realise as two shorts (resolution); the bre­ves and
# the line-final element are never resolved.
_TRIMETER: tuple[tuple[str, bool], ...] = (
    (ANCEPS, False), (HEAVY, True), (LIGHT, False), (HEAVY, True),   # metron 1
    (ANCEPS, False), (HEAVY, True), (LIGHT, False), (HEAVY, True),   # metron 2
    (ANCEPS, False), (HEAVY, True), (LIGHT, False), (ANCEPS, False),  # metron 3
)


def _fits_element(option: frozenset[str], quantity: str) -> bool:
    """An anceps element accepts any syllable; otherwise the quantity must be
    among the syllable's options."""
    return quantity == ANCEPS or quantity in option


def _scan_trimeter(
    syllables: list[_Syllable],
) -> tuple[list[tuple[str, list[str]]], list[int]] | None:
    """Fit the line to iambic trimeter, allowing resolution of long elements.

    Returns ``(plan, element_starts)`` — the three metra as feet, plus the
    syllable index at which each of the twelve elements begins (for the
    caesura) — or ``None`` if it does not fit."""
    opts = [s.options for s in syllables]
    n = len(opts)
    quants: list[str] = []          # realised quantity per syllable, in order
    starts = [0] * len(_TRIMETER)

    def rec(i: int, el: int) -> bool:
        if el == len(_TRIMETER):
            return i == n
        starts[el] = i
        quantity, resolvable = _TRIMETER[el]
        if i < n and _fits_element(opts[i], quantity):
            quants.append(quantity)          # one syllable fills the element
            if rec(i + 1, el + 1):
                return True
            quants.pop()
        if resolvable and i + 1 < n and LIGHT in opts[i] and LIGHT in opts[i + 1]:
            quants.extend((LIGHT, LIGHT))     # resolution: longum → two shorts
            if rec(i + 2, el + 1):
                return True
            del quants[-2:]
        return False

    if not rec(0, 0):
        return None
    # group the realised quantities into the three metra by element boundaries
    plan = [
        ("metron", quants[starts[0]:starts[4]]),
        ("metron", quants[starts[4]:starts[8]]),
        ("metron", quants[starts[8]:n]),
    ]
    return plan, starts


def _count_trimeter(syllables: list[_Syllable]) -> int:
    """Distinct trimeter fits (capped at 2 — only ambiguity matters)."""
    opts = [s.options for s in syllables]
    n = len(opts)
    found = 0

    def rec(i: int, el: int) -> None:
        nonlocal found
        if found >= 2:
            return
        if el == len(_TRIMETER):
            if i == n:
                found += 1
            return
        quantity, resolvable = _TRIMETER[el]
        if i < n and _fits_element(opts[i], quantity):
            rec(i + 1, el + 1)
        if resolvable and i + 1 < n and LIGHT in opts[i] and LIGHT in opts[i + 1]:
            rec(i + 2, el + 1)

    rec(0, 0)
    return found


def _caesura_trimeter(
    syllables: list[_Syllable], starts: list[int]
) -> tuple[str | None, int | None]:
    """The trimeter caesura: a word break after the 5th element (penthemimeral)
    or, failing that, after the 7th (hephthemimeral)."""
    penth = starts[5]
    heph = starts[7]
    if penth < len(syllables) and syllables[penth].word_start:
        return ("penthemimeral", penth)
    if heph < len(syllables) and syllables[heph].word_start:
        return ("hephthemimeral", heph)
    return (None, None)


def scan_trimeter(line: str) -> LineScansion:
    """Scan a line of **iambic trimeter** — three metra of ``x – ⏑ –`` (the final
    element anceps), with resolution of long elements into two shorts.

    Raises `ScansionError` if the line does not fit (e.g. it needs synizesis on
    a word not in the lexicon)."""
    syllables = _analyze(line)
    fit = _scan_trimeter(syllables)
    if fit is None:
        raise ScansionError(
            f"line does not scan as iambic trimeter "
            f"({len(syllables)} syllables): {line!r}"
        )
    plan, starts = fit
    ambiguous = _count_trimeter(syllables) > 1
    scansion = _assemble(line, "trimeter", syllables, plan, ambiguous, detect_caesura=False)
    caesura, caesura_index = _caesura_trimeter(syllables, starts)
    from dataclasses import replace as _replace
    return _replace(scansion, caesura=caesura, caesura_index=caesura_index)


# --- aeolic lyric lines (fixed quantity templates) ---------------------------

# Each aeolic line is a fixed sequence of quantities (the choriambic nucleus does not
# resolve). Interior ANCEPS positions are the "aeolic base"; the final position is ANCEPS
# for brevis in longo. A line scans iff every syllable can take its position's quantity
# (an ANCEPS position accepts either) — no resolution, so it is a straight template match.
_AEOLIC: dict[str, tuple[str, ...]] = {
    # glyconic — × × — ⏑ ⏑ — ⏑ ×  (aeolic base + choriamb + ⏑ —)
    "glyconic": (ANCEPS, ANCEPS, HEAVY, LIGHT, LIGHT, HEAVY, LIGHT, ANCEPS),
    # pherecratean — × × — ⏑ ⏑ — ×  (catalectic glyconic)
    "pherecratean": (ANCEPS, ANCEPS, HEAVY, LIGHT, LIGHT, HEAVY, ANCEPS),
    # sapphic hendecasyllable — — ⏑ — × — ⏑ ⏑ — ⏑ — ×
    "sapphic_hendecasyllable": (
        HEAVY, LIGHT, HEAVY, ANCEPS, HEAVY, LIGHT, LIGHT, HEAVY, LIGHT, HEAVY, ANCEPS,
    ),
    # adonean — — ⏑ ⏑ — ×  (the close of the sapphic stanza)
    "adonean": (HEAVY, LIGHT, LIGHT, HEAVY, ANCEPS),
    # alcaic hendecasyllable — × — ⏑ — × — ⏑ ⏑ — ⏑ ×
    "alcaic_hendecasyllable": (
        ANCEPS, HEAVY, LIGHT, HEAVY, ANCEPS, HEAVY, LIGHT, LIGHT, HEAVY, LIGHT, ANCEPS,
    ),
    # alcaic enneasyllable — × — ⏑ — × — ⏑ — ×
    "alcaic_enneasyllable": (ANCEPS, HEAVY, LIGHT, HEAVY, ANCEPS, HEAVY, LIGHT, HEAVY, ANCEPS),
    # alcaic decasyllable — — ⏑ ⏑ — ⏑ ⏑ — ⏑ — ×
    "alcaic_decasyllable": (
        HEAVY, LIGHT, LIGHT, HEAVY, LIGHT, LIGHT, HEAVY, LIGHT, HEAVY, ANCEPS,
    ),
}

AEOLIC_LINES: tuple[str, ...] = tuple(_AEOLIC)  # the supported aeolic line names


def _scan_aeolic(syllables: list[_Syllable], template: tuple[str, ...]) -> list[str] | None:
    """Fit syllables to a fixed aeolic quantity template, or ``None`` if they do not match."""
    opts = [s.options for s in syllables]
    if len(opts) != len(template):
        return None
    quantities: list[str] = []
    for opt, code in zip(opts, template):
        if code == ANCEPS:
            quantities.append(ANCEPS)
        elif _fits(opt, code):
            quantities.append(code)
        else:
            return None
    return quantities


def scan_aeolic(line: str, line_type: str = "glyconic") -> LineScansion:
    """Scan an **aeolic lyric line** against a fixed quantity template.

    ``line_type`` is one of `AEOLIC_LINES` — ``"glyconic"``, ``"pherecratean"``,
    ``"sapphic_hendecasyllable"``, ``"adonean"``, ``"alcaic_hendecasyllable"``,
    ``"alcaic_enneasyllable"``, ``"alcaic_decasyllable"``. These are fixed patterns (the
    choriamb does not resolve), so the line either matches or it doesn't — `ScansionError`
    is raised on a mismatch (e.g. the wrong syllable count, or a line needing synizesis on a
    word not in the lexicon)."""
    if line_type not in _AEOLIC:
        raise ScansionError(
            f"unknown aeolic line {line_type!r}; available: {', '.join(sorted(_AEOLIC))}"
        )
    template = _AEOLIC[line_type]
    syllables = _analyze(line)
    quantities = _scan_aeolic(syllables, template)
    if quantities is None:
        raise ScansionError(
            f"line does not scan as {line_type} "
            f"({len(syllables)} syllables, expected {len(template)}): {line!r}"
        )
    plan = [(line_type, quantities)]
    return _assemble(line, line_type, syllables, plan, ambiguous=False, detect_caesura=False)


def _aeolic_scanner(line_type: str) -> Callable[[str], LineScansion]:
    """A single-argument scanner bound to one aeolic ``line_type`` (for ``_SCANNERS``)."""
    def _scan(line: str) -> LineScansion:
        return scan_aeolic(line, line_type)

    return _scan


_SCANNERS: dict[str, Callable[[str], LineScansion]] = {
    "hexameter": scan_hexameter,
    "pentameter": scan_pentameter,
    "trimeter": scan_trimeter,
    **{name: _aeolic_scanner(name) for name in _AEOLIC},
}


def scan_line(line: str, meter: str = "hexameter") -> LineScansion:
    """Scan ``line`` against ``meter`` (``"hexameter"`` or ``"pentameter"``)."""
    try:
        scanner = _SCANNERS[meter]
    except KeyError:
        raise ScansionError(
            f"unknown meter {meter!r}; available: {', '.join(sorted(_SCANNERS))}"
        ) from None
    return scanner(line)


def syllable_options(line: str) -> list[tuple[str, list[str]]]:
    """``(syllable, [possible quantities])`` across the whole line — the raw,
    pre-metrical analysis, with cross-word position and correptio applied."""
    return [
        (s.text, sorted(s.options))
        for s in _analyze(line)
    ]
