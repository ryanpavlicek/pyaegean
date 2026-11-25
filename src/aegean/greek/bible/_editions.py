"""Multi-edition Greek New Testament loading and word-level variant comparison.

Supports nine Greek New Testament editions:

- ``nestle1904`` — Nestle 1904 with gold lemma, Robinson morph, Strong's, and
  UD UPOS (bundled offline sample: John 1 & Philemon 1; full 27 books in
  ``nt-corpus``, CC0).
- ``sblgnt`` — SBL Greek New Testament (Holmes 2010; CC BY 4.0 / MorphGNT CC BY-SA 3.0).
- ``srgnt`` — Statistical Restoration GNT (CNTR; CC BY 4.0).
- ``bhp`` — Bunning Heuristic Prototype GNT (CNTR; CC BY 4.0).
- ``tisch`` — Tischendorf 8th *Editio Octava Critica Maior* (1869–1872; Public Domain).
- ``wh`` — Westcott–Hort (1881; Public Domain, unaccented Unicode).
- ``byz`` — Robinson–Pierpont Byzantine Majority Textform (Public Domain).
- ``antoniades`` — Antoniades 1904 Patriarchal Edition (Public Domain, unaccented Unicode).
- ``tr`` — Textus Receptus (KJTR; CC BY 4.0).
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ...scripts.greek.nt import _parse_ref, _resolve_book
from ._catalogs import NT_EDITIONS, resolve_edition

_EDITIONS_CACHE: dict[str, Any] | None = None
_NON_WORD_RE = re.compile(r"[^\w]+", re.UNICODE)
_APPARATUS_MARKS_RE = re.compile(r"[⸂⸃⸀⸁⸄⸅¶˚\[\]]")


@dataclass(frozen=True, slots=True)
class WordVariant:
    """One word-level textual difference between a baseline edition and another edition."""

    edition: str
    kind: str  # "replace" | "insert" | "delete"
    base_words: tuple[str, ...]
    edition_words: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "edition": self.edition,
            "kind": self.kind,
            "base_words": list(self.base_words),
            "edition_words": list(self.edition_words),
        }


@dataclass(frozen=True, slots=True)
class VerseComparison:
    """Side-by-side comparison of one Greek NT verse across multiple editions."""

    ref: str
    texts: dict[str, str]
    identical: bool
    variants: tuple[WordVariant, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "texts": dict(self.texts),
            "identical": self.identical,
            "variants": [v.to_dict() for v in self.variants],
        }


@dataclass(frozen=True, slots=True)
class EditionComparison:
    """Multi-edition comparison for a passage (one or more verses)."""

    book: str
    ref: str
    editions: tuple[str, ...]
    verses: tuple[VerseComparison, ...]

    @property
    def variant_verse_count(self) -> int:
        return sum(1 for v in self.verses if not v.identical)

    def to_dict(self) -> dict[str, Any]:
        return {
            "book": self.book,
            "ref": self.ref,
            "editions": list(self.editions),
            "variant_verse_count": self.variant_verse_count,
            "verses": [v.to_dict() for v in self.verses],
        }


def nt_editions() -> list[dict[str, Any]]:
    """List the five supported Greek New Testament editions and their licenses."""
    return [dict(e) for e in NT_EDITIONS]


def _load_editions_bundle(
    *,
    allow_fetch: bool = True,
    required_edition: str | None = None,
) -> dict[str, Any]:
    global _EDITIONS_CACHE
    from ...data import _REMOTE, DataNotAvailableError, cache_dir, fetch, load_gzip_json, present_paths

    if _EDITIONS_CACHE is not None and (
        required_edition is None or required_edition in _EDITIONS_CACHE.get("editions", {})
    ):
        return _EDITIONS_CACHE

    paths = present_paths(_REMOTE["nt-editions"], cache_dir())
    if not paths:
        if not allow_fetch:
            raise DataNotAvailableError(
                "nt-editions is not cached — run `aegean data fetch nt-editions` "
                "or pass allow_fetch=True"
            )
        path = fetch("nt-editions")
        _EDITIONS_CACHE = load_gzip_json(path)
        return _EDITIONS_CACHE

    bundle = load_gzip_json(paths[0])
    if required_edition is not None and required_edition not in bundle.get("editions", {}):
        if not allow_fetch:
            raise DataNotAvailableError(
                f"cached nt-editions bundle does not include {required_edition!r} (pre-v2 cache) — "
                "run `aegean data fetch nt-editions --force` to upgrade to v2 (8 editions)"
            )
        path = fetch("nt-editions", force=True)
        bundle = load_gzip_json(path)
    _EDITIONS_CACHE = bundle
    return _EDITIONS_CACHE


def _verse_key_tuple(cv: str) -> tuple[int, int]:
    c, _, v = cv.partition(".")
    return int(c), int(v)


def _select_verses(
    book_verses: dict[str, str],
    book: str,
    ref: str | None,
) -> list[tuple[int, int, str]]:
    items = sorted(
        ((_verse_key_tuple(cv)[0], _verse_key_tuple(cv)[1], txt) for cv, txt in book_verses.items()),
        key=lambda x: (x[0], x[1]),
    )
    if ref is None:
        return items
    sc, sv, ec, ev = _parse_ref(ref)
    kept: list[tuple[int, int, str]] = []
    for c, v, txt in items:
        if c < sc or c > ec:
            continue
        if c == sc and sv is not None and v < sv:
            continue
        if c == ec and ev is not None and v > ev:
            continue
        kept.append((c, v, txt))
    if not kept:
        raise ValueError(f"no verses matched {book} ref {ref!r}")
    return kept


def load_nt(
    book: str | None = None,
    ref: str | None = None,
    *,
    edition: str = "nestle1904",
    offline: bool = False,
    force: bool = False,
) -> Any:
    """Load the Greek New Testament in any of the 5 supported editions.

    ``edition`` accepts ``'nestle1904'`` (default, full gold lemma/morph/Strong's,
    offline sample John 1 & Philemon 1), ``'sblgnt'``, ``'srgnt'``, ``'byz'``,
    or ``'tr'``. Returns a standard :class:`aegean.Corpus` with one
    :class:`aegean.Document` per chapter and verse-aligned lines.
    """
    ed = resolve_edition(edition)
    if ed == "nestle1904":
        from ...data import _REMOTE, cache_dir, is_downloaded
        from ...scripts.greek.nt import (
            _bundled_payload,
            _provenance,
            _select,
            _selection_scope,
        )
        from ...scripts.greek.nt import (
            load_nt as _load_nestle,
        )

        if not offline or is_downloaded(_REMOTE["nt-corpus"], cache_dir()):
            return _load_nestle(book, ref=ref, force=force)
        from ...core.corpus import Corpus
        from ...scripts.greek.inventory import greek_inventory

        payload = _bundled_payload()
        docs = _select(payload["documents"], book, ref)
        scope = _selection_scope(docs, book, ref, offline=True)
        prov = _provenance(payload.get("_meta", {}), offline=True, scope=scope)
        return Corpus(docs, sign_inventory=greek_inventory(), provenance=prov, script_id="greek")

    if ref is not None and book is None:
        raise ValueError("ref requires a book, e.g. load_nt('John', ref='1.1-18', edition='sblgnt')")

    bundle = _load_editions_bundle(allow_fetch=not offline, required_edition=ed)
    ed_data = bundle["editions"][ed]
    info = ed_data.get("_info", {})
    books_map: dict[str, dict[str, str]] = ed_data["books"]

    if book is not None:
        osis = _resolve_book(book)
        selected_books = [(osis, books_map[osis])]
    else:
        selected_books = list(books_map.items())

    from ...core.corpus import Corpus
    from ...core.model import Document, DocumentMeta, Token, TokenKind
    from ...core.provenance import Provenance
    from ..tokenize import tokenize

    ed_docs: list[Document] = []
    for osis, vmap in selected_books:
        verses = _select_verses(vmap, osis, ref)
        by_chapter: dict[int, list[tuple[int, str]]] = {}
        for c, v, txt in verses:
            by_chapter.setdefault(c, []).append((v, txt))
        for chap, cverses in sorted(by_chapter.items()):
            tokens: list[Token] = []
            lines: list[list[int]] = []
            for vno, text in cverses:
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
                                "ref": f"{osis}.{chap}.{vno}",
                                "edition": ed,
                            },
                        )
                    )
                    line_indices.append(pos)
                if line_indices:
                    lines.append(line_indices)
            if tokens:
                ed_docs.append(
                    Document(
                        id=f"{osis} {chap}",
                        script_id="greek",
                        tokens=tokens,
                        lines=lines,
                        meta=DocumentMeta(
                            period="Koine",
                            name=f"{osis} {chap} ({info.get('name', ed)})",
                        ),
                    )
                )

    prov = Provenance(
        source=info.get("name", ed),
        license=info.get("license", bundle.get("_meta", {}).get("license", "")),
        url=info.get("source", ""),
        notes=(f"Greek New Testament edition: {ed}. Loaded via aegean.greek.bible.load_nt.",),
    )
    return Corpus(ed_docs, script_id="greek", provenance=prov)


def _norm_words(text: str) -> tuple[list[str], list[str]]:
    """Return ``(display_words, comparison_keys)`` stripping punctuation and apparatus marks."""
    cleaned = _APPARATUS_MARKS_RE.sub("", unicodedata.normalize("NFC", text))
    display: list[str] = []
    keys: list[str] = []
    for raw in cleaned.split():
        word = _NON_WORD_RE.sub("", raw)
        if not word:
            continue
        display.append(word)
        folded = "".join(
            c for c in unicodedata.normalize("NFD", word) if not unicodedata.combining(c)
        ).lower().replace("ς", "σ")
        keys.append(folded)
    return display, keys


def _verse_text_map(
    book: str,
    ref: str,
    edition: str,
    *,
    offline: bool = False,
) -> dict[str, str]:
    osis = _resolve_book(book)
    if edition == "nestle1904":
        corp = load_nt(osis, ref, edition="nestle1904", offline=offline)
        verses: dict[str, list[str]] = {}
        for doc in corp:
            for tok in doc.tokens:
                vref = tok.annotations.get("ref", "")
                if vref:
                    _, _, cv = vref.partition(".")
                    verses.setdefault(cv, []).append(tok.text)
        return {cv: " ".join(ws) for cv, ws in verses.items()}
    bundle = _load_editions_bundle(allow_fetch=not offline, required_edition=edition)
    vmap = bundle["editions"][edition]["books"].get(osis, {})
    kept = _select_verses(vmap, osis, ref)
    return {f"{c}.{v}": txt for c, v, txt in kept}


def compare_editions(
    book: str,
    ref: str,
    *,
    editions: Sequence[str] | None = None,
    offline: bool = False,
) -> EditionComparison:
    """Compare a Greek NT passage side-by-side across editions with word-level variant diffs.

    By default compares all five editions (``nestle1904``, ``sblgnt``,
    ``srgnt``, ``byz``, ``tr``). Pure punctuation and orthographic/accent
    differences are ignored when computing variants so genuine textual variants
    (such as John 1:18 ``μονογενὴς θεός`` vs. ``ὁ μονογενὴς υἱός``) stand out.
    """
    osis = _resolve_book(book)
    ed_ids = tuple(
        resolve_edition(e)
        for e in (editions if editions is not None else ("nestle1904", "sblgnt", "srgnt", "byz", "tr"))
    )
    if not ed_ids:
        raise ValueError("compare_editions() requires at least one edition")

    per_ed: dict[str, dict[str, str]] = {}
    for eid in ed_ids:
        per_ed[eid] = _verse_text_map(osis, ref, eid, offline=offline)

    all_cvs = sorted(
        {cv for vmap in per_ed.values() for cv in vmap},
        key=_verse_key_tuple,
    )
    base_ed = ed_ids[0]
    verse_rows: list[VerseComparison] = []
    for cv in all_cvs:
        texts = {eid: per_ed[eid].get(cv, "") for eid in ed_ids}
        base_disp, base_keys = _norm_words(texts[base_ed])
        variants: list[WordVariant] = []
        for eid in ed_ids[1:]:
            ed_disp, ed_keys = _norm_words(texts[eid])
            if ed_keys == base_keys:
                continue
            sm = difflib.SequenceMatcher(None, base_keys, ed_keys, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    continue
                variants.append(
                    WordVariant(
                        edition=eid,
                        kind=tag,
                        base_words=tuple(base_disp[i1:i2]),
                        edition_words=tuple(ed_disp[j1:j2]),
                    )
                )
        verse_rows.append(
            VerseComparison(
                ref=f"{osis} {cv.replace('.', ':')}",
                texts=texts,
                identical=len(variants) == 0,
                variants=tuple(variants),
            )
        )
    return EditionComparison(book=osis, ref=ref, editions=ed_ids, verses=tuple(verse_rows))
