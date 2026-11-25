"""Septuagint (LXX) corpus reader, concordance search, and patristic commentary excerpts.

Provides fast, verse-indexed access to all 55 Greek Septuagint books in Henry
Barclay Swete's *The Old Testament in Greek according to the Septuagint*
(1887–1894, Public Domain Greek base text; First1KGreek TEI digitization CC
BY-SA 4.0) via the SHA-256-pinned ``lxx-corpus`` release asset, plus an
always-offline sample (Genesis 1:1–5 and LXX Psalm 22:1–6 [MT Psalm 23]) so
offline calls, tests, MCP tools, and the browser demo work immediately with
zero network access.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from ._catalogs import (
    _LXX_BOOKS,
    _normalize_commentary_book,
    patristic_commentaries,
    resolve_lxx_book,
)

# Public-domain Swete (1887–1894) offline sample: Genesis 1:1–5 & LXX Psalm 22:1–6 (MT 23).
_OFFLINE_LXX_SAMPLE: dict[str, dict[str, str]] = {
    "Gen": {
        "1.1": "ΕΝ ΑΡΧΗ ἐποίησεν ὁ θεὸς τὸν οὐρανὸν καὶ τὴν γῆν.",
        "1.2": "ἡ δὲ γῆ ἦν ἀόρατος καὶ ἀκατασκεύαστος, καὶ σκότος ἐπάνω τῆς ἀβύσσου· καὶ πνεῦμα θεοῦ ἐπεφέρετο ἐπάνω τοῦ ὕδατος.",
        "1.3": "καὶ εἶπεν ὁ θεός Γενηθήτω φῶς· καὶ ἐγένετο φῶς.",
        "1.4": "καὶ ἴδεν ὁ θεὸς τὸ φῶς ὅτι καλόν· καὶ διεχώρισεν ὁ θεὸς ἀνὰ μέσον τοῦ φωτὸς καὶ ἀνὰ μέσον τοῦ σκότους.",
        "1.5": "καὶ ἐκάλεσεν ὁ θεὸς τὸ φῶς ἡμέραν, καὶ τὸ σκότος ἐκάλεσεν νύκτα. καὶ ἐγένετο ἑσπέρα καὶ ἐγένετο πρωί, ἡμέρα μία.",
    },
    "Ps": {
        "22.1": "Κύριος ποιμαίνει με, καὶ οὐδέν με ὑστερήσει.",
        "22.2": "εἰς τόπον χλόης, ἐκεῖ με κατεσκήνωσεν· ἐπὶ ὕδατος ἀναπαύσεως ἐξέθρεψέν με·",
        "22.3": "τὴν ψυχήν μου ἐπέστρεψεν. ὡδήγησέν με ἐπὶ τρίβους δικαιοσύνης ἕνεκεν τοῦ ὀνόματος αὐτοῦ.",
        "22.4": "ἐάν γὰρ καὶ πορευθῶ ἐν μέσῳ σκιᾶς θανάτου, οὐ φοβηθήσομαι κακά, ὅτι σὺ μετʼ ἐμοῦ εἶ· ἡ ῥάβδος σου καὶ ἡ βακτηρία σου, αὐταί με παρεκάλεσαν.",
        "22.5": "ἡτοίμασας ἐνώπιόν μου τράπεζαν ἐξ ἐναντίας τῶν θλιβόντων με· ἐλίπανας ἐν ἐλαίῳ τὴν κεφαλήν μου,",
        "22.6": "καὶ τὸ ἔλεός σου καταδιώξεταί με πάσας τὰς ἡμέρας τῆς ζωῆς καὶ τὸ κατοικεῖν με ἐν οἴκῳ Κυρίου εἰς μακρότητα ἡμερῶν.",
    },
}

_LXX_CACHE: dict[str, Any] | None = None
_PART_RE = re.compile(r"^(\d+)(.*)$")


def _fold(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped).lower().replace("ς", "σ")


def _part_key(part: str) -> tuple[int, int, str]:
    low = part.strip().lower()
    if low in ("prologue", "praef", "0"):
        return (0, 0, low)
    m = _PART_RE.match(low)
    if m:
        return (1, int(m.group(1)), m.group(2))
    return (2, 0, low)


def _verse_sort_key(cv: str) -> tuple[tuple[int, int, str], tuple[int, int, str]]:
    c, _, v = cv.partition(".")
    return _part_key(c), _part_key(v)


def _verse_line_int(v_str: str, fallback: int) -> int:
    m = _PART_RE.match(v_str.strip())
    return int(m.group(1)) if m else fallback


@dataclass(frozen=True, slots=True)
class LxxHit:
    """One Septuagint (LXX) concordance search match."""

    ref: str
    book: str
    title: str
    section: str
    verse_text: str
    matched_words: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "book": self.book,
            "title": self.title,
            "section": self.section,
            "verse_text": self.verse_text,
            "matched_words": list(self.matched_words),
        }


@dataclass(frozen=True, slots=True)
class CommentaryExcerpt:
    """One Greek patristic commentary section or search match (*Catenae* or Origen)."""

    work_id: str
    book: str
    author: str
    title: str
    kind: str
    section_id: str
    text: str
    matched_words: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "book": self.book,
            "author": self.author,
            "title": self.title,
            "kind": self.kind,
            "section_id": self.section_id,
            "text": self.text,
            "matched_words": list(self.matched_words),
        }


def lxx_loaded() -> bool:
    """Return ``True`` if the full 55-book ``lxx-corpus`` bundle is cached locally."""
    if _LXX_CACHE is not None:
        return True
    from ..data import _REMOTE, cache_dir, present_paths

    spec = _REMOTE.get("lxx-corpus")
    return bool(spec and present_paths(spec, cache_dir()))


def _load_lxx_bundle(*, allow_fetch: bool = True, force: bool = False) -> dict[str, Any] | None:
    global _LXX_CACHE
    if _LXX_CACHE is not None and not force:
        return _LXX_CACHE
    from ..data import _REMOTE, cache_dir, fetch, load_gzip_json, present_paths

    spec = _REMOTE["lxx-corpus"]
    paths = [] if force else present_paths(spec, cache_dir())
    if not paths:
        if not allow_fetch:
            return None
        path = fetch("lxx-corpus", force=force)
    else:
        path = paths[0]
    _LXX_CACHE = load_gzip_json(path)
    return _LXX_CACHE


def _select_lxx_verses(
    verses_map: dict[str, str],
    book: str,
    ref: str | None,
) -> list[tuple[str, str, str]]:
    """Return ordered ``(chapter_str, verse_str, text)`` tuples matching ``ref``."""
    ordered = sorted(verses_map.items(), key=lambda kv: _verse_sort_key(kv[0]))
    parsed = [(k.partition(".")[0], k.partition(".")[2], txt, k) for k, txt in ordered]
    if ref is None or not ref.strip():
        return [(c, v, txt) for c, v, txt, _ in parsed]

    s = ref.strip().replace(":", ".")
    if "." not in s:
        if "-" in s:
            a, _, b = s.partition("-")
            ka, kb = _part_key(a), _part_key(b)
            out = [(c, v, txt) for c, v, txt, _ in parsed if ka <= _part_key(c) <= kb]
        else:
            want_c = s.strip().lower()
            out = [(c, v, txt) for c, v, txt, _ in parsed if c.lower() == want_c]
    else:
        chap_part, _, vpart = s.partition(".")
        want_c = chap_part.strip().lower()
        if "-" in vpart:
            va, _, vb = vpart.partition("-")
            kva, kvb = _part_key(va), _part_key(vb)
            out = [
                (c, v, txt)
                for c, v, txt, _ in parsed
                if c.lower() == want_c and kva <= _part_key(v) <= kvb
            ]
        else:
            want_v = vpart.strip().lower()
            out = [
                (c, v, txt)
                for c, v, txt, _ in parsed
                if c.lower() == want_c and v.lower() == want_v
            ]

    if not out:
        raise ValueError(f"no Septuagint verses matched {book} {ref!r}")
    return out


def load_lxx(
    book: str | None = None,
    ref: str | None = None,
    *,
    offline: bool = False,
    force: bool = False,
) -> Any:
    """Load a Septuagint (LXX) book or passage as a :class:`~aegean.core.corpus.Corpus`.

    Uses the SHA-256-pinned ``lxx-corpus`` bundle (all 55 Swete Septuagint books,
    29,248 verses) when cached or ``offline=False``. When ``offline=True`` and the
    full bundle is not yet cached, serves from the bundled Swete 1887 offline
    sample (Genesis 1:1–5 and LXX Psalm 22:1–6 [MT Psalm 23]).
    """
    if ref is not None and book is None:
        raise ValueError("ref requires a book name, e.g. load_lxx('Gen', ref='1.1-5')")

    bundle = _load_lxx_bundle(allow_fetch=not offline, force=force)
    using_sample = bundle is None

    from ..core.corpus import Corpus
    from ..core.model import Document, DocumentMeta, Token, TokenKind
    from ..core.provenance import Provenance
    from ..data import DataNotAvailableError
    from ..greek.tokenize import tokenize

    book_specs = [resolve_lxx_book(book)] if book is not None else list(_LXX_BOOKS)

    if using_sample:
        if book is not None and book_specs[0].name not in _OFFLINE_LXX_SAMPLE:
            raise DataNotAvailableError(
                f"Septuagint book {book_specs[0].name!r} is not in the offline sample "
                "(Gen 1:1–5, Ps 22:1–6) — run `aegean data fetch lxx-corpus` or omit offline=True"
            )
        book_specs = [b for b in book_specs if b.name in _OFFLINE_LXX_SAMPLE]

    docs: list[Document] = []
    for bspec in book_specs:
        if using_sample:
            vmap = _OFFLINE_LXX_SAMPLE[bspec.name]
        else:
            assert bundle is not None
            vmap = bundle["books"][bspec.name]["verses"]
        try:
            selected = _select_lxx_verses(vmap, bspec.name, ref)
        except ValueError as exc:
            if using_sample:
                raise DataNotAvailableError(
                    f"{exc} in the offline LXX sample (Gen 1:1–5, Ps 22:1–6) — "
                    "run `aegean data fetch lxx-corpus` or omit offline=True"
                ) from exc
            raise

        by_chap: dict[str, list[tuple[str, str]]] = {}
        for chap_s, verse_s, txt in selected:
            by_chap.setdefault(chap_s, []).append((verse_s, txt))

        for chap_s, cverses in by_chap.items():
            tokens: list[Token] = []
            lines: list[list[int]] = []
            for idx, (verse_s, text) in enumerate(cverses, start=1):
                vno = _verse_line_int(verse_s, idx)
                line_indices: list[int] = []
                for tok in tokenize(text):
                    if not any(ch.isalpha() for ch in tok.text):
                        continue
                    pos = len(tokens)
                    tokens.append(
                        Token(
                            text=unicodedata.normalize("NFC", tok.text),
                            kind=TokenKind.WORD,
                            glyphs=unicodedata.normalize("NFC", tok.text),
                            line_no=vno,
                            position=pos,
                            annotations={
                                "ref": f"{bspec.name}.{chap_s}.{verse_s}",
                                "edition": "swete-lxx",
                            },
                        )
                    )
                    line_indices.append(pos)
                if line_indices:
                    lines.append(line_indices)
            if tokens:
                docs.append(
                    Document(
                        id=f"{bspec.name} {chap_s}",
                        script_id="greek",
                        tokens=tokens,
                        lines=lines,
                        meta=DocumentMeta(
                            period="Koine",
                            name=f"{bspec.title} {chap_s} (Swete LXX)",
                        ),
                    )
                )

    if using_sample:
        prov = Provenance(
            source="Swete Septuagint (1887–1894, offline sample: Gen 1:1–5, Ps 22:1–6)",
            license="Public Domain (Henry Barclay Swete, Cambridge University Press, 1887–1894)",
            url="https://github.com/OpenGreekAndLatin/First1KGreek",
            notes=("Bundled offline Swete Septuagint sample; fetch 'lxx-corpus' for all 55 books.",),
        )
    else:
        assert bundle is not None
        meta = bundle.get("_meta", {})
        prov = Provenance(
            source="Swete Septuagint (1887–1894) via OpenGreekAndLatin/First1KGreek",
            license=meta.get("license", "CC BY-SA 4.0"),
            url=meta.get("source_repo", "https://github.com/OpenGreekAndLatin/First1KGreek"),
            data_version=meta.get("source_commit"),
            notes=("Loaded from SHA-256-pinned lxx-corpus release asset.",),
        )
    return Corpus(docs, script_id="greek", provenance=prov)


def search_lxx(
    query: str,
    *,
    book: str | None = None,
    section: str | None = None,
    limit: int = 25,
    offline: bool = False,
) -> list[LxxHit]:
    """Search the Greek Septuagint (LXX) by Greek word, folded stem, or phrase.

    Searches all 55 Swete Septuagint books when ``lxx-corpus`` is cached or
    ``offline=False``, or searches the bundled Swete 1887 sample (Genesis 1:1–5
    and LXX Psalm 22:1–6) when ``offline=True`` and the full bundle is not cached.
    ``limit <= 0`` returns all matches.
    """
    q = query.strip()
    if not q:
        raise ValueError("search_lxx requires a non-empty Greek query")
    q_fold = _fold(q)
    if not q_fold:
        return []

    bundle = _load_lxx_bundle(allow_fetch=not offline)
    using_sample = bundle is None

    if book is not None:
        book_specs = [resolve_lxx_book(book)]
    else:
        book_specs = list(_LXX_BOOKS)
        if section is not None:
            want_sec = section.strip().lower()
            book_specs = [b for b in book_specs if b.section.lower() == want_sec]

    if using_sample:
        book_specs = [b for b in book_specs if b.name in _OFFLINE_LXX_SAMPLE]

    hits: list[LxxHit] = []
    from ..greek.tokenize import tokenize

    for bspec in book_specs:
        vmap = (
            _OFFLINE_LXX_SAMPLE[bspec.name]
            if using_sample
            else bundle["books"][bspec.name]["verses"]  # type: ignore[index]
        )
        for cv, text in sorted(vmap.items(), key=lambda kv: _verse_sort_key(kv[0])):
            if q_fold not in _fold(text):
                continue
            words = [t.text for t in tokenize(text) if any(ch.isalpha() for ch in t.text)]
            matched = tuple(
                dict.fromkeys(w for w in words if _fold(w) == q_fold or _fold(w).startswith(q_fold))
            )
            if not matched and " " not in q:
                continue
            pretty_ref = f"{bspec.name} {cv.replace('.', ':')}"
            hits.append(
                LxxHit(
                    ref=pretty_ref,
                    book=bspec.name,
                    title=bspec.title,
                    section=bspec.section,
                    verse_text=text,
                    matched_words=matched or (q,),
                )
            )
            if limit > 0 and len(hits) >= limit:
                return hits
    return hits


def commentary_excerpt(
    book: str,
    *,
    work_id: str | None = None,
    kind: str | None = None,
    ref: str | None = None,
    query: str | None = None,
    limit: int = 5,
    force: bool = False,
) -> list[CommentaryExcerpt]:
    """Read or search Greek patristic commentary sections (*Catenae* or Origen) for a book.

    Loads the selected commentary volume via :func:`aegean.greek.load_work` (cached
    after first fetch) and returns structured :class:`CommentaryExcerpt` records,
    optionally filtered by Greek ``query`` (accent/case-insensitive).
    """
    if work_id is not None:
        matches = [c for c in patristic_commentaries() if c["work_id"] == work_id]
        meta = matches[0] if matches else {
            "work_id": work_id,
            "book": book,
            "author": "Patristic",
            "title": work_id,
            "kind": kind or "catena",
        }
    else:
        canon = _normalize_commentary_book(book)
        candidates = patristic_commentaries(canon, kind=kind)
        if not candidates:
            raise ValueError(
                f"no Greek patristic commentary matched book={book!r}"
                + (f", kind={kind!r}" if kind else "")
            )
        meta = candidates[0]

    from ..scripts.greek.perseus import load_work

    corp = load_work(meta["work_id"], ref=ref, source="first1k", force=force)
    q_fold = _fold(query.strip()) if query and query.strip() else ""

    excerpts: list[CommentaryExcerpt] = []
    for doc in corp:
        words = [t.text for t in doc.tokens]
        full_text = " ".join(words)
        if not full_text.strip():
            continue
        matched: tuple[str, ...] = ()
        if q_fold:
            if q_fold not in _fold(full_text):
                continue
            hit_indices = [
                i
                for i, w in enumerate(words)
                if _fold(w) == q_fold or _fold(w).startswith(q_fold)
            ]
            if not hit_indices and query and " " not in query.strip():
                continue
            if hit_indices:
                first_idx = hit_indices[0]
                lo = max(0, first_idx - 35)
                hi = min(len(words), first_idx + 85)
                snippet = ("… " if lo > 0 else "") + " ".join(words[lo:hi]) + (" …" if hi < len(words) else "")
                matched = tuple(dict.fromkeys(words[i] for i in hit_indices[:8]))
            else:
                snippet = " ".join(words[:120]) + (" …" if len(words) > 120 else "")
                matched = (query.strip(),) if query else ()
        else:
            snippet = " ".join(words[:140]) + (" …" if len(words) > 140 else "")

        sec = doc.id.partition(":")[2] or doc.id
        excerpts.append(
            CommentaryExcerpt(
                work_id=meta["work_id"],
                book=meta["book"],
                author=meta["author"],
                title=meta["title"],
                kind=meta["kind"],
                section_id=sec,
                text=snippet,
                matched_words=matched,
            )
        )
        if limit > 0 and len(excerpts) >= limit:
            break
    return excerpts
