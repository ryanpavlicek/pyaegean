"""Greek NLP pipeline — composable, individually-callable stages.

v0.1: ``normalize`` (NFC/NFD + Beta Code ↔ Unicode), ``tokenize`` (word/sentence),
``syllabify``, accent analysis (``accentuation``), ``prosody``/``meter`` scansion,
``phonology`` (IPA), a seed ``lemmatize``, baseline ``pos``, and a rule-based
``morphology`` analyzer (``analyze``) — with an **opt-in** treebank backend
(``use_treebank``; Perseus AGDT) that supplies attested, correctly-accented lemmas
and full features for known forms, an **opt-in** LSJ lexicon (``use_lsj``; Perseus
Liddell-Scott-Jones) for glossing (``gloss``/``lookup``), and an **opt-in** baseline
**dependency parser** (``use_parser``/``parse``; arc-eager + averaged perceptron,
trained on the AGDT) — see docs/PLAN.md.

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
from .morphology import Analysis, analyze, best_pos, lemmas
from .treebank import TreebankLexicon, disable_treebank, use_treebank
from .lexicon import LSJEntry, LSJLexicon, disable_lsj, gloss, lookup, use_lsj
from .syntax import DepToken, DepTree, disable_parser, evaluate, parse, use_parser
from .tagger import disable_tagger, evaluate_tagger, use_tagger
from .lemmatizer import disable_lemmatizer, evaluate_lemmatizer, use_lemmatizer
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
    "analyze",
    "lemmas",
    "best_pos",
    "Analysis",
    "benchmark",
    "use_treebank",
    "disable_treebank",
    "TreebankLexicon",
    "use_lsj",
    "disable_lsj",
    "gloss",
    "lookup",
    "LSJEntry",
    "LSJLexicon",
    "parse",
    "use_parser",
    "disable_parser",
    "evaluate",
    "DepTree",
    "DepToken",
    "use_tagger",
    "disable_tagger",
    "evaluate_tagger",
    "use_lemmatizer",
    "disable_lemmatizer",
    "evaluate_lemmatizer",
]
