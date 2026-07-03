"""Word and sentence tokenization for Greek text.

A word is a run of Greek letters (with their combining diacritics) plus edge and
internal elision apostrophes: a trailing one for ordinary elision (``δ'``) and a
leading one for prodelision / aphaeresis (``'στι`` for ``ἐστι`` after a long vowel).
Everything else is punctuation or whitespace. Sentence
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
_WORD_RE = re.compile(rf"[{_APOS}]?[{_LETTER}{_MARK}]+(?:[{_APOS}][{_LETTER}{_MARK}]*)*")
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
        if _WORD_RE.fullmatch(s):
            tokens.append(Token(s, TokenKind.WORD, position=pos))
            pos += 1
            continue
        # A letter-bearing chunk that is not one clean word (e.g. a doubled leading
        # apostrophe, ''στι): split it into PUNCT / WORD / PUNCT pieces so the WORD is
        # realized the same way `tokenize_words` sees it, not swallowed as one PUNCT blob.
        idx = 0
        for wm in _WORD_RE.finditer(s):
            if wm.start() > idx:
                tokens.append(Token(s[idx:wm.start()], TokenKind.PUNCT, position=pos))
                pos += 1
            tokens.append(Token(wm.group(0), TokenKind.WORD, position=pos))
            pos += 1
            idx = wm.end()
        if idx < len(s):  # trailing punctuation, or the whole chunk when it holds no word
            tokens.append(Token(s[idx:], TokenKind.PUNCT, position=pos))
            pos += 1
    return tokens


def sentences(text: str) -> list[str]:
    """Split into trimmed sentences on Greek sentence-final punctuation."""
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
