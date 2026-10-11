"""Shared lexical views for corpus counts, compound queries, and SQLite search.

These are comparison keys, not editorial regularizations or new annotations.
Normalization preserves accents, breathings, and iota subscript. Missing lemmas
are excluded rather than silently replaced with a surface form.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from collections.abc import Iterable
from typing import Any, Literal

from .model import Document, ReadingStatus, Token, TokenKind
from .provenance import Provenance

WordView = Literal["surface", "normalized", "lemma"]
CountUnit = Literal["token", "document"]


def validate_view(view: str) -> WordView:
    if view not in ("surface", "normalized", "lemma"):
        raise ValueError(f"view must be 'surface', 'normalized', or 'lemma'; got {view!r}")
    return view  # type: ignore[return-value]


def normalize_word(text: str) -> str:
    """NFC, lowercase, final-sigma folding, then NFC; preserve diacritics.

    Full Unicode casefold would expand iota subscript and conflate distinct
    grammatical forms (e.g. ἐκκλησίᾳ and ἐκκλησίαι), so it is deliberately avoided.
    """
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", text).lower().replace("ς", "σ"))


def normalization_name(view: WordView) -> str:
    return "none (exact Token.text)" if view == "surface" else "NFC + lowercase + final-sigma fold + NFC; diacritics preserved"


def reading_statuses(statuses: Iterable[ReadingStatus | str] | None) -> frozenset[ReadingStatus]:
    """Validate a status selection; omitted means every editorial status."""
    if isinstance(statuses, str):
        statuses = (statuses,)
    return (frozenset(ReadingStatus(s.strip()) for s in statuses)
            if statuses is not None else frozenset(ReadingStatus))


def token_selected(token: Token, statuses: frozenset[ReadingStatus]) -> bool:
    """Select a whole token only when its reading and every typed segment qualify."""
    return token.status in statuses and (
        token.form_state is None
        or all(segment.status in statuses for segment in token.form_state.segments)
    )


def word_key(token: Token, view: WordView) -> str | None:
    """A lexical token's selected comparison key, or None for missing lemma/nonword."""
    if token.kind is not TokenKind.WORD:
        return None
    if view == "lemma":
        lemma = token.annotations.get("lemma")
        return normalize_word(lemma) if isinstance(lemma, str) and lemma.strip() else None
    return token.text if view == "surface" else normalize_word(token.text)


def count_words(
    documents: Iterable[Document], *, view: WordView, count_unit: CountUnit,
    statuses: frozenset[ReadingStatus],
) -> tuple[list[tuple[str, int]], dict[str, Any]]:
    """Count a selected view and describe its population before item filtering."""
    if count_unit not in ("token", "document"):
        raise ValueError(f"count_unit must be 'token' or 'document'; got {count_unit!r}")
    counts: Counter[str] = Counter()
    occurrences: dict[str, set[str]] = {}
    total_documents = selected = represented = excluded = missing = 0
    lemma_sources: Counter[str] = Counter()
    for doc in documents:
        total_documents += 1
        for token in doc.tokens:
            if token.kind is not TokenKind.WORD:
                continue
            if not token_selected(token, statuses):
                excluded += 1
                continue
            selected += 1
            key = word_key(token, view)
            if key is None:
                missing += 1
                continue
            represented += 1
            counts[key] += 1
            if count_unit == "document":
                occurrences.setdefault(key, set()).add(doc.id)
            if view == "lemma":
                lemma_sources[str(token.annotations.get("lemma_source") or "unspecified")] += 1
    values = counts if count_unit == "token" else Counter({w: len(ids) for w, ids in occurrences.items()})
    metadata: dict[str, Any] = {
        "view": view, "normalization": normalization_name(view), "count_unit": count_unit,
        "denominator": represented if count_unit == "token" else total_documents,
        "total_documents": total_documents, "selected_word_tokens": selected,
        "represented_word_tokens": represented, "excluded_word_tokens": excluded,
        "missing_lemma_tokens": missing,
        "reading_statuses": sorted(s.value for s in statuses),
        "status_scope": "whole token and every typed editorial segment",
        "lemma_sources": dict(sorted(lemma_sources.items())),
    }
    return sorted(values.items(), key=lambda kv: (-kv[1], kv[0])), metadata


class WordFrequencies(list[tuple[str, int]]):
    """List-compatible frequency pairs with their population and source provenance.

    ``metadata['denominator']`` counts represented lexical tokens for token
    frequency, or all selected documents (including empty ones) for document
    frequency. Lemma-source labels describe annotations, not verified accuracy.
    """

    def __init__(self, values: Iterable[tuple[str, int]], *, metadata: dict[str, Any],
                 provenance: Provenance | None = None) -> None:
        super().__init__(values)
        self.metadata = metadata
        self.provenance = provenance

    def cite(self) -> str:
        """Cite the corpus with this view, count unit, denominator, and status selection."""
        if self.provenance is None:
            raise ValueError("these frequencies carry no provenance to cite")
        m = self.metadata
        return (f"{self.provenance.cite()} [frequencies: {m['view']}; {m['normalization']}; "
                f"{m['count_unit']} denominator={m['denominator']}; "
                f"statuses={','.join(m['reading_statuses'])}; "
                f"missing lemmas={m['missing_lemma_tokens']}]")
