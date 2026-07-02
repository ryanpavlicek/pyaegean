"""Compound-query predicate engine over the corpus.

A faithful port of the workbench ``src/lib/queryEngine.ts`` — the field
registry, per-document/per-word predicates, AND/OR/NOT combination, and the
query evaluator — adapted to the script-agnostic `Document` / `Corpus`
model. The presentational Query Builder UI is intentionally not ported.

The predicates are deterministic corpus filters (not exploratory): they select
documents and words by surface properties. Sign-pattern matching reuses
`aegean.analysis.patterns.word_matches_sign_pattern`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field as _field, replace
from typing import TYPE_CHECKING, Any, Literal

from ..core.model import Document
from ..core.provenance import Provenance
from .patterns import word_matches_sign_pattern

if TYPE_CHECKING:
    from ..core.corpus import Corpus

# ── Field registry ───────────────────────────────────────────────────────────
FieldKind = Literal[
    "text", "number", "boolean", "site", "scribe", "period", "support", "word", "sign"
]
Scope = Literal["inscription", "word"]
Connector = Literal["and", "or"]
Output = Literal["inscriptions", "words"]


@dataclass(frozen=True, slots=True)
class FieldDef:
    """A queryable field: its display label, scope (inscription/word), and value kind."""

    label: str
    scope: Scope
    kind: FieldKind


FIELDS: dict[str, FieldDef] = {
    "id-contains": FieldDef("Inscription ID contains", "inscription", "text"),
    "site-is": FieldDef("Site is", "inscription", "site"),
    "scribe-is": FieldDef("Scribe is", "inscription", "scribe"),
    "period-is": FieldDef("Period is", "inscription", "period"),
    "support-is": FieldDef("Support is", "inscription", "support"),
    "has-image": FieldDef("Has facsimile image", "inscription", "boolean"),
    "has-annotation": FieldDef("Has annotation", "inscription", "boolean"),
    "ins-contains-word": FieldDef("Contains exact word", "inscription", "word"),
    "word-contains": FieldDef("Word contains text", "word", "text"),
    "word-prefix": FieldDef("Word starts with", "word", "text"),
    "word-suffix": FieldDef("Word ends with", "word", "text"),
    "word-min-syllables": FieldDef("Word has ≥ N signs", "word", "number"),
    "word-max-syllables": FieldDef("Word has ≤ N signs", "word", "number"),
    "word-contains-sign": FieldDef("Word contains sign", "word", "sign"),
    "word-cooccurs-with": FieldDef("Word co-occurs with", "word", "word"),
    "word-sign-pattern": FieldDef("Word matches sign pattern", "word", "text"),
}


@dataclass(frozen=True, slots=True)
class FilterRow:
    """One query row. ``connector`` joins this row to the running result within
    its scope (ignored on the first row); ``negate`` flips the row's own test."""

    field: str
    value: Any
    connector: Connector | None = None
    negate: bool = False


@dataclass(frozen=True, slots=True)
class QueryResults:
    """A query's result set: the matching inscriptions and/or ``(word, count)`` pairs.

    In ``words``, ``count`` is the word's **document frequency**: the number of
    distinct inscriptions the word occurs in (e.g. ``("KU-RO", 34)`` means KU-RO
    appears in 34 separate documents), not how many times it is written. A word
    repeated within one inscription still counts that inscription once. This
    differs from `Corpus.word_frequencies`, whose ``count`` is the token
    frequency (every occurrence). The list is sorted by descending count, then
    by word.

    `Corpus.query` attaches the corpus's ``provenance`` and a ``description``
    of the filters, so `cite` can cite the exact result set used in a paper."""

    inscriptions: list[Document]
    words: list[tuple[str, int]]
    provenance: Provenance | None = None
    description: str = ""

    def cite(self, style: str = "plain") -> str:
        """Cite this exact result set: the source plus the query that produced it.

        ``style``: ``"plain"`` (one line), ``"bibtex"`` (a ``@misc`` entry), or
        ``"apa"``. Raises `ValueError` when the results carry no provenance
        (results from `eval_query` directly rather than `Corpus.query`)."""
        if self.provenance is None:
            raise ValueError("these results carry no provenance to cite — use Corpus.query")
        n, unit = (
            (len(self.inscriptions), "inscriptions")
            if self.inscriptions or not self.words
            else (len(self.words), "words")
        )
        note = f"query: {self.description or 'all'} → {n} {unit}"
        if style == "plain":
            return f"{self.provenance.cite()} [{note}]"
        stamped = replace(self.provenance, notes=self.provenance.notes + (note,))
        if style == "bibtex":
            return stamped.bibtex(key="aegean-query")
        if style == "apa":
            return stamped.apa()
        raise ValueError(f"style must be 'plain', 'bibtex', or 'apa'; got {style!r}")

    def to_corpus(self, source: "Corpus") -> "Corpus":
        """Rebuild a reusable `Corpus` from this result set's matched inscriptions.

        Carries ``source``'s sign inventory and script id, and stamps a ``subset:`` provenance
        note so `cite` on the saved corpus names the query. A words-only result has no
        inscriptions, so it yields an empty corpus — query with ``output="inscriptions"``."""
        from ..core.corpus import Corpus

        prov = source.provenance
        if prov is not None:
            note = (
                f"subset: query({self.description or 'all'}) → "
                f"{len(self.inscriptions)} documents"
            )
            prov = replace(prov, notes=prov.notes + (note,))
        return Corpus(self.inscriptions, source.sign_inventory, prov, source.script_id)


