"""I/O adapters — move the corpus model to and from interchange formats.

Import your own material with ``from_text`` / ``from_text_file`` / ``from_text_dir`` /
``from_csv`` (plain text, a folder of texts, or a CSV → a `Corpus`); export with the
CSV/Parquet/EpiDoc writers. EpiDoc *reading* (bring-your-own Linear B corpora) lives in
`aegean.scripts.linearb` and ``Corpus.load("linearb")``. For pyaegean's own lossless
archive format, use ``Corpus.to_json`` / ``Corpus.from_json``.
"""

from __future__ import annotations

from .epidoc import to_epidoc, write_epidoc
from .tabular import to_csv, to_parquet
from .text import from_csv, from_text, from_text_dir, from_text_file
from .workbench import from_workbench_export, to_workbench

__all__ = [
    "from_csv",
    "from_text",
    "from_text_dir",
    "from_text_file",
    "from_workbench_export",
    "to_csv",
    "to_epidoc",
    "to_parquet",
    "to_workbench",
    "write_epidoc",
]
