"""Offline catalogues and scholarly reference helpers for Biblical & Koine Greek.

Maps friendly biblical book names and scholarly abbreviations onto:

- **Septuagint (LXX)**: all 55 Swete Septuagint books (``tlg0527.*``) already
  present in pyaegean's First1KGreek work catalogue, plus exact **LXX ↔ Masoretic
  (MT) Psalm numbering** conversion.
- **Greek Patristic Commentaries**: all 30 Greek New Testament *Catenae*
  volumes (``tlg4102.*``) covering 26 of the 27 NT books, plus Origen's biblical
  commentaries, homilies, and scholia (``tlg2042.*``).
- **Greek New Testament Editions**: ``nestle1904``, ``sblgnt``, ``srgnt``,
  ``byz``, and ``tr``.
- **Early Greek NT Manuscript Witnesses**: 13 landmark 2nd–5th century CE
  uncials and papyri (``01``/ℵ, ``02``/A, ``03``/B, ``04``/C, ``05``/D,
  ``032``/W, ``P45``, ``P46``, ``P47``, ``P52``, ``P66``, ``P72``, ``P75``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...scripts.greek.nt import _resolve_book as _resolve_nt_book


@dataclass(frozen=True, slots=True)
class LxxBook:
    """Metadata for one Septuagint (LXX) book in the First1KGreek catalogue."""

    name: str
    title: str
    work_id: str
    section: str
    aliases: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "work_id": self.work_id,
            "section": self.section,
            "aliases": list(self.aliases),
        }


@dataclass(frozen=True, slots=True)
class CommentaryWork:
    """Metadata for one Greek patristic biblical commentary in First1KGreek."""

    work_id: str
    book: str
    author: str
    title: str
    kind: str  # "catena" or "origen"

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "book": self.book,
            "author": self.author,
            "title": self.title,
            "kind": self.kind,
        }


# All 55 Swete Septuagint works in First1KGreek (works_catalogue.json), in LXX order.
_LXX_BOOKS: tuple[LxxBook, ...] = (
    # Pentateuch
    LxxBook("Gen", "Genesis", "tlg0527.tlg001", "Pentateuch", ("genesis", "gen", "gn")),
    LxxBook("Exod", "Exodus", "tlg0527.tlg002", "Pentateuch", ("exodus", "exod", "ex")),
    LxxBook("Lev", "Leviticus", "tlg0527.tlg003", "Pentateuch", ("leviticus", "lev", "lv")),
    LxxBook("Num", "Numbers", "tlg0527.tlg004", "Pentateuch", ("numbers", "num", "nm", "numeri")),
    LxxBook("Deut", "Deuteronomy", "tlg0527.tlg005", "Pentateuch", ("deuteronomy", "deut", "dt")),
    # Historical Books
    LxxBook("Josh", "Joshua", "tlg0527.tlg006", "History", ("joshua", "josh", "josue", "jos")),
    LxxBook("Judg", "Judges", "tlg0527.tlg008", "History", ("judges", "judg", "judices", "jdg")),
    LxxBook("Ruth", "Ruth", "tlg0527.tlg010", "History", ("ruth", "ru")),
    LxxBook("1Kgdms", "1 Kingdoms (1 Samuel)", "tlg0527.tlg011", "History", ("1kingdoms", "1kgdms", "1samuel", "1sam", "1reg", "regnorum1")),
    LxxBook("2Kgdms", "2 Kingdoms (2 Samuel)", "tlg0527.tlg012", "History", ("2kingdoms", "2kgdms", "2samuel", "2sam", "2reg", "regnorum2")),
    LxxBook("3Kgdms", "3 Kingdoms (1 Kings)", "tlg0527.tlg013", "History", ("3kingdoms", "3kgdms", "1kings", "1kgs", "3reg", "regnorum3")),
    LxxBook("4Kgdms", "4 Kingdoms (2 Kings)", "tlg0527.tlg014", "History", ("4kingdoms", "4kgdms", "2kings", "2kgs", "4reg", "regnorum4")),
    LxxBook("1Chr", "1 Chronicles (1 Paralipomenon)", "tlg0527.tlg015", "History", ("1chronicles", "1chr", "1par", "1paralipomenon")),
    LxxBook("2Chr", "2 Chronicles (2 Paralipomenon)", "tlg0527.tlg016", "History", ("2chronicles", "2chr", "2par", "2paralipomenon")),
    LxxBook("1Esdr", "1 Esdras", "tlg0527.tlg017", "History", ("1esdras", "1esdr", "esdras1")),
    LxxBook("2Esdr", "2 Esdras (Ezra–Nehemiah)", "tlg0527.tlg018", "History", ("2esdras", "2esdr", "esdras2", "ezra", "nehemiah", "neh")),
    LxxBook("Esth", "Esther", "tlg0527.tlg019", "History", ("esther", "esth", "est")),
    LxxBook("Jdt", "Judith", "tlg0527.tlg020", "Deuterocanonical", ("judith", "jdt")),
    LxxBook("Tob", "Tobit", "tlg0527.tlg021", "Deuterocanonical", ("tobit", "tob", "tobias")),
    LxxBook("1Macc", "1 Maccabees", "tlg0527.tlg023", "Deuterocanonical", ("1maccabees", "1macc", "1mac")),
    LxxBook("2Macc", "2 Maccabees", "tlg0527.tlg024", "Deuterocanonical", ("2maccabees", "2macc", "2mac")),
    LxxBook("3Macc", "3 Maccabees", "tlg0527.tlg025", "Deuterocanonical", ("3maccabees", "3macc", "3mac")),
    LxxBook("4Macc", "4 Maccabees", "tlg0527.tlg026", "Deuterocanonical", ("4maccabees", "4macc", "4mac")),
    # Poetic & Wisdom Books
    LxxBook("Ps", "Psalms", "tlg0527.tlg027", "Wisdom", ("psalms", "psalm", "ps", "pss", "psalmi")),
    LxxBook("Odes", "Odes", "tlg0527.tlg028", "Wisdom", ("odes", "odae", "ode")),
    LxxBook("Prov", "Proverbs", "tlg0527.tlg029", "Wisdom", ("proverbs", "prov", "pr", "proverbia")),
    LxxBook("Song", "Song of Songs (Canticum)", "tlg0527.tlg031", "Wisdom", ("song", "songofsongs", "cant", "canticum", "canticles")),
    LxxBook("Job", "Job", "tlg0527.tlg032", "Wisdom", ("job", "jb")),
    LxxBook("Wis", "Wisdom of Solomon", "tlg0527.tlg033", "Deuterocanonical", ("wisdom", "wisdomofsolomon", "wis", "sapientia")),
    LxxBook("Sir", "Sirach (Ecclesiasticus)", "tlg0527.tlg034", "Deuterocanonical", ("sirach", "sir", "ecclesiasticus", "ecclus", "bensira")),
    LxxBook("PssSol", "Psalms of Solomon", "tlg0527.tlg035", "Deuterocanonical", ("psalmsofsolomon", "psssol", "pssol")),
    # Minor Prophets (The Twelve, in LXX order)
    LxxBook("Hos", "Hosea", "tlg0527.tlg036", "Minor Prophets", ("hosea", "hos", "osee")),
    LxxBook("Amos", "Amos", "tlg0527.tlg037", "Minor Prophets", ("amos", "am")),
    LxxBook("Mic", "Micah", "tlg0527.tlg038", "Minor Prophets", ("micah", "mic", "michaeas")),
    LxxBook("Joel", "Joel", "tlg0527.tlg039", "Minor Prophets", ("joel", "jl")),
    LxxBook("Obad", "Obadiah", "tlg0527.tlg040", "Minor Prophets", ("obadiah", "obad", "ob", "abdias")),
    LxxBook("Jonah", "Jonah", "tlg0527.tlg041", "Minor Prophets", ("jonah", "jon", "jonas")),
    LxxBook("Nah", "Nahum", "tlg0527.tlg042", "Minor Prophets", ("nahum", "nah", "na")),
    LxxBook("Hab", "Habakkuk", "tlg0527.tlg043", "Minor Prophets", ("habakkuk", "hab", "habacuc")),
    LxxBook("Zeph", "Zephaniah", "tlg0527.tlg044", "Minor Prophets", ("zephaniah", "zeph", "zep", "sophonias")),
    LxxBook("Hag", "Haggai", "tlg0527.tlg045", "Minor Prophets", ("haggai", "hag", "hg", "aggaeus")),
    LxxBook("Zech", "Zechariah", "tlg0527.tlg046", "Minor Prophets", ("zechariah", "zech", "zec", "zacharias")),
    LxxBook("Mal", "Malachi", "tlg0527.tlg047", "Minor Prophets", ("malachi", "mal", "malachias")),
    # Major Prophets
    LxxBook("Isa", "Isaiah", "tlg0527.tlg048", "Major Prophets", ("isaiah", "isa", "is", "isaias")),
    LxxBook("Jer", "Jeremiah", "tlg0527.tlg049", "Major Prophets", ("jeremiah", "jer", "jr", "jeremias")),
    LxxBook("Bar", "Baruch", "tlg0527.tlg050", "Deuterocanonical", ("baruch", "bar")),
    LxxBook("Lam", "Lamentations", "tlg0527.tlg051", "Major Prophets", ("lamentations", "lam", "threni")),
    LxxBook("EpJer", "Epistle of Jeremiah", "tlg0527.tlg052", "Deuterocanonical", ("epistleofjeremiah", "epjer", "letterofjeremiah")),
    LxxBook("Ezek", "Ezekiel", "tlg0527.tlg053", "Major Prophets", ("ezekiel", "ezek", "ez", "ezechiel")),
    LxxBook("Sus-OG", "Susanna (Old Greek)", "tlg0527.tlg054", "Deuterocanonical", ("susanna-og", "sus-og", "susannaog")),
    LxxBook("Sus-Th", "Susanna (Theodotion)", "tlg0527.tlg055", "Deuterocanonical", ("susanna", "sus", "susanna-th", "sus-th")),
    LxxBook("Dan-OG", "Daniel (Old Greek)", "tlg0527.tlg056", "Major Prophets", ("daniel-og", "dan-og", "danielog")),
    LxxBook("Dan-Th", "Daniel (Theodotion)", "tlg0527.tlg057", "Major Prophets", ("daniel", "dan", "dn", "daniel-th", "dan-th")),
    LxxBook("Bel-OG", "Bel and the Dragon (Old Greek)", "tlg0527.tlg058", "Deuterocanonical", ("bel-og", "belog")),
    LxxBook("Bel-Th", "Bel and the Dragon (Theodotion)", "tlg0527.tlg059", "Deuterocanonical", ("bel", "belandthedragon", "bel-th")),
)

_LXX_ALIAS: dict[str, LxxBook] = {}
for _b in _LXX_BOOKS:
    for _k in (_b.name, _b.title, _b.work_id, *_b.aliases):
        _norm = _k.strip().lower().replace(" ", "").replace(".", "")
        _LXX_ALIAS.setdefault(_norm, _b)


def lxx_books(*, section: str | None = None) -> list[dict[str, Any]]:
    """List the 55 Septuagint (LXX) books available in the First1KGreek catalogue.

    Optionally filter by ``section`` (``'Pentateuch'``, ``'History'``,
    ``'Wisdom'``, ``'Minor Prophets'``, ``'Major Prophets'``, or
    ``'Deuterocanonical'``). Offline metadata — requires no download."""
    rows = _LXX_BOOKS
    if section is not None:
        want = section.strip().lower()
        rows = tuple(b for b in rows if b.section.lower() == want)
    return [b.to_dict() for b in rows]


def resolve_lxx_book(book: str) -> LxxBook:
    """Resolve a friendly LXX book name, abbreviation, or TLG work ID."""
    key = book.strip().lower().replace(" ", "").replace(".", "")
    hit = _LXX_ALIAS.get(key)
    if hit is not None:
        return hit
    from ...core.resolve import suggest

    choices = [b.name for b in _LXX_BOOKS] + [a for b in _LXX_BOOKS for a in b.aliases]
    close = suggest(book, choices, n=1)
    if close:
        canonical = _LXX_ALIAS.get(close[0].lower().replace(" ", ""), None)
        hint = canonical.name if canonical else close[0]
        raise ValueError(
            f"unknown LXX book {book!r} — did you mean {hint!r}? "
            "(aegean.greek.bible.lxx_books() lists all 55)"
        )
    raise ValueError(
        f"unknown LXX book {book!r}; try 'Gen', 'Exod', 'Ps', 'Isa', 'Wis', 'Sir', '1Macc', 'Dan' "
        "(aegean.greek.bible.lxx_books() lists all 55)"
    )


def psalm_lxx_to_mt(psalm: int) -> tuple[int, ...]:
    """Convert a Septuagint (LXX) Psalm number (1–151) to Masoretic / English Psalm number(s).

    Returns a tuple of corresponding MT Psalm numbers:
    - ``psalm_lxx_to_mt(9)`` -> ``(9, 10)`` (LXX combines MT 9 and 10)
    - ``psalm_lxx_to_mt(22)`` -> ``(23,)`` (The Lord is my shepherd)
    - ``psalm_lxx_to_mt(113)`` -> ``(114, 115)``
    - ``psalm_lxx_to_mt(114)`` -> ``(116,)`` (LXX splits MT 116 into 114–115)
    - ``psalm_lxx_to_mt(151)`` -> ``()`` (LXX-only extra-canonical Psalm 151)
    """
    if not isinstance(psalm, int) or psalm < 1 or psalm > 151:
        raise ValueError(f"LXX Psalm number must be between 1 and 151, got {psalm!r}")
    if psalm <= 8 or 148 <= psalm <= 150:
        return (psalm,)
    if psalm == 9:
        return (9, 10)
    if 10 <= psalm <= 112:
        return (psalm + 1,)
    if psalm == 113:
        return (114, 115)
    if psalm in (114, 115):
        return (116,)
    if 116 <= psalm <= 145:
        return (psalm + 1,)
    if psalm in (146, 147):
        return (147,)
    return ()  # Psalm 151 is LXX-only


def psalm_mt_to_lxx(psalm: int) -> tuple[int, ...]:
    """Convert a Masoretic / English Psalm number (1–150) to Septuagint (LXX) Psalm number(s).

    Returns a tuple of corresponding LXX Psalm numbers:
    - ``psalm_mt_to_lxx(23)`` -> ``(22,)``
    - ``psalm_mt_to_lxx(10)`` -> ``(9,)``
    - ``psalm_mt_to_lxx(116)`` -> ``(114, 115)``
    - ``psalm_mt_to_lxx(147)`` -> ``(146, 147)``
    """
    if not isinstance(psalm, int) or psalm < 1 or psalm > 150:
        raise ValueError(f"Masoretic Psalm number must be between 1 and 150, got {psalm!r}")
    if psalm <= 8 or 148 <= psalm <= 150:
        return (psalm,)
    if psalm in (9, 10):
        return (9,)
    if 11 <= psalm <= 113:
        return (psalm - 1,)
    if psalm in (114, 115):
        return (113,)
    if psalm == 116:
        return (114, 115)
    if 117 <= psalm <= 146:
        return (psalm - 1,)
    return (146, 147)  # MT 147


def convert_psalm(psalm: int, *, system: str = "mt") -> dict[str, Any]:
    """Convert a Psalm number between Masoretic (``'mt'``) and Septuagint (``'lxx'``) numbering.

    Returns a dictionary containing ``mt``, ``lxx``, ``note``, and ``lxx_work_id``.
    """
    src = system.strip().lower()
    if src == "mt":
        lxx = list(psalm_mt_to_lxx(psalm))
        mt = [psalm]
    elif src == "lxx":
        mt = list(psalm_lxx_to_mt(psalm))
        lxx = [psalm]
    else:
        raise ValueError(f"system must be 'mt' or 'lxx', got {system!r}")
    note = ""
    if lxx == [151]:
        note = "Psalm 151 is extra-canonical in the Masoretic Text (preserved in LXX and 11QPsᵃ)."
    elif lxx == [9] or mt == [9, 10]:
        note = "LXX Psalm 9 combines Masoretic Psalms 9 and 10."
    elif lxx == [113] or mt == [114, 115]:
        note = "LXX Psalm 113 combines Masoretic Psalms 114 and 115."
    elif lxx == [114, 115] or mt == [116]:
        note = "LXX splits Masoretic Psalm 116 into Psalms 114 and 115."
    elif lxx == [146, 147] or mt == [147]:
        note = "LXX splits Masoretic Psalm 147 into Psalms 146 and 147."
    return {
        "system": src,
        "input": psalm,
        "mt": mt,
        "lxx": lxx,
        "note": note,
        "lxx_work_id": "tlg0527.tlg027",
    }


# All 30 Greek NT Catenae volumes (tlg4102.*) + key Origen biblical commentaries (tlg2042.*).
_COMMENTARIES: tuple[CommentaryWork, ...] = (
    # NT Catenae (Cramer edition via First1KGreek)
    CommentaryWork("tlg4102.tlg001", "Matt", "Catenae (NT)", "Catena in Matthaeum (Catena Integra)", "catena"),
    CommentaryWork("tlg4102.tlg003", "Matt", "Catenae (NT)", "Supplementum ad commentarium Chrysostomi in Matthaeum", "catena"),
    CommentaryWork("tlg4102.tlg002", "Mark", "Catenae (NT)", "Catena in Marcum (Recensio II)", "catena"),
    CommentaryWork("tlg4102.tlg004", "Luke", "Catenae (NT)", "Catena in Lucam (Typus B)", "catena"),
    CommentaryWork("tlg4102.tlg006", "Luke", "Catenae (NT)", "Supplementum ad catenam in Lucam", "catena"),
    CommentaryWork("tlg4102.tlg005", "John", "Catenae (NT)", "Catena in Joannem (Catena Integra)", "catena"),
    CommentaryWork("tlg4102.tlg007", "John", "Catenae (NT)", "Supplementum ad catenam in Joannem", "catena"),
    CommentaryWork("tlg4102.tlg008", "Acts", "Catenae (NT)", "Catena in Acta (Catena Andreae)", "catena"),
    CommentaryWork("tlg4102.tlg010", "Rom", "Catenae (NT)", "Catena in Epistulam ad Romanos (Typus Vaticanus)", "catena"),
    CommentaryWork("tlg4102.tlg011", "Rom", "Catenae (NT)", "Catena in Epistulam ad Romanos (Typus Monacensis)", "catena"),
    CommentaryWork("tlg4102.tlg012", "1Cor", "Catenae (NT)", "Catena in 1 Corinthios (Typus Vaticanus)", "catena"),
    CommentaryWork("tlg4102.tlg013", "2Cor", "Catenae (NT)", "Catena in 2 Corinthios (Pseudo-Oecumenius)", "catena"),
    CommentaryWork("tlg4102.tlg019", "Gal", "Catenae (NT)", "Catena in Galatas (Typus Parisinus)", "catena"),
    CommentaryWork("tlg4102.tlg020", "Eph", "Catenae (NT)", "Catena in Ephesios (Typus Parisinus)", "catena"),
    CommentaryWork("tlg4102.tlg021", "Phil", "Catenae (NT)", "Catena in Philippenses (Typus Parisinus)", "catena"),
    CommentaryWork("tlg4102.tlg022", "Col", "Catenae (NT)", "Catena in Colossenses (Typus Parisinus)", "catena"),
    CommentaryWork("tlg4102.tlg023", "1Thess", "Catenae (NT)", "Catena in 1 Thessalonicenses (Typus Parisinus)", "catena"),
    CommentaryWork("tlg4102.tlg024", "2Thess", "Catenae (NT)", "Catena in 2 Thessalonicenses (Typus Parisinus)", "catena"),
    CommentaryWork("tlg4102.tlg034", "1Tim", "Catenae (NT)", "Catena in 1 Timotheum (Cod. Coislin. 204)", "catena"),
    CommentaryWork("tlg4102.tlg035", "2Tim", "Catenae (NT)", "Catena in 2 Timotheum (Cod. Coislin. 204)", "catena"),
    CommentaryWork("tlg4102.tlg036", "Titus", "Catenae (NT)", "Catena in Titum (Cod. Coislin. 204)", "catena"),
    CommentaryWork("tlg4102.tlg037", "Phlm", "Catenae (NT)", "Catena in Philemonem (Cod. Coislin. 204)", "catena"),
    CommentaryWork("tlg4102.tlg038", "Heb", "Catenae (NT)", "Catena in Hebraeos (Cod. Coislin. 204)", "catena"),
    CommentaryWork("tlg4102.tlg040", "Jas", "Catenae (NT)", "Catena in Epistulam Jacobi (Catena Andreae)", "catena"),
    CommentaryWork("tlg4102.tlg041", "1Pet", "Catenae (NT)", "Catena in 1 Petri (Catena Andreae)", "catena"),
    CommentaryWork("tlg4102.tlg042", "2Pet", "Catenae (NT)", "Catena in 2 Petri (Catena Andreae)", "catena"),
    CommentaryWork("tlg4102.tlg043", "1John", "Catenae (NT)", "Catena in 1 Joannis (Catena Andreae)", "catena"),
    CommentaryWork("tlg4102.tlg044", "2John", "Catenae (NT)", "Catena in 2 Joannis (Catena Andreae)", "catena"),
    CommentaryWork("tlg4102.tlg045", "3John", "Catenae (NT)", "Catena in 3 Joannis (Catena Andreae)", "catena"),
    CommentaryWork("tlg4102.tlg046", "Jude", "Catenae (NT)", "Catena in Epistulam Judae (Catena Andreae)", "catena"),
    # Origen's Greek Biblical Commentaries & Homilies (First1KGreek)
    CommentaryWork("tlg2042.tlg029", "Matt", "Origen", "Commentarium in Evangelium Matthaei (Books 10–11)", "origen"),
    CommentaryWork("tlg2042.tlg030", "Matt", "Origen", "Commentarium in Evangelium Matthaei (Books 12–17)", "origen"),
    CommentaryWork("tlg2042.tlg077", "Matt", "Origen", "Scholia in Matthaeum", "origen"),
    CommentaryWork("tlg2042.tlg016", "Luke", "Origen", "Homiliae in Lucam", "origen"),
    CommentaryWork("tlg2042.tlg017", "Luke", "Origen", "Fragmenta in Lucam (in Catenis)", "origen"),
    CommentaryWork("tlg2042.tlg078", "Luke", "Origen", "Scholia in Lucam", "origen"),
    CommentaryWork("tlg2042.tlg005", "John", "Origen", "Commentarii in Evangelium Joannis (Books 1–13)", "origen"),
    CommentaryWork("tlg2042.tlg079", "John", "Origen", "Commentarii in Evangelium Joannis (Books 19, 20, 28, 32)", "origen"),
    CommentaryWork("tlg2042.tlg006", "John", "Origen", "Fragmenta in Evangelium Joannis (in Catenis)", "origen"),
    CommentaryWork("tlg2042.tlg048", "Gen", "Origen", "Selecta in Genesim", "origen"),
    CommentaryWork("tlg2042.tlg050", "Exod", "Origen", "Selecta in Exodum", "origen"),
    CommentaryWork("tlg2042.tlg051", "Lev", "Origen", "Selecta in Leviticum", "origen"),
    CommentaryWork("tlg2042.tlg052", "Num", "Origen", "Selecta in Numeros", "origen"),
    CommentaryWork("tlg2042.tlg053", "Deut", "Origen", "Selecta in Deuteronomium", "origen"),
    CommentaryWork("tlg2042.tlg044", "Ps", "Origen", "Fragmenta in Psalmos 1–150 [Dub.]", "origen"),
    CommentaryWork("tlg2042.tlg009", "Jer", "Origen", "Homiliae in Jeremiam (1–11)", "origen"),
    CommentaryWork("tlg2042.tlg021", "Jer", "Origen", "Homiliae in Jeremiam (12–20)", "origen"),
    CommentaryWork("tlg2042.tlg061", "Ezek", "Origen", "Fragmenta ex commentariis in Ezechielem", "origen"),
)


def _normalize_commentary_book(book: str) -> str:
    """Resolve an NT or LXX book name to its canonical key in ``_COMMENTARIES``."""
    try:
        return _resolve_nt_book(book)
    except ValueError:
        pass
    try:
        return resolve_lxx_book(book).name
    except ValueError:
        pass
    raise ValueError(
        f"unknown biblical book {book!r} for patristic commentaries; "
        "try 'John', 'Matt', 'Rom', 'Gen', 'Ps', 'Jer' "
        "(aegean.greek.bible.patristic_commentaries() lists all 48)"
    )


def patristic_commentaries(
    book: str | None = None,
    *,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    """List Greek patristic biblical commentaries available in First1KGreek.

    Includes all 30 Greek New Testament *Catenae* volumes (``tlg4102.*``,
    covering Matthew–Jude) and 18 major Origen biblical commentaries, homilies,
    and scholia (``tlg2042.*``). Filter by ``book`` (e.g. ``'John'``, ``'Rom'``,
    ``'Gen'``) and/or ``kind`` (``'catena'`` or ``'origen'``). Pure metadata —
    works offline."""
    rows = _COMMENTARIES
    if book is not None:
        canon = _normalize_commentary_book(book)
        rows = tuple(c for c in rows if c.book == canon)
    if kind is not None:
        want = kind.strip().lower()
        if want not in ("catena", "origen"):
            raise ValueError(f"unknown commentary kind {kind!r}; expected 'catena' or 'origen'")
        rows = tuple(c for c in rows if c.kind == want)
    return [c.to_dict() for c in rows]


# Metadata for the 5 supported Greek New Testament editions.
NT_EDITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "nestle1904",
        "name": "Nestle 1904 Greek New Testament",
        "editor": "Eberhard Nestle (digital text Diego Santos; morph Ulrik Sandborg-Petersen)",
        "license": "CC0-1.0 (morphology, lemmas, Strong's); base text public domain",
        "asset": "nt-corpus",
        "annotated": True,
        "offline_sample": "John 1, Philemon 1",
    },
    {
        "id": "sblgnt",
        "name": "SBL Greek New Testament (2010)",
        "editor": "Michael W. Holmes (SBL / Logos)",
        "license": "CC BY 4.0 (SBLGNT text); CC BY-SA 3.0 (MorphGNT)",
        "asset": "nt-editions",
        "annotated": False,
        "offline_sample": None,
    },
    {
        "id": "srgnt",
        "name": "Statistical Restoration Greek New Testament",
        "editor": "Alan Bunning (Center for New Testament Restoration)",
        "license": "CC BY 4.0",
        "asset": "nt-editions",
        "annotated": False,
        "offline_sample": None,
    },
    {
        "id": "byz",
        "name": "Robinson–Pierpont Byzantine Majority Textform",
        "editor": "Maurice A. Robinson & William G. Pierpont",
        "license": "Public Domain",
        "asset": "nt-editions",
        "annotated": False,
        "offline_sample": None,
    },
    {
        "id": "tr",
        "name": "Textus Receptus (King James Greek Underlying Text)",
        "editor": "Center for New Testament Restoration (KJTR)",
        "license": "CC BY 4.0",
        "asset": "nt-editions",
        "annotated": False,
        "offline_sample": None,
    },
)

_EDITION_ALIASES: dict[str, str] = {
    "nestle": "nestle1904",
    "nestle1904": "nestle1904",
    "n1904": "nestle1904",
    "sbl": "sblgnt",
    "sblgnt": "sblgnt",
    "sr": "srgnt",
    "srgnt": "srgnt",
    "byz": "byz",
    "byzantine": "byz",
    "rp": "byz",
    "majority": "byz",
    "tr": "tr",
    "kjtr": "tr",
    "textusreceptus": "tr",
}


def resolve_edition(edition: str) -> str:
    """Resolve an edition name or alias to its canonical id."""
    key = edition.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    hit = _EDITION_ALIASES.get(key)
    if hit is None:
        valid = ", ".join(e["id"] for e in NT_EDITIONS)
        raise ValueError(f"unknown Greek NT edition {edition!r}; valid editions: {valid}")
    return hit


# Metadata for the 13 early Greek NT manuscript witnesses in nt-witnesses.
WITNESS_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "siglum": "01", "alias": "ℵ", "name": "Codex Sinaiticus", "century": "4th c. CE",
        "kind": "uncial", "text_type": "Alexandrian (Western in John 1:1–8:38)",
        "aliases": ("01", "א", "ℵ", "aleph", "sinaiticus", "codexsinaiticus"),
    },
    {
        "siglum": "02", "alias": "A", "name": "Codex Alexandrinus", "century": "5th c. CE",
        "kind": "uncial", "text_type": "Byzantine in Gospels; Alexandrian in Acts–Revelation",
        "aliases": ("02", "a", "alexandrinus", "codexalexandrinus"),
    },
    {
        "siglum": "03", "alias": "B", "name": "Codex Vaticanus", "century": "4th c. CE",
        "kind": "uncial", "text_type": "Alexandrian",
        "aliases": ("03", "b", "vaticanus", "codexvaticanus"),
    },
    {
        "siglum": "04", "alias": "C", "name": "Codex Ephraemi Rescriptus", "century": "5th c. CE",
        "kind": "uncial", "text_type": "Mixed / Alexandrian–Byzantine palimpsest",
        "aliases": ("04", "c", "ephraemi", "codexephraemi"),
    },
    {
        "siglum": "05", "alias": "D", "name": "Codex Bezae Cantabrigiensis", "century": "5th c. CE",
        "kind": "uncial", "text_type": "Western (Greek–Latin bilingual)",
        "aliases": ("05", "d", "bezae", "codexbezae"),
    },
    {
        "siglum": "032", "alias": "W", "name": "Codex Washingtonianus (Freer Gospels)", "century": "4th/5th c. CE",
        "kind": "uncial", "text_type": "Block-mixed (Alexandrian, Western, Byzantine, Caesarean)",
        "aliases": ("032", "w", "washingtonianus", "freer", "codexwashingtonianus"),
    },
    {
        "siglum": "P45", "alias": "𝔓45", "name": "Papyrus 45 (Chester Beatty I)", "century": "3rd c. CE",
        "kind": "papyrus", "text_type": "Early Alexandrian / Caesarean-leaning (Gospels & Acts)",
        "aliases": ("p45", "𝔓45", "chesterbeatty1"),
    },
    {
        "siglum": "P46", "alias": "𝔓46", "name": "Papyrus 46 (Chester Beatty II)", "century": "c. 200 CE",
        "kind": "papyrus", "text_type": "Early Alexandrian (Pauline Epistles & Hebrews)",
        "aliases": ("p46", "𝔓46", "chesterbeatty2"),
    },
    {
        "siglum": "P47", "alias": "𝔓47", "name": "Papyrus 47 (Chester Beatty III)", "century": "3rd c. CE",
        "kind": "papyrus", "text_type": "Early Alexandrian (Revelation 9–17)",
        "aliases": ("p47", "𝔓47", "chesterbeatty3"),
    },
    {
        "siglum": "P52", "alias": "𝔓52", "name": "Papyrus 52 (Rylands Library Papyrus P52)", "century": "2nd c. CE",
        "kind": "papyrus", "text_type": "Earliest extant NT fragment (John 18:31–33, 37–38)",
        "aliases": ("p52", "𝔓52", "rylands"),
    },
    {
        "siglum": "P66", "alias": "𝔓66", "name": "Papyrus 66 (Bodmer II)", "century": "c. 200 CE",
        "kind": "papyrus", "text_type": "Early Alexandrian with Western readings (Gospel of John)",
        "aliases": ("p66", "𝔓66", "bodmer2"),
    },
    {
        "siglum": "P72", "alias": "𝔓72", "name": "Papyrus 72 (Bodmer VII–VIII)", "century": "3rd/4th c. CE",
        "kind": "papyrus", "text_type": "Early Alexandrian (1–2 Peter & Jude)",
        "aliases": ("p72", "𝔓72", "bodmer7"),
    },
    {
        "siglum": "P75", "alias": "𝔓75", "name": "Papyrus 75 (Bodmer XIV–XV)", "century": "early 3rd c. CE",
        "kind": "papyrus", "text_type": "Strict Alexandrian, close to Codex Vaticanus (Luke & John)",
        "aliases": ("p75", "𝔓75", "bodmer14"),
    },
)

_WITNESS_ALIASES: dict[str, str] = {
    alias: spec["siglum"]
    for spec in WITNESS_CATALOG
    for alias in spec["aliases"]
}


def resolve_witness(siglum: str) -> str:
    """Resolve a Gregory–Aland siglum, symbol (ℵ, B, 𝔓52), or codex name."""
    key = siglum.strip().lower().replace(" ", "").replace("-", "")
    hit = _WITNESS_ALIASES.get(key)
    if hit is None:
        valid = ", ".join(w["siglum"] for w in WITNESS_CATALOG)
        raise ValueError(
            f"unknown early NT witness {siglum!r}; valid witnesses: {valid} "
            "(also accepts ℵ/Sinaiticus, B/Vaticanus, A/Alexandrinus, D/Bezae, P52, …)"
        )
    return hit
