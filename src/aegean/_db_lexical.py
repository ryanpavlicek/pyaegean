"""Lexical search index and SQLite FTS/lexical query engine for :mod:`aegean.db`."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

from . import db as _db
from .core.model import ReadingStatus, Token, TokenKind
from .core.word_views import WordView
from .db import (
    _check_schema_version,
    _corpus_db_error,
    _form_state_from_json,
    _has_column,
)

def _fold(text: str) -> str:
    """Case-fold for search WITHOUT expanding the iota subscript.

    ``str.casefold`` decomposes the ypogegrammeni family (``ᾳ`` becomes ``αι``), which
    merges two different grammatical forms: a dative singular ``ἐκκλησίᾳ`` compared equal
    to the nominative plural ``ἐκκλησίαι``, and it was a *substring* of ``ἐκκλησίαις``.
    The iota subscript is a diacritic and the documented contract is that diacritics have
    to match, so lowercase and fold only the final sigma, as the docstring describes."""
    return text.lower().replace("ς", "σ")


_LEXICAL_STORAGE_VERSION = 1
# These bit assignments are part of lexical semantics version 1.
_READING_BITS = {
    ReadingStatus.CERTAIN: 1, ReadingStatus.UNCLEAR: 2,
    ReadingStatus.RESTORED: 4, ReadingStatus.LOST: 8,
}
_LEXICAL_COLUMNS = {
    "surface": "surface_key", "normalized": "normalized_key",
    "lemma": "lemma_key", None: "legacy_key",
}
_LEXICAL_SCHEMA = {
    "token_lexical_keys": (
        "CREATE TABLE token_lexical_keys (source_order INTEGER PRIMARY KEY, "
        "doc_id TEXT NOT NULL, position, original_text TEXT NOT NULL, "
        "surface_key TEXT, normalized_key TEXT, lemma_key TEXT, legacy_key TEXT NOT NULL, "
        "status_mask INTEGER NOT NULL)"
    ),
    "lexical_index_state": (
        "CREATE TABLE lexical_index_state (id INTEGER PRIMARY KEY CHECK (id = 1), "
        "storage_version INTEGER NOT NULL, semantics_version TEXT, "
        "source_generation INTEGER NOT NULL, indexed_generation INTEGER, indexed_tokens INTEGER)"
    ),
}
for _view, _column in _LEXICAL_COLUMNS.items():
    _index_name = "idx_lexical_" + (_view or "legacy")
    _LEXICAL_SCHEMA[_index_name] = (
        f"CREATE INDEX {_index_name} ON token_lexical_keys"
        f"({_column}, source_order, status_mask) WHERE {_column} IS NOT NULL"
    )
for _event in ("INSERT", "UPDATE", "DELETE"):
    _name = "lexical_source_" + _event.lower()
    _LEXICAL_SCHEMA[_name] = (
        f"CREATE TRIGGER {_name} AFTER {_event} ON tokens BEGIN "
        "UPDATE lexical_index_state SET source_generation = source_generation + 1 WHERE id = 1; END"
    )
    _name = "lexical_keys_" + _event.lower()
    _LEXICAL_SCHEMA[_name] = (
        f"CREATE TRIGGER {_name} AFTER {_event} ON token_lexical_keys BEGIN "
        "UPDATE lexical_index_state SET indexed_generation = NULL "
        "WHERE id = 1 AND indexed_generation IS NOT NULL; END"
    )
del _view, _column, _index_name, _event, _name


def _lexical_semantics_version() -> str:
    import unicodedata

    # Unicode lowercasing/NFC tables can differ between Python runtimes.
    return "lexical-1;unicode=" + unicodedata.unidata_version


def _lexical_objects(conn: sqlite3.Connection) -> dict[str, str]:
    names = tuple(_LEXICAL_SCHEMA)
    return dict(conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE name IN (" + ",".join("?" for _ in names) + ")",
        names,
    ))


def _same_schema(actual: str, expected: str) -> bool:
    return " ".join(actual.split()) == " ".join(expected.split())


def _lexical_index_status(conn: sqlite3.Connection) -> dict[str, Any]:
    """Inspect only small metadata/schema objects, within the caller's snapshot."""
    expected = _db._lexical_semantics_version()
    result: dict[str, Any] = {
        "state": "absent", "semantics_version": None, "expected_semantics_version": expected,
        "source_generation": None, "indexed_generation": None, "indexed_tokens": None,
        "reason": "index has not been built",
    }
    objects = _lexical_objects(conn)
    if not objects:
        return result
    for name, sql in objects.items():
        if not isinstance(sql, str) or not _same_schema(sql, _LEXICAL_SCHEMA[name]):
            result.update(state="unsupported", reason=f"unexpected index schema object: {name}")
            return result
    if "lexical_index_state" in objects:
        row = conn.execute(
            "SELECT storage_version, semantics_version, source_generation, "
            "indexed_generation, indexed_tokens FROM lexical_index_state WHERE id = 1"
        ).fetchone()
        if row is not None:
            storage, semantics, source, indexed, count = row
            result.update(semantics_version=semantics, source_generation=source,
                          indexed_generation=indexed, indexed_tokens=count)
            if storage != _LEXICAL_STORAGE_VERSION:
                result.update(state="unsupported", reason="unsupported lexical storage version")
                return result
            if (not isinstance(source, int) or source < 0
                    or (indexed is not None and (not isinstance(indexed, int) or indexed < 0))
                    or (count is not None and (not isinstance(count, int) or count < 0))):
                result.update(state="unsupported", reason="invalid index generation metadata")
                return result
    missing = set(_LEXICAL_SCHEMA) - objects.keys()
    if missing:
        result.update(state="stale", reason="missing index schema objects: " + ", ".join(sorted(missing)))
    elif result["semantics_version"] != expected:
        result.update(state="stale", reason="lexical comparison semantics have changed")
    elif result["indexed_generation"] is None or result["indexed_tokens"] is None:
        result.update(state="stale", reason="index rows changed or no complete build is recorded")
    elif result["source_generation"] != result["indexed_generation"]:
        result.update(state="stale", reason="source token rows have changed")
    else:
        result.update(state="ready", reason="index matches source generation and comparison semantics")
    return result


