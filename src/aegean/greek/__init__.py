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

from . import benchmark  # noqa: F401 — CLTK benchmark harness (run_benchmark, compare_lemmatizers)
from .accent import AccentInfo, accentuation
from .lemmatize import lemmatize, lemmatize_verbose
from .normalize import (
    betacode_to_unicode,
    normalize,
    strip_diacritics,
    unicode_to_betacode,
)
from .prosody import scan, syllable_quantities
from .meter import (
    Foot,
    LineScansion,
    ScansionError,
    scan_hexameter,
    scan_line,
    scan_pentameter,
    syllable_options,
)
from .phonology import to_ipa
from .pos import pos_tag, pos_tags
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
    "syllable_quantities",
    "scan",
    "scan_line",
    "scan_hexameter",
    "scan_pentameter",
    "syllable_options",
    "LineScansion",
    "Foot",
    "ScansionError",
    "to_ipa",
    "pos_tag",
    "pos_tags",
    "lemmatize",
    "lemmatize_verbose",
    "benchmark",
]
