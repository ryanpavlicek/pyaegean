"""Exact lexical indexes preserve scan results and transactional source snapshots."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import threading
import unicodedata
from pathlib import Path

import pytest

from aegean import db
from aegean.core.corpus import Corpus
from aegean.core.model import (
    Document, FormSegment, ReadingStatus, Token, TokenFormState, TokenKind,
)


def _corpus(doc_id: str = "first", text: str = "λόγου", lemma: str = "λόγος") -> Corpus:
    return Corpus([Document(doc_id, "greek", tokens=[
        Token(text, TokenKind.WORD, position=None, annotations={"lemma": lemma}),
    ], lines=[[0]])], script_id="greek")


def _forms() -> Corpus:
    words = [
        Token("ΛΌΓΟΣ", TokenKind.WORD, position=19, annotations={"lemma": "Λόγος"}),
        Token("λόγος", TokenKind.WORD, position=None, annotations={"lemma": "λόγος"}),
        Token(unicodedata.normalize("NFD", "λόγος"), TokenKind.WORD, position=3,
              annotations={"lemma": unicodedata.normalize("NFD", "λόγος")}),
        Token("λόγου", TokenKind.WORD, position=0, annotations={"lemma": "λόγος"}),
        Token("λογος", TokenKind.WORD, position=0, annotations={"lemma": "λογος"}),
        Token("Σ", TokenKind.WORD, annotations={"lemma": "Σ"}),
        Token("ς", TokenKind.WORD, annotations={"lemma": "ς"}),
        Token("σ", TokenKind.WORD, annotations={"lemma": "σ"}),
        Token("ἐκκλησίᾳ", TokenKind.WORD, annotations={"lemma": "ἐκκλησίᾳ"}),
        Token("ἐκκλησίαι", TokenKind.WORD, annotations={"lemma": "ἐκκλησίαι"}),
        Token("without", TokenKind.WORD),
        Token("blank", TokenKind.WORD, annotations={"lemma": " \t"}),
        Token("spaced", TokenKind.WORD, annotations={"lemma": " λόγος "}),
        Token("unclear", TokenKind.WORD, status=ReadingStatus.UNCLEAR,
              annotations={"lemma": "λόγος"}),
        Token("restored", TokenKind.WORD, status=ReadingStatus.RESTORED,
              annotations={"lemma": "λόγος"}),
        Token("segments", TokenKind.WORD, annotations={"lemma": "λόγος"},
              form_state=TokenFormState("segments", segments=(
                  FormSegment("s"), FormSegment("e", ReadingStatus.RESTORED),
                  FormSegment("", ReadingStatus.LOST),
              ))),
        Token("unclear-segment", TokenKind.WORD, annotations={"lemma": "λόγος"},
              form_state=TokenFormState("different diplomatic text", normalized="λόγος", segments=(
                  FormSegment("?", ReadingStatus.UNCLEAR),
              ))),
        Token("7", TokenKind.NUMERAL, annotations={"lemma": "λόγος"}),
        Token("·", TokenKind.PUNCT, annotations={"lemma": "λόγος"}),
        Token("λόγος", TokenKind.LOGOGRAM, annotations={"lemma": "λόγος"}),
        Token("a\x00b", TokenKind.WORD, annotations={"lemma": "a\x00b"}),
        Token("", TokenKind.WORD, annotations={"lemma": ""}),
        Token("lost", TokenKind.WORD, status=ReadingStatus.LOST),
    ]
    return Corpus([
        Document("first", "greek", tokens=words, lines=[]),
        Document("duplicate-edition", "greek", tokens=[
            Token("λόγος", TokenKind.WORD, position=100, annotations={"lemma": "λόγος"}),
            Token("λόγου", TokenKind.WORD, position=-2, annotations={"lemma": "λόγος"}),
        ], lines=[]),
    ], script_id="greek")


def _index_rows(path: Path) -> tuple[dict[str, str], list[tuple], list[tuple]]:
    with sqlite3.connect(path) as connection:
        objects = db._lexical_objects(connection)
        if not objects:
            return objects, [], []
        return (objects,
                connection.execute("SELECT * FROM token_lexical_keys ORDER BY source_order").fetchall(),
                connection.execute("SELECT * FROM lexical_index_state").fetchall())


@pytest.mark.parametrize("fts", [False, True])
def test_indexed_exact_results_equal_reference_scan_for_all_views(tmp_path: Path, fts: bool) -> None:
    path = tmp_path / "forms.sqlite"
    corpus = _forms()
    db.to_sqlite(corpus, path, fts=fts)
    queries = [
        "λόγος", "ΛΌΓΟΣ", unicodedata.normalize("NFD", "λόγος"), "λόγου", "λογος",
        "Σ", "ς", "σ", "ἐκκλησίᾳ", "ἐκκλησίαι", "without", "blank", " λόγος ",
        "segments", "·", "7", "a\x00b", "", "absent",
    ]
    selections = [None, [], ["certain"], ["certain", "restored"],
                  ["certain", "restored", "lost"], list(ReadingStatus)]
    cases = [(view, query, selection, limit)
             for view in ("surface", "normalized", "lemma", None)
             for query in queries for selection in selections for limit in (0, -3, 1, 3)]
    # view=None without statuses deliberately remains the separate legacy path.
    expected = [db.search(path, query, view=view, statuses=selection, limit=limit)
                for view, query, selection, limit in cases]
    progress: list[tuple[int, int]] = []
    report = db.build_lexical_index(path, progress=lambda done, total: progress.append((done, total)))
    assert report["state"] == "ready"
    assert report["source_generation"] == report["indexed_generation"] == 0
    assert report["indexed_tokens"] == 25
    assert progress == [(n, 25) for n in range(1, 26)]
    for case, reference in zip(cases, expected):
        view, query, selection, limit = case
        assert db.search(path, query, view=view, statuses=selection, limit=limit) == reference, case
    assert db.from_sqlite(path).documents == corpus.documents


def test_hand_counted_keys_keep_original_forms_positions_and_status_scope(tmp_path: Path) -> None:
    path = tmp_path / "forms.db"
    db.to_sqlite(_forms(), path)
    db.build_lexical_index(path)
    assert db.search(path, "λόγος", view="surface", limit=0) == [
        ("first", None, "λόγος"), ("duplicate-edition", 100, "λόγος"),
    ]
    assert db.search(path, "ΛΌΓΟΣ", view="normalized", limit=0) == [
        ("first", 19, "ΛΌΓΟΣ"), ("first", None, "λόγος"),
        ("first", 3, unicodedata.normalize("NFD", "λόγος")),
        ("duplicate-edition", 100, "λόγος"),
    ]
    certain_lemmas = db.search(path, "λόγος", view="lemma", statuses=["certain"], limit=0)
    assert certain_lemmas == [
        ("first", 19, "ΛΌΓΟΣ"), ("first", None, "λόγος"),
        ("first", 3, unicodedata.normalize("NFD", "λόγος")), ("first", 0, "λόγου"),
        ("duplicate-edition", 100, "λόγος"), ("duplicate-edition", -2, "λόγου"),
    ]
    assert "segments" not in [t for _, _, t in db.search(
        path, "λόγος", view="lemma", statuses=["certain", "restored"], limit=0,
    )]
    assert "segments" in [t for _, _, t in db.search(
        path, "λόγος", view="lemma", statuses=["certain", "restored", "lost"], limit=0,
    )]
    assert db.search(path, "·", statuses=["certain"]) == [("first", None, "·")]
    assert db.search(path, "·", view="surface") == []
    assert db.search(path, "λόγος", view="lemma", statuses=[]) == []
    assert db.search(path, "ἐκκλησίᾳ", view="normalized") == [("first", None, "ἐκκλησίᾳ")]
    assert db.search(path, "σ", view="normalized") == [
        ("first", None, "Σ"), ("first", None, "ς"), ("first", None, "σ"),
    ]
    assert db.search(path, "λόγος", view="lemma", limit=1) == certain_lemmas[:1]


@pytest.mark.parametrize("view", ["surface", "normalized", "lemma", None])
def test_exact_plan_uses_key_index_and_never_reads_source_rows(
    tmp_path: Path, monkeypatch, view: str | None,
) -> None:
    path = tmp_path / "index.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    with sqlite3.connect(path) as connection:
        plan = connection.execute(
            "EXPLAIN QUERY PLAN " + db._lexical_search_sql(view), ("λόγοσ", 15, -1),
        ).fetchall()
    details = " ".join(str(row[-1]) for row in plan)
    assert "INDEX idx_lexical_" + (view or "legacy") in details
    assert "tokens" not in details
    assert "SCAN" not in details
    statements: list[str] = []
    connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        connection = connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(db.sqlite3, "connect", traced_connect)
    monkeypatch.setattr(db, "_lexical_token", lambda *args: pytest.fail("indexed search decoded a row"))
    query = "λόγου" if view in ("surface", "normalized", None) else "λόγος"
    assert db.search(path, query, view=view, statuses=["certain"]) == [("first", None, "λόγου")]
    assert any("FROM token_lexical_keys" in sql for sql in statements)
    assert not any("FROM tokens ORDER" in sql or "COUNT(*) FROM tokens" in sql for sql in statements)


@pytest.mark.parametrize("view", ["surface", "normalized", "lemma", None])
def test_substring_still_uses_scan_after_build(tmp_path: Path, monkeypatch, view: str | None) -> None:
    path = tmp_path / "substring.db"
    db.to_sqlite(_forms(), path)
    expected = db.search(path, "λόγ", view=view, statuses=["certain"], mode="substring", limit=0)
    db.build_lexical_index(path)
    monkeypatch.setattr(db, "_lexical_search_sql", lambda *args: pytest.fail("substring used exact index"))
    assert db.search(path, "λόγ", view=view, statuses=["certain"], mode="substring", limit=0) == expected


@pytest.mark.parametrize("empty_status", [None, ""])
def test_missing_legacy_annotation_and_status_values_keep_scan_rules(tmp_path: Path, empty_status) -> None:
    path = tmp_path / "missing.db"
    db.to_sqlite(_corpus(), path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE tokens SET status = ?, annotations = NULL", (empty_status,))
    db.build_lexical_index(path)
    assert db.search(path, "λόγος", view="lemma") == []
    assert db.search(path, "λόγου", view="surface", statuses=["certain"]) == [("first", None, "λόγου")]


def test_hosted_shape_without_optional_source_columns_can_be_indexed(tmp_path: Path) -> None:
    path = tmp_path / "hosted-shape.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO meta VALUES ('schema_version', '1');
            CREATE TABLE tokens (doc_id TEXT, position INTEGER, text TEXT, kind TEXT,
                                 status TEXT, annotations TEXT);
            INSERT INTO tokens VALUES ('old', NULL, 'ΛΌΓΟΣ', 'word', NULL, '{"lemma":"λόγος"}');
        """)
        source_columns = connection.execute("PRAGMA table_info(tokens)").fetchall()
    assert db.lexical_index_status(path)["state"] == "absent"
    assert db.search(path, "λόγος", view="lemma") == [("old", None, "ΛΌΓΟΣ")]
    assert db.build_lexical_index(path)["state"] == "ready"
    assert db.search(path, "λόγος", view="lemma") == [("old", None, "ΛΌΓΟΣ")]
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA table_info(tokens)").fetchall() == source_columns