@dataclass(frozen=True, slots=True)
class WordEntry:
    """Per-word index entry: the documents a (multi-sign) word appears in."""

    count: int
    inscription_ids: tuple[str, ...]
    sites: frozenset[str] = _field(default_factory=frozenset)


def default_value(field: str) -> Any:
    """The neutral default value for a field, by kind."""
    k = FIELDS[field].kind
    if k == "number":
        return 2
    if k == "boolean":
        return True
    return ""


# ── Evaluation ───────────────────────────────────────────────────────────────
def _combine_rows(rows: list[FilterRow], test) -> bool:  # type: ignore[no-untyped-def]
    """Combine a scope's rows left-to-right: the first row seeds the result,
    each later row joins with its connector (default AND). An empty scope is
    vacuously true; ``negate`` flips an individual row's test."""
    acc: bool | None = None
    for f in rows:
        m = test(f)
        if f.negate:
            m = not m
        if acc is None:
            acc = m
        else:
            acc = (acc or m) if f.connector == "or" else (acc and m)
    return acc if acc is not None else True


def _doc_token_texts(doc: Document) -> list[str]:
    return [t.text for t in doc.tokens]


def _inscription_row_match(doc: Document, f: FilterRow, annotated_ids: set[str]) -> bool:
    v = f.value
    fld = f.field
    if fld == "id-contains":
        return not v or str(v).upper() in doc.id.upper()
    if fld == "site-is":
        return not v or doc.meta.site == v
    if fld == "scribe-is":
        return not v or doc.meta.scribe == v
    if fld == "period-is":
        return not v or doc.meta.period == v
    if fld == "support-is":
        return not v or doc.meta.support == v
    if fld == "has-image":
        has = len(doc.meta.images) > 0
        return has if v else not has
    if fld == "has-annotation":
        has = doc.id in annotated_ids
        return has if v else not has
    if fld == "ins-contains-word":
        return not v or str(v) in _doc_token_texts(doc)
    return True


def inscription_matches(
    doc: Document, filters: Iterable[FilterRow], annotated_ids: set[str]
) -> bool:
    """True if a document satisfies the inscription-scope filter rows (AND/OR/NOT-combined)."""
    rows = [f for f in filters if FIELDS[f.field].scope == "inscription"]
    return _combine_rows(rows, lambda f: _inscription_row_match(doc, f, annotated_ids))


def _word_row_match(word: str, f: FilterRow, cooccur_map: dict[str, set[str]]) -> bool:
    v = f.value
    fld = f.field
    upper = word.upper()
    parts = word.split("-")
    if fld == "word-contains":
        return not v or str(v).upper() in upper
    if fld == "word-prefix":
        return not v or upper.startswith(str(v).upper())
    if fld == "word-suffix":
        return not v or upper.endswith(str(v).upper())
    if fld == "word-min-syllables":
        # A blank value is neutral (matches everything), like the workbench.
        return not str(v or "").strip() or len(parts) >= int(v)
    if fld == "word-max-syllables":
        return not str(v or "").strip() or len(parts) <= int(v)
    if fld == "word-contains-sign":
        if not v:
            return True
        # Both sides share the sign key: only the "*" of unread labels is
        # stripped (so "*301" and "301" both find *301-bearing words) and the
        # query folds to the corpus's uppercase convention. Subscripted signs
        # stay distinct: RA₂ matches only RA₂, never plain RA, and vice versa.
        target = _sign_key(str(v)).upper()
        return any(_sign_key(p).upper() == target for p in parts)
    if fld == "word-cooccurs-with":
        return not v or str(v) in cooccur_map.get(word, set())
    if fld == "word-sign-pattern":
        return not v or word_matches_sign_pattern(word, str(v))
    return True


