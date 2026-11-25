"""Tests for default-REPL bare `aegean` launch and unified predictive completion.

Covers:
1. Bare `aegean` launches the interactive REPL on a TTY and prints help when non-interactive;
2. Unified `_complete.py` engine handles arbitrary nesting depth (including all 9 `bible`
   subcommands and all 7 3-level `greek` subcommands), `--flag` options, and offline domain
   values (NT/LXX books, editions, comma-separated manuscript witnesses, corpora, datasets,
   Greek meters, dictionaries, shell directives);
3. Fish-style inline ghost-text (`suggest_inline`) combines recent history with live
   command/flag/argument prediction in both `aegean repl` (`_make_auto_suggest`) and TUI `:`.
"""

from __future__ import annotations

import types

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean import cli as cli_mod  # noqa: E402
from aegean.cli import _build_app  # noqa: E402
from aegean.cli._complete import (  # noqa: E402
    complete_line,
    shell_complete_bible_book,
    shell_complete_witness,
    suggest_inline,
    walk_command_paths,
)

runner = CliRunner()


@pytest.fixture(scope="module")
def group():  # type: ignore[no-untyped-def]
    return typer.main.get_command(_build_app())


def test_bare_aegean_launches_repl_on_tty_and_help_when_piped(monkeypatch) -> None:
    from aegean.cli import _repl as repl_mod

    app = _build_app()
    # Non-TTY (default under CliRunner): prints help and exits 0.
    monkeypatch.setattr(cli_mod, "_is_interactive_tty", lambda: False)
    res_help = runner.invoke(app, [])
    assert res_help.exit_code == 0
    assert "bible" in res_help.output and "greek" in res_help.output

    # Interactive TTY: launches run_repl directly.
    called: list[object] = []
    monkeypatch.setattr(cli_mod, "_is_interactive_tty", lambda: True)
    monkeypatch.setattr(repl_mod, "run_repl", lambda ctx: called.append(ctx.find_root().command))
    res_tty = runner.invoke(app, [])
    assert res_tty.exit_code == 0, res_tty.output
    assert len(called) == 1


def test_walk_command_paths_covers_bible_and_3level_nested_commands(group) -> None:  # type: ignore[no-untyped-def]
    paths = {p for p, _ in walk_command_paths(group, include_directives=True)}
    for sub in (
        "bible",
        "bible read",
        "bible compare",
        "bible witnesses",
        "bible strongs",
        "bible word-study",
        "bible search",
        "bible commentary",
        "bible books",
        "bible psalm",
    ):
        assert sub in paths
    for nested3 in (
        "greek annotation-profiles list",
        "greek annotation-profiles show",
        "greek conllu export",
        "greek conllu inspect",
        "greek interop export",
        "greek interop import",
        "greek interop report",
    ):
        assert nested3 in paths


def test_complete_line_bible_commands_flags_and_domain_values(group) -> None:  # type: ignore[no-untyped-def]
    def inserts(line: str) -> list[str]:
        return [c.insert for c in complete_line(group, line)]

    # Subcommands
    assert "read" in inserts("bible r")
    assert "witnesses" in inserts("bible w")
    assert "word-study" in inserts("bible w")

    # Positional NT & LXX book completion
    assert "John" in inserts("bible read J")
    assert "Gen" in inserts("bible read G")
    lxx_books = inserts("bible read --lxx P")
    assert "Ps" in lxx_books and "Prov" in lxx_books
    assert "Phil" not in lxx_books  # NT-only book excluded once --lxx is passed

    # Edition & comma-separated manuscript witness completion
    assert "sblgnt" in inserts("bible read John 1.1 -e s")
    assert "srgnt" in inserts("bible read John 1.1 -e s")
    assert "byz" in inserts("bible compare John 1.18 -e b")
    assert "sblgnt,byz" in inserts("bible compare John 1.18 -e sblgnt,b")
    assert "P52" in inserts("bible witnesses John 18.37 --sigla P5")
    assert "P52,P66" in inserts("bible witnesses John 18.37 --sigla P52,P6")
    assert "P52,P52" not in inserts("bible witnesses John 18.37 --sigla P52,P5")

    # Flags with deduplication of already-used non-repeatable flags
    flags_fresh = inserts("bible read John 1.1 --")
    assert "--interlinear" in flags_fresh and "--lxx" in flags_fresh and "--offline" in flags_fresh
    flags_used = inserts("bible read John 1.1 --lxx --")
    assert "--lxx" not in flags_used and "--offline" in flags_used

    # Other bible option values & collections
    assert set(inserts("bible books ")) == {"nt", "lxx", "editions", "witnesses", "all"}
    assert "morph" in inserts("bible search V-AAI --by m")
    assert "catena" in inserts("bible commentary John --kind c")
    assert set(inserts("bible psalm 23 --from ")) == {"mt", "lxx"}