def test_append_replacement_and_rowid_reuse_invalidate_atomically(tmp_path: Path) -> None:
    path = tmp_path / "append.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    db.to_sqlite(_corpus("first", "νέα", "νέος"), path, append=True)
    assert db.lexical_index_status(path)["state"] == "stale"
    assert db.search(path, "λόγος", view="lemma") == []
    assert db.search(path, "νέος", view="lemma") == [("first", None, "νέα")]
    db.build_lexical_index(path)
    assert db.search(path, "νέος", view="lemma") == [("first", None, "νέα")]
    db.to_sqlite(_corpus("second", "νέος", "νέος"), path, append=True)
    assert db.lexical_index_status(path)["state"] == "stale"
    reference = db.search(path, "νέος", view="lemma", limit=0)
    assert reference == [("first", None, "νέα"), ("second", None, "νέος")]
    db.build_lexical_index(path)
    db.to_sqlite(_corpus("first", "τελευταία", "νέος"), path, append=True)
    reference = db.search(path, "νέος", view="lemma", limit=0)
    assert reference == [("second", None, "νέος"), ("first", None, "τελευταία")]
    db.build_lexical_index(path)
    assert db.search(path, "νέος", view="lemma", limit=0) == reference
    assert db.search(path, "νέος", view="lemma", limit=1) == reference[:1]


