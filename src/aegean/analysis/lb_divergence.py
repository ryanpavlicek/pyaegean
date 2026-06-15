"""Linear A vs Linear B sign-frequency divergence.

Compares how the two scripts use their shared signary. The join key is the
conventional phonetic value: Linear A's AB signs are matched to the Linear B
syllabograms they are graphically identified with (KU ↔ ku). **That
identification is exactly the hypothesis the comparison probes** — the
circularity is real, so read this as exploratory, not as evidence the values
are right.

The Linear B side is counted from the DAMOS corpus (Aurora 2015,
``damos.hf.uio.no``, CC BY-NC-SA), which pyaegean fetches on demand and never
bundles; :func:`parse_damos_frequencies` takes the decoded payload. Ported from
the workbench's ``src/lib/linearB.ts``; the counting basis (signs inside
multi-sign word tokens only) is mirrored on both sides so the rates compare.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field

from ..scripts.lineara.commodities import is_lexical_word
from ..scripts.lineara.phonetic import phonetic_map
from .patterns import normalize_sign_label

__all__ = [
    "LbFrequencies",
    "parse_damos_frequencies",
    "LaValueCount",
    "LaValueCounts",
    "linear_a_sign_value_counts",
    "DivergenceRow",
    "build_lb_divergence",
]

_LINE_LABEL_RE = re.compile(r"^\.[A-Za-z0-9]+\.?$")
_LB_SYLLABOGRAM_RE = re.compile(r"^[a-z]{1,3}[0-9]?$")
_LB_STARRED_RE = re.compile(r"^\*\d+[a-z]*$")
_COMBINING_RE = re.compile(r"[̀-ͯ]")
_BRACKET_RE = re.compile(r"[\[\]⟦⟧⌞⌟⌐¬?!⸤⸥]")
_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


@dataclass(frozen=True)
class LbFrequencies:
    """Linear B syllabogram frequencies from a DAMOS payload: ``counts`` maps a
    lowercase syllabogram value to its token count inside multi-sign words;
    ``total_signs`` / ``word_tokens`` / ``doc_count`` are the denominators and
    coverage, and ``version`` / ``generated`` / ``cite`` echo the dataset meta."""

    version: str
    generated: str
    cite: str
    counts: dict[str, int]
    total_signs: int
    word_tokens: int
    doc_count: int


def _clean_piece(piece: str) -> str:
    """Strip supraliteral quotes, NFD-decomposed underdots, editorial brackets /
    uncertainty marks, and fold unicode subscripts to ASCII digits."""
    p = piece
    if len(p) >= 2 and p.startswith("'") and p.endswith("'"):
        p = p[1:-1]
    p = unicodedata.normalize("NFD", p)
    p = _COMBINING_RE.sub("", p)
    p = _BRACKET_RE.sub("", p)
    return p.translate(_SUBSCRIPTS)


def parse_damos_frequencies(payload: dict[str, object]) -> LbFrequencies:
    """Count Linear B syllabogram frequencies in a ``damos-corpus.json`` payload
    (``{_meta, documents: [{content}]}``).

    Counting basis (mirrored on the Linear A side): signs inside multi-sign word
    tokens only. Logograms, numerals, single-sign words, and pieces that don't
    parse as syllabogram chains are skipped. Damaged-sign dots and editorial
    brackets are stripped rather than excluded — DAMOS marks uncertainty densely,
    and dropping every dotted sign would bias against worn tablets."""
    counts: dict[str, int] = {}
    total_signs = 0
    word_tokens = 0
    documents = payload.get("documents") or []
    docs: Sequence[dict[str, object]] = documents if isinstance(documents, list) else []
    for doc in docs:
        content = doc.get("content") if isinstance(doc, dict) else ""
        if not isinstance(content, str):
            continue
        for raw_line in content.split("\n"):
            pieces = [p for p in raw_line.strip().split() if p]
            start = 1 if pieces and _LINE_LABEL_RE.match(pieces[0]) else 0
            for piece in pieces[start:]:
                if piece in (",", "/"):
                    continue
                cleaned = _clean_piece(piece)
                if "-" not in cleaned:
                    continue
                parts = [p for p in cleaned.split("-") if p]
                if len(parts) < 2:
                    continue
                if not all(
                    _LB_SYLLABOGRAM_RE.match(p) or _LB_STARRED_RE.match(p) for p in parts
                ):
                    continue
                word_tokens += 1
                for p in parts:
                    total_signs += 1
                    if _LB_SYLLABOGRAM_RE.match(p):
                        counts[p] = counts.get(p, 0) + 1
    meta = payload.get("_meta")
    meta_d: dict[str, object] = meta if isinstance(meta, dict) else {}
    return LbFrequencies(
        version=str(meta_d.get("version", "")),
        generated=str(meta_d.get("generated", "")),
        cite=str(meta_d.get("cite", "")),
        counts=counts,
        total_signs=total_signs,
        word_tokens=word_tokens,
        doc_count=len(docs),
    )


@dataclass
class LaValueCount:
    """A Linear A phonetic value's token count and the AB sign labels behind it."""

    count: int = 0
    labels: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LaValueCounts:
    """Linear A sign counts keyed by phonetic value, plus the ``total_signs``
    denominator (every sign of every lexical word, valued or not)."""

    by_value: dict[str, LaValueCount]
    total_signs: int


