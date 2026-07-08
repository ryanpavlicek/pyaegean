"""Load the EDH Greek corpus (opt-in, fetched).

EDH — Epigraphic Database Heidelberg (Heidelberg Academy of Sciences and Humanities;
github.com/epigraphic-database-heidelberg/data). The data dump is CC BY-SA 4.0 and frozen (the
project closed in 2021), so pyaegean mirrors the Greek subset as the ``edh-corpus`` release asset,
both to add a distinct epigraphic database and to preserve a corpus that will not be republished.
EDH is overwhelmingly Latin; this is the pure Ancient-Greek subset (the edition marked
``xml:lang="grc"``), decoded into a compact pyaegean ``Corpus`` JSON by
``scripts/build_edh_corpus.py``. The Greek is Imperial-period Koine — dedications, boundary and
funerary texts, largely onomastic — and each document keeps its Trismegistos id (``meta.notes``) for
cross-referencing. ``aegean.load("edh")`` fetches it to the cache on first use, then loads offline.
Cite EDH (Heidelberg Academy of Sciences and Humanities) in academic work.
"""

from __future__ import annotations

from typing import Any


def load_edh() -> Any:
    """Load the EDH Ancient-Greek inscriptions as a `Corpus` (opt-in, fetched, CC BY-SA).

    One `Document` per inscription (id ``HDnnnnnn``), the Greek reading tokenised into words, with
    the ancient place (``meta.site``), date (``meta.period``), modern find-place (``meta.findspot``),
    and the Trismegistos id + inscription type in ``meta.notes``. The attribution travels with the
    corpus provenance; cite EDH (Heidelberg Academy of Sciences and Humanities)."""
    from ...core.corpus import Corpus
    from ...data import fetch

    path = fetch("edh-corpus")
    return Corpus.from_json(path)


from ...core.corpus import register_loader  # noqa: E402

# loadable by name: aegean.load("edh") — fetches the corpus to the cache on first use
register_loader("edh", load_edh)
