"""LSJ glossing — the full Perseus Liddell-Scott-Jones lexicon (opt-in).

**Opt-in.** Call `use_lsj` to download the Perseus LSJ (TEI) into the user
cache, build a *lemma → entry* index (also cached), and then `gloss` /
`lookup` turn a Greek word into its dictionary entry. Looking up an inflected
form works: it tries the form, then (on a miss) lemmatizes — using the treebank
backend if active — and retries. Default behaviour without `use_lsj` touches
no network.

Data: ``github.com/PerseusDL/lexica`` ``…/grc/lsj/grc.lsj.perseus-eng{1..27}.xml``,
pinned to a commit, **CC BY-SA 4.0** (Perseus Digital Library; see NOTICE for the
required attribution). It is fetched to the cache and the index is built there —
**never bundled** (respects ShareAlike and keeps the wheel small). Entry markup is
``<entryFree key="lo/gos">`` with ``<orth>`` headwords and nested ``<sense>``
elements; the ``key``/``<orth>``/``<foreign>`` Greek is **Beta Code**, converted
here with `aegean.greek.betacode_to_unicode`.
"""

from __future__ import annotations

import gzip
import json
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..data import cache_dir, download_file
from .normalize import betacode_to_unicode

__all__ = [
    "LSJEntry",
    "LSJLexicon",
    "LexiconNotLoadedError",
    "Sense",
    "build_index",
    "disable_lsj",
    "gloss",
    "lookup",
    "use_lsj",
]

_COMMIT = "b5e707bdda2d6c8e0bb6c29657454996b4fb04d7"
_BASE_URL = (
    f"https://raw.githubusercontent.com/PerseusDL/lexica/{_COMMIT}"
    "/CTS_XML_TEI/perseus/pdllex/grc/lsj/"
)
_FILES: tuple[str, ...] = tuple(f"grc.lsj.perseus-eng{i}.xml" for i in range(1, 28))
_CACHE_SUBDIR = "lsj-perseus"
_INDEX_NAME = "lsj-perseus-index.json.gz"

# Tags whose text is Beta Code Greek (convert to Unicode); citations are compacted.
_BETACODE_TAGS = {"foreign", "ref", "quote", "orth"}


class LexiconNotLoadedError(RuntimeError):
    """Raised when gloss/lookup is called before `use_lsj`."""


# --- TEI flattening ----------------------------------------------------------


def _local(tag: str) -> str:
    """Local tag name, ignoring any XML namespace."""
    return tag.rsplit("}", 1)[-1]


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip().lower()


def _strip_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", _norm(text))
    return "".join(c for c in nfd if not unicodedata.combining(c))


def _btc(text: str | None) -> str:
    """Beta Code → Unicode, dropping metrical marks (``^`` vrachy, ``_`` macron)."""
    if not text:
        return ""
    cleaned = text.replace("^", "").replace("_", "")
    try:
        return betacode_to_unicode(cleaned)
    except Exception:  # pragma: no cover - fall back to raw on any conversion issue
        return text


def _ws(text: str) -> str:
    return " ".join(text.split())


def _greek_initial(text: str) -> bool:
    """Whether the first letter is Greek — LSJ 'forms' senses (dialectal variants,
    inflections) lead with Greek, whereas a real definition leads with English."""
    for ch in text:
        if ch.isalpha():
            return "Ͱ" <= ch <= "Ͽ" or "ἀ" <= ch <= "῿"
    return False


def _short_gloss(senses: tuple[Sense, ...], lead: str) -> str:
    """A concise gloss: the first sense that reads as an English definition (skipping
    the morphological/forms senses that lead with Greek), else the first sense."""
    for s in senses:
        if s.text and not _greek_initial(s.text):
            return s.text
    return senses[0].text if senses else lead


def _compact_bibl(elem: ET.Element) -> str:
    """A citation rendered compactly, e.g. ``Il. 8.403``."""
    return _ws("".join(elem.itertext()))


