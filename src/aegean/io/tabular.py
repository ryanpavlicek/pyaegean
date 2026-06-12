"""Export a corpus to tabular formats (CSV, Parquet) via its DataFrame view.

Thin wrappers over `aegean.core.corpus.Corpus.to_dataframe`. pandas is the ``[data]`` extra;
Parquet additionally needs a parquet engine (the ``[parquet]`` extra — pyarrow).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.corpus import Corpus


def to_csv(corpus: Corpus, path: str | Path, *, level: str = "document") -> None:
    """Write the corpus's ``level`` DataFrame (``"document"``/``"token"``/``"word"``) to CSV."""
    corpus.to_dataframe(level).to_csv(path, index=False)


def to_parquet(corpus: Corpus, path: str | Path, *, level: str = "document") -> None:
    """Write the corpus's ``level`` DataFrame to Parquet (needs a parquet engine)."""
    df = corpus.to_dataframe(level)
    try:
        df.to_parquet(path, index=False)
    except ImportError as e:  # no parquet engine (pyarrow/fastparquet) installed
        raise ImportError(
            "Parquet export needs a parquet engine: pip install 'pyaegean[parquet]'"
        ) from e
