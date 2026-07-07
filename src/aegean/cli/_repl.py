"""``aegean repl`` — an interactive shell over the whole command tree.

Drops the ``aegean`` prefix: inside the shell you type subcommands directly
(``stats lineara --top 5``, ``greek catalog plato``, ``ai translate …``) with
Tab-completion of commands and options and a history that persists across
sessions (``~/.config/pyaegean/repl_history``, honoring ``XDG_CONFIG_HOME``).
Each line is dispatched through the same Typer app the ``aegean`` command uses,
so every subcommand behaves identically. Two shell-only directives add session
sugar: ``use CORPUS`` validates a corpus spec (with the standard did-you-mean)
and stores it as the session default, which corpus-first commands (``show``,
``stats``, ``search``, …) then inherit when their line names none; and
``:examples`` prints copyable starter lines spanning the command groups. The
interactive line editing is provided by ``prompt_toolkit`` (ships with the
``[cli]`` extra); when standard input is not a terminal (a pipe or a test
harness) commands are read line-by-line instead, so the shell is scriptable too.

The Click that backs the command tree is reached through Typer (``typer.Context``
and the group object itself), never by importing the standalone ``click``
package — typer ≥ 0.26 vendors its own Click, so the standalone package may not
be installed.
"""

from __future__ import annotations

import dataclasses
import os
import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import typer

if TYPE_CHECKING:  # type hints only; at runtime Click is reached via typer, not imported
    import click

_EXIT_WORDS = {":exit", ":quit", ":q", "exit", "quit"}
_HELP_WORDS = {":help", "help", "?"}
_EXAMPLE_WORDS = {":examples", "examples"}

_BANNER = (
    "aegean interactive shell — commands without the 'aegean' prefix.\n"
    "Tab completes, history persists, :help lists commands, :exit or Ctrl-D quits.\n"
    ":examples shows starter lines; 'aegean --install-completion' (outside the shell) "
    "adds completion to your regular shell."
)

# Commands whose FIRST positional argument is a corpus. The session default set by the
# `use` directive is injected only for these exact command paths — an explicit
# allowlist, never a signature heuristic, so no other command's arguments are rewritten.
_CORPUS_FIRST: frozenset[tuple[str, ...]] = frozenset(
    {
        ("info",), ("load",), ("show",), ("search",), ("query",), ("stats",),
        ("dispersion",), ("keyness",), ("balance",), ("cite",), ("export",),
        ("geo",), ("sign",),
        ("db", "build"),
        ("analyze", "assoc"), ("analyze", "cooccur"), ("analyze", "clusters"),
        ("analyze", "structure"), ("analyze", "hands"),
    }
)

# The `:examples` starter lines: real commands, kept runnable as typed and in order
# (the final pair demonstrates the `use` directive, so `show HT13` follows `use lineara`).
# tests/test_cli_repl.py executes the whole list in one scripted session.
_EXAMPLES: tuple[tuple[str, str], ...] = (
    ("info lineara", "corpus overview: size, provenance, license"),
    ("show lineara HT13", "one document, metadata and line-by-line tokens"),
    ('search lineara "KU-*-RO"', "wildcard sign-pattern search (* is one sign)"),
    ("stats lineara --top 10", "word frequencies (--signs for single signs)"),
    ("balance lineara HT13", "do the stated accounting totals add up?"),
    ("geo lineara", "find-site coordinates, Pleiades-aligned"),
    ("bridge linearb po-me", "read a deciphered syllabic word as Greek"),
    ("greek syllabify Ποσειδῶνι", "Greek NLP: syllabification"),
    ('greek pipeline "μῆνιν ἄειδε θεά"', "per-token analysis in one call"),
    ("analyze compare po-me ποιμήν", "cross-script phonetic comparison"),
    ("data list", "the fetchable datasets and what is local"),
    ("use lineara", "set a session corpus for corpus-first commands"),
    ("show HT13", "…which can then drop the corpus argument"),
)


def register(app: typer.Typer) -> None:
    app.command()(repl)


@dataclasses.dataclass
class _Session:
    """Mutable per-shell state: the corpus stored by the ``use`` directive."""

    corpus: str | None = None


