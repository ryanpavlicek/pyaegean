"""Biblical Greek word study, concordance search, Septuagint, and patristic commentary loaders."""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any

from ._catalogs import (
    _normalize_commentary_book,
    patristic_commentaries,
)
from ._editions import load_nt
from ._strongs import (
    StrongsEntry,
    normalize_strongs_id,
    strongs_entry,
    strongs_roots,
)


def _fold(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)
    ).lower().replace("ς", "σ")


@dataclass(frozen=True, slots=True)
class ConcordanceHit:
    """One verse-level concordance match in the Greek New Testament."""

    ref: str
    book: str
    surface: str
    lemma: str
    morph: str
    strongs: str
    gloss: str
    verse_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "book": self.book,
            "surface": self.surface,
            "lemma": self.lemma,
            "morph": self.morph,
            "strongs": self.strongs,
            "gloss": self.gloss,
            "verse_text": self.verse_text,
        }


@dataclass(frozen=True, slots=True)
class WordStudy:
    """Complete Koine / Biblical Greek word study report."""

    query: str
    lemma: str
    strongs: str
    entry: StrongsEntry | None
    roots: dict[str, Any] | None
    lexicon_entries: dict[str, str]
    scope: str
    total_occurrences: int
    by_book: dict[str, int]
    by_morph: dict[str, int]
    by_surface: dict[str, int]
    occurrences: tuple[ConcordanceHit, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "lemma": self.lemma,
            "strongs": self.strongs,
            "entry": self.entry.to_dict() if self.entry is not None else None,
            "roots": self.roots,
            "lexicon_entries": dict(self.lexicon_entries),
            "scope": self.scope,
            "total_occurrences": self.total_occurrences,
            "by_book": dict(self.by_book),
            "by_morph": dict(self.by_morph),
            "by_surface": dict(self.by_surface),
            "occurrences": [h.to_dict() for h in self.occurrences],
        }


def _load_nt_for_search(
    book: str | None = None,
    *,
    edition: str = "nestle1904",
    offline: bool = False,
) -> tuple[Any, str]:
    """Load NT corpus for search/word study, falling back gracefully to bundled offline sample."""
    if edition == "nestle1904":
        corp = load_nt(book, edition="nestle1904", offline=offline)
        cit = getattr(getattr(corp, "provenance", None), "citation", "") or ""
        is_sample = "Bundled sample" in cit
        scope = (
            "Bundled sample (John 1, Philemon 1)"
            if is_sample
            else (f"Nestle 1904 ({book})" if book else "Nestle 1904 (27 books)")
        )
        return corp, scope
    corp = load_nt(book, edition=edition, offline=offline)
    scope = f"{edition} ({book})" if book else f"{edition} (27 books)"
    return corp, scope


def _verse_text_for_line(doc: Any, line_no: int | None) -> str:
    if line_no is None:
        return " ".join(t.text for t in doc.tokens)
    return " ".join(t.text for t in doc.tokens if t.line_no == line_no)


def search_bible(
    query: str,
    *,
    by: str = "lemma",
    book: str | None = None,
    edition: str = "nestle1904",
    limit: int = 50,
    offline: bool = False,
) -> list[ConcordanceHit]:
    """Search the Greek New Testament by lemma, surface text, Strong's number, morphology, or gloss.

    Works immediately offline on the bundled Nestle 1904 sample (John 1 &
    Philemon 1) and automatically spans all 27 books when ``nt-corpus`` is
    cached.

    Parameters
    ----------
    query:
        Search value (e.g. ``'λόγος'``, ``'G3056'``, ``'V-AAI'``, ``'light'``).
    by:
        One of ``'lemma'`` (default), ``'text'``, ``'strongs'``, ``'morph'``,
        or ``'gloss'``.
    book:
        Optional NT book filter (e.g. ``'John'``, ``'Rom'``).
    edition:
        NT edition (default ``'nestle1904'``; non-annotated editions support
        ``by='text'``).
    limit:
        Maximum hits to return (default ``50``).
    """
    mode = by.strip().lower()
    if mode not in ("lemma", "text", "strongs", "morph", "gloss"):
        raise ValueError(
            f"unknown search mode by={by!r}; expected 'lemma', 'text', 'strongs', 'morph', or 'gloss'"
        )
    q = query.strip()
    if not q:
        return []
    corp, _ = _load_nt_for_search(book, edition=edition, offline=offline)

    q_fold = _fold(q)
    q_low = q.lower()
    want_strongs_digits = ""
    if mode == "strongs":
        norm = normalize_strongs_id(q)
        if norm is not None:
            want_strongs_digits = norm[1:].rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ").lstrip("0")
        else:
            want_strongs_digits = q.lstrip("Gg").lstrip("0")

    hits: list[ConcordanceHit] = []
    for doc in corp:
        verse_cache: dict[int | None, str] = {}
        for tok in doc.tokens:
            ann = tok.annotations
            matched = False
            if mode == "lemma":
                lem = ann.get("lemma", "")
                matched = bool(lem) and _fold(lem) == q_fold
            elif mode == "text":
                matched = q_fold in _fold(tok.text) or q_fold in _fold(ann.get("normalized", ""))
            elif mode == "strongs":
                ts = str(ann.get("strongs", "")).lstrip("Gg").lstrip("0")
                matched = bool(ts) and ts == want_strongs_digits
            elif mode == "morph":
                m = str(ann.get("morph", "")).lower()
                matched = bool(m) and (m == q_low or m.startswith(q_low) or q_low in m)
            elif mode == "gloss":
                g = str(ann.get("gloss", "")).lower()
                matched = bool(g) and q_low in g

            if matched:
                if tok.line_no not in verse_cache:
                    verse_cache[tok.line_no] = _verse_text_for_line(doc, tok.line_no)
                vref = str(ann.get("ref", doc.id))
                bname, _, rest = vref.partition(".")
                pretty_ref = f"{bname} {rest.replace('.', ':')}" if rest else vref
                tok_strongs = str(ann.get("strongs", ""))
                hits.append(
                    ConcordanceHit(
                        ref=pretty_ref,
                        book=bname,
                        surface=tok.text,
                        lemma=str(ann.get("lemma", "")),
                        morph=str(ann.get("morph", "")),
                        strongs=normalize_strongs_id(tok_strongs) or tok_strongs,
                        gloss=str(ann.get("gloss", "")),
                        verse_text=verse_cache[tok.line_no],
                    )
                )
                if limit > 0 and len(hits) >= limit:
                    return hits
    return hits


