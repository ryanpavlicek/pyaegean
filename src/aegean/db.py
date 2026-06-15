"""SQLite persistence for a `Corpus` — stdlib ``sqlite3`` only, so the core stays
dependency-free (the same precedent as ``aegean.cache``).

``to_sqlite`` / ``from_sqlite`` are a faithful, queryable round-trip: documents and tokens
are normalized into rows (so SQL and full-text search work over them), with the nested
structure (signs, alternate readings, annotations, line groupings, image refs, notes) kept
in JSON columns. Provenance and the sign inventory live in a small key/value ``meta`` table.
``search`` uses FTS5 when the local SQLite build has it, falling back to ``LIKE``; ``stream``
yields documents lazily for a large DB-backed corpus without materializing it.

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
    """Create + populate an FTS5 index over token text, or no-op if FTS5 is unavailable."""
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE tokens_fts USING fts5(text, doc_id UNINDEXED, position UNINDEXED)"
        )
    except sqlite3.OperationalError:
        return  # this SQLite build has no FTS5; search() falls back to LIKE
    conn.execute(
        "INSERT INTO tokens_fts(text, doc_id, position) SELECT text, doc_id, position FROM tokens"
    )


def to_sqlite(corpus: Corpus, path: str | Path, *, fts: bool = True) -> None:
    """Write ``corpus`` to a SQLite database at ``path`` (overwriting any existing file).

    Documents and tokens become queryable rows; provenance and the sign inventory are stored
    in a ``meta`` table; with ``fts=True`` an FTS5 index over token text is built when the
    local SQLite supports it. Round-trips losslessly via `from_sqlite`."""
    p = str(path)
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
            dd = _document_to_dict(doc)
            m = dd["meta"]
            conn.execute(
                "INSERT INTO documents(doc_order, id, script_id, glyphs, transcription, "
                "translations, site, support, scribe, findspot, period, name, images, notes, "
                "lines) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    i, dd["id"], dd["script_id"], dd["glyphs"], dd["transcription"],
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
        if fts:
            _build_fts(conn)
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


def search(path: str | Path, query: str, *, limit: int = 50) -> list[tuple[str, int, str]]:
    """Full-text search a SQLite corpus's tokens; returns ``(doc_id, position, text)`` hits.

    The query is matched as a literal token/phrase, so transliterations with hyphens or other
    punctuation (``KU-RO``, ``A-DU``) work directly. Uses the FTS5 index built by ``to_sqlite``
    when present, falling back to a ``LIKE`` substring match otherwise."""
    conn = sqlite3.connect(str(path))
    try:
        has_fts = bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tokens_fts'"
            ).fetchone()
        )
        if has_fts:
            phrase = '"' + query.replace('"', '""') + '"'  # match literally, not as FTS5 syntax
            cur = conn.execute(
                "SELECT doc_id, position, text FROM tokens_fts WHERE tokens_fts MATCH ? LIMIT ?",
                (phrase, limit),
            )
        else:
            cur = conn.execute(
                "SELECT doc_id, position, text FROM tokens WHERE text LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            )
        return [(str(r[0]), int(r[1]), str(r[2])) for r in cur]
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