def _is_group(cmd: object) -> bool:
    """Whether a command can enumerate and resolve subcommands. Duck-typed on
    purpose: a Typer/Click group answers ``get_command``/``list_commands``, and
    typer 0.26's ``TyperGroup`` is not a ``click.Group`` subclass for ``isinstance``."""
    return hasattr(cmd, "get_command") and hasattr(cmd, "list_commands")


def repl(ctx: typer.Context) -> None:
    """Start an interactive shell — run commands without the ``aegean`` prefix.

    Type subcommands directly (``stats lineara --top 5``, ``greek catalog plato``)
    with Tab-completion and a history that persists across sessions. Shell-only
    directives: ``use CORPUS`` sets a session corpus (corpus-first commands such as
    ``show`` or ``stats`` then default to it; ``use off`` clears), ``:examples``
    prints copyable starter lines, ``:help`` shows the command list; ``:exit``,
    ``quit``, or Ctrl-D leaves the shell.
    """
    group = cast("click.Group", ctx.find_root().command)  # the top-level aegean group
    session = _Session()
    if sys.stdin.isatty():
        _interactive_loop(group, session)
    else:
        for raw in sys.stdin:  # scriptable / testable path: one command per line
            if not _run_line(group, raw, session):
                break


def _run_line(group: click.Group, line: str, session: _Session) -> bool:
    """Execute one REPL line against the group. Return ``False`` to stop the loop."""
    line = line.strip()
    if not line:
        return True
    if line in _EXIT_WORDS:
        return False
    if line in _EXAMPLE_WORDS:
        _print_examples()
        return True
    if line in _HELP_WORDS:
        print(
            "shell-only: use CORPUS sets a session corpus (use off clears), "
            ":examples prints starter lines, :exit leaves.",
            file=sys.stderr,
        )
        _print_menu(group)
        return True
    try:
        args = shlex.split(line)
    except ValueError as exc:  # unbalanced quotes etc.
        print(f"aegean: {exc}", file=sys.stderr)
        return True
    if args and args[0] == "use":  # shell-only directive, never dispatched
        _handle_use(args[1:], session)
        return True
    if args and args[0] == "repl":  # don't nest the shell into itself
        print("aegean: already in the interactive shell.", file=sys.stderr)
        return True
    args = _with_session_corpus(args, session.corpus)
    try:
        # Re-enter the CLI as if freshly invoked; non-standalone so Click raises
        # instead of exiting the process, keeping the shell alive line to line.
        group.main(args=args, prog_name="aegean", standalone_mode=False)
    except SystemExit:
        pass  # e.g. --help calls ctx.exit(); not a reason to leave the shell
    except Exception as exc:  # any command error must not end the session
        # Click's own errors render themselves via .show(); anything else gets one
        # line. Duck-typed so it holds whether typer uses standalone or vendored Click.
        show = getattr(exc, "show", None)
        if callable(show):
            show()
        else:
            print(f"aegean: {exc}", file=sys.stderr)
    return True


def _print_menu(group: click.Group) -> None:
    """Render the root command map — the same output bare ``aegean`` (and ``aegean --help``)
    show. Dispatched through the live group so it can never drift from the real command
    surface; ``standalone_mode=False`` makes ``--help`` raise ``SystemExit``, which we swallow."""
    try:
        group.main(args=["--help"], prog_name="aegean", standalone_mode=False)
    except SystemExit:
        pass


def _print_examples() -> None:
    """Render the ``:examples`` starter lines: the command, then a dim description.

    ``soft_wrap`` keeps each command on one physical line whatever the console
    width, so every line can be copied and run as printed."""
    from rich.text import Text

    from ._common import console

    width = max(len(cmd) for cmd, _ in _EXAMPLES) + 2
    for cmd, desc in _EXAMPLES:
        text = Text("  ")
        text.append(cmd.ljust(width))
        text.append(desc, style="dim")
        console().print(text, soft_wrap=True)


