"""Import a user's own text into the corpus model.

The export side of `aegean.io` turns a `Corpus` into CSV/Parquet/EpiDoc; this is the
*import* side for plain material. ``from_text`` / ``from_text_file`` / ``from_text_dir`` /
``from_csv`` build a real `Corpus` (with the full filter/query/analyse/export API) from a
string, a ``.txt`` file, a folder of text files, or a CSV — so someone with their own
passage of Greek can analyse it without writing the `Corpus.from_records` boilerplate by
hand. The default preserves decoded source text and aligned tokens, including punctuation,
foreign text, and numerals. ``Document.words`` / ``Corpus.iter_words()`` give the linguistic
word view. ``token_view="words"`` explicitly selects the former, lossy import behavior.
Everything is stdlib — importing this module pulls no heavy dependency.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from collections import Counter
from bisect import bisect_right
from dataclasses import replace
import hashlib
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any
import unicodedata

if TYPE_CHECKING:  # keep this module import-clean
    from ..core.corpus import Corpus

_SPLITS = ("whole", "paragraph", "line")
_TOKEN_VIEWS = ("all", "words")
# A decoded UTF-8 BOM. str.strip() does not remove it (it is not whitespace), so a BOM
# left in place becomes part of the first token of the text.
_BOM = "\ufeff"


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


def _source_segments(text: str, split: str) -> list[str]:
    """Partition decoded content without discarding separators or blank lines.

    Leading blank lines belong to the first document; separators and trailing blanks to
    the preceding document. Joining the snapshots in document order reconstructs the
    content even for paragraph/line splitting. Offsets are local to each snapshot.
    """
    if split not in _SPLITS:
        raise ValueError(f"split must be one of {_SPLITS}, got {split!r}")
    if not text.strip():
        return []
    if split == "whole":
        return [text]
    starts: list[int] = []
    offset = 0
    after_blank = True
    for line in text.splitlines(keepends=True):
        if line.strip():
            if split == "line" or after_blank:
                starts.append(offset)
            after_blank = False
        else:
            after_blank = True
        offset += len(line)
    starts[0] = 0
    return [text[start:end] for start, end in zip(starts, [*starts[1:], len(text)])]


def _outside_greek_kind(character: str) -> Any:
    from ..core.model import TokenKind

    category = unicodedata.category(character)
    if category.startswith("N"):
        return TokenKind.NUMERAL
    if category.startswith("P"):
        return TokenKind.PUNCT
    return TokenKind.UNKNOWN


def _aligned_tokens(text: str, document_id: str, script_id: str) -> list[Any]:
    """Use the existing alignment model, refining the Greek tokenizer's foreign chunks.

    The analysis tokenizer intentionally calls every non-Greek chunk PUNCT. Import is a
    preservation boundary: foreign text is UNKNOWN (excluded from Greek word counts),
    and Unicode number characters are NUMERAL, without asserting a numeric value.
    """
    from ..core.model import SourceAlignment, Token, TokenKind
    from ..core.numerals import parse_value

    if script_id in ("greek", "nt"):
        from ..greek.tokenize import tokenize_aligned

        original = tokenize_aligned(text, document_id=document_id)
        tokens: list[Token] = []
        for token in original:
            if token.kind is TokenKind.WORD:
                # The analysis tokenizer allows combining marks as word characters.
                # Without a Greek base they are evidence, not an extra Greek word.
                has_greek_base = any(
                    unicodedata.category(character) in {"Lu", "Ll", "Lt", "Lo"}
                    and "GREEK" in unicodedata.name(character, "")
                    for character in token.text
                )
                if not has_greek_base:
                    alignment = token.alignment
                    assert alignment is not None
                    marks_only = all(unicodedata.category(character).startswith("M") for character in token.text)
                    previous = tokens[-1] if tokens else None
                    if (
                        marks_only and previous is not None and previous.kind is TokenKind.UNKNOWN
                        and previous.alignment is not None
                        and previous.alignment.end_char == alignment.start_char
                        and unicodedata.category(previous.text[-1]).startswith(("L", "M"))
                    ):
                        text_with_marks = previous.text + token.text
                        normalized = unicodedata.normalize("NFC", text_with_marks)
                        combined = replace(
                            previous.alignment,
                            source_token_id=f"{previous.alignment.source_token_id}:marks:{alignment.end_char}",
                            original_text=text_with_marks, end_char=alignment.end_char,
                            normalized_text=normalized,
                            normalization_ops=("unicode:nfc",) if normalized != text_with_marks else (),
                        )
                        tokens[-1] = replace(previous, text=text_with_marks, alignment=combined)
                    else:
                        tokens.append(replace(
                            token, kind=TokenKind.UNKNOWN, position=len(tokens),
                            annotations={"import_role": "unattached-mark" if marks_only else "no-Greek-base", "counting_exclusion": "no Greek letter base"},
                        ))
                    continue
                tokens.append(replace(token, position=len(tokens)))
                continue
            alignment = token.alignment
            assert alignment is not None
            start = 0
            while start < len(token.text):
                kind = _outside_greek_kind(token.text[start])
                end = start + 1
                while end < len(token.text) and _outside_greek_kind(token.text[end]) is kind:
                    end += 1
                piece = token.text[start:end]
                normalized = unicodedata.normalize("NFC", piece)
                refined = replace(
                    alignment,
                    source_token_id=f"{alignment.source_token_id}:piece:{start}-{end}",
                    original_text=piece,
                    start_char=alignment.start_char + start,
                    end_char=alignment.start_char + end,
                    whitespace_before=alignment.whitespace_before if start == 0 else "",
                    normalized_text=normalized,
                    normalization_ops=("unicode:nfc",) if normalized != piece else (),
                )
                annotations = {}
                if kind is TokenKind.UNKNOWN:
                    annotations = {"import_role": "non-Greek", "counting_exclusion": "non-Greek word view"}
                tokens.append(Token(piece, kind, position=len(tokens), alignment=refined, annotations=annotations))
                start = end
        return tokens

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    tokens = []
    previous_end = 0
    for ordinal, match in enumerate(re.finditer(r"\S+", text)):
        piece = match.group()
        normalized = unicodedata.normalize("NFC", piece)
        alignment = SourceAlignment(
            document_id=document_id, sentence_id=None,
            source_token_id=f"{document_id}:{digest}:{ordinal}:{match.start()}-{match.end()}",
            original_text=piece, start_char=match.start(), end_char=match.end(),
            whitespace_before=text[previous_end:match.start()], normalized_text=normalized,
            normalization_ops=("unicode:nfc",) if normalized != piece else (),
        )
        tokens.append(Token(
            piece, TokenKind.NUMERAL if parse_value(piece) is not None else TokenKind.WORD,
            signs=tuple(piece.split("-")) if "-" in piece else (),
            position=ordinal, alignment=alignment,
        ))
        previous_end = match.end()
    return tokens


def _import_documents(
    text: str, doc_id: str, split: str, script_id: str,
    meta: dict[str, str] | None, token_view: str,
) -> tuple[list[Any], tuple[str, ...]]:
    from ..core.corpus import Corpus
    from ..core.model import Document, DocumentMeta, TokenKind

    if token_view not in _TOKEN_VIEWS:
        raise ValueError(f"token_view must be one of {_TOKEN_VIEWS}, got {token_view!r}")
    bom_count = len(text) - len(text.lstrip(_BOM))
    text = text.lstrip(_BOM)
    blocks = _source_segments(text, split)
    multi = len(blocks) > 1
    docs = []
    excluded: Counter[str] = Counter()
    for ordinal, source in enumerate(blocks, 1):
        rid = f"{doc_id}:{ordinal}" if multi else doc_id
        tokens = _aligned_tokens(source, rid, script_id)
        starts = []
        offset = 0
        for line in source.splitlines(keepends=True):
            starts.append(offset)
            offset += len(line)
        lines: list[list[int]] = [[] for _ in starts]
        for index, token in enumerate(tokens):
            assert token.alignment is not None
            line_no = bisect_right(starts, token.alignment.start_char) - 1
            tokens[index] = replace(token, line_no=line_no)
            lines[line_no].append(index)
            if token.kind is not TokenKind.WORD:
                excluded[token.kind.value] += 1
        m = meta or {}
        doc = Document(
            rid, script_id, tokens, lines, source_text=source,
            meta=DocumentMeta(
                site=m.get("site", ""), support=m.get("support", ""),
                scribe=m.get("scribe", ""), findspot=m.get("findspot", ""),
                period=m.get("period", ""), name=m.get("name", ""),
            ),
        )
        doc.validate_source_alignment()
        docs.append(doc)
    notes = [f"token_view={token_view}; preserved-source word view excludes " + (
        ", ".join(f"{count} {kind}" for kind, count in sorted(excluded.items())) or "no tokens"
    )]
    if bom_count:
        notes.append(f"removed {bom_count} leading Unicode BOM signature(s) before importing content")
    if token_view == "words":
        records = _records_from_text(text, doc_id, split, _word_tokenizer(script_id), meta)
        legacy = Corpus.from_records(records, script_id=script_id).documents
        retained = sum(len(doc.tokens) for doc in legacy)
        total = sum(len(doc.tokens) for doc in docs)
        lost_characters = sum(not character.isspace() for character in text) - sum(
            len(token.text) for doc in legacy for token in doc.tokens
        )
        notes.append(
            f"legacy word-only import: excluded {total - retained} source token(s); "
            f"{lost_characters} non-whitespace source character(s) omitted; "
            "raw source text, whitespace, and source spans are unavailable; use token_view='all' "
            "and Document.words / Corpus.iter_words() for a source-preserving word view"
        )
        return legacy, tuple(notes)
    notes.append("decoded source content and character spans preserved; offsets are document-local")
    return docs, tuple(notes)


def _read_text(path: Path, encoding: str) -> str:
    # Unlike Path.read_text(), retain CRLF/CR rather than translating them to LF.
    with path.open(encoding=encoding, newline="") as stream:
        return stream.read()


def _provenance(source: str, *notes: str) -> Any:
    from ..core.provenance import Provenance

    return Provenance(source=source, license="user-supplied", notes=tuple(notes))


def from_text(
    text: str,
    *,
    script_id: str = "greek",
    doc_id: str = "text",
    split: str = "whole",
    meta: dict[str, str] | None = None,
    token_view: str = "all",
) -> "Corpus":
    """Build a `Corpus` from a raw string.

    ``split`` controls how the text becomes documents: ``"whole"`` (default, one document),
    ``"paragraph"`` (one per blank-line-separated block), or ``"line"`` (one per line).
    ``token_view="all"`` preserves decoded content in ``Document.source_text`` and gives
    every token an exact ``SourceAlignment``. Greek words are WORD; foreign text is
    UNKNOWN, numbers NUMERAL, punctuation PUNCT. ``Document.words`` / ``Corpus.iter_words()``
    explicitly exclude those other kinds. Blank lines and separators remain in the
    snapshots; joining the documents' source text reconstructs the content after splitting.

    ``token_view="words"`` opts into the former word-only import, without raw text or
    spans; exclusions are reported in provenance. This compatibility mode retains the
    former token positions and physical-line behavior. Leading Unicode BOM signatures
    are removed and reported. Raises `ValueError` if the content is empty or all blank."""
    from ..core.corpus import Corpus

    docs, notes = _import_documents(text, doc_id, split, script_id, meta, token_view)
    if not docs:
        raise ValueError("no text to import (the input was empty or all blank)")
    prov = _provenance(
        f"Imported text ({doc_id})",
        f"imported via aegean.io.from_text (split={split}); {len(docs)} document(s)",
        *notes,
    )
    return Corpus(docs, script_id=script_id, provenance=prov)


def from_text_file(
    path: str | Path,
    *,
    script_id: str = "greek",
    split: str = "whole",
    doc_id: str | None = None,
    encoding: str = "utf-8-sig",
    meta: dict[str, str] | None = None,
    token_view: str = "all",
) -> "Corpus":
    """Build a `Corpus` from a plain-text file. The document id defaults to the file's
    stem. See :func:`from_text` for ``split``. Raises `FileNotFoundError` if missing.

    The default ``utf-8-sig`` encoding drops a leading UTF-8 BOM (an editor or a Windows
    tool that writes one) instead of leaving it attached to the first word, and reads a
    BOM-less UTF-8 file identically."""
    from ..core.corpus import Corpus

    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"no such text file: {p}")
    docs, notes = _import_documents(
        _read_text(p, encoding), doc_id or p.stem, split, script_id, meta, token_view
    )
    if not docs:
        raise ValueError(f"no text to import from {p} (empty or all blank)")
    prov = _provenance(
        f"Imported text file: {p.name}",
        f"imported via aegean.io.from_text_file (split={split}, encoding={encoding}); {len(docs)} document(s)",
        *notes,
    )
    return Corpus(docs, script_id=script_id, provenance=prov)


def from_text_dir(
    path: str | Path,
    *,
    script_id: str = "greek",
    glob: str = "*.txt",
    split: str = "whole",
    encoding: str = "utf-8-sig",
    token_view: str = "all",
) -> "Corpus":
    """Build one `Corpus` from a folder of text files (one or more documents per file,
    per ``split``). Document ids come from each file's stem (de-duplicated with a ``#n``
    suffix on collision). Raises `NotADirectoryError` / `FileNotFoundError` as appropriate.

    Files are read as ``utf-8-sig`` by default, so a BOM one of them carries does not
    become part of its first word."""
    from ..core.corpus import Corpus

    d = Path(path)
    if not d.is_dir():
        raise NotADirectoryError(f"not a directory: {d}")
    files = sorted(p for p in d.glob(glob) if p.is_file())
    if not files:
        raise FileNotFoundError(f"no files matching {glob!r} in {d}")
    docs = []
    notes: list[str] = []
    seen: set[str] = set()
    for f in files:
        imported, report = _import_documents(
            _read_text(f, encoding), f.stem, split, script_id, None, token_view
        )
        notes.extend(f"{f.name}: {note}" for note in report)
        for doc in imported:
            rid = doc.id
            base, n = rid, 2
            while rid in seen:
                rid = f"{base}#{n}"
                n += 1
            seen.add(rid)
            if rid != doc.id:
                # Source identities include the owning document id; regenerate them when
                # a filename collision changes that identity.
                if doc.source_text is not None:
                    renamed, _ = _import_documents(doc.source_text, rid, "whole", script_id, None, token_view)
                    doc = renamed[0]
                else:
                    doc.id = rid
            docs.append(doc)
    if not docs:
        raise ValueError(f"no text to import under {d}")
    prov = _provenance(
        f"Imported text directory: {d.name}",
        f"imported {len(files)} file(s) via aegean.io.from_text_dir (split={split})",
        f"decoded files with encoding={encoding}",
        *notes,
    )
    return Corpus(docs, script_id=script_id, provenance=prov)


def from_csv(
    path: str | Path,
    *,
    text_col: str = "text",
    id_col: str | None = None,
    script_id: str = "greek",
    meta_cols: Sequence[str] = (),
    encoding: str = "utf-8-sig",
    token_view: str = "all",
) -> "Corpus":
    """Build a `Corpus` from a CSV file. ``text_col`` holds each row's text; ``id_col``
    (optional) holds its document id (otherwise ids are ``<stem>:<row>``). ``meta_cols``
    names columns to carry into document metadata (recognized: site/period/scribe/support/
    findspot/name). Raises `ValueError` if ``text_col`` is absent.

    A row whose ``text_col`` is empty or blank yields no document, the way a blank line
    yields no document on the text-file path: a zero-token document would sit in the corpus
    contributing nothing to any count, search, or export. The provenance records how many
    rows were skipped, and a CSV in which *every* row is blank raises `ValueError` rather
    than returning a corpus of empty documents. Text that is present but yields no tokens
    under ``script_id`` is a different case and keeps its document, as the text path does.

    The default ``utf-8-sig`` encoding transparently strips a leading UTF-8 BOM (Excel
    writes one), so the first column name is not silently prefixed with it; it reads a
    BOM-less UTF-8 file identically."""
    import csv

    from ..core.corpus import Corpus

    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"no such CSV file: {p}")
    docs = []
    reports: list[str] = []
    with p.open(encoding=encoding, newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or text_col not in reader.fieldnames:
            raise ValueError(
                f"CSV {p.name} has no column {text_col!r}; columns: {reader.fieldnames}"
            )
        rows = 0
        skipped = 0
        for n, row in enumerate(reader, start=1):
            rows += 1
            text = row.get(text_col) or ""
            if not text.strip():
                # The text-file path drops a blank line rather than making a document out
                # of it; a row with nothing in its text cell is the same case. (Text that
                # is present but yields no tokens under this script is NOT this case: the
                # row carries text, and the text path keeps such a line too.)
                skipped += 1
                continue
            rid = str(row[id_col]) if id_col and row.get(id_col) else f"{p.stem}:{n}"
            meta = {c: row[c] for c in meta_cols if c in row and row[c]}
            imported, report = _import_documents(text, rid, "whole", script_id, meta, token_view)
            if token_view == "words":
                # CSV's former importer treated a multiline cell as one flat token line.
                imported = Corpus.from_records([
                    {"id": rid, "words": _word_tokenizer(script_id)(text.lstrip(_BOM)), "meta": meta},
                ], script_id=script_id).documents
            docs.extend(imported)
            reports.extend(f"row {n}: {note}" for note in report)
    if not docs:
        if rows:
            raise ValueError(
                f"no text to import from {p}: all {rows} row(s) have an empty "
                f"{text_col!r} column (is that the column holding the text?)"
            )
        raise ValueError(f"no rows to import from {p}")
    notes = [f"imported {len(docs)} row(s) via aegean.io.from_csv", *reports]
    if skipped:
        notes.append(f"skipped {skipped} row(s) with an empty {text_col!r} column")
    prov = _provenance(f"Imported CSV: {p.name}", *notes)
    return Corpus(docs, script_id=script_id, provenance=prov)