def _sign_key(sign: str) -> str:
    """The shared sign-key rule (the workbench's ``signKeys.ts``; the same rule
    the lineara ``phonetic.py`` lookup applies): strip only the "*" of unread
    sign labels (*118, *301). Subscripted signs (RA₂, PA₃, TA₂, PU₂) are
    distinct signs, not variants of their plain series, so subscripts are
    preserved."""
    return sign.replace("*", "")


def word_matches(
    word: str, filters: Iterable[FilterRow], cooccur_map: dict[str, set[str]]
) -> bool:
    """True if a word satisfies the word-scope filter rows (AND/OR/NOT-combined)."""
    rows = [f for f in filters if FIELDS[f.field].scope == "word"]
    return _combine_rows(rows, lambda f: _word_row_match(word, f, cooccur_map))


def eval_query(
    filters: list[FilterRow],
    output: Output,
    documents: list[Document],
    word_index: dict[str, WordEntry],
    annotated_ids: set[str],
    cooccur_map: dict[str, set[str]],
) -> QueryResults:
    """Run a query (filters + output mode) over pre-built indices and return the
    result set in canonical shape.

    For ``output="words"`` each ``(word, count)`` pair's ``count`` is the word's
    document frequency (the number of matching inscriptions it occurs in), not
    its token frequency; a word repeated within one inscription counts that
    inscription once."""
    matching = [d for d in documents if inscription_matches(d, filters, annotated_ids)]
    has_word_filters = any(FIELDS[f.field].scope == "word" for f in filters)

    if output == "inscriptions":
        if not has_word_filters:
            return QueryResults(matching, [])
        kept = [
            d
            for d in matching
            if any(
                "-" in t.text and word_matches(t.text, filters, cooccur_map)
                for t in d.tokens
            )
        ]
        return QueryResults(kept, [])

    matched_ids = {d.id for d in matching}
    word_counts: dict[str, int] = {}
    for w, entry in word_index.items():
        if "-" not in w:
            continue
        if not word_matches(w, filters, cooccur_map):
            continue
        cnt = sum(1 for doc_id in entry.inscription_ids if doc_id in matched_ids)
        if cnt > 0:
            word_counts[w] = cnt
    words = sorted(word_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return QueryResults([], words)


def summarize_filters(filters: list[FilterRow]) -> str:
    """One-line, human-readable label for a filter set."""
    parts: list[str] = []
    for f in filters:
        d = FIELDS[f.field]
        if d.kind == "boolean":
            val_txt = "yes" if f.value else "no"
        else:
            val_txt = str("" if f.value is None else f.value).strip() or "(any)"
        neg = "NOT " if f.negate else ""
        parts.append(f"{neg}{d.label}: {val_txt}")
    return " · ".join(parts) or "(no filters)"


# ── Index builders + corpus-level convenience ────────────────────────────────
def build_word_index(documents: Iterable[Document]) -> dict[str, WordEntry]:
    """Index every multi-sign word to the documents it appears in."""
    ids: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    sites: dict[str, set[str]] = {}
    for doc in documents:
        seen: set[str] = set()
        for t in doc.tokens:
            w = t.text
            if "-" not in w:
                continue
            counts[w] = counts.get(w, 0) + 1
            if w not in seen:
                seen.add(w)
                ids.setdefault(w, []).append(doc.id)
                sites.setdefault(w, set()).add(doc.meta.site)
    return {
        w: WordEntry(counts[w], tuple(ids[w]), frozenset(sites[w])) for w in ids
    }


def build_cooccurrence_map(documents: Iterable[Document]) -> dict[str, set[str]]:
    """Map each multi-sign word to the set of multi-sign words it shares a
    document with."""
    cooccur: dict[str, set[str]] = {}
    for doc in documents:
        words = sorted({t.text for t in doc.tokens if "-" in t.text})
        for w in words:
            bucket = cooccur.setdefault(w, set())
            for other in words:
                if other != w:
                    bucket.add(other)
    return cooccur


def run_query(
    corpus: Any,
    filters: list[FilterRow],
    output: Output = "inscriptions",
    annotated_ids: set[str] | None = None,
) -> QueryResults:
    """Build the indices from a `Corpus` and evaluate ``filters``.

    Convenience over `eval_query` for the common whole-corpus case. The result
    carries the corpus's provenance and a filter summary, so it is citable
    via `QueryResults.cite`.
    """
    documents = list(corpus)
    results = eval_query(
        filters,
        output,
        documents,
        build_word_index(documents),
        annotated_ids or set(),
        build_cooccurrence_map(documents),
    )
    return replace(
        results,
        provenance=getattr(corpus, "provenance", None),
        description=summarize_filters(filters),
    )
