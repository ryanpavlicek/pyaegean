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
import unicodedata
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
# An ideogram may carry a qualifier after its label: ``:`` and the sex of an animal
# (``m`` male, ``f`` female, ``x`` not determined) as in ``OVIS:m``; or ``;`` and the
# numbered variant of the sign (``x`` = variant not determined) as in ``TELA;1``. A
# ligatured sign may follow the qualifier, as in ``TELA;1+TE``. The qualified form is
# a distinct written sign, so it stays one LOGOGRAM token with one sign label.
_QUALIFIED_IDEOGRAM_RE = re.compile(r"^[A-Z*][A-Z0-9*+'\[\]?]*[:;][mfx0-9][A-Z0-9*+'\[\]?]*$")
_RESTORED_RE = re.compile(r"^\[[^\]]+\]$")  # an editorially restored reading, e.g. [KO]

_UNDERDOT = "̣"  # combining dot below — Leiden: damaged but legible
# Leiden lacuna brackets: text is missing on the bracketed side.
_LACUNA_BRACKETS = "[]"
# Brackets that delimit a stretch of text the edition does give — an erasure by the
# scribe (still legible), and the half-brackets of a partly preserved stretch. The
# reading is on the tokens inside the span, so the delimiter itself loses nothing.
_SPAN_BRACKETS = "⟦⟧⌞⌟⌜⌝"
_APPARATUS_BRACKETS = _LACUNA_BRACKETS + _SPAN_BRACKETS
# Notation that may trail a marker: an editorial query for a stretch that could not be
# read, and the arrows recording the direction the next stretch of the object is
# written in.
_UNREAD = "?"
_APPARATUS_TRAILING = _UNREAD + "↓→↗"
# The editorial apparatus a Mycenaean edition prints inside the transliteration line,
# with what each abbreviation stands for. Every entry records something about the
# object — its state, its sides, the stretches left blank, the traces too damaged to
# read — rather than a reading, so none of them is a sign the scribe wrote.
_APPARATUS: dict[str, str] = {
    # the text here is destroyed or was not read (`_APPARATUS_LOST`)
    "mut": "mutila — mutilated",
    "mut.": "mutila — mutilated",
    "mutila": "mutilated",
    "vest.": "vestigia — traces of signs, not read",
    "vestigia": "traces of signs, not read",
    "deest": "missing",
    # notation about the object, where no text is missing
    "sup.": "superne — above",
    "inf.": "inferne — below",
    "supra": "above",
    "lat.": "latus — side of the object",
    "sin.": "sinistrum — left side",
    "dex.": "dextrum — right side",
    "r.": "recto",
    "v.": "verso",
    "vac.": "vacat — space left blank",
    "vacat": "space left blank",
    "sigillum": "seal impression",
    "graffito": "graffito",
    "fragmentum": "fragment",
    "separatum": "separate",
    "angustum": "narrow",
    "reliqua": "remaining",
    "pars": "part",
    "sine": "without",
    "regulis": "rulings",
    "prior": "earlier",
}
# The markers that say the text at this position is not preserved or not read.
_APPARATUS_LOST = frozenset({"mut", "mut.", "mutila", "vest.", "vestigia", "deest"})
# A token that is bracketing and nothing else has no marker word: the empty string,
# which no `_APPARATUS` key can collide with.
_BARE_BRACKETS = ""


