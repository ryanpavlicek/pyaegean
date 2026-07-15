"""CLI-friendliness correctness tests for the db / viz / workbench / data / ai
groups and the root app.

Covers: `db search` opening the database read-only (a missing path is a clean
one-line failure that never creates a file; a non-SQLite file fails cleanly and
is left untouched), `aegean.db.search` treating limit <= 0 as unlimited on every
query path, the whole-token no-match hint, the `db build` next-command hint,
`plot` failing in one line on bad extensions/dpi and creating missing parent
directories on success, the plot meter help naming every meter `scan_line`
accepts, `workbench --port` range validation, `data fetch`/`remove` one-line
unknown-name errors with did-you-mean over names and stems, the fetch
next-command hint, the `data store` rename with `data cache` as a deprecated
alias, the ai stdin notes / `ai eval -o` / the translate lemmatizer warning
surfacing as one clean line, and the root help epilog + corrected --json claim
+ the module docstring command map."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean.cli import _build_app  # noqa: E402
from aegean.core.corpus import Corpus  # noqa: E402
from aegean.core.model import Document, DocumentMeta, Token, TokenKind  # noqa: E402

runner = CliRunner()


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


def _output(res) -> str:  # type: ignore[no-untyped-def]
    """Everything the user saw: click >= 8.2 mixes stdout and stderr in .output
    (older CliRunner defaults mixed them too)."""
    return res.output


def _stdout(res) -> str:  # type: ignore[no-untyped-def]
    """stdout alone when this click version separates it, else the mixed output."""
    try:
        return res.stdout
    except (ValueError, AttributeError):
        return res.output


def _stderr(res) -> str | None:  # type: ignore[no-untyped-def]
    """stderr alone when this click version separates it, else None."""
    try:
        return res.stderr
    except (ValueError, AttributeError):
        return None


def _word(text: str, position: int) -> Token:
    return Token(text, TokenKind.WORD, tuple(text.split("-")), line_no=0, position=position)


def _tiny_corpus() -> Corpus:
    """Three documents; KU-RO occurs four times (the top word), A-DU twice."""
    d0 = Document(
        id="D0", script_id="lineara", tokens=[_word("KU-RO", 0), _word("KU-RO", 1)],
        lines=[[0, 1]], meta=DocumentMeta(site="Haghia Triada"),
    )
    d1 = Document(
        id="D1", script_id="lineara", tokens=[_word("KU-RO", 0), _word("A-DU", 1)],
        lines=[[0, 1]], meta=DocumentMeta(site="Haghia Triada"),
    )
    d2 = Document(
        id="D2", script_id="lineara", tokens=[_word("KU-RO", 0), _word("A-DU", 1)],
        lines=[[0, 1]], meta=DocumentMeta(site="Zakros"),
    )
    return Corpus([d0, d1, d2], script_id="lineara")


@pytest.fixture()
def tiny_db(tmp_path: Path) -> Path:
    from aegean import db

    p = tmp_path / "tiny.db"
    db.to_sqlite(_tiny_corpus(), p)
    return p


@pytest.fixture()
def tiny_json(tmp_path: Path) -> Path:
    p = tmp_path / "tiny.json"
    _tiny_corpus().to_json(p)
    return p


# ── db search: read-only, clean failures ────────────────────────────────────
def test_db_search_missing_file_fails_cleanly_and_creates_nothing(app, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    missing = tmp_path / "missing.db"
    res = runner.invoke(app, ["db", "search", str(missing), "KU-RO"])
    assert res.exit_code == 1
    out = _output(res)
    assert "no database at" in out and "db build" in out
    assert "Traceback" not in out
    assert not missing.exists()  # a search must never create a file as a side effect


def test_db_search_non_database_file_fails_cleanly_and_leaves_it_untouched(
    app, tmp_path: Path  # type: ignore[no-untyped-def]
) -> None:
    junk = tmp_path / "notadb.db"
    junk.write_bytes(b"definitely not sqlite")
    res = runner.invoke(app, ["db", "search", str(junk), "KU-RO"])
    assert res.exit_code == 1
    out = _output(res)
    assert "not a corpus database" in out and "db build" in out
    assert "Traceback" not in out
    assert junk.read_bytes() == b"definitely not sqlite"  # read-only: byte-identical


def test_db_search_library_is_read_only_for_a_missing_path(tmp_path: Path) -> None:
    import sqlite3

    from aegean import db

    missing = tmp_path / "nope.db"
    with pytest.raises(sqlite3.Error):
        db.search(missing, "KU-RO")
    assert not missing.exists()  # plain sqlite3.connect would have created it


# ── db.search: limit <= 0 means every match ─────────────────────────────────
def test_db_search_limit_zero_or_negative_returns_every_match(tiny_db: Path) -> None:
    from aegean import db

    all_hits = db.search(tiny_db, "KU-RO", limit=0)
    assert len(all_hits) == 4  # every occurrence, hand-counted in the fixture
    assert all(t == "KU-RO" for _, _, t in all_hits)
    assert db.search(tiny_db, "KU-RO", limit=-1) == all_hits
    assert len(db.search(tiny_db, "KU-RO", limit=2)) == 2  # a positive limit still caps


def test_db_search_limit_zero_is_unlimited_in_substring_mode(tiny_db: Path) -> None:
    from aegean import db

    hits = db.search(tiny_db, "DU", limit=0, mode="substring")
    assert [t for _, _, t in hits] == ["A-DU", "A-DU"]  # both occurrences, not one
    assert len(db.search(tiny_db, "DU", limit=1, mode="substring")) == 1


def test_db_search_limit_zero_is_unlimited_without_fts(tmp_path: Path) -> None:
    from aegean import db

    p = tmp_path / "nofts.db"
    db.to_sqlite(_tiny_corpus(), p, fts=False)
    assert len(db.search(p, "KU-RO", limit=0)) == 4  # the NOCASE fallback path
    assert len(db.search(p, "κύριος", limit=0)) == 0  # the non-ASCII scan path survives


# ── db search / build UX ─────────────────────────────────────────────────────
def test_db_search_no_match_hint_names_substring_mode(app, tiny_db: Path) -> None:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["db", "search", str(tiny_db), "ZZ-ZZ"])
    assert res.exit_code == 0
    assert "no matches" in res.output
    assert "--substring" in res.output  # the whole-token default is the classic confusion
    res2 = runner.invoke(app, ["db", "search", str(tiny_db), "ZZ-ZZ", "--substring"])
    assert res2.exit_code == 0
    assert "no matches" in res2.output
    assert "pass --substring" not in res2.output  # already in substring mode: no hint


def test_db_search_writes_a_result_file(app, tiny_db: Path, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "hits.json"
    res = runner.invoke(app, ["db", "search", str(tiny_db), "KU-RO", "-o", str(out)])
    assert res.exit_code == 0
    hits = json.loads(out.read_text(encoding="utf-8"))
    assert len(hits) == 4
    assert all(h["text"] == "KU-RO" for h in hits)
    assert {h["doc_id"] for h in hits} == {"D0", "D1", "D2"}
    assert f"wrote {out}" in _output(res)


def test_db_build_hints_the_next_search_with_the_top_word(
    app, tiny_json: Path, tmp_path: Path  # type: ignore[no-untyped-def]
) -> None:
    from aegean import db

    out = tmp_path / "built.db"
    res = runner.invoke(app, ["db", "build", str(tiny_json), "-o", str(out)])
    assert res.exit_code == 0
    assert f"wrote 3 documents to {out}" in res.output
    # the hint names the real next command with this corpus's most frequent word
    assert f"search it:  aegean db search {out} KU-RO" in res.output
    assert len(db.search(out, "KU-RO", limit=0)) == 4  # and the hinted command works


def test_db_add_into_a_non_database_file_fails_in_one_line(
    app, tiny_json: Path, tmp_path: Path  # type: ignore[no-untyped-def]
) -> None:
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not sqlite either")
    res = runner.invoke(app, ["db", "add", str(tiny_json), "-o", str(junk)])
    assert res.exit_code == 1
    out = _output(res)
    assert "cannot write" in out and "Traceback" not in out


def test_db_group_help_mentions_append(app) -> None:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["db", "--help"])
    assert res.exit_code == 0
    assert "append to" in res.output  # the group one-liner covers add, not just build/search


# ── plot: clean failures, guarded write, honest help ─────────────────────────
def test_plot_meter_help_names_every_meter_scan_line_accepts() -> None:
    from aegean.cli import _viz
    from aegean.greek import meter

    for name in meter._SCANNERS:  # hexameter … trimeter + the seven aeolic lines
        assert name in _viz._METER_HELP


def test_plot_help_names_the_viz_extra_literally(app) -> None:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["plot", "--help"])
    assert res.exit_code == 0
    assert "pyaegean[viz]" in res.output  # rich must not eat the bracketed extra


def test_plot_unknown_corpus_prints_exactly_one_error_line(app, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("matplotlib")
    target = tmp_path / "f.png"
    res = runner.invoke(app, ["plot", "freq", "nosuchcorpus", "-o", str(target)])
    assert res.exit_code == 1
    out = _output(res)
    assert "unknown corpus" in out
    assert out.count("aegean:") == 1  # no spurious second 'aegean: Exit' line
    assert not target.exists()


def test_plot_bad_image_extension_fails_cleanly(app, tiny_json: Path, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("matplotlib")
    target = tmp_path / "out.xyz"
    res = runner.invoke(app, ["plot", "freq", str(tiny_json), "-o", str(target)])
    assert res.exit_code == 1
    out = _output(res)
    assert "xyz" in out  # matplotlib's readable unsupported-format message
    assert "Traceback" not in out
    assert not target.exists()


def test_plot_negative_dpi_fails_cleanly(app, tiny_json: Path, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("matplotlib")
    target = tmp_path / "out.png"
    res = runner.invoke(app, ["plot", "freq", str(tiny_json), "-o", str(target), "--dpi=-5"])
    assert res.exit_code == 1
    out = _output(res)
    assert "dpi" in out and "Traceback" not in out
    assert not target.exists()


def test_plot_creates_missing_parent_directories_on_success(
    app, tiny_json: Path, tmp_path: Path  # type: ignore[no-untyped-def]
) -> None:
    pytest.importorskip("matplotlib")
    target = tmp_path / "new" / "deep" / "out.png"
    res = runner.invoke(app, ["plot", "freq", str(tiny_json), "-o", str(target)])
    assert res.exit_code == 0, _output(res)
    assert target.exists() and target.stat().st_size > 0
    assert f"wrote {target}" in res.output


# ── workbench: port validation ───────────────────────────────────────────────
@pytest.mark.parametrize("port", ["0", "65536", "99999", "-1"])
def test_workbench_rejects_out_of_range_ports_up_front(app, port: str) -> None:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["workbench", f"--port={port}", "--no-browser"])
    assert res.exit_code == 1
    out = _output(res)
    assert "between 1 and 65535" in out
    assert "Traceback" not in out and "OverflowError" not in out


# ── data fetch / remove: one-line unknown-name errors with did-you-mean ─────
def test_data_fetch_unknown_name_is_one_fail_line_with_a_suggestion(app) -> None:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["data", "fetch", "damso"])
    assert res.exit_code == 1  # fail(), not typer.BadParameter's usage-error exit 2
    out = _output(res)
    assert "unknown dataset 'damso'" in out
    assert "did you mean" in out and "damos-corpus" in out  # the stem still finds it
    assert "aegean data list" in out
    assert "Usage:" not in out  # one line, no boxed usage panel


def test_data_remove_unknown_name_suggests_the_registered_name(app) -> None:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["data", "remove", "damoss"])
    assert res.exit_code == 1
    out = _output(res)
    assert "unknown dataset 'damoss'" in out and "damos-corpus" in out


def test_data_fetch_unknown_name_without_a_close_match_points_at_data_list(app) -> None:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["data", "fetch", "zzz-qqq-xyz"])
    assert res.exit_code == 1
    out = _output(res)
    assert "unknown dataset" in out and "aegean data list" in out
    assert "did you mean" not in out  # nothing is close: no fabricated suggestion


def test_data_fetch_prints_the_next_command_hint_off_stdout(
    app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # type: ignore[no-untyped-def]
) -> None:
    from aegean import data

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    src = tmp_path / "nt.src"
    src.write_bytes(b"x" * 16)
    monkeypatch.setitem(
        data._REMOTE, "nt-corpus", data.DataSpec(name="nt-corpus", url="", license="x")
    )
    monkeypatch.setenv(data._env_url_var("nt-corpus"), src.as_uri())
    res = runner.invoke(app, ["data", "fetch", "nt-corpus"])
    assert res.exit_code == 0
    stored = tmp_path / "cache" / "pyaegean" / "nt-corpus"
    stderr = _stderr(res)
    if stderr is not None:
        assert _stdout(res).strip() == str(stored)  # stdout stays the bare path (scripting)
        assert "load it:  aegean info nt" in stderr
    else:
        assert "load it:  aegean info nt" in _output(res)


def test_data_fetch_of_an_unmapped_asset_prints_no_hint(
    app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # type: ignore[no-untyped-def]
) -> None:
    from aegean import data

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    src = tmp_path / "blob.src"
    src.write_bytes(b"y" * 16)
    monkeypatch.setitem(data._REMOTE, "blob", data.DataSpec(name="blob", url="", license="x"))
    monkeypatch.setenv(data._env_url_var("blob"), src.as_uri())
    res = runner.invoke(app, ["data", "fetch", "blob"])
    assert res.exit_code == 0
    out = _output(res)
    assert "load it:" not in out and "serve it:" not in out


# ── data store (renamed) + the deprecated cache alias ────────────────────────
def test_data_store_reports_location_and_entries(
    app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    from aegean.data import cache_dir

    root = cache_dir()
    root.mkdir(parents=True, exist_ok=True)  # cache_dir() may already create it
    (root / "thing.bin").write_bytes(b"z" * 100)
    res = runner.invoke(app, ["data", "store", "--json"])
    assert res.exit_code == 0
    payload = json.loads(_stdout(res))
    assert payload["cache_dir"] == str(root)
    assert payload["entries"] == [{"name": "thing.bin", "mb": 0.0}]


def test_data_cache_is_a_deprecated_alias_that_names_the_replacement(
    app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    from aegean.data import cache_dir

    root = cache_dir()
    root.mkdir(parents=True, exist_ok=True)  # cache_dir() may already create it
    (root / "thing.bin").write_bytes(b"z" * 100)
    res = runner.invoke(app, ["data", "cache", "--json"])
    assert res.exit_code == 0  # the existing alias warns and names its replacement
    store_res = runner.invoke(app, ["data", "store", "--json"])
    assert json.loads(_stdout(res)) == json.loads(_stdout(store_res))  # same payload
    out = _output(res)
    assert "deprecated" in out and "aegean data store" in out  # names the replacement


# ── ai: stdin notes, eval -o, the surfaced lemmatizer warning ────────────────
def test_ai_ask_and_hypotheses_help_note_stdin(app) -> None:  # type: ignore[no-untyped-def]
    cmd = typer.main.get_command(app)
    ai_grp = cmd.commands["ai"]
    for name, arg in (("ask", "question"), ("hypotheses", "text")):
        param = next(p for p in ai_grp.commands[name].params if p.name == arg)
        assert "'-' reads stdin" in (param.help or ""), name


def test_ai_eval_output_option_writes_the_report(
    app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # type: ignore[no-untyped-def]
) -> None:
    from aegean import ai as ai_mod
    from aegean.cli import _ai

    report = {"groundedness": 0.9, "cases": [{"name": "c1", "grounded": 1.0}]}
    monkeypatch.setattr(_ai, "_client", lambda provider, model: object())
    monkeypatch.setattr(ai_mod, "run_eval", lambda cases, client: report)
    out = tmp_path / "eval.json"
    res = runner.invoke(app, ["ai", "eval", "-o", str(out)])
    assert res.exit_code == 0, _output(res)
    assert json.loads(out.read_text(encoding="utf-8")) == report
    assert f"wrote {out}" in _output(res)
    # -o combines with --json: the file is written and JSON still prints to stdout
    out2 = tmp_path / "eval2.json"
    res2 = runner.invoke(app, ["ai", "eval", "--json", "-o", str(out2)])
    assert res2.exit_code == 0
    assert json.loads(_stdout(res2)) == report
    assert json.loads(out2.read_text(encoding="utf-8")) == report


def test_ai_translate_surfaces_the_lemmatizer_warning_as_one_clean_line(
    app, monkeypatch: pytest.MonkeyPatch  # type: ignore[no-untyped-def]
) -> None:
    from aegean import translate as tr_mod
    from aegean.cli import _ai

    message = "Grounded Greek translation is using the baseline lemmatizer"

    def fake_translate(text: str, **kwargs: object) -> SimpleNamespace:
        warnings.warn(message, UserWarning, stacklevel=1)
        return SimpleNamespace(
            text="in the beginning", provider="prov", model="mod", grounding=()
        )

    monkeypatch.setattr(_ai, "_client", lambda provider, model: object())
    monkeypatch.setattr(tr_mod, "translate", fake_translate)
    res = runner.invoke(app, ["ai", "translate", "ἐν ἀρχῇ"])
    assert res.exit_code == 0, _output(res)
    out = _output(res)
    assert f"aegean: {message}" in out  # the house one-line surface
    assert "UserWarning" not in out and "_ai.py" not in out  # not a raw Python warning
    assert "in the beginning" in _stdout(res)  # the translation itself still prints


# ── root app: epilog, honest --json claim, complete docstring map ────────────
def test_root_help_epilog_names_a_quickstart_and_the_docs(app) -> None:  # type: ignore[no-untyped-def]
    cmd = typer.main.get_command(app)
    epilog = cmd.epilog or ""
    assert "https://github.com/ryanpavlicek/pyaegean/wiki" in epilog
    assert "aegean info lineara" in epilog and "aegean repl" in epilog
    res = runner.invoke(app, ["--help"])  # and it actually renders
    assert res.exit_code == 0
    assert "pyaegean/wiki" in res.output


def test_root_help_does_not_overclaim_json(app) -> None:  # type: ignore[no-untyped-def]
    cmd = typer.main.get_command(app)
    help_text = cmd.help or ""
    assert "Every command takes --json" not in help_text
    assert "data-producing command takes --json" in help_text


def test_cli_module_docstring_maps_every_registered_command(app) -> None:  # type: ignore[no-untyped-def]
    import aegean.cli as cli_pkg

    cmd = typer.main.get_command(app)
    doc = cli_pkg.__doc__ or ""
    for name in cmd.commands:  # cache, combine, import, db, workbench, repl included
        assert f"``{name}``" in doc or f"aegean {name} " in doc, name
