"""Build the bundled Cypriot corpus into the script-agnostic model and register it so
``Corpus.load("cypriot")`` works.

The corpus bundles the **Cypriot syllabic inscriptions of Inscriptiones Graecae XV 1** (the
BBAW digital edition, ``telota.bbaw.de/ig``, CC BY 4.0) as a hosted snapshot — so the package
carries the readable text itself and never depends on the source staying online — plus a couple
of illustrative samples. Each inscription keeps its own source URL for the CC-BY link-back.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from ...core.corpus import Corpus, register_loader
from ...core.model import Document, DocumentMeta, Token, TokenKind
from ...core.numerals import parse_value
from ...core.provenance import Provenance
from ...data import bundled_data_version
from ...data import load_bundled_json
from .inventory import cypriot_inventory

_SEP = {"\U00010100", "\U00010101"}  # 𐄀 𐄁 — Aegean word dividers
_IDEOGRAM_RE = re.compile(r"^[A-Z*][A-Z0-9*+'\[\]?]*$")


def classify(text: str, line_no: int | None, position: int) -> Token:
    """Tag a transliterated Cypriot token by role."""
    if text in _SEP:
        return Token(text, TokenKind.SEPARATOR, (text,), None, line_no, position)
    if parse_value(text) is not None:
        return Token(text, TokenKind.NUMERAL, (text,), None, line_no, position)
    if "-" in text:
        return Token(text, TokenKind.WORD, tuple(text.split("-")), None, line_no, position)
    if _IDEOGRAM_RE.match(text):
        return Token(text, TokenKind.LOGOGRAM, (text,), None, line_no, position)
    return Token(text, TokenKind.UNKNOWN, (text,), None, line_no, position)


def _build_document(rec: dict[str, Any]) -> Document:
    lines_raw: list[list[str]] = rec.get("lines") or ([rec["words"]] if rec.get("words") else [])
    tokens: list[Token] = []
    lines: list[list[int]] = []
    pos = 0
    for li, line in enumerate(lines_raw):
        idxs: list[int] = []
        for w in line:
            tokens.append(classify(w, li, pos))
            idxs.append(pos)
            pos += 1
        if idxs:
            lines.append(idxs)
    notes: list[str] = []
    if rec.get("source_url"):
        notes.append(rec["source_url"])  # CC-BY link-back
    if rec.get("greek"):
        notes.append("Greek: " + rec["greek"])  # the alphabetic side of a bilingual
    meta = DocumentMeta(
        site=rec.get("site", ""), support=rec.get("support", ""), scribe=rec.get("scribe", ""),
        findspot=rec.get("findspot", ""), period=rec.get("context", ""), name=rec.get("name", ""),
        notes=tuple(notes),
    )
    return Document(
        id=rec["id"], script_id="cypriot", tokens=tokens, lines=lines,
        glyphs=rec.get("glyphs", ""), transcription=rec.get("transcription", ""),
        translations=list(rec.get("translations") or []), meta=meta,
    )


_PROVENANCE = Provenance(
    data_version=bundled_data_version(),
    source="Inscriptiones Graecae XV 1: Cypriot syllabic inscriptions (BBAW digital edition), plus illustrative samples",
    license="Inscriptiones Graecae XV 1: CC BY 4.0 (Berlin-Brandenburg Academy of Sciences and Humanities). Sign data: Unicode-3.0.",
    citation="Inscriptiones Graecae XV 1 (Cypriot syllabic inscriptions), digital edition, https://telota.bbaw.de/ig (CC BY 4.0).",
    url="https://telota.bbaw.de/ig/",
)


@lru_cache(maxsize=1)
def load_cypriot() -> Corpus:
    recs = load_bundled_json("cypriot", "ig_inscriptions.json")
    recs += load_bundled_json("cypriot", "sample_inscriptions.json")
    docs = [_build_document(r) for r in recs]
    return Corpus(docs, sign_inventory=cypriot_inventory(), provenance=_PROVENANCE, script_id="cypriot")


register_loader("cypriot", load_cypriot)
