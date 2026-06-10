"""Build the bundled Linear B sample corpus into the script-agnostic model and register it so
``Corpus.load("linearb")`` works.

No openly-licensed Linear B tablet corpus exists — the most complete one, DAMOS, is CC BY-NC-SA —
so only a small illustrative sample of canonical tablets is bundled. Point
``PYAEGEAN_LINEARB_CORPUS`` at your own licensed export (e.g. a DAMOS EpiDoc download) to work
with a full corpus; pyaegean never re-hosts it.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any

from ...core.corpus import Corpus, register_loader
from ...core.model import Document, DocumentMeta, Token, TokenKind
from ...core.numerals import parse_value
from ...core.provenance import Provenance
from ...data import load_bundled_json
from .inventory import linear_b_inventory

_SEP = {"\U00010100", "\U00010101"}  # 𐄀 𐄁 — Aegean word dividers
_IDEOGRAM_RE = re.compile(r"^[A-Z*][A-Z0-9*+'\[\]?]*$")


def classify(text: str, line_no: int | None, position: int) -> Token:
    """Tag a transliterated Linear B token by role (same conventions as Linear A)."""
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
        id=rec["id"], script_id="linearb", tokens=tokens, lines=lines,
        glyphs=rec.get("glyphs", ""), transcription=rec.get("transcription", ""),
        translations=list(rec.get("translations") or []), meta=meta,
    )


_PROVENANCE = Provenance(
    source="Illustrative sample of canonical Linear B tablets; transliterations after Ventris & Chadwick and standard editions",
    license="Sign data from the Unicode Character Database (Unicode-3.0). Sample transliterations are scholarly facts, bundled as illustrative excerpts — not a corpus.",
    citation="Ventris, M. & Chadwick, J. (1973). Documents in Mycenaean Greek (2nd ed.). Cambridge University Press.",
    url="",
)


@lru_cache(maxsize=1)
def load_linearb() -> Corpus:
    # Bring-your-own: PYAEGEAN_LINEARB_CORPUS points at a local EpiDoc file/directory; otherwise
    # the bundled illustrative sample is used (no openly-licensed corpus exists to ship).
    source = os.environ.get("PYAEGEAN_LINEARB_CORPUS")
    if source:
        from .epidoc import load_epidoc_corpus

        return load_epidoc_corpus(source)
    recs = load_bundled_json("linearb", "sample_inscriptions.json")
    docs = [_build_document(r) for r in recs]
    return Corpus(docs, sign_inventory=linear_b_inventory(), provenance=_PROVENANCE, script_id="linearb")


register_loader("linearb", load_linearb)
