"""Koine / New Testament glossing via the Dodson Greek lexicon.

The Dodson lexicon (John Jeffrey Dodson; public domain / CC0) is a Strong's-keyed
Greek-English glossary of the New Testament. It is small enough to bundle in the wheel,
so this backend needs no download: ``use_dodson()`` loads it, then ``gloss_nt`` /
``lookup_nt`` resolve a word (lemmatizing on a miss) and ``gloss_strongs`` resolves a
Strong's number — the form the NT corpus tokens carry.

This is the Koine counterpart to ``use_lsj`` (classical LSJ glossing): same one-backend /
one-global / one-error idiom, a different, NT-focused lexicon. They compose — an NT word's
Strong's number gives a Dodson gloss, and its lemma feeds the LSJ index for the fuller
classical entry.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache


class DodsonNotLoadedError(RuntimeError):
    """Raised when a Dodson glossing call is made before ``use_dodson()``."""


@dataclass(frozen=True, slots=True)
class DodsonEntry:
    """One Dodson lexicon entry."""

    strongs: str
    lemma: str
    gloss: str          # the brief gloss
    definition: str     # the fuller definition (falls back to the brief gloss)


def _key(s: str) -> str:
    """Accent- and case-insensitive lookup key (NFD, drop combining marks, casefold)."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)
    ).casefold()


class DodsonLexicon:
    """The Dodson lexicon indexed by Strong's number and (accent-folded) lemma."""

    def __init__(self, entries: dict[str, DodsonEntry]) -> None:
        self._by_strongs = entries
        self._by_lemma: dict[str, DodsonEntry] = {}
        for e in entries.values():
            self._by_lemma.setdefault(_key(e.lemma), e)

    def __len__(self) -> int:
        return len(self._by_strongs)

    @classmethod
    def load(cls) -> DodsonLexicon:
        from ..data import load_bundled_json

        payload = load_bundled_json("greek", "dodson.json")
        entries = {
            s: DodsonEntry(
                strongs=s, lemma=rec.get("lemma", ""),
                gloss=rec.get("gloss", ""), definition=rec.get("definition", rec.get("gloss", "")),
            )
            for s, rec in payload["entries"].items()
        }
        return cls(entries)

    def by_strongs(self, strongs: str | int) -> DodsonEntry | None:
        return self._by_strongs.get(str(strongs).lstrip("G").lstrip("g").lstrip("0") or "0")

    def lookup(self, word: str) -> DodsonEntry | None:
        """The Dodson entry for a word — by lemma, accent-folded, then lemmatized on a miss."""
        hit = self._by_lemma.get(_key(word))
        if hit is not None:
            return hit
        from .lemmatize import lemmatize

        lemma = lemmatize(word)
        if lemma and lemma != word:
            return self._by_lemma.get(_key(lemma))
        return None

    def gloss(self, word: str) -> str | None:
        entry = self.lookup(word)
        return entry.gloss if entry is not None else None


_ACTIVE: DodsonLexicon | None = None


def use_dodson(*, force: bool = False) -> DodsonLexicon:
    """Activate Dodson Koine glossing for this session (loads the bundled lexicon).

    No download — the lexicon is bundled (CC0). ``gloss_nt`` / ``lookup_nt`` /
    ``gloss_strongs`` resolve against it afterwards."""
    global _ACTIVE
    if force or _ACTIVE is None:
        _ACTIVE = DodsonLexicon.load()
    return _ACTIVE


def disable_dodson() -> None:
    """Deactivate Dodson glossing."""
    global _ACTIVE
    _ACTIVE = None


def active() -> DodsonLexicon | None:
    """The active Dodson lexicon, or ``None`` when Koine glossing is off (the default)."""
    return _ACTIVE


def _require() -> DodsonLexicon:
    if _ACTIVE is None:
        raise DodsonNotLoadedError(
            "Dodson is not loaded — call aegean.greek.use_dodson() first"
        )
    return _ACTIVE


def gloss_nt(word: str) -> str | None:
    """Brief Koine gloss for a word (lemmatized on a miss); requires `use_dodson`."""
    return _require().gloss(word)


def lookup_nt(word: str) -> DodsonEntry | None:
    """Full Dodson entry for a word; requires `use_dodson`. ``None`` if unknown."""
    return _require().lookup(word)


def gloss_strongs(strongs: str | int) -> str | None:
    """Brief Koine gloss for a Strong's number (e.g. ``3056`` -> 'a word, speech, …');
    requires `use_dodson`. The NT corpus tokens carry these numbers in
    ``Token.annotations['strongs']``."""
    entry = _require().by_strongs(strongs)
    return entry.gloss if entry is not None else None


@lru_cache(maxsize=1)
def _strongs_gloss_map() -> dict[str, str]:
    """Strong's -> brief gloss, straight from the bundled lexicon (no activation needed).

    Used to self-gloss the NT corpus tokens at load time."""
    from ..data import load_bundled_json

    payload = load_bundled_json("greek", "dodson.json")
    return {s: rec.get("gloss", "") for s, rec in payload["entries"].items() if rec.get("gloss")}
