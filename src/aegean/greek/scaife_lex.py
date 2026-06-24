"""Scaife-Viewer JSONL dictionaries — Middle Liddell and Cunliffe (opt-in).

Both are served one-entry-per-line as JSONL by ``scaife-viewer/atlas-data-prep``
(MIT), each line ``{"headword", "key" (Beta Code), "definition", ...}``. Middle
Liddell is Liddell & Scott's *An Intermediate Greek-English Lexicon* (the concise
abridged LSJ, classical); Cunliffe is *A Lexicon of the Homeric Dialect*.

``use_lexicon("middle-liddell")`` / ``use_lexicon("cunliffe")`` build a lemma→entry
index in the cache on first use (preferring a hosted prebuilt index, else fetching
the source), then ``gloss`` / ``entry`` resolve a word, lemmatizing on a miss. Never
bundled; the *data* is open (Perseus / public domain) and the wheel stays Apache-2.0.
"""

from __future__ import annotations

import ast
import gzip
import json
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..data import cache_dir, download_file, fetch_prebuilt
from .lexicons import LexEntry, Lexicon, LexiconInfo, register_lexicon

_REPO = "https://raw.githubusercontent.com/scaife-viewer/atlas-data-prep"
_COMMIT = "584ffe1269b65fe632df731d2883f49b1db4af8f"
_DICT_PATH = "test-data/dictionaries"
_CACHE_SUBDIR = "scaife-lex"


@dataclass(frozen=True, slots=True)
class _Source:
    info: LexiconInfo
    files: tuple[str, ...]   # paths under .../dictionaries/
    index_name: str          # cache filename for the built index
    prebuilt: str            # data-registry asset name for the hosted index


_SOURCES: dict[str, _Source] = {
    "middle-liddell": _Source(
        info=LexiconInfo(
            id="middle-liddell",
            name="Liddell & Scott, An Intermediate Greek-English Lexicon",
            scope="classical",
            license="public domain (1889); digitization CC BY-SA (Perseus), data MIT (Scaife)",
            source="scaife-viewer/atlas-data-prep",
            hosted=True,
        ),
        files=tuple(f"middle-liddell/entries_{i:02d}.jsonl" for i in range(2, 26)),
        index_name="middle-liddell-index.json.gz",
        prebuilt="middle-liddell-index",
    ),
    "cunliffe": _Source(
        info=LexiconInfo(
            id="cunliffe",
            name="Cunliffe, A Lexicon of the Homeric Dialect",
            scope="Homeric",
            license="public domain (1924); structured data MIT (Scaife)",
            source="scaife-viewer/atlas-data-prep",
            hosted=True,
        ),
        files=("cunliffe-1-lex/entries_01.jsonl",),
        index_name="cunliffe-index.json.gz",
        prebuilt="cunliffe-index",
    ),
}


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip().lower()


def _strip_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", _norm(text))
    return "".join(c for c in nfd if not unicodedata.combining(c))


def _concise(text: str, limit: int = 160) -> str:
    """A concise one-line gloss from a (possibly long) definition."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    head = cut[:space] if space > limit // 2 else cut
    return head.rstrip(" ,;:.") + "…"


def _definition(rec: dict[str, Any], headword: str) -> str:
    """The definition text of a Scaife entry. Cunliffe stores ``definition``
    directly; Middle Liddell nests it as ``data`` → ``content`` (a Python-repr
    string) whose first line repeats the Greek headword."""
    direct = rec.get("definition")
    if direct:
        return " ".join(str(direct).split())
    obj = rec.get("data")
    if isinstance(obj, str) and obj:
        try:
            obj = ast.literal_eval(obj)
        except (ValueError, SyntaxError):
            obj = None
    content = obj.get("content") if isinstance(obj, dict) else None
    if isinstance(content, str) and content:
        lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
        if lines and _norm(lines[0]) == _norm(headword):
            lines = lines[1:]
        return " ".join(lines)
    return ""


def _fetch_source(name: str) -> Path:
    dest = cache_dir() / _CACHE_SUBDIR / name
    if not dest.exists():
        download_file(f"{_REPO}/{_COMMIT}/{_DICT_PATH}/{name}", dest)
    return dest


def build_index(source_id: str, *, source_dir: Path | str | None = None, force: bool = False) -> Path:
    """Build (and cache, gzipped) the lemma→entry index for a Scaife dictionary.

    A present index is reused unless ``force`` (or a ``source_dir``) is given.
    Otherwise it prefers a hosted prebuilt index, then fetches the JSONL source and
    builds locally. ``source_dir`` parses local ``*.jsonl`` fixtures instead (tests;
    no network).
    """
    src = _SOURCES[source_id]
    out = cache_dir() / src.index_name
    if out.exists() and not force and source_dir is None:
        return out
    if source_dir is None:
        if fetch_prebuilt(src.prebuilt, out):
            return out
        files = [_fetch_source(name) for name in src.files]
    else:
        files = sorted(Path(source_dir).glob("*.jsonl"))

    index = index_from_files(files)
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    return out


def index_from_files(files: Iterable[Path]) -> dict[str, dict[str, str]]:
    """Parse Scaife JSONL files into a normalized lemma→entry index (first sense wins)."""
    index: dict[str, dict[str, str]] = {}
    for fp in files:
        if not Path(fp).exists():
            continue
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec: dict[str, Any] = json.loads(line)
                headword = (rec.get("headword") or "").strip()
                definition = _definition(rec, headword)
                key = _norm(headword)
                if key and definition and key not in index:  # first sense wins
                    index[key] = {"hw": headword, "def": definition}
    return index


class ScaifeLexicon:
    """A lemma→entry view of a Scaife JSONL dictionary, lemmatizing on a miss."""

    def __init__(self, info: LexiconInfo, data: dict[str, dict[str, str]]) -> None:
        self.info = info
        self._data = data
        self._stripped: dict[str, str] = {}
        for key in data:
            self._stripped.setdefault(_strip_accents(key), key)

    def __len__(self) -> int:
        return len(self._data)

    def _record(self, word: str) -> dict[str, str] | None:
        hit = self._data.get(_norm(word))
        if hit is not None:
            return hit
        sk = self._stripped.get(_strip_accents(word))
        if sk is not None:
            return self._data[sk]
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

    def lookup(self, word: str) -> LexEntry | None:
        rec = self._record(word)
        if rec is None:
            return None
        return LexEntry(
            headword=rec["hw"], gloss=_concise(rec["def"]), body=rec["def"], lexicon=self.info.id
        )

    def gloss(self, word: str) -> str | None:
        e = self.lookup(word)
        return None if e is None else f"{e.headword}: {e.gloss}"


def load_scaife(source_id: str, *, build: bool = True, force: bool = False) -> ScaifeLexicon:
    """Load a Scaife dictionary (building/fetching its index on first use)."""
    src = _SOURCES[source_id]
    out = cache_dir() / src.index_name
    if build and (force or not out.exists()):
        build_index(source_id, force=force)
    with gzip.open(out, "rt", encoding="utf-8") as f:
        data: dict[str, dict[str, str]] = json.load(f)
    return ScaifeLexicon(src.info, data)


def _make_loader(source_id: str) -> Callable[..., Lexicon]:
    return lambda **kw: load_scaife(source_id, **kw)


for _sid, _src in _SOURCES.items():
    register_lexicon(_src.info, _make_loader(_sid))
