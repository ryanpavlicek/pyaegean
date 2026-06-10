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
  is not inferred — it is lexical, not spelling-predictable — so a handful of
  Homeric lines that need it will not fit. ``scan_line`` raises
  `ScansionError` rather than guessing.
- Diaeresis (e.g. ``ϊ``) correctly blocks diphthong formation.
- Only dactylic meters are implemented here; lyric and iambic meters are future
  work (see ``docs/PLAN.md``).
"""

from __future__ import annotations

import re
import unicodedata
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
        i = 0
        first = True
        while i < len(chars):
            ch = chars[i]
            base = _strip_combining(ch).lower()
            if base in _VOWELS:
                text = ch
                if i + 1 < len(chars) and _strip_combining(chars[i + 1]).lower() in _VOWELS \
                        and _is_diphthong(ch, chars[i + 1]):
                    text += chars[i + 1]
                    i += 1
                items.append(_Item(True, text, base, word_idx, first))
            else:
                items.append(_Item(False, ch, base, word_idx, first))
            first = False
            i += 1
    return items


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
    texts = _partition_text(items, nuclei)
    syllables: list[_Syllable] = []
    for ni, pos in enumerate(nuclei):
        nucleus = items[pos]
        is_last = ni == len(nuclei) - 1
        following = items[pos + 1: nuclei[ni + 1]] if not is_last else items[pos + 1:]
        weight = _consonant_weight(following)
        category = _nucleus_category(nucleus.text)

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


_SCANNERS = {
    "hexameter": scan_hexameter,
    "pentameter": scan_pentameter,
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
