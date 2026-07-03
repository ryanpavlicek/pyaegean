"""Deterministic LSJ sense-selection and a grounding-regime detector (EXPLORATORY).

The measured wall behind this module: feeding a model the *dominant* gloss of a
polysemous word is neutral-to-harmful, because the first LSJ sense is often the
wrong contextual one (στάσις, κρίσις, ἄρουρα). `ai.grounding.content_glosses`
copes by *refusing* to gloss high-polysemy words at all. This module takes the
other route: rank a word's senses by fit to its surrounding context and surface
the contextually-best one, so a buried-but-right sense can still ground the model.

`select_sense` scores each LSJ ``Sense`` of a word by:

- **lexical overlap** between the Greek cited in the sense's gloss text (LSJ
  definitions quote related/illustrative Greek via ``<foreign>``/``<quote>``)
  and the *content lemmas* of the context window (via `greek.lemmatize`, with a
  morphology fallback); accent-insensitive;
- a **dialect/register** bonus when the sense's own text carries the same LSJ
  markedness markers as the entry (a characteristic-sense tie-breaker);
- a mild **sense-order / length prior** (earlier, more central senses first),
  the same dominant-sense intuition `content_glosses` relies on.

`grounding_regime` estimates, offline, whether lexical grounding will *help*,
be *neutral*, or *hurt* a given text, from three deterministic signals: term
rarity (corpus-relative via `greek.terminology_rarity` when a corpus is given,
else a length/charset heuristic), polysemy load (mean senses per content word),
and register markedness.

**Exploratory.** A ranked sense is a *hypothesis*, not a disambiguation: this is
an offline lexical-overlap heuristic with no parser-grade word-sense model behind
it. The regime label is a difficulty *signal*, not a measured accuracy. Both
require the LSJ lexicon (`greek.use_lsj()`); without it they degrade to empty /
heuristic-only results rather than raising.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from ..greek.usage import _DIALECTS, _REGISTERS
from .grounding import _FUNCTION_LEMMAS, _concise_gloss

__all__ = [
    "RegimeSignal",
    "SenseCandidate",
    "grounding_regime",
    "select_sense",
]

# A Greek-letter run (polytonic block + basic Greek + extended) of length >= 2:
# the cited/illustrative Greek inside an LSJ sense's English definition text.
_GREEK_RUN = re.compile(r"[Ͱ-Ͽἀ-῿]{2,}")
# Markedness abbreviations (dialect + register) reused from greek.usage.
_MARKERS = {**_DIALECTS, **_REGISTERS}
_ABBR = re.compile(r"[A-Za-z]+\.")


def _strip(text: str) -> str:
    """NFC-lower, accents removed: the key for accent-insensitive Greek overlap."""
    nfd = unicodedata.normalize("NFD", unicodedata.normalize("NFC", text).lower())
    return "".join(c for c in nfd if not unicodedata.combining(c))


def _context_lemmas(context: str) -> set[str]:
    """Accent-stripped content lemmas of the context window.

    Uses the active `greek.lemmatize` cascade, falling back to the rule-based
    morphology engine's lemma hint and finally the surface form; function words
    are dropped. Degrades to an empty set without any backend only if tokenizing
    fails (it does not require one)."""
    try:
        from ..greek import lemmatize, tokenize_words
    except Exception:  # pragma: no cover - greek always importable, defensive
        return set()
    out: set[str] = set()
    for w in tokenize_words(context):
        try:
            lemma = lemmatize(w) or w
        except Exception:  # pragma: no cover - defensive
            lemma = w
        norm = unicodedata.normalize("NFC", lemma).lower()
        if norm in _FUNCTION_LEMMAS:
            continue
        stripped = _strip(lemma)
        if len(stripped) >= 2:
            out.add(stripped)
    return out


def _sense_greek(text: str) -> set[str]:
    """Accent-stripped Greek tokens cited inside a sense's (English) gloss text."""
    return {_strip(m.group()) for m in _GREEK_RUN.finditer(text)}


def _sense_markers(text: str) -> tuple[set[str], set[str]]:
    """The (dialects, registers) a sense's own text carries, as LSJ abbreviations."""
    dialects: set[str] = set()
    registers: set[str] = set()
    for tok in _ABBR.findall(text):
        key = tok.lower()
        if key in _DIALECTS:
            dialects.add(_DIALECTS[key])
        if key in _REGISTERS:
            registers.add(_REGISTERS[key])
    return dialects, registers


