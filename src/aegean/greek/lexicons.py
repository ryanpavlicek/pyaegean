"""Lexicon registry — pluggable Greek dictionaries behind one glossing API.

Generalizes the ad-hoc ``use_lsj`` (classical LSJ) and ``use_dodson`` (Koine/NT)
backends into a registry: ``lexica()`` lists what is available, ``use_lexicon(id)``
activates a hosted dictionary, and ``gloss(word, dictionary=...)`` /
``entry(word, dictionary=...)`` resolve a word against a chosen (or any active)
lexicon. ``lexicon_link`` builds a Logeion deep-link for the dictionaries pyaegean
does not host.

Each hosted lexicon is fetch-to-cache (sha256-pinned, never bundled) and license-gated;
the deep-link layer covers the rest (Autenrieth, Slater, Montanari, DGE, Bailly, ...),
which Logeion aggregates.
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from . import koine, lexicon
from .lexicon import LexiconNotLoadedError

__all__ = [
    "LexEntry",
    "Lexicon",
    "LexiconInfo",
    "LexiconNotLoadedError",
    "active_lexica",
    "disable_lexicon",
    "entry",
    "gloss",
    "lexica",
    "lexicon_link",
    "register_lexicon",
    "use_lexicon",
]


@dataclass(frozen=True, slots=True)
class LexiconInfo:
    """Metadata for one registered lexicon."""

    id: str
    name: str
    scope: str       # "classical" | "Homeric" | "NT" | "lyric" | ...
    license: str
    source: str
    hosted: bool     # True: pyaegean ingests it; False: deep-link only


@dataclass(frozen=True, slots=True)
class LexEntry:
    """A dictionary entry, uniform across lexica."""

    headword: str
    gloss: str          # a concise gloss
    body: str           # the fuller definition / senses
    lexicon: str        # the source lexicon id

    def __str__(self) -> str:
        return f"{self.headword} ({self.lexicon}): {self.body or self.gloss}"


@runtime_checkable
class Lexicon(Protocol):
    """The interface a lexicon backend exposes to the registry."""

    info: LexiconInfo

    def lookup(self, word: str) -> LexEntry | None: ...
    def gloss(self, word: str) -> str | None: ...


@dataclass
class _Spec:
    info: LexiconInfo
    loader: Callable[..., Lexicon]


_SPECS: dict[str, _Spec] = {}
_ACTIVE: dict[str, Lexicon] = {}

# Priority for an unspecified ``dictionary=`` (classical first, then Homeric, then NT).
_DEFAULT_ORDER = ("lsj", "middle-liddell", "cunliffe", "abbott-smith", "dodson")


def register_lexicon(info: LexiconInfo, loader: Callable[..., Lexicon]) -> None:
    """Register a lexicon plugin: its metadata and a loader that activates it."""
    _SPECS[info.id] = _Spec(info=info, loader=loader)


def lexica() -> list[LexiconInfo]:
    """Every registered lexicon's metadata (hosted and deep-link), id-sorted."""
    return [s.info for s in sorted(_SPECS.values(), key=lambda s: s.info.id)]


def use_lexicon(dictionary: str, **kwargs: object) -> Lexicon:
    """Activate a hosted lexicon by id, fetching/building its index on first use."""
    spec = _SPECS.get(dictionary)
    if spec is None:
        raise KeyError(f"unknown lexicon {dictionary!r}; see greek.lexica()")
    if not spec.info.hosted:
        raise ValueError(
            f"{dictionary!r} is deep-link only; use greek.lexicon_link(word) instead"
        )
    lex = spec.loader(**kwargs)
    _ACTIVE[dictionary] = lex
    return lex


def disable_lexicon(dictionary: str) -> None:
    """Deactivate a lexicon."""
    _ACTIVE.pop(dictionary, None)
    if dictionary == "lsj":
        lexicon.disable_lsj()
    elif dictionary == "dodson":
        koine.disable_dodson()


def _active_map() -> dict[str, Lexicon]:
    """Currently-active lexica, including the legacy ``use_lsj`` / ``use_dodson`` globals."""
    out: dict[str, Lexicon] = dict(_ACTIVE)
    lsj = lexicon.active()
    if "lsj" not in out and lsj is not None:
        out["lsj"] = _LSJAdapter(lsj)
    dodson = koine.active()
    if "dodson" not in out and dodson is not None:
        out["dodson"] = _DodsonAdapter(dodson)
    return out


def active_lexica() -> list[str]:
    """Ids of the lexica currently active."""
    return sorted(_active_map())


def _resolve(dictionary: str | None) -> list[Lexicon]:
    active = _active_map()
    if dictionary is not None:
        lex = active.get(dictionary)
        if lex is not None:
            return [lex]
        if dictionary in _SPECS:
            raise LexiconNotLoadedError(
                f"lexicon {dictionary!r} is not loaded — "
                f"call greek.use_lexicon({dictionary!r}) first"
            )
        raise KeyError(f"unknown lexicon {dictionary!r}; see greek.lexica()")
    if not active:
        raise LexiconNotLoadedError(
            "no lexicon is loaded — call greek.use_lexicon(...) "
            "(or use_lsj / use_dodson) first"
        )
    ordered = [active[k] for k in _DEFAULT_ORDER if k in active]
    ordered += [active[k] for k in sorted(active) if k not in _DEFAULT_ORDER]
    return ordered


