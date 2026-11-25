"""Load the Cretan Institutional Inscriptions Greek corpus (opt-in, fetched).

*Cretan Institutional Inscriptions* (Irene Vagionakis, Università Ca' Foscari Venezia,
2016–2019; **CC BY-NC-SA 4.0**) collects 600 Archaic–Hellenistic Greek inscriptions from
Crete (7th–1st c. BCE) documenting the political institutions of Cretan city-states.
Built into a compact gzipped pyaegean ``Corpus`` JSON by ``scripts/build_crete_corpus.py``
and hosted as the ``crete-corpus`` release asset. ``aegean.load("crete")`` fetches it on
first use. NonCommercial + ShareAlike obligations pass to the user.
"""

from __future__ import annotations

from typing import Any


def load_crete() -> Any:
    """Load the 600 Cretan Institutional Inscriptions as a `Corpus` (CC BY-NC-SA 4.0)."""
    from ...core.corpus import Corpus
    from ...data import fetch

    path = fetch("crete-corpus")
    return Corpus.from_json(path)


from ...core.corpus import register_loader  # noqa: E402

register_loader("crete", load_crete, fresh=True)
