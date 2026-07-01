"""Corpus profiling: document types, account dossiers, and metrology.

Three descriptive profiles ported from the Linear A Research Workbench's
Document Types, Account Dossiers, and Metrology Lab modules:

- :func:`document_type_profile` — the corpus grouped by physical support, with
  per-type counts, mean writing per document, and how many documents carry a
  numeral (a proxy for accounting function).
- :func:`account_dossiers` — follow a candidate account-holder: every counted
  ledger line it heads, with quantities, commodities, and co-listed heads.
- :func:`metrology_profile` — the fraction census and a counted-vs-measured
  picture per commodity.

All exploratory on an undeciphered script. "Account holder", "document type",
and the metrological readings are working frames for gathering evidence, not
decipherments; quantity sums mix contested units and are coarse activity proxies.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..core.model import Document
from ..core.numerals import line_value, markers_for, parse_value
from ..scripts.lineara.commodities import (
    COMMODITIES,
    commodity_head,
    is_lexical_word,
    is_undeciphered_logogram,
)

__all__ = [
    "DocumentTypeProfile",
    "document_type_profile",
    "DossierEntry",
    "Dossier",
    "account_dossiers",
    "FractionRow",
    "CommodityMetrology",
    "MetrologyProfile",
    "metrology_profile",
]


def _documents(corpus: Any) -> list[Document]:
    return list(getattr(corpus, "documents", corpus))


# ── document-type profile ────────────────────────────────────────────────────

# The canonical physical supports; an unrecognized support stays as written,
# an empty one folds to "(unrecorded)". Only the first character is case-folded
# (a deliberate, lossy fold over stray case variants), matching the workbench.
_TYPE_NOTES = frozenset(
    {
        "Tablet", "Nodule", "Roundel", "Stone vessel", "Clay vessel",
        "Lames (short thin tablet)", "Sealing", "Inked inscription",
        "3-sided bar", "4-sided bar", "Metal object", "Stone object",
        "Architecture", "Graffito", "Label", "Loom weight", "Triton", "ivory object",
    }
)


def _fold_support(support: str) -> str:
    t = support.strip()
    if t in _TYPE_NOTES:
        return t
    norm = (t[0].upper() + t[1:]) if t else t
    if norm in _TYPE_NOTES:
        return norm
    if t == "":
        return "(unrecorded)"
    return t


@dataclass(frozen=True)
class DocumentTypeProfile:
    """One physical-support type: document ``count``, corpus ``share_pct``, mean
    multi-sign words per document (``words_per_doc``), the share of documents
    carrying at least one numeral (``numerals_pct`` — a proxy for accounting
    function, NOT a token fraction), and the ``top_sites`` (up to 2)."""

    type: str
    count: int
    share_pct: float
    words_per_doc: float
    numerals_pct: float
    top_sites: list[str]


@dataclass
class _TypeAcc:
    count: int = 0
    word_tokens: int = 0
    with_numerals: int = 0
    sites: Counter[str] = field(default_factory=Counter)


def document_type_profile(corpus: Any) -> list[DocumentTypeProfile]:
    """Profile a corpus by physical document type, most common type first.

    ``words_per_doc`` counts multi-sign (hyphenated) word *tokens*, the writing
    an object carries. ``numerals_pct`` is the percentage of documents with at
    least one numeral (the separator dot is never a numeral)."""
    docs = _documents(corpus)
    types: dict[str, _TypeAcc] = defaultdict(_TypeAcc)
    for doc in docs:
        acc = types[_fold_support(doc.meta.support)]
        acc.count += 1
        acc.word_tokens += sum(1 for t in doc.tokens if "-" in t.text)
        if doc.numerals:
            acc.with_numerals += 1
        if doc.meta.site:
            acc.sites[doc.meta.site] += 1
    total = len(docs)
    rows = [
        DocumentTypeProfile(
            type=key,
            count=a.count,
            share_pct=100 * a.count / max(1, total),
            words_per_doc=a.word_tokens / a.count if a.count else 0.0,
            numerals_pct=100 * a.with_numerals / a.count if a.count else 0.0,
            top_sites=[s for s, _ in sorted(a.sites.items(), key=lambda kv: (-kv[1], kv[0]))[:2]],
        )
        for key, a in types.items()
    ]
    rows.sort(key=lambda r: (-r.count, r.type))
    return rows


# ── account dossiers ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DossierEntry:
    """One ledger line an account head appears on: the source ``ins_id`` and
    ``site``, the full ``line_tokens``, the summed ``value`` after the head, and
    the line's ``commodity`` (or ``None``)."""

    ins_id: str
    site: str
    line_tokens: list[str]
    value: float
    commodity: str | None


