"""Load the DDbDP Greek documentary-papyri corpus (opt-in, fetched).

DDbDP — the Duke Databank of Documentary Papyri, via papyri.info (github.com/papyri/idp.data). The
data is CC BY 3.0, so pyaegean mirrors it as the ``ddbdp-corpus`` release asset. This is by far the
largest corpus pyaegean ships — **57,331 Greek documentary papyri, ~4.4M tokens** — so it is hosted
and read as a **SQLite** database (with full-text search), not JSON, built by
``scripts/build_ddbdp_corpus.py``.

Because a corpus this size costs multiple GB of RAM to hold in memory, the recommended access is the
memory-friendly DB layer, which streams and full-text-searches without materialising all the tokens:

    from aegean.scripts.greek import ddbdp_db
    from aegean.db import search, stream
    for doc_id, pos, text in search(ddbdp_db(), "βασιλέως"):   # instant FTS across all papyri
        ...
    for doc in stream(ddbdp_db()):                             # flat-memory iteration
        ...

``aegean.load("ddbdp")`` still returns the whole thing as an in-memory ``Corpus`` for those who want
it and have the RAM. Cite the DDbDP / papyri.info in academic work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def ddbdp_db() -> Path:
    """The path to the fetched DDbDP SQLite database (fetched + unpacked on first use).

    Pass it to ``aegean.db.search()`` / ``stream()`` / ``from_sqlite()`` for memory-friendly,
    full-text-searchable access to the 57k papyri without materialising the whole corpus."""
    from ...data import fetch

    return Path(fetch("ddbdp-corpus")) / "ddbdp.sqlite"


def load_ddbdp() -> Any:
    """Load ALL of DDbDP as an in-memory ``Corpus`` (opt-in, fetched, CC BY 3.0).

    WARNING: 57,331 papyri / ~4.4M tokens — this materialises the entire corpus and costs several GB
    of RAM. For most work prefer the memory-friendly DB layer: ``aegean.db.search(ddbdp_db(), ...)``
    for instant full-text search, or ``aegean.db.stream(ddbdp_db())`` for flat-memory iteration.
    The attribution travels with the corpus provenance; cite the DDbDP (papyri.info)."""
    from ...db import from_sqlite

    return from_sqlite(ddbdp_db())


from ...core.corpus import register_loader  # noqa: E402

# loadable by name: aegean.load("ddbdp") — fetches + unpacks the SQLite corpus on first use
register_loader("ddbdp", load_ddbdp)
