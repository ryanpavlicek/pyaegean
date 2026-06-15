"""Script-agnostic + Aegean-specific analysis over the core model.

Ported faithfully from the Linear A Research Workbench (``src/lib/*.ts``) and
checked against shared golden fixtures so the Python port can't silently
diverge. Methods over the undeciphered Linear A material are **exploratory** —
see each function's docstring.
"""

from __future__ import annotations

from ..core.numerals import BalanceCheck
from .accounting import (
    account_lines,
    balance_check,
    checkable_accounts,
    is_checkable_account,
)
from .align import (
    AlignCell,
    AlignOp,
    AlnPos,
    add_sequence,
    align_phonetic,
    align_sequences,
)
from .collocation import (
    chi_squared_2x2,
    chi_squared_p_value,
    fishers_exact,
    log_likelihood_ratio_2x2,
    pmi_interval,
    sign_bigram_pmi,
    sign_bigram_pmis,
    wilson_interval,
)
from .commodity import (
    ExclusivityRow,
    ideogram_group_exclusivity,
    line_cooccurrence_pmi,
)
from .compare import (
    PHONEME_SCRIPTS,
    PhoneticComparison,
    nearest,
    phonetic_compare,
    romanize_greek,
    to_phonemes,
)
from .distance import (
    BASE_VOWELS,
    CONSERVATIVE_PHONETIC_SCHEME,
    DEFAULT_PHONETIC_CLASSES,
    DEFAULT_PHONETIC_SCHEME,
    DEFAULT_WEIGHTS,
    PhoneticClasses,
    PhoneticScheme,
    PhoneticWeights,
    build_phonetic_classes,
    describe_phonetic_scheme,
    extract_root,
    is_numeral_token,
    phonetic_distance,
    reference_key,
    sequence_distance,
    sequence_similarity,
)
from .edge import (
    EdgeBiasRow,
    PositionalRow,
    Productivity,
    SuccessorRow,
    SuccessorVariety,
    affix_edge_bias,
    baayen_productivity,
    edge_bias_g2,
    positional_bias,
    positional_bias_g2,
    successor_variety,
)
from .morphology import (
    ClusterMember,
    MorphCluster,
    find_morphological_clusters,
)
from .multivariate import (
    CAPoint,
    CAResult,
    DendroMerge,
    DendroResult,
    correspondence_analysis,
    label_propagation,
    upgma_with_bootstrap,
)
from .patterns import (
    SIGN_PATTERN_HELP,
    CompiledSignPattern,
    compile_sign_pattern,
    match_sign_pattern,
    normalize_sign_label,
    word_matches_sign_pattern,
)
from .query import (
    FIELDS,
    Connector,
    FieldDef,
    FilterRow,
    Output,
    QueryResults,
    WordEntry,
    build_cooccurrence_map,
    build_word_index,
    default_value,
    eval_query,
    inscription_matches,
    run_query,
    summarize_filters,
    word_matches,
)
from .stats import (
    BootstrapCI,
    Chao1Result,
    Dispersion,
    HeapsFit,
    KeynessRow,
    ZipfMandelbrotFit,
    bootstrap_ci,
    bootstrap_counts_ci,
    chao1,
    dispersion,
    dispersions,
    fit_heaps,
    fit_zipf_mandelbrot_mle,
    keyness,
    mattr,
    miller_madow_entropy,
    mulberry32,
    shannon_entropy,
    spearman_rho,
)
from .lb_divergence import (
    DivergenceRow,
    LaValueCount,
    LaValueCounts,
    LbFrequencies,
    build_lb_divergence,
    linear_a_sign_value_counts,
    parse_damos_frequencies,
)
from .profiling import (
    CommodityMetrology,
    Dossier,
    DossierEntry,
    DocumentTypeProfile,
    FractionRow,
    MetrologyProfile,
    account_dossiers,
    document_type_profile,
    metrology_profile,
)
from .scribal import (
    HandProfile,
    hand_keyness,
    scribal_hands,
)
from .structure import (
    CATEGORIES,
    LIBATION_WORDS,
    StructureCategory,
    classify_corpus,
    classify_structure,
)
from .surprisal import (
    SignBigramModel,
    SurprisalStep,
    WordSurprisal,
    train_sign_bigram_model,
    word_surprisal,
)

