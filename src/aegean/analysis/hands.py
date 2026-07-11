"""Scribal-hand and archival-series tooling over a Linear B corpus.

Where :mod:`aegean.analysis.scribal` profiles the person who wrote a tablet, this
module adds the **archival series** — the Mycenological classification prefix a
tablet's designation carries (``Fp`` in ``KN Fp(1) 1 (138)``, ``Da`` in
``KN Da 1156 (117)``) — and joins it to the scribal hand and the find-site. The
result is the standard Mycenological working unit: the *set* / *series* of
tablets, who wrote it, and where.

**Where the series comes from.** DAMOS records the site, chronology, scribal
hand, find context, and physical support of each tablet in
:class:`~aegean.core.model.DocumentMeta`, but the *series* is **not a stored
metadata field** — it lives in the tablet's conventional designation (the
document id / heading), e.g. ``KN Db 1196 + 8233 (117)``. :func:`series_of`
parses it out: the alphabetic run of the token after the site code (``Db``).
DAMOS parenthetical sub-set markers (``Fp(1)`` vs ``Fp(2)``, both scribally
distinct sets within the Fp series) are folded to the parent series, matching
how a Mycenologist speaks of "the Fp series". A designation without a
parseable series (e.g. ``SID 1``) yields ``None`` and is left out of the
series-based groupings.

**Attribution is the editors'.** A scribal hand grouping is DAMOS's attribution
(from the standard hand studies) passed through unaltered — this module only
counts and joins the recorded fields; it makes no attribution of its own. All
three functions are descriptive: they report what the edition records.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "series_of",
    "HandGroup",
    "by_hand",
    "HandReport",
    "hand_profile",
    "SeriesDossier",
    "dossiers",
]

# The classification prefix is the leading alphabetic run of the designation token
# that follows the site code: "Fp(1)" -> "Fp", "Db" -> "Db", "X" -> "X". The
# parenthetical sub-set marker and any join/number that follow are dropped.
_SERIES_RE = re.compile(r"^([A-Za-z]+)")


def _documents(corpus: Any) -> list[Any]:
    return list(getattr(corpus, "documents", corpus))


def series_of(doc: Any) -> str | None:
    """The archival series of a tablet, parsed from its designation, or ``None``.

    Accepts a `Document` (uses ``doc.id``) or a plain id string. The series is the
    alphabetic run of the second whitespace-delimited field — the classification
    prefix after the site code: ``series_of("KN Fp(1) 1 (138)") == "Fp"``,
    ``series_of("PY Ta 641") == "Ta"``. A designation with no such field (only a
    site code and a number, e.g. ``"SID 1 (-)"``) returns ``None``.

    The parse is the standard Mycenological convention and is descriptive only —
    it reads the editors' tablet designation, it does not classify anything anew."""
    doc_id = getattr(doc, "id", doc)
    parts = str(doc_id).split()
    if len(parts) < 2:
        return None
    m = _SERIES_RE.match(parts[1])
    return m.group(1) if m else None


@dataclass(frozen=True, slots=True)
class HandGroup:
    """One scribal hand's tablets, broken down by find-site and archival series.

    ``sites`` / ``series`` / ``periods`` are ``value -> tablet count`` maps
    (most-common first); ``doc_ids`` lists the hand's tablets in corpus order. A
    tablet whose series does not parse is counted in ``doc_count`` but not in
    ``series``."""

    hand: str
    doc_count: int
    doc_ids: list[str] = field(default_factory=list)
    sites: dict[str, int] = field(default_factory=dict)
    series: dict[str, int] = field(default_factory=dict)
    periods: dict[str, int] = field(default_factory=dict)


def by_hand(corpus: Any, *, min_docs: int = 1) -> list[HandGroup]:
    """Group a corpus's documents by scribal hand, with a site / series breakdown.

    Returns one `HandGroup` per hand (``meta.scribe``) attested on at least
    ``min_docs`` documents, sorted by tablet count desc, then hand id. Documents
    with no recorded hand are skipped. The series breakdown is parsed from each
    document's designation (see :func:`series_of`).

    The hand attribution is the edition's (DAMOS), passed through unchanged; this
    just counts the tablets, sites, and series each recorded hand carries."""
    groups: dict[str, list[Any]] = {}
    for doc in _documents(corpus):
        hand = (doc.meta.scribe or "").strip()
        if hand:
            groups.setdefault(hand, []).append(doc)

    out: list[HandGroup] = []
    for hand, docs in groups.items():
        if len(docs) < min_docs:
            continue
        sites: Counter[str] = Counter()
        series: Counter[str] = Counter()
        periods: Counter[str] = Counter()
        for d in docs:
            if d.meta.site:
                sites[d.meta.site] += 1
            s = series_of(d)
            if s is not None:
                series[s] += 1
            if d.meta.period:
                periods[d.meta.period] += 1
        out.append(
            HandGroup(
                hand=hand,
                doc_count=len(docs),
                doc_ids=[d.id for d in docs],
                sites=dict(sites.most_common()),
                series=dict(series.most_common()),
                periods=dict(periods.most_common()),
            )
        )
    out.sort(key=lambda g: (-g.doc_count, g.hand))
    return out


