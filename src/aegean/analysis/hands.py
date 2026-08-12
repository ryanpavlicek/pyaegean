"""Scribal-hand and archival-series tooling over a Linear B corpus.

Where :mod:`aegean.analysis.scribal` profiles the person who wrote a tablet, this
module adds the **archival series**, the Mycenological classification prefix a
tablet's designation carries (``Fp`` in ``KN Fp(1) 1 (138)``, ``Da`` in
``KN Da 1156 (117)``), and joins it to the scribal hand and the find-site.

**The series is a Linear B convention.** The classification prefix belongs to the
Bennett/Olivier tablet-designation system used for the Linear B corpus, so the
series parse and the dossier grouping are defined for Linear B only.
:func:`dossiers` raises on a non-Linear-B corpus rather than read a spurious
prefix out of an unrelated id scheme (an ``IG XV 1, 217`` inscription number, say),
and the ``series`` breakdown in the hand groupings is filled only for a Linear B
corpus.

**Where the series comes from.** DAMOS records the site, chronology, scribal
hand, find context, and physical support of each tablet in
:class:`~aegean.core.model.DocumentMeta`, but the *series* is not a stored
metadata field. It lives in the tablet's conventional designation (the document
id / heading), e.g. ``KN Db 1196 + 8233 (117)``. :func:`series_of` parses it out:
the alphabetic run of the token after the site code (``Db``). Parenthetical
sub-set markers (``Fp(1)`` vs ``Fp(2)``, scribally distinct sets within the Fp
series) are folded to the parent prefix. A designation with no parseable prefix
(e.g. ``SID 1``) yields ``None`` and is left out of the series-based groupings.
The parse follows the designation convention: a well-established prefix names a
recognised set, while a residual or unconventional prefix (a single-capital ``X``
fragment class, say) is grouped as parsed, not asserted to be an attested archival
set.

**Attribution is the editors'.** A hand grouping is DAMOS's attribution (from the
standard hand studies) passed through unaltered; this module only counts and joins
the recorded fields, it makes no attribution of its own. A grouping key is one
distinct attribution *string* (a hand number, possibly qualified with a certainty
mark such as ``117?`` or a sub-hand tag), not necessarily one distinct scribe. All
functions are descriptive: they report what the edition records.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from ..core.model import Document

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


def _documents(corpus: Any) -> list[Document]:
    """Coerce a corpus, a query's results, or an iterable of Documents to a list.

    `Corpus.query` returns `aegean.analysis.QueryResults`, whose matched documents are
    its ``inscriptions``, so a queried subset can be grouped by hand or dossier
    directly. Anything else that yields documents (a `Corpus`, a plain list) is taken as
    it comes; anything that does not raises a ``TypeError`` naming what arrived."""
    docs = getattr(corpus, "inscriptions", None)
    if docs is None:
        docs = getattr(corpus, "documents", corpus)
    try:
        out = list(docs)
    except TypeError:
        raise TypeError(
            f"expected a corpus or documents, got {type(corpus).__name__}"
        ) from None
    if out and not isinstance(out[0], Document):
        raise TypeError(f"expected a corpus or documents, got {type(out[0]).__name__}")
    return out


def _script_id(corpus: Any, docs: Sequence[Document]) -> str:
    """The script the series convention is judged against, or ``""`` when unknown.

    A `Corpus` records the script in ``script_id``. A query's results and a plain
    document list do not, so the script is read from the documents themselves, each of
    which carries its own: the same tablets answer the same way however they are handed
    in. Documents that disagree, or none at all, leave it unknown."""
    script = getattr(corpus, "script_id", None)
    if isinstance(script, str) and script:
        return script
    scripts = {d.script_id for d in docs}
    return scripts.pop() if len(scripts) == 1 else ""


def _require_linear_b(script: str, func: str) -> None:
    """Guard a series-grouping path: it is defined for Linear B designations only."""
    if script != "linearb":
        script = script or "unknown"
        raise ValueError(
            f"{func}() is defined for Linear B only (the archival-series parse follows "
            f"the Bennett/Olivier tablet-designation convention), but this corpus is "
            f"{script!r}. Load a Linear B corpus, e.g. aegean.load('damos')."
        )


def series_of(doc: Any) -> str | None:
    """The archival series of a Linear B tablet, parsed from its designation, or ``None``.

    Defined for Linear B tablet designations (the Bennett/Olivier sigla). Accepts a
    `Document` (uses ``doc.id``) or a plain id string. The series is the alphabetic
    run of the second whitespace-delimited field, the classification prefix after
    the site code: ``series_of("KN Fp(1) 1 (138)") == "Fp"``,
    ``series_of("PY Ta 641") == "Ta"``. A designation with no such field (only a
    site code and a number, e.g. ``"SID 1 (-)"``) returns ``None``.

    This is a pure parser: it reads whatever second field an id carries and does not
    check the script, so a caller that passes an unrelated id scheme gets that
    scheme's second field back. It classifies nothing anew, and a residual or
    unconventional prefix is returned as parsed, not asserted to be an attested
    series. For the script-guarded grouping use :func:`dossiers`."""
    doc_id = getattr(doc, "id", doc)
    parts = str(doc_id).split()
    if len(parts) < 2:
        return None
    m = _SERIES_RE.match(parts[1])
    return m.group(1) if m else None


@dataclass(frozen=True, slots=True)
class HandGroup:
    """One hand attribution's tablets, broken down by find-site and archival series.

    ``hand`` is one distinct editorial attribution string (a hand number, possibly
    qualified). ``sites`` / ``series`` / ``periods`` are ``value -> tablet count``
    maps (most-common first); ``doc_ids`` lists the tablets in corpus order. The
    ``series`` breakdown is populated only for a Linear B corpus (the designation
    convention it parses); a tablet whose series does not parse is counted in
    ``doc_count`` but not in ``series``."""

    hand: str
    doc_count: int
    doc_ids: list[str] = field(default_factory=list)
    sites: dict[str, int] = field(default_factory=dict)
    series: dict[str, int] = field(default_factory=dict)
    periods: dict[str, int] = field(default_factory=dict)


def by_hand(corpus: Any, *, min_docs: int = 1) -> list[HandGroup]:
    """Group a corpus's documents by hand attribution, with a site / series breakdown.

    Returns one `HandGroup` per distinct attribution string (``meta.scribe``)
    attested on at least ``min_docs`` documents, sorted by tablet count desc, then
    attribution string. A group key is one attribution string (a hand number,
    possibly qualified with a certainty mark or sub-hand tag), so the number of
    groups counts distinct attribution strings, not necessarily distinct scribes.
    Documents with no recorded hand are skipped.

    The series breakdown is parsed from each document's designation (see
    :func:`series_of`) and is filled only for a Linear B corpus, where that
    convention applies; on other scripts it is left empty. The attribution is the
    edition's, passed through unchanged; this just counts the tablets, sites, and
    series each recorded attribution carries."""
    docs_in = _documents(corpus)
    linear_b = _script_id(corpus, docs_in) == "linearb"
    groups: dict[str, list[Any]] = {}
    for doc in docs_in:
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
            if linear_b:
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
    """One hand attribution's full descriptive profile.

    ``hand`` is one editorial attribution string (a hand number, possibly
    qualified). Tablet / token / lexical-word totals, its tablets (``doc_ids``),
    its ``sites`` / ``series`` / ``periods`` breakdowns (``value -> count``,
    most-common first), and its ``top_words`` (the attribution's most frequent
    lexical words, ``(word, count)``) computed with the standard corpus frequency
    machinery over the attribution's slice. The ``series`` breakdown is populated
    only for a Linear B corpus."""

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
    """Profile one hand attribution ``hand``: its tablets, sites, series, and vocabulary.

    ``hand`` is an editorial attribution string (a hand number, possibly qualified).
    Builds the sub-corpus of the tablets carrying that attribution and reports its
    counts, its site / series / chronology breakdowns, and its ``top_n`` most
    frequent lexical words (via `Corpus.word_frequencies`, the standard machinery).
    The series breakdown is filled only for a Linear B corpus. Raises ``ValueError``
    if no document carries the attribution.

    The vocabulary is descriptive (the words this attribution happened to write
    most), not a claim about a scribe's remit; for what is *distinctive* of one
    attribution versus the others use :func:`aegean.analysis.hand_keyness`."""
    from ..core.corpus import Corpus

    docs_in = _documents(corpus)
    docs = [d for d in docs_in if (d.meta.scribe or "").strip() == hand]
    if not docs:
        raise ValueError(f"no documents attributed to scribal hand {hand!r}")

    script = _script_id(corpus, docs_in)
    linear_b = script == "linearb"
    sub = Corpus(docs, script_id=script)
    freqs = sub.word_frequencies()
    sites: Counter[str] = Counter()
    series: Counter[str] = Counter()
    periods: Counter[str] = Counter()
    token_count = 0
    for d in docs:
        token_count += len(d.tokens)
        if d.meta.site:
            sites[d.meta.site] += 1
        if linear_b:
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
    """One archival grouping: the tablets sharing a find-site and a parsed series prefix.

    A common Mycenological working unit, e.g. the Knossos ``Da`` sheep-tablets or the
    Pylos ``Aa`` personnel tablets. The grouping follows the tablet-designation
    convention: a well-established prefix names a recognised set, while a residual or
    unconventional prefix (a single-capital ``X`` fragment class, say) is grouped as
    parsed and is not asserted to be an attested archival set. ``hands`` / ``periods``
    are ``value -> tablet count`` maps (most-common first) over the grouping's
    tablets; ``doc_ids`` lists them in corpus order; ``token_count`` / ``word_count``
    sum the writing they carry."""

    site: str
    series: str
    doc_count: int
    doc_ids: list[str] = field(default_factory=list)
    hands: dict[str, int] = field(default_factory=dict)
    periods: dict[str, int] = field(default_factory=dict)
    token_count: int = 0
    word_count: int = 0


def dossiers(corpus: Any, *, min_docs: int = 1) -> list[SeriesDossier]:
    """Group Linear B documents into archival dossiers by shared find-site **and** series.

    A *dossier* here is a ``(site, series)`` grouping: the tablets found at one site
    and sharing one series prefix (see :func:`series_of`). This is the conservative
    reading of the metadata that exists, the find-site (``meta.site``) and the series
    parsed from the designation. It does **not** attempt joins, hand-based sets, or
    physical-fit reconstructions the recorded fields cannot support.

    The series parse is a Linear B designation convention, so this raises
    ``ValueError`` on a non-Linear-B corpus rather than read a spurious prefix out of
    an unrelated id scheme. The script is the corpus's ``script_id``, or, for a query's
    results or a plain document list, the one the documents themselves record. The grouping
    follows the designation convention: a residual or unconventional prefix is
    grouped as parsed, not asserted to be an attested archival set.

    Returns one `SeriesDossier` per grouping with at least ``min_docs`` documents,
    sorted by tablet count desc, then site, then series. Documents whose series
    does not parse are left out (they belong to no series)."""
    docs_in = _documents(corpus)
    _require_linear_b(_script_id(corpus, docs_in), "dossiers")
    groups: dict[tuple[str, str], list[Any]] = {}
    for doc in docs_in:
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
