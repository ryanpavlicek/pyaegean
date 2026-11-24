"""Strong's and Extended Strong's Greek lexicon lookup, search, and root trees.

Works immediately offline using the bundled Dodson Greek-English NT lexicon
(CC0) and upgrades seamlessly to the full 11,142-entry Extended Strong's Greek
lexicon (``strongs-greek`` release asset: STEPBible TBESG + OpenScriptures
Strong's, covering NT + LXX + Apocrypha + Apostolic Fathers, with etymological
root chains and Hebrew Strong's equivalents) once fetched or activated via
:func:`use_strongs`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

_STRONGS_ID_RE = re.compile(r"^[Gg]?(\d{1,5})([A-Za-z]?)$")


@dataclass(frozen=True, slots=True)
class StrongsEntry:
    """One Strong's or Extended Strong's Greek lexicon entry."""

    strongs: str
    lemma: str
    gloss: str
    definition: str
    translit: str = ""
    morph: str = ""
    strongs_def: str = ""
    kjv_def: str = ""
    derivation: str = ""
    roots: tuple[str, ...] = ()
    hebrew: tuple[str, ...] = ()
    variants: tuple[str, ...] = ()
    source: str = "dodson"

    def to_dict(self) -> dict[str, Any]:
        return {
            "strongs": self.strongs,
            "lemma": self.lemma,
            "translit": self.translit,
            "morph": self.morph,
            "gloss": self.gloss,
            "definition": self.definition,
            "strongs_def": self.strongs_def,
            "kjv_def": self.kjv_def,
            "derivation": self.derivation,
            "roots": list(self.roots),
            "hebrew": list(self.hebrew),
            "variants": list(self.variants),
            "source": self.source,
        }


def normalize_strongs_id(query: str | int) -> str | None:
    """Normalize ``3056``, ``'G3056'``, ``'g0026'``, or ``'G0001G'`` to canonical ``'G3056'`` / ``'G0001G'``.

    Returns ``None`` if ``query`` is not a Strong's number (e.g. a Greek lemma).
    """
    if isinstance(query, int):
        if query < 1:
            return None
        return f"G{query:04d}"
    s = query.strip()
    m = _STRONGS_ID_RE.match(s)
    if not m:
        return None
    num = int(m.group(1))
    if num < 1:
        return None
    suffix = m.group(2).upper()
    return f"G{num:04d}{suffix}"


def _fold(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)
    ).lower().replace("ς", "σ")


def _exact(s: str) -> str:
    return unicodedata.normalize("NFC", s).lower().replace("ς", "σ")


class _ExtendedStrongsIndex:
    """In-memory index over ``strongs-greek.json.gz``."""

    def __init__(self, entries: dict[str, StrongsEntry], meta: dict[str, Any]) -> None:
        self.entries = entries
        self.meta = meta
        self._by_exact: dict[str, StrongsEntry] = {}
        self._by_fold: dict[str, StrongsEntry] = {}
        for entry in entries.values():
            if not entry.lemma:
                continue
            # Prefer canonical numeric entries (G3056) over lettered disambiguations
            # when indexing by Greek lemma.
            if entry.strongs[-1].isdigit():
                self._by_exact.setdefault(_exact(entry.lemma), entry)
                self._by_fold.setdefault(_fold(entry.lemma), entry)
        for entry in entries.values():
            if not entry.lemma:
                continue
            self._by_exact.setdefault(_exact(entry.lemma), entry)
            self._by_fold.setdefault(_fold(entry.lemma), entry)

    def lookup(self, query: str | int) -> StrongsEntry | None:
        sid = normalize_strongs_id(query)
        if sid is not None:
            return self.entries.get(sid)
        word = str(query).strip()
        if not word:
            return None
        hit = self._by_exact.get(_exact(word))
        if hit is not None:
            return hit
        hit = self._by_fold.get(_fold(word))
        if hit is not None:
            return hit
        from ..greek.lemmatize import lemmatize

        lemma = lemmatize(word)
        if lemma and lemma != word:
            hit = self._by_exact.get(_exact(lemma)) or self._by_fold.get(_fold(lemma))
            if hit is not None:
                return hit
        return None

    def search(self, query: str, *, limit: int = 20) -> list[StrongsEntry]:
        q = query.strip()
        if not q:
            return []
        sid = normalize_strongs_id(q)
        if sid is not None:
            exact = self.entries.get(sid)
            return [exact] if exact is not None else []
        q_fold = _fold(q)
        q_low = q.lower()
        exact_hits: list[StrongsEntry] = []
        prefix_hits: list[StrongsEntry] = []
        gloss_hits: list[StrongsEntry] = []
        seen: set[str] = set()
        for sid_k, entry in self.entries.items():
            # Skip lettered variant duplicates when their base entry is present unless needed
            if not sid_k[-1].isdigit() and sid_k[:-1] in self.entries:
                continue
            lf = _fold(entry.lemma)
            tf = entry.translit.lower()
            gl = entry.gloss.lower()
            if lf == q_fold or tf == q_low or gl == q_low:
                exact_hits.append(entry)
                seen.add(sid_k)
            elif lf.startswith(q_fold) or tf.startswith(q_low):
                prefix_hits.append(entry)
                seen.add(sid_k)
            elif q_low in gl or q_low in entry.definition.lower() or q_low in entry.kjv_def.lower():
                gloss_hits.append(entry)
                seen.add(sid_k)
        all_hits = exact_hits + prefix_hits + gloss_hits
        return all_hits if limit <= 0 else all_hits[:limit]


_EXTENDED: _ExtendedStrongsIndex | None = None


def _load_extended_if_cached() -> _ExtendedStrongsIndex | None:
    global _EXTENDED
    if _EXTENDED is not None:
        return _EXTENDED
    from ..data import _REMOTE, cache_dir, load_gzip_json, present_paths

    paths = present_paths(_REMOTE["strongs-greek"], cache_dir())
    if not paths:
        return None
    path = paths[0]
    payload = load_gzip_json(path)
    entries = {
        k: StrongsEntry(
            strongs=rec.get("strongs", k),
            lemma=rec.get("lemma", ""),
            gloss=rec.get("gloss", ""),
            definition=rec.get("definition", rec.get("gloss", "")),
            translit=rec.get("translit", ""),
            morph=rec.get("morph", ""),
            strongs_def=rec.get("strongs_def", ""),
            kjv_def=rec.get("kjv_def", ""),
            derivation=rec.get("derivation", ""),
            roots=tuple(rec.get("roots", ())),
            hebrew=tuple(rec.get("hebrew", ())),
            variants=tuple(rec.get("variants", ())),
            source="strongs-greek",
        )
        for k, rec in payload["entries"].items()
    }
    _EXTENDED = _ExtendedStrongsIndex(entries, payload.get("_meta", {}))
    return _EXTENDED


def use_strongs(*, fetch: bool = True, force: bool = False) -> int:
    """Activate the full 11,142-entry Extended Strong's Greek Lexicon.

    Fetches ``strongs-greek`` (~1.5 MB gzip, CC BY-SA 4.0) to the local data
    store on first use when ``fetch=True``. Returns the number of loaded
    entries.
    """
    global _EXTENDED
    if force:
        _EXTENDED = None
    idx = _load_extended_if_cached()
    if idx is not None:
        return len(idx.entries)
    if not fetch:
        raise RuntimeError(
            "strongs-greek is not cached — run `aegean data fetch strongs-greek` "
            "or call use_strongs(fetch=True)"
        )
    from ..data import fetch as data_fetch

    data_fetch("strongs-greek")
    idx = _load_extended_if_cached()
    assert idx is not None
    return len(idx.entries)


def strongs_loaded() -> bool:
    """Return ``True`` if the Extended Strong's lexicon is loaded or cached locally."""
    return _load_extended_if_cached() is not None


