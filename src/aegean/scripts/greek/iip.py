"""Load the IIP (Inscriptions of Israel/Palestine) Greek corpus (opt-in, fetched).

IIP (Michael L. Satlow, ed., Brown University; https://www.inscriptionsisraelpalestine.org,
github.com/Brown-University-Library/iip-texts, **CC BY-NC 4.0**) is a multilingual EpiDoc corpus.
The ``iip-corpus`` release asset is the ~2,113 **primary-Greek** inscriptions, their Greek reading
extracted from each primary edition with the find-place and coordinates, decoded into a compact
pyaegean ``Corpus`` JSON by ``scripts/build_iip_corpus.py``. ``aegean.load("iip")`` fetches it to
the cache on first use, then loads offline. CC BY-NC permits the redistribution (the NonCommercial
obligation passes to you); the asset is fetched, never bundled. Adds regional and late-antique
Greek epigraphy (much of it in majuscule, as inscribed). Cite IIP in academic work.
"""

from __future__ import annotations

from typing import Any


def load_iip() -> Any:
    """Load the IIP Greek inscriptions as a `Corpus` (opt-in, fetched, CC BY-NC 4.0).

    One `Document` per inscription, the Greek reading tokenised into words, with the find-place
    (``meta.site``) and coordinates (``meta.findspot``). The CC BY-NC attribution travels with the
    corpus provenance; cite IIP (M. L. Satlow, Brown University; see ``NOTICE``)."""
    from ...core.corpus import Corpus
    from ...data import fetch

    path = fetch("iip-corpus")
    return Corpus.from_json(path)


from ...core.corpus import register_loader  # noqa: E402

# loadable by name: aegean.load("iip") — fetches the corpus to the cache on first use
register_loader("iip", load_iip)