@pytest.mark.parametrize("drop_before_build", [False, True])
def test_vacuum_renumbering_hidden_source_rowids_cannot_change_hits_or_order(
    tmp_path: Path, drop_before_build: bool,
) -> None:
    path = tmp_path / "vacuum.db"
    corpus = Corpus([Document("sparse", "greek", tokens=[
        Token("removed", TokenKind.WORD),
        Token("β", TokenKind.WORD, position=None, annotations={"lemma": "κοινός"}),
        Token("γ", TokenKind.WORD, position=0, annotations={"lemma": "κοινός"}),
        Token("δ", TokenKind.WORD, position=0, annotations={"lemma": "κοινός"}),
    ], lines=[])])
    db.to_sqlite(corpus, path, fts=False)
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM tokens WHERE rowid = 1")
        if drop_before_build:
            connection.execute("DROP INDEX idx_tokens_doc")
            connection.execute("DROP INDEX idx_tokens_text")
    db.build_lexical_index(path)
    expected = [("sparse", None, "β"), ("sparse", 0, "γ"), ("sparse", 0, "δ")]
    assert db.search(path, "κοινός", view="lemma", limit=0) == expected
    with sqlite3.connect(path) as connection:
        if not drop_before_build:
            connection.execute("DROP INDEX idx_tokens_doc")
            connection.execute("DROP INDEX idx_tokens_text")
        before = connection.execute("SELECT rowid FROM tokens ORDER BY rowid").fetchall()
        connection.execute("VACUUM")
        after = connection.execute("SELECT rowid FROM tokens ORDER BY rowid").fetchall()
    assert before == [(2,), (3,), (4,)] and after == [(1,), (2,), (3,)]
    assert db.lexical_index_status(path)["state"] == "ready"
    assert db.search(path, "β", view="surface", limit=0) == expected[:1]
    assert db.search(path, "κοινός", view="lemma", limit=0) == expected
    assert db.search(path, "κοινός", view="lemma", limit=1) == expected[:1]
    # A rebuild records the compacted row order and still returns identical hits.
    db.build_lexical_index(path)
    assert db.search(path, "κοινός", view="lemma", limit=0) == expected


