"""Export a corpus to tabular formats (CSV, Parquet) via its DataFrame view.

Thin wrappers over `aegean.core.corpus.Corpus.to_dataframe`. pandas is the ``[data]`` extra;
Parquet additionally needs a parquet engine (the ``[parquet]`` extra — pyarrow).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._atomic import atomic_path

if TYPE_CHECKING:
    from ..core.corpus import Corpus


def _progress_dataframe(
    corpus: Corpus, level: str, progress: Callable[[int, int], None]
) -> Any:
    """Build the same DataFrame as ``Corpus.to_dataframe(level)`` while reporting
    per-DOCUMENT progress: ``progress(done, total)`` fires once after each document,
    with ``total`` the document count (a 57k-document / 4.4M-token DDbDP export is
    otherwise ~140 s of silence).

    Rows come from the same builders ``Corpus.to_dataframe`` uses, so the two paths
    describe a document or a token identically by construction; only the outer loop
    differs, because per-document completion has to be observable. The byte-identity
    tests pin the outputs together."""
    import pandas as pd  # lazy, optional [data] extra

    from ..core.corpus import _document_row, _token_blocks, _token_row
    from ..core.model import TokenKind

    docs = corpus.documents
    total = len(docs)
    if level == "document":
        rows: list[dict[str, Any]] = []
        for i, d in enumerate(docs, 1):
            rows.append(_document_row(d))
            progress(i, total)
        return pd.DataFrame(rows)

    if level in ("token", "word"):
        want_word = level == "word"
        form_state, alignment = _token_blocks(docs, want_word)
        rows = []
        for i, d in enumerate(docs, 1):
            for tok in d.tokens:
                if want_word and tok.kind is not TokenKind.WORD:
                    continue
                rows.append(_token_row(d, tok, form_state=form_state, alignment=alignment))
            progress(i, total)
        return pd.DataFrame(rows)

    raise ValueError(f"level must be 'document', 'token', or 'word'; got {level!r}")


def to_csv(
    corpus: Corpus,
    path: str | Path,
    *,
    level: str = "document",
    progress: Callable[[int, int], None] | None = None,
) -> None:
    """Write the corpus's ``level`` DataFrame (``"document"``/``"token"``/``"word"``) to CSV.

    ``progress``, when given, is called ``progress(done, total)`` once per document as the
    rows are generated (``total`` is the document count) so a very large export is not
    silent; the default (``None``) is the byte-identical original path."""
    # temp+replace so a failed/interrupted write never truncates a prior export
    if progress is None:
        with atomic_path(path) as tmp:
            corpus.to_dataframe(level).to_csv(tmp, index=False)
        return
    df = _progress_dataframe(corpus, level, progress)  # rows built (progress fires) then written
    with atomic_path(path) as tmp:
        df.to_csv(tmp, index=False)


def to_parquet(
    corpus: Corpus,
    path: str | Path,
    *,
    level: str = "document",
    progress: Callable[[int, int], None] | None = None,
) -> None:
    """Write the corpus's ``level`` DataFrame to Parquet (needs a parquet engine).

    ``progress`` (``progress(done, total)`` per document, ``total`` = document count) covers
    the row-generation phase only: Parquet buffers the whole DataFrame before its single
    write call, so the final progress call lands at ``(total, total)`` and the write follows.
    The default (``None``) is the byte-identical original path."""
    if progress is None:
        df = corpus.to_dataframe(level)
    else:
        df = _progress_dataframe(corpus, level, progress)
    try:
        with atomic_path(path) as tmp:
            df.to_parquet(tmp, index=False)
    except ImportError as e:  # no parquet engine (pyarrow/fastparquet) installed
        raise ImportError(
            "Parquet export needs a parquet engine: pip install 'pyaegean[parquet]'"
        ) from e