def _flatten(elem: ET.Element) -> str:
    """Flatten an element's mixed content to text — converting Beta Code in
    ``<foreign>``/``<ref>``/``<quote>``/``<orth>``, compacting ``<bibl>`` citations,
    and skipping nested ``<sense>`` (those are captured separately)."""
    parts: list[str] = [elem.text or ""]
    for child in elem:
        tag = _local(child.tag)
        if tag == "sense":
            pass  # captured as its own Sense; don't duplicate its text
        elif tag in _BETACODE_TAGS:
            parts.append(_btc(child.text))
        elif tag == "bibl":
            parts.append(_compact_bibl(child))
        else:
            parts.append(_flatten(child))
        parts.append(child.tail or "")
    return "".join(parts)


@dataclass(frozen=True, slots=True)
class Sense:
    """One LSJ sense: its marker (``A``, ``II``, …), nesting level, and text."""

    marker: str
    level: int
    text: str


@dataclass(frozen=True, slots=True)
class LSJEntry:
    """A Liddell-Scott-Jones entry."""

    headword: str
    raw_key: str
    lead: str                       # the orth + grammatical preamble before sense A
    senses: tuple[Sense, ...]
    short: str                      # a concise gloss (first sense, else the lead)

    def __str__(self) -> str:
        head = self.headword + (f" — {self.lead}" if self.lead else "")
        body = "\n".join(
            f"  {s.marker or '·'}. {s.text}" for s in self.senses
        )
        return f"{head}\n{body}" if body else head

    def _repr_html_(self) -> str:
        import html

        rows = "".join(
            f"<li><b>{html.escape(s.marker or '·')}</b> {html.escape(s.text)}</li>"
            for s in self.senses
        )
        lead = f" <span style='color:#666'>{html.escape(self.lead)}</span>" if self.lead else ""
        return (
            f"<div><b style='font-size:1.1em'>{html.escape(self.headword)}</b>{lead}"
            f"<ol>{rows}</ol></div>"
        )


def _parse_entry(entry: ET.Element) -> tuple[str, LSJEntry] | None:
    """Parse one ``<entryFree>`` into ``(lemma_key, LSJEntry)``, or ``None``."""
    raw_key = entry.get("key") or ""
    lemma = _norm(_btc(raw_key))
    if not lemma:
        return None
    orth = next((e for e in entry.iter() if _local(e.tag) == "orth"), None)
    headword = _btc(orth.text) if orth is not None and orth.text else _btc(raw_key)
    senses = tuple(
        Sense(marker=e.get("n") or "", level=int(e.get("level") or 0), text=text)
        for e in entry.iter()
        if _local(e.tag) == "sense" and (text := _ws(_flatten(e)))
    )
    lead = _ws(_flatten(entry))
    short = _short_gloss(senses, lead)
    return lemma, LSJEntry(headword=headword, raw_key=raw_key, lead=lead, senses=senses, short=short)


# --- index build + load ------------------------------------------------------


def _entry_to_dict(entry: LSJEntry) -> dict[str, Any]:
    return {
        "hw": entry.headword,
        "key": entry.raw_key,
        "lead": entry.lead,
        "short": entry.short,
        "senses": [{"m": s.marker, "l": s.level, "t": s.text} for s in entry.senses],
    }


def _dict_to_entry(d: dict[str, Any]) -> LSJEntry:
    senses = tuple(
        Sense(marker=s.get("m", ""), level=int(s.get("l", 0)), text=s.get("t", ""))
        for s in d.get("senses", [])
    )
    return LSJEntry(
        headword=d.get("hw", ""), raw_key=d.get("key", ""), lead=d.get("lead", ""),
        senses=senses, short=d.get("short", ""),
    )


def _lsj_dir(*, download: bool) -> Path:
    d = cache_dir() / _CACHE_SUBDIR
    if download:
        for name in _FILES:
            dest = d / name
            if not dest.exists():
                download_file(_BASE_URL + name, dest)
    return d