def lexical_index_status(path: str | Path) -> dict[str, Any]:
    """Report an exact-search index's state without writing or scanning token rows.

    ``state`` is ``absent`` before an explicit build, ``ready`` when its source
    generation and lexical/Unicode semantics agree, ``stale`` after source/index
    changes, or ``unsupported`` for an unrecognized storage structure. Only a
    ready index is used. ``indexed_tokens`` describes the last complete build,
    including nonword tokens retained for status-only searches.
    """
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
        conn.execute("BEGIN")
        _check_schema_version(dict(conn.execute("SELECT key, value FROM meta")))
        # An arbitrary SQLite file with a meta table is not a corpus database.
        conn.execute("SELECT text, kind, status, annotations FROM tokens LIMIT 0")
        return _db._lexical_index_status(conn)
    except sqlite3.Error as exc:
        raise _corpus_db_error(path, exc) from exc
    finally:
        if conn is not None:
            conn.close()


def _lexical_token(
    doc_id: Any, position: Any, text: Any, kind: Any, status: Any,
    annotations: Any, raw_form: Any,
) -> Token:
    context = f"{doc_id}, position {position}"
    try:
        values = json.loads(annotations or "{}")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError(f"malformed token annotations in {context}: invalid JSON") from exc
    if not isinstance(values, dict):
        raise ValueError(f"malformed token annotations in {context}: expected a JSON object")
    try:
        form = _form_state_from_json(raw_form, context=context)
    except RecursionError as exc:
        raise ValueError(f"malformed token form_state in {context}: invalid JSON") from exc
    return Token(
        text=str(text), kind=TokenKind(kind), status=ReadingStatus(status or "certain"),
        annotations=values, form_state=form,
    )