def _handle_use(rest: list[str], session: _Session) -> None:
    """The ``use`` directive: set (``use lineara``), show (``use``), or clear
    (``use off``) the session corpus. Messages follow the shell's stderr style."""
    if not rest:
        if session.corpus is None:
            print(
                "aegean: no session corpus — 'use CORPUS' sets one (e.g. use lineara).",
                file=sys.stderr,
            )
        else:
            print(f"aegean: session corpus: {session.corpus}", file=sys.stderr)
        return
    if len(rest) > 1:
        print("aegean: use takes one corpus ('use lineara'; 'use off' clears).", file=sys.stderr)
        return
    spec = rest[0]
    if spec == "off":
        session.corpus = None
        print("aegean: session corpus cleared.", file=sys.stderr)
        return
    error = _session_corpus_error(spec)
    if error is not None:
        print(f"aegean: {error}", file=sys.stderr)
        return
    session.corpus = spec
    print(
        f"aegean: session corpus: {spec} — corpus-first commands (show, stats, search, …) "
        "now default to it; 'use off' clears.",
        file=sys.stderr,
    )


def _registered_ids() -> list[str]:
    """The registered corpus ids, importing ``aegean`` so every built-in loader
    (lineara, linearb, cypriot, cyprominoan, greek, nt, damos, sigla) is present."""
    import aegean  # noqa: F401  (importing registers the built-in loaders)
    from aegean.core.corpus import _LOADERS

    return sorted(_LOADERS)


def _session_corpus_error(spec: str) -> str | None:
    """``None`` when ``spec`` can serve as the session corpus, else a one-line error.

    Mirrors the precedence of :func:`aegean.core.resolve.read_corpus` (registered id,
    case-forgiven id, Greek work id, .json/.db file) WITHOUT loading anything, so
    ``use damos`` never triggers a network fetch just to validate the name; the
    did-you-mean comes from the same :func:`aegean.core.resolve.suggest` every layer
    uses. Stdin/inline JSON is rejected: a session default must be re-loadable on
    every subsequent line."""
    if spec == "-" or spec.lstrip().startswith("{"):
        return (
            "the session corpus must be re-loadable: a registered id, a Greek work id, "
            "or a .json/.db file (not stdin JSON)"
        )
    ids = _registered_ids()
    if spec in ids or spec.casefold() in {i.casefold() for i in ids}:
        return None
    from aegean.core.resolve import _WORK_ID_RE

    if _WORK_ID_RE.match(spec):
        return None
    path = Path(spec)
    if path.suffix.lower() in (".json", ".db", ".sqlite", ".sqlite3"):
        return None if path.exists() else f"no such corpus file: {path}"
    from aegean.core.resolve import suggest

    close = suggest(spec, ids, n=2)
    did = f" — did you mean {' or '.join(repr(m) for m in close)}? " if close else "; "
    return (
        f"unknown corpus {spec!r}{did}expected a registered id ({', '.join(ids)}), "
        "a Greek work id like tlg0012.tlg001, or a path to a .json or .db corpus"
    )


def _looks_like_corpus(token: str) -> bool:
    """Whether ``token`` has one of ``read_corpus``'s corpus shapes: a registered id
    (case forgiven), a Greek work id, stdin/inline JSON, or a .json/.db/.sqlite
    extension. Purely syntactic — nothing is loaded and existence is not checked,
    because a user who typed ``show missing.json HT13`` meant a corpus either way."""
    if token == "-" or token.lstrip().startswith("{"):
        return True
    ids = _registered_ids()
    if token in ids or token.casefold() in {i.casefold() for i in ids}:
        return True
    from aegean.core.resolve import _WORK_ID_RE

    if _WORK_ID_RE.match(token):
        return True
    return Path(token).suffix.lower() in (".json", ".db", ".sqlite", ".sqlite3")


