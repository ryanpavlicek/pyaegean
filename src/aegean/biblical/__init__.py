"""Biblical & Koine Greek specialist toolkit (`aegean.biblical`).

Provides an integrated, scholarly workflow for Koine and Biblical Greek across
five pillars — zero extra dependencies, lazy-loaded so ``import aegean`` pays
no startup cost, and usable offline with seamless upgrades to SHA-256-pinned
fetch-on-demand release assets:

1. **Multi-edition Greek New Testament** (:func:`load_nt`, :func:`compare_editions`,
   :func:`nt_editions`, :func:`nt_books`): Nestle 1904 (gold lemma, Robinson
   morphology, Strong's, UD UPOS; John 1 & Philemon 1 bundled offline),
   SBLGNT, Statistical Restoration GNT, Robinson–Pierpont Byzantine Majority
   Text, and Textus Receptus, with word-level textual variant diffing.
2. **Early Greek NT Manuscript Witnesses** (:func:`witnesses`, :func:`load_witness`,
   :func:`compare_witnesses`, :func:`parse_mes`, :func:`expand_nomen_sacrum`):
   13 landmark 2nd–5th c. CE uncials and papyri (Sinaiticus ``01``/ℵ,
   Alexandrinus ``02``/A, Vaticanus ``03``/B, Ephraemi ``04``/C, Bezae
   ``05``/D, Washingtonianus ``032``/W, ``P45``, ``P46``, ``P47``, ``P52``,
   ``P66``, ``P72``, ``P75``) with CNTR MES diplomatic markup and *nomina sacra*
   expansion.
3. **Strong's & Extended Strong's Greek Lexicon** (:func:`strongs_entry`,
   :func:`strongs_roots`, :func:`search_strongs`, :func:`use_strongs`): works
   immediately offline via bundled Dodson (CC0) and upgrades to 11,142 entries
   covering NT + LXX + Apocrypha + Apostolic Fathers with etymological root
   trees and Hebrew equivalents.
4. **Septuagint (LXX) & Psalm Numbering** (:func:`lxx_books`, :func:`load_lxx`,
   :func:`psalm_lxx_to_mt`, :func:`psalm_mt_to_lxx`): friendly book-name access
   to all 55 Swete Septuagint books in First1KGreek plus exact LXX ↔ Masoretic
   Psalm numbering conversion.
5. **Greek Patristic Commentaries & Word Studies** (:func:`patristic_commentaries`,
   :func:`load_commentary`, :func:`word_study`, :func:`search_bible`): friendly
   book-name access to all 30 Greek NT *Catenae* volumes and 18 Origen biblical
   commentaries, plus unified word-study reports and concordance search.
"""

from __future__ import annotations

from ..scripts.greek.nt import nt_books
from ._catalogs import (
    CommentaryWork,
    LxxBook,
    convert_psalm,
    lxx_books,
    patristic_commentaries,
    psalm_lxx_to_mt,
    psalm_mt_to_lxx,
    resolve_edition,
    resolve_lxx_book,
    resolve_witness,
)
from ._editions import (
    EditionComparison,
    VerseComparison,
    WordVariant,
    compare_editions,
    load_nt,
    nt_editions,
)
from ._lxx import (
    CommentaryExcerpt,
    LxxHit,
    commentary_excerpt,
    load_lxx,
    lxx_loaded,
    search_lxx,
)
from ._mes import (
    NOMINA_SACRA,
    WitnessReading,
    expand_nomen_sacrum,
    expand_nomina_sacra,
    parse_mes,
)
from ._strongs import (
    StrongsEntry,
    normalize_strongs_id,
    search_strongs,
    strongs_entry,
    strongs_loaded,
    strongs_roots,
    use_strongs,
)
from ._study import (
    ConcordanceHit,
    WordStudy,
    load_commentary,
    search_bible,
    word_study,
)
from ._witnesses import (
    WitnessVerseComparison,
    WitnessVerseEntry,
    compare_witnesses,
    load_witness,
    witnesses,
)

__all__ = [
    # Catalogs & reference helpers
    "CommentaryWork",
    "LxxBook",
    "nt_books",
    "nt_editions",
    "lxx_books",
    "patristic_commentaries",
    "psalm_lxx_to_mt",
    "psalm_mt_to_lxx",
    "convert_psalm",
    "resolve_edition",
    "resolve_lxx_book",
    "resolve_witness",
    # Multi-edition Greek NT
    "EditionComparison",
    "VerseComparison",
    "WordVariant",
    "load_nt",
    "compare_editions",
    # Early Greek NT manuscript witnesses & MES
    "NOMINA_SACRA",
    "WitnessReading",
    "WitnessVerseEntry",
    "WitnessVerseComparison",
    "witnesses",
    "load_witness",
    "compare_witnesses",
    "parse_mes",
    "expand_nomen_sacrum",
    "expand_nomina_sacra",
    # Strong's & Extended Strong's lexicon
    "StrongsEntry",
    "normalize_strongs_id",
    "use_strongs",
    "strongs_loaded",
    "strongs_entry",
    "strongs_roots",
    "search_strongs",
    # Word study, concordance, LXX, & commentaries
    "ConcordanceHit",
    "WordStudy",
    "LxxHit",
    "CommentaryExcerpt",
    "word_study",
    "search_bible",
    "load_lxx",
    "lxx_loaded",
    "search_lxx",
    "load_commentary",
    "commentary_excerpt",
]
