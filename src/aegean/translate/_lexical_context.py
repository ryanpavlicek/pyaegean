"""Bounded dictionary navigation evidence for an explicitly supplied analysis.

Only already active builtin dictionaries are consulted. Their existing direct
probes preserve collision-safe spelling rules without the ``lookup`` API's
module-level lemmatization fallback. Unknown backend contracts are reported as
unsupported rather than consulted. No dictionary, parser, or model is activated.

Exact, accent-preserving word overlap and supplied dependency features select
entry excerpts; neither establishes a contextual sense. Excerpts retain exact
half-open code-point offsets into ``LexEntry.body``. Cached entries can themselves
be abridgements or cross-references; this helper cannot restore absent material.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..ai.grounding import GroundingItem
from ..greek import koine, lexicon, lexicons
from ..greek.lemmatize import LemmaSource
from ..greek.lexicons import LexEntry, Lexicon, LexiconInfo
from ..greek.lexindex import IndexLexicon, concise
from ..greek.pipeline import TokenRecord

_MAX_RECORDS = 512
_MAX_REQUESTS = 48
_MAX_DICTIONARIES = 16
_MAX_SCAN_CHARS = 200_000
_MAX_IDENTITY_CHARS = 256
_MAX_CUES = 24
_MAX_CUE_CHARS = 64
_MIN_EXCERPT_CHARS = 256
_SUMMARY_RESERVE = 1024

_CONSTRUCTIONS = {
    "Case=Dat": r"\b(?:c\.\s*dat\.|with\s+dat\.|with\s+(?:the\s+)?dative\b)",
    "Case=Gen": r"\b(?:c\.\s*gen\.|with\s+gen(?:it)?\.|with\s+(?:the\s+)?genitive\b)",
    "Case=Acc": r"\b(?:c\.\s*acc\.|with\s+acc\.|with\s+(?:the\s+)?accusative\b)",
    "VerbForm=Inf": r"\b(?:c\.\s*inf\.|with\s+inf(?:in)?\.|with\s+(?:the\s+)?infinitive\b)",
    "Voice=Mid": r"\b(?:med\.|mid\.|middle\b)",
    "Voice=Pass": r"\b(?:pass\.|passive\b)",
}


@dataclass(frozen=True)
class _Candidate:
    record: TokenRecord
    info: LexiconInfo
    entry: LexEntry
    neighbors: tuple[TokenRecord, ...]


def _supported(backend: Lexicon) -> bool:
    # A subclass can replace a private probe with an unrelated plugin contract.
    # Check both the registry adapter and its wrapped implementation.
    return (
        type(backend) is IndexLexicon
        or type(backend) is lexicons._LSJAdapter
        and type(getattr(backend, "_b", None)) is lexicon.LSJLexicon
        or type(backend) is lexicons._DodsonAdapter
        and type(getattr(backend, "_b", None)) is koine.DodsonLexicon
    )


def _direct_entry(backend: Lexicon, lemma: str) -> LexEntry | None:
    """Use known builtin probe shapes only, never a plugin's arbitrary method."""
    if not _supported(backend):
        return None
    if isinstance(backend, IndexLexicon):
        record = backend._probe(lemma)
        if record is None:
            return None
        return LexEntry(record["hw"], concise(record["def"][:160]), record["def"], backend.info.id)
    if isinstance(backend, lexicons._LSJAdapter):
        raw = backend._b._probe(lemma)
        if raw is None:
            return None
        entry = lexicon._dict_to_entry(raw)
        return LexEntry(entry.headword, entry.short, str(entry), "lsj")
    if isinstance(backend, lexicons._DodsonAdapter):
        entry_nt = backend._b._probe(lemma)
        if entry_nt is None:
            return None
        return LexEntry(entry_nt.lemma, entry_nt.gloss, entry_nt.definition or entry_nt.gloss, "dodson")
    return None


def _norm(word: str) -> str:
    # casefold expands iota subscript into a spacing iota, merging distinct
    # spellings such as ἐκκλησίᾳ and ἐκκλησίαι. Navigation preserves that mark.
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", word).lower()).replace("ς", "σ")


def _words(text: str) -> list[tuple[str, int, int]]:
    """Letters and combining marks, with offsets into the unmodified string."""
    out: list[tuple[str, int, int]] = []
    start: int | None = None
    for index, char in enumerate(text):
        category = unicodedata.category(char)
        if category.startswith("L") or (start is not None and category.startswith("M")):
            if start is None:
                start = index
        elif start is not None:
            out.append((_norm(text[start:index]), start, index))
            start = None
    if start is not None:
        out.append((_norm(text[start:]), start, len(text)))
    return out


