"""SQLite persistence for a `Corpus` — stdlib ``sqlite3`` only, so the core stays
dependency-free (the same precedent as ``aegean.cache``).

``to_sqlite`` / ``from_sqlite`` are a faithful, queryable round-trip: documents and tokens
are normalized into rows (so SQL and full-text search work over them), with the nested
structure (signs, alternate readings, annotations, line groupings, image refs, notes) kept
in JSON columns. Provenance and the sign inventory live in a small key/value ``meta`` table.
``search`` matches a whole token by default (an FTS5 phrase when available, else an indexed
exact-match query on ``tokens(text)``); ``mode="substring"`` is the opt-in ``LIKE`` within-token
search. ``stream`` yields documents lazily for a large DB-backed corpus without materializing it.

A corpus out of the database cites exactly like a corpus out of JSON — the provenance round-
trips. ``Corpus.to_sql`` / ``Corpus.from_sql`` are thin wrappers over these functions.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

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
from .core.provenance import SCHEMA_VERSION

__all__ = ["to_sqlite", "from_sqlite", "search", "stream"]

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE documents (
    doc_order INTEGER, id TEXT PRIMARY KEY, script_id TEXT, glyphs TEXT, transcription TEXT,
    translations TEXT, site TEXT, support TEXT, scribe TEXT, findspot TEXT, period TEXT,
    name TEXT, images TEXT, notes TEXT, lines TEXT
);
CREATE TABLE tokens (
    doc_id TEXT, position INTEGER, line_no INTEGER, text TEXT, kind TEXT, glyphs TEXT,
    status TEXT, signs TEXT, alt TEXT, annotations TEXT
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
        "INSERT INTO tokens(doc_id, position, line_no, text, kind, glyphs, status, "
        "signs, alt, annotations) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (
                dd["id"], t["position"], t["line_no"], t["text"], t["kind"],
                t.get("glyphs"), t.get("status", "certain"),
                json.dumps(t.get("signs", [])), json.dumps(t.get("alt", [])),
                json.dumps(t.get("annotations", {})),
            )
            for t in dd["tokens"]
        ],
    )


def to_sqlite(corpus: Corpus, path: str | Path, *, fts: bool = True, append: bool = False) -> None:
    """Write ``corpus`` to a SQLite database at ``path``.

    By default this **overwrites** any existing file. With ``append=True`` it instead
    upserts ``corpus``'s documents into an existing database (by document id — a document
    with a matching id is replaced, others are added), keeping the rest intact; the FTS5
    index is refreshed. Documents and tokens become queryable rows; provenance and the sign
    inventory live in a ``meta`` table. Round-trips losslessly via `from_sqlite`."""
    p = str(path)
    if append:
        if p != ":memory:" and not Path(p).exists():
            raise FileNotFoundError(f"no database to append to: {p} (build it first)")
        _append_sqlite(corpus, p)
        return
    if p != ":memory:":
        Path(p).unlink(missing_ok=True)
    conn = sqlite3.connect(p)
    try:
        conn.executescript(_SCHEMA)
        meta = {
            "schema_version": str(SCHEMA_VERSION),
            "script_id": corpus.script_id,
            "provenance": json.dumps(_provenance_to_dict(corpus.provenance)),
            "sign_inventory": json.dumps(_inventory_to_dict(corpus.sign_inventory)),
        }
        conn.executemany("INSERT INTO meta(key, value) VALUES (?, ?)", list(meta.items()))
        for i, doc in enumerate(corpus.documents):
            _insert_document(conn, _document_to_dict(doc), i)
        if fts:
            _build_fts(conn)
        conn.commit()
    finally:
        conn.close()


def _append_sqlite(corpus: Corpus, p: str) -> None:
    """Upsert ``corpus``'s documents into the existing DB at ``p`` (by document id)."""
    conn = sqlite3.connect(p)
    try:
        has_fts = bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tokens_fts'"
            ).fetchone()
        )
        next_order = conn.execute("SELECT COALESCE(MAX(doc_order), -1) FROM documents").fetchone()[0] + 1
        row = conn.execute("SELECT value FROM meta WHERE key = 'script_id'").fetchone()
        existing_script = row[0] if row else ""
        for doc in corpus.documents:
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
        if has_fts:  # rebuild from current tokens so replaced docs leave no stale hits
            conn.execute("DROP TABLE tokens_fts")
            _build_fts(conn)
        if existing_script and corpus.script_id and existing_script not in ("mixed", corpus.script_id):
            conn.execute("UPDATE meta SET value = 'mixed' WHERE key = 'script_id'")
            import sys

            print(
                f"aegean: appended a {corpus.script_id!r} corpus into a {existing_script!r} "
                "database; the database's script id is now 'mixed'",
                file=sys.stderr,
            )
        conn.commit()
    finally:
        conn.close()


