"""Greek NLP pipeline — composable, individually-callable stages.

v0.1 start: ``normalize`` (NFC/NFD + Beta Code ↔ Unicode), ``tokenize``
(word/sentence), ``syllabify``, accent analysis (``accentuation``), and a
baseline ``lemmatize`` (open-data seed). Deeper stages — full morphology, POS,
dependency parsing, prosody, LSJ — land across later versions (docs/PLAN.md).

Every stage is a plain function so it can be used standalone::

    from aegean import greek
    greek.betacode_to_unicode("mh=nin")      # 'μῆνιν'
    greek.syllabify("ἄνθρωπος")              # ['ἄν', 'θρω', 'πος']
    greek.accentuation("λόγος").classification  # 'paroxytone'
"""

from __future__ import annotations

from .accent import AccentInfo, accentuation
from .lemmatize import lemmatize, lemmatize_verbose
from .normalize import (
    betacode_to_unicode,
    normalize,
    strip_diacritics,
    unicode_to_betacode,
)
from .syllabify import syllabify
from .tokenize import sentences, tokenize, tokenize_words

__all__ = [
    "normalize",
    "strip_diacritics",
    "betacode_to_unicode",
    "unicode_to_betacode",
    "tokenize",
    "tokenize_words",
    "sentences",
    "syllabify",
    "accentuation",
    "AccentInfo",
    "lemmatize",
    "lemmatize_verbose",
]
