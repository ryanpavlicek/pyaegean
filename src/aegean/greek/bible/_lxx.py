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
    """Return ``True`` if the full 56-book ``lxx-corpus`` bundle is cached locally."""
    if _LXX_CACHE is not None:
        return True
    from ...data import _REMOTE, cache_dir, present_paths

    spec = _REMOTE.get("lxx-corpus")
    return bool(spec and present_paths(spec, cache_dir()))


def _load_lxx_bundle(
    *,
    allow_fetch: bool = True,
    force: bool = False,
) -> dict[str, Any] | None:
    global _LXX_CACHE
    if _LXX_CACHE is not None and not force:
        return _LXX_CACHE
    from ...data import _REMOTE, cache_dir, fetch, load_gzip_json, present_paths

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


def _ensure_lxx_book(
    bundle: dict[str, Any] | None,
    required_book: str | None,
    *,
    allow_fetch: bool,
) -> dict[str, Any] | None:
    """Auto-upgrade a cached v1 (55-book) LXX bundle when a v2 book like Eccl is requested."""
    if bundle is None or required_book is None:
        return bundle
    if required_book in bundle.get("books", {}):
        return bundle
    from ...data import DataNotAvailableError

    if not allow_fetch:
        raise DataNotAvailableError(
            f"cached lxx-corpus bundle (v1, 55 books) does not include {required_book!r} — "
            "run `aegean data fetch lxx-corpus --force` to upgrade to v2 (56 books)"
        )
    return _load_lxx_bundle(allow_fetch=True, force=True)


def _split_lxx_book_and_ref(
    book: str | None,
    ref: str | None,
    numbering: str,
) -> tuple[str | None, str | None, str]:
    """Allow inline refs like ``load_lxx('Gen 1:1-5')`` or ``load_lxx('MT Ps 23')``."""
    if book is None:
        return None, ref, numbering
    raw = book.strip()
    sys_mode = numbering.strip().lower()
    if raw.upper().startswith("MT "):
        sys_mode = "mt"
        raw = raw[3:].strip()
    if ref is not None:
        return raw, ref, sys_mode
    parts = raw.split()
    if len(parts) < 2:
        return raw, None, sys_mode
    # Handle numbered books like "1 Kgdms 1:1" or "1 Macc 2:1-5"
    if parts[0].isdigit() and len(parts) >= 3:
        tail = " ".join(parts[2:])
        if any(ch.isdigit() for ch in tail) or tail.lower() in ("prologue", "praef"):
            return f"{parts[0]} {parts[1]}", tail, sys_mode
    tail = " ".join(parts[1:])
    if any(ch.isdigit() for ch in tail) or tail.lower() in ("prologue", "praef"):
        return parts[0], tail, sys_mode
    return raw, None, sys_mode


def _translate_mt_psalm_ref(ref: str) -> tuple[str, dict[str, int]]:
    """Map a Masoretic Psalm ref (e.g. ``'23'``, ``'23:1-6'``, ``'23-24'``) to LXX ref + map."""
    from ._catalogs import psalm_mt_to_lxx

    s = ref.strip().replace(":", ".")
    lxx_to_mt: dict[str, int] = {}
    if "." in s:
        chap_part, _, vpart = s.partition(".")
        if not chap_part.strip().isdigit():
            raise ValueError(f"invalid Masoretic Psalm reference {ref!r}")
        mt_num = int(chap_part.strip())
        lxx_nums = psalm_mt_to_lxx(mt_num)
        for ln in lxx_nums:
            lxx_to_mt[str(ln)] = mt_num
        # Single-chapter MT Psalm -> primary LXX Psalm number
        return f"{lxx_nums[0]}.{vpart}", lxx_to_mt
    if "-" in s:
        a, _, b = s.partition("-")
        if not (a.strip().isdigit() and b.strip().isdigit()):
            raise ValueError(f"invalid Masoretic Psalm range {ref!r}")
        lo, hi = int(a.strip()), int(b.strip())
        if lo > hi:
            raise ValueError(f"invalid Masoretic Psalm range {ref!r}")
        lxx_all: list[int] = []
        for mt_n in range(lo, hi + 1):
            for ln in psalm_mt_to_lxx(mt_n):
                lxx_all.append(ln)
                lxx_to_mt.setdefault(str(ln), mt_n)
        return f"{min(lxx_all)}-{max(lxx_all)}", lxx_to_mt
    if not s.isdigit():
        raise ValueError(f"invalid Masoretic Psalm reference {ref!r}")
    mt_num = int(s)
    lxx_nums = psalm_mt_to_lxx(mt_num)
    for ln in lxx_nums:
        lxx_to_mt[str(ln)] = mt_num
    if len(lxx_nums) == 1:
        return str(lxx_nums[0]), lxx_to_mt
    return f"{min(lxx_nums)}-{max(lxx_nums)}", lxx_to_mt


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


