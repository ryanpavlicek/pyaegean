"""Build the bundled Cypriot corpus into the script-agnostic model and register it so
``Corpus.load("cypriot")`` works.

The corpus bundles the **Cypriot syllabic inscriptions of Inscriptiones Graecae XV 1** (the
BBAW digital edition, ``telota.bbaw.de/ig``, CC BY 4.0) as a hosted snapshot — so the package
carries the readable text itself and never depends on the source staying online — plus a couple
of illustrative samples. Each inscription keeps its own source URL for the CC-BY link-back.

The loader also *interprets the Leiden apparatus the edition carries*: a combining underdot
(damaged but legible sign) becomes `ReadingStatus.UNCLEAR`, and square lacuna brackets
(editorially supplied text) become ``RESTORED``, tracking bracket spans that run across word
dividers and line breaks. The markers are stripped from the emitted token text; the marked
form is kept in ``annotations["leiden"]`` and the raw ``transcription`` stays untouched.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any

from ...core.corpus import Corpus, register_loader
from ...core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind
from ...core.numerals import parse_value
from ...core.provenance import Provenance
from ...data import bundled_data_version
from ...data import load_bundled_json
from .inventory import cypriot_inventory

_SEP = {"\U00010100", "\U00010101"}  # 𐄀 𐄁 — Aegean word dividers
_IDEOGRAM_RE = re.compile(r"^[A-Z*][A-Z0-9*+'\[\]?]*$")
_UNDERDOT = "̣"  # combining dot below — Leiden: damaged but legible


def classify(
    text: str, line_no: int | None, position: int, *, restored: bool = False
) -> Token:
    """Tag a transliterated Cypriot token by role and editorial status (Leiden conventions).

    The IG edition marks a damaged-but-legible sign with a combining underdot
    (-> ``UNCLEAR``) and editorially supplied text with square lacuna brackets
    (-> ``RESTORED``). Both markers are stripped from the emitted token; the marked form is
    kept in ``annotations["leiden"]``. ``restored=True`` flags a token inside a bracket span
    opened by an earlier token (spans run across word dividers and line breaks;
    `_build_document` tracks them).
    """
    nfd = unicodedata.normalize("NFD", text)
    bare = text
    if _UNDERDOT in nfd:
        bare = unicodedata.normalize("NFC", nfd.replace(_UNDERDOT, ""))
    bracketed = "[" in bare or "]" in bare
    if bracketed:
        bare = bare.replace("[", "").replace("]", "")
    if not bare:  # nothing outside the lacuna brackets: the text here is not preserved
        return Token(
            text, TokenKind.UNKNOWN, (text,), None, line_no, position,
            status=ReadingStatus.LOST,
        )
    if restored or bracketed:
        status = ReadingStatus.RESTORED  # wholly or partly editor-supplied at a lacuna
    elif bare != text:
        status = ReadingStatus.UNCLEAR  # underdotted: damaged but read
    else:
        status = ReadingStatus.CERTAIN
    ann = {"leiden": text} if bare != text else {}
    if bare in _SEP:
        return Token(
            bare, TokenKind.SEPARATOR, (bare,), None, line_no, position,
            status=status, annotations=ann,
        )
    if parse_value(bare) is not None:
        return Token(
            bare, TokenKind.NUMERAL, (bare,), None, line_no, position,
            status=status, annotations=ann,
        )
    if "-" in bare:
        # sign labels come from the preserved reading; the markers are not signs
        return Token(
            bare, TokenKind.WORD, tuple(s for s in bare.split("-") if s), None,
            line_no, position, status=status, annotations=ann,
        )
    if _IDEOGRAM_RE.match(bare):
        return Token(
            bare, TokenKind.LOGOGRAM, (bare,), None, line_no, position,
            status=status, annotations=ann,
        )
    return Token(
        bare, TokenKind.UNKNOWN, (bare,), None, line_no, position,
        status=status, annotations=ann,
    )


def _build_document(rec: dict[str, Any]) -> Document:
    lines_raw: list[list[str]] = rec.get("lines") or ([rec["words"]] if rec.get("words") else [])
    tokens: list[Token] = []
    lines: list[list[int]] = []
    pos = 0
    depth = 0  # open lacuna brackets; a restoration span may cross tokens and lines
    for li, line in enumerate(lines_raw):
        idxs: list[int] = []
        for w in line:
            tokens.append(classify(w, li, pos, restored=depth > 0))
            for ch in w:
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth = max(0, depth - 1)  # the opener fell in a lost edge
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