def build_index(*, source_dir: Path | str | None = None, force: bool = False) -> Path:
    """Build (and cache, gzipped) the lemma→entry index, returning its path.

    Downloads the Perseus LSJ files into the cache first, unless ``source_dir`` is
    given (used by tests to parse a local fixture without any network). A present
    index is reused unless ``force`` (or a ``source_dir``) is given.
    """
    out = cache_dir() / _INDEX_NAME
    if out.exists() and not force and source_dir is None:
        return out
    if source_dir is not None:
        files = sorted(Path(source_dir).glob("*.xml"))
    else:
        files = [_lsj_dir(download=True) / name for name in _FILES]

    index: dict[str, dict[str, Any]] = {}
    for fp in files:
        if not fp.exists():
            continue
        for _event, elem in ET.iterparse(str(fp), events=("end",)):
            if _local(elem.tag) == "entryFree":
                parsed = _parse_entry(elem)
                if parsed is not None and parsed[0] not in index:  # first wins
                    index[parsed[0]] = _entry_to_dict(parsed[1])
                elem.clear()
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    return out


class LSJLexicon:
    """A lemma→entry view of the Perseus LSJ, with lemmatize-on-miss lookup."""

    def __init__(self, data: dict[str, dict[str, Any]]) -> None:
        self._data = data
        self._stripped: dict[str, str] = {}
        for key in data:
            self._stripped.setdefault(_strip_accents(key), key)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "LSJLexicon":
        p = Path(path) if path is not None else cache_dir() / _INDEX_NAME
        if not p.exists():
            raise LexiconNotLoadedError(
                f"no LSJ index at {p}; call build_index() (or use_lsj()) first"
            )
        with gzip.open(p, "rt", encoding="utf-8") as f:
            data: dict[str, dict[str, Any]] = json.load(f)
        return cls(data)

    def __len__(self) -> int:
        return len(self._data)

    def _entry_dict(self, word: str) -> dict[str, Any] | None:
        hit = self._data.get(_norm(word))
        if hit is not None:
            return hit
        sk = self._stripped.get(_strip_accents(word))
        if sk is not None:
            return self._data[sk]
        # Miss: lemmatize (uses the treebank backend if active) and retry.
        from .lemmatize import lemmatize

        lemma = lemmatize(word)
        if _norm(lemma) != _norm(word):
            hit = self._data.get(_norm(lemma))
            if hit is not None:
                return hit
            sk = self._stripped.get(_strip_accents(lemma))
            if sk is not None:
                return self._data[sk]
        return None

    def lookup(self, word: str) -> LSJEntry | None:
        """The full LSJ entry for a word (form or lemma), or ``None`` if unknown."""
        d = self._entry_dict(word)
        return _dict_to_entry(d) if d is not None else None

    def gloss(self, word: str) -> str | None:
        """A concise gloss — ``headword: <first sense>`` — or ``None`` if unknown."""
        entry = self.lookup(word)
        return f"{entry.headword}: {entry.short}" if entry is not None else None


_ACTIVE: LSJLexicon | None = None


def use_lsj(*, build: bool = True, force: bool = False) -> LSJLexicon:
    """Activate the LSJ lexicon for this session.

    Downloads (~270 MB) + builds the index on first use (``build=True``); pass
    ``force=True`` to rebuild. Then `gloss` / `lookup` resolve words
    against it.
    """
    global _ACTIVE
    if build and (force or not (cache_dir() / _INDEX_NAME).exists()):
        build_index(force=force)
    _ACTIVE = LSJLexicon.load()
    return _ACTIVE


def disable_lsj() -> None:
    """Deactivate the LSJ lexicon."""
    global _ACTIVE
    _ACTIVE = None


def active() -> LSJLexicon | None:
    """The active lexicon, or ``None`` when LSJ glossing is off (the default)."""
    return _ACTIVE


def gloss(word: str) -> str | None:
    """Concise LSJ gloss for a word; requires `use_lsj`. ``None`` if unknown."""
    if _ACTIVE is None:
        raise LexiconNotLoadedError("LSJ is not loaded — call aegean.greek.use_lsj() first")
    return _ACTIVE.gloss(word)


def lookup(word: str) -> LSJEntry | None:
    """Full LSJ entry for a word; requires `use_lsj`. ``None`` if unknown."""
    if _ACTIVE is None:
        raise LexiconNotLoadedError("LSJ is not loaded — call aegean.greek.use_lsj() first")
    return _ACTIVE.lookup(word)
