"""Treebank-derived Greek lemmatizer + morphology (Perseus AGDT v2.1).

**Opt-in.** Call :func:`use_treebank` to download the Ancient Greek Dependency
Treebank (Greek, v2.1) into the user cache, build a *form → analyses* lexicon
(also cached), and have :func:`aegean.greek.lemmatize` / :func:`aegean.greek.analyze`
prefer attested, **correctly-accented** lemmas and full morphological features for
known forms — covering the irregular/contract/athematic/3rd-declension forms the
rule-based engine can't (e.g. ``εἶπον → λέγω``). On a miss they fall back to the
rule/seed engines. Default behaviour (without :func:`use_treebank`) is unchanged
and fully offline.

Data: ``github.com/PerseusDL/treebank_data`` ``v2.1/Greek/texts/*.tb.xml``,
pinned to a commit, licensed **CC BY-SA 3.0**. It is fetched to the cache and the
derived lexicon is built there — **never bundled** (respects ShareAlike, since the
package does not redistribute it, and keeps the wheel small). Word schema:
``<word form="…" lemma="…" postag="…"/>`` where ``postag`` is the Perseus 9-character
positional tag (pos, person, number, tense, mood, voice, gender, case, degree;
``-`` means not-applicable).
"""

from __future__ import annotations

import json
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from ..data import DataNotAvailableError, cache_dir, download_file
from .morphology import Analysis

__all__ = [
    "TreebankLexicon",
    "build_lexicon",
    "decode_postag",
    "disable_treebank",
    "use_treebank",
]

# Perseus AGDT v2.1 Greek, pinned for reproducibility.
_COMMIT = "bf4334f0af5e13d16b04c1cccd6237e683ac6f5f"
_BASE_URL = (
    f"https://raw.githubusercontent.com/PerseusDL/treebank_data/{_COMMIT}/v2.1/Greek/texts/"
)
_CACHE_SUBDIR = "agdt-greek"
_LEXICON_NAME = "agdt-greek-lexicon.json"

_AGDT_FILES: tuple[str, ...] = (
    "tlg0003.tlg001.perseus-grc1.1.tb.xml",
    "tlg0007.tlg004.perseus-grc1.tb.xml",
    "tlg0007.tlg015.perseus-grc1.tb.xml",
    "tlg0008.tlg001.perseus-grc1.12.tb.xml",
    "tlg0008.tlg001.perseus-grc1.13.tb.xml",
    "tlg0011.tlg001.perseus-grc2.tb.xml",
    "tlg0011.tlg002.perseus-grc2.tb.xml",
    "tlg0011.tlg003.perseus-grc1.tb.xml",
    "tlg0011.tlg004.perseus-grc1.tb.xml",
    "tlg0011.tlg005.perseus-grc2.tb.xml",
    "tlg0012.tlg001.perseus-grc1.tb.xml",
    "tlg0012.tlg002.perseus-grc1.tb.xml",
    "tlg0013.tlg002.perseus-grc1.tb.xml",
    "tlg0016.tlg001.perseus-grc1.1.tb.xml",
    "tlg0020.tlg001.perseus-grc1.tb.xml",
    "tlg0020.tlg002.perseus-grc1.tb.xml",
    "tlg0020.tlg003.perseus-grc1.tb.xml",
    "tlg0059.tlg001.perseus-grc1.tb.xml",
    "tlg0060.tlg001.perseus-grc3.11.tb.xml",
    "tlg0085.tlg001.perseus-grc2.tb.xml",
    "tlg0085.tlg002.perseus-grc2.tb.xml",
    "tlg0085.tlg003.perseus-grc2.tb.xml",
    "tlg0085.tlg004.perseus-grc2.tb.xml",
    "tlg0085.tlg005.perseus-grc1.tb.xml",
    "tlg0085.tlg006.perseus-grc2.tb.xml",
    "tlg0085.tlg007.perseus-grc1.tb.xml",
    "tlg0096.tlg002.opp-grc2.1-53.tb.xml",
    "tlg0540.tlg001.perseus-grc1.tb.xml",
    "tlg0540.tlg014.perseus-grc1.tb.xml",
    "tlg0540.tlg015.perseus-grc1.tb.xml",
    "tlg0540.tlg023.perseus-grc1.tb.xml",
    "tlg0543.tlg001.perseus-grc1.tb.xml",
    "tlg0548.tlg001.perseus-grc1.1.1.1-1.4.1.tb.xml",
)

