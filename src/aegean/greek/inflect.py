"""Inflection synthesis: the inverse of lemmatization.

Given a lemma and a target morphological feature spec, produce the attested inflected
form(s). Where the lemmatizer maps a form to its lemma, the inflector maps a lemma plus
features back to the form(s) that realise it, read off the same AGDT treebank the analysis
stack already uses.

Opt-in and offline: `use_inflector()` builds (and caches, via the treebank lexicon) the
inverse index, then `inflect` / `paradigm` resolve against it. Coverage is what the corpus
attests: every (lemma, features) cell seen in the AGDT is generated exactly. Unseen lemmas
or cells are not synthesised by this lookup layer (a generalising edit-tree layer, mirroring
the lemmatizer, can be added later).

Feature values use the same short codes as the analyzer: ``pos`` NOUN/VERB/ADJ/...,
``case`` nom/gen/dat/acc/voc/loc, ``number`` sg/pl/du, ``gender`` masc/fem/neut, ``tense``
pres/impf/aor/perf/plup/fut/futperf, ``voice`` act/mid/pass/mp, ``mood`` ind/subj/opt/inf/
imp/part, ``person`` 1/2/3, ``degree`` comp/sup.

Built from the AGDT (CC BY-SA 3.0), fetched and cached, never bundled.
"""

from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from pathlib import Path

from .treebank import _FEATURE_FIELDS, _clean_lemma, build_lexicon

__all__ = [
    "Inflector",
    "InflectorNotLoadedError",
    "active",
    "disable_inflector",
    "inflect",
    "paradigm",
    "use_inflector",
]

# Feature keys an inflection query accepts: POS plus the morphological fields the treebank
# lexicon records.
_FEATURES: tuple[str, ...] = ("pos", *_FEATURE_FIELDS)


class InflectorNotLoadedError(RuntimeError):
    """Raised when an inflection call is made before `use_inflector`."""


def _key(lemma: str) -> str:
    return _clean_lemma(unicodedata.normalize("NFC", lemma)).lower()


def _validated(features: dict[str, str | None]) -> dict[str, str]:
    want = {k: v for k, v in features.items() if v is not None}
    unknown = set(want) - set(_FEATURES)
    if unknown:
        raise ValueError(
            f"unknown inflection feature(s) {sorted(unknown)}; valid keys: {list(_FEATURES)}"
        )
    return want


class Inflector:
    """An inverse-lemmatization index: lemma -> attested ``(features, form)`` cells."""

    def __init__(self, index: dict[str, list[tuple[dict[str, str], str]]]) -> None:
        self._index = index

    @classmethod
    def from_lexicon(cls, lexicon: dict[str, list[dict[str, str]]]) -> Inflector:
        """Invert a treebank form->analyses lexicon into lemma->(features, form) cells.

        Forms keep the lexicon's frequency order (most-attested first); duplicate
        (features, form) cells per lemma are collapsed."""
        index: dict[str, list[tuple[dict[str, str], str]]] = defaultdict(list)
        seen: dict[str, set[tuple[tuple[tuple[str, str], ...], str]]] = defaultdict(set)
        for form, analyses in lexicon.items():
            for a in analyses:
                lemma = a.get("lemma")
                if not lemma:
                    continue
                lk = lemma.lower()
                feats = {k: a[k] for k in _FEATURES if k in a}
                sig = (tuple(sorted(feats.items())), form)
                if sig not in seen[lk]:
                    seen[lk].add(sig)
                    index[lk].append((feats, form))
        return cls(dict(index))

    def inflect(self, lemma: str, **features: str | None) -> tuple[str, ...]:
        """Attested form(s) of ``lemma`` matching ``features`` (a partial set of the keys
        in `_FEATURES`), most-attested first. Empty if nothing matches."""
        want = _validated(features)
        forms: list[str] = []
        for feats, form in self._index.get(_key(lemma), ()):
            if all(feats.get(k) == v for k, v in want.items()) and form not in forms:
                forms.append(form)
        return tuple(forms)

    def paradigm(self, lemma: str) -> tuple[tuple[dict[str, str], str], ...]:
        """Every attested ``(features, form)`` cell of ``lemma`` (empty if unattested)."""
        return tuple((dict(feats), form) for feats, form in self._index.get(_key(lemma), ()))

    def __len__(self) -> int:
        return len(self._index)


_ACTIVE: Inflector | None = None


def _lexicon_path() -> Path:
    from ..data import cache_dir
    from .treebank import _LEXICON_NAME

    return cache_dir() / _LEXICON_NAME


def use_inflector(*, build: bool = True, force: bool = False) -> Inflector:
    """Activate inflection synthesis for this session.

    Builds (and caches) the AGDT lexicon on first use (``build=True``; downloads the AGDT
    files if needed), inverts it into the form index, and makes `inflect` / `paradigm`
    resolve against it. ``build=False`` loads an already-built lexicon."""
    global _ACTIVE
    path = build_lexicon(force=force) if build else _lexicon_path()
    lexicon: dict[str, list[dict[str, str]]] = json.loads(path.read_text(encoding="utf-8"))
    _ACTIVE = Inflector.from_lexicon(lexicon)
    return _ACTIVE


def disable_inflector() -> None:
    """Deactivate inflection synthesis."""
    global _ACTIVE
    _ACTIVE = None


def active() -> Inflector | None:
    """The active inflector, or ``None`` when synthesis is off (the default)."""
    return _ACTIVE


def inflect(lemma: str, **features: str | None) -> tuple[str, ...]:
    """Attested inflected form(s) of ``lemma`` for the given features (e.g.
    ``inflect("λόγος", case="gen", number="sg")``); requires `use_inflector`. Empty tuple
    if nothing matching is attested."""
    if _ACTIVE is None:
        raise InflectorNotLoadedError(
            "inflection synthesis is not loaded — call aegean.greek.use_inflector() first"
        )
    return _ACTIVE.inflect(lemma, **features)


def paradigm(lemma: str) -> tuple[tuple[dict[str, str], str], ...]:
    """The full attested paradigm of ``lemma`` as ``(features, form)`` cells; requires
    `use_inflector`."""
    if _ACTIVE is None:
        raise InflectorNotLoadedError(
            "inflection synthesis is not loaded — call aegean.greek.use_inflector() first"
        )
    return _ACTIVE.paradigm(lemma)
