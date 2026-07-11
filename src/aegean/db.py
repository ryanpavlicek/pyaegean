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

A corpus out of the database cites exactly like a corpus out of JSON — the provenance round-
trips, and a database grown with ``append=True`` records every appended corpus's provenance,
so the reloaded corpus cites them all. ``Corpus.to_sql`` / ``Corpus.from_sql`` are thin
wrappers over these functions.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from ._atomic import atomic_path
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
from .core.model import Document
from .core.provenance import SCHEMA_VERSION, Provenance

__all__ = ["to_sqlite", "from_sqlite", "search", "stream"]

_LOG = get_logger("db")

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE documents (
    doc_order INTEGER, id TEXT PRIMARY KEY, script_id TEXT, glyphs TEXT, transcription TEXT,
    translations TEXT, site TEXT, support TEXT, scribe TEXT, findspot TEXT, period TEXT,
    name TEXT, images TEXT, notes TEXT, lines TEXT
);
CREATE TABLE tokens (
    doc_id TEXT, token_order INTEGER, position INTEGER, line_no INTEGER, text TEXT, kind TEXT,
    glyphs TEXT, status TEXT, signs TEXT, alt TEXT, annotations TEXT
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


def _insert_document(conn: sqlite3.Connection, dd: dict[str, Any], order: int) -> None:
    """Insert one ``_document_to_dict`` dict and its tokens at ``doc_order = order``."""
    m = dd["meta"]
    conn.execute(
        "INSERT INTO documents(doc_order, id, script_id, glyphs, transcription, "
        "translations, site, support, scribe, findspot, period, name, images, notes, "
        "lines) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            order, dd["id"], dd["script_id"], dd["glyphs"], dd["transcription"],
            json.dumps(dd["translations"]), m["site"], m["support"], m["scribe"],
            m["findspot"], m["period"], m["name"], json.dumps(m["images"]),
            json.dumps(m["notes"]), json.dumps(dd["lines"]),
        ),
    )
    conn.executemany(
        "INSERT INTO tokens(doc_id, token_order, position, line_no, text, kind, glyphs, "
        "status, signs, alt, annotations) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                # token_order is the token's index in the document's list, so the round trip
                # preserves list order even when `position` is None or does not match order.
                dd["id"], i, t["position"], t["line_no"], t["text"], t["kind"],
                t.get("glyphs"), t.get("status", "certain"),
                json.dumps(t.get("signs", [])), json.dumps(t.get("alt", [])),
                json.dumps(t.get("annotations", {})),
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

    By default this **overwrites** any existing file. With ``append=True`` it instead
    upserts ``corpus``'s documents into an existing database (by document id — a document
    with a matching id is replaced, others are added), keeping the rest intact; the FTS5
    index is refreshed, and the appended corpus's provenance is recorded alongside the
    original's, so the reloaded corpus cites every source that went in (see `from_sqlite`).
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
    # Build into a temp database then atomically replace, so a failed or interrupted
    # rebuild (full disk, Ctrl+C) never destroys the user's existing .db — the prior
    # unlink-then-rebuild-in-place left no recoverable file. Same temp+replace the
    # caches and the .part download use.
    with atomic_path(Path(p)) as tmp:
        _build(str(tmp))


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
            if progress is not None:
                progress(done, total)
        if has_fts:  # rebuild from current tokens so replaced docs leave no stale hits
            conn.execute("DROP TABLE tokens_fts")
            _build_fts(conn)
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
    conn: sqlite3.Connection, row: sqlite3.Row, *, order_col: str = "token_order"
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
        total = (
            int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
            if progress is not None
            else 0
        )
        docs: list[Document] = []
        for done, r in enumerate(
            conn.execute("SELECT * FROM documents ORDER BY doc_order"), start=1
        ):
            docs.append(_document_from_row(conn, r, order_col=order_col))
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


def search(path: str | Path, query: str, *, limit: int = 50, mode: str = "token"
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
    case in Python (SQLite's ``LIKE`` also folds ASCII only), scanning the token table: about
    4 ms on the bundled 1,721-document Linear A corpus, linear in the token count.

    Both modes fold case, Greek included (``ku-ro`` finds ``KU-RO``; ``λόγος`` finds
    ``ΛΌΓΟΣ``, final sigma folding with the rest). Diacritics still have to match:
    ``λογος`` does not find ``λόγος``.

    ``limit`` caps the number of hits (default 50); zero or a negative value returns
    every match. The database is opened **read-only** (a sqlite ``mode=ro`` URI), so a
    search can never create or modify a file: a missing path or a non-SQLite file raises
    ``sqlite3.OperationalError`` / ``sqlite3.DatabaseError`` instead of leaving an empty
    database behind."""
    if mode not in {"token", "substring"}:
        raise ValueError(f"mode must be 'token' or 'substring', got {mode!r}")
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        target = query.casefold()
        out: list[tuple[str, int | None, str]] = []
        # position is an int, or None for a token stored without one (SQL NULL); keep it
        # as-is rather than int()-coercing, which would crash on the None case (0.19.9).
        if mode == "substring":
            for doc_id, position, text in conn.execute(
                "SELECT doc_id, position, text FROM tokens"
            ):
                if target in str(text).casefold():
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
            if str(text).casefold() == target:  # FTS only narrows; confirm an exact token match
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
                doc = _document_from_row(conn, row, order_col=order_col) if row else None
            finally:
                conn.rollback()
            if doc is not None:  # dropped by a concurrent append between listing and read
                yield doc
    finally:
        conn.close()