def _dodson_entry(query: str | int) -> StrongsEntry | None:
    lex = _dodson_cached()
    sid = normalize_strongs_id(query)
    raw = lex.by_strongs(sid) if sid is not None else lex.lookup(str(query))
    if raw is None:
        return None
    norm_id = normalize_strongs_id(raw.strongs) or f"G{raw.strongs}"
    return StrongsEntry(
        strongs=norm_id,
        lemma=raw.lemma,
        gloss=raw.gloss,
        definition=raw.definition,
        source="dodson (offline)",
    )


_DODSON_CACHE: Any = None


def _dodson_cached() -> Any:
    global _DODSON_CACHE
    if _DODSON_CACHE is None:
        from ..greek.koine import DodsonLexicon

        _DODSON_CACHE = DodsonLexicon.load()
    return _DODSON_CACHE


def strongs_entry(query: str | int, *, allow_fetch: bool = False) -> StrongsEntry | None:
    """Look up a Strong's Greek entry by number (``'G3056'``, ``3056``) or Greek word (``'λόγος'``).

    Uses the full Extended Strong's lexicon (STEPBible TBESG + OpenScriptures,
    covering NT + LXX + Apocrypha + Apostolic Fathers with root derivations)
    when cached or when ``allow_fetch=True``; otherwise falls back cleanly to
    the bundled offline Dodson NT lexicon (CC0).
    """
    idx = _load_extended_if_cached()
    if idx is None and allow_fetch:
        use_strongs(fetch=True)
        idx = _load_extended_if_cached()
    if idx is not None:
        hit = idx.lookup(query)
        if hit is not None:
            return hit
    return _dodson_entry(query)


