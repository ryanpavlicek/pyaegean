"""CLI commands added for the 0.8.1 features: gloss-nt, export sqlite + --level,
analyze hands, db build/search, and corpus discoverability."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from aegean.cli import _build_app
from aegean.core.corpus import Corpus, _LOADERS, register_loader

runner = CliRunner()


def _run(*args: str) -> object:
    return runner.invoke(_build_app(), list(args))


def test_gloss_nt_word() -> None:
    r = _run("greek", "gloss-nt", "λόγος")
    assert r.exit_code == 0 and "word" in r.output.lower()


def test_gloss_nt_strongs() -> None:
    r = _run("greek", "gloss-nt", "3056", "--strongs")
    assert r.exit_code == 0 and "word" in r.output.lower()


def test_gloss_nt_unknown_exits_1() -> None:
    assert _run("greek", "gloss-nt", "zzznotgreek").exit_code == 1


def test_export_sqlite(tmp_path: Path) -> None:
    out = tmp_path / "c.db"
    r = _run("export", "lineara", "-f", "sqlite", "-o", str(out))
    assert r.exit_code == 0 and out.exists()
    assert len(Corpus.from_sql(out)) == 1721


def test_export_csv_word_level(tmp_path: Path) -> None:
    out = tmp_path / "c.csv"
    r = _run("export", "lineara", "-f", "csv", "--level", "word", "-o", str(out))
    assert r.exit_code == 0 and out.exists() and out.stat().st_size > 0


def test_db_build_and_search(tmp_path: Path) -> None:
    db = tmp_path / "la.db"
    assert _run("db", "build", "lineara", "-o", str(db)).exit_code == 0
    r = _run("db", "search", str(db), "KU-RO")
    assert r.exit_code == 0 and "KU-RO" in r.output


def test_analyze_hands_lineara() -> None:
    # the Linear A corpus carries scribe attributions, so this is a real, populated result
    r = _run("analyze", "hands", "lineara", "--top", "3")
    assert r.exit_code == 0 and "tablets" in r.output.lower()


def test_analyze_hands_no_scribes_exits_1() -> None:
    name = "test-noscribe-cli"
    register_loader(name, lambda: Corpus.from_records(
        [{"id": "x1", "text": "A-B C-D"}, {"id": "x2", "text": "E-F"}], script_id="lineara"))
    try:
        r = _run("analyze", "hands", name)
        assert r.exit_code == 1 and "no scribal hands" in r.output.lower()
    finally:
        _LOADERS.pop(name, None)


def test_analyze_hands_populated() -> None:
    name = "test-hands-cli"
    register_loader(name, lambda: Corpus.from_records(
        [
            {"id": "t1", "text": "DA-RE DA-RE", "meta": {"scribe": "117", "site": "KN"}},
            {"id": "t2", "text": "DA-RE KU-RO", "meta": {"scribe": "117"}},
            {"id": "t3", "text": "PO-TI A-DU", "meta": {"scribe": "103"}},
        ],
        script_id="linearb",
    ))
    try:
        r = _run("analyze", "hands", name)
        assert r.exit_code == 0 and "117" in r.output
        r2 = _run("analyze", "hands", name, "--hand", "117")
        assert r2.exit_code == 0 and "DA-RE" in r2.output
    finally:
        _LOADERS.pop(name, None)


def test_corpus_error_lists_fetched_corpora() -> None:
    r = _run("show", "bogus-corpus", "X1")
    assert r.exit_code == 1
    assert "damos" in r.output and "sigla" in r.output  # fetched corpora now discoverable
