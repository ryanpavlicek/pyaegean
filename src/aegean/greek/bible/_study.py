"""Biblical Greek word study, concordance search, Septuagint, and patristic commentary loaders."""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ._catalogs import (
    _normalize_commentary_book,
    patristic_commentaries,
    resolve_lxx_book,
)
from ._editions import load_nt
from ._lxx import LxxHit, lxx_loaded, search_lxx
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
    """One verse-level concordance match in the Greek New Testament or Septuagint."""

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
    """Complete Koine / Biblical Greek word study report (NT + optional LXX)."""

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
    lxx_total: int = 0
    lxx_scope: str = ""
    lxx_by_book: dict[str, int] = field(default_factory=dict)
    lxx_occurrences: tuple[LxxHit, ...] = ()

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
            "lxx_total": self.lxx_total,
            "lxx_scope": self.lxx_scope,
            "lxx_by_book": dict(self.lxx_by_book),
            "lxx_occurrences": [h.to_dict() for h in self.lxx_occurrences],
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


def _is_lxx_only_book(book: str | None) -> bool:
    if not book:
        return False
    from ...scripts.greek.nt import _resolve_book

    try:
        _resolve_book(book)
        return False
    except ValueError:
        pass
    try:
        resolve_lxx_book(book)
        return True
    except ValueError:
        return False


def _search_lxx_as_concordance(
    query: str,
    *,
    mode: str,
    book: str | None,
    limit: int,
    offline: bool,
) -> list[ConcordanceHit]:
    lxx_q = query
    entry: StrongsEntry | None = None
    if mode == "strongs":
        entry = strongs_entry(query, allow_fetch=False)
        if entry is None:
            return []
        lxx_q = entry.lemma
    elif mode in ("morph", "gloss"):
        return []
    lxx_hits = search_lxx(lxx_q, book=book, limit=limit, offline=offline)
    out: list[ConcordanceHit] = []
    for lh in lxx_hits:
        surf = lh.matched_words[0] if lh.matched_words else lxx_q
        out.append(
            ConcordanceHit(
                ref=lh.ref,
                book=lh.book,
                surface=surf,
                lemma=entry.lemma if entry is not None else (lxx_q if mode == "lemma" else ""),
                morph="LXX",
                strongs=entry.strongs if entry is not None else "",
                gloss=entry.gloss if entry is not None else "",
                verse_text=lh.verse_text,
            )
        )
    return out


