"""Scribal-hand analysis over a corpus that records a hand per document.

DAMOS (``aegean.load("damos")``) carries the DAMOS-curated scribal hand in
``DocumentMeta.scribe`` for the tablets where it is known, so the Mycenaean corpus can be
sliced by the person who wrote each tablet. ``scribal_hands`` builds a profile per hand
(how many tablets, where, when, the words they wrote most); ``hand_keyness`` measures what
is *characteristic* of one hand by comparing that hand's tablets against all the others
with the same log-likelihood keyness used elsewhere. Per-hand dispersion is just
``dispersion(corpus.filter(scribe=hand), item)`` — the standard helper over the hand's slice.

Script-agnostic: any corpus whose documents set ``meta.scribe`` works (DAMOS and the
bundled Linear A corpus both ship with hands today).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .stats import KeynessRow, keyness

__all__ = ["HandProfile", "scribal_hands", "hand_keyness"]


@dataclass(frozen=True, slots=True)
class HandProfile:
    """A summary of one scribal hand's output within a corpus."""

    hand: str
    doc_count: int
    token_count: int
    word_count: int
    sites: dict[str, int] = field(default_factory=dict)      # site -> tablets
    periods: dict[str, int] = field(default_factory=dict)    # chronology -> tablets
    top_words: list[tuple[str, int]] = field(default_factory=list)


def _documents(corpus: Any) -> list[Any]:
    return list(getattr(corpus, "documents", corpus))


def scribal_hands(
    corpus: Any, *, top_n: int = 8, min_docs: int = 1
) -> list[HandProfile]:
    """Profile every scribal hand in ``corpus`` (documents grouped by ``meta.scribe``).

    Returns one `HandProfile` per hand with at least ``min_docs`` tablets — tablet count,
    token and lexical-word totals, the sites and chronologies the hand is attested at, and
    the hand's ``top_n`` most frequent words — sorted by tablet count (then hand id).
    Documents with no recorded hand are skipped."""
    from ..core.model import TokenKind

    groups: dict[str, list[Any]] = {}
    for doc in _documents(corpus):
        hand = (doc.meta.scribe or "").strip()
        if hand:
            groups.setdefault(hand, []).append(doc)

    profiles: list[HandProfile] = []
    for hand, docs in groups.items():
        if len(docs) < min_docs:
            continue
        words: Counter[str] = Counter()
        token_count = 0
        sites: Counter[str] = Counter()
        periods: Counter[str] = Counter()
        for d in docs:
            token_count += len(d.tokens)
            words.update(t.text for t in d.tokens if t.kind is TokenKind.WORD)
            if d.meta.site:
                sites[d.meta.site] += 1
            if d.meta.period:
                periods[d.meta.period] += 1
        profiles.append(
            HandProfile(
                hand=hand,
                doc_count=len(docs),
                token_count=token_count,
                word_count=sum(words.values()),
                sites=dict(sites.most_common()),
                periods=dict(periods.most_common()),
                top_words=words.most_common(top_n),
            )
        )
    profiles.sort(key=lambda p: (-p.doc_count, p.hand))
    return profiles


def hand_keyness(
    corpus: Any, hand: str, *, kind: str = "words", min_target: int = 2
) -> list[KeynessRow]:
    """Words (or signs) characteristic of one scribal ``hand`` versus all other hands.

    Splits ``corpus`` into the ``hand``'s documents (target) and every other document
    (reference) and runs the standard log-likelihood `keyness`. Raises ``ValueError`` if no
    document is attributed to ``hand``."""
    from ..core.corpus import Corpus

    docs = _documents(corpus)
    target = [d for d in docs if (d.meta.scribe or "").strip() == hand]
    if not target:
        raise ValueError(f"no documents attributed to scribal hand {hand!r}")
    reference = [d for d in docs if (d.meta.scribe or "").strip() != hand]
    script_id = getattr(corpus, "script_id", "")
    return keyness(
        Corpus(target, script_id=script_id),
        Corpus(reference, script_id=script_id),
        kind=kind,
        min_target=min_target,
    )
