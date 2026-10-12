"""Shared base for index-backed lexica.

A lemma→entry index (``{lemma: {"hw", "def"}}``) served as a registry `Lexicon`,
with accent-folding and lemmatize-on-miss lookup, plus gzip load/store helpers.
Backends parse their own source (Scaife JSONL, Abbott-Smith TEI) into this common
index shape and serve it through `IndexLexicon`.
"""

from __future__ import annotations

import gzip
import json
import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path

from ..data import load_gzip_json
from .lexicons import LexEntry, LexiconInfo


def norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip().lower()


def strip_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", norm(text))
    return "".join(c for c in nfd if not unicodedata.combining(c))


_GRAVE = "̀"
_ACUTE = "́"


def accent_marks(text: str) -> set[tuple[int, str]]:
    """The combining marks of a word as ``(base-letter index, mark)`` pairs, with
    graves levelled to acutes."""
    marks: set[tuple[int, str]] = set()
    index = -1
    for char in unicodedata.normalize("NFD", norm(text)):
        if unicodedata.combining(char):
            marks.add((index, _ACUTE if char == _GRAVE else char))
        else:
            index += 1
    return marks


def compatible_accents(query: str, key: str) -> bool:
    """Whether *query* may be answered by headword *key*.

    Every mark the headword carries must be present in the query at the same letter,
    and anything extra in the query must be an acute -- that is the enclitic throwback
    (``ἄνθρωπός τις``, Smyth §183), the one case where a correctly written form
    carries an accent its citation form does not. Two words that simply accent the
    same letters differently are different words: ``εἰ`` "if" is not ``εἷ`` "where"."""
    query_marks = accent_marks(query)
    key_marks = accent_marks(key)
    if not key_marks <= query_marks:
        return False
    return all(mark == _ACUTE for _index, mark in query_marks - key_marks)


def level_grave(text: str) -> str:
    """Grave for acute. A grave is the positional form of an acute on a non-final
    word (Smyth §154), so ``καλὸς`` and ``καλός`` are the same headword; two
    different accents on the same letters are two different words."""
    nfd = unicodedata.normalize("NFD", norm(text))
    return unicodedata.normalize("NFC", nfd.replace(_GRAVE, _ACUTE))


def _headword_key(key: str) -> str:
    """A lookup alias without editorial counters or Cunliffe's leading dagger.

    Perseus/Middle Liddell append digits, Abbott-Smith appends ``_N``, and
    Cunliffe prefixes ``†``. Keep every Greek accent, breathing and other character.
    The original index keys and displayed entries remain unchanged.
    """
    alias = re.sub(r"(?<=[^\W\d_])_?[0-9]+$", "", norm(key)).removeprefix("†")
    return alias or norm(key)


def _lookup_maps(
    keys: Iterable[str],
) -> tuple[dict[str, str | None], dict[str, str | None], dict[str, tuple[str, ...]]]:
    """Grave-levelled and accent-stripped keys, including unambiguous aliases."""
    levelled: dict[str, str | None] = {}
    stripped: dict[str, tuple[str, ...]] = {}
    for key in keys:
        for spelling in {norm(key), _headword_key(key)}:
            folded = level_grave(spelling)
            if folded not in levelled:
                levelled[folded] = key
            elif levelled[folded] != key:
                levelled[folded] = None
            folded = strip_accents(spelling)
            candidates = stripped.get(folded, ())
            if key not in candidates:
                # A record's own alias is not a second candidate.
                stripped[folded] = (*candidates, key)
    return (
        levelled,
        {folded: keys[0] if len(keys) == 1 else None for folded, keys in stripped.items()},
        {folded: keys for folded, keys in stripped.items() if len(keys) > 1},
    )


def _ambiguous_key(word: str, ambiguous: dict[str, tuple[str, ...]]) -> bool:
    """Whether a failed probe has several headwords compatible with its marks.

    Differently marked candidates cannot forbid inflection fallback: ``ᾧ`` is not
    ``ω`` or ``ὦ``, and must still lemmatize to ``ὅς``.
    """
    query = _headword_key(word)
    unaccented = strip_accents(query) == query
    return any(
        sum(
            unaccented or compatible_accents(query, _headword_key(key))
            for key in ambiguous.get(strip_accents(spelling), ())
        ) > 1
        for spelling in {norm(word), query}
    )


def concise(text: str, limit: int = 160) -> str:
    """A concise one-line gloss from a (possibly long) definition."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    head = cut[:space] if space > limit // 2 else cut
    return head.rstrip(" ,;:.") + "…"


def write_index(path: Path, index: dict[str, dict[str, str]]) -> None:
    """Write a gzipped lemma→entry index."""
    from .._atomic import atomic_path

    path.parent.mkdir(parents=True, exist_ok=True)
    with atomic_path(path) as tmp:
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False)


def load_index(path: Path) -> dict[str, dict[str, str]]:
    """Load a gzipped lemma→entry index."""
    data: dict[str, dict[str, str]] = load_gzip_json(path)
    return data


class IndexLexicon:
    """A lemma→entry index served as a registry `Lexicon` (accent-fold, lemmatize-on-miss)."""

    def __init__(self, info: LexiconInfo, data: dict[str, dict[str, str]]) -> None:
        self.info = info
        self._data = data
        self._levelled, self._stripped, self._ambiguous = _lookup_maps(data)

    def __len__(self) -> int:
        return len(self._data)

    def _probe(self, word: str) -> dict[str, str] | None:
        """Exact key, then an unambiguous grave-levelled key or editorial alias,
        then an unambiguous accent-stripped key with compatible query accents.

        Folding an ACCENTED query onto a differently accented headword is a homograph
        guess, not a hit, and it was answering the commonest words in Greek with the
        wrong entry: εἰ "if" returned εἷ "where", λαός "people" returned λᾶος "stone",
        and καλῶς "well" returned κάλως "rope". An honest miss lets the caller fall
        through to the next dictionary."""
        hit = self._data.get(norm(word))
        if hit is not None:
            return hit
        key = self._levelled.get(level_grave(word))
        if key is not None:
            return self._data[key]
        key = self._stripped.get(strip_accents(word))
        if key is not None and (
            strip_accents(word) == norm(word)  # unaccented query: nothing to contradict
            or compatible_accents(_headword_key(word), _headword_key(key))
        ):
            return self._data[key]
        return None

    def _record(self, word: str) -> dict[str, str] | None:
        hit = self._probe(word)
        if hit is not None:
            return hit
        if _ambiguous_key(word, self._ambiguous):
            return None
        from .lemmatize import lemmatize

        lemma = lemmatize(word)
        if norm(lemma) != norm(word):
            return self._probe(lemma)
        return None

    def lookup(self, word: str) -> LexEntry | None:
        rec = self._record(word)
        if rec is None:
            return None
        return LexEntry(
            headword=rec["hw"], gloss=concise(rec["def"]), body=rec["def"], lexicon=self.info.id
        )

    def gloss(self, word: str) -> str | None:
        e = self.lookup(word)
        return None if e is None else f"{e.headword}: {e.gloss}"