@dataclass(frozen=True, slots=True)
class SenseCandidate:
    """One ranked LSJ sense of a word (EXPLORATORY: a hypothesis, not a decision).

    ``marker``/``level``/``gloss`` mirror the underlying `greek.lexicon.Sense`;
    ``score`` is the context-fit total; ``overlap`` are the context lemmas (accent-
    stripped) that the sense's cited Greek shares; ``dominant`` flags the order-1
    sense (the gloss `content_glosses` would have used)."""

    marker: str
    level: int
    gloss: str
    score: float
    overlap: tuple[str, ...]
    dominant: bool

    def __str__(self) -> str:
        head = self.marker or "·"
        return f"{head}. {self.gloss}  [{self.score:.2f}]"


def select_sense(
    word: str,
    context: str,
    *,
    max_candidates: int = 3,
    overlap_weight: float = 1.0,
    markedness_weight: float = 0.25,
    prior_weight: float = 0.15,
) -> list[SenseCandidate]:
    """Rank ``word``'s LSJ senses by fit to ``context``; best first (EXPLORATORY).

    Returns up to ``max_candidates`` `SenseCandidate`s, the contextually-best sense
    first. Each sense scores by lexical overlap (``overlap_weight``) between the
    Greek it cites and the context's content lemmas, a markedness bonus
    (``markedness_weight``) when the sense carries the entry's dialect/register
    markers, and a mild sense-order/length prior (``prior_weight``) favouring the
    earlier, more central senses. Ties keep LSJ order, so with no overlap signal at
    all the dominant sense leads, exactly as `content_glosses` assumes.

    Best-effort and offline: returns ``[]`` if the LSJ lexicon is not loaded
    (`greek.use_lsj()`) or the word has no entry. A ranked sense is a *hypothesis*
    from a lexical-overlap heuristic, not a word-sense disambiguation — label it
    unverified at point of use.
    """
    try:
        from ..greek import lexicon as _lexicon
        from ..greek import lookup
    except Exception:  # pragma: no cover - greek always importable, defensive
        return []
    if _lexicon.active() is None:  # LSJ not loaded — best-effort, not required
        return []
    try:
        entry = lookup(word)
    except Exception:
        entry = None
    if entry is None or not entry.senses:
        return []

    ctx = _context_lemmas(context)
    # The entry's own markedness (so a sense only earns the bonus if the word as a
    # whole is dialectally/register-marked, not on a stray citation abbreviation).
    entry_d, entry_r = _sense_markers(" ".join([entry.lead, *(s.text for s in entry.senses)]))
    n = len(entry.senses)

    scored: list[tuple[float, int, SenseCandidate]] = []
    for i, s in enumerate(entry.senses):
        gloss = _concise_gloss(s.text) or s.text
        shared = sorted(ctx & _sense_greek(s.text))
        overlap = overlap_weight * float(len(shared))
        sd, sr = _sense_markers(s.text)
        marked = bool((sd & entry_d) or (sr & entry_r))
        markedness = markedness_weight if marked else 0.0
        # Order prior: 1.0 for the first sense, decaying; a short central gloss is
        # the dominant reading LSJ leads with.
        prior = prior_weight * (1.0 - i / n) * (1.0 if len(gloss) <= 60 else 0.6)
        score = overlap + markedness + prior
        cand = SenseCandidate(
            marker=s.marker,
            level=s.level,
            gloss=gloss,
            score=round(score, 4),
            overlap=tuple(shared),
            dominant=(i == 0),
        )
        scored.append((score, i, cand))

    # Sort by score desc, LSJ order on ties (negate index → lower index wins).
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [c for _score, _i, c in scored[: max(0, max_candidates)]]


# --- grounding-regime detector ----------------------------------------------

_HELP = "help"
_NEUTRAL = "neutral"
_HURT = "hurt"


@dataclass(frozen=True, slots=True)
class RegimeSignal:
    """An estimate of whether lexical grounding helps this text (EXPLORATORY).

    ``regime`` is ``"help"`` / ``"neutral"`` / ``"hurt"``; ``rarity``,
    ``polysemy``, and ``markedness`` are the three component signals (each
    0..1-ish), and ``content_words`` is how many content words fed the estimate.
    A difficulty *signal*, not a measured accuracy."""

    regime: str
    rarity: float
    polysemy: float
    markedness: float
    content_words: int

    def __bool__(self) -> bool:
        return self.regime == _HELP


def _heuristic_rarity(content: list[str]) -> float:
    """A corpus-free rarity proxy: longer mean word length and a wider charset
    (diacritics, rare letters) track the technical/documentary vocabulary that
    grounding helps with. 0 (common-looking) .. ~1 (rare-looking)."""
    if not content:
        return 0.0
    mean_len = sum(len(w) for w in content) / len(content)
    # Map mean length ~5 → 0, ~11 → 1 (Greek content words average ~6-7 chars).
    length_signal = max(0.0, min(1.0, (mean_len - 5.0) / 6.0))
    # φ is the ordinary GREEK SMALL LETTER PHI (U+03C6) that real text uses, not the
    # PHI SYMBOL (U+03D5); ξ ψ φ and rough-breathing ῥ are the marked/rare consonants.
    rare_letters = sum(1 for w in content for ch in w if ch in "ξψφῥ") / max(1, len(content))
    return max(0.0, min(1.0, 0.7 * length_signal + 0.3 * min(1.0, rare_letters)))


