"""The `aegean repl` interactive shell, exercised through its scriptable
(non-TTY) path: each line of piped stdin is dispatched as one command, errors
keep the shell alive, and the exit words stop it. The prompt_toolkit line editor
only runs under a real terminal and is not driven here."""

from __future__ import annotations

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean.cli import _build_app  # noqa: E402

runner = CliRunner()


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


def _repl(app, script: str):  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["repl"], input=script)
    assert res.exit_code == 0, res.output
    return res.output


def test_repl_is_registered(app):  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "repl" in res.output


def test_repl_dispatches_a_command(app):  # type: ignore[no-untyped-def]
    out = _repl(app, "info lineara\n:exit\n")
    assert "lineara" in out and "documents" in out


def test_repl_descends_into_subgroups(app):  # type: ignore[no-untyped-def]
    out = _repl(app, "greek syllabify Ποσειδῶνι\n:exit\n")
    assert "Πο-σει-δῶ-νι" in out


def test_repl_survives_a_bad_command(app):  # type: ignore[no-untyped-def]
    # An unknown command must not end the session — the next line still runs.
    out = _repl(app, "boguscmd\ngreek syllabify Ποσειδῶνι\n")
    assert "Πο-σει-δῶ-νι" in out


def test_repl_exit_word_stops_the_loop(app):  # type: ignore[no-untyped-def]
    # Nothing after :exit should run.
    out = _repl(app, ":exit\ninfo lineara\n")
    assert "documents" not in out


def test_repl_does_not_nest(app):  # type: ignore[no-untyped-def]
    out = _repl(app, "repl\ngreek syllabify Ποσειδῶνι\n")
    assert "already in the interactive shell" in out
    assert "Πο-σει-δῶ-νι" in out  # the line after the guard still runs


def test_repl_help_word_shows_commands(app):  # type: ignore[no-untyped-def]
    out = _repl(app, ":help\n:exit\n")
    assert "Commands" in out and "greek" in out


def test_repl_completer(app):  # type: ignore[no-untyped-def]
    # The Tab-completer is TTY-only in use, but its logic is pure and testable: it
    # completes commands at the current level, descends into sub-groups, and offers a
    # leaf command's options. (Also guards the typer-version-robust group handling.)
    from aegean.cli._repl import _make_completer

    group = typer.main.get_command(app)
    comp = _make_completer(group)

    class _Doc:
        def __init__(self, text: str) -> None:
            self.text_before_cursor = text

    def names(text: str) -> set:  # type: ignore[type-arg]
        return {c.text for c in comp.get_completions(_Doc(text), None)}

    assert "stats" in names("st")  # top-level command
    assert "syllabify" in names("greek sy")  # descend into the greek sub-group
    assert any(o.startswith("--") for o in names("stats lineara --"))  # leaf options
