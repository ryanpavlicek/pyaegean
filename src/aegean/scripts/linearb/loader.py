"""Build the bundled Linear B sample corpus into the script-agnostic model and register it so
``Corpus.load("linearb")`` works.

The bundled corpus is a small illustrative sample of canonical tablets — the zero-network
default (the Apache-2.0 wheel carries no NC-licensed data). For the **full corpus**,
``aegean.load("damos")`` fetches the ~5,900-tablet DAMOS edition (CC BY-NC-SA 4.0) to the
cache; or point ``PYAEGEAN_LINEARB_CORPUS`` at your own licensed EpiDoc export, which
pyaegean parses locally and never re-hosts.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any

from ...core.corpus import Corpus, register_loader
from ...core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind
from ...core.numerals import parse_value
from ...core.provenance import Provenance
from ...data import bundled_data_version
from ...data import load_bundled_json
from .inventory import linear_b_inventory

_SEP = {"\U00010100", "\U00010101"}  # 𐄀 𐄁 — Aegean word dividers
_IDEOGRAM_RE = re.compile(r"^[A-Z*][A-Z0-9*+'\[\]?]*$")
_RESTORED_RE = re.compile(r"^\[[^\]]+\]$")  # an editorially restored reading, e.g. [KO]


def classify(text: str, line_no: int | None, position: int) -> Token:
    """Tag a transliterated Linear B token by role and editorial status
    (same conventions as Linear A)."""
    status = ReadingStatus.CERTAIN
    bare = text
    if _RESTORED_RE.match(text):  # wholly editor-supplied reading
        status = ReadingStatus.RESTORED
        bare = text[1:-1]
    elif "[" in text or "]" in text or "?" in text:
        status = ReadingStatus.UNCLEAR  # bracketed uncertain element, e.g. VIR+[?]
    if bare in _SEP:
        return Token(text, TokenKind.SEPARATOR, (bare,), None, line_no, position, status=status)
    if parse_value(bare) is not None:
        return Token(text, TokenKind.NUMERAL, (bare,), None, line_no, position, status=status)
    if "-" in bare:
        return Token(
            text, TokenKind.WORD, tuple(bare.split("-")), None, line_no, position, status=status
        )
    if _IDEOGRAM_RE.match(bare):
        return Token(text, TokenKind.LOGOGRAM, (bare,), None, line_no, position, status=status)
    return Token(text, TokenKind.UNKNOWN, (bare,), None, line_no, position, status=status)


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
    data_version=bundled_data_version(),
    source="Illustrative sample of canonical Linear B tablets; transliterations after Ventris & Chadwick and standard editions",
    license="Sign data from the Unicode Character Database (Unicode-3.0). Sample transliterations are scholarly facts, bundled as illustrative excerpts — not a corpus.",
    citation="Ventris, M. & Chadwick, J. (1973). Documents in Mycenaean Greek (2nd ed.). Cambridge University Press.",
    url="",
)


@lru_cache(maxsize=1)
def load_linearb() -> Corpus:
    # Bring-your-own: PYAEGEAN_LINEARB_CORPUS points at a local EpiDoc file/directory; otherwise
    # the bundled illustrative sample is used (the full corpus is aegean.load("damos"), fetched).
    source = os.environ.get("PYAEGEAN_LINEARB_CORPUS")
    if source:
        from .epidoc import load_epidoc_corpus

        return load_epidoc_corpus(source)
    recs = load_bundled_json("linearb", "sample_inscriptions.json")
    docs = [_build_document(r) for r in recs]
    return Corpus(docs, sign_inventory=linear_b_inventory(), provenance=_PROVENANCE, script_id="linearb")


register_loader("linearb", load_linearb)