# --- Perseus 9-character postag decoding -------------------------------------

_POS = {
    "n": "NOUN", "v": "VERB", "a": "ADJ", "d": "ADV", "l": "DET", "g": "PART",
    "c": "CCONJ", "r": "ADP", "p": "PRON", "m": "NUM", "i": "INTJ", "e": "INTJ",
    "u": "PUNCT", "x": "X",
}
_PERSON = {"1": "1", "2": "2", "3": "3"}
_NUMBER = {"s": "sg", "p": "pl", "d": "du"}
_TENSE = {"p": "pres", "i": "impf", "r": "perf", "l": "plup", "t": "futperf", "f": "fut", "a": "aor"}
_MOOD = {"i": "ind", "s": "subj", "o": "opt", "n": "inf", "m": "imp", "p": "part"}
_VOICE = {"a": "act", "p": "pass", "m": "mid", "e": "mp"}
_GENDER = {"m": "masc", "f": "fem", "n": "neut"}
_CASE = {"n": "nom", "g": "gen", "d": "dat", "a": "acc", "v": "voc", "l": "loc"}
_DEGREE = {"c": "comp", "s": "sup"}

# (Analysis field, position in the postag, code→value table). Field order matches
# Analysis.features() so a rendered analysis reads naturally.
_DECODERS: tuple[tuple[str, int, dict[str, str]], ...] = (
    ("case", 7, _CASE),
    ("number", 2, _NUMBER),
    ("gender", 6, _GENDER),
    ("tense", 3, _TENSE),
    ("voice", 5, _VOICE),
    ("mood", 4, _MOOD),
    ("person", 1, _PERSON),
    ("degree", 8, _DEGREE),
)


def decode_postag(tag: str) -> dict[str, str]:
    """Decode a Perseus 9-char postag into ``{field: value}`` (``pos`` plus any set
    morphological features). Unknown codes and ``-`` placeholders are skipped."""
    out: dict[str, str] = {}
    if not tag:
        return out
    pos = _POS.get(tag[0])
    if pos:
        out["pos"] = pos
    for field, idx, table in _DECODERS:
        if len(tag) > idx and tag[idx] != "-":
            value = table.get(tag[idx])
            if value:
                out[field] = value
    return out


# --- normalisation + lemma cleanup -------------------------------------------


def _norm(form: str) -> str:
    """The lexicon key: NFC, lower-cased, stripped."""
    return unicodedata.normalize("NFC", form).strip().lower()


def _strip_accents(form: str) -> str:
    nfd = unicodedata.normalize("NFD", _norm(form))
    return "".join(c for c in nfd if not unicodedata.combining(c))


def _clean_lemma(lemma: str) -> str:
    """NFC-normalise and drop Perseus homonym numbering (``μένω1`` → ``μένω``)."""
    lemma = unicodedata.normalize("NFC", lemma).strip()
    end = len(lemma)
    while end > 0 and lemma[end - 1].isdigit():
        end -= 1
    return lemma[:end] if end > 0 else lemma  # keep a purely-numeric lemma as-is


# --- building the lexicon ----------------------------------------------------

_FEATURE_FIELDS = ("case", "number", "gender", "tense", "voice", "mood", "person", "degree")


def _agdt_dir(*, download: bool) -> Path:
    """The cache directory of downloaded treebank files (fetching any missing)."""
    d = cache_dir() / _CACHE_SUBDIR
    if download:
        for name in _AGDT_FILES:
            dest = d / name
            if not dest.exists():
                download_file(_BASE_URL + name, dest)
    return d


