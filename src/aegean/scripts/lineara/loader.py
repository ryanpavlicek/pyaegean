"""Build the bundled Linear A corpus into the script-agnostic model and
register it so ``Corpus.load("lineara")`` works.

The loader also *interprets the apparatus the data carries*: the upstream
erased-sign placeholder becomes `ReadingStatus.LOST`, words damaged at a break
or with bracketed uncertain readings become ``UNCLEAR``, and tablet ruling
dashes become separators. The bundled JSON stays a faithful mirror of the
upstream; the interpretation lives here, versioned and tested.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from ...core.corpus import Corpus, register_loader
from ...core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind
from ...core.numerals import parse_value
from ...core.provenance import Provenance
from ...data import bundled_data_version
from ...data import load_bundled_json
from .inventory import linear_a_inventory

_SEP = {"\U00010101"}  # 𐄁 — word/entry divider
_RULE = {"—", "–"}  # a ruling/divider line drawn on the tablet
# The upstream (mwenge/lineara.xyz) marks erased/illegible signs with U+1076B —
# an unassigned codepoint just past the Linear A block; its own utils.js
# `stripErased()` removes it. Standalone runs mean the text here is lost;
# attached to a word, the reading is damaged at a break.
_ERASED = "\U0001076B"
# Logogram/ligature labels: an uppercase or "*NNN" base with ligature "+" and
# editorial brackets/queries, plus the GORILA variant marks — subscript ₂₃₄
# (PA₃) and a single lowercase variant letter after a letter or digit
# (VIR+*313b, CAPm+KU). Two lowercase letters never run together, so prose
# strays like "None" stay UNKNOWN.
_IDEOGRAM_RE = re.compile(r"^[A-Z*](?:[A-Z0-9*+'\[\]?₂₃₄]|(?<=[A-Z0-9])[a-z])*$")


def classify(text: str, line_no: int | None, position: int) -> Token:
    """Tag a transliterated token by role and editorial status (Linear A conventions)."""
    bare = text.replace(_ERASED, "")
    if not bare:  # nothing but erased-sign marks: the text here is not preserved
        return Token(
            text, TokenKind.UNKNOWN, (text,), None, line_no, position,
            status=ReadingStatus.LOST,
        )
    status = ReadingStatus.CERTAIN
    if bare != text:
        status = ReadingStatus.UNCLEAR  # partially erased / damaged at a break
    elif "[" in text or "]" in text or "?" in text:
        status = ReadingStatus.UNCLEAR  # bracketed uncertain reading, e.g. VIR+[?]
    if bare in _SEP:
        return Token(text, TokenKind.SEPARATOR, (bare,), None, line_no, position, status=status)
    if bare in _RULE:
        return Token(text, TokenKind.SEPARATOR, (bare,), None, line_no, position, status=status)
    if parse_value(bare) is not None:
        # Covers approximate readings ("≈ ¹⁄₆"): the editor's estimated value of a
        # damaged or unclear quantity is still a numeral (the ≈ is editorial
        # apparatus). A bare "≈" with nothing legible after it stays UNKNOWN.
        return Token(text, TokenKind.NUMERAL, (bare,), None, line_no, position, status=status)
    if "-" in bare:
        # sign labels come from the preserved reading; the marker is not a sign
        return Token(
            text, TokenKind.WORD, tuple(s for s in bare.split("-") if s), None,
            line_no, position, status=status,
        )
    if _IDEOGRAM_RE.match(bare):
        return Token(text, TokenKind.LOGOGRAM, (bare,), None, line_no, position, status=status)
    return Token(text, TokenKind.UNKNOWN, (bare,), None, line_no, position, status=status)


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
        # Facsimile/photograph references (relative paths under the upstream
        # mirror; never binaries) — what the `has-image` query field tests,
        # matching the workbench's behavior on the same corpus.
        images=tuple(rec.get("images") or ()),
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
    data_version=bundled_data_version(),
    source="GORILA (Godart & Olivier 1976–1985) via mwenge/lineara.xyz",
    license="Apache-2.0 (corpus JSON); facsimile imagery © École Française d'Athènes, not redistributed",
    citation="Godart, L. & Olivier, J.-P. (1976–1985). Recueil des inscriptions en linéaire A.",
    url="https://github.com/mwenge/lineara.xyz",
    notes=(
        "GORILA digitized at CEFAEL (École française d'Athènes): "
        "https://cefael.efa.gr/result.php?serie_title_operator=con&volume_number_operator=%3D&issue_year_operator=%3D&section_title=Recueil+des+inscriptions+en+lin%C3%A9aire+A&section_title_operator=con&author_lastname_operator=con&publisher_name_operator=con&site_id=1&actionID=advanced&operator=AND",
    ),
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