def test_refresh_preserves_live_schema_and_source_rows(tmp_path: Path) -> None:
    path = tmp_path / "stable-schema.db"
    db.to_sqlite(_forms(), path)
    db.build_lexical_index(path)
    with sqlite3.connect(path) as connection:
        cookie = connection.execute("PRAGMA schema_version").fetchone()[0]
        schema = connection.execute("SELECT name, type, sql FROM sqlite_master ORDER BY name").fetchall()
        source = connection.execute("SELECT rowid, * FROM tokens ORDER BY rowid").fetchall()
    before = _index_rows(path)
    assert db.build_lexical_index(path)["state"] == "ready"
    assert _index_rows(path) == before
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA schema_version").fetchone()[0] == cookie
        assert connection.execute("SELECT name, type, sql FROM sqlite_master ORDER BY name").fetchall() == schema
        assert connection.execute("SELECT rowid, * FROM tokens ORDER BY rowid").fetchall() == source


@pytest.mark.parametrize("change", [
    "UPDATE tokens SET annotations = '{\"lemma\":\"νέος\"}'",
    "UPDATE tokens SET text = 'νέος'",
    "UPDATE tokens SET status = 'restored'",
    "UPDATE tokens SET kind = 'punct'",
    "UPDATE tokens SET rowid = 20, position = 20, doc_id = 'external'",
    "UPDATE tokens SET form_state_json = ?",
    "DELETE FROM tokens",
    "INSERT INTO tokens(doc_id, text, kind, status, annotations) "
    "VALUES ('external', 'νέος', 'word', 'certain', '{\"lemma\":\"νέος\"}')",
], ids=["lemma", "form", "status", "kind", "rowid-and-location", "segments", "delete", "insert"])
def test_external_writers_invalidate_every_token_mutation(tmp_path: Path, change: str) -> None:
    path = tmp_path / "external.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    form = TokenFormState("λόγου", segments=(FormSegment("λόγου", ReadingStatus.RESTORED),))
    with sqlite3.connect(path) as connection:
        connection.execute(change, (json.dumps(form.to_dict()),) if "?" in change else ())
    status = db.lexical_index_status(path)
    assert status["state"] == "stale"
    assert status["source_generation"] == 1 and status["indexed_generation"] == 0
    reference = [db.search(path, q, view=v, statuses=["certain"], limit=0)
                 for q, v in (("λόγος", "lemma"), ("νέος", "lemma"), ("λόγου", "surface"))]
    db.build_lexical_index(path)
    assert [db.search(path, q, view=v, statuses=["certain"], limit=0)
            for q, v in (("λόγος", "lemma"), ("νέος", "lemma"), ("λόγου", "surface"))] == reference


@pytest.mark.parametrize("change", [
    "DELETE FROM token_lexical_keys",
    "UPDATE token_lexical_keys SET lemma_key = 'incorrect'",
    "INSERT INTO token_lexical_keys VALUES (999, 'external', NULL, 'x', 'x', 'x', 'x', 'x', 1)",
])
def test_external_derived_key_changes_fail_safely_to_scan(tmp_path: Path, change: str) -> None:
    path = tmp_path / "derived.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    with sqlite3.connect(path) as connection:
        connection.execute(change)
    assert db.lexical_index_status(path)["state"] == "stale"
    assert db.search(path, "λόγος", view="lemma") == [("first", None, "λόγου")]
    assert db.build_lexical_index(path)["state"] == "ready"
    assert db.search(path, "λόγος", view="lemma") == [("first", None, "λόγου")]