_STRONGS_POS_MAP: dict[str, str] = {
    "N": "NOUN",
    "V": "VERB",
    "A": "ADJ",
    "ADV": "ADV",
    "PREP": "ADP",
    "CONJ": "CCONJ",
    "COND": "SCONJ",
    "T": "DET",
    "P": "PRON",
    "D": "PRON",
    "R": "PRON",
    "I": "PRON",
    "X": "PRON",
    "F": "PRON",
    "C": "PRON",
    "K": "PRON",
    "Q": "PRON",
    "S": "PRON",
    "PRT": "PART",
    "INJ": "INTJ",
}


def _strongs_morph_to_upos(morph: str) -> str | None:
    """Map a STEPBible/Strong's morphology tag (e.g. ``G:PREP``, ``G:V``, ``G:A``) to coarse UPOS."""
    if not morph:
        return None
    head = morph.split("/")[0].split("+")[0].strip()
    if head.startswith(("G:", "H:")):
        head = head[2:]
    head = head.split("-")[0].split("=")[0].split(":")[0].strip().upper()
    return _STRONGS_POS_MAP.get(head)


# Closed-class Koine/LXX improper prepositions (especially -ω forms like ἐπάνω
# that would otherwise trip the offline suffix heuristic -> VERB when Extended
# Strong's is not cached). Kept local to LXX enrichment so offline_baseline_ud
# POS benchmarks in aegean.greek.pos remain untouched.
_LXX_IMPROPER_PREPS: frozenset[str] = frozenset(
    _fold(w)
    for w in (
        "ἐπάνω",
        "ὑποκάτω",
        "κάτω",
        "ἄνω",
        "ἔξω",
        "ἔσω",
        "ὀπίσω",
        "πόρρω",
        "ἐνώπιον",
        "ἔμπροσθεν",
        "μεταξύ",
        "πέραν",
        "χωρίς",
        "ἕως",
        "ἄχρι",
        "μέχρι",
    )
)


