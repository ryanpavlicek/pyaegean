"""Durable, resumable SQLite corpus annotation jobs.

Annotates a local SQLite corpus database document-by-document into a new SQLite
corpus database, keeping peak memory bounded by the active backend plus one
document at a time (never materializing the document ID list or the full corpus).

Design invariants:

1. **Consistent source snapshot.** Starting a job takes a SQLite online backup
   of ``source`` into ``job_dir/snapshot.sqlite`` (safe with live-WAL writers),
   verifies its schema, indexes ``(doc_order, id)`` for forward keyset reading,
   and binds both the snapshot's file SHA-256 and a streaming logical content
   digest of ``source`` into the job record.
2. **Identity-bound resume.** Resuming rejects any change to the source
   database, snapshot bytes, output destination, annotation options, or active
   backend/model identity before modifying a single row.
3. **Single-transaction document + checkpoint commits.** Each annotated document
   and its checkpoint progress record (``meta['_aegean_job_checkpoint']``) are
   committed together in one SQLite transaction inside ``job_dir/working.sqlite``.
   A crash before commit retries that document; a crash after commit advances to
   the next document with zero duplicates and zero skipped documents.
4. **Shared annotation primitive.** Uses the same per-document engine as
   ``aegean.greek.annotate_corpus``, preserving one logical
   ``analysis_generation`` across resumes so resumed output matches an
   uninterrupted collected run.
5. **Atomic final publication.** Working-only checkpoint keys are stripped on a
   private publishable copy, FTS5 is built if requested, document counts and
   order digest are verified, and the finished database is published via
   ``aegean.db._publish_sqlite``. A failed publication keeps any prior final
   database intact and leaves ``working.sqlite`` resumable.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from ._atomic import atomic_path
from ._locking import FileLock
from ._log import get_logger
from .core.corpus import _document_to_dict
from .core.provenance import SCHEMA_VERSION
from .db import (
    _SCHEMA,
    _build_fts,
    _check_schema_version,
    _corpus_db_error,
    _document_from_row,
    _has_token_order,
    _insert_document,
    _open_existing_db,
    _publish_sqlite,
)
from .greek.annotate import _DocumentAnnotator
from .greek.heldout import TagSentence

__all__ = [
    "JobCancelledError",
    "JobConflictError",
    "JobStatus",
    "annotate_sqlite_job",
    "job_status",
]

_LOG = get_logger("db.jobs")

_JOB_FORMAT = "pyaegean-sqlite-annotate-job/1"
_CHECKPOINT_META_KEY = "_aegean_job_checkpoint"
_JOB_META_PREFIX = "_aegean_job_"

_SNAPSHOT_NAME = "snapshot.sqlite"
_WORKING_NAME = "working.sqlite"
_PUBLISH_NAME = "publish.sqlite"
_MANIFEST_NAME = "job.json"
_LOCK_NAME = "job.lock"


class JobConflictError(RuntimeError):
    """Raised when a job path aliases source/output, is locked, or mismatches on resume."""


class JobCancelledError(RuntimeError):
    """Raised when ``cancel_check`` requests cancellation between documents.

    All documents committed before cancellation remain durable in ``job_dir``
    and can be resumed with ``resume=True``.
    """


@dataclass(frozen=True, slots=True)
class JobStatus:
    """Snapshot of a durable SQLite corpus annotation job's state."""

    job_id: str
    state: Literal["running", "cancelled", "completed", "failed"]
    generation: str
    source_path: str
    output_path: str
    job_dir: str
    source_sha256: str
    snapshot_sha256: str
    config_sha256: str
    order_digest: str
    total_documents: int
    completed_documents: int
    last_doc_order: int | None
    last_doc_id: str | None
    resumed: bool
    published: bool
    fts: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation of this status."""
        return {
            "job_id": self.job_id,
            "state": self.state,
            "generation": self.generation,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "job_dir": self.job_dir,
            "source_sha256": self.source_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            "config_sha256": self.config_sha256,
            "order_digest": self.order_digest,
            "total_documents": self.total_documents,
            "completed_documents": self.completed_documents,
            "last_doc_order": self.last_doc_order,
            "last_doc_id": self.last_doc_id,
            "resumed": self.resumed,
            "published": self.published,
            "fts": self.fts,
            "error": self.error,
        }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_paths(source: Path, output: Path, job_dir: Path) -> None:
    if source == output:
        raise JobConflictError(
            f"source and output cannot be the same path: {source}"
        )
    if _is_relative_to(output, job_dir) or _is_relative_to(job_dir, output):
        raise JobConflictError(
            f"output path {output} conflicts with job directory {job_dir}"
        )
    if _is_relative_to(source, job_dir) or _is_relative_to(job_dir, source):
        raise JobConflictError(
            f"source path {source} conflicts with job directory {job_dir}"
        )


def _stream_source_digest(conn: sqlite3.Connection) -> tuple[str, str, int]:
    """Return ``(content_sha256, order_digest, total_documents)`` in O(1) memory.

    Computes a deterministic logical digest over a single read snapshot so live
    WAL checkpointing or page-layout differences never cause false mismatches
    while any change to metadata, documents, or tokens invalidates resume.
    """
    content = hashlib.sha256()
    order = hashlib.sha256()
    order_col = "token_order" if _has_token_order(conn) else "position"
    has_form_state = any(
        r[1] == "form_state_json"
        for r in conn.execute("PRAGMA table_info(tokens)")
    )
    has_alignment = any(
        r[1] == "alignment"
        for r in conn.execute("PRAGMA table_info(tokens)")
    )
    has_source_text = any(
        r[1] == "source_text"
        for r in conn.execute("PRAGMA table_info(documents)")
    )

    conn.execute("BEGIN")
    try:
        meta_rows = conn.execute(
            "SELECT key, value FROM meta ORDER BY key ASC"
        ).fetchall()
        meta_dict = {str(k): str(v) for k, v in meta_rows}
        _check_schema_version(meta_dict)
        for key, value in meta_rows:
            if str(key).startswith(_JOB_META_PREFIX):
                continue
            content.update(b"M\0")
            content.update(_canonical_json([key, value]).encode("utf-8"))
            content.update(b"\n")

        source_text_expr = "source_text" if has_source_text else "NULL"
        doc_sql = (
            "SELECT doc_order, id, script_id, glyphs, transcription, translations, "
            "site, support, scribe, findspot, period, name, images, notes, lines, "
            f"{source_text_expr} FROM documents ORDER BY COALESCE(doc_order, rowid) ASC, id ASC"
        )
        total = 0
        for row in conn.execute(doc_sql):
            total += 1
            content.update(b"D\0")
            content.update(_canonical_json(list(row)).encode("utf-8"))
            content.update(b"\n")
            order.update(_canonical_json([row[0], row[1]]).encode("utf-8"))
            order.update(b"\n")

        align_expr = "alignment" if has_alignment else "NULL"
        form_expr = "form_state_json" if has_form_state else "NULL"
        tok_sql = (
            f"SELECT doc_id, {order_col}, position, line_no, text, kind, glyphs, "
            f"status, signs, alt, annotations, {align_expr}, {form_expr} "
            f"FROM tokens ORDER BY doc_id ASC, {order_col} ASC, rowid ASC"
        )
        for row in conn.execute(tok_sql):
            content.update(b"T\0")
            content.update(_canonical_json(list(row)).encode("utf-8"))
            content.update(b"\n")
    finally:
        conn.rollback()

    return content.hexdigest(), order.hexdigest(), total


def _stream_order_digest(conn: sqlite3.Connection) -> tuple[str, int]:
    """Return ``(order_digest, total_documents)`` in O(1) memory."""
    order = hashlib.sha256()
    total = 0
    for row in conn.execute(
        "SELECT doc_order, id FROM documents "
        "ORDER BY COALESCE(doc_order, rowid) ASC, id ASC"
    ):
        total += 1
        order.update(_canonical_json([row[0], row[1]]).encode("utf-8"))
        order.update(b"\n")
    return order.hexdigest(), total


def _write_manifest(manifest_path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with atomic_path(manifest_path) as tmp:
        tmp.write_text(text, encoding="utf-8", newline="\n")


def _read_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise JobConflictError(f"job manifest not found: {manifest_path}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JobConflictError(f"corrupt job manifest {manifest_path}: {exc}") from None
    if not isinstance(data, dict) or data.get("format") != _JOB_FORMAT:
        raise JobConflictError(
            f"unsupported or corrupt job manifest format in {manifest_path}"
        )
    required = {
        "job_id",
        "state",
        "generation",
        "source_path",
        "output_path",
        "source_sha256",
        "snapshot_sha256",
        "config_sha256",
        "order_digest",
        "total_documents",
        "completed_documents",
        "fts",
        "published",
    }
    missing = required - set(data)
    if missing:
        raise JobConflictError(
            f"job manifest {manifest_path} is missing required fields: {sorted(missing)}"
        )
    return data


def _read_working_checkpoint(working_path: Path) -> tuple[dict[str, Any], int]:
    """Read authoritative committed checkpoint metadata and document count."""
    if not working_path.is_file():
        raise JobConflictError(f"working database not found: {working_path}")
    conn: sqlite3.Connection | None = None
    try:
        conn = _open_existing_db(working_path)
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (_CHECKPOINT_META_KEY,)
        ).fetchone()
        if row is None:
            raise JobConflictError(
                f"working database {working_path} has no checkpoint record"
            )
        try:
            checkpoint = json.loads(str(row[0]))
        except json.JSONDecodeError as exc:
            raise JobConflictError(
                f"corrupt checkpoint record in {working_path}: {exc}"
            ) from None
        if not isinstance(checkpoint, dict):
            raise JobConflictError(f"invalid checkpoint record in {working_path}")
        count_row = conn.execute("SELECT COUNT(*) FROM documents").fetchone()
        doc_count = int(count_row[0]) if count_row is not None else 0
        return checkpoint, doc_count
    except sqlite3.Error as exc:
        raise JobConflictError(f"corrupt working database {working_path}: {exc}") from None
    finally:
        if conn is not None:
            conn.close()


def _create_snapshot(source_path: Path, snapshot_path: Path) -> tuple[str, str, str, int, dict[str, str]]:
    """Take a consistent SQLite backup of ``source_path`` into ``snapshot_path``.

    Returns ``(snapshot_sha256, source_content_sha256, order_digest, total_docs, meta)``.
    """
    src_conn: sqlite3.Connection | None = None
    snap_conn: sqlite3.Connection | None = None
    try:
        src_conn = _open_existing_db(source_path)
        snap_conn = sqlite3.connect(snapshot_path)
        src_conn.backup(snap_conn, pages=128)
        snap_conn.commit()
    except sqlite3.Error as exc:
        raise _corpus_db_error(source_path, exc) from None
    finally:
        if snap_conn is not None:
            snap_conn.close()
        if src_conn is not None:
            src_conn.close()

    # Validate corpus metadata, normalize any legacy NULL doc_order values on the
    # private snapshot, add a keyset index, and compute content + file hashes.
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(snapshot_path)
        meta = {
            str(k): str(v)
            for k, v in conn.execute("SELECT key, value FROM meta")
            if not str(k).startswith(_JOB_META_PREFIX)
        }
        _check_schema_version(meta)
        has_null_order = conn.execute(
            "SELECT 1 FROM documents WHERE doc_order IS NULL LIMIT 1"
        ).fetchone()
        if has_null_order is not None:
            conn.execute(
                "UPDATE documents SET doc_order = rowid - 1 WHERE doc_order IS NULL"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshot_doc_order_id "
            "ON documents(doc_order, id)"
        )
        conn.commit()
        content_sha, order_digest, total_docs = _stream_source_digest(conn)
    except sqlite3.Error as exc:
        raise _corpus_db_error(source_path, exc) from None
    finally:
        if conn is not None:
            conn.close()

    snapshot_sha = _sha256_file(snapshot_path)
    return snapshot_sha, content_sha, order_digest, total_docs, meta


def _init_working_db(
    working_path: Path,
    *,
    source_meta: dict[str, str],
    checkpoint: dict[str, Any],
) -> None:
    conn = sqlite3.connect(working_path)
    try:
        conn.executescript(_SCHEMA)
        meta_rows = {
            "schema_version": str(SCHEMA_VERSION),
            "script_id": source_meta.get("script_id", ""),
            "provenance": source_meta.get("provenance", "{}"),
            "sign_inventory": source_meta.get("sign_inventory", "[]"),
            _CHECKPOINT_META_KEY: _canonical_json(checkpoint),
        }
        if "appended_provenances" in source_meta:
            meta_rows["appended_provenances"] = source_meta["appended_provenances"]
        conn.executemany(
            "INSERT INTO meta(key, value) VALUES (?, ?)", list(meta_rows.items())
        )
        conn.commit()
    finally:
        conn.close()


def _next_snapshot_row(
    snap_conn: sqlite3.Connection,
    last_doc_order: int | None,
    last_doc_id: str | None,
) -> sqlite3.Row | None:
    """Fetch the next document row using forward keyset pagination (O(1) memory)."""
    if last_doc_order is None or last_doc_id is None:
        row: sqlite3.Row | None = snap_conn.execute(
            "SELECT * FROM documents ORDER BY doc_order ASC, id ASC LIMIT 1"
        ).fetchone()
        return row
    next_row: sqlite3.Row | None = snap_conn.execute(
        "SELECT * FROM documents "
        "WHERE (doc_order > ?) OR (doc_order = ? AND id > ?) "
        "ORDER BY doc_order ASC, id ASC LIMIT 1",
        (last_doc_order, last_doc_order, last_doc_id),
    ).fetchone()
    return next_row


def _publish_working(
    working_path: Path,
    publish_path: Path,
    output_path: Path,
    *,
    expected_total: int,
    expected_order_digest: str,
    fts: bool,
) -> None:
    """Build a clean publishable SQLite copy and publish it atomically."""
    if publish_path.exists():
        publish_path.unlink()
    work_conn: sqlite3.Connection | None = None
    pub_conn: sqlite3.Connection | None = None
    try:
        work_conn = _open_existing_db(working_path)
        pub_conn = sqlite3.connect(publish_path)
        work_conn.backup(pub_conn, pages=128)
        pub_conn.commit()
    finally:
        if pub_conn is not None:
            pub_conn.close()
        if work_conn is not None:
            work_conn.close()

    try:
        pub_conn = sqlite3.connect(publish_path)
        try:
            pub_conn.execute(
                "DELETE FROM meta WHERE key LIKE ?", (f"{_JOB_META_PREFIX}%",)
            )
            order_digest, total = _stream_order_digest(pub_conn)
            if total != expected_total:
                raise JobConflictError(
                    f"working corpus document count {total} differs from snapshot count {expected_total}"
                )
            if order_digest != expected_order_digest:
                raise JobConflictError(
                    "working corpus document order does not match source snapshot"
                )
            if fts:
                _build_fts(pub_conn)
            pub_conn.commit()
        finally:
            pub_conn.close()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _publish_sqlite(publish_path, output_path)
    finally:
        with contextlib.suppress(OSError):
            if publish_path.exists():
                publish_path.unlink()


def _status_from_manifest(
    manifest: dict[str, Any],
    *,
    job_dir: Path,
    resumed: bool,
    completed_documents: int | None = None,
    last_doc_order: int | None = None,
    last_doc_id: str | None = None,
    state: Literal["running", "cancelled", "completed", "failed"] | None = None,
    published: bool | None = None,
    error: str | None = None,
) -> JobStatus:
    resolved_state: Any = state if state is not None else manifest["state"]
    if resolved_state not in ("running", "cancelled", "completed", "failed"):
        resolved_state = "failed"
    return JobStatus(
        job_id=str(manifest["job_id"]),
        state=resolved_state,
        generation=str(manifest["generation"]),
        source_path=str(manifest["source_path"]),
        output_path=str(manifest["output_path"]),
        job_dir=str(job_dir),
        source_sha256=str(manifest["source_sha256"]),
        snapshot_sha256=str(manifest["snapshot_sha256"]),
        config_sha256=str(manifest["config_sha256"]),
        order_digest=str(manifest["order_digest"]),
        total_documents=int(manifest["total_documents"]),
        completed_documents=(
            int(completed_documents)
            if completed_documents is not None
            else int(manifest["completed_documents"])
        ),
        last_doc_order=(
            last_doc_order
            if completed_documents is not None
            else manifest.get("last_doc_order")
        ),
        last_doc_id=(
            last_doc_id
            if completed_documents is not None
            else manifest.get("last_doc_id")
        ),
        resumed=resumed,
        published=bool(published if published is not None else manifest["published"]),
        fts=bool(manifest["fts"]),
        error=error if error is not None else manifest.get("error"),
    )


def job_status(job_dir: str | Path) -> JobStatus:
    """Inspect a durable SQLite annotation job directory read-only.

    Reads ``job.json`` and reconciles committed progress against
    ``working.sqlite`` without acquiring a write lock or modifying any file.
    """
    job_path = Path(job_dir).resolve()
    manifest = _read_manifest(job_path / _MANIFEST_NAME)
    working_path = job_path / _WORKING_NAME
    completed = int(manifest["completed_documents"])
    last_order = manifest.get("last_doc_order")
    last_id = manifest.get("last_doc_id")
    if working_path.is_file():
        checkpoint, doc_count = _read_working_checkpoint(working_path)
        if doc_count == int(checkpoint.get("completed_documents", -1)):
            completed = doc_count
            last_order = checkpoint.get("last_doc_order")
            last_id = checkpoint.get("last_doc_id")
    return _status_from_manifest(
        manifest,
        job_dir=job_path,
        resumed=False,
        completed_documents=completed,
        last_doc_order=last_order,
        last_doc_id=last_id,
    )


def annotate_sqlite_job(
    source: str | Path,
    output: str | Path,
    *,
    job_dir: str | Path,
    resume: bool = False,
    fts: bool = True,
    tag_sentence: TagSentence | None = None,
    with_evidence: bool = True,
    with_dependencies: bool = False,
    long_input: Literal["strict", "partial", "windowed"] = "strict",
    progress: Callable[[int, int], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    on_phase: Callable[[str], None] | None = None,
    generation: str | None = None,
) -> JobStatus:
    """Run or resume a durable, checkpointed SQLite corpus annotation job.

    Reads documents one at a time from a frozen snapshot of ``source``, annotates
    each document through the shared ``aegean.greek.annotate_corpus`` engine,
    commits each annotated document and its checkpoint marker in a single SQLite
    transaction, and atomically publishes the finished corpus to ``output`` only
    when every document has succeeded.

    Parameters
    ----------
    source
        Path to an existing SQLite corpus database (read-only; WAL-safe).
    output
        Destination SQLite corpus path. Must not alias ``source`` or ``job_dir``.
        Any existing destination database is replaced transactionally only after
        all documents complete; failure leaves it untouched.
    job_dir
        Directory storing the frozen snapshot, working database, lock, and
        manifest. Must be fresh unless ``resume=True``.
    resume
        Continue an interrupted, cancelled, or publication-failed job in
        ``job_dir``. Rejects any mismatch in source data, snapshot integrity,
        output path, options, or active backend/model identity before writing.
    fts
        Build the FTS5 full-text index on the published output database
        (default ``True``). Lexical indexes are never auto-built during a job.
    tag_sentence, with_evidence, with_dependencies, long_input
        Passed directly to the shared Greek annotation engine.
    progress
        Optional ``(completed_documents, total_documents)`` callback fired after
        each committed document.
    cancel_check
        Optional zero-argument predicate checked before and after each document;
        returning ``True`` cleanly aborts with `JobCancelledError` while keeping
        all earlier commits resumable.
    on_phase
        Optional phase notification callback receiving ``"snapshot"``,
        ``"annotate"``, and ``"publish"``.
    generation
        Optional explicit ``analysis_generation`` string for a new job (useful
        when verifying exact parity against a reference run). Ignored on resume
        unless it matches the job's recorded generation.
    """
    source_path = Path(source).resolve()
    output_path = Path(output).resolve()
    job_path = Path(job_dir).resolve()
    _validate_paths(source_path, output_path, job_path)

    if not source_path.is_file():
        raise FileNotFoundError(f"source corpus database not found: {source_path}")

    # Validate annotator options and capture backend identity before touching disk.
    probe_annotator = _DocumentAnnotator(
        tag_sentence=tag_sentence,
        with_evidence=with_evidence,
        with_dependencies=with_dependencies,
        long_input=long_input,
        generation=generation,
    )

    job_path.mkdir(parents=True, exist_ok=True)
    lock_path = job_path / _LOCK_NAME
    manifest_path = job_path / _MANIFEST_NAME
    snapshot_path = job_path / _SNAPSHOT_NAME
    working_path = job_path / _WORKING_NAME
    publish_path = job_path / _PUBLISH_NAME

    lock = FileLock(lock_path, timeout=0.0)
    try:
        lock.__enter__()
    except TimeoutError:
        raise JobConflictError(
            f"job directory is locked by another active process: {job_path}"
        ) from None

    try:
        config_payload = {
            "format": _JOB_FORMAT,
            "output_path": str(output_path),
            "fts": bool(fts),
            "with_evidence": bool(with_evidence),
            "with_dependencies": bool(with_dependencies),
            "long_input": long_input,
            "annotation_configuration": probe_annotator.configuration,
            "backend_identity": probe_annotator.backend_identity,
        }
        config_sha = _sha256_bytes(_canonical_json(config_payload).encode("utf-8"))

        if not resume:
            existing = [
                p.name
                for p in (manifest_path, snapshot_path, working_path)
                if p.exists()
            ]
            if existing:
                raise JobConflictError(
                    f"job directory {job_path} already contains {', '.join(existing)}; "
                    "pass resume=True or choose a fresh job_dir"
                )
            if on_phase is not None:
                on_phase("snapshot")
            snapshot_sha, source_sha, order_digest, total_docs, source_meta = (
                _create_snapshot(source_path, snapshot_path)
            )
            job_id = uuid4().hex
            annotator = probe_annotator
            checkpoint: dict[str, Any] = {
                "job_id": job_id,
                "generation": annotator.generation,
                "config_sha256": config_sha,
                "total_documents": total_docs,
                "completed_documents": 0,
                "last_doc_order": None,
                "last_doc_id": None,
            }
            _init_working_db(
                working_path,
                source_meta=source_meta,
                checkpoint=checkpoint,
            )
            manifest: dict[str, Any] = {
                "format": _JOB_FORMAT,
                "job_id": job_id,
                "state": "running",
                "generation": annotator.generation,
                "source_path": str(source_path),
                "output_path": str(output_path),
                "source_sha256": source_sha,
                "snapshot_sha256": snapshot_sha,
                "config_sha256": config_sha,
                "config": config_payload,
                "order_digest": order_digest,
                "total_documents": total_docs,
                "completed_documents": 0,
                "last_doc_order": None,
                "last_doc_id": None,
                "fts": bool(fts),
                "published": False,
                "error": None,
            }
            _write_manifest(manifest_path, manifest)
            completed_docs = 0
            last_doc_order: int | None = None
            last_doc_id: str | None = None
        else:
            manifest = _read_manifest(manifest_path)
            if not snapshot_path.is_file():
                raise JobConflictError(f"snapshot database missing: {snapshot_path}")
            if str(output_path) != str(manifest["output_path"]):
                raise JobConflictError(
                    f"resume output path {output_path} differs from job output {manifest['output_path']}"
                )
            if config_sha != manifest["config_sha256"]:
                raise JobConflictError(
                    "resume configuration or active backend/model differs from the original job"
                )
            if generation is not None and generation != manifest["generation"]:
                raise JobConflictError(
                    "explicit generation differs from the recorded job generation"
                )
            actual_snapshot_sha = _sha256_file(snapshot_path)
            if actual_snapshot_sha != manifest["snapshot_sha256"]:
                raise JobConflictError(
                    "snapshot database digest mismatch; job snapshot was modified or corrupted"
                )
            # Confirm the live source database has not changed since snapshot creation.
            src_check: sqlite3.Connection | None = None
            try:
                src_check = _open_existing_db(source_path)
                live_source_sha, live_order_digest, live_total = _stream_source_digest(
                    src_check
                )
            except sqlite3.Error as exc:
                raise _corpus_db_error(source_path, exc) from None
            finally:
                if src_check is not None:
                    src_check.close()
            if (
                live_source_sha != manifest["source_sha256"]
                or live_order_digest != manifest["order_digest"]
                or live_total != int(manifest["total_documents"])
            ):
                raise JobConflictError(
                    "source database has changed since the job snapshot was created"
                )

            checkpoint, doc_count = _read_working_checkpoint(working_path)
            if (
                checkpoint.get("job_id") != manifest["job_id"]
                or checkpoint.get("generation") != manifest["generation"]
                or checkpoint.get("config_sha256") != manifest["config_sha256"]
            ):
                raise JobConflictError(
                    "working database checkpoint identity does not match job manifest"
                )
            if doc_count != int(checkpoint.get("completed_documents", -1)):
                raise JobConflictError(
                    f"working database document count ({doc_count}) disagrees with "
                    f"checkpoint ({checkpoint.get('completed_documents')})"
                )

            total_docs = int(manifest["total_documents"])
            completed_docs = doc_count
            last_doc_order = checkpoint.get("last_doc_order")
            last_doc_id = checkpoint.get("last_doc_id")

            if manifest["published"] and completed_docs == total_docs and output_path.is_file():
                return _status_from_manifest(
                    manifest,
                    job_dir=job_path,
                    resumed=True,
                    completed_documents=completed_docs,
                    last_doc_order=last_doc_order,
                    last_doc_id=last_doc_id,
                    state="completed",
                    published=True,
                )

            annotator = _DocumentAnnotator(
                tag_sentence=tag_sentence,
                with_evidence=with_evidence,
                with_dependencies=with_dependencies,
                long_input=long_input,
                generation=str(manifest["generation"]),
            )
            manifest["state"] = "running"
            manifest["error"] = None
            manifest["completed_documents"] = completed_docs
            manifest["last_doc_order"] = last_doc_order
            manifest["last_doc_id"] = last_doc_id
            _write_manifest(manifest_path, manifest)

        if on_phase is not None:
            on_phase("annotate")

        snap_conn: sqlite3.Connection | None = None
        work_conn: sqlite3.Connection | None = None
        try:
            snap_conn = _open_existing_db(snapshot_path)
            snap_conn.row_factory = sqlite3.Row
            order_col = "token_order" if _has_token_order(snap_conn) else "position"
            raw_schema_row = snap_conn.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            try:
                allow_form_state = (
                    int(raw_schema_row[0]) >= 3 if raw_schema_row is not None else False
                )
            except (TypeError, ValueError):
                allow_form_state = False

            work_conn = sqlite3.connect(working_path, isolation_level=None)
            work_conn.execute("PRAGMA busy_timeout = 30000")

            while completed_docs < total_docs:
                if cancel_check is not None and cancel_check():
                    manifest["state"] = "cancelled"
                    manifest["completed_documents"] = completed_docs
                    manifest["last_doc_order"] = last_doc_order
                    manifest["last_doc_id"] = last_doc_id
                    _write_manifest(manifest_path, manifest)
                    raise JobCancelledError(
                        f"job cancelled after {completed_docs}/{total_docs} documents"
                    )

                row = _next_snapshot_row(snap_conn, last_doc_order, last_doc_id)
                if row is None:
                    raise JobConflictError(
                        f"snapshot ended early at {completed_docs}/{total_docs} documents"
                    )
                doc_order = int(row["doc_order"])
                doc_id = str(row["id"])
                doc = _document_from_row(
                    snap_conn,
                    row,
                    order_col=order_col,
                    allow_form_state=allow_form_state,
                )
                annotated_doc = annotator.annotate_document(doc)

                if cancel_check is not None and cancel_check():
                    manifest["state"] = "cancelled"
                    manifest["completed_documents"] = completed_docs
                    manifest["last_doc_order"] = last_doc_order
                    manifest["last_doc_id"] = last_doc_id
                    _write_manifest(manifest_path, manifest)
                    raise JobCancelledError(
                        f"job cancelled after {completed_docs}/{total_docs} documents"
                    )

                next_completed = completed_docs + 1
                next_checkpoint = {
                    "job_id": manifest["job_id"],
                    "generation": manifest["generation"],
                    "config_sha256": manifest["config_sha256"],
                    "total_documents": total_docs,
                    "completed_documents": next_completed,
                    "last_doc_order": doc_order,
                    "last_doc_id": doc_id,
                }
                work_conn.execute("BEGIN IMMEDIATE")
                try:
                    _insert_document(work_conn, _document_to_dict(annotated_doc), doc_order)
                    work_conn.execute(
                        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                        (_CHECKPOINT_META_KEY, _canonical_json(next_checkpoint)),
                    )
                    work_conn.execute("COMMIT")
                except BaseException:
                    with contextlib.suppress(sqlite3.Error):
                        work_conn.execute("ROLLBACK")
                    raise

                completed_docs = next_completed
                last_doc_order = doc_order
                last_doc_id = doc_id
                manifest["completed_documents"] = completed_docs
                manifest["last_doc_order"] = last_doc_order
                manifest["last_doc_id"] = last_doc_id
                _write_manifest(manifest_path, manifest)
                if progress is not None:
                    progress(completed_docs, total_docs)
        except JobCancelledError:
            raise
        except BaseException as exc:
            manifest["state"] = "failed"
            manifest["error"] = f"{type(exc).__name__}: {exc}"
            manifest["completed_documents"] = completed_docs
            manifest["last_doc_order"] = last_doc_order
            manifest["last_doc_id"] = last_doc_id
            with contextlib.suppress(OSError):
                _write_manifest(manifest_path, manifest)
            raise
        finally:
            if work_conn is not None:
                work_conn.close()
            if snap_conn is not None:
                snap_conn.close()

        if on_phase is not None:
            on_phase("publish")

        try:
            _publish_working(
                working_path,
                publish_path,
                output_path,
                expected_total=total_docs,
                expected_order_digest=str(manifest["order_digest"]),
                fts=fts,
            )
        except BaseException as exc:
            manifest["state"] = "failed"
            manifest["error"] = f"publish failed ({type(exc).__name__}: {exc})"
            manifest["published"] = False
            with contextlib.suppress(OSError):
                _write_manifest(manifest_path, manifest)
            raise

        manifest["state"] = "completed"
        manifest["published"] = True
        manifest["error"] = None
        _write_manifest(manifest_path, manifest)
        _LOG.info(
            "completed SQLite annotation job %s (%d documents -> %s)",
            manifest["job_id"],
            total_docs,
            output_path,
        )
        return _status_from_manifest(
            manifest,
            job_dir=job_path,
            resumed=resume,
            completed_documents=completed_docs,
            last_doc_order=last_doc_order,
            last_doc_id=last_doc_id,
            state="completed",
            published=True,
            error=None,
        )
    finally:
        lock.__exit__(None, None, None)
