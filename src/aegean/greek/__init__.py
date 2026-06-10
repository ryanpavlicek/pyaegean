"""Greek NLP pipeline — composable, individually-callable stages.

The dependency-free core covers ``normalize`` (NFC/NFD + Beta Code ↔ Unicode),
``tokenize`` (word/sentence), ``syllabify``, accent analysis (``accentuation``),
``prosody``/``meter`` scansion, ``phonology`` (IPA), a seed ``lemmatize``, baseline
``pos``, and a rule-based ``morphology`` analyzer (``analyze``).

Opt-in backends layer on richer data and models:

- ``use_treebank`` (Perseus AGDT) supplies attested, correctly-accented lemmas and
  full features for known forms.
- ``use_lsj`` (Perseus Liddell-Scott-Jones) provides glossing (``gloss``/``lookup``).
- ``use_parser`` (``parse``; arc-eager + averaged perceptron, trained on the AGDT) is
  a projective dependency parser (~0.67 UAS / 0.57 LAS).
- ``use_tagger`` is an averaged-perceptron POS tagger (~84% on unseen forms).
- ``use_lemmatizer`` is an edit-tree lemmatizer (~40% on unseen forms).
- ``use_neural_lemmatizer`` (the ``[neural]`` extra) is a GreTa T5 seq2seq model
  served as int8 ONNX without torch; it pairs a gold lookup with seq2seq decoding and
  reaches 76.3% on unseen forms. ``lemmatize`` cascades treebank -> neural ->
  edit-tree -> seed.

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
from .lexicon import LSJEntry, LSJLexicon, LexiconNotLoadedError, disable_lsj, gloss, lookup, use_lsj
from .syntax import (
    DepToken,
    DepTree,
    ParserNotLoadedError,
    disable_parser,
    evaluate as evaluate_parser,
    parse,
    use_parser,
)
from .tagger import TaggerNotLoadedError, disable_tagger, evaluate_tagger, use_tagger
from .lemmatizer import (
    LemmatizerNotLoadedError,
    disable_lemmatizer,
    evaluate_lemmatizer,
    use_lemmatizer,
)
from .neural_lemmatizer import (
    NeuralLemmatizerNotLoadedError,
    disable_neural_lemmatizer,
    use_neural_lemmatizer,
)
from .proiel import evaluate_on_proiel, load_proiel_gold, proiel_dir
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
    "evaluate_parser",
    "DepTree",
    "DepToken",
    "use_tagger",
    "disable_tagger",
    "evaluate_tagger",
    "use_lemmatizer",
    "disable_lemmatizer",
    "evaluate_lemmatizer",
    "use_neural_lemmatizer",
    "disable_neural_lemmatizer",
    "evaluate_on_proiel",
    "load_proiel_gold",
    "proiel_dir",
    "ParserNotLoadedError",
    "TaggerNotLoadedError",
    "LemmatizerNotLoadedError",
    "NeuralLemmatizerNotLoadedError",
    "LexiconNotLoadedError",
]