def enrich_lxx_interlinear(corpus: Any, *, allow_fetch: bool = False) -> Any:
    """Attach automatic lemma, POS, Strong's ID, and gloss to LXX tokens in place.

    Clearly tags each enriched token with ``annotation_source="auto-lexicon"`` so
    automatic lexicon lookup is always distinguished from gold treebank/Nestle 1904
    annotations. Uses Extended Strong's (fetched once when ``allow_fetch=True`` and
    not yet cached, providing curated STEPBible morphology across 11,142 Greek
    entries) and falls back cleanly to the bundled offline Dodson lexicon +
    offline lemmatizer/POS rules when offline.
    """
    from ..lemmatize import lemmatize
    from ..pos import pos_tag
    from ._strongs import strongs_entry, use_strongs

    if allow_fetch:
        try:
            use_strongs(fetch=True)
        except Exception:
            pass

    entry_cache: dict[str, Any] = {}
    for doc in corpus:
        for tok in doc.tokens:
            ann = tok.annotations
            if ann.get("lemma") and ann.get("gloss"):
                continue
            surface = tok.text
            lem = ann.get("lemma") or lemmatize(surface)
            key = _fold(lem)
            if key not in entry_cache:
                ent = strongs_entry(lem, allow_fetch=False)
                if ent is None and _fold(surface) != key:
                    ent = strongs_entry(surface, allow_fetch=False)
                entry_cache[key] = ent
            ent = entry_cache[key]
            resolved_lemma = ent.lemma if ent is not None else lem
            pos = ann.get("morph") or ann.get("pos")
            if not pos:
                # Prefer Strong's curated lexicon POS when available (avoids suffix-heuristic
                # traps like ἐπάνω 'above' ending in -ω -> VERB, or unaccented ΕΝ -> NOUN).
                strongs_pos = _strongs_morph_to_upos(ent.morph) if ent is not None else None
                if strongs_pos:
                    pos = strongs_pos
                elif _fold(resolved_lemma) in _LXX_IMPROPER_PREPS or _fold(surface) in _LXX_IMPROPER_PREPS:
                    pos = "ADP"
                else:
                    pos = pos_tag(surface)
                    if pos == "NOUN" and resolved_lemma != surface:
                        lem_pos = pos_tag(resolved_lemma)
                        if lem_pos != "NOUN":
                            pos = lem_pos
            ann["lemma"] = resolved_lemma
            if pos:
                ann.setdefault("morph", pos)
            if ent is not None:
                ann.setdefault("strongs", ent.strongs)
                ann.setdefault("gloss", ent.gloss)
            ann["annotation_source"] = "auto-lexicon"
    return corpus


def load_lxx(
    book: str | None = None,
    ref: str | None = None,
    *,
    numbering: str = "lxx",
    interlinear: bool = False,
    offline: bool = False,
    force: bool = False,
) -> Any:
    """Load a Septuagint (LXX) book or passage as a :class:`~aegean.core.corpus.Corpus`.

    Uses the SHA-256-pinned ``lxx-corpus`` bundle (all 56 Greek Septuagint books
    including Ecclesiastes, 29,470 verses) when cached or ``offline=False``.
    When ``offline=True`` and the full bundle is not yet cached, serves from the
    bundled Swete 1887 offline sample (Genesis 1:1–5 and LXX Psalm 22:1–6 [MT 23]).

    Accepts inline references (``load_lxx("Gen 1:1-5")`` or ``load_lxx("MT Ps 23")``),
    Masoretic Psalm numbering (``numbering="mt"``), and automatic offline interlinear
    glossing (``interlinear=True``, tagged ``annotation_source="auto-lexicon"``).
    """
    book, ref, sys_mode = _split_lxx_book_and_ref(book, ref, numbering)
    if sys_mode not in ("lxx", "mt"):
        raise ValueError(f"numbering must be 'lxx' or 'mt', got {numbering!r}")
    if ref is not None and book is None:
        raise ValueError("ref requires a book name, e.g. load_lxx('Gen', ref='1.1-5')")

    book_specs = [resolve_lxx_book(book)] if book is not None else list(_LXX_BOOKS)
    req_book = book_specs[0].name if book is not None else None

    lxx_to_mt_map: dict[str, int] = {}
    effective_ref = ref
    if sys_mode == "mt" and req_book == "Ps" and ref is not None:
        effective_ref, lxx_to_mt_map = _translate_mt_psalm_ref(ref)

    bundle = _ensure_lxx_book(
        _load_lxx_bundle(allow_fetch=not offline, force=force),
        req_book,
        allow_fetch=not offline,
    )
    using_sample = bundle is None

    from ...core.corpus import Corpus
    from ...core.model import Document, DocumentMeta, Token, TokenKind
    from ...core.provenance import Provenance
    from ...data import DataNotAvailableError
    from ..tokenize import tokenize

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
            selected = _select_lxx_verses(vmap, bspec.name, effective_ref)
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
            mt_num = lxx_to_mt_map.get(chap_s)
            for idx, (verse_s, text) in enumerate(cverses, start=1):
                vno = _verse_line_int(verse_s, idx)
                line_indices: list[int] = []
                for tok in tokenize(text):
                    if not any(ch.isalpha() for ch in tok.text):
                        continue
                    pos = len(tokens)
                    ann: dict[str, Any] = {
                        "ref": f"{bspec.name}.{chap_s}.{verse_s}",
                        "edition": "swete-lxx",
                    }
                    if mt_num is not None:
                        ann["mt_ref"] = f"MT Ps.{mt_num}.{verse_s}"
                    tokens.append(
                        Token(
                            text=unicodedata.normalize("NFC", tok.text),
                            kind=TokenKind.WORD,
                            glyphs=unicodedata.normalize("NFC", tok.text),
                            line_no=vno,
                            position=pos,
                            annotations=ann,
                        )
                    )
                    line_indices.append(pos)
                if line_indices:
                    lines.append(line_indices)
            if tokens:
                mt_suffix = f" [MT Ps {mt_num}]" if mt_num is not None else ""
                docs.append(
                    Document(
                        id=f"{bspec.name} {chap_s}",
                        script_id="greek",
                        tokens=tokens,
                        lines=lines,
                        meta=DocumentMeta(
                            period="Koine",
                            name=f"{bspec.title} {chap_s} (Swete LXX{mt_suffix})",
                        ),
                    )
                )

    if using_sample:
        prov = Provenance(
            source="Swete Septuagint (1887–1894, offline sample: Gen 1:1–5, Ps 22:1–6)",
            license="Public Domain (Henry Barclay Swete, Cambridge University Press, 1887–1894)",
            url="https://github.com/OpenGreekAndLatin/First1KGreek",
            notes=("Bundled offline Swete Septuagint sample; fetch 'lxx-corpus' for all 56 books.",),
        )
    else:
        assert bundle is not None
        meta = bundle.get("_meta", {})
        prov = Provenance(
            source=meta.get(
                "edition",
                "Swete Septuagint (1887–1894) + Wikisource Ecclesiastes",
            ),
            license=meta.get("license", "CC BY-SA 4.0"),
            url=meta.get("source_repo", "https://github.com/OpenGreekAndLatin/First1KGreek"),
            data_version=meta.get("source_commit"),
            notes=("Loaded from SHA-256-pinned lxx-corpus release asset (56 books).",),
        )
    corpus = Corpus(docs, script_id="greek", provenance=prov)
    if interlinear:
        enrich_lxx_interlinear(corpus, allow_fetch=not offline)
    return corpus


