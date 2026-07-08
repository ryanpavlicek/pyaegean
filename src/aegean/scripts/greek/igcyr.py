"""Load the IGCyr/GVCyr (Greek inscriptions of Cyrenaica) corpus (opt-in, fetched).

IGCyr²/GVCyr² (eds. C. Dobias-Lalou et al., Università di Bologna, 2024; **CC BY-NC-SA 4.0**) is the
EpiDoc corpus of the Greek inscriptions of ancient Cyrenaica, including the archaic epichoric
**Doric** dialect and the GVCyr metrical/**verse** subset. The ``igcyr-corpus`` release asset is the
997 inscriptions, their Greek reading extracted with title, find-place, and date, decoded into a
compact pyaegean ``Corpus`` JSON by ``scripts/build_igcyr_corpus.py``. ``aegean.load("igcyr")``
fetches it to the cache on first use, then loads offline. CC BY-NC-SA permits the redistribution
(NonCommercial + ShareAlike pass to you). The text preserves epichoric letterforms (e.g. ``ō``/``ē``
for long o/e), i.e. NON-normalized epichoric Greek — valuable for dialect study, unusual for a
standard-polytonic pipeline. Cite IGCyr/GVCyr in academic work.
"""

from __future__ import annotations

from typing import Any


def load_igcyr() -> Any:
    """Load the Greek inscriptions of Cyrenaica as a `Corpus` (opt-in, fetched, CC BY-NC-SA 4.0).

    One `Document` per inscription (``igcyrNNN`` / ``gvcyrNNN``), the Greek reading tokenised into
    words, with a descriptive title (``meta.name``), find-place (``meta.site``, e.g. ``"Cyrene"``),
    and date (``meta.period``). Attribution travels with the corpus provenance; cite IGCyr/GVCyr."""
    from ...core.corpus import Corpus
    from ...data import fetch

    path = fetch("igcyr-corpus")
    return Corpus.from_json(path)


from ...core.corpus import register_loader  # noqa: E402

# loadable by name: aegean.load("igcyr") — fetches the corpus to the cache on first use
register_loader("igcyr", load_igcyr)