@dataclass(frozen=True)
class Dossier:
    """An account-head candidate and its evidence: the heading ``word``, its
    ``entries`` (counted lines), distinct ``tablet_count``, summed
    ``total_value`` (mixed units — a coarse proxy), and the ``commodities`` /
    ``sites`` / ``co_listed`` heads it travels with (insertion-ordered counts)."""

    word: str
    entries: list[DossierEntry]
    entry_count: int
    tablet_count: int
    total_value: float
    commodities: dict[str, int]
    sites: dict[str, int]
    co_listed: dict[str, int]


@dataclass
class _DossierAcc:
    word: str
    entries: list[DossierEntry] = field(default_factory=list)
    total_value: float = 0.0
    commodities: Counter[str] = field(default_factory=Counter)
    sites: Counter[str] = field(default_factory=Counter)
    tablets: set[str] = field(default_factory=set)
    co_listed: Counter[str] = field(default_factory=Counter)


def _line_commodity(after: list[str]) -> str | None:
    for t in after:
        head = commodity_head(t)
        if head is not None:
            return head
        if is_undeciphered_logogram(t):
            return t
    return None


def account_dossiers(corpus: Any) -> list[Dossier]:
    """Gather, per account-head candidate, the counted ledger lines it heads.

    A line's head is its first lexical (syllabic) word; the script's total /
    grand-total / deficit markers (KU-RO, PO-TO-KU-RO, KI-RO; Linear B's
    to-so / to-sa / to-so-de, o-pe-ro; matched case-insensitively) are
    excluded — they are accounting operators, not holders. A line counts only if a numeral follows
    the head; its ``value`` sums the tokens after the head and its commodity is
    the first commodity logogram after it. Sorted by entry count desc, head asc.

    "Account holder" is a working hypothesis — a head may be a person, place,
    institution, or transaction term; this just assembles the evidence."""
    docs = _documents(corpus)
    dossiers: dict[str, _DossierAcc] = {}
    heads_by_tablet: dict[str, set[str]] = defaultdict(set)
    for doc in docs:
        markers = markers_for(doc.script_id)
        for line in doc.line_tokens:
            texts = [t.text for t in line]
            head = next((tx for tx in texts if is_lexical_word(tx)), None)
            if head is None or markers.is_marker(head):
                continue
            after = texts[texts.index(head) + 1 :]
            if not any(parse_value(t) is not None for t in after):
                continue
            value = line_value(after)
            commodity = _line_commodity(after)
            acc = dossiers.setdefault(head, _DossierAcc(head))
            acc.entries.append(
                DossierEntry(
                    ins_id=doc.id,
                    site=doc.meta.site,
                    line_tokens=texts,
                    value=value,
                    commodity=commodity,
                )
            )
            acc.total_value += value
            if commodity:
                acc.commodities[commodity] += 1
            if doc.meta.site:
                acc.sites[doc.meta.site] += 1
            acc.tablets.add(doc.id)
            heads_by_tablet[doc.id].add(head)
    for heads in heads_by_tablet.values():
        for a in sorted(heads):
            for b in sorted(heads):
                if a != b:
                    dossiers[a].co_listed[b] += 1
    result = [
        Dossier(
            word=acc.word,
            entries=acc.entries,
            entry_count=len(acc.entries),
            tablet_count=len(acc.tablets),
            total_value=acc.total_value,
            commodities=dict(acc.commodities),
            sites=dict(acc.sites),
            co_listed=dict(acc.co_listed),
        )
        for acc in dossiers.values()
    ]
    result.sort(key=lambda d: (-d.entry_count, d.word))
    return result


# ── metrology profile ────────────────────────────────────────────────────────


def _approx_fraction(v: float) -> str:
    for d in range(2, 17):
        n = v * d
        if abs(n - round(n)) < 1e-9 and round(n) >= 1:
            return f"{round(n)}/{d}"
    return f"{v:.3f}"


def _denominator_of(v: float) -> int | None:
    for d in range(2, 17):
        n = v * d
        if abs(n - round(n)) < 1e-9:
            return d
    return None


@dataclass(frozen=True)
class FractionRow:
    """One attested metrological fraction: its ``value``, a ``display`` form
    (e.g. ``3/4``), corpus ``count``, the ``commodities`` it co-occurs with on a
    line, and up to 12 ``example_ids``."""

    value: float
    display: str
    count: int
    commodities: dict[str, int]
    example_ids: list[str]