def build_lexical_index(
    path: str | Path, *, progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Explicitly build or refresh exact lexical keys on an existing writable database.

    Uses the same surface/normalized/lemma and whole-token/segment status rules
    as `search`. A single write transaction replaces derived rows and their
    generation marker; rollback, interruption, and competing writers cannot
    publish partial keys. Live schemas are retained during refresh. Triggers
    invalidate the index on every token INSERT/UPDATE/DELETE, including external
    SQL; append/update requires another explicit refresh. Full corpus replacement
    produces a database without this optional index.

    Existing hosted databases continue to scan until explicitly indexed on a
    writable copy. ``progress(done, total)`` counts tokens; an exception from the
    callback rolls back the entire build. Returns `lexical_index_status` for the
    committed build. Read-only searches never call this function.
    """
    from .core.word_views import word_key

    target = Path(path).resolve()
    if not target.exists():
        raise FileNotFoundError(f"no database to index: {path} (build it first)")
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(target.as_uri() + "?mode=rw", uri=True, timeout=30)
        conn.execute("BEGIN IMMEDIATE")
        _check_schema_version(dict(conn.execute("SELECT key, value FROM meta")))
        form_column = "form_state_json" if _has_column(conn, "tokens", "form_state_json") else "NULL"
        rows = conn.execute(
            "SELECT rowid, doc_id, position, text, kind, status, annotations, "
            + form_column + " FROM tokens ORDER BY rowid"
        )
        objects = _lexical_objects(conn)
        for name, sql in objects.items():
            if not isinstance(sql, str) or not _same_schema(sql, _LEXICAL_SCHEMA[name]):
                raise ValueError(f"unsupported lexical index schema object: {name}")
        for name, sql in _LEXICAL_SCHEMA.items():
            if name not in objects:
                conn.execute(sql)
        conn.execute(
            "INSERT OR IGNORE INTO lexical_index_state"
            "(id, storage_version, source_generation) VALUES (1, ?, 0)",
            (_LEXICAL_STORAGE_VERSION,),
        )
        if _db._lexical_index_status(conn)["state"] == "unsupported":
            raise ValueError("unsupported lexical index storage or generation metadata")
        total = conn.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]
        conn.execute("DELETE FROM token_lexical_keys")

        def keys() -> Iterator[tuple[Any, ...]]:
            for done, row in enumerate(rows, start=1):
                rowid, doc_id, position, text, kind, status, annotations, raw_form = row
                token = _lexical_token(doc_id, position, text, kind, status, annotations, raw_form)
                mask = _READING_BITS[token.status]
                if token.form_state is not None:
                    for segment in token.form_state.segments:
                        mask |= _READING_BITS[segment.status]
                # Hidden source rowids can change under VACUUM without firing row
                # triggers. They record scan order, not an identity to join back to.
                yield (rowid, str(doc_id), position, token.text,
                       word_key(token, "surface"), word_key(token, "normalized"),
                       word_key(token, "lemma"), _fold(token.text), mask)
                if progress is not None:
                    progress(done, total)

        conn.executemany("INSERT INTO token_lexical_keys VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", keys())
        conn.execute(
            "UPDATE lexical_index_state SET semantics_version = ?, "
            "indexed_generation = source_generation, indexed_tokens = ? WHERE id = 1",
            (_db._lexical_semantics_version(), total),
        )
        result = _db._lexical_index_status(conn)
        conn.commit()
        return result
    except sqlite3.Error as exc:
        if "readonly" in str(exc).lower():
            raise ValueError(
                f"cannot build lexical index at {path}: database is read-only; use a writable copy"
            ) from exc
        raise _corpus_db_error(path, exc) from exc
    finally:
        if conn is not None:
            conn.close()


def _lexical_search_sql(view: WordView | None) -> str:
    column = _LEXICAL_COLUMNS[view]
    # Stored source rowids record scan order. Returning the materialized payload
    # avoids joining to hidden rowids that VACUUM can renumber without row triggers.
    # Keep the partial-index predicate explicit: SQLite 3.45 cannot infer it for
    # the NOT NULL legacy column and otherwise scans the entire key table.
    return (
        "SELECT k.doc_id, k.position, k.original_text FROM token_lexical_keys AS k "
        f"WHERE k.{column} IS NOT NULL AND k.{column} = ? "
        "AND (k.status_mask & ?) = k.status_mask "
        "ORDER BY k.source_order LIMIT ?"
    )


def search(path: str | Path, query: str, *, limit: int = 50, mode: str = "token",
           view: WordView | None = None, statuses: Iterable[ReadingStatus | str] | None = None,
           ) -> list[tuple[str, int | None, str]]:
    """Search a SQLite corpus's tokens; returns ``(doc_id, position, text)`` hits.

    ``position`` is the token's stored position, or ``None`` for a token saved without
    one (a supported state since 0.19.4: an appended token keeps ``position=None``).

    ``mode="token"`` (default) matches a **whole token literally**: the query must equal the
    token, so a transliteration with hyphens (``KU-RO``, ``A-DU``) matches only that token and
    never a longer token that merely contains it (``KU-RO`` does not match ``PO-TO-KU-RO``). It
    uses the FTS5 index when present (then confirms the exact match); without FTS5 it falls
    back to an indexed exact-match query for an ASCII query, or a Python scan for a non-ASCII
    one (SQLite's ``NOCASE`` folds ASCII case only).

    ``mode="substring"`` matches the query as a **substring** of a token, so ``KU-RO`` also
    finds ``PO-TO-KU-RO`` — useful for tracing every token a sign-group occurs in. It folds
    case in Python (SQLite's ``LIKE`` also folds ASCII only) and therefore has to scan the
    token table: on the bundled 1,721-document Linear A corpus (6,406 tokens) that is
    around 9 ms warm, against around 2 ms for the same query in ``token`` mode. Both
    figures are machine-dependent; the substring cost is linear in the token count, so it
    scales with the corpus while the indexed whole-token match does not.

    Both modes fold case, Greek included (``ku-ro`` finds ``KU-RO``; ``λόγος`` finds
    ``ΛΌΓΟΣ``, final sigma folding with the rest). Diacritics still have to match:
    ``λογος`` does not find ``λόγος``.

    Explicit ``view='surface'``, ``'normalized'``, or ``'lemma'`` searches lexical
    WORD tokens using the same keys as ``Corpus.word_frequencies`` and
    ``Corpus.query``. Surface is case-sensitive; normalized/lemma use NFC,
    lowercase, and final-sigma folding, preserving diacritics/iota subscript.
    Lemma reads existing annotations only; missing lemmas do not match. Returned
    hits still contain the original token text. ``statuses`` selects whole tokens
    and every typed editorial segment. Exact searches use a ready index built with
    `build_lexical_index`, otherwise scan. Substring searches always scan. Omitting
    both options preserves the legacy indexed, case-insensitive search across all
    token kinds.

    ``limit`` caps the number of hits (default 50); zero or a negative value returns
    every match. The database is opened **read-only** (a sqlite ``mode=ro`` URI), so a
    search can never create or modify a file: a missing path or a non-SQLite file raises
    ``sqlite3.OperationalError`` / ``sqlite3.DatabaseError`` instead of leaving an empty
    database behind."""
    if mode not in {"token", "substring"}:
        raise ValueError(f"mode must be 'token' or 'substring', got {mode!r}")
    from .core.word_views import normalize_word, reading_statuses, token_selected, validate_view, word_key

    if view is not None:
        view = validate_view(view)
    selected = reading_statuses(statuses)
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    # A reader waits for a writer rather than failing. sqlite's default busy timeout is
    # 5 s, which a loaded machine can exhaust while an append commits, surfacing as
    # "database is locked" to a caller that only wanted to read. Searching is read-only
    # and idempotent, so waiting longer is always better than erroring.
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        # Index validity and candidate rows must belong to the same source snapshot.
        conn.execute("BEGIN")
        if view is not None or statuses is not None:
            _check_schema_version(dict(conn.execute("SELECT key, value FROM meta")))
            target = query if view == "surface" else (normalize_word(query) if view is not None else _fold(query))
            if mode == "token" and _db._lexical_index_status(conn)["state"] == "ready":
                mask = sum(_READING_BITS[status] for status in selected)
                return [(str(d), p, str(t)) for d, p, t in conn.execute(
                    _lexical_search_sql(view), (target, mask, limit if limit > 0 else -1),
                )]
            form_column = "form_state_json" if _has_column(conn, "tokens", "form_state_json") else "NULL"
            hits: list[tuple[str, int | None, str]] = []
            for doc_id, position, text, kind, status, annotations, raw_form in conn.execute(
                "SELECT doc_id, position, text, kind, status, annotations, "
                + form_column + " FROM tokens ORDER BY rowid"
            ):
                token = _lexical_token(doc_id, position, text, kind, status, annotations, raw_form)
                if not token_selected(token, selected):
                    continue
                key = word_key(token, view) if view is not None else _fold(token.text)
                if key is None:
                    continue
                if (key == target if mode == "token" else target in key):
                    hits.append((str(doc_id), position, token.text))
                    if 0 < limit <= len(hits):
                        break
            return hits
        target = _fold(query)
        out: list[tuple[str, int | None, str]] = []
        # position is an int, or None for a token stored without one (SQL NULL); keep it
        # as-is rather than int()-coercing, which would crash on the None case (0.19.9).
        if mode == "substring":
            for doc_id, position, text in conn.execute(
                "SELECT doc_id, position, text FROM tokens"
            ):
                if target in _fold(str(text)):
                    out.append((str(doc_id), position, str(text)))
                    if 0 < limit <= len(out):
                        break
            return out
        has_fts = bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tokens_fts'"
            ).fetchone()
        )
        # unicode61 drops everything that is not a letter/digit, so a query that is all
        # separators (a punctuation token like "·" or "—") tokenizes to an empty FTS phrase
        # and would match nothing; route those to the exact path, which finds the token. A
        # NUL in the query makes the FTS5 phrase parser raise ("unterminated string"), so it
        # is routed the same way (the token itself stores and matches fine on the exact path).
        fts_usable = has_fts and "\x00" not in query and any(ch.isalnum() for ch in query)
        if fts_usable:  # unicode61 folds Greek case, so the phrase query finds either case
            phrase = '"' + query.replace('"', '""') + '"'  # a literal FTS5 phrase, not syntax
            try:
                cur = conn.execute(
                    "SELECT doc_id, position, text FROM tokens_fts WHERE tokens_fts MATCH ?",
                    (phrase,),
                )
                rows = cur.fetchall()
            except sqlite3.OperationalError:
                # A concurrent append rebuilds the FTS index by dropping and recreating
                # it; a reader landing in that window cannot construct the vtable. The
                # exact-match paths below answer the same question, just slower.
                fts_usable = False
        if fts_usable:
            source: Any = rows
        elif query.isascii():  # NOCASE folds ASCII, which is all this query needs
            source = conn.execute(
                "SELECT doc_id, position, text FROM tokens WHERE text = ? COLLATE NOCASE",
                (query,),
            )
        else:  # a Greek (non-ASCII) query: scan, the casefold confirmation below matches
            source = conn.execute("SELECT doc_id, position, text FROM tokens")
        for doc_id, position, text in source:
            if _fold(str(text)) == target:  # FTS only narrows; confirm an exact token match
                out.append((str(doc_id), position, str(text)))
                if 0 < limit <= len(out):
                    break
        return out
    finally:
        conn.close()


