"""UniMorph paradigm lexicon — offline irregular/third-declension coverage (opt-in).

**Opt-in.** Call `use_paradigms` to fetch the prebuilt UniMorph Ancient Greek paradigm
index into the user cache and have `aegean.greek.lemmatize` / `analyze` resolve the
irregular, third-declension, and heteroclite nominal forms the seed table and the
generalizing ending rules cannot — ``γυναικός → γυνή``, ``πατράσι → πατήρ``,
``ὕδατος → ὕδωρ``, ``κόλακος → κόλαξ`` — together with their case/number/gender. On a miss
the cascade falls back to the ending rules unchanged. Default behaviour (without
`use_paradigms`) is unchanged and fully offline.

The index is a ``{form: [analysis, ...]}`` table whose analysis records have the SAME shape
as the AGDT treebank lexicon (`aegean.greek.treebank`) — ``{lemma, pos, case, number,
gender?}`` — so both backends serve identical `Analysis` records and the consumer layer is
uniform. It is a curated inflection table (Wiktionary paradigms), so a hit is a **grounded,
correctly-accented** lemma reported under the ``SEED`` evidence class (a curated lexical
lookup, like the bundled seed table): it does not need human review.

Cascade rank: **below** the neural pipeline / treebank / bundled seed table, **above** the
generalizing ending rules — the same slot `use_treebank` occupies, one tier lower. The data
is the purely-nominal UniMorph Ancient Greek set (``github.com/unimorph/grc``, **CC BY-SA
3.0**, from Wiktionary), fetched as a prebuilt gzip index and **never bundled** (ShareAlike;
keeps the wheel small). Build recipe: ``scripts/build_paradigm_table.py``.
"""

from __future__ import annotations

import gzip
import json
import unicodedata
from pathlib import Path
from typing import Any

from ..data import DataNotAvailableError, cache_dir, fetch_prebuilt, load_gzip_json
from .morphology import Analysis

__all__ = [
    "ParadigmLexicon",
    "active",
    "disable_paradigms",
    "load_paradigms",
    "use_paradigms",
]

_INDEX_NAME = "grc-paradigms.json.gz"
_PREBUILT = "grc-paradigms"  # the data/_REMOTE dataset name

_GRAVE = "̀"
_ACUTE = "́"


def _norm(form: str) -> str:
    """The lookup key: NFC, lower-cased, with a grave folded to the acute (the grave is only
    the running-text notation of a final acute, Smyth §155, so καλὸν must find the citation
    καλόν). Deliberately **accent-sensitive** otherwise: unlike the treebank lexicon, the
    paradigm table carries no accent-stripped fallback — Greek is dense with accent/breathing
    minimal pairs (ὁδός/ὀδούς, ὄρος/ὅρος, βασιλεία/βασίλεια), and an accent-blind fallback
    resolves the wrong lemma far more often than it helps (measured on the NT: it added ~1,000
    regressions for ~40 corrections)."""
    nfd = unicodedata.normalize("NFD", form.strip().lower()).replace(_GRAVE, _ACUTE)
    return unicodedata.normalize("NFC", nfd)


def _validate(data: Any, source: str) -> dict[str, list[dict[str, str]]]:
    """Check a loaded object is a ``{form: [analysis-dict, ...]}`` index; clean error if not."""
    if not isinstance(data, dict):
        raise DataNotAvailableError(f"{source}: not a paradigm index (expected a JSON object)")
    for key, entries in data.items():
        if not isinstance(key, str) or not isinstance(entries, list) or not all(
            isinstance(e, dict) and "lemma" in e for e in entries
        ):
            raise DataNotAvailableError(
                f"{source}: malformed paradigm index (form {key!r} is not mapped to a list of "
                "analysis records)"
            )
    return data


def _load_json_gz(path: Path) -> dict[str, list[dict[str, str]]]:
    """Load a ``.json.gz`` (or plain ``.json``) index, turning any corruption into a clean
    `DataNotAvailableError` rather than leaking a raw gzip/JSON traceback."""
    try:
        if path.suffix == ".gz" or path.name.endswith(".json.gz"):
            data = load_gzip_json(path)
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
    except DataNotAvailableError:
        raise
    except (OSError, gzip.BadGzipFile, ValueError, json.JSONDecodeError) as exc:
        raise DataNotAvailableError(f"{path}: could not read paradigm index ({exc})") from exc
    return _validate(data, str(path))


