"""SQLite persistence for a `Corpus` — stdlib ``sqlite3`` only, so the core stays
dependency-free (the same precedent as ``aegean.cache``).

``to_sqlite`` / ``from_sqlite`` are a faithful, queryable round-trip: documents and tokens
are normalized into rows (so SQL and full-text search work over them), with the nested
structure (signs, alternate readings, annotations, line groupings, image refs, notes) kept
in JSON columns. Provenance and the sign inventory live in a small key/value ``meta`` table.
``search`` matches a whole token by default (an FTS5 phrase when available, else an indexed
exact-match query on ``tokens(text)``); ``mode="substring"`` is the opt-in within-token search
(a casefolded Python scan, since SQLite's ``LIKE`` folds ASCII case only). ``stream`` yields
documents lazily for a large DB-backed corpus without materializing it.
Explicit lexical searches can use materialized comparison keys built or refreshed with
``build_lexical_index``. Token writes invalidate these keys in the same transaction;
``lexical_index_status`` reports whether they can be used. Searches never build an index.

A corpus out of the database cites exactly like a corpus out of JSON — the provenance round-
trips, and a database grown with ``append=True`` records every appended corpus's provenance,
so the reloaded corpus cites them all. ``Corpus.to_sql`` / ``Corpus.from_sql`` are thin
wrappers over these functions.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

from ._log import get_logger
from .core.corpus import (
    Corpus,
    _document_from_dict,
    _document_to_dict,
    _inventory_from_dict,
    _inventory_to_dict,
    _provenance_from_dict,
    _provenance_to_dict,
)
from .core.model import Document, ReadingStatus, SourceAlignment, Token, TokenFormState, TokenKind
from .core.provenance import SCHEMA_VERSION, Provenance
from .core.word_views import WordView

__all__ = [
    "to_sqlite", "from_sqlite", "search", "stream", "build_lexical_index", "lexical_index_status",
]

_LOG = get_logger("db")

_REPLACEMENT_BUSY_TIMEOUT = 5.0

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE documents (
    doc_order INTEGER, id TEXT PRIMARY KEY, script_id TEXT, glyphs TEXT, transcription TEXT,
    translations TEXT, site TEXT, support TEXT, scribe TEXT, findspot TEXT, period TEXT,
    name TEXT, images TEXT, notes TEXT, lines TEXT, source_text TEXT
);
CREATE TABLE tokens (
    doc_id TEXT, token_order INTEGER, position INTEGER, line_no INTEGER, text TEXT, kind TEXT,
    glyphs TEXT, status TEXT, signs TEXT, alt TEXT, annotations TEXT, alignment TEXT,
    form_state_json TEXT
);
CREATE INDEX idx_tokens_doc ON tokens(doc_id);
CREATE INDEX idx_tokens_text ON tokens(text);
"""


def _build_fts(conn: sqlite3.Connection) -> None:
    """Create + populate an FTS5 index over token text, or no-op if FTS5 is unavailable.

    ``tokenchars '-'`` keeps the hyphen a token character so a hyphenated transliteration
    (``KU-RO``, ``PO-TO-KU-RO``) stays a single FTS token instead of splitting into ``KU`` +
    ``RO``; otherwise a phrase query ``"KU-RO"`` would match the subsequence inside
    ``PO-TO-KU-RO``. ``search`` still confirms an exact token match on top of this."""
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE tokens_fts USING fts5(text, doc_id UNINDEXED, "
            "position UNINDEXED, tokenize=\"unicode61 tokenchars '-'\")"
        )
    except sqlite3.OperationalError:
        return  # this SQLite build has no FTS5; search() falls back to an exact-match query
    conn.execute(
        "INSERT INTO tokens_fts(text, doc_id, position) SELECT text, doc_id, position FROM tokens"
    )


_ALIGNMENT_FIELDS = (
    "document_id", "sentence_id", "source_token_id", "original_text",
    "start_char", "end_char", "whitespace_before", "normalized_text",
    "normalization_ops",
)


