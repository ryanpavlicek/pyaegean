"""Shared base for index-backed lexica.

A lemma→entry index (``{lemma: {"hw", "def"}}``) served as a registry `Lexicon`,
with accent-folding and lemmatize-on-miss lookup, plus gzip load/store helpers.
Backends parse their own source (Scaife JSONL, Abbott-Smith TEI) into this common
index shape and serve it through `IndexLexicon`.
"""

from __future__ import annotations

import gzip
import json
import unicodedata
from pathlib import Path

from .lexicons import LexEntry, LexiconInfo


def norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip().lower()


def strip_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", norm(text))
    return "".join(c for c in nfd if not unicodedata.combining(c))


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
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)


def load_index(path: Path) -> dict[str, dict[str, str]]:
    """Load a gzipped lemma→entry index."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data: dict[str, dict[str, str]] = json.load(f)
    return data


class IndexLexicon:
    """A lemma→entry index served as a registry `Lexicon` (accent-fold, lemmatize-on-miss)."""

    def __init__(self, info: LexiconInfo, data: dict[str, dict[str, str]]) -> None:
        self.info = info
        self._data = data
        self._stripped: dict[str, str] = {}
        for key in data:
            self._stripped.setdefault(strip_accents(key), key)

    def __len__(self) -> int:
        return len(self._data)

    def _record(self, word: str) -> dict[str, str] | None:
        hit = self._data.get(norm(word))
        if hit is not None:
            return hit
        sk = self._stripped.get(strip_accents(word))
        if sk is not None:
            return self._data[sk]
        from .lemmatize import lemmatize

        lemma = lemmatize(word)
        if norm(lemma) != norm(word):
            hit = self._data.get(norm(lemma))
            if hit is not None:
                return hit
            sk = self._stripped.get(strip_accents(lemma))
            if sk is not None:
                return self._data[sk]
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