def strongs_roots(
    query: str | int,
    *,
    max_depth: int = 4,
    allow_fetch: bool = False,
) -> dict[str, Any]:
    """Build the recursive etymological root family tree for a Strong's entry.

    Requires the ``strongs-greek`` lexicon for derivation chains (falls back to
    a single-node tree when only offline Dodson is available).
    """
    entry = strongs_entry(query, allow_fetch=allow_fetch)
    if entry is None:
        raise ValueError(f"no Strong's Greek entry matched {query!r}")

    def _walk(item: StrongsEntry, depth: int, seen: frozenset[str]) -> dict[str, Any]:
        children: list[dict[str, Any]] = []
        if depth < max_depth:
            for root_id in item.roots:
                if root_id in seen:
                    continue
                if root_id.startswith("H"):
                    children.append({"strongs": root_id, "lemma": "", "gloss": "(Hebrew root)", "roots": []})
                    continue
                child = strongs_entry(root_id, allow_fetch=False)
                if child is not None:
                    children.append(_walk(child, depth + 1, seen | {root_id}))
                else:
                    children.append({"strongs": root_id, "lemma": "", "gloss": "", "roots": []})
        return {
            "strongs": item.strongs,
            "lemma": item.lemma,
            "gloss": item.gloss,
            "derivation": item.derivation,
            "hebrew": list(item.hebrew),
            "roots": children,
        }

    return _walk(entry, 0, frozenset({entry.strongs}))


def search_strongs(
    query: str,
    *,
    limit: int = 20,
    allow_fetch: bool = False,
) -> list[StrongsEntry]:
    """Search Strong's Greek entries by Greek lemma, transliteration, Strong's ID, or English gloss."""
    idx = _load_extended_if_cached()
    if idx is None and allow_fetch:
        use_strongs(fetch=True)
        idx = _load_extended_if_cached()
    if idx is not None:
        return idx.search(query, limit=limit)
    # Offline fallback over bundled Dodson
    q = query.strip()
    if not q:
        return []
    sid = normalize_strongs_id(q)
    if sid is not None:
        hit = _dodson_entry(sid)
        return [hit] if hit is not None else []
    lex = _dodson_cached()
    q_fold = _fold(q)
    q_low = q.lower()
    exact: list[StrongsEntry] = []
    partial: list[StrongsEntry] = []
    for raw in lex._by_strongs.values():
        lf = _fold(raw.lemma)
        gl = raw.gloss.lower()
        item = StrongsEntry(
            strongs=normalize_strongs_id(raw.strongs) or f"G{raw.strongs}",
            lemma=raw.lemma,
            gloss=raw.gloss,
            definition=raw.definition,
            source="dodson (offline)",
        )
        if lf == q_fold or gl == q_low:
            exact.append(item)
        elif q_fold in lf or q_low in gl or q_low in raw.definition.lower():
            partial.append(item)
    all_hits = exact + partial
    return all_hits if limit <= 0 else all_hits[:limit]
