"""Word and sentence tokenization for Greek text.

A word is a run of Greek letters (with their combining diacritics) plus edge and
internal elision apostrophes: a trailing one for ordinary elision (``δ'``) and a
leading one for prodelision / aphaeresis (``'στι`` for ``ἐστι`` after a long vowel).
Everything else is punctuation or whitespace. Sentence boundaries come from the
shared conservative segmenter: callers can select a documented domain policy or
provide a validated external segmenter without changing tokenization.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from ..core.model import SourceAlignment, Token, TokenKind
from .sentence_segmentation import SegmentationResult, SegmenterLike, segment_text

# Greek + Coptic (U+0370–03FF) minus its two punctuation code points, plus the
# polytonic Extended Greek block (U+1F00–1FFF). U+037E GREEK QUESTION MARK and
# U+0387 GREEK ANO TELEIA are canonical punctuation (NFC folds them to ";" and
# "·"), so they must tokenize as PUNCT exactly like those lookalikes; a plain
# U+0370–03FF span would glue them into WORD tokens. Combining marks
# (U+0300–036F) are a separate class below.
_LETTER = r"Ͱ-ͽͿ-ΆΈ-Ͽἀ-῿"
_MARK = r"̀-ͯ"
_APOS = r"'’᾽ʼ"  # straight ', right single quote, koronis, modifier
# Milesian numeral sign. The trailing keraia U+0374 (e.g. δʹ = 4) sits in the
# Greek block above but NFC-folds to U+02B9 in the Spacing Modifier Letters
# block, outside that range, so U+02B9 counts as a word character too and the
# numeral stays one token whichever normalization the caller passed (the neural
# contract mandates NFC). The leading lower keraia U+0375 (͵α = 1000) is
# NFC-stable and already covered by the Greek range.
_NUMERAL_SIGN = "ʹ"  # NFC image of the keraia U+0374
_WORD_RE = re.compile(rf"[{_APOS}]?[{_LETTER}{_MARK}{_NUMERAL_SIGN}]+(?:[{_APOS}][{_LETTER}{_MARK}{_NUMERAL_SIGN}]*)*")
_TOKEN_RE = re.compile(rf"([{_LETTER}{_MARK}{_NUMERAL_SIGN}{_APOS}]+|[^\s{_LETTER}{_MARK}{_NUMERAL_SIGN}{_APOS}]+)")
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


def _tokenize_aligned_result(
    text: str,
    *,
    document_id: str = "input",
    segmentation_policy: str = "default",
    segmenter: SegmenterLike | None = None,
    segmentation_result: SegmentationResult | None = None,
) -> list[Token]:
    """Tokenize *text* while retaining an immutable, lossless source mapping.

    Token pieces are exactly those returned by :func:`tokenize`; sentence identities
    come from the shared segmenter and may not bisect one of those atomic pieces.
    Model-facing text is NFC-normalized in the alignment only; ``Token.text`` remains
    the original token text so legacy callers retain their established values.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not isinstance(document_id, str):
        raise TypeError("document_id must be a string")
    if not document_id:
        raise ValueError("document_id must be a non-empty string")

    segmentation = (
        segmentation_result
        if segmentation_result is not None
        else segment_text(text, policy=segmentation_policy, segmenter=segmenter)
    )
    if segmentation.source != text:
        raise ValueError("segmentation_result belongs to a different source")
    raw_spans = _token_spans(text)
    boundary_points = [
        point
        for boundary in segmentation.boundaries
        for point in (boundary.start, boundary.end)
    ]
    token_index = 0
    for point in boundary_points:
        while token_index < len(raw_spans) and raw_spans[token_index][3] <= point:
            token_index += 1
        if token_index < len(raw_spans):
            token_start, token_end = raw_spans[token_index][2:]
            if token_start < point < token_end:
                raise ValueError("sentence boundary bisects a token")
    source_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    tokens: list[Token] = []
    previous_end = 0
    sentence_ordinal = 0
    for ordinal, (token_text, kind, start, end) in enumerate(raw_spans):
        while (
            sentence_ordinal + 1 < len(segmentation.boundaries)
            and start >= segmentation.boundaries[sentence_ordinal].end
        ):
            sentence_ordinal += 1
        sentence_id = f"{document_id}:sentence:{sentence_ordinal}"
        normalized = unicodedata.normalize("NFC", token_text)
        ops = ("unicode:nfc",) if normalized != token_text else ()
        alignment = SourceAlignment(
            document_id=document_id,
            sentence_id=sentence_id,
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
    return tokens


def tokenize_aligned(
    text: str,
    *,
    document_id: str = "input",
    sentence_policy: str = "default",
    segmenter: SegmenterLike | None = None,
) -> list[Token]:
    """Tokenize with lossless alignment under one named sentence policy."""
    return _tokenize_aligned_result(
        text,
        document_id=document_id,
        segmentation_policy=sentence_policy,
        segmenter=segmenter,
    )


def sentences(
    text: str,
    *,
    sentence_policy: str = "default",
    segmenter: SegmenterLike | None = None,
) -> list[str]:
    """Project rich, policy-aware segmentation to the legacy list-of-strings shape."""
    return list(segment_text(text, policy=sentence_policy, segmenter=segmenter).sentences)