def search_bible(
    query: str,
    *,
    by: str = "lemma",
    book: str | None = None,
    edition: str = "nestle1904",
    corpus: str = "auto",
    limit: int = 50,
    offline: bool = False,
) -> list[ConcordanceHit]:
    """Search the Greek New Testament and/or Septuagint (LXX) by lemma, surface text,
    Strong's number, morphology, or gloss.

    Works immediately offline on the bundled Nestle 1904 sample (John 1 & Philemon 1)
    and Swete LXX sample (Gen 1 & Ps 22) and automatically spans all 27 NT books and
    56 LXX books once cached.

    Parameters
    ----------
    query:
        Search value (e.g. ``'λόγος'``, ``'G3056'``, ``'V-AAI'``, ``'light'``).
    by:
        One of ``'lemma'`` (default), ``'text'``, ``'strongs'``, ``'morph'``,
        or ``'gloss'``.
    book:
        Optional NT or LXX book filter (e.g. ``'John'``, ``'Rom'``, ``'Gen'``, ``'Eccl'``).
        When ``corpus='auto'``, passing an LXX book automatically searches the Septuagint.
    edition:
        NT edition (default ``'nestle1904'``; non-annotated editions support
        ``by='text'``).
    corpus:
        ``'auto'`` (default: NT unless ``book`` is an LXX book), ``'nt'``, ``'lxx'``,
        or ``'both'`` (searches both NT and LXX).
    limit:
        Maximum hits to return (default ``50``; ``0`` returns all matches).
    """
    mode = by.strip().lower()
    if mode not in ("lemma", "text", "strongs", "morph", "gloss"):
        raise ValueError(
            f"unknown search mode by={by!r}; expected 'lemma', 'text', 'strongs', 'morph', or 'gloss'"
        )
    scope_mode = corpus.strip().lower()
    if scope_mode not in ("auto", "nt", "lxx", "both"):
        raise ValueError(
            f"unknown corpus={corpus!r}; expected 'auto', 'nt', 'lxx', or 'both'"
        )
    q = query.strip()
    if not q:
        return []

    if scope_mode == "auto":
        scope_mode = "lxx" if _is_lxx_only_book(book) else "nt"

    if scope_mode == "lxx":
        return _search_lxx_as_concordance(q, mode=mode, book=book, limit=limit, offline=offline)

    nt_book = None if (scope_mode == "both" and _is_lxx_only_book(book)) else book
    hits: list[ConcordanceHit] = []
    if not (scope_mode == "both" and _is_lxx_only_book(book)):
        corp, _ = _load_nt_for_search(nt_book, edition=edition, offline=offline)
        q_fold = _fold(q)
        q_low = q.lower()
        want_strongs_digits = ""
        if mode == "strongs":
            norm = normalize_strongs_id(q)
            if norm is not None:
                want_strongs_digits = norm[1:].rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ").lstrip("0")
            else:
                want_strongs_digits = q.lstrip("Gg").lstrip("0")

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
                        break
            if limit > 0 and len(hits) >= limit:
                break

    if scope_mode == "both":
        lxx_book = book if _is_lxx_only_book(book) else None
        lxx_hits = _search_lxx_as_concordance(
            q, mode=mode, book=lxx_book, limit=limit, offline=offline
        )
        if limit <= 0 or len(hits) + len(lxx_hits) <= limit:
            hits.extend(lxx_hits)
        else:
            # Split the limit fairly so common NT words do not starve LXX results.
            lxx_share = min(len(lxx_hits), max(1, limit // 2))
            nt_share = min(len(hits), limit - lxx_share)
            lxx_share = min(len(lxx_hits), limit - nt_share)
            hits = hits[:nt_share] + lxx_hits[:lxx_share]
    return hits


def word_study(
    query: str | int,
    *,
    book: str | None = None,
    include_lxx: bool | None = None,
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
      breakdown, inflected surface-form breakdown, and verse concordance;
    - Septuagint (LXX) occurrence counts, book distribution, and sample verses
      (automatically included when ``book`` is unset or an LXX book, or when
      ``include_lxx=True``).
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

    book_is_lxx = _is_lxx_only_book(book)
    want_lxx = (book is None or book_is_lxx) if include_lxx is None else bool(include_lxx)

    book_counts: Counter[str] = Counter()
    morph_counts: Counter[str] = Counter()
    surface_counts: Counter[str] = Counter()
    hits: list[ConcordanceHit] = []
    total = 0
    scope = "Septuagint only" if book_is_lxx else ""

    if not book_is_lxx:
        corp, scope = _load_nt_for_search(book, edition="nestle1904", offline=offline)
        want_strongs = sid[1:].rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ").lstrip("0") if sid else ""
        want_lemma = _fold(lemma) if lemma else _fold(q_str)

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

    lxx_total = 0
    lxx_scope = ""
    lxx_book_counts: Counter[str] = Counter()
    lxx_occ: tuple[LxxHit, ...] = ()
    lxx_term = lemma or ("" if sid else q_str)
    if want_lxx and lxx_term:
        try:
            lxx_hits = search_lxx(
                lxx_term,
                book=book if book_is_lxx else None,
                limit=0,
                offline=offline,
            )
            lxx_total = len(lxx_hits)
            for lh in lxx_hits:
                lxx_book_counts[lh.book] += 1
            lxx_occ = tuple(lxx_hits[:limit] if limit > 0 else lxx_hits)
            if lxx_loaded():
                lxx_scope = f"Swete LXX ({book})" if book_is_lxx else "Swete LXX (56 books)"
            else:
                lxx_scope = "LXX offline sample (Gen 1, Ps 22)"
        except Exception:
            lxx_total = 0

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
        lxx_total=lxx_total,
        lxx_scope=lxx_scope,
        lxx_by_book=dict(lxx_book_counts.most_common()),
        lxx_occurrences=lxx_occ,
    )


def load_commentary(
    book: str,
    *,
    work_id: str | None = None,
    kind: str | None = None,
    ref: str | None = None,
    force: bool = False,
) -> Any:
    """Load a Greek patristic biblical commentary (Catenae, Origen, John Chrysostom,
    First1KGreek Fathers, or *Patrologia Graeca*) by book name or explicit ``work_id``.

    For example, ``load_commentary('John')`` loads the *Catena Integra* in
    Joannem (``tlg4102.tlg005``), ``load_commentary('John', kind='chrysostom')``
    loads John Chrysostom's *Homilies on John* (``ogc002058``),
    ``load_commentary('John', kind='origen')`` loads Origen's *Commentarii in
    Evangelium Joannis* (``tlg2042.tlg005``), and ``load_commentary('John',
    kind='patrologia')`` loads Cyril of Alexandria's *Commentary on John* (``PG073``).
    Pass ``work_id`` explicitly to pick any volume from :func:`patristic_commentaries`.
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
    if wid.upper().startswith("PG"):
        from ...scripts.greek.patrologia import load_patrologia

        return load_patrologia(wid)
    if wid.lower().startswith("ogc"):
        from ...scripts.greek._collections import load_collection_work

        return load_collection_work(wid, force=force)
    from ...scripts.greek.perseus import load_work

    return load_work(wid, ref=ref, source="first1k", force=force)
