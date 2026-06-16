"""``aegean repl`` — an interactive shell over the whole command tree.

Drops the ``aegean`` prefix: inside the shell you type subcommands directly
(``stats lineara --top 5``, ``greek catalog plato``, ``ai translate …``) with
Tab-completion of commands and options and a recallable history. Each line is
dispatched through the same Typer/Click app the ``aegean`` command uses, so every
subcommand behaves identically. The interactive line editing is provided by
``prompt_toolkit`` (ships with the ``[cli]`` extra); when standard input is not a
terminal (a pipe or a test harness) commands are read line-by-line instead, so
the shell is scriptable too.
"""

from __future__ import annotations

import shlex
import sys
from typing import Any

import click
import typer

_EXIT_WORDS = {":exit", ":quit", ":q", "exit", "quit"}
_HELP_WORDS = {":help", "help", "?"}


def register(app: typer.Typer) -> None:
    app.command()(repl)


def repl(ctx: typer.Context) -> None:
    """Start an interactive shell — run commands without the ``aegean`` prefix.

    Type subcommands directly (``stats lineara --top 5``, ``greek catalog plato``)
    with Tab-completion and history. ``:help`` shows the command list; ``:exit``,
    ``quit``, or Ctrl-D leaves the shell.
    """
    group = ctx.find_root().command  # the top-level aegean group
    assert isinstance(group, click.Group)  # the root command is always the group
    if sys.stdin.isatty():
        _interactive_loop(group)
    else:
        for raw in sys.stdin:  # scriptable / testable path: one command per line
            if not _run_line(group, raw):
                break


def _run_line(group: click.Group, line: str) -> bool:
    """Execute one REPL line against the group. Return ``False`` to stop the loop."""
    line = line.strip()
    if not line:
        return True
    if line in _EXIT_WORDS:
        return False
    if line in _HELP_WORDS:
        args = ["--help"]
    else:
        try:
            args = shlex.split(line)
        except ValueError as exc:  # unbalanced quotes etc.
            print(f"aegean: {exc}", file=sys.stderr)
            return True
    if args and args[0] == "repl":  # don't nest the shell into itself
        print("aegean: already in the interactive shell.", file=sys.stderr)
        return True
    try:
        # Re-enter the CLI as if freshly invoked; non-standalone so errors raise
        # instead of killing the process, keeping the shell alive line to line.
        group.main(args=args, prog_name="aegean", standalone_mode=False)
    except SystemExit:
        pass  # e.g. --help calls ctx.exit(); not a reason to leave the shell
    except click.ClickException as exc:
        exc.show()
    except click.exceptions.Abort:
        print("aborted.", file=sys.stderr)
    except Exception as exc:  # a command blowing up must not end the session
        print(f"aegean: {exc}", file=sys.stderr)
    return True


def _interactive_loop(group: click.Group) -> None:  # pragma: no cover - needs a TTY
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import InMemoryHistory
    except ModuleNotFoundError:
        print(
            "aegean repl needs prompt_toolkit — pip install 'pyaegean[cli]'",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    session: Any = PromptSession(
        history=InMemoryHistory(), completer=_make_completer(group)
    )
    print(
        "aegean interactive shell — commands without the 'aegean' prefix.\n"
        "Tab completes, :help lists commands, :exit or Ctrl-D quits.",
        file=sys.stderr,
    )
    while True:
        try:
            line = session.prompt("aegean> ")
        except KeyboardInterrupt:  # Ctrl-C clears the current line
            continue
        except EOFError:  # Ctrl-D leaves
            break
        if not _run_line(group, line):
            break


def _make_completer(group: click.Group) -> Any:  # pragma: no cover - needs a TTY
    """A prompt_toolkit completer that walks the Click command tree: it completes
    command names at the current level, descends into sub-groups, and offers a
    command's option flags once the word starts with ``-``."""
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
            ctx = click.Context(group, info_name="aegean")
            for tok in tokens:  # descend through any sub-groups already typed
                if not isinstance(cmd, click.Group):
                    return
                cmd = cmd.get_command(ctx, tok)
                if cmd is None:
                    return

            if word.startswith("-"):
                seen = set()
                for param in getattr(cmd, "params", []):
                    for opt in getattr(param, "opts", []):
                        if opt.startswith("-") and opt.startswith(word) and opt not in seen:
                            seen.add(opt)
                            yield Completion(opt, start_position=-len(word))
            elif isinstance(cmd, click.Group):
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