def gloss(word: str, *, dictionary: str | None = None) -> str | None:
    """A concise gloss for ``word`` from ``dictionary`` (or the first active lexicon
    that has it). With no active lexicon, raises `LexiconNotLoadedError`."""
    for lex in _resolve(dictionary):
        g = lex.gloss(word)
        if g is not None:
            return g
    return None


def entry(word: str, *, dictionary: str | None = None) -> LexEntry | None:
    """The full `LexEntry` for ``word`` from ``dictionary`` (or the first active
    lexicon that has it)."""
    for lex in _resolve(dictionary):
        e = lex.lookup(word)
        if e is not None:
            return e
    return None


_LINKS = {
    "logeion": "https://logeion.uchicago.edu/{w}",
    "perseus": "https://www.perseus.tufts.edu/hopper/morph?l={w}&la=greek",
}


def lexicon_link(word: str, *, service: str = "logeion", lemmatize: bool = True) -> str:
    """A deep-link to ``word`` in an online dictionary aggregator (Logeion by default).

    Covers the lexica pyaegean does not host (Autenrieth, Slater, Montanari, DGE,
    Bailly, ...): Logeion aggregates them. ``lemmatize`` (default) links the lemma."""
    template = _LINKS.get(service)
    if template is None:
        raise KeyError(f"unknown link service {service!r}; choices: {sorted(_LINKS)}")
    target = word
    if lemmatize:
        from .lemmatize import lemmatize as _lemmatize

        target = _lemmatize(word) or word
    return template.format(w=urllib.parse.quote(target))


# --- adapters over the existing LSJ / Dodson backends ------------------------

_LSJ_INFO = LexiconInfo(
    id="lsj",
    name="Liddell-Scott-Jones, A Greek-English Lexicon",
    scope="classical",
    license="CC BY-SA 4.0 (Perseus)",
    source="PerseusDL/lexica",
    hosted=True,
)
_DODSON_INFO = LexiconInfo(
    id="dodson",
    name="Dodson, Greek-English Lexicon (NT)",
    scope="NT",
    license="CC0 (public domain)",
    source="biblicalhumanities/Dodson",
    hosted=True,
)


class _LSJAdapter:
    """Presents a loaded `lexicon.LSJLexicon` as a registry `Lexicon`."""

    info = _LSJ_INFO

    def __init__(self, backend: lexicon.LSJLexicon) -> None:
        self._b = backend

    def lookup(self, word: str) -> LexEntry | None:
        e = self._b.lookup(word)
        if e is None:
            return None
        return LexEntry(headword=e.headword, gloss=e.short, body=str(e), lexicon="lsj")

    def gloss(self, word: str) -> str | None:
        e = self.lookup(word)
        return None if e is None else f"{e.headword}: {e.gloss}"


class _DodsonAdapter:
    """Presents a loaded `koine.DodsonLexicon` as a registry `Lexicon`."""

    info = _DODSON_INFO

    def __init__(self, backend: koine.DodsonLexicon) -> None:
        self._b = backend

    def lookup(self, word: str) -> LexEntry | None:
        e = self._b.lookup(word)
        if e is None:
            return None
        return LexEntry(
            headword=e.lemma, gloss=e.gloss, body=e.definition or e.gloss, lexicon="dodson"
        )

    def gloss(self, word: str) -> str | None:
        e = self.lookup(word)
        return None if e is None else f"{e.headword}: {e.gloss}"


def _deeplink_only(**_kwargs: object) -> Lexicon:  # pragma: no cover - never called
    raise ValueError("deep-link-only lexicon; use greek.lexicon_link(word)")


def _register_builtins() -> None:
    register_lexicon(_LSJ_INFO, lambda **kw: _LSJAdapter(lexicon.use_lsj(**kw)))
    register_lexicon(_DODSON_INFO, lambda **kw: _DodsonAdapter(koine.use_dodson(**kw)))
    # Dictionaries pyaegean does not host: reachable via lexicon_link (Logeion aggregates them).
    for _id, _name, _scope in (
        ("autenrieth", "Autenrieth, A Homeric Dictionary", "Homeric"),
        ("slater", "Slater, A Lexicon to Pindar", "lyric"),
        ("montanari", "Montanari, The Brill Dictionary of Ancient Greek", "classical"),
    ):
        register_lexicon(
            LexiconInfo(
                id=_id, name=_name, scope=_scope,
                license="(rights vary; linked, not hosted)",
                source="logeion.uchicago.edu", hosted=False,
            ),
            _deeplink_only,
        )


_register_builtins()
