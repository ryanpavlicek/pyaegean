"""Wildcard sign-pattern matching for syllabic words.

Port of ``src/lib/signPattern.ts``. Patterns are dash-separated sign labels
with two wildcards: ``*`` matches exactly one sign, ``**`` matches zero or
more. Case-insensitive after subscript normalisation (RA₂ ≡ RA2).
"""

from __future__ import annotations

from dataclasses import dataclass

SIGN_PATTERN_HELP = (
    "Dash-separated sign labels. Use * for one sign (any value), ** for zero "
    "or more. Examples: KU-*-RO · **-RE · JA-SA-** · *-KU-*"
)

_SUBSCRIPTS = {"₂": "2", "₃": "3", "₄": "4"}


def normalize_sign_label(label: str) -> str:
    """Fold subscript digits to ASCII (RA₂ → RA2)."""
    return "".join(_SUBSCRIPTS.get(c, c) for c in label)


@dataclass(frozen=True, slots=True)
class CompiledSignPattern:
    """A parsed sign-pattern query: the normalized sign tokens (with ``*`` = one sign and ``**`` =
    zero-or-more wildcards) and whether the pattern contains a ``**``."""

    tokens: tuple[str, ...]
    has_double_star: bool


def compile_sign_pattern(raw: str) -> CompiledSignPattern | None:
    """Parse a wildcard sign pattern (``KU-*-RO``) into a `CompiledSignPattern`, or ``None`` if empty."""
    toks = [t.strip() for t in raw.split("-") if t.strip()]
    if not toks:
        return None
    norm = [t if t in ("*", "**") else normalize_sign_label(t).upper() for t in toks]
    return CompiledSignPattern(tuple(norm), any(t == "**" for t in norm))


def match_sign_pattern(signs: list[str], pattern: CompiledSignPattern) -> bool:
    """Match a word's sign sequence against a compiled pattern.

    Walks the pattern once, carrying the set of sign positions still reachable, so
    cost is O(len(pattern) * len(word)). A pattern with several ``**`` wildcards
    would otherwise branch exponentially: ``**-**-**-...`` against the corpus's
    longest word took over a minute at ten wildcards and had no practical bound.
    """
    ws = [normalize_sign_label(s).upper() for s in signs]
    ps = pattern.tokens
    end = len(ws)

    reachable = {0}
    for tok in ps:
        if tok == "**":  # zero or more signs: everything from here to the end
            reachable = set(range(min(reachable), end + 1)) if reachable else set()
        elif tok == "*":
            reachable = {si + 1 for si in reachable if si < end}
        else:
            reachable = {si + 1 for si in reachable if si < end and ws[si] == tok}
        if not reachable:
            return False
    return end in reachable


def word_matches_sign_pattern(word: str, raw: str) -> bool:
    """Compile and match in one call. False for single-sign words / empty patterns."""
    if "-" not in word:
        return False
    compiled = compile_sign_pattern(raw)
    if compiled is None:
        return False
    return match_sign_pattern(word.split("-"), compiled)
