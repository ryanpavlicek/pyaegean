"""Tests for durable, checkpointed, resumable SQLite corpus annotation jobs."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from aegean import db
from aegean._locking import FileLock
from aegean.core.corpus import Corpus
from aegean.core.model import (
    Document,
    DocumentMeta,
    ReadingStatus,
    SourceAlignment,
    Token,
    TokenFormState,
    TokenKind,
)
from aegean.core.provenance import Provenance
from aegean.db import (
    JobCancelledError,
    JobConflictError,
    annotate_sqlite_job,
    from_sqlite,
    job_status,
    lexical_index_status,
    search,
    to_sqlite,
)
from aegean.greek.annotate import _DocumentAnnotator


def _make_rich_greek_corpus() -> Corpus:
    """Build a multi-document Greek corpus exercising edge cases for parity testing."""
    src_text = "ἐν ἀρχῇ ἦν ὁ λόγος."
    docs = [
        Document(
            id="doc_1",
            script_id="greek",
            transcription=src_text,
            source_text=src_text,
            meta=DocumentMeta(
                site="Alexandria",
                period="Koine",
                name="John 1.1",
                notes=["opening clause"],
            ),
            translations=["In the beginning was the Word."],
            tokens=[
                Token(
                    text="ἐν",
                    kind=TokenKind.WORD,
                    position=0,
                    line_no=1,
                    annotations={"source_morph": "PREP"},
                    alignment=SourceAlignment(
                        document_id="doc_1",
                        sentence_id="s1",
                        source_token_id="t1",
                        original_text="ἐν",
                        start_char=0,
                        end_char=2,
                        whitespace_before="",
                        normalized_text="ἐν",
                    ),
                ),
                Token(
                    text="ἀρχῇ",
                    kind=TokenKind.WORD,
                    position=1,
                    line_no=1,
                    annotations={
                        "lemma": "old_lemma",
                        "lemma_review_decision": "accept",
                        "lemma_verified": "true",
                        "source_morph": "N-DSF",
                    },
                    alignment=SourceAlignment(
                        document_id="doc_1",
                        sentence_id="s1",
                        source_token_id="t2",
                        original_text="ἀρχῇ",
                        start_char=3,
                        end_char=7,
                        whitespace_before=" ",
                        normalized_text="ἀρχῇ",
                    ),
                    form_state=TokenFormState(
                        diplomatic="ἀρχῇ",
                        regularized="ἀρχῇ",
                    ),
                ),
                Token(
                    text="ἦν",
                    kind=TokenKind.WORD,
                    position=2,
                    line_no=2,
                    alignment=SourceAlignment(
                        document_id="doc_1",
                        sentence_id="s1",
                        source_token_id="t3",
                        original_text="ἦν",
                        start_char=8,
                        end_char=10,
                        whitespace_before=" ",
                        normalized_text="ἦν",
                    ),
                ),
                Token(
                    text="ὁ",
                    kind=TokenKind.WORD,
                    position=3,
                    line_no=2,
                    alignment=SourceAlignment(
                        document_id="doc_1",
                        sentence_id="s1",
                        source_token_id="t4",
                        original_text="ὁ",
                        start_char=11,
                        end_char=12,
                        whitespace_before=" ",
                        normalized_text="ὁ",
                    ),
                ),
                Token(
                    text="λόγος",
                    kind=TokenKind.WORD,
                    position=4,
                    line_no=2,
                    status=ReadingStatus.UNCLEAR,
                    alignment=SourceAlignment(
                        document_id="doc_1",
                        sentence_id="s1",
                        source_token_id="t5",
                        original_text="λόγος",
                        start_char=13,
                        end_char=18,
                        whitespace_before=" ",
                        normalized_text="λόγος",
                    ),
                ),
                Token(
                    text=".",
                    kind=TokenKind.PUNCT,
                    position=5,
                    line_no=2,
                    alignment=SourceAlignment(
                        document_id="doc_1",
                        sentence_id="s1",
                        source_token_id="t6",
                        original_text=".",
                        start_char=18,
                        end_char=19,
                        whitespace_before="",
                        normalized_text=".",
                    ),
                ),
            ],
            lines=[[0, 1], [2, 3, 4, 5]],
        ),
        Document(
            id="doc_empty",
            script_id="greek",
            transcription="",
            meta=DocumentMeta(name="Empty tablet"),
            tokens=[],
            lines=[],
        ),
        Document(
            id="doc_punct_only",
            script_id="greek",
            transcription="· .",
            tokens=[
                Token(text="·", kind=TokenKind.PUNCT, position=0, line_no=1),
                Token(text=".", kind=TokenKind.PUNCT, position=1, line_no=1),
            ],
            lines=[[0, 1]],
        ),
        Document(
            id="doc_dup_a",
            script_id="greek",
            transcription="καὶ ὁ λόγος",
            tokens=[
                Token(text="καὶ", kind=TokenKind.WORD, position=0, line_no=1),
                Token(text="ὁ", kind=TokenKind.WORD, position=1, line_no=1),
                Token(text="λόγος", kind=TokenKind.WORD, position=2, line_no=1),
            ],
            lines=[[0, 1, 2]],
        ),
        Document(
            id="doc_dup_b",
            script_id="greek",
            transcription="καὶ ὁ λόγος",
            tokens=[
                Token(text="καὶ", kind=TokenKind.WORD, position=0, line_no=1),
                Token(text="ὁ", kind=TokenKind.WORD, position=1, line_no=1),
                Token(text="λόγος", kind=TokenKind.WORD, position=2, line_no=1),
            ],
            lines=[[0, 1, 2]],
        ),
    ]
    prov = Provenance(
        source="Test Koine Sample",
        citation="Test Edition 2026",
        license="CC0",
    )
    return Corpus(docs, provenance=prov, script_id="greek")


def _assert_corpora_identical(actual: Corpus, expected: Corpus) -> None:
    assert actual.script_id == expected.script_id
    assert actual.provenance == expected.provenance
    assert len(actual.documents) == len(expected.documents)
    for got, want in zip(actual.documents, expected.documents, strict=True):
        assert got.id == want.id
        assert got.script_id == want.script_id
        assert got.transcription == want.transcription
        assert got.source_text == want.source_text
        assert got.translations == want.translations
        assert got.meta == want.meta
        assert got.lines == want.lines
        assert len(got.tokens) == len(want.tokens)
        for gt, wt in zip(got.tokens, want.tokens, strict=True):
            assert gt.text == wt.text
            assert gt.kind == wt.kind
            assert gt.position == wt.position
            assert gt.line_no == wt.line_no
            assert gt.status == wt.status
            assert gt.signs == wt.signs
            assert gt.alt == wt.alt
            assert gt.alignment == wt.alignment
            assert gt.form_state == wt.form_state
            assert gt.annotations == wt.annotations


def _deterministic_tagger(forms: list[str]) -> list[tuple[str, str]]:
    return [(f"L:{form}", "NOUN") for form in forms]


def test_resumable_job_exact_parity_with_collected_baseline(tmp_path: Path) -> None:
    corpus = _make_rich_greek_corpus()
    src = tmp_path / "source.db"
    out = tmp_path / "annotated.db"
    job_dir = tmp_path / "job"
    to_sqlite(corpus, src)

    phases: list[str] = []
    progress_calls: list[tuple[int, int]] = []
    fixed_gen = "gen-parity-baseline-001"

    status = annotate_sqlite_job(
        src,
        out,
        job_dir=job_dir,
        progress=lambda done, total: progress_calls.append((done, total)),
        on_phase=phases.append,
        generation=fixed_gen,
    )

    assert status.state == "completed"
    assert status.published is True
    assert status.resumed is False
    assert status.generation == fixed_gen
    assert status.total_documents == len(corpus.documents)
    assert status.completed_documents == len(corpus.documents)
    assert phases == ["snapshot", "annotate", "publish"]
    assert progress_calls == [(i, 5) for i in range(1, 6)]

    # Build collected reference using the exact same generation.
    annotator = _DocumentAnnotator(generation=fixed_gen)
    source_loaded = from_sqlite(src)
    expected = Corpus(
        [annotator.annotate_document(d) for d in source_loaded.documents],
        source_loaded.sign_inventory,
        source_loaded.provenance,
        source_loaded.script_id,
    )
    actual = from_sqlite(out)
    _assert_corpora_identical(actual, expected)

    # Prior review decision must be marked stale while source morphology survives.
    tok_arche = actual.get("doc_1").tokens[1]
    assert tok_arche.annotations["lemma_review_decision"] == "stale"
    assert "lemma_verified" not in tok_arche.annotations or tok_arche.annotations["lemma_verified"] in ("true", "false")
    assert tok_arche.annotations["source_morph"] == "N-DSF"
    assert tok_arche.annotations["analysis_generation"] == fixed_gen

    # Lexical index is NOT auto-built during jobs; FTS5 search works; no working meta keys leak.
    assert lexical_index_status(out)["state"] == "absent"
    assert search(out, "λόγος")
    conn = sqlite3.connect(out)
    try:
        job_meta_keys = [
            r[0]
            for r in conn.execute("SELECT key FROM meta WHERE key LIKE '_aegean_job_%'")
        ]
    finally:
        conn.close()
    assert job_meta_keys == []


def test_failure_mid_job_and_resume_match_uninterrupted_run(tmp_path: Path) -> None:
    corpus = _make_rich_greek_corpus()
    src = tmp_path / "source.db"
    out = tmp_path / "annotated.db"
    ref_out = tmp_path / "reference.db"
    job_dir = tmp_path / "job"
    to_sqlite(corpus, src)

    calls_run1: list[list[str]] = []

    def flaky_tagger(forms: list[str]) -> list[tuple[str, str]]:
        calls_run1.append(list(forms))
        if len(calls_run1) == 3:
            raise RuntimeError("boom on third word group")
        return _deterministic_tagger(forms)

    fixed_gen = "gen-resume-parity-002"
    with pytest.raises(RuntimeError, match="boom on third word group"):
        annotate_sqlite_job(
            src,
            out,
            job_dir=job_dir,
            tag_sentence=flaky_tagger,
            generation=fixed_gen,
        )

    assert not out.exists()
    mid = job_status(job_dir)
    assert mid.state == "failed"
    assert mid.published is False
    # doc_1 (2 line groups), doc_empty (0), doc_punct_only (0) committed; doc_dup_a failed on 3rd call
    assert mid.completed_documents == 3
    assert mid.last_doc_id == "doc_punct_only"

    calls_run2: list[list[str]] = []

    def resume_tagger(forms: list[str]) -> list[tuple[str, str]]:
        calls_run2.append(list(forms))
        return _deterministic_tagger(forms)

    # Preserve same callable identity as flaky_tagger for resume config check.
    resume_tagger.__qualname__ = flaky_tagger.__qualname__

    done = annotate_sqlite_job(
        src,
        out,
        job_dir=job_dir,
        resume=True,
        tag_sentence=resume_tagger,
    )
    assert done.state == "completed"
    assert done.resumed is True
    assert done.published is True
    assert done.generation == fixed_gen
    # Only doc_dup_a and doc_dup_b were left to tag!
    assert len(calls_run2) == 2

    # Uninterrupted reference run with the same generation must match 100%.
    annotate_sqlite_job(
        src,
        ref_out,
        job_dir=tmp_path / "ref_job",
        tag_sentence=resume_tagger,
        generation=fixed_gen,
    )
    _assert_corpora_identical(from_sqlite(out), from_sqlite(ref_out))

    # Re-resuming an already completed published job is a clean no-op.
    calls_before_noop = len(calls_run2)
    again = annotate_sqlite_job(
        src,
        out,
        job_dir=job_dir,
        resume=True,
        tag_sentence=resume_tagger,
    )
    assert again.state == "completed"
    assert again.published is True
    assert again.resumed is True
    assert len(calls_run2) == calls_before_noop  # zero additional calls


def test_crash_after_commit_before_manifest_update_does_not_duplicate(tmp_path: Path) -> None:
    corpus = _make_rich_greek_corpus()
    src = tmp_path / "source.db"
    out = tmp_path / "annotated.db"
    job_dir = tmp_path / "job"
    to_sqlite(corpus, src)

    # Cancel cleanly after 3 docs, then manually rewind job.json to simulate a crash
    # right after working.sqlite COMMIT and before job.json was updated.
    seen = 0

    def cancel_after_three() -> bool:
        return seen >= 3

    def on_progress(done: int, total: int) -> None:
        nonlocal seen
        seen = done

    with pytest.raises(JobCancelledError):
        annotate_sqlite_job(
            src,
            out,
            job_dir=job_dir,
            progress=on_progress,
            cancel_check=cancel_after_three,
        )

    manifest_path = job_dir / "job.json"
    stale_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stale_manifest["completed_documents"] = 1
    stale_manifest["last_doc_order"] = 0
    stale_manifest["last_doc_id"] = "doc_1"
    stale_manifest["state"] = "running"
    manifest_path.write_text(json.dumps(stale_manifest), encoding="utf-8")

    # Read-only status reconciles from working.sqlite's committed checkpoint (3 docs).
    assert job_status(job_dir).completed_documents == 3

    # Resume uses working.sqlite's checkpoint (3 docs) and completes with 0 duplicates.
    resumed_progress: list[tuple[int, int]] = []
    status = annotate_sqlite_job(
        src,
        out,
        job_dir=job_dir,
        resume=True,
        progress=lambda d, t: resumed_progress.append((d, t)),
    )
    assert status.completed_documents == 5
    assert resumed_progress == [(4, 5), (5, 5)]
    assert [d.id for d in from_sqlite(out).documents] == [
        "doc_1", "doc_empty", "doc_punct_only", "doc_dup_a", "doc_dup_b"
    ]


def test_abrupt_subprocess_death_releases_lock_and_resumes_cleanly(tmp_path: Path) -> None:
    corpus = _make_rich_greek_corpus()
    src = tmp_path / "source.db"
    out = tmp_path / "annotated.db"
    job_dir = tmp_path / "job"
    to_sqlite(corpus, src)

    child_code = f"""