def _document_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> Document:
    tokens: list[dict[str, Any]] = []
    for t in conn.execute(
        "SELECT * FROM tokens WHERE doc_id = ? ORDER BY position", (row["id"],)
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


def from_sqlite(path: str | Path) -> Corpus:
    """Reconstruct the `Corpus` written by `to_sqlite` — documents, sign inventory, and
    provenance, byte-for-byte equivalent to the original."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        meta = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM meta")}
        provenance = _provenance_from_dict(json.loads(meta.get("provenance") or "null"))
        inventory = _inventory_from_dict(json.loads(meta.get("sign_inventory") or "null"))
        docs = [
            _document_from_row(conn, r)
            for r in conn.execute("SELECT * FROM documents ORDER BY doc_order")
        ]
    finally:
        conn.close()
    return Corpus(docs, inventory, provenance, meta.get("script_id", ""))


def search(path: str | Path, query: str, *, limit: int = 50, mode: str = "token"
           ) -> list[tuple[str, int, str]]:
    """Search a SQLite corpus's tokens; returns ``(doc_id, position, text)`` hits.

    ``mode="token"`` (default) matches a **whole token literally**: the query must equal the
    token, so a transliteration with hyphens (``KU-RO``, ``A-DU``) matches only that token and
    never a longer token that merely contains it (``KU-RO`` does not match ``PO-TO-KU-RO``). It
    uses the FTS5 index when present (then confirms the exact match) and an indexed exact-match
    query otherwise.

    ``mode="substring"`` matches the query as a **substring** of a token, so ``KU-RO`` also
    finds ``PO-TO-KU-RO`` — useful for tracing every token a sign-group occurs in.

    Matching is case-insensitive."""
    if mode not in {"token", "substring"}:
        raise ValueError(f"mode must be 'token' or 'substring', got {mode!r}")
    conn = sqlite3.connect(str(path))
    try:
        if mode == "substring":
            esc = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            cur = conn.execute(
                "SELECT doc_id, position, text FROM tokens WHERE text LIKE ? ESCAPE '\\' LIMIT ?",
                (f"%{esc}%", limit),
            )
            return [(str(r[0]), int(r[1]), str(r[2])) for r in cur]
        target = query.casefold()
        has_fts = bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tokens_fts'"
            ).fetchone()
        )
        if has_fts:
            phrase = '"' + query.replace('"', '""') + '"'  # a literal FTS5 phrase, not syntax
            cur = conn.execute(
                "SELECT doc_id, position, text FROM tokens_fts WHERE tokens_fts MATCH ?",
                (phrase,),
            )
        else:
            cur = conn.execute(
                "SELECT doc_id, position, text FROM tokens WHERE text = ? COLLATE NOCASE",
                (query,),
            )
        out: list[tuple[str, int, str]] = []
        for doc_id, position, text in cur:
            if str(text).casefold() == target:  # FTS only narrows; confirm an exact token match
                out.append((str(doc_id), int(position), str(text)))
                if len(out) >= limit:
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
        ids = [r["id"] for r in conn.execute("SELECT id FROM documents ORDER BY doc_order")]
        for doc_id in ids:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
            yield _document_from_row(conn, row)
    finally:
        conn.close()
