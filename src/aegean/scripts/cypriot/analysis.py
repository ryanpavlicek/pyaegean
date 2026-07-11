"""Descriptive analysis for the Cypriot syllabic corpus.

The Cypriot syllabary is deciphered, so two descriptive profiles the Linear A/B
analysis surface already offers have Cypriot counterparts here:

- :func:`syllabary_profile` — sign frequency across the corpus measured against
  the full ICS/Unicode syllabary grid, and which grid cells are **gaps** (never
  attested in the bundled corpus).
- :func:`bridge_coverage` — how much of the corpus reads as Greek through the
  existing Greek-reading bridge (:func:`aegean.scripts.cypriot.greek_reading`),
  broken down by the editorial reading status of each word.

Both are observational: they count what the bundled Inscriptiones Graecae XV 1
edition and the shipped sign table / lexicon contain. The Greek-reading lexicon
is deliberately small (only securely-established equations); low bridge coverage
is a fact about the lexicon's conservative scope, not the legibility of the
corpus. Neither function adds sign values or lexicon entries.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ...core.model import TokenKind
from .lexicon import greek_reading

__all__ = [
    "SignUsage",
    "SyllabaryProfile",
    "syllabary_profile",
    "BridgeReading",
    "BridgeCoverage",
    "bridge_coverage",
]


def _cypriot_corpus(corpus: Any) -> Any:
    if corpus is not None:
        return corpus
    from ...core.corpus import Corpus

    return Corpus.load("cypriot")


def _word_tokens(corpus: Any) -> list[Any]:
    docs = getattr(corpus, "documents", corpus)
    return [t for d in docs for t in d.tokens if t.kind is TokenKind.WORD]


# ── syllabary structure ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SignUsage:
    """One grid sign and how often it is attested as a syllabogram in the corpus.

    ``count`` is occurrences across all lexical words (case-folded to the grid
    label); ``attested`` is ``count > 0``. A sign with ``attested`` False is a
    grid gap — a cell of the syllabary the bundled corpus does not exercise."""

    label: str
    glyph: str | None
    phonetic: str | None
    count: int
    attested: bool


@dataclass(frozen=True, slots=True)
class SyllabaryProfile:
    """The corpus's use of the Cypriot syllabary grid.

    ``grid_size`` grid signs, of which ``attested_count`` occur in the corpus and
    ``gap_count`` do not (``gaps`` lists the unattested labels). ``signs`` is every
    grid sign as a `SignUsage`, most-frequent first (ties by label); ``sign_tokens``
    is the total syllabogram occurrences counted."""

    grid_size: int
    attested_count: int
    gap_count: int
    gaps: list[str] = field(default_factory=list)
    signs: list[SignUsage] = field(default_factory=list)
    sign_tokens: int = 0


def syllabary_profile(corpus: Any = None) -> SyllabaryProfile:
    """Profile sign frequency against the Cypriot syllabary grid, and report gaps.

    Counts every syllabogram occurrence in the corpus's lexical words (a token's
    decomposed ``signs``, case-folded to the grid's uppercase labels) and measures
    it against the full sign inventory (the ICS/Unicode grid). Grid signs the
    corpus never uses are reported as ``gaps``. ``corpus`` defaults to the bundled
    Cypriot corpus; its own ``sign_inventory`` is the grid, falling back to the
    packaged inventory when a passed corpus carries none.

    Descriptive: a gap means "unattested in *this* corpus", nothing about whether
    the sign existed or was legible elsewhere."""
    corpus = _cypriot_corpus(corpus)
    inv = getattr(corpus, "sign_inventory", None)
    if inv is None:
        from .inventory import cypriot_inventory

        inv = cypriot_inventory()

    counts: Counter[str] = Counter()
    sign_tokens = 0
    for tok in _word_tokens(corpus):
        for sign in tok.signs:
            # corpus signs are written as-transliterated (lowercase in IG XV 1,
            # uppercase in the samples); the grid labels are uppercase, so fold.
            counts[sign.upper()] += 1
            sign_tokens += 1

    signs: list[SignUsage] = []
    gaps: list[str] = []
    attested_count = 0
    for s in inv:
        n = counts.get(s.label.upper(), 0)
        if n > 0:
            attested_count += 1
        else:
            gaps.append(s.label)
        signs.append(
            SignUsage(
                label=s.label,
                glyph=s.glyph,
                phonetic=s.phonetic,
                count=n,
                attested=n > 0,
            )
        )
    signs.sort(key=lambda u: (-u.count, u.label))
    gaps.sort()
    return SyllabaryProfile(
        grid_size=len(signs),
        attested_count=attested_count,
        gap_count=len(gaps),
        gaps=gaps,
        signs=signs,
        sign_tokens=sign_tokens,
    )


# ── Greek-bridge coverage ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class BridgeReading:
    """One word form the Greek-reading bridge resolves: its ``lemma`` and ``gloss``
    and its token ``count`` in the corpus."""

    form: str
    lemma: str
    gloss: str
    count: int


@dataclass(frozen=True, slots=True)
class BridgeCoverage:
    """How much of the Cypriot corpus reads as Greek through the bundled bridge.

    ``read_tokens`` of ``word_tokens`` lexical words resolve to a Greek reading
    (``coverage_pct``). ``read_by_status`` / ``words_by_status`` break the read
    tokens and all word tokens down by editorial reading status (certain / unclear
    / restored). ``distinct_read_forms`` of ``distinct_forms`` word forms are in
    the lexicon; ``readings`` lists them (most-frequent first)."""

    word_tokens: int
    read_tokens: int
    coverage_pct: float
    read_by_status: dict[str, int] = field(default_factory=dict)
    words_by_status: dict[str, int] = field(default_factory=dict)
    distinct_forms: int = 0
    distinct_read_forms: int = 0
    readings: list[BridgeReading] = field(default_factory=list)


def bridge_coverage(corpus: Any = None) -> BridgeCoverage:
    """Measure Greek-reading coverage over the Cypriot corpus, by reading status.

    For every lexical word, checks the Greek-reading bridge
    (:func:`aegean.scripts.cypriot.greek_reading`) and tallies how many tokens
    resolve, split by the token's editorial reading status. ``corpus`` defaults to
    the bundled Cypriot corpus.

    Coverage is bounded by the deliberately small, securely-attested lexicon (this
    reports its reach; it does not extend it). Read the number as "share of the
    corpus the shipped lexicon already equates to Greek", not as a legibility or
    decipherment rate."""
    corpus = _cypriot_corpus(corpus)
    words = _word_tokens(corpus)

    read_by_status: Counter[str] = Counter()
    words_by_status: Counter[str] = Counter()
    form_counts: Counter[str] = Counter()
    read_forms: dict[str, tuple[str, str]] = {}
    read_tokens = 0
    for tok in words:
        words_by_status[tok.status.value] += 1
        form_counts[tok.text] += 1
        reading = greek_reading(tok.text)
        if reading is not None:
            read_tokens += 1
            read_by_status[tok.status.value] += 1
            read_forms.setdefault(tok.text, reading)

    readings = [
        BridgeReading(form=f, lemma=read_forms[f][0], gloss=read_forms[f][1], count=form_counts[f])
        for f in read_forms
    ]
    readings.sort(key=lambda r: (-r.count, r.form))
    return BridgeCoverage(
        word_tokens=len(words),
        read_tokens=read_tokens,
        coverage_pct=100 * read_tokens / len(words) if words else 0.0,
        read_by_status=dict(read_by_status.most_common()),
        words_by_status=dict(words_by_status.most_common()),
        distinct_forms=len(form_counts),
        distinct_read_forms=len(read_forms),
        readings=readings,
    )
