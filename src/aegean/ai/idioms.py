"""Idiom / multiword-expression grounding for Ancient Greek.

The one translation-error class that per-token morphology grounding structurally
cannot reach: **non-compositional** multiword expressions, where the phrase means
something the words do not. ``ἐφ' ἡμῖν`` is "in our power", not "upon us"; ``οὐκ
ἔστιν ὅπως`` is "there is no way that", not "it is not how"; ``οἷός τε εἰμί`` is "be
able to", not "be such and". A literal, token-by-token reading of these is wrong,
and morphology lines (lemma, case, voice) only reinforce the literal reading. A
phrase-level gloss of the real meaning gives the model the one fact it needs.

This is a **curated lexicon** of vetted non-compositional expressions (bundled as
``data/bundled/greek/idioms.json``), each carrying a polytonic surface form, its
space-joined content lemmas, an English gloss, and a register note. Detection is
**surface- and lemma-based, not a parser**: it finds idioms two ways and never
claims a syntactic analysis. ``idiom_glosses`` returns one `GroundingItem` per
match (source ``lexicon:idiom``); it is best-effort and never raises.

Matching:

- **surface** (primary): the idiom's accent-stripped surface form is sought as an
  ordered token run inside the accent-stripped text, with elision/apostrophe
  normalized away. This catches fixed idioms verbatim (``ἐφ' ἡμῖν``,
  ``διὰ τοῦτο``), including their elided spellings. Gapped correlatives written
  with ``...`` in the lexicon (``οὐ μόνον ... ἀλλὰ καί``) match when each segment
  appears in order.
- **contiguous lemma match** (secondary): if the idiom's content lemmas appear as an
  *adjacent* run among the text's content lemmas (via `greek.pipeline` /
  `greek.lemmatize`), the idiom matches even when inflected away from its citation form
  (``οἷός τε ἐστί`` for the lexicon's ``οἷός τε εἰμί``). Adjacency, not a gapped
  subsequence, keeps an all-function-word idiom from firing on the same words scattered
  across an unrelated sentence; explicitly gapped ``...`` correlatives are caught by the
  surface path instead. Inflection coverage tracks the active lemmatizer, so this path is
  strongest with a treebank or the neural pipeline loaded and degrades, never raising,
  without one.

On overlapping matches the **longest** idiom wins (its shorter sub-idioms are
suppressed), and identical glosses are de-duplicated.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from ..greek.pipeline import TokenRecord

from ..data import load_bundled_json
from .grounding import GroundingItem

__all__ = ["idiom_glosses"]

# Apostrophe variants that mark Greek elision (ASCII ', right single quote, modifier
# letter apostrophe, Greek koronis). Normalized to a single space so an elided word and
# its full form tokenize the same way for the surface match.
_APOSTROPHES = "'’ʼ᾽··"
# A gap marker in a lexicon surface form (the "..." in a correlative idiom).
_GAP_RE = re.compile(r"\s*\.\.\.\s*")


@dataclass(frozen=True, slots=True)
class _Idiom:
    """One lexicon entry, with its surface segments and lemmas precomputed for matching."""

    surface: str  # the polytonic citation form, shown to the user
    gloss: str
    note: str
    segments: tuple[tuple[str, ...], ...]  # accent-stripped token runs split on "..."
    lemmas: tuple[str, ...]  # accent-stripped content lemmas
    span: int  # total accent-stripped surface tokens (longest-match key)


def _strip(text: str) -> str:
    """NFC-lower, accents/breathings removed: the key for accent-insensitive matching."""
    nfd = unicodedata.normalize("NFD", unicodedata.normalize("NFC", text).lower())
    return "".join(c for c in nfd if not unicodedata.combining(c))


def _tokens(text: str) -> list[str]:
    """Accent-stripped word tokens of ``text``, apostrophe-elision normalized away.

    Apostrophes (elision) become spaces so ``ἐφ' ἡμῖν`` and an un-elided spelling
    tokenize alike; everything non-alphabetic is a separator, so punctuation and
    numerals do not bridge or break a match spuriously."""
    s = _strip(text)
    for ch in _APOSTROPHES:
        s = s.replace(ch, " ")
    return [t for t in re.split(r"[^a-zα-ωϊϋ]+", s) if t]


@lru_cache(maxsize=1)
def _idioms() -> tuple[_Idiom, ...]:
    """The bundled idiom lexicon, parsed once and ordered longest-surface-first.

    Longest-first ordering means that when two idioms would match the same span the
    longer (more specific) one is offered first, so the longest-match preference in
    `idiom_glosses` is a stable, single pass."""
    raw = load_bundled_json("greek", "idioms.json")
    out: list[_Idiom] = []
    for entry in raw:
        surface = entry["surface"]
        segments = tuple(
            tuple(_tokens(seg)) for seg in _GAP_RE.split(surface) if _tokens(seg)
        )
        if not segments:  # pragma: no cover - defensive: every curated entry has tokens
            continue
        lemmas = tuple(_strip(lemma) for lemma in entry["lemmas"].split() if _strip(lemma))
        span = sum(len(seg) for seg in segments)
        out.append(
            _Idiom(
                surface=surface,
                gloss=entry["gloss"],
                note=entry.get("note", ""),
                segments=segments,
                lemmas=lemmas,
                span=span,
            )
        )
    out.sort(key=lambda it: (-it.span, it.surface))
    return tuple(out)


def _run_at(tokens: list[str], start: int, seg: tuple[str, ...]) -> bool:
    """Whether ``seg`` matches ``tokens`` contiguously starting at ``start``."""
    end = start + len(seg)
    return end <= len(tokens) and tuple(tokens[start:end]) == seg


def _surface_span(tokens: list[str], idiom: _Idiom) -> tuple[int, int] | None:
    """The ``[start, end)`` token span an idiom's surface covers in ``tokens``, or ``None``.

    A single-segment idiom is a contiguous token run; a gapped (``...``) idiom matches
    when its segments appear in order with any tokens between them, and the covered span
    runs from the first segment's start to the last segment's end."""
    first = idiom.segments[0]
    for i in range(len(tokens)):
        if not _run_at(tokens, i, first):
            continue
        cursor = i + len(first)
        ok = True
        last_end = cursor
        for seg in idiom.segments[1:]:
            j = cursor
            found = -1
            while j + len(seg) <= len(tokens):
                if _run_at(tokens, j, seg):
                    found = j
                    break
                j += 1
            if found < 0:
                ok = False
                break
            cursor = found + len(seg)
            last_end = cursor
        if ok:
            return (i, last_end)
    return None


def _content_lemmas(
    text: str, *, analysis: Sequence[TokenRecord] | None = None
) -> list[str]:
    """Accent-stripped lemmas of ``text`` in order, via the active analysis backends.

    Prefers `greek.pipeline` (one pass, sentence-contextual lemmas under the neural
    pipeline); falls back to per-token `greek.lemmatize`. Punctuation is dropped.
    Returns ``[]`` rather than raising if no Greek backend is importable, so the
    lemma path simply yields nothing instead of failing the whole call."""
    if analysis is not None:
        return [
            _strip(record.lemma)
            for record in analysis
            if record.upos != "PUNCT" and _strip(record.lemma)
        ]
    try:
        from ..greek import pipeline
    except Exception:  # pragma: no cover - greek always importable, defensive
        return []
    try:
        recs = pipeline(text, parse=False)
    except Exception:  # pragma: no cover - defensive
        recs = []
    if recs:
        return [_strip(r.lemma) for r in recs if r.upos != "PUNCT" and _strip(r.lemma)]
    # Fallback: tokenize + per-token lemmatize.
    try:
        from ..greek import lemmatize, tokenize_words
    except Exception:  # pragma: no cover - defensive
        return []
    out: list[str] = []
    for w in tokenize_words(text):
        try:
            lemma = lemmatize(w) or w
        except Exception:  # pragma: no cover - defensive
            lemma = w
        s = _strip(lemma)
        if s:
            out.append(s)
    return out


def _lemma_span(lemmas: list[str], wanted: tuple[str, ...]) -> tuple[int, int] | None:
    """The first ``[start, end)`` lemma-index span where ``wanted`` appears **contiguously**.

    Returns ``None`` when ``wanted`` is not an adjacent run inside ``lemmas``. The span is
    what lets the lemma path apply the same longest-match suppression the surface path
    does: a shorter idiom whose lemma span is contained in a longer match's is dropped.

    Contiguity is deliberate: a *gapped* subsequence match over an all-function-word
    idiom (e.g. ``ἐν ὁ``) fires on any sentence that merely contains those words
    scattered apart (``ἐν ἀρχῇ ἦν ὁ λόγος`` → lemmas ``ἐν ἀρχή εἰμί ὁ λόγος``), injecting
    a wrong idiom gloss. Requiring the idiom's lemmas to be adjacent in the text's lemma
    stream confines the lemma path to genuine inflected occurrences of the phrase. Empty
    ``wanted`` never matches (an idiom must have content lemmas). Explicitly gapped
    ``...`` correlatives are not routed here at all (they are caught by the surface
    path); see `idiom_glosses`."""
    n = len(wanted)
    if n == 0 or n > len(lemmas):
        return None
    for i in range(len(lemmas) - n + 1):
        if tuple(lemmas[i : i + n]) == wanted:
            return (i, i + n)
    return None


def idiom_glosses(
    text: str, *, analysis: Sequence[TokenRecord] | None = None
) -> list[GroundingItem]:
    """Detect curated Greek idioms in ``text`` and gloss their real (non-literal) meaning.

    For each idiom from the bundled lexicon that is present in ``text``, returns one
    `GroundingItem` whose ``content`` is ``"<surface>: <gloss>"`` (e.g.
    ``"ἐφ' ἡμῖν: in our power, up to us"``), ``source="lexicon:idiom"``, and
    ``ref`` the idiom's surface form. These ground a translator in the meaning of a
    non-compositional phrase, the one class of error per-token morphology cannot fix.

    Detection is two-pronged and **not** a parser:

    - **surface** (primary): accent-insensitive match of the idiom's surface form,
      with elision/apostrophe normalized away, so fixed idioms are caught verbatim
      (including elided and gapped-correlative spellings);
    - **contiguous lemma match** (secondary): the idiom's content lemmas appearing as an
      *adjacent* run among the text's content lemmas (via `greek.pipeline` /
      `greek.lemmatize`), which catches inflected idioms (``οἷός τε ἐστί`` for ``οἷός τε
      εἰμί``) without firing on the same function words scattered across an unrelated
      sentence. Explicitly gapped ``...`` correlatives are not routed through this path
      (the surface path catches them). Inflection coverage depends on the active
      lemmatizer; the path simply yields fewer matches without a rich backend loaded.

    ``analysis`` may supply already-computed `TokenRecord`s. Their lemmas drive the
    secondary path without consulting or rerunning a module-level Greek backend; hybrid
    translation uses this to preserve explicit `GreekPipeline` isolation.

    When idioms overlap, the **longest** match wins and its shorter sub-idioms are
    suppressed, on both the surface path (by token span) and the lemma path (by
    lemma-index span); identical glosses are de-duplicated. Best-effort and offline:
    returns ``[]`` (never raises) on empty input or a missing backend. The lexicon is a
    curated set of vetted non-compositional expressions, not an exhaustive idiom
    dictionary; a gloss is a meaning aid, not a syntactic claim.
    """
    if not text or not text.strip():
        return []

    tokens = _tokens(text)
    lemmas = _content_lemmas(text, analysis=analysis)

    # Pass 1: surface matches (already longest-first), recording covered token spans so a
    # shorter idiom nested inside a longer one is suppressed.
    covered: list[tuple[int, int]] = []
    matched: list[_Idiom] = []
    seen_surface: set[str] = set()

    def _overlaps(span: tuple[int, int]) -> bool:
        return any(span[0] < c[1] and c[0] < span[1] for c in covered)

    for idiom in _idioms():
        if not tokens:
            break
        span = _surface_span(tokens, idiom)
        if span is None or _overlaps(span):
            continue
        covered.append(span)
        matched.append(idiom)
        seen_surface.add(idiom.surface)

    # Pass 2: contiguous lemma matches for idioms the surface pass missed (inflected
    # forms). The idiom's content lemmas must be *adjacent* in the text's lemma stream, not
    # merely present in order: a gapped subsequence over an all-function-word idiom would
    # fire on any sentence containing those words scattered apart. Explicitly gapped ``...``
    # correlatives are excluded here (contiguity is wrong for them); the surface path
    # already catches them. Longest-match suppression applies on this path too, keyed on
    # the lemma-index span: ``_idioms()`` is longest-first, so a shorter idiom whose lemma
    # span is contained in an already-accepted longer match is dropped (``οἷόν τε`` nested
    # in ``οἷός τε εἰμί``). Two genuinely distinct idioms occupy disjoint lemma spans and
    # both survive. Gloss-level de-duplication below drops any restated meanings.
    lemma_covered: list[tuple[int, int]] = []
    for idiom in _idioms():
        if idiom.surface in seen_surface or len(idiom.segments) > 1:
            continue
        lspan = _lemma_span(lemmas, idiom.lemmas)
        if lspan is None:
            continue
        if any(c[0] <= lspan[0] and lspan[1] <= c[1] for c in lemma_covered):
            continue  # contained in a longer accepted match
        lemma_covered.append(lspan)
        matched.append(idiom)

    out: list[GroundingItem] = []
    seen_gloss: set[str] = set()
    for idiom in matched:
        key = idiom.gloss.strip().lower()
        if key in seen_gloss:
            continue
        seen_gloss.add(key)
        out.append(
            GroundingItem(
                f"{idiom.surface}: {idiom.gloss}",
                source="lexicon:idiom",
                ref=idiom.surface,
            )
        )
    return out
