"""Greek NLP pipeline — composable, individually-callable stages.

The dependency-free core covers ``normalize`` (NFC/NFD + Beta Code ↔ Unicode, with
a lenient OCR-repair mode), ``tokenize`` (word/sentence), ``syllabify``, accent
analysis (``accentuation``), ``prosody``/``meter`` scansion, ``phonology`` (IPA),
a seed+rule ``lemmatize``, baseline ``pos``, and a rule-based ``morphology`` analyzer
(``analyze``). ``pipeline`` runs the whole stack over a text in one call.

Opt-in backends layer on richer data and models:

- ``use_neural_pipeline`` (the ``[neural]`` extra) loads the joint neural model —
  one pass serving UPOS, full morphology (UD FEATS), UD dependency trees, and
  lemmas, state of the art on the UD Ancient Greek (Perseus) benchmark (measured numbers
  in ``docs/benchmarks.md``). Once active, ``pos_tag``/``pos_tags``,
  ``lemmatize``, ``parse``, and ``pipeline`` all use it.
- ``use_treebank`` (Perseus AGDT) supplies attested, correctly-accented lemmas and
  full features for known forms.
- ``use_lsj`` (Perseus Liddell-Scott-Jones) provides glossing (``gloss``/``lookup``).
- ``use_parser`` (``parse``; arc-eager + averaged perceptron, trained on the AGDT) is
  a projective dependency parser (~0.67 UAS / 0.57 LAS).
- ``use_tagger`` is an averaged-perceptron POS tagger (~84% on unseen forms).
- ``use_lemmatizer`` is an edit-tree lemmatizer (~40% on unseen forms).
- ``use_neural_lemmatizer`` (the ``[neural]`` extra) is a GreTa T5 seq2seq model
  served as int8 ONNX without torch; it pairs a gold lookup with seq2seq decoding and
  reaches 76.3% on unseen forms. ``lemmatize`` cascades neural pipeline ->
  treebank -> neural -> edit-tree -> seed table -> generalizing ending rules.

Every stage is a plain function so it can be used standalone::

    from aegean import greek
    greek.betacode_to_unicode("mh=nin")      # 'μῆνιν'
    greek.syllabify("ἄνθρωπος")              # ['ἄν', 'θρω', 'πος']
    greek.accentuation("λόγος").classification  # 'paroxytone'
    greek.pipeline("ἐν ἀρχῇ ἦν ὁ λόγος.")    # per-token records, one call
"""

from __future__ import annotations

from . import benchmark  # noqa: F401 — CLTK benchmark harness (run_benchmark, compare_lemmatizers)
from .accent import AccentInfo, accentuation
from .accent_law import AccentPlacement, place_accent, persistent_accent, recessive_accent
from .sandhi import ResolvedForm, resolve_sandhi, resolve_sentence
from .inflect import (
    Inflector,
    InflectorNotLoadedError,
    disable_inflector,
    inflect,
    paradigm,
    use_inflector,
)
from .lemmatize import lemmatize, lemmatize_verbose
from .morphology import Analysis, analyze, best_pos, lemmas
from .rarity import RarityResult, WordRarity, terminology_rarity
from .treebank import TreebankLexicon, disable_treebank, use_treebank
from .lexicon import LSJEntry, LSJLexicon, LexiconNotLoadedError, disable_lsj, lookup, use_lsj
from .usage import UsageInfo, usage
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
from .joint import (
    NeuralPipelineNotLoadedError,
    SentenceAnalysis,
    analyze_sentence,
    disable_neural_pipeline,
    use_neural_pipeline,
)
from .proiel import DriftReport, evaluate_on_proiel, load_proiel_gold, proiel_dir, proiel_drift
from .ud import agdt_ud_overlap, bootstrap_ud, evaluate_on_ud
from .eval_receipt import EvalReceipt, eval_receipt
from .normalize import (
    NormalizationWarning,
    betacode_to_unicode,
    normalize,
    strip_diacritics,
    unicode_to_betacode,
)
from .koine import (
    DodsonEntry,
    DodsonNotLoadedError,
    gloss_nt,
    gloss_strongs,
    lookup_nt,
    use_dodson,
)
from .lexicons import (
    LexEntry,
    LexiconInfo,
    active_lexica,
    disable_lexicon,
    entry,
    gloss,
    lexica,
    lexicon_link,
    use_lexicon,
)
from . import abbott_smith, scaife_lex  # noqa: F401  -- register the new lexica
from .nt_eval import evaluate_on_nt
from .pipeline import TokenRecord, pipeline
from ..scripts.greek.perseus import (
    GitHubRateLimitError,
    WorkFetchResult,
    catalog,
    fetch_works,
    list_fetched_works,
    load_work,
    popular_works,
)
from ..scripts.greek.nt import load_nt, nt_books
from .prosody import scan, syllable_quantities
from .meter import (
    AEOLIC_LINES,
    Foot,
    LineScansion,
    ScansionError,
    scan_aeolic,
    scan_hexameter,
    scan_line,
    scan_pentameter,
    scan_trimeter,
    syllable_options,
)
from .phonology import to_ipa
from .pos import pos_tag, pos_tags
from .syllabify import syllabify
from .tokenize import sentences, tokenize, tokenize_words

__all__ = [
    "normalize",
    "NormalizationWarning",
    "strip_diacritics",
    "betacode_to_unicode",
    "unicode_to_betacode",
    "pipeline",
    "TokenRecord",
    "load_work",
    "popular_works",
    "catalog",
    "fetch_works",
    "list_fetched_works",
    "WorkFetchResult",
    "GitHubRateLimitError",
    "load_nt",
    "nt_books",
    "use_dodson",
    "gloss_nt",
    "lookup_nt",
    "gloss_strongs",
    "DodsonEntry",
    "DodsonNotLoadedError",
    "evaluate_on_nt",
    "tokenize",
    "tokenize_words",
    "sentences",
    "syllabify",
    "accentuation",
    "AccentInfo",
    "place_accent",
    "recessive_accent",
    "persistent_accent",
    "AccentPlacement",
    "resolve_sandhi",
    "resolve_sentence",
    "ResolvedForm",
    "syllable_quantities",
    "scan",
    "scan_line",
    "scan_hexameter",
    "scan_pentameter",
    "scan_trimeter",
    "scan_aeolic",
    "AEOLIC_LINES",
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
    "use_inflector",
    "disable_inflector",
    "inflect",
    "paradigm",
    "Inflector",
    "InflectorNotLoadedError",
    "terminology_rarity",
    "RarityResult",
    "WordRarity",
    "use_lsj",
    "disable_lsj",
    "gloss",
    "lookup",
    "usage",
    "UsageInfo",
    "entry",
    "LSJEntry",
    "LSJLexicon",
    "LexEntry",
    "LexiconInfo",
    "lexica",
    "use_lexicon",
    "disable_lexicon",
    "active_lexica",
    "lexicon_link",
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
    "bootstrap_ud",
    "evaluate_on_proiel",
    "proiel_drift",
    "DriftReport",
    "evaluate_on_ud",
    "eval_receipt",
    "EvalReceipt",
    "use_neural_pipeline",
    "disable_neural_pipeline",
    "analyze_sentence",
    "SentenceAnalysis",
    "NeuralPipelineNotLoadedError",
    "agdt_ud_overlap",
    "load_proiel_gold",
    "proiel_dir",
    "ParserNotLoadedError",
    "TaggerNotLoadedError",
    "LemmatizerNotLoadedError",
    "NeuralLemmatizerNotLoadedError",
    "LexiconNotLoadedError",
]