@dataclass(frozen=True, slots=True)
class HandReport:
    """A single scribal hand's full descriptive profile.

    Tablet / token / lexical-word totals, the hand's tablets (``doc_ids``), its
    ``sites`` / ``series`` / ``periods`` breakdowns (``value -> count``,
    most-common first), and its ``top_words`` (the hand's most frequent lexical
    words, ``(word, count)``) computed with the standard corpus frequency
    machinery over the hand's slice."""

    hand: str
    doc_count: int
    token_count: int
    word_count: int
    doc_ids: list[str] = field(default_factory=list)
    sites: dict[str, int] = field(default_factory=dict)
    series: dict[str, int] = field(default_factory=dict)
    periods: dict[str, int] = field(default_factory=dict)
    top_words: list[tuple[str, int]] = field(default_factory=list)


def hand_profile(corpus: Any, hand: str, *, top_n: int = 15) -> HandReport:
    """Profile one scribal ``hand``: its tablets, sites, series, and vocabulary.

    Builds the sub-corpus of the tablets attributed to ``hand`` and reports its
    counts, its site / series / chronology breakdowns, and its ``top_n`` most
    frequent lexical words (via `Corpus.word_frequencies`, the standard machinery).
    Raises ``ValueError`` if no document is attributed to ``hand``.

    The vocabulary is descriptive — the words this hand happened to write most —
    not a claim about the hand's remit; for what is *distinctive* of a hand versus
    the others use :func:`aegean.analysis.hand_keyness`."""
    from ..core.corpus import Corpus

    docs = [d for d in _documents(corpus) if (d.meta.scribe or "").strip() == hand]
    if not docs:
        raise ValueError(f"no documents attributed to scribal hand {hand!r}")

    sub = Corpus(docs, script_id=getattr(corpus, "script_id", ""))
    freqs = sub.word_frequencies()
    sites: Counter[str] = Counter()
    series: Counter[str] = Counter()
    periods: Counter[str] = Counter()
    token_count = 0
    for d in docs:
        token_count += len(d.tokens)
        if d.meta.site:
            sites[d.meta.site] += 1
        s = series_of(d)
        if s is not None:
            series[s] += 1
        if d.meta.period:
            periods[d.meta.period] += 1
    return HandReport(
        hand=hand,
        doc_count=len(docs),
        token_count=token_count,
        word_count=sum(n for _, n in freqs),
        doc_ids=[d.id for d in docs],
        sites=dict(sites.most_common()),
        series=dict(series.most_common()),
        periods=dict(periods.most_common()),
        top_words=freqs[:top_n],
    )


@dataclass(frozen=True, slots=True)
class SeriesDossier:
    """One archival dossier: the tablets sharing a find-site and an archival series.

    The Mycenological working unit — e.g. the Knossos ``Da`` sheep-tablets, or the
    Pylos ``Aa`` personnel tablets. ``hands`` / ``periods`` are ``value -> tablet
    count`` maps (most-common first) over the dossier's tablets; ``doc_ids`` lists
    them in corpus order; ``token_count`` / ``word_count`` sum the writing they
    carry."""

    site: str
    series: str
    doc_count: int
    doc_ids: list[str] = field(default_factory=list)
    hands: dict[str, int] = field(default_factory=dict)
    periods: dict[str, int] = field(default_factory=dict)
    token_count: int = 0
    word_count: int = 0


def dossiers(corpus: Any, *, min_docs: int = 1) -> list[SeriesDossier]:
    """Group documents into archival dossiers by shared find-site **and** series.

    A *dossier* here is a ``(site, series)`` grouping — the set of tablets found at
    one site and classified under one archival series (see :func:`series_of`). This
    is the conservative reading of the metadata that exists: the find-site
    (``meta.site``) and the series parsed from the designation. It does **not**
    attempt joins, hand-based sets, or physical-fit reconstructions the recorded
    fields cannot support.

    Returns one `SeriesDossier` per grouping with at least ``min_docs`` documents,
    sorted by tablet count desc, then site, then series. Documents whose series
    does not parse are left out (they belong to no series)."""
    groups: dict[tuple[str, str], list[Any]] = {}
    for doc in _documents(corpus):
        s = series_of(doc)
        if s is None:
            continue
        groups.setdefault((doc.meta.site, s), []).append(doc)

    from ..core.model import TokenKind

    out: list[SeriesDossier] = []
    for (site, series), docs in groups.items():
        if len(docs) < min_docs:
            continue
        hands: Counter[str] = Counter()
        periods: Counter[str] = Counter()
        token_count = 0
        word_count = 0
        for d in docs:
            token_count += len(d.tokens)
            word_count += sum(1 for t in d.tokens if t.kind is TokenKind.WORD)
            hand = (d.meta.scribe or "").strip()
            if hand:
                hands[hand] += 1
            if d.meta.period:
                periods[d.meta.period] += 1
        out.append(
            SeriesDossier(
                site=site,
                series=series,
                doc_count=len(docs),
                doc_ids=[d.id for d in docs],
                hands=dict(hands.most_common()),
                periods=dict(periods.most_common()),
                token_count=token_count,
                word_count=word_count,
            )
        )
    out.sort(key=lambda d: (-d.doc_count, d.site, d.series))
    return out
