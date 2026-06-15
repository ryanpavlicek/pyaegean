"""DB append: aegean.db.to_sqlite(append=True) / Corpus.to_sql(append=True) / `aegean db add`."""

from __future__ import annotations

import sqlite3

import pytest

import aegean
from aegean.core.corpus import Corpus
from aegean.db import from_sqlite, search, stream


def _records(items):
    return Corpus.from_records([{"id": i, "text": t} for i, t in items], script_id="lineara")


def test_append_adds_and_round_trips(tmp_path) -> None:
    p = tmp_path / "c.db"
    _records([("X1", "AA BB"), ("X2", "CC")]).to_sql(p)
    _records([("X3", "FF GG")]).to_sql(p, append=True)
    back = from_sqlite(p)
    assert [d.id for d in back] == ["X1", "X2", "X3"]
    assert [d.id for d in stream(p)] == ["X1", "X2", "X3"]  # order stable


def test_append_upserts_by_id_without_duplicate_tokens(tmp_path) -> None:
    p = tmp_path / "c.db"
    _records([("X1", "AA BB"), ("X2", "CC")]).to_sql(p)
    _records([("X2", "DD EE"), ("X3", "FF")]).to_sql(p, append=True)
    back = from_sqlite(p)
    assert [d.id for d in back] == ["X1", "X2", "X3"]  # X2 replaced in place, X3 appended
    assert [t.text for t in back.get("X2").tokens] == ["DD", "EE"]  # new tokens
    conn = sqlite3.connect(str(p))
    n = conn.execute("SELECT COUNT(*) FROM tokens WHERE doc_id='X2'").fetchone()[0]
    conn.close()
    assert n == 2  # no orphaned/duplicate rows from the old X2


def test_append_search_finds_old_and_new(tmp_path) -> None:
    p = tmp_path / "c.db"
    _records([("X1", "AA BB")]).to_sql(p)
    _records([("X2", "DD EE")]).to_sql(p, append=True)
    assert any(h[0] == "X1" for h in search(p, "AA"))
    assert any(h[0] == "X2" for h in search(p, "DD"))


def test_append_missing_db_errors(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        _records([("X1", "AA")]).to_sql(tmp_path / "ghost.db", append=True)


def test_append_mixed_script_marks_meta(tmp_path) -> None:
    p = tmp_path / "c.db"
    _records([("X1", "AA")]).to_sql(p)
    Corpus.from_records([{"id": "G1", "text": "λόγος"}], script_id="greek").to_sql(p, append=True)
    assert from_sqlite(p).script_id == "mixed"


def test_cli_db_add(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    a, b = tmp_path / "a.json", tmp_path / "b.json"
    db = tmp_path / "c.db"
    _records([("X1", "AA")]).to_json(a)
    _records([("X2", "BB")]).to_json(b)
    app = _build_app()
    assert CliRunner().invoke(app, ["db", "build", str(a), "-o", str(db)]).exit_code == 0
    r = CliRunner().invoke(app, ["db", "add", str(b), "-o", str(db)])
    assert r.exit_code == 0, r.output
    assert len(from_sqlite(db)) == 2
    # appending to a non-existent db is a clean error
    assert CliRunner().invoke(app, ["db", "add", str(b), "-o", str(tmp_path / "no.db")]).exit_code == 1


def test_aegean_db_exports_unchanged() -> None:
    assert set(aegean.db.__all__) >= {"to_sqlite", "from_sqlite", "search", "stream"}
