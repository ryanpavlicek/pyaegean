"""I/O adapters — move the corpus model to and from interchange formats.

Import your own material with ``from_text`` / ``from_text_file`` / ``from_text_dir`` /
``from_csv`` (plain text, a folder of texts, or a CSV → a `Corpus`), or ``from_epidoc``
(pyaegean output or token-carrier EpiDoc TEI → a `Corpus`). Export as tabular
CSV/Parquet, semantic EpiDoc, RDF Turtle/JSON-LD, SQLite, review CSV, or the
intentionally lossy Workbench surface format. The
Linear B-specific EpiDoc reader (DAMOS-style files, text-derived Aegean token kinds) lives
in `aegean.scripts.linearb` and ``Corpus.load("linearb")``. For pyaegean's own lossless
archive format, use ``Corpus.to_json`` / ``Corpus.from_json``; use JSON or SQLite
when every corpus field must survive. Loss-aware NLP adapters for CoNLL-U, spaCy,
Stanza, and CLTK use ``InteropDocument`` plus an integrity-bound JSON sidecar so
unsupported target fields are disclosed rather than silently discarded.
"""

from __future__ import annotations

from ._interop_bundle import (
    BUNDLE_SCHEMA,
    InteropBundle,
    bundle_from_document,
    bundle_from_result,
    dumps_interop_bundle,
    loads_interop_bundle,
    read_interop_bundle,
    write_interop_bundle,
)
from ._interop_cltk import from_cltk, make_cltk_process, to_cltk
from ._interop_spacy import from_spacy, to_spacy
from ._interop_stanza import from_stanza, to_stanza
from .epidoc import from_epidoc, read_epidoc, to_epidoc, write_epidoc
from .interop import (
    SIDECAR_COMMENT_PREFIX,
    InteropDependencyError,
    InteropDocument,
    InteropError,
    InteropLossError,
    InteropReport,
    InteropResult,
    InteropSchemaError,
    InteropSentenceMetadata,
    InteropTokenMetadata,
    decode_sidecar,
    encode_sidecar,
    from_conllu,
    from_token_records,
    from_ud_document,
    to_conllu,
)
from .rdf import to_rdf
from .review import (
    REVIEW_COLUMNS,
    MergedReview,
    ReviewConflict,
    ReviewerValue,
    apply_merged,
    from_review_table,
    merge_review_tables,
    needs_review_flag,
    to_review_table,
)
from .tabular import to_csv, to_parquet
from .text import from_csv, from_text, from_text_dir, from_text_file
from .workbench import from_workbench_export, to_workbench

# The corpus export formats `aegean export` accepts, in the order they are advertised.
# The single source of truth: cli._corpus.export() validates against it and derives its
# --format help from it, and tests/test_propagation_parity anchors to it — so a new
# writer cannot reach the CLI (or drift out of the help / wiki table) unnoticed.
EXPORT_FORMATS: tuple[str, ...] = (
    "json", "csv", "parquet", "epidoc", "sqlite", "workbench", "ttl", "jsonld",
)

__all__ = [
    "BUNDLE_SCHEMA",
    "EXPORT_FORMATS",
    "SIDECAR_COMMENT_PREFIX",
    "REVIEW_COLUMNS",
    "InteropBundle",
    "InteropDependencyError",
    "InteropDocument",
    "InteropError",
    "InteropLossError",
    "InteropReport",
    "InteropResult",
    "InteropSchemaError",
    "InteropSentenceMetadata",
    "InteropTokenMetadata",
    "MergedReview",
    "ReviewConflict",
    "ReviewerValue",
    "apply_merged",
    "bundle_from_document",
    "bundle_from_result",
    "decode_sidecar",
    "dumps_interop_bundle",
    "encode_sidecar",
    "from_cltk",
    "from_conllu",
    "from_csv",
    "from_epidoc",
    "from_review_table",
    "from_spacy",
    "from_stanza",
    "from_text",
    "from_text_dir",
    "from_text_file",
    "from_workbench_export",
    "from_token_records",
    "from_ud_document",
    "loads_interop_bundle",
    "make_cltk_process",
    "merge_review_tables",
    "needs_review_flag",
    "read_epidoc",
    "read_interop_bundle",
    "to_cltk",
    "to_conllu",
    "to_csv",
    "to_epidoc",
    "to_parquet",
    "to_rdf",
    "to_review_table",
    "to_spacy",
    "to_stanza",
    "to_workbench",
    "write_epidoc",
    "write_interop_bundle",
]