__all__ = [
    # accounting
    "balance_check",
    "account_lines",
    "BalanceCheck",
    "is_checkable_account",
    "checkable_accounts",
    # sign patterns
    "word_matches_sign_pattern",
    "compile_sign_pattern",
    "match_sign_pattern",
    "normalize_sign_label",
    "SIGN_PATTERN_HELP",
    "CompiledSignPattern",
    # phonetic distance / schemes / sequence
    "phonetic_distance",
    "extract_root",
    "reference_key",
    "is_numeral_token",
    "sequence_distance",
    "sequence_similarity",
    "build_phonetic_classes",
    "describe_phonetic_scheme",
    "PhoneticClasses",
    "PhoneticScheme",
    "PhoneticWeights",
    "DEFAULT_PHONETIC_SCHEME",
    "CONSERVATIVE_PHONETIC_SCHEME",
    "DEFAULT_PHONETIC_CLASSES",
    "DEFAULT_WEIGHTS",
    "BASE_VOWELS",
    # alignment
    "align_phonetic",
    "align_sequences",
    "add_sequence",
    "AlignCell",
    "AlignOp",
    "AlnPos",
    # cross-script phonetic comparison
    "romanize_greek",
    "to_phonemes",
    "phonetic_compare",
    "nearest",
    "PhoneticComparison",
    "PHONEME_SCRIPTS",
    # collocation statistics
    "chi_squared_2x2",
    "log_likelihood_ratio_2x2",
    "chi_squared_p_value",
    "fishers_exact",
    "wilson_interval",
    "pmi_interval",
    # morphology
    "find_morphological_clusters",
    "MorphCluster",
    "ClusterMember",
    # corpus statistics (dispersion / keyness / bootstrap)
    "dispersion",
    "dispersions",
    "keyness",
    "bootstrap_ci",
    "Dispersion",
    "KeynessRow",
    "BootstrapCI",
    # vocabulary richness & information (count-vector estimators)
    "mulberry32",
    "shannon_entropy",
    "miller_madow_entropy",
    "bootstrap_counts_ci",
    "chao1",
    "Chao1Result",
    "mattr",
    "fit_heaps",
    "HeapsFit",
    "fit_zipf_mandelbrot_mle",
    "ZipfMandelbrotFit",
    # positional / edge keyness + morphological productivity
    "edge_bias_g2",
    "affix_edge_bias",
    "EdgeBiasRow",
    "positional_bias_g2",
    "positional_bias",
    "PositionalRow",
    "baayen_productivity",
    "Productivity",
    "successor_variety",
    "SuccessorVariety",
    "SuccessorRow",
    # sign-bigram adjacency PMI + commodity/ideogram line statistics
    "sign_bigram_pmi",
    "sign_bigram_pmis",
    "line_cooccurrence_pmi",
    "ideogram_group_exclusivity",
    "ExclusivityRow",
    # graphotactic surprisal (Witten-Bell sign-bigram, leave-one-out)
    "train_sign_bigram_model",
    "word_surprisal",
    "SignBigramModel",
    "WordSurprisal",
    "SurprisalStep",
    # multivariate (correspondence analysis, UPGMA, label propagation)
    "correspondence_analysis",
    "CAPoint",
    "CAResult",
    "upgma_with_bootstrap",
    "DendroMerge",
    "DendroResult",
    "label_propagation",
    # Linear A vs Linear B sign-frequency divergence
    "spearman_rho",
    "parse_damos_frequencies",
    "LbFrequencies",
    "linear_a_sign_value_counts",
    "LaValueCounts",
    "LaValueCount",
    "build_lb_divergence",
    "DivergenceRow",
    # scribal-hand analysis (DAMOS hands)
    "scribal_hands",
    "HandProfile",
    "hand_keyness",
    # corpus profiling (document types, dossiers, metrology)
    "document_type_profile",
    "DocumentTypeProfile",
    "account_dossiers",
    "Dossier",
    "DossierEntry",
    "metrology_profile",
    "MetrologyProfile",
    "FractionRow",
    "CommodityMetrology",
    # query engine
    "FIELDS",
    "FieldDef",
    "FilterRow",
    "Connector",
    "Output",
    "QueryResults",
    "WordEntry",
    "default_value",
    "inscription_matches",
    "word_matches",
    "eval_query",
    "run_query",
    "build_word_index",
    "build_cooccurrence_map",
    "summarize_filters",
    # structure detection
    "classify_structure",
    "classify_corpus",
    "CATEGORIES",
    "StructureCategory",
    "LIBATION_WORDS",
]
