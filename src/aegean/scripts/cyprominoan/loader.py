"""Build the bundled Cypro-Minoan sample corpus into the script-agnostic model and register it so
``Corpus.load("cyprominoan")`` works.

The script is undeciphered, so a "word" is a sequence of sign numbers (``CM005-CM023-…``) with no
phonetic reading or translation. Only a small illustrative sample is bundled: the edited corpus
(Enkomi/Ugarit, the HoChyMin edition) is not openly redistributable, and sign readings are contested.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from ...core.corpus import Corpus, register_loader
from ...core.model import Document, DocumentMeta, Token, TokenKind
from ...core.provenance import Provenance
from ...data import load_bundled_json
from .inventory import cyprominoan_inventory

_SEP = {"\U00010100", "\U00010101"}  # 𐄀 𐄁 — Aegean word dividers


def classify(text: str, line_no: int | None, position: int) -> Token:
    """Tag a Cypro-Minoan token. Undeciphered: a hyphen-joined sign sequence is a WORD; a lone
    sign or anything else is UNKNOWN (there are no phonetic readings to resolve)."""
    if text in _SEP:
        return Token(text, TokenKind.SEPARATOR, (text,), None, line_no, position)
    if "-" in text:
        return Token(text, TokenKind.WORD, tuple(text.split("-")), None, line_no, position)
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
        id=rec["id"], script_id="cyprominoan", tokens=tokens, lines=lines,
        glyphs=rec.get("glyphs", ""), transcription=rec.get("transcription", ""),
        translations=list(rec.get("translations") or []), meta=meta,
    )


_PROVENANCE = Provenance(
    source="Illustrative sample of Cypro-Minoan sign sequences",
    license="Sign data from the Unicode Character Database (Unicode-3.0). Sample sequences are illustrative — chosen to exercise the model, not transcriptions of specific edited inscriptions.",
    citation="Ferrara, S. (2012–2013). Cypro-Minoan Inscriptions, vols. 1–2.",
    url="",
)


@lru_cache(maxsize=1)
def load_cyprominoan() -> Corpus:
    recs = load_bundled_json("cyprominoan", "sample_inscriptions.json")
    docs = [_build_document(r) for r in recs]
    return Corpus(docs, sign_inventory=cyprominoan_inventory(), provenance=_PROVENANCE, script_id="cyprominoan")


register_loader("cyprominoan", load_cyprominoan)
