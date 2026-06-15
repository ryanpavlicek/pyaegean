"""The universal corpus resolver (`aegean.read_corpus`) and the CLI input flexibility it gives
every corpus command: registered id, Greek work id, .json/.db file, inline JSON, or stdin.
"""

from __future__ import annotations

import io as _io

import pytest

import aegean
from aegean import read_corpus
from aegean.core.resolve import CorpusNotFound


def test_read_corpus_registered_id() -> None:
    assert len(read_corpus("lineara")) == 1721


def test_read_corpus_json_file(tmp_path) -> None:
    p = tmp_path / "c.json"
    aegean.load("greek").to_json(p)
    assert len(read_corpus(str(p))) == len(aegean.load("greek"))


def test_read_corpus_db_file(tmp_path) -> None:
    p = tmp_path / "c.db"
    aegean.load("greek").to_sql(p)
    assert len(read_corpus(str(p))) == len(aegean.load("greek"))


def test_read_corpus_inline_json() -> None:
    text = aegean.load("greek").to_json()
    assert len(read_corpus(text)) == len(aegean.load("greek"))


def test_read_corpus_stdin(monkeypatch) -> None:
    text = aegean.load("greek").to_json()
    monkeypatch.setattr("sys.stdin", _io.StringIO(text))
    assert len(read_corpus("-")) == len(aegean.load("greek"))


def test_read_corpus_work_id_routes_to_load_work(monkeypatch) -> None:
    sentinel = aegean.load("greek")
    seen: dict[str, str] = {}

    def fake_load_work(work: str, **kw):  # type: ignore[no-untyped-def]
        seen["work"] = work
        return sentinel

    monkeypatch.setattr("aegean.greek.load_work", fake_load_work)
    out = read_corpus("tlg0012.tlg001")
    assert seen["work"] == "tlg0012.tlg001"
    assert out is sentinel


def test_read_corpus_unknown_lists_accepted_forms() -> None:
    with pytest.raises(CorpusNotFound) as exc:
        read_corpus("definitely-not-a-corpus")
    msg = str(exc.value)
    assert "lineara" in msg and "tlg0012.tlg001" in msg


def test_registered_id_beats_same_named_file(tmp_path, monkeypatch) -> None:
    (tmp_path / "lineara").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert len(read_corpus("lineara")) == 1721


def test_missing_file_errors(tmp_path) -> None:
    with pytest.raises(CorpusNotFound):
        read_corpus(str(tmp_path / "ghost.json"))
    with pytest.raises(CorpusNotFound):
        read_corpus(str(tmp_path / "ghost.db"))


# ── CLI cascade: corpus commands now accept a .json/.db source ───────────────────────
def test_cli_stats_accepts_json_file(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    p = tmp_path / "c.json"
    aegean.load("greek").to_json(p)
    r = CliRunner().invoke(_build_app(), ["stats", str(p), "--json"])
    assert r.exit_code == 0, r.output


def test_cli_db_build_accepts_json_file(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    src = tmp_path / "c.json"
    db = tmp_path / "c.db"
    aegean.load("greek").to_json(src)
    r = CliRunner().invoke(_build_app(), ["db", "build", str(src), "-o", str(db)])
    assert r.exit_code == 0, r.output
    assert db.exists()


def test_cli_unknown_corpus_exit_1() -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    r = CliRunner().invoke(_build_app(), ["info", "definitely-not-a-corpus"])
    assert r.exit_code == 1


# ── query -o: save a filtered/queried subset as a reusable corpus ─────────────────────
def test_query_save_subset(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    out = tmp_path / "ht.json"
    r = CliRunner().invoke(
        _build_app(), ["query", "lineara", "--where", "site-is=Haghia Triada", "-o", str(out)]
    )
    assert r.exit_code == 0, r.output
    saved = read_corpus(str(out))
    assert len(saved) == len(aegean.load("lineara").filter(site="Haghia Triada"))
    assert "subset: query" in saved.cite()  # the saved subset cites the query


def test_query_save_rejects_words_mode(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    r = CliRunner().invoke(
        _build_app(),
        ["query", "lineara", "--where", "word-prefix=KU", "--output-kind", "words",
         "-o", str(tmp_path / "x.json")],
    )
    assert r.exit_code == 1


def test_query_results_to_corpus() -> None:
    from aegean.analysis import FilterRow

    c = aegean.load("lineara")
    res = c.query([FilterRow("site-is", "Haghia Triada")], "inscriptions")
    sub = res.to_corpus(c)
    assert len(sub) == len(c.filter(site="Haghia Triada"))
    assert sub.script_id == c.script_id
