"""Early Greek New Testament manuscript witnesses (2nd–5th century CE).

Provides access to 13 landmark early Greek NT manuscripts transcribed by the
Center for New Testament Restoration (``nt-witnesses`` release asset,
CC BY-SA 4.0):

- **Six major uncial codices**: ``01`` (Sinaiticus ℵ), ``02`` (Alexandrinus A),
  ``03`` (Vaticanus B), ``04`` (Ephraemi Rescriptus C), ``05`` (Bezae D), and
  ``032`` (Washingtonianus W).
- **Seven landmark early papyri**: ``P45``, ``P46``, ``P47``, ``P52`` (Rylands),
  ``P66``, ``P72``, and ``P75``.

Exposes both raw CNTR MES diplomatic transcriptions (preserving *nomina sacra*,
line breaks, lacunae, and original vs. corrector hands) and expanded readable
Greek text.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ...scripts.greek.nt import _parse_ref, _resolve_book
from ._catalogs import WITNESS_CATALOG, resolve_witness
from ._mes import WitnessReading, parse_mes

_WITNESSES_CACHE: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class WitnessVerseEntry:
    """One early manuscript's attestation for a verse."""

    siglum: str
    alias: str
    name: str
    century: str
    reading: WitnessReading

    def to_dict(self) -> dict[str, Any]:
        return {
            "siglum": self.siglum,
            "alias": self.alias,
            "name": self.name,
            "century": self.century,
            **self.reading.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class WitnessVerseComparison:
    """All extant early manuscript witnesses attesting one verse."""

    ref: str
    witnesses: tuple[WitnessVerseEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "witness_count": len(self.witnesses),
            "witnesses": [w.to_dict() for w in self.witnesses],
        }


def witnesses() -> list[dict[str, Any]]:
    """List the 13 early Greek New Testament manuscript witnesses (offline metadata)."""
    return [
        {k: v for k, v in spec.items() if k != "aliases"}
        for spec in WITNESS_CATALOG
    ]


def _load_witnesses_bundle(*, allow_fetch: bool = True) -> dict[str, Any]:
    global _WITNESSES_CACHE
    if _WITNESSES_CACHE is not None:
        return _WITNESSES_CACHE
    from ...data import _REMOTE, DataNotAvailableError, cache_dir, fetch, load_gzip_json, present_paths

    paths = present_paths(_REMOTE["nt-witnesses"], cache_dir())
    if not paths:
        if not allow_fetch:
            raise DataNotAvailableError(
                "nt-witnesses is not cached — run `aegean data fetch nt-witnesses` "
                "or pass allow_fetch=True"
            )
        path = fetch("nt-witnesses")
    else:
        path = paths[0]
    _WITNESSES_CACHE = load_gzip_json(path)
    return _WITNESSES_CACHE


def _verse_key_tuple(cv: str) -> tuple[int, int]:
    c, _, v = cv.partition(".")
    return int(c), int(v)


def _select_witness_verses(
    book_verses: dict[str, str],
    ref: str | None,
) -> list[tuple[int, int, str]]:
    items = sorted(
        ((_verse_key_tuple(cv)[0], _verse_key_tuple(cv)[1], raw) for cv, raw in book_verses.items()),
        key=lambda x: (x[0], x[1]),
    )
    if ref is None:
        return items
    sc, sv, ec, ev = _parse_ref(ref)
    kept: list[tuple[int, int, str]] = []
    for c, v, raw in items:
        if c < sc or c > ec:
            continue
        if c == sc and sv is not None and v < sv:
            continue
        if c == ec and ev is not None and v > ev:
            continue
        kept.append((c, v, raw))
    return kept


def load_witness(
    siglum: str,
    book: str | None = None,
    ref: str | None = None,
    *,
    hand: str = "original",
    expand_nomina_sacra: bool = True,
    include_supplied: bool = True,
    offline: bool = False,
) -> Any:
    """Load an early Greek NT manuscript witness as a :class:`aegean.Corpus`.

    Accepts Gregory–Aland sigla (``'01'``, ``'03'``, ``'P52'``, ``'P66'``),
    traditional symbols (``'ℵ'``, ``'B'``, ``'A'``, ``'D'``), or names
    (``'Sinaiticus'``, ``'Vaticanus'``, ``'Rylands'``). Each token carries
    ``ref``, ``witness``, and ``diplomatic_verse`` annotations.
    """
    canon = resolve_witness(siglum)
    if ref is not None and book is None:
        raise ValueError(f"ref requires a book, e.g. load_witness({canon!r}, 'John', ref='1.1-18')")

    bundle = _load_witnesses_bundle(allow_fetch=not offline)
    wdata = bundle["witnesses"][canon]
    info = wdata["_info"]
    books_map: dict[str, dict[str, str]] = wdata["books"]

    if book is not None:
        osis = _resolve_book(book)
        if osis not in books_map:
            avail = ", ".join(books_map)
            raise ValueError(
                f"{info['name']} ({canon}) is not extant for {osis}; extant books: {avail}"
            )
        selected_books = [(osis, books_map[osis])]
    else:
        selected_books = list(books_map.items())

    from ...core.corpus import Corpus
    from ...core.model import Document, DocumentMeta, Token, TokenKind
    from ...core.provenance import Provenance

    docs: list[Document] = []
    for osis, vmap in selected_books:
        verses = _select_witness_verses(vmap, ref)
        by_chapter: dict[int, list[tuple[int, str]]] = {}
        for c, v, raw in verses:
            by_chapter.setdefault(c, []).append((v, raw))
        for chap, cverses in sorted(by_chapter.items()):
            tokens: list[Token] = []
            lines: list[list[int]] = []
            for vno, raw in cverses:
                reading = parse_mes(
                    raw,
                    hand=hand,
                    expand_nomina_sacra=expand_nomina_sacra,
                    include_supplied=include_supplied,
                )
                line_indices: list[int] = []
                for word in reading.readable.split():
                    pos = len(tokens)
                    tokens.append(
                        Token(
                            text=word,
                            kind=TokenKind.WORD,
                            glyphs=word,
                            line_no=vno,
                            position=pos,
                            annotations={
                                "ref": f"{osis}.{chap}.{vno}",
                                "witness": canon,
                                "hand": hand,
                            },
                        )
                    )
                    line_indices.append(pos)
                if line_indices:
                    lines.append(line_indices)
            if tokens:
                docs.append(
                    Document(
                        id=f"{canon} {osis} {chap}",
                        script_id="greek",
                        tokens=tokens,
                        lines=lines,
                        meta=DocumentMeta(
                            period=info.get("century", "Koine"),
                            name=f"{info['name']} ({canon}/{info['alias']}) — {osis} {chap}",
                        ),
                    )
                )
    if not docs:
        raise ValueError(
            f"{info['name']} ({canon}) has no extant text for {book or ''} {ref or ''}".strip()
        )
    prov = Provenance(
        source=f"{info['name']} ({canon}) via CNTR Class 1 transcriptions",
        license=bundle.get("_meta", {}).get("license", "CC BY-SA 4.0"),
        url=bundle.get("_meta", {}).get("source_url", ""),
        notes=(
            f"Text type: {info.get('text_type', '')}",
            f"Repository: {info.get('repository', '')}",
            f"Rendered hand={hand!r}, expand_nomina_sacra={expand_nomina_sacra}.",
        ),
    )
    return Corpus(docs, script_id="greek", provenance=prov)


def compare_witnesses(
    book: str,
    ref: str,
    *,
    sigla: Sequence[str] | None = None,
    hand: str = "original",
    expand_nomina_sacra: bool = True,
    include_supplied: bool = True,
    offline: bool = False,
) -> list[WitnessVerseComparison]:
    """Compare extant early Greek NT manuscripts verse-by-verse for a passage.

    For example, ``compare_witnesses('John', '1.18')`` shows ``P66``, ``P75``,
    ``01`` (Sinaiticus), ``02`` (Alexandrinus), ``03`` (Vaticanus), ``04``
    (Ephraemi), and ``032`` (Washingtonianus) side by side, preserving both
    diplomatic MES markup and expanded readable readings.
    """
    osis = _resolve_book(book)
    bundle = _load_witnesses_bundle(allow_fetch=not offline)
    if sigla is not None:
        chosen = [resolve_witness(s) for s in sigla]
    else:
        # Show earliest papyri first, then major uncials in canonical order
        papyri = [w["siglum"] for w in WITNESS_CATALOG if w["kind"] == "papyrus"]
        uncials = [w["siglum"] for w in WITNESS_CATALOG if w["kind"] == "uncial"]
        chosen = papyri + uncials

    per_verse: dict[str, list[WitnessVerseEntry]] = {}
    for sig in chosen:
        wdata = bundle["witnesses"].get(sig)
        if wdata is None:
            continue
        vmap = wdata["books"].get(osis)
        if not vmap:
            continue
        info = wdata["_info"]
        for c, v, raw in _select_witness_verses(vmap, ref):
            cv = f"{c}.{v}"
            reading = parse_mes(
                raw,
                hand=hand,
                expand_nomina_sacra=expand_nomina_sacra,
                include_supplied=include_supplied,
            )
            per_verse.setdefault(cv, []).append(
                WitnessVerseEntry(
                    siglum=sig,
                    alias=info.get("alias", sig),
                    name=info.get("name", sig),
                    century=info.get("century", ""),
                    reading=reading,
                )
            )

    if not per_verse:
        raise ValueError(f"no extant early witnesses matched {osis} {ref!r}")

    return [
        WitnessVerseComparison(
            ref=f"{osis} {cv.replace('.', ':')}",
            witnesses=tuple(per_verse[cv]),
        )
        for cv in sorted(per_verse, key=_verse_key_tuple)
    ]
