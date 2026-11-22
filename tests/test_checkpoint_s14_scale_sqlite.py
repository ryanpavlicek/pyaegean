"""Regression tests for §14 SQLite read-only/single-scan/hardlink-fallback, interop O(N), and greek.__dir__."""

from __future__ import annotations

import os
import pathlib
import sqlite3

import pytest

import aegean
from aegean import db
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind


def test_from_sqlite_and_stream_do_not_create_missing_db_file(tmp_path: pathlib.Path) -> None:
    missing = tmp_path / "does_not_exist.db"
    with pytest.raises(ValueError, match="not a pyaegean corpus database"):
        db.from_sqlite(missing)
    assert not missing.exists()

    with pytest.raises(ValueError, match="not a pyaegean corpus database"):
        list(db.stream(missing))
    assert not missing.exists()


def test_sqlite_composite_index_and_single_scan_preserves_empty_docs_and_order(
    tmp_path: pathlib.Path,
) -> None:
    docs = [
        Document(
            id="D1",
            script_id="greek",
            tokens=[
                Token("ὁ", TokenKind.WORD, (), None, 0, 0),
                Token("λόγος", TokenKind.WORD, (), None, 0, 1),
            ],
            lines=[[0, 1]],
            meta=DocumentMeta(site="Athens"),
        ),
        Document(
            id="D2_empty",
            script_id="greek",
            tokens=[],
            lines=[],
            meta=DocumentMeta(site="Delphi"),
        ),
        Document(
            id="D3",
            script_id="greek",
            tokens=[Token("ἔστιν", TokenKind.WORD, (), None, 0, 0)],
            lines=[[0]],
            meta=DocumentMeta(site="Thebes"),
        ),
    ]
    corpus = Corpus(docs, script_id="greek")
    target = tmp_path / "order.db"
    db.to_sqlite(corpus, target)

    # Composite index covers (doc_id, token_order)
    conn = sqlite3.connect(str(target))
    try:
        cols = [r[2] for r in conn.execute("PRAGMA index_info(idx_tokens_doc)")]
    finally:
        conn.close()
    assert cols == ["doc_id", "token_order"]

    seen_progress: list[tuple[int, int]] = []
    loaded = db.from_sqlite(target, progress=lambda done, total: seen_progress.append((done, total)))
    assert [d.id for d in loaded.documents] == ["D1", "D2_empty", "D3"]
    assert [[t.text for t in d.tokens] for d in loaded.documents] == [
        ["ὁ", "λόγος"],
        [],
        ["ἔστιν"],
    ]
    assert seen_progress == [(1, 3), (2, 3), (3, 3)]


def test_publish_sqlite_works_when_hardlinks_are_unsupported(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = Document(
        id="D1",
        script_id="greek",
        tokens=[Token("λόγος", TokenKind.WORD, (), None, 0, 0)],
        lines=[[0]],
        meta=DocumentMeta(site="Athens"),
    )
    corpus = Corpus([doc], script_id="greek")
    target = tmp_path / "no_hardlink.db"

    def _deny_link(_src: object, _dst: object) -> None:
        raise OSError("hardlinks unsupported on filesystem")

    monkeypatch.setattr(os, "link", _deny_link)
    db.to_sqlite(corpus, target)
    back = db.from_sqlite(target)
    assert [d.id for d in back.documents] == ["D1"]
    assert [t.text for t in back.documents[0].tokens] == ["λόγος"]


def test_greek_dir_exposes_all_public_exports() -> None:
    d = dir(aegean.greek)
    for name in aegean.greek.__all__:
        assert name in d