import os
from aegean.db import annotate_sqlite_job

def crash_after_two(done, total):
    if done == 2:
        os._exit(137)

annotate_sqlite_job(
    {str(src)!r},
    {str(out)!r},
    job_dir={str(job_dir)!r},
    progress=crash_after_two,
)
"""
    proc = subprocess.run(
        [sys.executable, "-c", child_code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 137
    assert not out.exists()

    mid = job_status(job_dir)
    assert mid.completed_documents == 2
    assert mid.last_doc_id == "doc_empty"

    # OS released FileLock on child death; parent resumes cleanly without waiting.
    resumed = annotate_sqlite_job(src, out, job_dir=job_dir, resume=True)
    assert resumed.state == "completed"
    assert resumed.completed_documents == 5
    assert len(from_sqlite(out)) == 5


def test_failed_publish_preserves_prior_output_and_resumes_without_reannotating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import aegean.db_jobs as db_jobs

    corpus = _make_rich_greek_corpus()
    src = tmp_path / "source.db"
    out = tmp_path / "existing.db"
    job_dir = tmp_path / "job"
    to_sqlite(corpus, src)

    # Seed an existing output database that must stay intact if publication fails.
    prior_corpus = Corpus([corpus.documents[0]], script_id="greek")
    to_sqlite(prior_corpus, out)

    tag_calls = 0

    def counting_tagger(forms: list[str]) -> list[tuple[str, str]]:
        nonlocal tag_calls
        tag_calls += 1
        return _deterministic_tagger(forms)

    real_publish = db_jobs._publish_sqlite

    def fail_publish(*args: Any, **kwargs: Any) -> None:
        raise sqlite3.OperationalError("simulated destination busy")

    monkeypatch.setattr(db_jobs, "_publish_sqlite", fail_publish)
    with pytest.raises(sqlite3.OperationalError, match="simulated destination busy"):
        annotate_sqlite_job(src, out, job_dir=job_dir, tag_sentence=counting_tagger)

    # Prior destination untouched; working.sqlite has all 5 documents committed.
    assert len(from_sqlite(out)) == 1
    mid = job_status(job_dir)
    assert mid.state == "failed"
    assert mid.published is False
    assert mid.completed_documents == 5
    calls_before_resume = tag_calls
    assert calls_before_resume > 0

    # Restore publish and resume: 0 additional tagger calls!
    monkeypatch.setattr(db_jobs, "_publish_sqlite", real_publish)
    done = annotate_sqlite_job(
        src, out, job_dir=job_dir, resume=True, tag_sentence=counting_tagger
    )
    assert done.state == "completed"
    assert done.published is True
    assert tag_calls == calls_before_resume
    assert len(from_sqlite(out)) == 5


def test_live_wal_source_and_existing_wal_destination_readers(tmp_path: Path) -> None:
    corpus = _make_rich_greek_corpus()
    src = tmp_path / "source_wal.db"
    out = tmp_path / "out_wal.db"
    job_dir = tmp_path / "job"
    to_sqlite(corpus, src)

    # Switch source to WAL mode, write a new committed document into WAL without checkpointing,
    # and hold an open reader on source while the job snapshots it.
    wal_writer = sqlite3.connect(src)
    wal_writer.execute("PRAGMA journal_mode=WAL")
    wal_writer.execute("PRAGMA wal_autocheckpoint=0")
    wal_writer.execute(
        "INSERT INTO documents(doc_order, id, script_id, glyphs, transcription, translations, "
        "site, support, scribe, findspot, period, name, images, notes, lines, source_text) "
        "VALUES (5, 'doc_wal', 'greek', NULL, 'θεός', '[]', NULL, NULL, NULL, NULL, NULL, "
        "'WAL doc', '[]', '[]', '[[0]]', NULL)"
    )
    wal_writer.execute(
        "INSERT INTO tokens(doc_id, token_order, position, line_no, text, kind, glyphs, "
        "status, signs, alt, annotations, alignment, form_state_json) "
        "VALUES ('doc_wal', 0, 0, 1, 'θεός', 'word', NULL, 'certain', '[]', '[]', '{}', NULL, NULL)"
    )
    wal_writer.commit()

    # Seed destination in WAL mode with an active reader holding a snapshot.
    to_sqlite(Corpus([corpus.documents[0]], script_id="greek"), out)
    out_reader = sqlite3.connect(out)
    out_reader.execute("PRAGMA journal_mode=WAL")
    out_reader.execute("BEGIN")
    assert out_reader.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1

    try:
        status = annotate_sqlite_job(src, out, job_dir=job_dir)
        assert status.state == "completed"
        assert status.total_documents == 6
        # Existing WAL reader still sees its consistent prior snapshot.
        assert out_reader.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    finally:
        out_reader.rollback()
        out_reader.close()
        wal_writer.close()

    loaded = from_sqlite(out)
    assert len(loaded) == 6
    assert loaded.get("doc_wal").tokens[0].annotations["lemma"] == "θεός"


def test_adversarial_conflicts_and_resume_identity_guards(tmp_path: Path) -> None:
    corpus = _make_rich_greek_corpus()
    src = tmp_path / "source.db"
    out = tmp_path / "annotated.db"
    job_dir = tmp_path / "job"
    to_sqlite(corpus, src)

    # Aliasing checks
    with pytest.raises(JobConflictError, match="same path"):
        annotate_sqlite_job(src, src, job_dir=job_dir)
    with pytest.raises(JobConflictError, match="conflicts with job directory"):
        annotate_sqlite_job(src, job_dir / "nested.db", job_dir=job_dir)
    with pytest.raises(JobConflictError, match="conflicts with job directory"):
        annotate_sqlite_job(src, out, job_dir=src.parent)

    # Active lock rejection (non-blocking)
    job_dir.mkdir(parents=True, exist_ok=True)
    with FileLock(job_dir / "job.lock"):
        with pytest.raises(JobConflictError, match="locked"):
            annotate_sqlite_job(src, out, job_dir=job_dir)

    # Start and cancel a real job so we can test every resume mismatch guard.
    with pytest.raises(JobCancelledError):
        annotate_sqlite_job(src, out, job_dir=job_dir, cancel_check=lambda: True)

    # Fresh resume=False on an existing job_dir must refuse.
    with pytest.raises(JobConflictError, match="already contains"):
        annotate_sqlite_job(src, out, job_dir=job_dir, resume=False)

    # Changed output path rejected.
    with pytest.raises(JobConflictError, match="output path"):
        annotate_sqlite_job(src, tmp_path / "other.db", job_dir=job_dir, resume=True)

    # Changed options (with_evidence / fts / backend) rejected.
    with pytest.raises(JobConflictError, match="configuration"):
        annotate_sqlite_job(
            src, out, job_dir=job_dir, resume=True, with_evidence=False
        )
    with pytest.raises(JobConflictError, match="configuration"):
        annotate_sqlite_job(src, out, job_dir=job_dir, resume=True, fts=False)
    with pytest.raises(JobConflictError, match="configuration"):
        annotate_sqlite_job(
            src, out, job_dir=job_dir, resume=True, tag_sentence=_deterministic_tagger
        )

    # Tampered source database rejected before writing.
    modified_corpus = Corpus(
        [*corpus.documents[:-1]],
        provenance=corpus.provenance,
        script_id="greek",
    )
    to_sqlite(modified_corpus, src)
    with pytest.raises(JobConflictError, match="source database has changed"):
        annotate_sqlite_job(src, out, job_dir=job_dir, resume=True)
    # Restore original source so we can test snapshot tampering and corrupt manifest.
    to_sqlite(corpus, src)

    snap_bytes = (job_dir / "snapshot.sqlite").read_bytes()
    (job_dir / "snapshot.sqlite").write_bytes(snap_bytes + b"\0")
    with pytest.raises(JobConflictError, match="snapshot database digest mismatch"):
        annotate_sqlite_job(src, out, job_dir=job_dir, resume=True)
    (job_dir / "snapshot.sqlite").write_bytes(snap_bytes)

    (job_dir / "job.json").write_text("{truncated", encoding="utf-8")
    with pytest.raises(JobConflictError, match="corrupt job manifest"):
        annotate_sqlite_job(src, out, job_dir=job_dir, resume=True)


def test_cli_db_annotate_and_job_status_journey(tmp_path: Path) -> None:
    pytest.importorskip("typer")
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    app = _build_app()

    corpus = _make_rich_greek_corpus()
    src = tmp_path / "source.db"
    out = tmp_path / "cli_out.db"
    job_dir = tmp_path / "cli_job"
    to_sqlite(corpus, src)

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "db",
            "annotate",
            str(src),
            "-o",
            str(out),
            "--job-dir",
            str(job_dir),
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.stdout)
    assert payload["state"] == "completed"
    assert payload["published"] is True
    assert payload["completed_documents"] == 5

    st = runner.invoke(app, ["db", "job-status", str(job_dir), "--json"])
    assert st.exit_code == 0, st.output
    st_payload = json.loads(st.stdout)
    assert st_payload["job_id"] == payload["job_id"]
    assert st_payload["completed_documents"] == 5

    # Re-read final artifact and verify real Greek annotations survived end-to-end.
    reloaded = from_sqlite(out)
    assert len(reloaded) == 5
    doc1 = reloaded.get("doc_1")
    assert doc1.tokens[0].annotations["lemma"] == "ἐν"
    assert doc1.tokens[4].annotations["lemma"] == "λόγος"
    assert doc1.tokens[4].annotations["analysis_generation"] == payload["generation"]
    assert db.job_status(job_dir).published is True