def _alignment_to_dict(value: SourceAlignment | dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the deliberately small, stable SQLite representation of an alignment."""
    if value is None:
        return None
    if isinstance(value, dict):
        # Core JSON serialization may already have produced the same wire mapping.
        # Normalize through the constructor so SQLite never stores an unchecked object.
        try:
            if set(value) != set(_ALIGNMENT_FIELDS):
                raise ValueError("wrong fields")
            if not isinstance(value["normalization_ops"], (list, tuple)):
                raise TypeError("normalization_ops must be a sequence")
            value = SourceAlignment(
                document_id=value["document_id"], sentence_id=value["sentence_id"],
                source_token_id=value["source_token_id"], original_text=value["original_text"],
                start_char=value["start_char"], end_char=value["end_char"],
                whitespace_before=value["whitespace_before"], normalized_text=value["normalized_text"],
                normalization_ops=tuple(value["normalization_ops"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid token alignment") from exc
    return {
        "document_id": value.document_id,
        "sentence_id": value.sentence_id,
        "source_token_id": value.source_token_id,
        "original_text": value.original_text,
        "start_char": value.start_char,
        "end_char": value.end_char,
        "whitespace_before": value.whitespace_before,
        "normalized_text": value.normalized_text,
        "normalization_ops": list(value.normalization_ops),
    }


def _alignment_from_json(raw: str | None, *, context: str) -> SourceAlignment | None:
    """Decode an alignment column, rejecting malformed rows with a useful error.

    A nullable column is the compatibility representation for pre-A4 databases.  A
    non-null value is intentionally strict: accepting a partial object would make a
    persisted alignment look complete while silently losing its source identity/span.
    """
    if raw is None or raw in ("", "null"):
        return None
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed token alignment in {context}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"malformed token alignment in {context}: expected a JSON object")
    if set(value) != set(_ALIGNMENT_FIELDS):
        missing = sorted(set(_ALIGNMENT_FIELDS) - set(value))
        extra = sorted(set(value) - set(_ALIGNMENT_FIELDS))
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unknown " + ", ".join(extra))
        raise ValueError(f"malformed token alignment in {context}: {('; '.join(detail))}")
    if (
        not isinstance(value["document_id"], str)
        or not isinstance(value["source_token_id"], str)
        or not isinstance(value["original_text"], str)
        or not isinstance(value["whitespace_before"], str)
        or not isinstance(value["normalized_text"], str)
        or (value["sentence_id"] is not None and not isinstance(value["sentence_id"], str))
    ):
        raise ValueError(f"malformed token alignment in {context}: text fields must be strings")
    if (
        isinstance(value["start_char"], bool)
        or isinstance(value["end_char"], bool)
        or not isinstance(value["start_char"], int)
        or not isinstance(value["end_char"], int)
        or value["start_char"] < 0
        or value["end_char"] < value["start_char"]
    ):
        raise ValueError(f"malformed token alignment in {context}: invalid character span")
    ops = value["normalization_ops"]
    if not isinstance(ops, list) or not all(isinstance(op, str) for op in ops):
        raise ValueError(f"malformed token alignment in {context}: normalization_ops must be a string list")
    try:
        return SourceAlignment(
            document_id=value["document_id"], sentence_id=value["sentence_id"],
            source_token_id=value["source_token_id"], original_text=value["original_text"],
            start_char=value["start_char"], end_char=value["end_char"],
            whitespace_before=value["whitespace_before"], normalized_text=value["normalized_text"],
            normalization_ops=tuple(ops),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"malformed token alignment in {context}: invalid value") from exc


def _alignment_json(value: SourceAlignment | dict[str, Any] | None) -> str | None:
    mapped = _alignment_to_dict(value)
    return json.dumps(mapped) if mapped is not None else None


def _form_state_json(value: TokenFormState | dict[str, Any] | None) -> str | None:
    """Encode one typed A6 state for the nullable canonical SQLite column."""
    if value is None:
        return None
    if isinstance(value, dict):
        try:
            value = TokenFormState.from_dict(value)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError("invalid token form_state") from exc
    if not isinstance(value, TokenFormState):
        raise TypeError("token form_state must be a TokenFormState or object")
    return json.dumps(value.to_dict(), ensure_ascii=False, separators=(",", ":"))


def _form_state_from_json(raw: str | None, *, context: str) -> TokenFormState | None:
    """Decode a form-state column with contextual, clean malformed-value errors."""
    if raw is None or raw in ("", "null"):
        return None
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed token form_state in {context}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"malformed token form_state in {context}: expected a JSON object")
    try:
        return TokenFormState.from_dict(value)
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError(f"malformed token form_state in {context}: {exc}") from exc


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})"))


def _ensure_alignment_columns(conn: sqlite3.Connection) -> None:
    """Add A4 columns to a schema-1 database, without touching existing rows."""
    if not _has_column(conn, "documents", "source_text"):
        conn.execute("ALTER TABLE documents ADD COLUMN source_text TEXT")
    if not _has_column(conn, "tokens", "alignment"):
        conn.execute("ALTER TABLE tokens ADD COLUMN alignment TEXT")


def _ensure_form_state_columns(conn: sqlite3.Connection) -> None:
    """Add the nullable A6 column to schema-1/2 databases during append."""
    if not _has_column(conn, "tokens", "form_state_json"):
        conn.execute("ALTER TABLE tokens ADD COLUMN form_state_json TEXT")


def _insert_document(conn: sqlite3.Connection, dd: dict[str, Any], order: int) -> None:
    """Insert one ``_document_to_dict`` dict and its tokens at ``doc_order = order``."""
    m = dd["meta"]
    conn.execute(
        "INSERT INTO documents(doc_order, id, script_id, glyphs, transcription, "
        "translations, site, support, scribe, findspot, period, name, images, notes, "
        "lines, source_text) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            order, dd["id"], dd["script_id"], dd["glyphs"], dd["transcription"],
            json.dumps(dd["translations"]), m["site"], m["support"], m["scribe"],
            m["findspot"], m["period"], m["name"], json.dumps(m["images"]),
            json.dumps(m["notes"]), json.dumps(dd["lines"]), dd.get("source_text"),
        ),
    )
    conn.executemany(
        "INSERT INTO tokens(doc_id, token_order, position, line_no, text, kind, glyphs, "
        "status, signs, alt, annotations, alignment, form_state_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                # token_order is the token's index in the document's list, so the round trip
                # preserves list order even when `position` is None or does not match order.
                dd["id"], i, t["position"], t["line_no"], t["text"], t["kind"],
                t.get("glyphs"), t.get("status", "certain"),
                json.dumps(t.get("signs", [])), json.dumps(t.get("alt", [])),
                json.dumps(t.get("annotations", {})),
                _alignment_json(t.get("alignment")),
                _form_state_json(t.get("form_state")),
            )
            for i, t in enumerate(dd["tokens"])
        ],
    )


def to_sqlite(
    corpus: Corpus,
    path: str | Path,
    *,
    fts: bool = True,
    append: bool = False,
    progress: Callable[[int, int], None] | None = None,
) -> None:
    """Write ``corpus`` to a SQLite database at ``path``.

    By default this **overwrites** any existing SQLite database. Replacement uses a
    SQLite transaction, including when committed pages live in an active WAL: readers
    retain their old snapshot until their transaction ends. A busy writer is given five
    seconds to finish before replacement raises ``sqlite3.OperationalError`` and keeps
    the existing database intact. Non-SQLite files are refused without overwriting them.
    With ``append=True`` it instead
    upserts ``corpus``'s documents into an existing database (by document id — a document
    with a matching id is replaced, others are added), keeping the rest intact; the FTS5
    index is updated transactionally, and the appended corpus's provenance is recorded
    alongside the original's, so the reloaded corpus cites every source that went in
    (see `from_sqlite`).
    Documents and tokens become queryable rows; provenance and the sign inventory live in
    a ``meta`` table. Round-trips losslessly via `from_sqlite`.

    ``progress`` (optional) is called as ``progress(done, total)`` after each document is
    written, counting documents — the hook a minutes-long write (a DDbDP-sized corpus is
    ~57k documents) reports through; the CLI paints a live line from it. The written
    database is identical with or without it; the final call is ``(total, total)``,
    made before the FTS index build (one bulk statement, not per-document)."""
    p = str(path)
    if append:
        if p != ":memory:" and not Path(p).exists():
            raise FileNotFoundError(f"no database to append to: {p} (build it first)")
        _append_sqlite(corpus, p, progress=progress)
        return

    _LOG.info("writing %d documents to SQLite database %s", len(corpus.documents), p)

    def _build(target: str) -> None:
        conn = sqlite3.connect(target)
        try:
            conn.executescript(_SCHEMA)
            meta = {
                "schema_version": str(SCHEMA_VERSION),
                "script_id": corpus.script_id,
                "provenance": json.dumps(_provenance_to_dict(corpus.provenance)),
                "sign_inventory": json.dumps(_inventory_to_dict(corpus.sign_inventory)),
            }
            conn.executemany("INSERT INTO meta(key, value) VALUES (?, ?)", list(meta.items()))
            total = len(corpus.documents)
            for i, doc in enumerate(corpus.documents):
                _insert_document(conn, _document_to_dict(doc), i)
                if progress is not None:
                    progress(i + 1, total)
            if fts:
                _build_fts(conn)
            conn.commit()
        finally:
            conn.close()

    if p == ":memory:":
        _build(p)
        return
    # Build off to the side before touching the destination. Renaming just the main
    # file over an existing SQLite database is unsafe: another connection may still
    # own its WAL/journal and combine those old pages with the replacement file.
    destination = Path(p)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    ) as folder:
        tmp = Path(folder) / "corpus.sqlite"
        _build(str(tmp))
        _publish_sqlite(tmp, destination)


def _publish_sqlite(source: Path, destination: Path) -> None:
    """Publish a complete new database, or replace an existing one transactionally.

    A no-clobber hard link makes creation atomic without a check-then-rename race
    against another creator. Existing databases keep their inode: SQLite's online
    backup owns the destination write transaction and rolls it back on failure.
    Never unlink or rename a destination or its SQLite-managed sidecars.
    """
    if not destination.exists() and any(
        Path(str(destination) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")
    ):
        raise sqlite3.OperationalError(
            f"cannot create {destination}: SQLite sidecars exist without their database; "
            "recover the original database first"
        )
    try:
        os.link(source, destination)
        return
    except FileExistsError:
        pass  # another creator may also have published while this corpus was built

    # mode=rw prohibits accidentally creating a new empty database if the target was
    # removed in the meantime. SQLite serializes other supported readers/writers;
    # external unlink/rename of an open database is not a supported SQLite operation.
    uri = destination.absolute().as_uri() + "?mode=rw"
    target = sqlite3.connect(uri, uri=True, timeout=0)
    origin: sqlite3.Connection | None = None
    try:
        origin = sqlite3.connect(source)
        # Backup cannot change a WAL database's page size. Match it on the private
        # source first; VACUUM failure still leaves the destination untouched.
        page_size = target.execute("PRAGMA page_size").fetchone()[0]
        if origin.execute("PRAGMA page_size").fetchone()[0] != page_size:
            origin.execute(f"PRAGMA page_size={int(page_size)}")
            origin.execute("VACUUM")
        busy_since: float | None = None

        def progress(status: int, remaining: int, total: int) -> None:
            nonlocal busy_since
            # SQLITE_BUSY / SQLITE_LOCKED; named constants require Python 3.11.
            if status in (5, 6):
                now = time.monotonic()
                if busy_since is None:
                    busy_since = now
                if now - busy_since >= _REPLACEMENT_BUSY_TIMEOUT:
                    raise sqlite3.OperationalError(
                        f"database is locked: cannot replace {destination}; retry when "
                        "other writers or blocking readers have finished"
                    )
            else:
                busy_since = None

        origin.backup(target, pages=128, progress=progress, sleep=0.05)
    finally:
        if origin is not None:
            origin.close()
        target.close()


def _append_sqlite(
    corpus: Corpus, p: str, *, progress: Callable[[int, int], None] | None = None
) -> None:
    """Upsert ``corpus``'s documents into the existing DB at ``p`` (by document id).

    The appended corpus's provenance joins the stored one(s) in ``meta`` (deduplicated),
    so `from_sqlite` can cite every corpus that went in. The sign inventory follows the
    `Corpus.merge` rule: a same-script inventory fills an empty slot, and a cross-script
    append clears it (a mixed corpus has no single-script inventory). ``progress`` is
    called as ``progress(done, total)`` after each upserted document (total = the
    appended corpus's document count); the final ``(total, total)`` call comes before
    the FTS rebuild and the provenance/inventory bookkeeping."""
    _LOG.info("appending %d documents into SQLite database %s", len(corpus.documents), p)
    conn = sqlite3.connect(p)
    try:
        # Take the write lock BEFORE the pre-insert reads (MAX(doc_order), the per-doc
        # existence checks): with sqlite's deferred implicit BEGIN those reads would see
        # stale state when two appenders race, minting duplicate doc_order values. A
        # second simultaneous appender now waits (sqlite's busy timeout) or gets a clean
        # "database is locked" instead of silently corrupting the ordering.
        conn.execute("BEGIN IMMEDIATE")
        _check_schema_version(
            {r[0]: r[1] for r in conn.execute("SELECT key, value FROM meta")}
        )
        _ensure_alignment_columns(conn)
        _ensure_form_state_columns(conn)
        # The append now writes schema-2 alignment and schema-3 form-state rows.  Do
        # not leave the file labelled with an older schema: an older reader could
        # otherwise silently discard additive state.
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        _ensure_token_order(conn)
        has_fts = bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tokens_fts'"
            ).fetchone()
        )
        next_order = conn.execute("SELECT COALESCE(MAX(doc_order), -1) FROM documents").fetchone()[0] + 1
        row = conn.execute("SELECT value FROM meta WHERE key = 'script_id'").fetchone()
        existing_script = row[0] if row else ""
        total = len(corpus.documents)
        for done, doc in enumerate(corpus.documents, start=1):
            dd = _document_to_dict(doc)
            if has_fts:
                # Keep the virtual table's schema stable for concurrent readers. Dropping
                # and recreating the whole FTS table took a schema lock that could leak as
                # ``database is locked`` from an otherwise read-only search.
                conn.execute("DELETE FROM tokens_fts WHERE doc_id = ?", (dd["id"],))
            prev = conn.execute(
                "SELECT doc_order FROM documents WHERE id = ?", (dd["id"],)
            ).fetchone()
            if prev is not None:  # replace in place: drop the old rows, reuse its order
                order = int(prev[0])
                conn.execute("DELETE FROM documents WHERE id = ?", (dd["id"],))
                conn.execute("DELETE FROM tokens WHERE doc_id = ?", (dd["id"],))
            else:
                order, next_order = next_order, next_order + 1
            _insert_document(conn, dd, order)
            if has_fts:
                conn.execute(
                    "INSERT INTO tokens_fts(text, doc_id, position) "
                    "SELECT text, doc_id, position FROM tokens WHERE doc_id = ?",
                    (dd["id"],),
                )
            if progress is not None:
                progress(done, total)
        # provenance: keep every distinct source that went in. meta holds one dict for a
        # single-source DB; the first append of a second source turns it into a list.
        row = conn.execute("SELECT value FROM meta WHERE key = 'provenance'").fetchone()
        stored = json.loads(row[0]) if row and row[0] else None
        provs: list[Any] = stored if isinstance(stored, list) else ([stored] if stored else [])
        added = _provenance_to_dict(corpus.provenance)
        if added is not None and added not in provs:
            provs.append(added)
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('provenance', ?)",
                (json.dumps(provs[0] if len(provs) == 1 else provs),),
            )
        if existing_script and corpus.script_id and existing_script not in ("mixed", corpus.script_id):
            conn.execute("UPDATE meta SET value = 'mixed' WHERE key = 'script_id'")
            # a mixed database has no single-script sign inventory (the Corpus.merge rule)
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('sign_inventory', 'null')"
            )
            import sys

            print(
                f"aegean: appended a {corpus.script_id!r} corpus into a {existing_script!r} "
                "database; the database's script id is now 'mixed'",
                file=sys.stderr,
            )
        elif corpus.sign_inventory is not None and existing_script == corpus.script_id:
            inv_row = conn.execute(
                "SELECT value FROM meta WHERE key = 'sign_inventory'"
            ).fetchone()
            if inv_row is None or not json.loads(inv_row[0] or "null"):
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES ('sign_inventory', ?)",
                    (json.dumps(_inventory_to_dict(corpus.sign_inventory)),),
                )
        conn.commit()
    finally:
        conn.close()


def _check_schema_version(meta: dict[str, Any]) -> None:
    """Refuse a database written by a NEWER pyaegean schema, with the fix named; a
    missing or older version reads normally (the reader carries fallbacks for those)."""
    from .core.provenance import SCHEMA_VERSION

    raw = meta.get("schema_version")
    try:
        stored = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return  # unreadable marker: treat as legacy rather than refuse a real file
    if stored is not None and stored > SCHEMA_VERSION:
        raise ValueError(
            f"this database uses schema version {stored}, but this pyaegean understands "
            f"up to {SCHEMA_VERSION} — upgrade pyaegean to read it"
        )


def _corpus_db_error(path: str | Path, exc: sqlite3.Error) -> ValueError:
    """Turn a raw ``sqlite3`` error from opening a supposed corpus database into a clean
    domain error with a next step, so a corpus-load path never leaks a third-party
    traceback (the guard the sibling ``aegean db search`` already applied, now at the
    shared primitive so every load path inherits it).

    A locked database is a distinct, transient condition (a read is blocked only while a
    writer holds the lock), not a malformed file — it names that and says to retry, rather
    than mislabelling the file as not a corpus. Everything else (no pyaegean schema table,
    an unreadable or non-SQLite file) means this is simply not a pyaegean corpus database."""
    if "locked" in str(exc).lower():
        return ValueError(
            f"corpus database {path} is locked (another process is writing it); retry"
        )
    return ValueError(
        f"{path} is not a pyaegean corpus database "
        "(build one with `aegean db build`, or aegean.db.to_sqlite)"
    )


def _has_token_order(conn: sqlite3.Connection) -> bool:
    """Whether the tokens table carries the explicit ``token_order`` column (databases
    written before it existed order by ``position`` — the best available for old files)."""
    return any(
        r[1] == "token_order" for r in conn.execute("PRAGMA table_info(tokens)")
    )


def _ensure_token_order(conn: sqlite3.Connection) -> None:
    """Migrate a legacy database in place: add ``token_order`` and backfill it from the
    stored ``position``/insertion order, so appends into an old file keep working."""
    if _has_token_order(conn):
        return
    conn.execute("ALTER TABLE tokens ADD COLUMN token_order INTEGER")
    doc_ids = [r[0] for r in conn.execute("SELECT DISTINCT doc_id FROM tokens")]
    for doc_id in doc_ids:
        rowids = [
            r[0]
            for r in conn.execute(
                "SELECT rowid FROM tokens WHERE doc_id = ? ORDER BY position, rowid",
                (doc_id,),
            )
        ]
        conn.executemany(
            "UPDATE tokens SET token_order = ? WHERE rowid = ?",
            [(i, rid) for i, rid in enumerate(rowids)],
        )


def _document_from_row(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    order_col: str = "token_order",
    allow_form_state: bool = True,
) -> Document:
    tokens: list[dict[str, Any]] = []
    # order_col is one of two module literals ("token_order" / "position"), never user input.
    for t in conn.execute(
        f"SELECT * FROM tokens WHERE doc_id = ? ORDER BY {order_col}", (row["id"],)
    ):
        td: dict[str, Any] = {
            "text": t["text"], "kind": t["kind"], "position": t["position"],
            "line_no": t["line_no"], "glyphs": t["glyphs"],
            "signs": json.loads(t["signs"] or "[]"), "alt": json.loads(t["alt"] or "[]"),
            "annotations": json.loads(t["annotations"] or "{}"),
        }
        if "alignment" in t.keys():
            alignment = _alignment_from_json(
                t["alignment"], context=f"document {row['id']!r}, token {t['position']!r}"
            )
            if alignment is not None:
                td["alignment"] = alignment
        if allow_form_state and "form_state_json" in t.keys():
            form_state = _form_state_from_json(
                t["form_state_json"],
                context=f"document {row['id']!r}, token {t['position']!r}",
            )
            if form_state is not None:
                td["form_state"] = form_state
        if t["status"] and t["status"] != "certain":
            td["status"] = t["status"]
        tokens.append(td)
    dd: dict[str, Any] = {
        "id": row["id"], "script_id": row["script_id"], "glyphs": row["glyphs"],
        "transcription": row["transcription"],
        "translations": json.loads(row["translations"] or "[]"),
        "meta": {
            "site": row["site"], "support": row["support"], "scribe": row["scribe"],
            "findspot": row["findspot"], "period": row["period"], "name": row["name"],
            "images": json.loads(row["images"] or "[]"),
            "notes": json.loads(row["notes"] or "[]"),
        },
        "tokens": tokens, "lines": json.loads(row["lines"] or "[]"),
    }
    if "source_text" in row.keys():
        dd["source_text"] = row["source_text"]
    return _document_from_dict(dd)


def _combined_provenance(provs: list[Provenance], n_docs: int) -> Provenance:
    """A fresh provenance naming every corpus appended into a database, so `cite` on the
    reloaded corpus stays truthful (the same pattern as ``Corpus.merge``)."""
    sources = [p.citation or p.source for p in provs]
    licenses = sorted({p.license for p in provs if p.license})
    # edition_fidelity carries through only when every appended source agrees on one
    # non-empty value (the same rule as Corpus.merge); otherwise honestly unknown.
    fidelities = {p.edition_fidelity for p in provs}
    return Provenance(
        source="Combined corpus (aegean.db)",
        license="; ".join(licenses) or "mixed",
        citation="Combined corpus of: " + "; ".join(sources),
        notes=(f"appended: {len(provs)} corpora → {n_docs} documents",),
        edition_fidelity=fidelities.pop() if len(fidelities) == 1 else "",
    )


def from_sqlite(
    path: str | Path, *, progress: Callable[[int, int], None] | None = None
) -> Corpus:
    """Reconstruct the `Corpus` written by `to_sqlite` — documents, sign inventory, and
    provenance, byte-for-byte equivalent to the original. A database grown with
    ``to_sqlite(append=True)`` stores one provenance per appended source; those come back
    as a single combined provenance naming every source, so `Corpus.cite` stays truthful.

    ``progress`` (optional) is called as ``progress(done, total)`` after each document is
    materialized, counting documents — the hook the ~100 s DDbDP whole-corpus load
    (``aegean.load("ddbdp")``) reports through. The returned corpus is identical with or
    without it; an empty database makes no calls, and the final call is ``(total, total)``."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        # One read transaction for the whole load: a concurrent append committing between
        # this reader's statements could otherwise yield a torn corpus (a document's row
        # from before the append, its tokens from after).
        conn.execute("BEGIN")
        meta = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM meta")}
        _check_schema_version(meta)
        raw = json.loads(meta.get("provenance") or "null")
        provs = [
            pv
            for pv in (_provenance_from_dict(d) for d in (raw if isinstance(raw, list) else [raw]))
            if pv is not None
        ]
        inventory = _inventory_from_dict(json.loads(meta.get("sign_inventory") or "null"))
        order_col = "token_order" if _has_token_order(conn) else "position"
        raw_schema = meta.get("schema_version")
        try:
            allow_form_state = int(raw_schema) >= 3 if raw_schema is not None else False
        except (TypeError, ValueError):
            allow_form_state = False
        total = (
            int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
            if progress is not None
            else 0
        )
        docs: list[Document] = []
        for done, r in enumerate(
            conn.execute("SELECT * FROM documents ORDER BY doc_order"), start=1
        ):
            docs.append(
                _document_from_row(
                    conn, r, order_col=order_col, allow_form_state=allow_form_state
                )
            )
            if progress is not None:
                progress(done, total)
    except sqlite3.Error as exc:
        # A wrong-schema, non-SQLite, or locked file leaked a raw sqlite3 traceback with
        # no path or next step; give a clean domain error instead. (_check_schema_version
        # raises ValueError, not sqlite3.Error, so its "upgrade pyaegean" message survives.)
        raise _corpus_db_error(path, exc) from None
    finally:
        try:
            conn.rollback()  # end the read transaction (read-only: nothing to write)
        except sqlite3.Error:
            pass
        conn.close()
    _LOG.info("loaded %d documents from SQLite database %s", len(docs), path)
    provenance: Provenance | None
    if len(provs) > 1:
        provenance = _combined_provenance(provs, len(docs))
    else:
        provenance = provs[0] if provs else None
    return Corpus(docs, inventory, provenance, meta.get("script_id", ""))


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
    expected = _lexical_semantics_version()
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
        return _lexical_index_status(conn)
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
        if _lexical_index_status(conn)["state"] == "unsupported":
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
            (_lexical_semantics_version(), total),
        )
        result = _lexical_index_status(conn)
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
            if mode == "token" and _lexical_index_status(conn)["state"] == "ready":
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


