"""Word and sentence tokenization for Greek text.

A word is a run of Greek letters (with their combining diacritics) plus edge and
internal elision apostrophes: a trailing one for ordinary elision (``δ'``) and a
leading one for prodelision / aphaeresis (``'στι`` for ``ἐστι`` after a long vowel).
Everything else is punctuation or whitespace. Sentence
boundaries are the Greek full stop ``.``, the question mark ``;`` / ``;``,
and the ano teleia ``·`` / ``·``.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from ..core.model import SourceAlignment, Token, TokenKind

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


def _token_spans(text: str) -> list[tuple[str, TokenKind, int, int]]:
    """Return legacy token pieces together with their exact source spans."""
    pieces: list[tuple[str, TokenKind, int, int]] = []
    for m in _TOKEN_RE.finditer(text):
        s = m.group(0)
        if _WORD_RE.fullmatch(s):
            pieces.append((s, TokenKind.WORD, m.start(), m.end()))
            continue
        # A letter-bearing chunk that is not one clean word (e.g. a doubled leading
        # apostrophe, ''στι): split it into PUNCT / WORD / PUNCT pieces so the WORD is
        # realized the same way `tokenize_words` sees it, not swallowed as one PUNCT blob.
        idx = 0
        for wm in _WORD_RE.finditer(s):
            if wm.start() > idx:
                start = m.start() + idx
                end = m.start() + wm.start()
                pieces.append((s[idx:wm.start()], TokenKind.PUNCT, start, end))
            start = m.start() + wm.start()
            end = m.start() + wm.end()
            pieces.append((wm.group(0), TokenKind.WORD, start, end))
            idx = wm.end()
        if idx < len(s):  # trailing punctuation, or the whole chunk when it holds no word
            pieces.append((s[idx:], TokenKind.PUNCT, m.start() + idx, m.end()))
    return pieces


def tokenize(text: str) -> list[Token]:
    """Typed tokens (WORD or PUNCT) with positions, in document order."""
    return [
        Token(token_text, kind, position=position)
        for position, (token_text, kind, _start, _end) in enumerate(_token_spans(text))
    ]


def tokenize_aligned(text: str, *, document_id: str = "input") -> list[Token]:
    """Tokenize *text* while retaining an immutable, lossless source mapping.

    The token boundaries and sentence transitions intentionally use the exact same
    regexes as :func:`tokenize` and the pipeline.  Model-facing text is NFC-normalized
    in the alignment only; ``Token.text`` remains the original token text so legacy
    callers retain their established values.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not isinstance(document_id, str):
        raise TypeError("document_id must be a string")
    if not document_id:
        raise ValueError("document_id must be a non-empty string")

    source_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    tokens: list[Token] = []
    previous_end = 0
    sentence_ordinal = 0
    for ordinal, (token_text, kind, start, end) in enumerate(_token_spans(text)):
        normalized = unicodedata.normalize("NFC", token_text)
        ops = ("unicode:nfc",) if normalized != token_text else ()
        alignment = SourceAlignment(
            document_id=document_id,
            sentence_id=f"{document_id}:sentence:{sentence_ordinal}",
            source_token_id=f"{document_id}:{source_digest}:{ordinal}:{start}-{end}",
            original_text=token_text,
            start_char=start,
            end_char=end,
            whitespace_before=text[previous_end:start],
            normalized_text=normalized,
            normalization_ops=ops,
        )
        tokens.append(Token(token_text, kind, position=ordinal, alignment=alignment))
        previous_end = end
        if kind is TokenKind.PUNCT and _SENTENCE_SPLIT_RE.search(token_text):
            sentence_ordinal += 1
    return tokens


def sentences(text: str) -> list[str]:
    """Split into trimmed sentences on Greek sentence-final punctuation."""
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
