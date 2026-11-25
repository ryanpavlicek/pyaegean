"""Load the Open Apostolic Fathers Greek corpus (opt-in, fetched).

*Open Apostolic Fathers* (edited by James Tauber & Seumas Macdonald, Zenodo
10.5281/zenodo.2555673; **CC BY-SA 4.0**) provides twice-independently hand-corrected Greek
texts of all 15 Apostolic Fathers works: 1–2 Clement, Ignatius's seven epistles, Polycarp to
the Philippians, *Didache*, *Epistle of Barnabas*, *Shepherd of Hermas*, *Martyrdom of
Polycarp*, and *Epistle to Diognetus*.
"""

from __future__ import annotations

from typing import Any


def load_apostolic_fathers() -> Any:
    """Load the 15 Greek Apostolic Fathers works as a `Corpus` (CC BY-SA 4.0)."""
    from ...core.corpus import Corpus
    from ...data import fetch

    path = fetch("apostolic-fathers-corpus")
    return Corpus.from_json(path)


from ...core.corpus import register_loader  # noqa: E402

register_loader("apostolic-fathers", load_apostolic_fathers, fresh=True)