def grounding_regime(text: str, *, corpus: object | None = None) -> RegimeSignal:
    """Estimate whether lexical grounding helps ``text`` (EXPLORATORY, offline).

    Combines three deterministic signals: **rarity** (corpus-relative via
    `greek.terminology_rarity` when ``corpus`` is given, else a length/charset
    heuristic), **polysemy load** (mean LSJ senses over the content words, when
    `greek.use_lsj()` is active; else 0), and **register markedness** (share of
    content words LSJ tags as dialectal/poetic/technical). High rarity favours
    grounding (``help``); high polysemy without rarity favours ``hurt`` (the
    dominant-gloss trap); little of either is ``neutral``.

    A best-effort heuristic: it never raises on missing backends, returning the
    signals it can compute. The label is exploratory — a guide for when to apply
    grounding, not a measured accuracy.
    """
    try:
        from ..greek import lemmatize, tokenize_words
    except Exception:  # pragma: no cover - greek always importable, defensive
        return RegimeSignal(_NEUTRAL, 0.0, 0.0, 0.0, 0)

    content: list[str] = []
    for w in tokenize_words(text):
        try:
            lemma = lemmatize(w) or w
        except Exception:  # pragma: no cover - defensive
            lemma = w
        if unicodedata.normalize("NFC", lemma).lower() not in _FUNCTION_LEMMAS:
            content.append(w)
    n = len(content)
    if n == 0:
        return RegimeSignal(_NEUTRAL, 0.0, 0.0, 0.0, 0)

    # Rarity.
    rarity: float
    if corpus is not None:
        try:
            from ..greek import terminology_rarity

            rarity = float(terminology_rarity(text, corpus).overall)
        except Exception:  # pragma: no cover - defensive corpus shapes
            rarity = _heuristic_rarity(content)
    else:
        rarity = _heuristic_rarity(content)

    # Polysemy load + markedness, both from the active LSJ (best-effort).
    polysemy, markedness = _lexical_load(content)

    regime = _classify(rarity, polysemy, markedness)
    return RegimeSignal(
        regime=regime,
        rarity=round(rarity, 4),
        polysemy=round(polysemy, 4),
        markedness=round(markedness, 4),
        content_words=n,
    )


def _lexical_load(content: Iterable[str]) -> tuple[float, float]:
    """``(mean_senses, marked_fraction)`` over content words, from the active LSJ.

    ``mean_senses`` is the average ``len(entry.senses)`` (the polysemy load);
    ``marked_fraction`` is the share of words whose entry carries a dialect/register
    marker. Returns ``(0.0, 0.0)`` when LSJ is not loaded."""
    try:
        from ..greek import lexicon as _lexicon
        from ..greek import lookup
        from ..greek import usage as _usage
    except Exception:  # pragma: no cover - greek always importable, defensive
        return 0.0, 0.0
    if _lexicon.active() is None:
        return 0.0, 0.0
    words = list(content)
    sense_counts: list[int] = []
    marked = 0
    seen = 0
    for w in words:
        try:
            entry = lookup(w)
        except Exception:
            entry = None
        if entry is None:
            continue
        seen += 1
        sense_counts.append(len(entry.senses))
        try:
            if _usage(w):
                marked += 1
        except Exception:  # pragma: no cover - defensive
            pass
    if not sense_counts:
        return 0.0, 0.0
    mean_senses = sum(sense_counts) / len(sense_counts)
    marked_fraction = marked / seen if seen else 0.0
    return mean_senses, marked_fraction


def _classify(rarity: float, polysemy: float, markedness: float) -> str:
    """Map the three signals to help / neutral / hurt.

    Rare vocabulary is where a dominant-sense gloss adds real signal (``help``).
    Heavily polysemous vocabulary that is *not* rare is the trap a first-sense
    gloss falls into (``hurt``). Otherwise ``neutral``. Markedness nudges toward
    ``help`` (a marked register is harder, so grounding is worth more)."""
    rare = rarity >= 0.6 or (rarity >= 0.45 and markedness >= 0.3)
    polysemous = polysemy >= 4.0
    if rare and not polysemous:
        return _HELP
    if polysemous and rarity < 0.45:
        return _HURT
    return _NEUTRAL
