"""Load the Byzantine & Early Modern Vernacular Greek corpus (opt-in, fetched).

Sources 12 medieval and early modern vernacular Greek literary texts (~191,000 words,
12th–17th centuries) from ``open-greek/byzantine-early-modern-corpus`` (**Public Domain /
CC BY-SA 3.0**), including *Digenes Akritas*, *Ptochoprodromika*, *Chronicle of Moreas*,
*Poulologos*, *Paidiophrastos Diegesis*, *Porikologos*, *Apokopos*, and *Erotokritos*.
"""

from __future__ import annotations

from typing import Any


def load_byzantine() -> Any:
    """Load the Byzantine & Early Modern Vernacular Greek corpus as a `Corpus`."""
    from ...core.corpus import Corpus
    from ...data import fetch

    path = fetch("byzantine-corpus")
    return Corpus.from_json(path)


from ...core.corpus import register_loader  # noqa: E402

register_loader("byzantine", load_byzantine, fresh=True)