def build_lexicon(*, source_dir: Path | str | None = None, force: bool = False) -> Path:
    """Build (and cache) the form→analyses JSON lexicon, returning its path.

    Downloads the AGDT Greek files into the cache first, unless ``source_dir`` is
    given (used by tests to parse a local fixture without any network). A present
    lexicon is reused unless ``force`` (or a ``source_dir``) is given.
    """
    out = cache_dir() / _LEXICON_NAME
    if out.exists() and not force and source_dir is None:
        return out

    if source_dir is not None:
        files = sorted(Path(source_dir).glob("*.tb.xml"))
    else:
        files = [_agdt_dir(download=True) / name for name in _AGDT_FILES]

    # form → Counter over deduped analyses (each analysis encoded as sorted items).
    agg: dict[str, Counter[tuple[tuple[str, str], ...]]] = {}
    for fp in files:
        if not fp.exists():
            continue
        for _event, elem in ET.iterparse(str(fp), events=("end",)):
            if elem.tag == "word":
                form = elem.get("form")
                lemma = elem.get("lemma")
                if form and lemma:
                    feats = decode_postag(elem.get("postag") or "")
                    analysis = {"lemma": _clean_lemma(lemma), "pos": feats.get("pos", "X")}
                    for field in _FEATURE_FIELDS:
                        if field in feats:
                            analysis[field] = feats[field]
                    dedup = tuple(sorted(analysis.items()))
                    agg.setdefault(_norm(form), Counter())[dedup] += 1
                elem.clear()

    # Serialise each form's analyses ordered by frequency (most attested first).
    lexicon: dict[str, list[dict[str, str]]] = {
        form: [dict(dedup) for dedup, _count in counter.most_common()]
        for form, counter in agg.items()
    }
    out.write_text(json.dumps(lexicon, ensure_ascii=False), encoding="utf-8")
    return out


# --- lexicon object + activation ---------------------------------------------


class TreebankLexicon:
    """An attested form→analyses lexicon built from the AGDT treebank."""

    def __init__(self, data: dict[str, list[dict[str, str]]]) -> None:
        self._data = data
        # Accent-insensitive fallback: stripped form → a real (accented) key.
        self._stripped: dict[str, str] = {}
        for key in data:
            self._stripped.setdefault(_strip_accents(key), key)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "TreebankLexicon":
        """Load a built lexicon JSON (defaults to the cached one)."""
        p = Path(path) if path is not None else cache_dir() / _LEXICON_NAME
        if not p.exists():
            raise DataNotAvailableError(
                f"no treebank lexicon at {p}; call build_lexicon() (or use_treebank()) first"
            )
        data: dict[str, list[dict[str, str]]] = json.loads(p.read_text(encoding="utf-8"))
        return cls(data)

    def __len__(self) -> int:
        return len(self._data)

    def _entries(self, form: str) -> list[dict[str, str]] | None:
        hit = self._data.get(_norm(form))
        if hit is not None:
            return hit
        key = self._stripped.get(_strip_accents(form))
        return self._data.get(key) if key is not None else None

    def analyze(self, form: str) -> tuple[Analysis, ...]:
        """Attested analyses for a form (frequency-ordered), or ``()`` if unknown."""
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
        """The most-attested lemma for a form, or ``None`` if unknown."""
        entries = self._entries(form)
        return entries[0]["lemma"] if entries else None


_ACTIVE: TreebankLexicon | None = None


def use_treebank(*, build: bool = True, force: bool = False) -> TreebankLexicon:
    """Activate the AGDT lexicon for this session.

    Downloads + builds it on first use (``build=True``); pass ``force=True`` to
    rebuild. Once active, :func:`aegean.greek.lemmatize` / :func:`analyze` prefer
    its attested analyses and fall back to the rule/seed engines on a miss.
    """
    global _ACTIVE
    if build and (force or not (cache_dir() / _LEXICON_NAME).exists()):
        build_lexicon(force=force)
    _ACTIVE = TreebankLexicon.load()
    return _ACTIVE


def disable_treebank() -> None:
    """Deactivate the treebank lexicon; restore the default rule/seed behaviour."""
    global _ACTIVE
    _ACTIVE = None


def active() -> TreebankLexicon | None:
    """The active lexicon, or ``None`` when the treebank backend is off (default)."""
    return _ACTIVE