def test_complete_line_all_other_cli_groups_and_directives(group) -> None:  # type: ignore[no-untyped-def]
    def inserts(line: str) -> list[str]:
        return [c.insert for c in complete_line(group, line)]

    # 3-level nested Greek subcommands
    assert set(inserts("greek interop ")) == {"export", "import", "report"}
    assert "spacy" in inserts("greek interop export f.conllu --target s")

    # Greek meters, dictionaries, policies, corpora, datasets, shell directives
    assert "hexameter" in inserts("greek scan line --meter h")
    assert "sapphic_hendecasyllable" in inserts("greek scan line --meter s")
    assert "lsj" in inserts("greek gloss λόγος -d l")
    assert "lineara" in inserts("show lin")
    assert "lxx-corpus" in inserts("data fetch lxx")
    assert "lineara" in inserts("use lin")
    assert "off" in inserts("use o")
    assert ":examples" in inserts(":ex")


def test_inline_ghost_text_history_precedence_and_auto_suggest(group) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._repl import _make_auto_suggest

    # Without history, predicts from live command/argument tree
    assert suggest_inline(group, "bible wit") == "bible witnesses"
    assert suggest_inline(group, "bible read Jo") == "bible read John"
    assert suggest_inline(group, "bible read John 1.1 --inter") == "bible read John 1.1 --interlinear"

    # With history, most recent matching command wins
    hist = ["bible read John 1.1 --offline", "bible read John 1.18 --interlinear"]
    assert suggest_inline(group, "bible read John 1.", history=hist) == "bible read John 1.18 --interlinear"

    # prompt_toolkit AutoSuggest returns suffix only
    suggester = _make_auto_suggest(group)
    doc = types.SimpleNamespace(text="bible read Jo", cursor_position=len("bible read Jo"))
    buf = types.SimpleNamespace(history=types.SimpleNamespace(get_strings=lambda: []))
    sugg = suggester.get_suggestion(buf, doc)
    assert sugg is not None and sugg.text == "hn"


def test_native_shell_complete_callbacks() -> None:
    ctx_lxx = types.SimpleNamespace(params={"lxx": True})
    lxx_hits = [v for v, _ in shell_complete_bible_book(ctx_lxx, "Ge")]
    assert "Gen" in lxx_hits
    wit_hits = [v for v, _ in shell_complete_witness("P52,P6")]
    assert "P52,P66" in wit_hits


def test_commentary_and_prioritized_flag_predictions(group) -> None:  # type: ignore[no-untyped-def]
    def inserts(line: str) -> list[str]:
        return [c.insert for c in complete_line(group, line)]

    comm_top = inserts("bible commentary ")
    assert comm_top[:2] == ["read", "search"]
    assert "tlg4102.tlg001" in comm_top
    assert "tlg4102.tlg001" in inserts("bible commentary read Matt ")

    flags = inserts("bible read John 1.1 --")
    assert flags[0] == "--interlinear"
    assert flags.index("--interlinear") < flags.index("--json") < flags.index("--ref")

