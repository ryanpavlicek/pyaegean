"""Load the IOSPE Greek corpus (opt-in, fetched).

IOSPE³ — Ancient Inscriptions of the Northern Black Sea (King's College London;
github.com/kingsdigitallab/iospe). The repo code is MIT and the project publishes the inscription
data under CC BY; pyaegean attributes IOSPE and treats the data as CC BY. The ``iospe-corpus``
release asset is the ~1,194 Greek inscriptions (Tyras, Olbia, Chersonesos, and Byzantine), their
Greek reading extracted from each edition with the find-place and date, decoded into a compact
pyaegean ``Corpus`` JSON by ``scripts/build_iospe_corpus.py``. ``aegean.load("iospe")`` fetches it to
the cache on first use, then loads offline. Adds Greek epigraphy of the Black Sea region (Doric and
Ionic, archaic to Byzantine) absent from pyaegean's other holdings. Cite IOSPE in academic work.
"""

from __future__ import annotations

from typing import Any


def load_iospe() -> Any:
    """Load the IOSPE Greek inscriptions as a `Corpus` (opt-in, fetched, CC BY).

    One `Document` per inscription (id ``vol.num``, e.g. ``"1.1"``), the Greek reading tokenised
    into words, with the find-place (``meta.site``, e.g. ``"Tyras"``) and date (``meta.period``).
    The attribution travels with the corpus provenance; cite IOSPE (King's College London)."""
    from ...core.corpus import Corpus
    from ...data import fetch

    path = fetch("iospe-corpus")
    return Corpus.from_json(path)


from ...core.corpus import register_loader  # noqa: E402

# loadable by name: aegean.load("iospe") — fetches the corpus to the cache on first use
register_loader("iospe", load_iospe)
