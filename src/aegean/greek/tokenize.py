"""Word and sentence tokenization for Greek text.

A word is a run of Greek letters (with their combining diacritics) plus internal
elision apostrophes; everything else is punctuation or whitespace. Sentence
boundaries are the Greek full stop ``.``, the question mark ``;`` / ``;``,
and the ano teleia ``·`` / ``·``.
"""

from __future__ import annotations

import re

from ..core.model import Token, TokenKind

# Greek + Coptic (U+0370–03FF) minus its two punctuation code points, plus the
# polytonic Extended Greek block (U+1F00–1FFF). U+037E GREEK QUESTION MARK and
# U+0387 GREEK ANO TELEIA are canonical punctuation (NFC folds them to ";" and
# "·"), so they must tokenize as PUNCT exactly like those lookalikes; a plain
# U+0370–03FF span would glue them into WORD tokens. Combining marks
# (U+0300–036F) are a separate class below.
_LETTER = r"Ͱ-ͽͿ-ΆΈ-Ͽἀ-῿"
_MARK = r"̀-ͯ"
_APOS = r"'’᾽ʼ"  # straight ', right single quote, koronis, modifier
_WORD_RE = re.compile(rf"[{_LETTER}{_MARK}]+(?:[{_APOS}][{_LETTER}{_MARK}]*)*")
_TOKEN_RE = re.compile(rf"([{_LETTER}{_MARK}{_APOS}]+|[^\s{_LETTER}{_MARK}{_APOS}]+)")
_SENTENCE_SPLIT_RE = re.compile(r"[.;;··]+")


def tokenize_words(text: str) -> list[str]:
    """Just the word strings, in order (punctuation dropped)."""
    return [m.group(0) for m in _WORD_RE.finditer(text)]


def tokenize(text: str) -> list[Token]:
    """Typed tokens (WORD or PUNCT) with positions, in document order."""
    tokens: list[Token] = []
    pos = 0
    for m in _TOKEN_RE.finditer(text):
        s = m.group(0)
        kind = TokenKind.WORD if _WORD_RE.fullmatch(s) else TokenKind.PUNCT
        tokens.append(Token(s, kind, position=pos))
        pos += 1
    return tokens


def sentences(text: str) -> list[str]:
    """Split into trimmed sentences on Greek sentence-final punctuation."""
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
