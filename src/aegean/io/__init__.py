"""I/O adapters — move the corpus model to and from interchange formats.

Import your own material with ``from_text`` / ``from_text_file`` / ``from_text_dir`` /
``from_csv`` (plain text, a folder of texts, or a CSV → a `Corpus`), or ``from_epidoc``
(any EpiDoc TEI edition → a `Corpus`); export with the CSV/Parquet/EpiDoc writers. The
Linear B-specific EpiDoc reader (DAMOS-style files, text-derived Aegean token kinds) lives
in `aegean.scripts.linearb` and ``Corpus.load("linearb")``. For pyaegean's own lossless
archive format, use ``Corpus.to_json`` / ``Corpus.from_json``.
"""

from __future__ import annotations

from .epidoc import from_epidoc, read_epidoc, to_epidoc, write_epidoc
from .review import REVIEW_COLUMNS, from_review_table, needs_review_flag, to_review_table
from .tabular import to_csv, to_parquet
from .text import from_csv, from_text, from_text_dir, from_text_file
from .workbench import from_workbench_export, to_workbench

__all__ = [
    "REVIEW_COLUMNS",
    "from_csv",
    "from_epidoc",
    "from_review_table",
    "from_text",
    "from_text_dir",
    "from_text_file",
    "from_workbench_export",
    "needs_review_flag",
    "read_epidoc",
    "to_csv",
    "to_epidoc",
    "to_parquet",
    "to_review_table",
    "to_workbench",
    "write_epidoc",
]