def linear_a_sign_value_counts(words: Sequence[tuple[str, int]]) -> LaValueCounts:
    """Token-weighted Linear A sign counts over the lexical multi-sign vocabulary,
    keyed by each sign's conventional phonetic value (lowercase — the Linear B
    join key).

    ``words`` is an iterable of ``(word, count)`` pairs; non-lexical words (see
    :func:`is_lexical_word`) are skipped. Signs without a conventional value
    still count toward ``total_signs`` so the two corpora share a denominator
    definition."""
    pmap = phonetic_map()
    by_value: dict[str, LaValueCount] = {}
    total_signs = 0
    for word, count in words:
        if not is_lexical_word(word):
            continue
        for raw_part in word.split("-"):
            total_signs += count
            label = normalize_sign_label(raw_part)
            value = pmap.get(label)
            if not value:
                continue
            key = value.lower()
            rec = by_value.get(key)
            if rec is None:
                rec = LaValueCount()
                by_value[key] = rec
            rec.count += count
            if label not in rec.labels:
                rec.labels.append(label)
    return LaValueCounts(by_value=by_value, total_signs=total_signs)


@dataclass(frozen=True)
class DivergenceRow:
    """One shared phonetic value: its Linear A / Linear B counts and per-mille
    rates, and ``log_ratio`` = log₂ of the add-half-smoothed rate ratio
    (positive = over-used in Linear A relative to Linear B)."""

    value: str
    labels: list[str]
    la_count: int
    lb_count: int
    la_per_1000: float
    lb_per_1000: float
    log_ratio: float


def build_lb_divergence(la: LaValueCounts, lb: LbFrequencies) -> list[DivergenceRow]:
    """Join the two sign-value frequency tables on their shared attested values,
    most divergent (largest |log ratio|) first.

    Rates are smoothed add-half before the log₂ ratio. Only values attested in
    *both* scripts are returned. Empty if either side has no signs. **The
    join itself assumes the conventional sign values — that is the hypothesis,
    not a result.**"""
    rows: list[DivergenceRow] = []
    if la.total_signs == 0 or lb.total_signs == 0:
        return rows
    for value, rec in la.by_value.items():
        lb_count = lb.counts.get(value, 0)
        if lb_count == 0:
            continue
        la_rate = rec.count / la.total_signs
        lb_rate = lb_count / lb.total_signs
        smoothed_la = (rec.count + 0.5) / (la.total_signs + 1)
        smoothed_lb = (lb_count + 0.5) / (lb.total_signs + 1)
        rows.append(
            DivergenceRow(
                value=value,
                labels=rec.labels,
                la_count=rec.count,
                lb_count=lb_count,
                la_per_1000=la_rate * 1000,
                lb_per_1000=lb_rate * 1000,
                log_ratio=math.log2(smoothed_la / smoothed_lb),
            )
        )
    rows.sort(key=lambda r: -abs(r.log_ratio))
    return rows
