"""Export a corpus to tabular formats (CSV, Parquet) via its DataFrame view.

Thin wrappers over `aegean.core.corpus.Corpus.to_dataframe`. pandas is the ``[data]`` extra;
Parquet additionally needs a parquet engine (the ``[parquet]`` extra — pyarrow).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .._atomic import atomic_path

if TYPE_CHECKING:
    from ..core.corpus import Corpus


def to_csv(corpus: Corpus, path: str | Path, *, level: str = "document") -> None:
    """Write the corpus's ``level`` DataFrame (``"document"``/``"token"``/``"word"``) to CSV."""
    # temp+replace so a failed/interrupted write never truncates a prior export
    with atomic_path(path) as tmp:
        corpus.to_dataframe(level).to_csv(tmp, index=False)


def to_parquet(corpus: Corpus, path: str | Path, *, level: str = "document") -> None:
    """Write the corpus's ``level`` DataFrame to Parquet (needs a parquet engine)."""
    df = corpus.to_dataframe(level)
    try:
        with atomic_path(path) as tmp:
            df.to_parquet(tmp, index=False)
    except ImportError as e:  # no parquet engine (pyarrow/fastparquet) installed
        raise ImportError(
            "Parquet export needs a parquet engine: pip install 'pyaegean[parquet]'"
        ) from e
