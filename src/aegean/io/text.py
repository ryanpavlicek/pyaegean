"""Import a user's own text into the corpus model.

The export side of `aegean.io` turns a `Corpus` into CSV/Parquet/EpiDoc; this is the
*import* side for plain material. ``from_text`` / ``from_text_file`` / ``from_text_dir`` /
``from_csv`` build a real `Corpus` (with the full filter/query/analyse/export API) from a
string, a ``.txt`` file, a folder of text files, or a CSV — so someone with their own
passage of Greek can analyse it without writing the `Corpus.from_records` boilerplate by
hand. Greek/Koine text is run through the Greek word tokenizer; other scripts split on
whitespace. Everything is stdlib — importing this module pulls no heavy dependency.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # keep this module import-clean
    from ..core.corpus import Corpus

_SPLITS = ("whole", "paragraph", "line")


def _whitespace_words(s: str) -> list[str]:
    return s.split()


def _word_tokenizer(script_id: str) -> Callable[[str], list[str]]:
    """The right word tokenizer for a script: the Greek tokenizer for alphabetic Greek
    (strips punctuation, handles elision), plain whitespace splitting otherwise."""
    if script_id in ("greek", "nt"):
        from ..greek.tokenize import tokenize_words

        return tokenize_words
    return _whitespace_words


def _segments(text: str, split: str) -> list[list[str]]:
    """Group a text's lines into documents: one document of all non-empty lines
    (``whole``), one per blank-line-separated block (``paragraph``), or one per
    non-empty line (``line``). Each document is a list of physical-line strings."""
    lines = text.splitlines()
    if split == "line":
        return [[ln] for ln in lines if ln.strip()]
    if split == "paragraph":
        docs: list[list[str]] = []
        cur: list[str] = []
        for ln in lines:
            if ln.strip():
                cur.append(ln)
            elif cur:
                docs.append(cur)
                cur = []
        if cur:
            docs.append(cur)
        return docs
    if split == "whole":
        nonempty = [ln for ln in lines if ln.strip()]
        return [nonempty] if nonempty else []
    raise ValueError(f"split must be one of {_SPLITS}, got {split!r}")


def _records_from_text(
    text: str, doc_id: str, split: str, tok: Callable[[str], list[str]], meta: dict[str, str] | None
) -> list[dict[str, Any]]:
    blocks = _segments(text, split)
    multi = len(blocks) > 1
    records: list[dict[str, Any]] = []
    for i, block in enumerate(blocks, start=1):
        records.append(
            {
                "id": f"{doc_id}:{i}" if multi else doc_id,
                "lines": [tok(line) for line in block],
                "meta": dict(meta) if meta else {},
            }
        )
    return records


def _provenance(source: str, note: str) -> Any:
    from ..core.provenance import Provenance

    return Provenance(source=source, license="user-supplied", notes=(note,))


def from_text(
    text: str,
    *,
    script_id: str = "greek",
    doc_id: str = "text",
    split: str = "whole",
    meta: dict[str, str] | None = None,
) -> "Corpus":
    """Build a `Corpus` from a raw string.

    ``split`` controls how the text becomes documents: ``"whole"`` (default, one document),
    ``"paragraph"`` (one per blank-line-separated block), or ``"line"`` (one per line).
    Line breaks are preserved as physical lines. ``script_id`` picks the tokenizer (``"greek"``
    by default). Raises `ValueError` if the text has no content."""
    from ..core.corpus import Corpus

    records = _records_from_text(text, doc_id, split, _word_tokenizer(script_id), meta)
    if not records:
        raise ValueError("no text to import (the input was empty or all blank)")
    prov = _provenance(
        f"Imported text ({doc_id})",
        f"imported via aegean.io.from_text (split={split}); {len(records)} document(s)",
    )
    return Corpus.from_records(records, script_id=script_id, provenance=prov)


def from_text_file(
    path: str | Path,
    *,
    script_id: str = "greek",
    split: str = "whole",
    doc_id: str | None = None,
    encoding: str = "utf-8",
    meta: dict[str, str] | None = None,
) -> "Corpus":
    """Build a `Corpus` from a plain-text file. The document id defaults to the file's
    stem. See :func:`from_text` for ``split``. Raises `FileNotFoundError` if missing."""
    from ..core.corpus import Corpus

    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"no such text file: {p}")
    records = _records_from_text(
        p.read_text(encoding=encoding), doc_id or p.stem, split, _word_tokenizer(script_id), meta
    )
    if not records:
        raise ValueError(f"no text to import from {p} (empty or all blank)")
    prov = _provenance(
        f"Imported text file: {p.name}",
        f"imported via aegean.io.from_text_file (split={split}); {len(records)} document(s)",
    )
    return Corpus.from_records(records, script_id=script_id, provenance=prov)


def from_text_dir(
    path: str | Path,
    *,
    script_id: str = "greek",
    glob: str = "*.txt",
    split: str = "whole",
    encoding: str = "utf-8",
) -> "Corpus":
    """Build one `Corpus` from a folder of text files (one or more documents per file,
    per ``split``). Document ids come from each file's stem (de-duplicated with a ``#n``
    suffix on collision). Raises `NotADirectoryError` / `FileNotFoundError` as appropriate."""
    from ..core.corpus import Corpus

    d = Path(path)
    if not d.is_dir():
        raise NotADirectoryError(f"not a directory: {d}")
    files = sorted(p for p in d.glob(glob) if p.is_file())
    if not files:
        raise FileNotFoundError(f"no files matching {glob!r} in {d}")
    tok = _word_tokenizer(script_id)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for f in files:
        for rec in _records_from_text(f.read_text(encoding=encoding), f.stem, split, tok, None):
            rid = str(rec["id"])
            base, n = rid, 2
            while rid in seen:
                rid = f"{base}#{n}"
                n += 1
            seen.add(rid)
            rec["id"] = rid
            records.append(rec)
    if not records:
        raise ValueError(f"no text to import under {d}")
    prov = _provenance(
        f"Imported text directory: {d.name}",
        f"imported {len(files)} file(s) via aegean.io.from_text_dir (split={split})",
    )
    return Corpus.from_records(records, script_id=script_id, provenance=prov)


def from_csv(
    path: str | Path,
    *,
    text_col: str = "text",
    id_col: str | None = None,
    script_id: str = "greek",
    meta_cols: Sequence[str] = (),
    encoding: str = "utf-8",
) -> "Corpus":
    """Build a `Corpus` from a CSV file. ``text_col`` holds each row's text; ``id_col``
    (optional) holds its document id (otherwise ids are ``<stem>:<row>``). ``meta_cols``
    names columns to carry into document metadata (recognized: site/period/scribe/support/
    findspot/name). Raises `ValueError` if ``text_col`` is absent."""
    import csv

    from ..core.corpus import Corpus

    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"no such CSV file: {p}")
    tok = _word_tokenizer(script_id)
    records: list[dict[str, Any]] = []
    with p.open(encoding=encoding, newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or text_col not in reader.fieldnames:
            raise ValueError(
                f"CSV {p.name} has no column {text_col!r}; columns: {reader.fieldnames}"
            )
        for n, row in enumerate(reader, start=1):
            rid = str(row[id_col]) if id_col and row.get(id_col) else f"{p.stem}:{n}"
            meta = {c: row[c] for c in meta_cols if c in row and row[c]}
            records.append({"id": rid, "words": tok(row.get(text_col) or ""), "meta": meta})
    if not records:
        raise ValueError(f"no rows to import from {p}")
    prov = _provenance(
        f"Imported CSV: {p.name}", f"imported {len(records)} row(s) via aegean.io.from_csv"
    )
    return Corpus.from_records(records, script_id=script_id, provenance=prov)
