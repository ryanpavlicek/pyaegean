"""The SQLite progress hooks: ``progress(done, total)`` on the document-scale db paths.

``aegean.load("ddbdp")`` materializes 57k documents in ~100 s and ``to_sqlite`` on a
corpus that size runs for minutes, previously with zero feedback; `db.to_sqlite`
(build + append) and `db.from_sqlite` now report per-document completion, threaded
end-to-end through the ``ddbdp`` loader, so the CLI (and any caller) can show the run
moving. Correctness: the callback sequence is exact and the written database / loaded
corpus is identical with or without it. Adversarial: no callback means no calls, an
empty corpus/database means no calls, and a raising callback aborts loudly while the
atomic write keeps the prior file intact."""

from __future__ import annotations

import io
import shutil
import sys
from pathlib import Path

import pytest

from aegean import db
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind
from aegean.core.provenance import Provenance


def _corpus(n_docs: int, *, prefix: str = "D", source: str = "Synthetic A") -> Corpus:
    docs = []
    for i in range(n_docs):
        toks = [
            Token(f"λόγος{i}", TokenKind.WORD, line_no=0, position=0,
                  annotations={"lemma": "λόγος"}),
            Token("5", TokenKind.NUMERAL, ("5",), line_no=0, position=1,
                  status=ReadingStatus.UNCLEAR),
        ]
        docs.append(
            Document(id=f"{prefix}{i}", script_id="greek", tokens=toks, lines=[[0, 1]],
                     meta=DocumentMeta(site="Testville"))
        )
    prov = Provenance(source=source, license="CC0", citation=f"{source} (2026).")
    return Corpus(docs, provenance=prov, script_id="greek")


# ── to_sqlite (build) ────────────────────────────────────────────────────────────


def test_to_sqlite_progress_sequence_exact_and_db_identical(tmp_path: Path) -> None:
    c = _corpus(5)
    calls: list[tuple[int, int]] = []
    db.to_sqlite(c, tmp_path / "with.db", progress=lambda d, t: calls.append((d, t)))
    db.to_sqlite(c, tmp_path / "without.db")
    assert calls == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]  # every document, in order
    # the hook never changes the write: the two database files are byte-identical
    assert (tmp_path / "with.db").read_bytes() == (tmp_path / "without.db").read_bytes()
    loaded = db.from_sqlite(tmp_path / "with.db")
    assert loaded.documents == c.documents  # and the round trip still holds
    assert loaded.provenance == c.provenance


def test_to_sqlite_empty_corpus_and_no_callback_make_no_calls(tmp_path: Path) -> None:
    calls: list[tuple[int, int]] = []
    db.to_sqlite(_corpus(0), tmp_path / "empty.db", progress=lambda d, t: calls.append((d, t)))
    assert calls == []  # nothing to report on an empty corpus
    # and the default is no callback at all: just writes (content covered above)
    db.to_sqlite(_corpus(2), tmp_path / "plain.db")
    assert len(db.from_sqlite(tmp_path / "plain.db")) == 2


def test_to_sqlite_raising_callback_aborts_loudly_keeping_prior_db(tmp_path: Path) -> None:
    p = tmp_path / "c.db"
    db.to_sqlite(_corpus(2), p)
    before = p.read_bytes()

    def boom(done: int, total: int) -> None:
        raise RuntimeError("observer failed")

    with pytest.raises(RuntimeError, match="observer failed"):
        db.to_sqlite(_corpus(4, prefix="X"), p, progress=boom)
    assert p.read_bytes() == before  # the atomic build left the existing file untouched
    assert not list(tmp_path.glob("*.tmp"))  # and no temp debris behind


# ── to_sqlite(append=True) ───────────────────────────────────────────────────────


def test_append_progress_sequence_exact_and_db_content_identical(tmp_path: Path) -> None:
    base = tmp_path / "base.db"
    db.to_sqlite(_corpus(2), base)
    twin = tmp_path / "twin.db"
    shutil.copyfile(base, twin)
    added = _corpus(3, prefix="N", source="Synthetic B")

    calls: list[tuple[int, int]] = []
    db.to_sqlite(added, base, append=True, progress=lambda d, t: calls.append((d, t)))
    db.to_sqlite(added, twin, append=True)
    assert calls == [(1, 3), (2, 3), (3, 3)]  # counts the appended corpus's documents
    with_cb, without = db.from_sqlite(base), db.from_sqlite(twin)
    assert with_cb.documents == without.documents  # same 5 documents, same order
    assert len(with_cb) == 5
    assert with_cb.provenance == without.provenance  # both sources cited either way