@pytest.mark.parametrize("missing", ["lexical_source_update", "idx_lexical_lemma"])
def test_missing_trigger_or_index_forces_scan_and_explicit_refresh_repairs(
    tmp_path: Path, missing: str,
) -> None:
    path = tmp_path / "missing-structure.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    with sqlite3.connect(path) as connection:
        object_type = "TRIGGER" if missing.startswith("lexical_source") else "INDEX"
        connection.execute(f"DROP {object_type} {missing}")
        connection.execute("UPDATE tokens SET annotations = '{\"lemma\":\"νέος\"}'")
    assert db.lexical_index_status(path)["state"] == "stale"
    assert db.search(path, "λόγος", view="lemma") == []
    assert db.search(path, "νέος", view="lemma") == [("first", None, "λόγου")]
    assert db.build_lexical_index(path)["state"] == "ready"
    assert db.search(path, "νέος", view="lemma") == [("first", None, "λόγου")]


def test_unexpected_trigger_definition_refuses_refresh_and_falls_back(tmp_path: Path) -> None:
    path = tmp_path / "unknown.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TRIGGER lexical_source_update")
        connection.execute("CREATE TRIGGER lexical_source_update AFTER UPDATE ON tokens BEGIN SELECT 1; END")
        connection.execute("UPDATE tokens SET annotations = '{\"lemma\":\"νέος\"}'")
    before = _index_rows(path)
    assert db.lexical_index_status(path)["state"] == "unsupported"
    assert db.search(path, "νέος", view="lemma") == [("first", None, "λόγου")]
    with pytest.raises(ValueError, match="unsupported lexical index schema"):
        db.build_lexical_index(path)
    assert _index_rows(path) == before


def test_changed_semantics_and_unicode_version_require_explicit_refresh(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "semantics.db"
    db.to_sqlite(_corpus(), path)
    report = db.build_lexical_index(path)
    assert unicodedata.unidata_version in report["semantics_version"]
    with monkeypatch.context() as patch:
        patch.setattr(db, "_lexical_semantics_version", lambda: "lexical-2;unicode=future")
        assert db.lexical_index_status(path)["state"] == "stale"
        assert db.search(path, "λόγος", view="lemma") == [("first", None, "λόγου")]
        assert db.build_lexical_index(path)["semantics_version"] == "lexical-2;unicode=future"
        assert db.lexical_index_status(path)["state"] == "ready"
    assert db.lexical_index_status(path)["state"] == "stale"


@pytest.mark.parametrize("bad", ["{", "[]", "null", "[" * 2000],
                         ids=["invalid", "array", "null", "deep"])
def test_malformed_annotation_refresh_rolls_back_and_search_rejects_stale_keys(
    tmp_path: Path, bad: str,
) -> None:
    path = tmp_path / "bad.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE tokens SET annotations = ?", (bad,))
    before = _index_rows(path)
    with pytest.raises(ValueError, match="malformed token annotations"):
        db.build_lexical_index(path)
    assert _index_rows(path) == before
    with pytest.raises(ValueError, match="malformed token annotations"):
        db.search(path, "λόγος", view="lemma")


@pytest.mark.parametrize("bad", ["{", "[]", '{"segments":[]}', "[" * 2000],
                         ids=["invalid", "array", "partial", "deep"])
def test_malformed_segment_state_cannot_publish_partial_index(tmp_path: Path, bad: str) -> None:
    path = tmp_path / "bad-state.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE tokens SET form_state_json = ?", (bad,))
    before = _index_rows(path)
    with pytest.raises(ValueError, match="malformed token form_state"):
        db.build_lexical_index(path)
    assert _index_rows(path) == before
    with pytest.raises(ValueError, match="malformed token form_state"):
        db.search(path, "λόγος", view="lemma")


@pytest.mark.parametrize("initial_index", [False, True])
def test_callback_interruption_rolls_back_schema_keys_and_markers(tmp_path: Path, initial_index: bool) -> None:
    path = tmp_path / "interrupted.db"
    db.to_sqlite(_forms(), path)
    if initial_index:
        db.build_lexical_index(path)
    before = _index_rows(path)

    def interrupt(done: int, total: int) -> None:
        if done == 4:
            raise KeyboardInterrupt("cancelled after some keys were inserted")

    with pytest.raises(KeyboardInterrupt, match="cancelled"):
        db.build_lexical_index(path, progress=interrupt)
    assert _index_rows(path) == before
    assert db.lexical_index_status(path)["state"] == ("ready" if initial_index else "absent")
    assert len(db.search(path, "ΛΌΓΟΣ", view="normalized", limit=0)) == 4


