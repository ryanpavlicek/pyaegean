"""I/O adapters — export the corpus model to interchange formats.

EpiDoc *reading* (bring-your-own Linear B corpora) lives in `aegean.scripts.linearb` and
``Corpus.load("linearb")``; this package provides the EpiDoc writer plus CSV/Parquet exporters.
For pyaegean's own lossless archive format, use ``Corpus.to_json`` / ``Corpus.from_json``.
"""

from __future__ import annotations

from .epidoc import to_epidoc, write_epidoc
from .tabular import to_csv, to_parquet

__all__ = ["to_csv", "to_epidoc", "to_parquet", "write_epidoc"]
