"""Load the Homer Multitext Venetus A Iliad & Homeric Scholia corpus (opt-in, fetched).

Extracts the normalized Venetus A (10th c. MS Marcianus Graecus Z. 454) *Iliad* (24 books,
15,645 lines) and Homeric *scholia* (Venetus A main, interlinear, intermarginal, interior,
exterior scholia, plus Venetus B and Escorial Upsilon 1.1 scholia) from the official
*Homer Multitext Project* release ``hmt-2026a.cex`` (**CC BY-NC 4.0**). NonCommercial
obligations pass to the user; fetched on demand and never bundled.
"""

from __future__ import annotations

from typing import Any


def load_homer_scholia() -> Any:
    """Load the Homer Multitext Venetus A Iliad & Scholia corpus as a `Corpus` (CC BY-NC 4.0)."""
    from ...core.corpus import Corpus
    from ...data import fetch

    path = fetch("homer-scholia-corpus")
    return Corpus.from_json(path)


from ...core.corpus import register_loader  # noqa: E402

register_loader("homer-scholia", load_homer_scholia, fresh=True)