def _greek(word: str) -> bool:
    return any("\u0370" <= char <= "\u03ff" or "\u1f00" <= char <= "\u1fff" for char in word)


def _match(candidate: _Candidate, body: str) -> tuple[int | None, str, str | None]:
    record = candidate.record
    excluded = {_norm(record.text), _norm(record.lemma), _norm(candidate.entry.headword)}
    cues: dict[str, tuple[int, str]] = {}
    constructions: set[str] = set()
    for neighbor in candidate.neighbors:
        linked = neighbor.head == record.index or record.head == neighbor.index
        nearby = abs(neighbor.index - record.index) <= 3
        if not (linked or nearby) or neighbor.index == record.index:
            continue
        for word in (neighbor.text, neighbor.lemma):
            if len(word) > _MAX_CUE_CHARS or not _greek(word):
                continue
            normalized = _norm(word)
            if normalized not in excluded and len(cues) < _MAX_CUES:
                weight = 2 if linked else 1
                if normalized not in cues or weight > cues[normalized][0]:
                    cues[normalized] = (weight, word)
        if linked and neighbor.feats:
            constructions.update(set(neighbor.feats.split("|")) & _CONSTRUCTIONS.keys())
    if record.feats:
        constructions.update(set(record.feats.split("|")) & {"Voice=Mid", "Voice=Pass"})

    # Longer, explicitly linked words beat incidental nearby function words.
    hits = [(cues[word][0], len(word), start, cues[word][1])
            for word, start, _end in _words(body) if word in cues]
    if hits:
        _weight, _length, offset, cue = min(hits, key=lambda hit: (-hit[0], -hit[1], hit[2]))
        return offset, "word-overlap-only", cue
    for feature in sorted(constructions):
        found = re.search(_CONSTRUCTIONS[feature], body, flags=re.IGNORECASE)
        if found:
            return found.start(), "construction-marker-only", feature
    return None, "no-contextual-match", None


