"""Build the bundled Cypriot sample corpus into the script-agnostic model and register it so
``Corpus.load("cypriot")`` works.

Only a small illustrative sample is bundled. The Cypriot epigraphic corpus (ICS — Inscriptions
de Chypre syllabiques, and successors) is not openly redistributable; a fuller corpus is a future
bring-your-own addition.
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
    meta = DocumentMeta(
        site=rec.get("site", ""), support=rec.get("support", ""), scribe=rec.get("scribe", ""),
        findspot=rec.get("findspot", ""), period=rec.get("context", ""), name=rec.get("name", ""),
    )
    return Document(
        id=rec["id"], script_id="cypriot", tokens=tokens, lines=lines,
        glyphs=rec.get("glyphs", ""), transcription=rec.get("transcription", ""),
        translations=list(rec.get("translations") or []), meta=meta,
    )


_PROVENANCE = Provenance(
    data_version=bundled_data_version(),
    source="Illustrative sample of Cypriot syllabic inscriptions",
    license="Sign data from the Unicode Character Database (Unicode-3.0). Sample transliterations are scholarly facts, bundled as illustrative excerpts — not a corpus.",
    citation="Masson, O. (1983). Les inscriptions chypriotes syllabiques (2nd ed.).",
    url="",
)


@lru_cache(maxsize=1)
def load_cypriot() -> Corpus:
    recs = load_bundled_json("cypriot", "sample_inscriptions.json")
    docs = [_build_document(r) for r in recs]
    return Corpus(docs, sign_inventory=cypriot_inventory(), provenance=_PROVENANCE, script_id="cypriot")


register_loader("cypriot", load_cypriot)
