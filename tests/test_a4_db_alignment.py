"""A4 source-alignment persistence and schema-1 SQLite compatibility."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from aegean.core.model import Document, SourceAlignment, Token, TokenKind
from aegean.core.corpus import Corpus
from aegean.db import from_sqlite, to_sqlite


def _aligned_corpus(doc_id: str = "d1") -> Corpus:
    alignment = SourceAlignment(
        document_id=doc_id,
        sentence_id="s1",
        source_token_id=f"{doc_id}:t0",
        original_text="λόγος",
        start_char=1,
        end_char=6,
        whitespace_before="\t",
        normalized_text="λογος",
        normalization_ops=("unicode:nfd", "strip:accent"),
    )
    token = Token(
        text="λογος", kind=TokenKind.WORD, position=0, alignment=alignment
    )
    return Corpus(
        [Document(
            id=doc_id, script_id="greek", tokens=[token], lines=[[0]],
            source_text="\tλόγος\n",
        )],
        script_id="greek",
    )


def _schema1(path: Path) -> None:
    """Write the previous-release (pre-A4) layout without new columns."""
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE documents (
                doc_order INTEGER, id TEXT PRIMARY KEY, script_id TEXT, glyphs TEXT,
                transcription TEXT, translations TEXT, site TEXT, support TEXT,
                scribe TEXT, findspot TEXT, period TEXT, name TEXT, images TEXT,
                notes TEXT, lines TEXT
            );
            CREATE TABLE tokens (
                doc_id TEXT, position INTEGER, line_no INTEGER, text TEXT, kind TEXT,
                glyphs TEXT, status TEXT, signs TEXT, alt TEXT, annotations TEXT
            );
            INSERT INTO meta VALUES ('schema_version', '1');
            INSERT INTO meta VALUES ('script_id', 'greek');
            INSERT INTO meta VALUES ('provenance', 'null');
            INSERT INTO meta VALUES ('sign_inventory', 'null');
            INSERT INTO documents VALUES
                (0, 'legacy', 'greek', '', '', '[]', '', '', '', '', '', '', '[]', '[]', '[[0]]');
            INSERT INTO tokens VALUES
                ('legacy', 0, 0, 'παῖς', 'word', NULL, 'certain', '[]', '[]', '{}');
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_new_database_roundtrips_source_alignment_exactly(tmp_path: Path) -> None:
    path = tmp_path / "aligned.db"
    original = _aligned_corpus()
    to_sqlite(original, path, fts=False)

    loaded = from_sqlite(path)
    document = loaded.documents[0]
    assert document.source_text == "\tλόγος\n"
    assert document.tokens[0].alignment == original.documents[0].tokens[0].alignment


def test_schema1_read_defaults_new_alignment_fields_to_none(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    _schema1(path)

    loaded = from_sqlite(path)
    assert loaded.documents[0].source_text is None
    assert loaded.documents[0].tokens[0].alignment is None


def test_append_migrates_schema1_and_preserves_old_and_new_rows(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    _schema1(path)
    to_sqlite(_aligned_corpus("new"), path, append=True, fts=False)

    loaded = from_sqlite(path)
    assert [document.id for document in loaded.documents] == ["legacy", "new"]
    assert loaded.documents[0].tokens[0].alignment is None
    assert loaded.documents[1].tokens[0].alignment is not None
    with sqlite3.connect(path) as conn:
        assert "source_text" in {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
        assert "alignment" in {row[1] for row in conn.execute("PRAGMA table_info(tokens)")}
        assert "form_state_json" in {
            row[1] for row in conn.execute("PRAGMA table_info(tokens)")
        }
        assert conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()[0] == "3"


def test_malformed_alignment_is_a_clean_value_error(tmp_path: Path) -> None:
    path = tmp_path / "aligned.db"
    to_sqlite(_aligned_corpus(), path, fts=False)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE tokens SET alignment = ?", (json.dumps({"document_id": "d1"}),))
        conn.commit()

    with pytest.raises(ValueError, match="malformed token alignment"):
        from_sqlite(path)