# Per-bundle pre-folded search index: keyed by id(source_map) so force-reloads and
# monkeypatched test bundles stay automatically isolated with zero stale hits.
_LXX_FOLD_INDEX: tuple[int, dict[str, tuple[tuple[str, str, str], ...]]] | None = None


def _folded_book_verses(
    source_key: int,
    book_name: str,
    vmap: dict[str, str],
) -> tuple[tuple[str, str, str], ...]:
    """Return ordered ``(cv, raw_text, folded_text)`` tuples for ``book_name``, cached per bundle."""
    global _LXX_FOLD_INDEX
    if _LXX_FOLD_INDEX is None or _LXX_FOLD_INDEX[0] != source_key:
        _LXX_FOLD_INDEX = (source_key, {})
    by_book = _LXX_FOLD_INDEX[1]
    cached = by_book.get(book_name)
    if cached is not None:
        return cached
    rows = tuple(
        (cv, text, _fold(text))
        for cv, text in sorted(vmap.items(), key=lambda kv: _verse_sort_key(kv[0]))
    )
    by_book[book_name] = rows
    return rows


def search_lxx(
    query: str,
    *,
    book: str | None = None,
    section: str | None = None,
    limit: int = 25,
    offline: bool = False,
) -> list[LxxHit]:
    """Search the Greek Septuagint (LXX) by Greek word, folded stem, or phrase.

    Searches all 56 Greek Septuagint books when ``lxx-corpus`` is cached or
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

    req_book = resolve_lxx_book(book).name if book is not None else None
    bundle = _ensure_lxx_book(
        _load_lxx_bundle(allow_fetch=not offline),
        req_book,
        allow_fetch=not offline,
    )
    using_sample = bundle is None
    source_key = id(_OFFLINE_LXX_SAMPLE) if using_sample else id(bundle)

    if book is not None:
        book_specs = [resolve_lxx_book(book)]
    else:
        book_specs = list(_LXX_BOOKS)
        if section is not None:
            want_sec = section.strip().lower()
            book_specs = [b for b in book_specs if b.section.lower() == want_sec]

    if using_sample:
        book_specs = [b for b in book_specs if b.name in _OFFLINE_LXX_SAMPLE]
    elif bundle is not None:
        avail_books = bundle.get("books", {})
        book_specs = [b for b in book_specs if b.name in avail_books]

    hits: list[LxxHit] = []
    from ..tokenize import tokenize

    for bspec in book_specs:
        vmap = (
            _OFFLINE_LXX_SAMPLE[bspec.name]
            if using_sample
            else bundle["books"][bspec.name]["verses"]  # type: ignore[index]
        )
        for cv, text, folded_text in _folded_book_verses(source_key, bspec.name, vmap):
            if q_fold not in folded_text:
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
    """Read or search Greek patristic commentary sections (Catenae, Origen, John
    Chrysostom, First1KGreek Fathers, or *Patrologia Graeca*) for a book.

    Loads First1KGreek volumes via :func:`aegean.greek.load_work`, John Chrysostom
    commentary/homily series (``ogc*``) via :func:`aegean.greek.load_collection_work`,
    and *Patrologia Graeca* volumes (``PG*``) via :func:`aegean.scripts.greek.load_patrologia`,
    returning structured :class:`CommentaryExcerpt` records optionally filtered by
    Greek ``query`` (accent/case-insensitive).
    """
    if work_id is not None:
        wid_up = work_id.strip().upper()
        matches = [
            c for c in patristic_commentaries()
            if c["work_id"].upper() == wid_up
        ]
        if matches:
            meta = matches[0]
        elif wid_up.startswith("OGC"):
            from ...scripts.greek._collections import resolve_collection_work

            resolved = resolve_collection_work(work_id)
            meta = {
                "work_id": resolved["work_id"],
                "book": book,
                "author": resolved["author"],
                "title": resolved["title"],
                "kind": "chrysostom" if resolved["collection"] == "chrysostom" else (kind or "patristic"),
            }
        else:
            meta = {
                "work_id": work_id,
                "book": book,
                "author": "Patristic",
                "title": work_id,
                "kind": "patrologia" if wid_up.startswith("PG") else (kind or "catena"),
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

    wid = str(meta["work_id"])
    q_fold = _fold(query.strip()) if query and query.strip() else ""

    # Build (section_id, words) chunks: page-by-page for PG, locus-by-locus for OGC, doc-by-doc for First1K.
    chunks: list[tuple[str, list[str]]] = []
    if wid.upper().startswith("PG"):
        from ...scripts.greek.patrologia import load_patrologia

        corp = load_patrologia(wid)
        for doc in corp:
            by_page: dict[str, list[str]] = {}
            for tok in doc.tokens:
                pg = str(tok.annotations.get("page", "1"))
                if ref and pg != ref.strip():
                    continue
                by_page.setdefault(pg, []).append(tok.text)
            for pg, words in by_page.items():
                chunks.append((f"{doc.id} p.{pg}", words))
    elif wid.lower().startswith("ogc"):
        from ...scripts.greek._collections import load_collection_work

        corp = load_collection_work(wid, force=force)
        for doc in corp:
            by_locus: dict[str, list[str]] = {}
            for tok in doc.tokens:
                loc = str(tok.annotations.get("ref", "1"))
                if ref and ref.strip().lower() not in loc.lower():
                    continue
                by_locus.setdefault(loc, []).append(tok.text)
            for loc, words in by_locus.items():
                chunks.append((loc, words))
    else:
        from ...scripts.greek.perseus import load_work

        corp = load_work(wid, ref=ref, source="first1k", force=force)
        for doc in corp:
            sec = doc.id.partition(":")[2] or doc.id
            chunks.append((sec, [t.text for t in doc.tokens]))

    excerpts: list[CommentaryExcerpt] = []
    for sec, words in chunks:
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