def _window(body: str, offset: int, limit: int) -> tuple[int, int]:
    """Retain a clause boundary when nearby, otherwise a marked partial clause."""
    start = max(0, offset - limit // 3)
    # Semicolon/newline delimiters are navigation boundaries, not parsed senses.
    # Dictionary clauses often inherit their governing construction from the
    # preceding examples. Retain up to two preceding clauses, not just the
    # semicolon immediately before the matched word.
    boundaries = [index for index in range(start, offset) if body[index] in "\n;"]
    if boundaries:
        start = boundaries[-3] + 1 if len(boundaries) >= 3 else boundaries[0] + 1
    end = min(len(body), start + limit)
    # A complete containing clause is preferable to stopping in a word.
    stops = [position + 1 for delimiter in (";", "\n")
             if (position := body.find(delimiter, offset, end)) >= 0]
    if stops and max(stops) - start >= limit // 2:
        end = max(stops)
    return start, end


def _excerpt_span(body: str, start: int, end: int, reason: str) -> dict[str, Any]:
    # Avoid emitting a detached combining mark or half a canonical cluster.
    while start < end and unicodedata.category(body[start]).startswith("M"):
        start += 1
    while start < end < len(body) and unicodedata.category(body[end]).startswith("M"):
        end -= 1
    return {
        "start": start, "end": end, "reason": reason,
        "left_cut": start > 0 and body[start - 1] not in "\n;",
        "right_cut": end < len(body) and (end == 0 or body[end - 1] not in "\n;"),
    }


def _spans(candidate: _Candidate, budget: int) -> tuple[list[dict[str, Any]], str | None]:
    original = candidate.entry.body or candidate.entry.gloss
    if len(original) <= budget:
        return [_excerpt_span(original, 0, len(original), "complete-cached-entry")], None
    scanned = original[:_MAX_SCAN_CHARS]
    offset, reason, cue = _match(candidate, scanned)
    opening = min(160, budget // 5)
    other = min(240, budget // 5)
    main = budget - opening - other
    ranges = [(0, opening, "entry-opening")]
    if offset is not None:
        start, end = _window(scanned, offset, main)
        ranges.append((start, end, reason))
    else:
        # A neutral interior excerpt avoids a first-sense-only selection when no
        # supplied contextual cue occurs. It is not called a relevant sense.
        start, end = _window(scanned, len(scanned) // 2, main)
        ranges.append((start, end, reason))
    ranges.append((max(0, len(scanned) - other), len(scanned), "other-entry-context"))
    merged: list[dict[str, Any]] = []
    for start, end, label in sorted(ranges):
        if merged and start <= merged[-1]["end"]:
            merged[-1]["end"] = max(end, merged[-1]["end"])
            merged[-1]["reason"] += "; " + label
        else:
            merged.append({"start": start, "end": end, "reason": label})
    return [_excerpt_span(original, span["start"], span["end"], span["reason"])
            for span in merged], cue


def _item(candidate: _Candidate, budget: int) -> GroundingItem:
    body = candidate.entry.body or candidate.entry.gloss
    spans, cue = _spans(candidate, budget)
    selected = sum(span["end"] - span["start"] for span in spans)
    fragments = [body[span["start"]:span["end"]] for span in spans]
    record = candidate.record
    provenance: dict[str, Any] = {
        "dictionary": candidate.entry.lexicon,
        "dictionary_source": candidate.info.source,
        "headword": candidate.entry.headword,
        "lemma": record.lemma,
        "sentence": record.sentence,
        "token_index": record.index,
        "lookup": "direct-probe-no-lemmatization",
        "contextual_sense_verified": False,
        "entry_field": "body" if candidate.entry.body else "gloss",
        "entry_chars": len(body),
        "scanned_chars": min(len(body), _MAX_SCAN_CHARS),
        "omitted_chars": len(body) - selected,
        "excerpt_spans": spans,
        "other_senses_may_be_omitted": selected < len(body),
    }
    if candidate.info.id != candidate.entry.lexicon:
        provenance["registry_dictionary"] = candidate.info.id
    if cue is not None:
        provenance["matched_cue"] = cue
    return GroundingItem(
        "Dictionary candidate, contextual sense unverified; exact entry excerpts: "
        + json.dumps(fragments, ensure_ascii=False),
        source="lexicon:" + candidate.info.id,
        ref=record.text,
        status="reference",
        provenance=provenance,
    )


def _summary(stats: dict[str, Any]) -> GroundingItem:
    return GroundingItem(
        "Contextual dictionary evidence coverage; excerpts are candidates, not verified senses.",
        source="lexicon:contextual-coverage", status="reference", provenance=stats,
    )


def contextual_lexical_evidence(
    analysis: Sequence[TokenRecord],
    *,
    max_entries: int = 16,
    entry_budget: int = 1200,
    total_budget: int = 12000,
) -> list[GroundingItem]:
    """Return bounded builtin dictionary candidates plus a coverage summary.

    ``entry_budget`` caps original entry characters selected per item;
    ``total_budget`` caps the sum of full ``GroundingItem.render()`` lengths,
    including provenance and summary. Budget reductions may omit entire entries.
    Requests alternate by supplied sentence/lemma and dictionary, without rarity
    or content-POS gating. Exact supplied lemmas reach known builtin direct probes;
    no surface-word, alternate-lemma, or module lemmatizer fallback is attempted.
    NFC/lowercase comparisons preserve accents, breathings and iota subscript in
    navigation cues. Lookup requests retain distinct supplied lemma strings.

    At most 512 records, 48 sentence/lemma requests, 16 active dictionaries, and
    200,000 characters per entry are examined. Every bound and lookup omission is
    reported; unavailable dictionaries and unsupported plugin contracts produce a
    summary even when no entry can be included. Entries do not certify the supplied
    lemma, parse, or contextual interpretation, including human-reviewed lemmas.
    """
    for name, value, lower, upper in (
        ("max_entries", max_entries, 0, 128),
        ("entry_budget", entry_budget, _MIN_EXCERPT_CHARS, 8192),
        ("total_budget", total_budget, _SUMMARY_RESERVE, 1_000_000),
    ):
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError(f"{name} must be an integer between {lower} and {upper}")
    if not isinstance(analysis, Sequence) or isinstance(analysis, (str, bytes)):
        raise ValueError("analysis must be a sequence of TokenRecord values")

    records: list[TokenRecord] = []
    invalid = excluded = 0
    for record in analysis[:_MAX_RECORDS]:
        if not isinstance(record, TokenRecord):
            raise ValueError("analysis must contain TokenRecord values")
        if not all(isinstance(value, str) for value in (record.text, record.lemma, record.upos)):
            raise ValueError("token text, lemma, and upos must be strings")
        if record.feats is not None and not isinstance(record.feats, str):
            raise ValueError("token feats must be a string or None")
        if not isinstance(record.lemma_source, LemmaSource):
            raise ValueError("token lemma_source must be a LemmaSource value")
        if record.feats is not None and len(record.feats) > 1024:
            invalid += 1
            continue
        if type(record.sentence) is not int or type(record.index) is not int:
            raise ValueError("token sentence and index must be integers")
        if record.sentence < 0 or record.index < 1:
            raise ValueError("token sentence must be nonnegative and index must be positive")
        if record.head is not None and (type(record.head) is not int or record.head < 0):
            raise ValueError("token head must be a nonnegative integer or None")
        if any(value is not None and value.bit_length() > 63
               for value in (record.sentence, record.index, record.head)):
            invalid += 1
            continue
        if len(record.lemma) > _MAX_IDENTITY_CHARS or len(record.text) > _MAX_IDENTITY_CHARS:
            invalid += 1
            continue
        if record.upos == "PUNCT" or not record.lemma_resolved or record.neural_analyzed is False:
            excluded += 1
            continue
        records.append(record)

    groups: dict[tuple[int, str], TokenRecord] = {}
    for record in records:
        if record.lemma.strip():
            groups.setdefault((record.sentence, record.lemma), record)
        else:
            excluded += 1
    requests = list(groups.values())[:_MAX_REQUESTS]
    active = lexicons._active_map()
    # Oversized plugin identifiers are excluded before sorting or rendering.
    backends = [(name, backend) for name, backend in active.items()
                if isinstance(name, str) and len(name) <= _MAX_IDENTITY_CHARS]
    backends.sort(key=lambda pair: pair[0])
    considered = backends[:_MAX_DICTIONARIES]
    supported: list[Lexicon] = []
    unsupported = malformed = 0
    for _name, backend in considered:
        if not _supported(backend):
            unsupported += 1
        elif not isinstance(backend.info, LexiconInfo):
            malformed += 1
        elif not all(isinstance(value, str) and len(value) <= _MAX_IDENTITY_CHARS
                     for value in (backend.info.id, backend.info.source)):
            malformed += 1
        else:
            supported.append(backend)

    rows: list[list[_Candidate]] = []
    errors = misses = lookups = 0
    for request_index, record in enumerate(requests):
        row: list[_Candidate] = []
        rotation = request_index % len(supported) if supported else 0
        ordered = supported[rotation:] + supported[:rotation]
        neighbors = tuple(member for member in records if member.sentence == record.sentence)
        for backend in ordered:
            lookups += 1
            try:
                entry = _direct_entry(backend, record.lemma)
            except Exception:
                errors += 1
                continue
            if entry is None:
                misses += 1
                continue
            if not all(isinstance(value, str) for value in
                       (entry.headword, entry.body, entry.gloss, entry.lexicon)):
                malformed += 1
                continue
            if (not (entry.body or entry.gloss)
                    or len(entry.headword) > _MAX_IDENTITY_CHARS
                    or len(entry.lexicon) > _MAX_IDENTITY_CHARS):
                malformed += 1
                continue
            row.append(_Candidate(record, backend.info, entry, neighbors))
        rows.append(row)
    candidates = [row[round_index] for round_index in range(len(supported))
                  for row in rows if round_index < len(row)]
    selected = candidates[:max_entries]

    # Allocate equally across the fair request/source order. If even a bounded
    # contextual excerpt cannot fit, reduce entry count and redistribute.
    items: list[GroundingItem] = []
    remaining = total_budget - _SUMMARY_RESERVE
    while selected:
        allowance = remaining // len(selected)
        items = []
        for candidate in selected:
            budget = entry_budget
            item = _item(candidate, budget)
            while len(item.render()) > allowance and budget > _MIN_EXCERPT_CHARS:
                budget = max(_MIN_EXCERPT_CHARS, budget - (len(item.render()) - allowance))
                item = _item(candidate, budget)
            if len(item.render()) > allowance:
                break
            items.append(item)
        if len(items) == len(selected):
            break
        selected = selected[:-1]
    if not selected:
        items = []

    if not active:
        availability = "no-active-dictionaries"
    elif not requests:
        availability = "no-eligible-lemmas"
    elif not supported:
        availability = "no-supported-dictionaries"
    elif not candidates:
        availability = "no-matching-entries"
    elif not items:
        availability = "entries-omitted-by-budget-or-limit"
    else:
        availability = "entries-included"
    stats: dict[str, Any] = {
        "availability": availability,
        "active_dictionaries": len(active),
        "supported_dictionaries": len(supported),
        "unsupported_dictionaries": unsupported,
        "dictionaries_omitted": len(active) - len(considered),
        "input_records": len(analysis),
        "records_omitted": max(0, len(analysis) - _MAX_RECORDS),
        "excluded_records": excluded,
        "invalid_or_oversized": invalid + malformed,
        "lemma_requests": len(groups),
        "requests_omitted": max(0, len(groups) - _MAX_REQUESTS),
        "lookups": lookups,
        "lookup_misses": misses,
        "lookup_errors": errors,
        "matching_entries": len(candidates),
        "entries_shown": len(items),
        "entries_omitted": len(candidates) - len(items),
        "entry_budget": entry_budget,
        "total_budget": total_budget,
        "contextual_sense_verified": False,
    }
    summary = _summary(stats)
    # The fixed-size summary remains available even under the smallest budget.
    assert len(summary.render()) <= _SUMMARY_RESERVE
    return [*items, summary]