class ParadigmLexicon:
    """A form→analyses paradigm lexicon (UniMorph grc), served like `TreebankLexicon`."""

    def __init__(self, data: dict[str, list[dict[str, str]]]) -> None:
        self._data = data

    @classmethod
    def load(cls, path: Path | str | None = None) -> "ParadigmLexicon":
        """Load a built paradigm index (defaults to the cached ``grc-paradigms.json.gz``)."""
        p = Path(path) if path is not None else cache_dir() / _INDEX_NAME
        if not p.exists():
            raise DataNotAvailableError(
                f"no paradigm index at {p}; call use_paradigms() first (fetches grc-paradigms)"
            )
        return cls(_load_json_gz(p))

    def __len__(self) -> int:
        return len(self._data)

    def _entries(self, form: str) -> list[dict[str, str]] | None:
        return self._data.get(_norm(form))

    def analyze(self, form: str) -> tuple[Analysis, ...]:
        """Paradigm analyses for a form, or ``()`` if unknown — same record shape as
        `TreebankLexicon.analyze`, so the two backends are interchangeable."""
        entries = self._entries(form)
        if not entries:
            return ()
        return tuple(
            Analysis(
                lemma=e["lemma"], pos=e.get("pos", "X"),
                case=e.get("case"), number=e.get("number"), gender=e.get("gender"),
                tense=e.get("tense"), voice=e.get("voice"), mood=e.get("mood"),
                person=e.get("person"), degree=e.get("degree"), lemma_certain=True,
            )
            for e in entries
        )

    def lemmatize(self, form: str) -> str | None:
        """The first (paradigm) lemma for a form, or ``None`` if unknown."""
        entries = self._entries(form)
        return entries[0]["lemma"] if entries else None

    def pos(self, form: str) -> str | None:
        """The first part-of-speech tag for a form, or ``None`` if unknown."""
        entries = self._entries(form)
        return entries[0].get("pos") if entries else None


def load_paradigms(
    *, build: bool = True, force: bool = False, path: Path | str | None = None
) -> ParadigmLexicon:
    """Load the paradigm lexicon, fetching its prebuilt index on first use.

    ``path`` loads a specific index file (a local build or a test fixture) with no network.
    Otherwise the ``grc-paradigms`` prebuilt index is fetched into the cache (``build=True``;
    ``force=True`` re-fetches). Raises `DataNotAvailableError` when the index is neither
    cached nor fetchable (no pinned URL yet — set ``PYAEGEAN_GRC_PARADIGMS_URL`` to a mirror,
    or run ``scripts/build_paradigm_table.py`` and point ``path`` at the output)."""
    if path is not None:
        return ParadigmLexicon.load(path)
    out = cache_dir() / _INDEX_NAME
    if build and (force or not out.exists()):
        if not fetch_prebuilt(_PREBUILT, out):
            raise DataNotAvailableError(
                "the UniMorph paradigm index is not available: it has no pinned download URL "
                "yet. Set PYAEGEAN_GRC_PARADIGMS_URL to a mirror, or build it with "
                "scripts/build_paradigm_table.py and pass its path to use_paradigms(path=...)."
            )
    return ParadigmLexicon.load(out)


_ACTIVE: ParadigmLexicon | None = None


def use_paradigms(
    *, build: bool = True, force: bool = False, path: Path | str | None = None
) -> ParadigmLexicon:
    """Activate the UniMorph paradigm lexicon for this session.

    Fetches the prebuilt index on first use (``build=True``); pass ``path`` to load a local
    build/fixture offline, or ``force=True`` to re-fetch. Once active,
    `aegean.greek.lemmatize` / `analyze` consult it for irregular/third-declension forms —
    ranked below the treebank/seed tiers and above the generalizing ending rules — and fall
    back to those rules on a miss. A paradigm hit is reported under the ``SEED`` evidence
    class (a grounded, curated lookup)."""
    global _ACTIVE
    _ACTIVE = load_paradigms(build=build, force=force, path=path)
    return _ACTIVE


def disable_paradigms() -> None:
    """Deactivate the paradigm lexicon; restore the default seed/rule behaviour."""
    global _ACTIVE
    _ACTIVE = None


def active() -> ParadigmLexicon | None:
    """The active paradigm lexicon, or ``None`` when the backend is off (default)."""
    return _ACTIVE