def _with_session_corpus(args: list[str], corpus: str | None) -> list[str]:
    """Inject the ``use`` session corpus into a corpus-first command line.

    Only the command paths in ``_CORPUS_FIRST`` are rewritten, and only when the
    token in the corpus position is absent, an option, or not corpus-shaped (so
    ``show linearb HT13`` keeps its explicit corpus). Deliberately a first-token
    rule: options written BEFORE an explicit corpus (``stats --top 5 linearb``)
    are not detected, and such a line fails with Click's extra-argument usage
    error rather than silently reading the wrong corpus."""
    if corpus is None or not args:
        return args
    if len(args) >= 2 and (args[0], args[1]) in _CORPUS_FIRST:
        pos = 2
    elif (args[0],) in _CORPUS_FIRST:
        pos = 1
    else:
        return args
    nxt = args[pos] if pos < len(args) else None
    if nxt is not None and not nxt.startswith("-") and _looks_like_corpus(nxt):
        return args  # the line names its own corpus; the session default stays out
    return args[:pos] + [corpus] + args[pos:]


def _history_path() -> Path:
    """Where the shell history persists: ``$XDG_CONFIG_HOME/pyaegean/repl_history``,
    defaulting to ``~/.config/pyaegean/repl_history`` — the config-side sibling of
    the data store's :func:`aegean.data.cache_dir` convention (kept out of the store
    itself so ``aegean data store`` lists downloads only)."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "pyaegean" / "repl_history"


def _history() -> Any:
    """A prompt_toolkit history that persists across sessions (all platforms,
    Windows included: prompt_toolkit ships with the ``[cli]`` extra, no readline
    needed). Falls back to an in-memory history when the file cannot be created
    (a read-only home), so the shell always starts."""
    from prompt_toolkit.history import FileHistory, InMemoryHistory

    try:
        path = _history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)  # verify writability now, not at the first append
        return FileHistory(str(path))
    except OSError:
        return InMemoryHistory()


def _interactive_loop(group: click.Group, session: _Session) -> None:  # pragma: no cover - TTY
    try:
        from prompt_toolkit import PromptSession
    except ModuleNotFoundError:
        print(
            "aegean repl needs prompt_toolkit — pip install 'pyaegean[cli]'",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    prompt_session: Any = PromptSession(
        history=_history(), completer=_make_completer(cast(Any, group))
    )
    print(_BANNER, file=sys.stderr)
    _print_menu(group)  # show the command map on entry, like bare `aegean`
    while True:
        try:
            line = prompt_session.prompt("aegean> ")
        except KeyboardInterrupt:  # Ctrl-C clears the current line
            continue
        except EOFError:  # Ctrl-D leaves
            break
        if not _run_line(group, line, session):
            break


def _make_completer(group: Any) -> Any:  # pragma: no cover - needs a TTY
    """A prompt_toolkit completer that walks the command tree: it completes command
    names at the current level, descends into sub-groups, and offers a command's
    option flags once the word starts with ``-``."""
    from prompt_toolkit.completion import Completer, Completion

    class _AegeanCompleter(Completer):  # type: ignore[misc]
        def get_completions(self, document: Any, complete_event: Any) -> Any:
            text = document.text_before_cursor
            try:
                tokens = shlex.split(text)
            except ValueError:
                return
            word = "" if text[-1:].isspace() else (tokens.pop() if tokens else "")

            cmd: Any = group
            ctx = typer.Context(group, info_name="aegean")
            for tok in tokens:  # descend through sub-groups; stop at the first leaf/arg
                if not _is_group(cmd):
                    break  # a leaf command — the remaining tokens are its args/options
                sub = cmd.get_command(ctx, tok)
                if sub is None:
                    break  # not a known subcommand here (a positional arg or a typo)
                cmd = sub

            if word.startswith("-"):
                seen = set()
                for param in getattr(cmd, "params", []):
                    for opt in getattr(param, "opts", []):
                        if opt.startswith("-") and opt.startswith(word) and opt not in seen:
                            seen.add(opt)
                            yield Completion(opt, start_position=-len(word))
            elif _is_group(cmd):
                for name in cmd.list_commands(ctx):
                    if name.startswith(word):
                        sub = cmd.get_command(ctx, name)
                        meta = (getattr(sub, "help", "") or "").strip().splitlines()
                        yield Completion(
                            name,
                            start_position=-len(word),
                            display_meta=meta[0] if meta else "",
                        )

    return _AegeanCompleter()