def _apparatus_marker(text: str) -> tuple[str, str] | None:
    """The editorial marker a token carries and its expansion, or ``None`` when the
    token is a reading rather than apparatus.

    A Mycenaean edition prints its own notation in the transliteration line: the
    Leiden brackets, and Latin abbreviations for the state of the object (``mut.``
    mutila, ``vest.`` vestigia, ``vac.`` vacat, ``v.`` verso, and the rest of
    `_APPARATUS`). Underdots, brackets, an editorial ``?`` and the writing-direction
    arrows are removed before the marker is looked up, so ``]vest.?[`` and
    ``⟦vest.⟧`` both resolve to ``vest.``. A token that is bracketing and nothing
    else carries `_BARE_BRACKETS`: it records no reading of its own.
    """
    if not text.strip():
        return None
    bare = unicodedata.normalize(
        "NFC", unicodedata.normalize("NFD", text).replace(_UNDERDOT, "")
    )
    for bracket in _APPARATUS_BRACKETS:
        bare = bare.replace(bracket, "")
    bare = bare.strip(_APPARATUS_TRAILING)
    if not bare:  # brackets, a query or a direction arrow and nothing else
        return _BARE_BRACKETS, "editorial notation, no reading recorded"
    gloss = _APPARATUS.get(bare)
    return None if gloss is None else (bare, gloss)


def _bracket_status(text: str) -> ReadingStatus:
    """The editorial status the Leiden brackets around a token give it.

    ``RESTORED`` for a wholly editor-supplied reading (``[KO]``), ``UNCLEAR`` when a
    bracket or an editorial ``?`` marks part of the token uncertain (``VIR+[?]``),
    ``CERTAIN`` otherwise. The one implementation for both an apparatus token and a
    reading, so the two cannot come to disagree about the same brackets."""
    if _RESTORED_RE.match(text):
        return ReadingStatus.RESTORED
    if "[" in text or "]" in text or _UNREAD in text:
        return ReadingStatus.UNCLEAR
    return ReadingStatus.CERTAIN


def classify(text: str, line_no: int | None, position: int) -> Token:
    """Tag a transliterated Linear B token by role and editorial status
    (same conventions as Linear A).

    A token that is the edition's apparatus rather than text (see `_apparatus_marker`)
    carries no signs in ``Token.signs``, and its expansion is kept in
    ``annotations["apparatus"]``. The token stays in the text stream, so a reader
    still shows where the edition broke off, but no sign-level count sees it: the
    shared sign rule (``analysis.stats._bears_signs``, which the frequency,
    dispersion, keyness, graph and sign-class readers all use) rejects both kinds it
    can be given, and the remaining sign-level readers (``analysis.seriation``,
    ``analysis.embeddings``, ``core.diagnose``) take WORD or WORD/LOGOGRAM tokens
    only. Which of the two ways that happens says what the marker means. A marker for
    text that is destroyed or unread (`_APPARATUS_LOST`, a lacuna bracket, an
    editorial ``?``) reads ``UNKNOWN`` / ``LOST``: nothing is preserved there. A
    marker that records something else about the object — a stretch left blank, a
    side, an erasure or half-bracket delimiting text the edition does give — reads
    ``SEPARATOR`` and keeps its editorial status: it stands between stretches of text
    rather than inside a reading, and calling it lost would claim damage the edition
    does not report.
    """
    marker = _apparatus_marker(text)
    if marker is not None:
        key, gloss = marker
        ann = {"apparatus": gloss}
        lacuna = any(ch in text for ch in _LACUNA_BRACKETS) or _UNREAD in text
        if key in _APPARATUS_LOST or (key == _BARE_BRACKETS and lacuna):
            return Token(text, TokenKind.UNKNOWN, (), None, line_no, position,
                         status=ReadingStatus.LOST, annotations=ann)
        return Token(text, TokenKind.SEPARATOR, (), None, line_no, position,
                     status=_bracket_status(text), annotations=ann)
    status = _bracket_status(text)
    # A wholly editor-supplied reading is classified on the text inside its brackets.
    bare = text[1:-1] if status is ReadingStatus.RESTORED else text
    if bare in _SEP:
        return Token(text, TokenKind.SEPARATOR, (bare,), None, line_no, position, status=status)
    if parse_value(bare) is not None:
        return Token(text, TokenKind.NUMERAL, (bare,), None, line_no, position, status=status)
    if "-" in bare:
        return Token(
            text, TokenKind.WORD, tuple(bare.split("-")), None, line_no, position, status=status
        )
    if _IDEOGRAM_RE.match(bare) or _QUALIFIED_IDEOGRAM_RE.match(bare):
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
