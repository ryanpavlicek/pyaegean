"""Heuristic tablet-structure classification by content shape.

A faithful port of the ``heuristicKey`` classifier behind the workbench's
Tablet Structure module (``src/modules/TabletStructure.tsx``): label each
inscription accounting / libation / list / text / other from the shape of its
token stream. The surrounding React UI (filtering, CSV export, manual
re-classification) is intentionally not ported.

**Exploratory.** These are content-shape heuristics on an undeciphered script,
not genre attributions — a researcher is expected to override individual calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..core.model import Document

# Known libation-formula words (the "Libation" signal). Matched against exact
# token text, so every entry must be spelled as the corpus writes it
# (subscripts included). The a-di-ki-te family is listed as the corpus
# actually attests it: the earlier entry "A-DI-KI-TE-TE-DU" matched zero
# bundled tokens (it is a fragment of Younger's restored reading of the
# damaged word on PK Za 11, A-DI-KI-TE-TE-DU-PU-RE, not a word any
# inscription carries). Attested forms, per Younger's readings: A-DI-KI-TE
# (PK Za 12), A-DI-KI-TE-TE (PK Za 11), and the ja-prefixed
# JA-DI-KI-TE-TE-DU-PU₂-RE (PK Za 15) / JA-DI-KI-TE-TE-*307-PU₂-RE (PK Za 8).
# Whether these are variants of one word (often connected to Mt. Dikte) is
# contested; treat the grouping as exploratory.
LIBATION_WORDS = frozenset(
    {
        "A-TA-I-*301-WA-JA",
        "JA-SA-SA-RA-ME",
        "A-DI-KI-TE",
        "A-DI-KI-TE-TE",
        "JA-DI-KI-TE-TE-DU-PU₂-RE",
        "JA-DI-KI-TE-TE-*307-PU₂-RE",
    }
)


@dataclass(frozen=True, slots=True)
class StructureCategory:
    """A heuristic tablet-structure category (e.g. accounting/libation/list): key, label, description."""

    key: str
    label: str
    description: str


CATEGORIES: tuple[StructureCategory, ...] = (
    StructureCategory(
        "accounting", "Accounting", "Contains numerals and/or KU-RO (total markers)"
    ),
    StructureCategory(
        "libation", "Libation", "Contains known libation formula words"
    ),
    StructureCategory("list", "Lists", "Multiple separator marks, no numerals"),
    StructureCategory("text", "Text / Other", "Extended text without numerals"),
    StructureCategory("other", "Unclassified", "Short or ambiguous inscriptions"),
)

_SEPARATOR = "\U00010101"  # 𐄁
_LEADING_DIGIT = re.compile(r"^[0-9]")


def classify_structure(document: Document) -> str:
    """The heuristic category key for one inscription, from its content shape.

    Mirrors the workbench precedence exactly: a KU-RO total marker (or numerals
    with several multi-sign words) ⇒ accounting; otherwise a libation formula ⇒
    libation; otherwise many separators and no numerals ⇒ list; otherwise an
    extended hyphenated text with no numerals ⇒ text; else other.
    """
    words = [t.text for t in document.tokens]
    has_nums = any(_LEADING_DIGIT.match(w) for w in words)
    has_kuro = "KU-RO" in words
    has_lib = any(w in LIBATION_WORDS for w in words)
    multi = sum(1 for w in words if "-" in w)
    sep = sum(1 for w in words if w == _SEPARATOR)
    if has_kuro or (has_nums and multi > 2):
        return "accounting"
    if has_lib:
        return "libation"
    if sep > 3 and not has_nums:
        return "list"
    if multi > 4 and not has_nums:
        return "text"
    return "other"


def classify_corpus(corpus: object) -> dict[str, list[str]]:
    """Classify every document in a corpus, returning ``{category_key:
    [doc_id, ...]}`` with every category present (empty lists included) and
    documents in corpus order."""
    buckets: dict[str, list[str]] = {c.key: [] for c in CATEGORIES}
    for doc in corpus:  # type: ignore[attr-defined]
        buckets[classify_structure(doc)].append(doc.id)
    return buckets