# ── from_sqlite ──────────────────────────────────────────────────────────────────


def test_from_sqlite_progress_sequence_exact_and_corpus_unchanged(tmp_path: Path) -> None:
    p = tmp_path / "c.db"
    db.to_sqlite(_corpus(5), p)
    calls: list[tuple[int, int]] = []
    with_cb = db.from_sqlite(p, progress=lambda d, t: calls.append((d, t)))
    without = db.from_sqlite(p)
    assert calls == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]
    assert calls[-1] == (5, 5)  # the final call is (total, total)
    assert with_cb.documents == without.documents  # identical corpus either way
    assert with_cb.provenance == without.provenance
    assert with_cb.fingerprint() == without.fingerprint()


def test_from_sqlite_empty_database_makes_no_calls(tmp_path: Path) -> None:
    p = tmp_path / "empty.db"
    db.to_sqlite(_corpus(0), p)
    calls: list[tuple[int, int]] = []
    assert len(db.from_sqlite(p, progress=lambda d, t: calls.append((d, t)))) == 0
    assert calls == []


def test_from_sqlite_raising_callback_aborts_loudly(tmp_path: Path) -> None:
    p = tmp_path / "c.db"
    db.to_sqlite(_corpus(3), p)

    def boom(done: int, total: int) -> None:
        raise RuntimeError("observer failed")

    with pytest.raises(RuntimeError, match="observer failed"):
        db.from_sqlite(p, progress=boom)


# ── end-to-end: the ddbdp loader threads progress into from_sqlite ───────────────


def test_load_ddbdp_threads_progress_to_the_document_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ~100 s ``aegean.load("ddbdp")`` path: the loader's hook reaches every
    materialized document (exercised against a small stand-in database)."""
    from aegean.scripts.greek import ddbdp as ddbdp_module

    p = tmp_path / "ddbdp.sqlite"
    db.to_sqlite(_corpus(4, prefix="p.mich;1;"), p)
    monkeypatch.setattr(ddbdp_module, "ddbdp_db", lambda: p)

    calls: list[tuple[int, int]] = []
    with_cb = ddbdp_module.load_ddbdp(progress=lambda d, t: calls.append((d, t)))
    without = ddbdp_module.load_ddbdp()
    assert calls == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert with_cb.documents == without.documents  # the hook never changes the corpus


# ── the CLI live line ────────────────────────────────────────────────────────────


def test_cli_live_progress_paints_tty_only() -> None:
    """The db commands' painter: silent when stderr is not a TTY (piped/CI runs stay
    clean), a repainted line ending in a newline at completion when it is."""
    from aegean.cli._db import live_progress

    class _Tty(io.StringIO):
        def isatty(self) -> bool:  # the painter's TTY probe
            return True

    paint = live_progress("writing")
    real = sys.stderr
    try:
        sys.stderr = _Tty()
        for d in range(1, 5):
            paint(d, 4)
        tty_out = sys.stderr.getvalue()
    finally:
        sys.stderr = real
    assert "\r  writing 1/4 documents (25%)" in tty_out
    assert tty_out.endswith("writing 4/4 documents (100%)\n")  # final call closes the line

    try:
        sys.stderr = io.StringIO()  # isatty() is False on a plain StringIO
        paint(2, 4)
        piped = sys.stderr.getvalue()
    finally:
        sys.stderr = real
    assert piped == ""  # captured/piped output stays clean


def test_cli_db_build_from_db_file_loads_and_writes(tmp_path: Path) -> None:
    """`aegean db build <file.db> -o out.db` routes the load through the progress-aware
    from_sqlite path and still produces a faithful database (non-TTY: no line painted)."""
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    src = tmp_path / "src.db"
    db.to_sqlite(_corpus(3), src)
    out = tmp_path / "out.db"
    r = CliRunner().invoke(_build_app(), ["db", "build", str(src), "-o", str(out)])
    assert r.exit_code == 0, r.output
    assert "\r" not in r.output  # no repainted line leaks into a captured run
    assert db.from_sqlite(out).documents == db.from_sqlite(src).documents
