"""Load the Inscriptions of Aphrodisias (IAph2007) Greek corpus (opt-in, fetched).

*Inscriptions of Aphrodisias 2007* (eds. Joyce Reynolds, Charlotte Roueché & Gabriel Bodard,
King's College London, 2007; **CC BY 2.5**, http://insaph.kcl.ac.uk/) collects ~1,471 Greek
inscriptions from Aphrodisias in Caria (Western Asia Minor, 2nd c. BCE to Byzantine period).
Built into a compact gzipped pyaegean ``Corpus`` JSON by ``scripts/build_aphrodisias_corpus.py``
and hosted as the ``aphrodisias-corpus`` release asset. ``aegean.load("aphrodisias")`` fetches
it to the cache on first use and loads offline thereafter.
"""

from __future__ import annotations

from typing import Any


def load_aphrodisias() -> Any:
    """Load the Greek inscriptions of Aphrodisias (IAph2007) as a `Corpus` (CC BY 2.5)."""
    from ...core.corpus import Corpus
    from ...data import fetch

    path = fetch("aphrodisias-corpus")
    return Corpus.from_json(path)


from ...core.corpus import register_loader  # noqa: E402

register_loader("aphrodisias", load_aphrodisias, fresh=True)
