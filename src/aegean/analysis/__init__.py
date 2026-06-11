"""Script-agnostic + Aegean-specific analysis over the core model.

Ported faithfully from the Linear A Research Workbench (``src/lib/*.ts``) and
checked against shared golden fixtures so the Python port can't silently
diverge. Methods over the undeciphered Linear A material are **exploratory** —
see each function's docstring.
"""

from __future__ import annotations

from ..core.numerals import BalanceCheck
from .accounting import account_lines, balance_check
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
    wilson_interval,
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
from .morphology import (
    ClusterMember,
    MorphCluster,
    find_morphological_clusters,
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
    Dispersion,
    KeynessRow,
    bootstrap_ci,
    dispersion,
    dispersions,
    keyness,
)
from .structure import (
    CATEGORIES,
    LIBATION_WORDS,
    StructureCategory,
    classify_corpus,
    classify_structure,
)

__all__ = [
    # accounting
    "balance_check",
    "account_lines",
    "BalanceCheck",
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