def stream(path: str | Path) -> Iterator[Document]:
    """Yield the documents of a SQLite corpus one at a time, without materializing the corpus.

    A separate read cursor fetches each document's tokens on demand, so memory stays flat for
    arbitrarily large databases — the DB-backed counterpart to a streamed load (item: large
    corpora). Pairs with `from_sqlite` when random access is wanted instead."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        _check_schema_version(
            {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM meta")}
        )
        order_col = "token_order" if _has_token_order(conn) else "position"
        raw_schema = None
        try:
            raw_schema = next(
                r[0] for r in conn.execute(
                    "SELECT value FROM meta WHERE key = 'schema_version'"
                )
            )
        except StopIteration:
            pass
        try:
            allow_form_state = int(raw_schema) >= 3 if raw_schema is not None else False
        except (TypeError, ValueError):
            allow_form_state = False
        ids = [r["id"] for r in conn.execute("SELECT id FROM documents ORDER BY doc_order")]
        _LOG.debug("streaming %d documents from SQLite database %s", len(ids), path)
        for doc_id in ids:
            # Each document's row + tokens are read inside one short transaction, so a
            # concurrent append committing between the two statements cannot yield a
            # torn Document (old metadata with new tokens). Per-document, not one big
            # transaction: a long streaming pass must not hold the read lock throughout.
            conn.execute("BEGIN")
            try:
                row = conn.execute(
                    "SELECT * FROM documents WHERE id = ?", (doc_id,)
                ).fetchone()
                doc = (
                    _document_from_row(
                        conn, row, order_col=order_col, allow_form_state=allow_form_state
                    )
                    if row
                    else None
                )
            finally:
                conn.rollback()
            if doc is not None:  # dropped by a concurrent append between listing and read
                yield doc
    finally:
        conn.close()
