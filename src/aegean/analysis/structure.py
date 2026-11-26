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

from dataclasses import dataclass
from typing import Any

from ..core.model import Document
from ..core.numerals import parse_value

# Known libation-formula words (the "Libation" signal), synced with
# linearaworkbench's shared src/data/libation.ts (14 attested forms).
# Matched against exact token text, so every entry must be spelled as the
# corpus writes it (subscripts included). The a-di-ki-te family is listed as
# the corpus actually attests it (PK Za 8/11/12/15).
LIBATION_WORDS = frozenset(
    {
        "A-TA-I-*301-WA-JA",
        "JA-SA-SA-RA-ME",
        "A-DI-KI-TE",
        "A-DI-KI-TE-TE",
        "JA-DI-KI-TE-TE-DU-PU₂-RE",
        "JA-DI-KI-TE-TE-*307-PU₂-RE",
        "TA-NA-TE",
        "I-DA-MA-TE",
        "SI-RU-TE",
        "DI-KI-SE",
        "A-SA-SA-RA-ME",
        "PI-TE-RI",
        "U-NA-KA-NA-SI",
        "I-PI-NA-MA",
    }
)

_TOTAL_MARKERS = frozenset({"KU-RO", "KU-RA", "PO-TO-KU-RO"})


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


def classify_structure(document: Document) -> str:
    """The heuristic category key for one inscription, from its content shape.

    Mirrors the workbench precedence (`heuristicCategory` in `corpusExport.ts`)
    exactly: a total marker (`KU-RO`, `KU-RA`, `PO-TO-KU-RO`) or numerals/fractions
    with more than two multi-sign words ⇒ accounting; otherwise a libation formula ⇒
    libation; otherwise more than three separators and no numerals ⇒ list; otherwise
    more than four multi-sign words with no numerals ⇒ text; else other.
    """
    words = [t.text for t in document.tokens]
    has_nums = any(parse_value(w) is not None for w in words)
    has_total = any(w in _TOTAL_MARKERS for w in words)
    has_lib = any(w in LIBATION_WORDS for w in words)
    multi = sum(1 for w in words if "-" in w)
    sep = sum(1 for w in words if w == _SEPARATOR)
    if has_total or (has_nums and multi > 2):
        return "accounting"
    if has_lib:
        return "libation"
    if sep > 3 and not has_nums:
        return "list"
    if multi > 4 and not has_nums:
        return "text"
    return "other"


def _documents(corpus: Any) -> list[Document]:
    """Coerce a corpus, a query's results, or an iterable of Documents to a list.

    `Corpus.query` returns `aegean.analysis.QueryResults`, whose matched documents are
    its ``inscriptions``, so the structure of a queried subset can be classified
    directly. Anything else that yields documents (a `Corpus`, a plain list) is taken as
    it comes; anything that does not raises a ``TypeError`` naming what arrived."""
    docs = getattr(corpus, "inscriptions", None)
    if docs is None:
        docs = getattr(corpus, "documents", corpus)
    try:
        out = list(docs)
    except TypeError:
        raise TypeError(
            f"expected a corpus or documents, got {type(corpus).__name__}"
        ) from None
    if out and not isinstance(out[0], Document):
        raise TypeError(f"expected a corpus or documents, got {type(out[0]).__name__}")
    return out


def classify_corpus(corpus: Any) -> dict[str, list[str]]:
    """Classify every document in a corpus, returning ``{category_key:
    [doc_id, ...]}`` with every category present (empty lists included) and
    documents in corpus order.

    Takes a `Corpus`, the results of a `Corpus.query`, or a plain list of documents;
    the documents classified are those of whatever was handed in, in its order."""
    buckets: dict[str, list[str]] = {c.key: [] for c in CATEGORIES}
    for doc in _documents(corpus):
        buckets[classify_structure(doc)].append(doc.id)
    return buckets
