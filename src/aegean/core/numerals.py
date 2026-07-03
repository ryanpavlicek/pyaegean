"""Aegean numerals + accounting reconciliation.

A faithful Python port of the workbench's ``src/lib/numerals.ts``: parse the
decimal numerals and metrological fractions that appear in Linear A tablets,
and verify KU-RO / PO-TO-KU-RO totals against the summed line items.

Ported to match the TypeScript workbench (see the shared golden fixtures): a
KU-RO subtotal reconciles against the items since the previous total, and a
PO-TO-KU-RO grand total against the stated subtotals that precede it. One
intentional divergence: every stated total yields a check here, so a leading or
otherwise item-less total surfaces as an explicit zero-item section rather than
being silently dropped. The accounting reconciliation is an *exploratory*
reading: section boundaries are heuristic and the metrology is scholarly-contested.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_SUPERSCRIPTS = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
}
_SUBSCRIPTS = {
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
}
_PRECOMPOSED = {
    "½": 1 / 2, "⅓": 1 / 3, "⅔": 2 / 3, "¼": 1 / 4, "¾": 3 / 4,
    "⅕": 1 / 5, "⅖": 2 / 5, "⅗": 3 / 5, "⅘": 4 / 5,
    "⅙": 1 / 6, "⅚": 5 / 6, "⅛": 1 / 8, "⅜": 3 / 8, "⅝": 5 / 8, "⅞": 7 / 8,
}


def _map_digits(s: str, table: dict[str, str]) -> str | None:
    out = []
    for ch in s:
        d = table.get(ch)
        if d is None:
            return None
        out.append(d)
    return "".join(out) if out else None


def parse_value(token: str) -> float | None:
    """Parse a single token into a number, or ``None`` if it isn't a numeral.

    Handles plain integers, built-up fractions (³⁄₄), precomposed vulgar
    fractions (¾), and approximate readings ("≈ ¹⁄₆"): the "≈" prefixes an
    editor-estimated reading of a damaged or unclear quantity, so the value is
    the editor's best reading and sums at face value. The ≈ qualifier is
    editorial apparatus (like the marks the account-line classifier skips) and
    is not propagated; a bare "≈" with nothing legible after it is not a value.
    """
    t = re.sub(r"^≈\s*", "", token.strip())
    if not t:
        return None
    if re.fullmatch(r"\d+", t):
        return int(t)
    if t in _PRECOMPOSED:
        return _PRECOMPOSED[t]
    parts = re.split(r"[⁄/]", t)  # fraction slash or ASCII slash
    if len(parts) == 2:
        num = _map_digits(parts[0], _SUPERSCRIPTS) or parts[0]
        den = _map_digits(parts[1], _SUBSCRIPTS) or parts[1]
        try:
            n, d = float(num), float(den)
        except ValueError:
            return None
        if math.isfinite(n) and math.isfinite(d) and d != 0:
            return n / d
    return None


def is_value_token(token: str) -> bool:
    return parse_value(token) is not None


def line_value(tokens: list[str]) -> float:
    """Sum every numeric token in a line (0 if none)."""
    total = 0.0
    for tk in tokens:
        v = parse_value(tk)
        if v is not None:
            total += v
    return total


def has_value(tokens: list[str]) -> bool:
    return any(is_value_token(tk) for tk in tokens)


_FRACTION_GLYPHS: list[tuple[float, str]] = [
    (1 / 2, "½"), (1 / 3, "⅓"), (2 / 3, "⅔"), (1 / 4, "¼"), (3 / 4, "¾"),
    (1 / 6, "⅙"), (5 / 6, "⅚"), (1 / 8, "⅛"), (3 / 8, "⅜"), (5 / 8, "⅝"),
    (7 / 8, "⅞"), (1 / 16, "¹⁄₁₆"), (1 / 5, "⅕"),
]


def format_value(v: float) -> str:
    """Render a value with a metrological fraction glyph when recognised.

    Works on the magnitude so a negative mixed number keeps its sign and its whole
    part (-1.5 renders "-1½", not "½"); math.floor alone would round -1.5 down to -2.
    """
    if float(v).is_integer():
        return str(int(v))
    sign = "-" if v < 0 else ""
    mag = abs(v)
    whole = math.floor(mag)
    frac = mag - whole
    for f, glyph in _FRACTION_GLYPHS:
        if abs(frac - f) < 1e-6:
            return f"{sign}{whole}{glyph}" if whole > 0 else f"{sign}{glyph}"
    # Format the magnitude, then re-attach the sign only if it survives rounding:
    # a tiny negative that rounds to "0" must not render as the malformed "-0".
    s = f"{mag:.3f}".rstrip("0").rstrip(".")
    return f"{sign}{s}" if sign and float(s) != 0 else s


# Total-marker recognition — among the most secure lexical identifications in
# Aegean accounting. Linear A: KU-RO (total), PO-TO-KU-RO (grand total), KI-RO (owed).
# KU-RA (ZA20, ARKH2) is read as a variant of KU-RO and closes a list the same way.
TOTAL_MARKERS = {"KU-RO", "KU-RA"}
GRAND_TOTAL_MARKERS = {"PO-TO-KU-RO"}
DEFICIT_MARKERS = {"KI-RO", "KU-RO₂"}


def _folded_in(term: str, lexemes: frozenset[str]) -> bool:
    t = term.casefold()
    return any(t == m.casefold() for m in lexemes)


@dataclass(frozen=True, slots=True)
class Markers:
    """The total / grand-total / deficit lexemes used on one script's accounting tablets.

    The canonical lexemes are uppercase; matching is case-insensitive because corpus
    transliteration case varies (the on-demand DAMOS Linear B corpus is lowercase)."""

    total: frozenset[str]
    grand_total: frozenset[str]
    deficit: frozenset[str]

    def is_total(self, term: str) -> bool:
        return _folded_in(term, self.total)

    def is_grand_total(self, term: str) -> bool:
        return _folded_in(term, self.grand_total)

    def is_deficit(self, term: str) -> bool:
        return _folded_in(term, self.deficit)

    def is_marker(self, term: str) -> bool:
        """Whether ``term`` is any accounting marker (total, grand total, or deficit)."""
        return self.is_total(term) or self.is_grand_total(term) or self.is_deficit(term)


# Linear A is the default (and matches the bundled golden fixtures). Linear B is Mycenaean Greek:
# to-so / to-sa = τόσος "so much/many" and to-so-de "and so much" (the total formulas),
# o-pe-ro = ὄφελος "what is owed" (the deficit).
LINEAR_A_MARKERS = Markers(frozenset(TOTAL_MARKERS), frozenset(GRAND_TOTAL_MARKERS), frozenset(DEFICIT_MARKERS))
LINEAR_B_MARKERS = Markers(
    frozenset({"TO-SO", "TO-SA", "TO-SO-DE"}), frozenset(), frozenset({"O-PE-RO", "O-PE-RO-SI"})
)
_MARKERS_BY_SCRIPT = {"lineara": LINEAR_A_MARKERS, "linearb": LINEAR_B_MARKERS}


def markers_for(script_id: str) -> Markers:
    """The accounting markers for a script (Linear A by default)."""
    return _MARKERS_BY_SCRIPT.get(script_id, LINEAR_A_MARKERS)


LineRole = str  # "header" | "item" | "total" | "grand-total" | "deficit"

_IDEOGRAM_RE = re.compile(r"^[A-Z*][A-Z0-9*+'\[\]?]*$")
_SKIP_TOKENS = {"\U00010101", "\U0001076B", "—", "≈"}  # 𐄁 etc.


@dataclass(slots=True)
class AccountLine:
    index: int
    tokens: list[str]
    terms: list[str]
    ideograms: list[str]
    value: float
    has_number: bool
    role: LineRole


def _classify_tokens(tokens: list[str]) -> tuple[list[str], list[str]]:
    terms: list[str] = []
    ideograms: list[str] = []
    for tk in tokens:
        if parse_value(tk) is not None:
            continue
        if tk in _SKIP_TOKENS:
            continue
        if "-" in tk:
            terms.append(tk)
        elif _IDEOGRAM_RE.match(tk):
            ideograms.append(tk)
        else:
            terms.append(tk)
    return terms, ideograms


def parse_account_lines(
    lines: list[list[str]], markers: Markers = LINEAR_A_MARKERS
) -> list[AccountLine]:
    """Tag each physical line with its accounting role (Linear A markers by default)."""
    out: list[AccountLine] = []
    for index, tokens in enumerate(lines):
        value = line_value(tokens)
        has_number = has_value(tokens)
        terms, ideograms = _classify_tokens(tokens)
        role: LineRole = "item"
        if any(markers.is_grand_total(t) for t in terms):
            role = "grand-total"
        elif any(markers.is_total(t) for t in terms):
            role = "total"
        elif any(markers.is_deficit(t) for t in terms):
            role = "deficit"
        elif not has_number:
            role = "header"
        out.append(AccountLine(index, tokens, terms, ideograms, value, has_number, role))
    return out


@dataclass(slots=True)
class BalanceCheck:
    """One total line reconciled against the item lines feeding it: the stated total, the computed
    sum, their signed difference (computed − stated), whether they balance, the total marker
    (e.g. ``KU-RO``), and the index of the total line."""

    stated_total: float
    computed_sum: float
    item_count: int
    difference: float        # computed - stated
    balances: bool
    marker: str
    total_line_index: int


def check_balances(
    lines: list[AccountLine], markers: Markers = LINEAR_A_MARKERS
) -> list[BalanceCheck]:
    """Verify each total line against the lines feeding it.

    A KU-RO subtotal is checked against the item lines since the previous total. A
    PO-TO-KU-RO grand total is checked against the stated KU-RO subtotals that precede it
    (plus any trailing items that never got their own subtotal): the standard reading of a
    Linear A account, where the grand total sums the subtotals rather than re-summing the
    raw items. Deficit and header lines are excluded from the sums. Section boundaries are
    heuristic, mirroring the standard reading.
    """
    checks: list[BalanceCheck] = []
    running: list[AccountLine] = []
    subtotals: list[float] = []
    for line in lines:
        if line.role == "item" and line.has_number:
            running.append(line)
            continue
        if line.role == "total":
            computed = sum(item.value for item in running)
            count = len(running)
            # The stated subtotal feeds any later grand total, whether or not it
            # balanced itself; the raw items it covered do not (they are already
            # accounted for in the subtotal).
            subtotals.append(line.value)
            running = []
        elif line.role == "grand-total":
            computed = sum(subtotals) + sum(item.value for item in running)
            count = len(subtotals) + len(running)
            subtotals = []
            running = []
        else:
            continue
        diff = computed - line.value
        # A line's role may have been assigned by a different marker set than the
        # one passed here; fall back to no marker rather than raising StopIteration.
        marker = next(
            (t for t in line.terms
             if markers.is_total(t) or markers.is_grand_total(t)),
            "",
        )
        checks.append(
            BalanceCheck(
                stated_total=line.value,
                computed_sum=computed,
                item_count=count,
                difference=diff,
                balances=abs(diff) < 1e-6,
                marker=marker,
                total_line_index=line.index,
            )
        )
    return checks
