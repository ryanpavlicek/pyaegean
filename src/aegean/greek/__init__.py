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
from .lemmatize import (
    LemmaSource,
    lemmatize,
    lemmatize_sourced,
    lemmatize_verbose,
    needs_review,
)
from .morphology import Analysis, analyze, best_pos, lemmas
from .rarity import RarityResult, WordRarity, terminology_rarity
from .treebank import TreebankLexicon, disable_treebank, use_treebank
from .paradigms import ParadigmLexicon, disable_paradigms, use_paradigms
from .documentary import (
    COORDINATORS,
    disable_documentary_lemma_rescue,
    disable_documentary_reconciliation,
    documentary_lemma_rescue_active,
    documentary_reconciliation_active,
    rescue_lemma,
    use_documentary_lemma_rescue,
    use_documentary_reconciliation,
)
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
    analyze_sentences,
    disable_neural_pipeline,
    neural_backend_info,
    use_neural_pipeline,
)
from .annotate import annotate_corpus
from .calibrate import (
    Calibration,
    UncalibratedConfidenceError,
    disable_calibration,
    ece,
    fit_temperature,
    temperature_softmax,
    top1_confidence,
    use_calibration,
)
from .coverage import MissingForm, missing_forms
from .explain import TokenExplanation, explain_pipeline, render_explanations
from .profile import TextProfile, profile_text
from .erroranalysis import (
    ErrorAnalysis,
    PosStat,
    analyze_errors,
    heldout_error_analysis,
    nt_error_analysis,
    proiel_error_analysis,
    ud_error_analysis,
)
from .proiel import (
    ConventionReport,
    DeprelConfusion,
    DriftReport,
    FeatureConventionStat,
    evaluate_on_proiel,
    load_proiel_gold,
    proiel_convention_report,
    proiel_dir,
    proiel_drift,
)
from .ud import agdt_ud_overlap, bootstrap_ud, evaluate_by_genre, evaluate_on_ud
from .papygreek import (
    PapyGreekConventionReport,
    evaluate_on_papygreek,
    evaluate_on_papygreek_dev,
    papygreek_convention_report,
    papygreek_dev_path,
    papygreek_path,
)
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
    citation_scheme,
    load_work,
    popular_works,
    remove_fetched_works,
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
    "citation_scheme",
    "load_work",
    "popular_works",
    "catalog",
    "fetch_works",
    "list_fetched_works",
    "remove_fetched_works",
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
    "lemmatize_sourced",
    "LemmaSource",
    "needs_review",
    "analyze",
    "lemmas",
    "best_pos",
    "Analysis",
    "benchmark",
    "use_treebank",
    "disable_treebank",
    "TreebankLexicon",
    "use_paradigms",
    "disable_paradigms",
    "ParadigmLexicon",
    "use_documentary_reconciliation",
    "disable_documentary_reconciliation",
    "documentary_reconciliation_active",
    "use_documentary_lemma_rescue",
    "disable_documentary_lemma_rescue",
    "documentary_lemma_rescue_active",
    "rescue_lemma",
    "COORDINATORS",
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
    "proiel_convention_report",
    "ConventionReport",
    "FeatureConventionStat",
    "DeprelConfusion",
    "ErrorAnalysis",
    "PosStat",
    "analyze_errors",
    "annotate_corpus",
    "missing_forms",
    "MissingForm",
    "explain_pipeline",
    "use_calibration",
    "disable_calibration",
    "Calibration",
    "UncalibratedConfidenceError",
    "fit_temperature",
    "ece",
    "temperature_softmax",
    "top1_confidence",
    "profile_text",
    "render_explanations",
    "TextProfile",
    "TokenExplanation",
    "proiel_error_analysis",
    "nt_error_analysis",
    "ud_error_analysis",
    "heldout_error_analysis",
    "evaluate_on_ud",
    "evaluate_by_genre",
    "evaluate_on_papygreek",
    "evaluate_on_papygreek_dev",
    "papygreek_path",
    "papygreek_dev_path",
    "papygreek_convention_report",
    "PapyGreekConventionReport",
    "eval_receipt",
    "EvalReceipt",
    "use_neural_pipeline",
    "disable_neural_pipeline",
    "analyze_sentence",
    "analyze_sentences",
    "neural_backend_info",
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
