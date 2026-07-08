"""Load the I.Sicily Greek-inscriptions corpus (opt-in, fetched).

I.Sicily (https://github.com/ISicily/ISicily, CC BY 4.0) is a corpus of ~5,120 EpiDoc TEI
inscriptions of ancient Sicily in many languages. The ``isicily-corpus`` release asset is the
~2,855 **primary-Greek** texts, their running Greek reading extracted from the primary edition
(line breaks resolved, abbreviations expanded, restored/uncertain letters kept, lost gaps and
symbols dropped) with the find-place, date, and coordinates, decoded into a compact pyaegean
``Corpus`` JSON by ``scripts/build_isicily_corpus.py``. ``aegean.load("isicily")`` fetches it to
the cache on first use (a few MB, sha256-pinned), then loads offline. CC BY 4.0 permits the
redistribution; attribution to I.Sicily is recorded in the corpus provenance (and ``NOTICE``).

This adds **epigraphic** Greek — real inscriptions on stone — alongside pyaegean's literary
(Perseus) and New Testament Greek. Cite I.Sicily in academic work (J. Prag et al., Oxford).
"""

from __future__ import annotations

from typing import Any


def load_isicily() -> Any:
    """Load the I.Sicily Greek inscriptions as a `Corpus` (opt-in, fetched, CC BY 4.0).

    One `Document` per inscription (id ``ISicNNNNNN``), carrying the Greek reading text tokenised
    into words, with the ancient find-place (``meta.site``, e.g. ``"Syracusae"``), the date
    (``meta.period``), and the coordinates (``meta.findspot``) in the metadata. The provenance and
    CC BY licence travel with the corpus; see ``NOTICE`` for the citation."""
    from ...core.corpus import Corpus
    from ...data import fetch

    path = fetch("isicily-corpus")
    return Corpus.from_json(path)


from ...core.corpus import register_loader  # noqa: E402

# loadable by name: aegean.load("isicily") — fetches the corpus to the cache on first use
register_loader("isicily", load_isicily)
