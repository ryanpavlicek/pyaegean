"""Regression tests for the compatibility / floors / performance fix pass.

Each pins the corrected OUTPUT or a property invariant of one fixed defect.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

from aegean import Corpus
from aegean.core.model import Document, Token, TokenKind


def _corpus(words: list[str]) -> Corpus:
    return Corpus(
        [Document(id=f"d{i}", script_id="greek",
                  tokens=[Token(w, TokenKind.WORD, position=0)], lines=[[0]])
         for i, w in enumerate(words)],
        script_id="greek",
    )


# ── the doctor report builds without the CLI dependency (the [tui]-only seam) ──


def test_doctor_report_builds_without_typer(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """aegean._doctor is the typer-free seam both the CLI and the TUI render; it must
    build the full report even when typer cannot be imported (a [tui]-only install)."""
    import importlib

    import aegean._doctor as doc

    monkeypatch.setitem(sys.modules, "typer", None)  # any `import typer` now fails
    importlib.reload(doc)  # prove the module itself imports without typer
    report = doc.build_report()
    assert set(report) >= {"ok", "issues", "versions", "extras", "data_store"}
    monkeypatch.undo()
    importlib.reload(doc)


def test_tui_doctor_report_uses_the_typer_free_seam() -> None:
    import inspect

    from aegean.tui import data as tui_data

    src = inspect.getsource(tui_data.doctor_report)
    assert "cli._doctor" not in src  # the adapter no longer routes through the CLI module


# ── run_query builds the co-occurrence map only when a filter needs it ──


def test_run_query_skips_the_cooccurrence_map_when_unneeded(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from aegean.analysis import query as q

    def boom(documents):  # type: ignore[no-untyped-def]
        raise AssertionError("co-occurrence map built for a query that does not use it")

    monkeypatch.setattr(q, "build_cooccurrence_map", boom)
    c = _corpus(["λόγος", "καί"])
    res = q.run_query(c, [q.FilterRow(field="word-prefix", value="λόγ")], output="words")
    assert [w for w, _ in res.words] == ["λόγος"]


def test_run_query_cooccurrence_filter_still_works() -> None:
    from aegean.analysis import query as q

    doc = Document(id="d", script_id="lineara",
                   tokens=[Token("KU-RO", TokenKind.WORD, signs=("KU", "RO"), position=0),
                           Token("KI-RO", TokenKind.WORD, signs=("KI", "RO"), position=1)],
                   lines=[[0, 1]])
    c = Corpus([doc], script_id="lineara")
    res = q.run_query(
        c, [q.FilterRow(field="word-cooccurs-with", value="KI-RO")], output="words"
    )
    assert any(w == "KU-RO" for w, _ in res.words)


# ── the bulk dispersions ranking equals the single-item reference values ──


def test_bulk_dispersions_match_the_single_item_reference() -> None:
    from aegean.analysis import stats

    docs = [
        Document(id="a", script_id="greek",
                 tokens=[Token(w, TokenKind.WORD, position=i)
                         for i, w in enumerate(["x", "x", "y"])], lines=[[0, 1, 2]]),
        Document(id="b", script_id="greek",
                 tokens=[Token(w, TokenKind.WORD, position=i)
                         for i, w in enumerate(["x", "z", "z", "z"])], lines=[[0, 1, 2, 3]]),
    ]
    c = Corpus(docs, script_id="greek")
    for row in stats.dispersions(c, kind="words", min_frequency=1):
        ref = stats.dispersion(c, row.item, kind="words")
        assert row.dp == pytest.approx(ref.dp)
        assert row.dp_norm == pytest.approx(ref.dp_norm)
        assert (row.frequency, row.range, row.parts) == (ref.frequency, ref.range, ref.parts)


# ── schema-version gate: a future-schema artifact is refused with the fix named ──


def test_from_dict_refuses_a_newer_schema_version() -> None:
    c = _corpus(["λόγος"])
    data = json.loads(c.to_json())
    data["_meta"]["schemaVersion"] = 99
    with pytest.raises(ValueError, match="schema version 99.*upgrade pyaegean"):
        Corpus.from_dict(data)
    # a missing version (a legacy file) still loads
    del data["_meta"]["schemaVersion"]
    assert len(Corpus.from_dict(data)) == 1


def test_from_sqlite_refuses_a_newer_schema_version() -> None:
    import sqlite3

    from aegean import db

    p = Path(tempfile.mkdtemp()) / "c.db"
    db.to_sqlite(_corpus(["λόγος"]), p)
    conn = sqlite3.connect(p)
    conn.execute("UPDATE meta SET value = '99' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="schema version 99.*upgrade pyaegean"):
        db.from_sqlite(p)
    with pytest.raises(ValueError, match="schema version 99"):
        list(db.stream(p))


# ── aegean-mcp names the actual fix when mcp is installed but too old ──


def test_mcp_main_distinguishes_old_sdk_from_missing_extra(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    from aegean import mcp_server

    def boom() -> None:
        raise ModuleNotFoundError("No module named 'mcp.server.fastmcp'")

    monkeypatch.setattr(mcp_server, "build_server", boom)
    # mcp IS importable in this env, so the message must say "upgrade", not "install the extra"
    with pytest.raises(SystemExit):
        mcp_server.main()
    err = capsys.readouterr().err
    assert "mcp>=1.2" in err and "[mcp] extra" not in err
