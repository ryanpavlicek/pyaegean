"""Load the bundled Greek sample corpus into the script-agnostic model and
register it so ``Corpus.load("greek")`` works.

The seed is a handful of short, public-domain Ancient Greek passages spanning
Archaic→Koine, used to exercise the NLP pipeline. The full open-data corpus
(First1KGreek / Perseus) is fetched/added in the deeper Greek track.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from ...core.corpus import Corpus, register_loader
from ...core.model import Document, DocumentMeta
from ...core.provenance import Provenance
from ...data import bundled_data_version
from ...data import load_bundled_json
from ...greek.tokenize import tokenize
from .inventory import greek_inventory


def _build_document(rec: dict[str, Any]) -> Document:
    text = rec.get("text", "")
    tokens = tokenize(text)
    meta = DocumentMeta(
        period=rec.get("period", ""),
        name=rec.get("work", ""),
        scribe=rec.get("author", ""),
    )
    return Document(
        id=rec["id"],
        script_id="greek",
        tokens=tokens,
        lines=[list(range(len(tokens)))] if tokens else [],
        transcription=text,
        meta=meta,
    )


_PROVENANCE = Provenance(
    data_version=bundled_data_version(),
    source="Public-domain Ancient Greek text samples (Archaic→Koine)",
    license="Public domain (ancient texts); seed sample for the v0.1 Greek start",
    citation="Homer, Herodotus, Heraclitus, Sappho, Gospel of John (sample excerpts).",
    notes=(
        "Offline seed sample. Real works load on demand via "
        "aegean.greek.load_work('tlg0012.tlg001') — Perseus canonical-greekLit "
        "and First1KGreek, fetched to cache (CC BY-SA).",
    ),
)


@lru_cache(maxsize=1)
def load_greek() -> Corpus:
    recs = load_bundled_json("greek", "sample_texts.json")
    docs = [_build_document(r) for r in recs]
    return Corpus(
        docs,
        sign_inventory=greek_inventory(),
        provenance=_PROVENANCE,
        script_id="greek",
    )


register_loader("greek", load_greek)