@pytest.mark.parametrize("initial_index", [False, True])
def test_process_death_during_spilled_wal_build_keeps_last_committed_generation(
    tmp_path: Path, initial_index: bool,
) -> None:
    path = tmp_path / "killed.db"
    corpus = Corpus([Document("large", "greek", tokens=[
        Token("x" * 9000 + str(i), TokenKind.WORD, annotations={"lemma": "λόγος"})
        for i in range(120)
    ], lines=[])])
    db.to_sqlite(corpus, path, fts=False)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    if initial_index:
        db.build_lexical_index(path)
    before = _index_rows(path)
    probe = """
import os, sqlite3, sys
from aegean import db
connect = sqlite3.connect
def small_cache(*args, **kwargs):
    connection = connect(*args, **kwargs)
    connection.execute('PRAGMA cache_size=5')
    return connection
db.sqlite3.connect = small_cache
def stop(done, total):
    if done == 80:
        os._exit(47)
db.build_lexical_index(sys.argv[1], progress=stop)
"""
    result = subprocess.run([sys.executable, "-c", probe, str(path)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 47, result.stderr
    assert _index_rows(path) == before
    assert db.lexical_index_status(path)["state"] == ("ready" if initial_index else "absent")
    assert len(db.search(path, "λόγος", view="lemma", limit=0)) == 120
    assert db.build_lexical_index(path)["state"] == "ready"


def test_append_callback_rollback_preserves_ready_index(tmp_path: Path) -> None:
    path = tmp_path / "rollback.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    before = _index_rows(path)

    def stop(done: int, total: int) -> None:
        raise RuntimeError("cancelled append")

    with pytest.raises(RuntimeError, match="cancelled append"):
        db.to_sqlite(_corpus("first", "νέος", "νέος"), path, append=True, progress=stop)
    assert _index_rows(path) == before
    assert db.lexical_index_status(path)["state"] == "ready"
    assert db.search(path, "λόγος", view="lemma") == [("first", None, "λόγου")]


def test_wal_reader_keeps_index_and_source_snapshot_across_refresh(tmp_path: Path) -> None:
    path = tmp_path / "wal.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    reader = sqlite3.connect(path)
    try:
        assert reader.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        reader.execute("BEGIN")
        assert db._lexical_index_status(reader)["state"] == "ready"
        db.to_sqlite(_corpus("first", "νέα", "νέος"), path, append=True)
        db.build_lexical_index(path)
        assert reader.execute(db._lexical_search_sql("lemma"), ("λόγοσ", 15, -1)).fetchall() == [
            ("first", None, "λόγου"),
        ]
        assert db._lexical_index_status(reader)["state"] == "ready"
        assert db.search(path, "λόγος", view="lemma") == []
        assert db.search(path, "νέος", view="lemma") == [("first", None, "νέα")]
        reader.rollback()
        assert reader.execute(db._lexical_search_sql("lemma"), ("νέοσ", 15, -1)).fetchall() == [
            ("first", None, "νέα"),
        ]
    finally:
        reader.close()


def test_search_validity_check_and_hits_use_one_read_transaction(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "search-snapshot.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    inspect = db._lexical_index_status
    changed = False

    def write_after_validity_check(connection):
        nonlocal changed
        result = inspect(connection)
        if not changed:
            changed = True
            with sqlite3.connect(path) as writer:
                writer.execute("UPDATE tokens SET annotations = '{\"lemma\":\"νέος\"}'")
        return result

    monkeypatch.setattr(db, "_lexical_index_status", write_after_validity_check)
    assert db.search(path, "λόγος", view="lemma") == [("first", None, "λόγου")]
    assert db.search(path, "λόγος", view="lemma") == []
    assert db.search(path, "νέος", view="lemma") == [("first", None, "λόγου")]


def test_uncommitted_wal_token_edits_and_rollback_do_not_invalidate_other_readers(tmp_path: Path) -> None:
    path = tmp_path / "uncommitted.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    writer = sqlite3.connect(path)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("UPDATE tokens SET annotations = '{\"lemma\":\"νέος\"}'")
        assert db._lexical_index_status(writer)["state"] == "stale"
        assert db.lexical_index_status(path)["state"] == "ready"
        assert db.search(path, "λόγος", view="lemma") == [("first", None, "λόγου")]
        writer.rollback()
        assert db.lexical_index_status(path)["state"] == "ready"
        writer.execute("UPDATE tokens SET annotations = '{\"lemma\":\"νέος\"}'")
        writer.commit()
        assert db.lexical_index_status(path)["state"] == "stale"
        assert db.search(path, "νέος", view="lemma") == [("first", None, "λόγου")]
    finally:
        writer.close()


def test_full_replacement_leaves_new_database_unindexed_and_old_wal_snapshot_ready(tmp_path: Path) -> None:
    path = tmp_path / "replacement.db"
    db.to_sqlite(_corpus(), path)
    db.build_lexical_index(path)
    reader = sqlite3.connect(path)
    try:
        reader.execute("PRAGMA journal_mode=WAL")
        reader.execute("BEGIN")
        assert db._lexical_index_status(reader)["state"] == "ready"
        db.to_sqlite(_corpus("new", "νέα", "νέος"), path)
        assert db.lexical_index_status(path)["state"] == "absent"
        assert db.search(path, "νέος", view="lemma") == [("new", None, "νέα")]
        assert db.search(path, "λόγος", view="lemma") == []
        assert reader.execute(db._lexical_search_sql("lemma"), ("λόγοσ", 15, -1)).fetchall() == [
            ("first", None, "λόγου"),
        ]
        assert db._lexical_index_status(reader)["state"] == "ready"
    finally:
        reader.close()


def test_two_competing_builders_serialize_and_publish_complete_indexes(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "competing.db"
    db.to_sqlite(_forms(), path)
    first_has_lock = threading.Event()
    second_attempted = threading.Event()
    release_first = threading.Event()
    reports: list[dict] = []
    errors: list[BaseException] = []
    connect = sqlite3.connect

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == "BEGIN IMMEDIATE" and threading.current_thread().name == "second-builder":
                second_attempted.set()
            return super().execute(sql, parameters)

    def observed_connect(*args, **kwargs):
        return connect(*args, **kwargs, factory=ObservedConnection)

    def hold(done: int, total: int) -> None:
        if done == 1:
            first_has_lock.set()
            assert release_first.wait(30)

    def build(progress=None) -> None:
        try:
            reports.append(db.build_lexical_index(path, progress=progress))
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(db.sqlite3, "connect", observed_connect)
    first = threading.Thread(target=build, args=(hold,), name="first-builder", daemon=True)
    second = threading.Thread(target=build, name="second-builder", daemon=True)
    first.start()
    try:
        assert first_has_lock.wait(30)
        second.start()
        assert second_attempted.wait(30)
    finally:
        release_first.set()
        first.join(30)
        if second.ident is not None:
            second.join(30)
    assert not first.is_alive() and not second.is_alive()
    assert not errors
    assert len(reports) == 2 and all(r["state"] == "ready" and r["indexed_tokens"] == 25 for r in reports)
    assert db.lexical_index_status(path)["state"] == "ready"
    assert len(db.search(path, "ΛΌΓΟΣ", view="normalized", limit=0)) == 4


def test_competing_token_writer_waits_for_build_then_invalidates_it(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "writer.db"
    db.to_sqlite(_corpus(), path)
    builder_has_lock = threading.Event()
    writer_attempted = threading.Event()
    release_builder = threading.Event()
    errors: list[BaseException] = []
    connect = sqlite3.connect

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == "BEGIN IMMEDIATE" and threading.current_thread().name == "token-writer":
                writer_attempted.set()
            return super().execute(sql, parameters)

    def observed_connect(*args, **kwargs):
        return connect(*args, **kwargs, factory=ObservedConnection)

    def hold(done: int, total: int) -> None:
        builder_has_lock.set()
        assert release_builder.wait(30)

    def build() -> None:
        try:
            db.build_lexical_index(path, progress=hold)
        except BaseException as exc:
            errors.append(exc)

    def write() -> None:
        try:
            with sqlite3.connect(path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("UPDATE tokens SET annotations = '{\"lemma\":\"νέος\"}'")
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(db.sqlite3, "connect", observed_connect)
    builder = threading.Thread(target=build, daemon=True)
    writer = threading.Thread(target=write, name="token-writer", daemon=True)
    builder.start()
    try:
        assert builder_has_lock.wait(30)
        writer.start()
        assert writer_attempted.wait(30)
    finally:
        release_builder.set()
        builder.join(30)
        if writer.ident is not None:
            writer.join(30)
    assert not builder.is_alive() and not writer.is_alive()
    assert not errors
    assert db.lexical_index_status(path)["state"] == "stale"
    assert db.search(path, "λόγος", view="lemma") == []
    assert db.search(path, "νέος", view="lemma") == [("first", None, "λόγου")]


@pytest.mark.parametrize("indexed", [False, True])
def test_search_and_status_never_write_even_with_read_only_authorizer(
    tmp_path: Path, monkeypatch, indexed: bool,
) -> None:
    path = tmp_path / "read-only.db"
    db.to_sqlite(_corpus(), path)
    if indexed:
        db.build_lexical_index(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    connect = sqlite3.connect
    attempts: list[int] = []
    modes: list[str] = []
    forbidden = {
        sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_CREATE_TRIGGER,
        sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_REINDEX,
    }

    def authorize(action, arg1, arg2, database, trigger):
        if action in forbidden:
            attempts.append(action)
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    def read_only_connect(*args, **kwargs):
        modes.append(str(args[0]))
        connection = connect(*args, **kwargs)
        connection.set_authorizer(authorize)
        return connection

    monkeypatch.setattr(db.sqlite3, "connect", read_only_connect)
    assert db.search(path, "λόγος", view="lemma") == [("first", None, "λόγου")]
    assert db.search(path, "absent", view="surface") == []
    assert db.search(path, "λόγ", view="normalized", mode="substring") == [("first", None, "λόγου")]
    assert db.lexical_index_status(path)["state"] == ("ready" if indexed else "absent")
    assert modes and all("mode=ro" in uri for uri in modes)
    assert attempts == []
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_missing_and_noncorpus_inputs_never_create_or_overwrite_files(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError, match="no database to index"):
        db.build_lexical_index(missing)
    with pytest.raises(ValueError, match="not a pyaegean corpus database"):
        db.lexical_index_status(missing)
    assert not missing.exists()
    text = tmp_path / "text.db"
    text.write_text("not sqlite", encoding="utf-8")
    with pytest.raises(ValueError, match="not a pyaegean corpus database"):
        db.build_lexical_index(text)
    assert text.read_text(encoding="utf-8") == "not sqlite"
    empty = tmp_path / "empty.db"
    with sqlite3.connect(empty) as connection:
        connection.execute("CREATE TABLE meta (key TEXT, value TEXT)")
    with pytest.raises(ValueError, match="not a pyaegean corpus database"):
        db.build_lexical_index(empty)
    with sqlite3.connect(empty) as connection:
        assert connection.execute("SELECT name FROM sqlite_master").fetchall() == [("meta",)]


def test_cli_build_status_search_edit_refresh_journey(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from aegean.cli import _build_app

    app = _build_app()
    path = tmp_path / "journey.db"
    db.to_sqlite(_corpus(), path)
    runner = CliRunner()
    result = runner.invoke(app, ["db", "index", str(path), "--status", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["state"] == "absent"
    assert db.lexical_index_status(path)["state"] == "absent"
    result = runner.invoke(app, ["db", "index", str(path), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["state"] == "ready"
    result = runner.invoke(app, ["db", "search", str(path), "λόγος", "--view", "lemma", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [{"doc_id": "first", "position": None, "text": "λόγου"}]
    db.to_sqlite(_corpus("first", "νέα", "νέος"), path, append=True)
    result = runner.invoke(app, ["db", "index", str(path), "--status", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["state"] == "stale"
    result = runner.invoke(app, ["db", "index", str(path), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["state"] == "ready"
    result = runner.invoke(app, ["db", "search", str(path), "νέος", "--view", "lemma", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [{"doc_id": "first", "position": None, "text": "νέα"}]
    assert db.from_sqlite(path).documents[0].tokens[0].annotations == {"lemma": "νέος"}


def test_cli_index_refuses_hosted_id_and_bad_files_without_fetching(tmp_path: Path, monkeypatch) -> None:
    from typer.testing import CliRunner
    from aegean.cli import _build_app
    from aegean.scripts import greek

    monkeypatch.chdir(tmp_path)
    app = _build_app()
    monkeypatch.setattr(greek, "ddbdp_db", lambda: pytest.fail("index fetched a hosted database"))
    runner = CliRunner()
    result = runner.invoke(app, ["db", "index", "ddbdp", "--json"])
    assert result.exit_code == 1 and "local file" in result.output
    assert not Path("ddbdp").exists()
    path = tmp_path / "bad.db"
    path.write_text("bad", encoding="utf-8")
    result = runner.invoke(app, ["db", "index", str(path), "--json"])
    assert result.exit_code == 1 and "not a pyaegean corpus database" in result.output
    assert path.read_text(encoding="utf-8") == "bad"
