"""Build the bundled Linear A corpus into the script-agnostic model and
register it so ``Corpus.load("lineara")`` works.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from ...core.corpus import Corpus, register_loader
from ...core.model import Document, DocumentMeta, Token, TokenKind
from ...core.numerals import parse_value
from ...core.provenance import Provenance
from ...data import load_bundled_json
from .inventory import linear_a_inventory

_SEP = {"\U00010101"}  # 𐄁 — word/entry divider
_IDEOGRAM_RE = re.compile(r"^[A-Z*][A-Z0-9*+'\[\]?]*$")


def classify(text: str, line_no: int | None, position: int) -> Token:
    """Tag a transliterated token by role (Linear A conventions)."""
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
    lines_raw: list[list[str]] = rec.get("lines") or []
    tokens: list[Token] = []
    lines: list[list[int]] = []
    pos = 0
    if lines_raw:
        for li, line in enumerate(lines_raw):
            idxs: list[int] = []
            for w in line:
                tokens.append(classify(w, li, pos))
                idxs.append(pos)
                pos += 1
            lines.append(idxs)
    else:
        idxs = []
        for w in rec.get("words") or []:
            tokens.append(classify(w, 0, pos))
            idxs.append(pos)
            pos += 1
        if idxs:
            lines.append(idxs)
    meta = DocumentMeta(
        site=rec.get("site", ""),
        support=rec.get("support", ""),
        scribe=rec.get("scribe", ""),
        findspot=rec.get("findspot", ""),
        period=rec.get("context", ""),
        name=rec.get("name", ""),
    )
    return Document(
        id=rec["id"],
        script_id="lineara",
        tokens=tokens,
        lines=lines,
        glyphs=rec.get("glyphs", ""),
        transcription=rec.get("transcription", ""),
        translations=list(rec.get("translations") or []),
        meta=meta,
    )


_PROVENANCE = Provenance(
    source="GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz",
    license="Apache-2.0 (corpus JSON); facsimile imagery © École Française d'Athènes, not redistributed",
    citation="Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A.",
    url="https://github.com/mwenge/lineara.xyz",
)


@lru_cache(maxsize=1)
def load_lineara() -> Corpus:
    recs = load_bundled_json("lineara", "inscriptions.json")
    docs = [_build_document(r) for r in recs]
    return Corpus(
        docs,
        sign_inventory=linear_a_inventory(),
        provenance=_PROVENANCE,
        script_id="lineara",
    )


register_loader("lineara", load_lineara)
