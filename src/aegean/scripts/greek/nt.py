"""The Greek New Testament (Nestle 1904) as a loadable, annotated Koine corpus.

``greek.load_nt(book, ref=...)`` is the Koine counterpart to ``greek.load_work``: it
returns a `Corpus` of the Greek NT with, per token, a gold **lemma**, a Robinson-style
**morph** parse, a **Strong's** number, a reconciled UD **upos**, and the **normalized**
form — all carried in ``Token.annotations`` (so ``to_dataframe`` surfaces them as columns).

Source: the Nestle 1904 edition with morphology/lemmas/Strong's dedicated to the public
domain under CC0 (biblicalhumanities/Nestle1904), built into a release asset by
``scripts/build_nt_corpus.py``. CC0 lets us both fetch the full 27-book corpus to cache
and bundle one book as an offline sample — ``aegean.load("nt")`` works with no network for
that book and fetches the rest on demand.

Reference addressing mirrors ``load_work``: ``ref="3"`` selects a chapter, ``ref="3.16"`` a
verse, ``ref="3.16-3.18"`` (or the shorthand ``ref="3.16-18"``) a verse range, ``ref="3-5"``
a chapter range.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

# Robinson POS -> UD UPOS. Bare tags (no case/feature block) first, then the
# hyphenated families keyed by their leading letter.
_BARE_UPOS: dict[str, str] = {
    "CONJ": "CCONJ", "PREP": "ADP", "ADV": "ADV", "PRT": "PART",
    "COND": "SCONJ", "INJ": "INTJ", "ARAM": "X", "HEB": "X",
}
_PREFIX_UPOS: dict[str, str] = {
    "N": "NOUN", "A": "ADJ", "T": "DET", "V": "VERB",
    "P": "PRON", "R": "PRON", "C": "PRON", "D": "PRON",
    "K": "PRON", "I": "PRON", "X": "PRON", "Q": "PRON", "F": "PRON", "S": "PRON",
}

# Friendly book name / abbreviation -> OSIS id (the canonical key used in the asset).
_OSIS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Matt", ("matthew", "matt", "mt")),
    ("Mark", ("mark", "mk", "mrk")),
    ("Luke", ("luke", "lk", "luk")),
    ("John", ("john", "jn", "jhn")),
    ("Acts", ("acts", "act")),
    ("Rom", ("romans", "rom", "rm")),
    ("1Cor", ("1corinthians", "1cor", "1co")),
    ("2Cor", ("2corinthians", "2cor", "2co")),
    ("Gal", ("galatians", "gal", "ga")),
    ("Eph", ("ephesians", "eph")),
    ("Phil", ("philippians", "phil", "php")),
    ("Col", ("colossians", "col")),
    ("1Thess", ("1thessalonians", "1thess", "1th")),
    ("2Thess", ("2thessalonians", "2thess", "2th")),
    ("1Tim", ("1timothy", "1tim", "1ti")),
    ("2Tim", ("2timothy", "2tim", "2ti")),
    ("Titus", ("titus", "tit")),
    ("Phlm", ("philemon", "phlm", "phm")),
    ("Heb", ("hebrews", "heb")),
    ("Jas", ("james", "jas", "jms")),
    ("1Pet", ("1peter", "1pet", "1pe")),
    ("2Pet", ("2peter", "2pet", "2pe")),
    ("1John", ("1john", "1jn", "1jhn")),
    ("2John", ("2john", "2jn", "2jhn")),
    ("3John", ("3john", "3jn", "3jhn")),
    ("Jude", ("jude", "jud")),
    ("Rev", ("revelation", "rev", "rv", "apocalypse")),
)
_ALIAS: dict[str, str] = {a: osis for osis, aliases in _OSIS for a in (osis.lower(), *aliases)}


def robinson_to_upos(morph: str) -> str:
    """Map a Robinson/Nestle1904 morph tag to a coarse UD UPOS (e.g. ``N-NSF`` -> NOUN)."""
    tag = morph.strip()
    if tag in _BARE_UPOS:
        return _BARE_UPOS[tag]
    if tag.startswith("N-PRI"):
        return "PROPN"
    if tag.startswith("A-NUI"):
        return "NUM"
    return _PREFIX_UPOS.get(tag.split("-", 1)[0], "X")


def _resolve_book(book: str) -> str:
    key = book.strip().lower().replace(" ", "").replace(".", "")
    osis = _ALIAS.get(key)
    if osis is None:
        raise ValueError(
            f"unknown NT book {book!r}; use a name or abbreviation like "
            "'John', 'Jn', 'Matthew', '1Cor', 'Rev'"
        )
    return osis


def _parse_ref(ref: str) -> tuple[int, int | None, int, int | None]:
    """``'3'``/``'3.16'``/``'3.16-3.18'``/``'3.16-18'``/``'3-5'`` ->
    (start_chapter, start_verse|None, end_chapter, end_verse|None)."""

    def part(s: str) -> tuple[int, int | None]:
        s = s.strip()
        if "." in s:
            c, v = s.split(".", 1)
            return int(c), int(v)
        return int(s), None

    ref = ref.strip()
    if "-" in ref:
        lo, hi = ref.split("-", 1)
        sc, sv = part(lo)
        hi = hi.strip()
        if "." in hi:
            ec, ev = part(hi)
        elif sv is not None:          # bare hi after a verse lo -> verse in lo's chapter
            ec, ev = sc, int(hi)
        else:                          # bare hi after a chapter lo -> chapter
            ec, ev = int(hi), None
        return sc, sv, ec, ev
    sc, sv = part(ref)
    return sc, sv, sc, sv


def _build_document(rec: dict[str, Any], keep: Callable[[int], bool] | None = None) -> Any:
    """Build a `Document` from one chapter record, optionally keeping only some verses."""
    from ...core.model import Document, DocumentMeta, Token, TokenKind
    from ...greek.koine import _strongs_gloss_map

    glosses = _strongs_gloss_map()  # Strong's -> brief Koine gloss (bundled Dodson, CC0)
    book = rec["book"]
    chapter = rec["chapter"]
    tokens: list[Token] = []
    lines: dict[int, list[int]] = {}
    for td in rec["tokens"]:
        verse = int(td["v"])
        if keep is not None and not keep(verse):
            continue
        pos = len(tokens)
        morph = td.get("morph", "")
        strongs = td.get("strongs", "")
        anno = {
            "lemma": td.get("lemma", ""),
            "morph": morph,
            "strongs": strongs,
            "normalized": td.get("norm", ""),
            "upos": robinson_to_upos(morph),
            "ref": f"{book}.{chapter}.{verse}",
        }
        gloss = glosses.get(strongs)
        if gloss:
            anno["gloss"] = gloss
        tokens.append(Token(
            text=td["t"], kind=TokenKind.WORD, glyphs=td["t"],
            line_no=verse, position=pos, annotations=anno,
        ))
        lines.setdefault(verse, []).append(pos)
    if not tokens:
        return None
    lines_list = [lines[v] for v in sorted(lines)]
    return Document(
        id=rec["id"], script_id="greek", tokens=tokens, lines=lines_list,
        meta=DocumentMeta(period="Koine", name=rec.get("name", rec["id"])),
    )


def _select(records: list[dict[str, Any]], book: str | None, ref: str | None) -> list[Any]:
    """Filter chapter records by book + ref and build the (verse-trimmed) Documents."""
    if ref is not None and book is None:
        raise ValueError("ref requires a book, e.g. load_nt('John', ref='1.1-18')")
    osis = _resolve_book(book) if book is not None else None
    sc = sv = ec = ev = None
    if ref is not None:
        sc, sv, ec, ev = _parse_ref(ref)

    docs: list[Any] = []
    for rec in records:
        if osis is not None and rec["book"] != osis:
            continue
        keep: Callable[[int], bool] | None = None
        if ref is not None:
            chapter = rec["chapter"]
            assert sc is not None and ec is not None
            if chapter < sc or chapter > ec:
                continue

            def keep(verse: int, _c: int = chapter) -> bool:
                if _c == sc and sv is not None and verse < sv:
                    return False
                if _c == ec and ev is not None and verse > ev:
                    return False
                return True

        doc = _build_document(rec, keep)
        if doc is not None:
            docs.append(doc)
    if not docs:
        where = f" for {book}" + (f" {ref}" if ref else "") if book else ""
        raise ValueError(f"no New Testament text matched the request{where}")
    return docs


def _provenance(meta: dict[str, Any], *, offline: bool) -> Any:
    from ...core.provenance import Provenance

    notes = [
        "Greek New Testament (Nestle 1904); per-token lemma/morph/Strong's/UPOS in "
        "Token.annotations. Morphology, lemmas, and Strong's numbers are CC0; the base "
        "Greek text is public domain.",
    ]
    if offline:
        notes.append(
            "Loaded from the bundled one-book offline sample; call greek.load_nt(book) "
            "with network access (or set PYAEGEAN_NT_CORPUS_URL) for the full 27 books."
        )
    return Provenance(
        source="Nestle 1904 Greek NT — morphology/lemmas (biblicalhumanities/Nestle1904)",
        license=str(meta.get("license", "CC0-1.0 (morphology); base text public domain")),
        citation=str(meta.get("cite", "Nestle, E. (1904). Novum Testamentum Graece.")),
        url=str(meta.get("source_url", "https://github.com/biblicalhumanities/Nestle1904")),
        data_version=f"nt-corpus-v{meta.get('version', 1)}@{meta.get('source_commit', meta.get('generated', ''))}",
        notes=tuple(notes),
    )


@lru_cache(maxsize=1)
def _bundled_payload() -> dict[str, Any]:
    from ...data import load_bundled_json

    return dict(load_bundled_json("greek", "nt_sample.json"))


def load_nt(book: str | None = None, *, ref: str | None = None, force: bool = False) -> Any:
    """Load the Greek New Testament (Nestle 1904) as an annotated `Corpus`.

    ``book`` selects one book by name or abbreviation (``'John'``, ``'Jn'``, ``'1Cor'``,
    ``'Rev'``); ``None`` returns the whole NT. ``ref`` selects within a book, mirroring
    ``load_work``: ``'3'`` a chapter, ``'3.16'`` a verse, ``'3.16-3.18'`` / ``'3.16-18'`` a
    verse range, ``'3-5'`` a chapter range. One `Document` per chapter; every token carries
    a gold lemma, Robinson morph, Strong's number, reconciled UD ``upos``, and the
    normalized form in ``Token.annotations``.

    The full 27-book corpus is fetched to cache on first use (sha256-pinned CC0 asset, or
    ``PYAEGEAN_NT_CORPUS_URL``). When that asset is unavailable the bundled one-book sample
    is used as an offline fallback (its provenance says so)."""
    import json as _json

    from ...core.corpus import Corpus
    from ...data import DataNotAvailableError, fetch
    from .inventory import greek_inventory

    offline = False
    try:
        path = fetch("nt-corpus", force=force)
        payload: dict[str, Any] = _json.loads(path.read_text(encoding="utf-8"))
    except DataNotAvailableError:
        payload = _bundled_payload()
        offline = True

    meta = payload.get("_meta", {})
    try:
        docs = _select(payload["documents"], book, ref)
    except ValueError:
        if not offline:
            raise
        # The offline sample is one book; re-raise with guidance only if that book was wanted.
        raise
    provenance = _provenance(meta, offline=offline)
    return Corpus(docs, sign_inventory=greek_inventory(), provenance=provenance, script_id="greek")


# loadable by name: aegean.load("nt") — fetches the full corpus, or the bundled sample offline
from ...core.corpus import register_loader  # noqa: E402

register_loader("nt", load_nt)
