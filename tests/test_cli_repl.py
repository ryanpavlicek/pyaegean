"""The `aegean repl` interactive shell, exercised through its scriptable
(non-TTY) path: each line of piped stdin is dispatched as one command, errors
keep the shell alive, and the exit words stop it. Also covered: the `use`
session-corpus directive (validation, did-you-mean, allowlist injection),
the `:examples` starter lines (every listed line must really run), and the
persistent prompt_toolkit history. The prompt_toolkit line editor itself only
runs under a real terminal and is not driven here."""

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


# --- the `use` session-corpus directive ---------------------------------------


def test_repl_use_sets_the_session_corpus(app):  # type: ignore[no-untyped-def]
    # After `use lineara`, a corpus-first command can drop its corpus argument.
    out = _repl(app, "use lineara\nshow HT13\n:exit\n")
    assert "session corpus: lineara" in out
    assert "KA-U-DE-TA" in out  # HT13 line 1 — show really read lineara


def test_repl_use_injects_for_stats_and_balance(app):  # type: ignore[no-untyped-def]
    out = _repl(app, "use lineara\nstats --top 3\nbalance ht13\n:exit\n")
    assert "KU-RO" in out  # lineara's most frequent word, from `stats --top 3`
    assert "130.5" in out  # HT13's stated KU-RO total, from `balance ht13`


def test_repl_use_explicit_corpus_still_wins(app):  # type: ignore[no-untyped-def]
    # A line that names its own corpus is never rewritten by the session default.
    out = _repl(app, "use linearb\ninfo lineara\n:exit\n")
    assert "1721" in out  # lineara's document count, not linearb's


def test_repl_use_unknown_target_gets_did_you_mean(app):  # type: ignore[no-untyped-def]
    out = _repl(app, "use linera\n:exit\n")
    assert "did you mean" in out and "lineara" in out
    # and the invalid target was not stored: the next corpus-less line is a usage error
    out2 = _repl(app, "use linera\nstats\n:exit\n")
    assert "Missing argument" in out2


def test_repl_use_missing_file_is_rejected(app):  # type: ignore[no-untyped-def]
    out = _repl(app, "use missing.json\n:exit\n")
    assert "no such corpus file" in out


def test_repl_use_off_clears_the_default(app):  # type: ignore[no-untyped-def]
    out = _repl(app, "use lineara\nuse off\nstats\n:exit\n")
    assert "session corpus cleared" in out
    assert "Missing argument" in out  # corpus-less stats fails again after the clear
    assert "KU-RO" not in out  # nothing was silently read from the cleared default


def test_repl_use_alone_reports_state(app):  # type: ignore[no-untyped-def]
    out = _repl(app, "use\n:exit\n")
    assert "no session corpus" in out
    out2 = _repl(app, "use lineara\nuse\n:exit\n")
    assert out2.count("session corpus: lineara") == 2  # the set line and the show line


def test_repl_use_accepts_a_saved_corpus_file(app, tmp_path):  # type: ignore[no-untyped-def]
    target = tmp_path / "ht.json"
    res = runner.invoke(app, ["load", "lineara", "--site", "Haghia Triada", "-o", str(target)])
    assert res.exit_code == 0
    out = _repl(app, f'use "{target.as_posix()}"\nstats --top 3\n:exit\n')
    assert "session corpus:" in out
    assert "KU-RO" in out  # the Haghia Triada subset still tops out at KU-RO


def test_with_session_corpus_injection_rules():  # type: ignore[no-untyped-def]
    # The injection is an explicit allowlist plus a corpus-shape check on the first
    # token after the command: absent/option-shaped tokens get the default, anything
    # corpus-shaped keeps the line as typed.
    from aegean.cli._repl import _with_session_corpus as inject

    assert inject(["show", "HT13"], "lineara") == ["show", "lineara", "HT13"]
    assert inject(["stats"], "lineara") == ["stats", "lineara"]
    assert inject(["stats", "--top", "5"], "lineara") == ["stats", "lineara", "--top", "5"]
    assert inject(["db", "build", "-o", "x.db"], "lineara") == [
        "db", "build", "lineara", "-o", "x.db",
    ]
    # explicit corpora win: exact id, case-forgiven id, work id, file extension
    assert inject(["show", "linearb", "HT13"], "lineara") == ["show", "linearb", "HT13"]
    assert inject(["show", "LINEARB", "HT13"], "lineara") == ["show", "LINEARB", "HT13"]
    assert inject(["show", "tlg0012.tlg001", "1"], "lineara") == ["show", "tlg0012.tlg001", "1"]
    assert inject(["stats", "saved.json"], "lineara") == ["stats", "saved.json"]
    # non-allowlisted commands and sessions without a default pass through untouched
    assert inject(["greek", "syllabify", "λόγος"], "lineara") == ["greek", "syllabify", "λόγος"]
    assert inject(["show", "HT13"], None) == ["show", "HT13"]


# --- :examples ------------------------------------------------------------------


def test_repl_examples_lists_every_starter_line(app):  # type: ignore[no-untyped-def]
    from aegean.cli._repl import _EXAMPLES

    assert len(_EXAMPLES) >= 10
    out = _repl(app, ":examples\n:exit\n")
    for cmd, _ in _EXAMPLES:
        assert cmd in out


def test_repl_examples_lines_all_execute(app):  # type: ignore[no-untyped-def]
    # The starter lines are real commands: the whole list runs in one scripted
    # session, in order (the final `show HT13` relies on `use lineara` before it).
    from aegean.cli._repl import _EXAMPLES

    script = "\n".join(cmd for cmd, _ in _EXAMPLES) + "\n:exit\n"
    out = _repl(app, script)
    assert "No such command" not in out and "Missing argument" not in out
    assert "KA-U-DE-TA" in out  # show lineara HT13 (and show HT13 via the session corpus)
    assert "Πο-σει-δῶ-νι" in out  # greek syllabify Ποσειδῶνι
    assert "ποιμήν" in out  # bridge linearb po-me
    assert "session corpus: lineara" in out  # the use directive really ran


# --- banner / help discoverability ------------------------------------------------


def test_repl_banner_names_examples_and_completion():  # type: ignore[no-untyped-def]
    from aegean.cli._repl import _BANNER

    both = [ln for ln in _BANNER.splitlines() if ":examples" in ln and "--install-completion" in ln]
    assert len(both) == 1  # one uncluttered line carries both pointers


def test_repl_help_names_the_shell_directives(app):  # type: ignore[no-untyped-def]
    out = _repl(app, ":help\n:exit\n")
    assert "use CORPUS" in out and ":examples" in out
    assert "Commands" in out  # the full --help still follows the preamble


# --- persistent history -------------------------------------------------------------


def test_repl_history_persists_across_sessions(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    pytest.importorskip("prompt_toolkit")
    from prompt_toolkit.history import FileHistory

    from aegean.cli import _repl as repl_mod

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert repl_mod._history_path() == tmp_path / "pyaegean" / "repl_history"
    first = repl_mod._history()
    assert isinstance(first, FileHistory)
    first.append_string("stats lineara --top 5")
    second = repl_mod._history()  # a fresh session over the same file
    assert "stats lineara --top 5" in list(second.load_history_strings())


def test_repl_history_falls_back_when_unwritable(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    pytest.importorskip("prompt_toolkit")
    from prompt_toolkit.history import InMemoryHistory

    from aegean.cli import _repl as repl_mod

    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(blocker / "config"))
    assert isinstance(repl_mod._history(), InMemoryHistory)  # the shell still starts