@dataclass(frozen=True)
class CommodityMetrology:
    """A commodity's metrology over its counted lines: ``entries`` lines, the
    ``fractional_pct`` that carry a fraction, the ``denominators`` seen
    (space-joined), and the ``median`` / ``max`` line quantity."""

    head: str
    gloss: str
    entries: int
    fractional_pct: float
    denominators: str
    median: float
    max: float


@dataclass(frozen=True)
class MetrologyProfile:
    """The corpus metrology: the ``fraction_rows`` census, per-commodity
    ``commodity_profiles`` (commodities with ≥3 counted lines), and the
    numeral / fraction / integer token totals."""

    fraction_rows: list[FractionRow]
    commodity_profiles: list[CommodityMetrology]
    numeral_tokens: int
    fraction_tokens: int
    integer_tokens: int
    distinct_fraction_values: int


@dataclass
class _FractionAcc:
    value: float
    count: int = 0
    commodities: Counter[str] = field(default_factory=Counter)
    example_ids: list[str] = field(default_factory=list)


@dataclass
class _ProfileAcc:
    values: list[float] = field(default_factory=list)
    fractional: int = 0
    denoms: set[int] = field(default_factory=set)


def metrology_profile(corpus: Any, *, min_entries: int = 3) -> MetrologyProfile:
    """Build the corpus metrology profile (fraction census + per-commodity
    counted-vs-measured), iterating physical lines.

    Each line is credited to its first commodity logogram; the line's numerals
    sum to one entry for that commodity. A commodity needs ``min_entries`` (3)
    counted lines to get a profile. Linear A metrology is contested, so read the
    denominators and fractional shares as exploratory description."""
    docs = _documents(corpus)
    fractions: dict[float, _FractionAcc] = {}
    profiles: dict[str, _ProfileAcc] = {}
    numeral_tokens = fraction_tokens = integer_tokens = 0
    for doc in docs:
        for line in doc.line_tokens:
            texts = [t.text for t in line]
            com = _line_commodity(texts)
            line_sum = 0.0
            line_has_value = False
            line_has_fraction = False
            for t in texts:
                v = parse_value(t)
                if v is None:
                    continue
                numeral_tokens += 1
                line_sum += v
                line_has_value = True
                if v < 1 or not float(v).is_integer():
                    fraction_tokens += 1
                    frac = v - math.floor(v)
                    key = frac if frac > 0 else v
                    if 0 < key < 1:
                        line_has_fraction = True
                        row = fractions.setdefault(key, _FractionAcc(key))
                        row.count += 1
                        if com is not None:
                            row.commodities[com] += 1
                        if len(row.example_ids) < 12 and doc.id not in row.example_ids:
                            row.example_ids.append(doc.id)
                else:
                    integer_tokens += 1
            if com is not None and line_has_value:
                p = profiles.setdefault(com, _ProfileAcc())
                p.values.append(line_sum)
                if line_has_fraction:
                    p.fractional += 1
                    frac = line_sum - math.floor(line_sum)
                    d = _denominator_of(frac) if frac > 0 else None
                    if d is not None:
                        p.denoms.add(d)
    fraction_rows = sorted(
        (
            FractionRow(
                value=a.value,
                display=_approx_fraction(a.value),
                count=a.count,
                commodities=dict(a.commodities),
                example_ids=a.example_ids,
            )
            for a in fractions.values()
        ),
        key=lambda r: -r.count,
    )
    commodity_profiles: list[CommodityMetrology] = []
    for head, p in profiles.items():
        if len(p.values) < min_entries:
            continue
        sv = sorted(p.values)
        entry = COMMODITIES.get(head)
        commodity_profiles.append(
            CommodityMetrology(
                head=head,
                gloss=entry.gloss if entry is not None else "undeciphered",
                entries=len(p.values),
                fractional_pct=100 * p.fractional / len(p.values),
                denominators=" ".join(str(d) for d in sorted(p.denoms)),
                median=sv[len(sv) // 2],
                max=sv[-1],
            )
        )
    commodity_profiles.sort(key=lambda c: (-c.entries, c.head))
    return MetrologyProfile(
        fraction_rows=fraction_rows,
        commodity_profiles=commodity_profiles,
        numeral_tokens=numeral_tokens,
        fraction_tokens=fraction_tokens,
        integer_tokens=integer_tokens,
        distinct_fraction_values=len(fraction_rows),
    )