def word_study(
    query: str | int,
    *,
    book: str | None = None,
    limit: int = 20,
    offline: bool = False,
) -> WordStudy:
    """Run a unified Biblical & Koine Greek word study for a Strong's ID or Greek word.

    Combines:
    - Strong's / Extended Strong's entry (gloss, definition, Hebrew equivalents,
      KJV usage) and recursive etymological root tree;
    - Entries from any active classical/Koine registry lexica (e.g. Abbott-Smith,
      LSJ, Middle Liddell);
    - Greek NT occurrence counts, book distribution, Robinson morphology
      breakdown, inflected surface-form breakdown, and verse concordance.

    Works immediately offline (using bundled Dodson + bundled John 1 / Philemon 1)
    and automatically expands to the full 27-book NT and 11,142-entry Extended
    Strong's lexicon once cached.
    """
    q_str = str(query).strip()
    entry = strongs_entry(query, allow_fetch=False)
    sid = entry.strongs if entry is not None else (normalize_strongs_id(query) or "")
    lemma = entry.lemma if entry is not None else ("" if sid else q_str)

    roots: dict[str, Any] | None = None
    if entry is not None:
        try:
            roots = strongs_roots(entry.strongs, allow_fetch=False)
        except ValueError:
            roots = None

    # Check active classical/Koine registry lexica (LSJ, Abbott-Smith, etc.) if loaded
    lex_entries: dict[str, str] = {}
    if lemma:
        try:
            from ..lexicons import active_lexica, entry as registry_entry

            for lex_name in active_lexica():
                found = registry_entry(lemma, dictionary=lex_name)
                if found:
                    lex_entries[lex_name] = found.gloss or found.body[:200]
        except Exception:
            pass

    corp, scope = _load_nt_for_search(book, edition="nestle1904", offline=offline)
    want_strongs = sid[1:].rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ").lstrip("0") if sid else ""
    want_lemma = _fold(lemma) if lemma else _fold(q_str)

    book_counts: Counter[str] = Counter()
    morph_counts: Counter[str] = Counter()
    surface_counts: Counter[str] = Counter()
    hits: list[ConcordanceHit] = []
    total = 0

    for doc in corp:
        verse_cache: dict[int | None, str] = {}
        for tok in doc.tokens:
            ann = tok.annotations
            ts = str(ann.get("strongs", "")).lstrip("Gg").lstrip("0")
            tl = _fold(str(ann.get("lemma", "")))
            matched = (want_strongs and ts == want_strongs) or (want_lemma and tl == want_lemma)
            if not matched:
                continue
            total += 1
            vref = str(ann.get("ref", doc.id))
            bname, _, rest = vref.partition(".")
            book_counts[bname] += 1
            m = str(ann.get("morph", ""))
            if m:
                morph_counts[m] += 1
            surface_counts[tok.text] += 1
            if limit <= 0 or len(hits) < limit:
                if tok.line_no not in verse_cache:
                    verse_cache[tok.line_no] = _verse_text_for_line(doc, tok.line_no)
                pretty_ref = f"{bname} {rest.replace('.', ':')}" if rest else vref
                hits.append(
                    ConcordanceHit(
                        ref=pretty_ref,
                        book=bname,
                        surface=tok.text,
                        lemma=str(ann.get("lemma", "")),
                        morph=m,
                        strongs=normalize_strongs_id(ts) or ts,
                        gloss=str(ann.get("gloss", "")),
                        verse_text=verse_cache[tok.line_no],
                    )
                )

    return WordStudy(
        query=q_str,
        lemma=lemma or q_str,
        strongs=sid,
        entry=entry,
        roots=roots,
        lexicon_entries=lex_entries,
        scope=scope,
        total_occurrences=total,
        by_book=dict(book_counts.most_common()),
        by_morph=dict(morph_counts.most_common()),
        by_surface=dict(surface_counts.most_common()),
        occurrences=tuple(hits),
    )


def load_commentary(
    book: str,
    *,
    work_id: str | None = None,
    kind: str | None = None,
    ref: str | None = None,
    force: bool = False,
) -> Any:
    """Load a Greek patristic biblical commentary (NT *Catenae* or Origen) by book name.

    For example, ``load_commentary('John')`` loads the *Catena Integra* in
    Joannem (``tlg4102.tlg005``), while ``load_commentary('John', kind='origen')``
    loads Origen's *Commentarii in Evangelium Joannis* (``tlg2042.tlg005``).
    Pass ``work_id`` explicitly to pick a specific volume from
    :func:`patristic_commentaries`.
    """
    if work_id is not None:
        wid = work_id
    else:
        canon = _normalize_commentary_book(book)
        candidates = patristic_commentaries(canon, kind=kind)
        if not candidates:
            raise ValueError(
                f"no Greek patristic commentary matched book={book!r}"
                + (f", kind={kind!r}" if kind else "")
            )
        wid = candidates[0]["work_id"]
    from ...scripts.greek.perseus import load_work

    return load_work(wid, ref=ref, source="first1k", force=force)
