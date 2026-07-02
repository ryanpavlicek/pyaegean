"""``aegean quickstart``: a guided first five minutes that runs real commands live.

Eight short steps, all offline, all on the bundled data (no keys, nothing to
download): a Linear A tour (info, one tablet, its accounting arithmetic, a
sign-pattern search), the Greek pipeline and a hexameter scansion, the
fetchable-dataset list, and pointers for where to go next. Each step prints one
dim line of context, the command as you would type it, then the command's real
output. ``--no-run`` prints the tour script without executing anything.

The outputs are real, not transcripts: every step re-enters the CLI through the
root Click group of the running app (``ctx.find_root().command.main(...,
standalone_mode=False)``, the same re-entry ``aegean repl`` uses for each shell
line), with stdout captured, so a step's output is byte-for-byte what the
command prints when its output is piped (``aegean show lineara HT13 | more``).
The one long table (``data list``) is cut to its first rows, with a dim note
saying how many rows were left out.

Click is reached through Typer (the command's ``typer.Context``), never by
importing the standalone ``click`` package: typer >= 0.26 vendors its own
Click, so the standalone package may not be installed.
"""

from __future__ import annotations

import contextlib
import io
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import typer

from ._common import console, fail

if TYPE_CHECKING:  # type hints only; at runtime Click is reached via typer, not imported
    import click

__all__ = ["STEPS", "quickstart", "register"]


def register(app: typer.Typer) -> None:
    app.command()(quickstart)


@dataclass(frozen=True)
class Step:
    """One tour step: a line of context, the command to run (``None`` marks the
    closing pointers step, which runs nothing), and an optional cap on how many
    table rows of its output to show."""

    say: str
    args: tuple[str, ...] | None = None
    max_rows: int | None = None


_ILIAD_1_1 = "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"

STEPS: tuple[Step, ...] = (
    Step(
        "Corpora ship in the box. Meet Linear A: size, source, license, citation.",
        ("info", "lineara"),
    ),
    Step(
        "Read one tablet: HT 13, a commodity list from Haghia Triada.",
        ("show", "lineara", "HT13"),
    ),
    Step(
        "Audit its arithmetic: the stated KU-RO total vs the summed entries.",
        ("balance", "lineara", "ht13"),
    ),
    Step(
        "Search words by sign pattern: * stands for exactly one sign.",
        ("search", "lineara", "KU-*-RO"),
    ),
    Step(
        "Greek NLP, offline: per-token analysis of the Iliad's opening words.",
        ("greek", "pipeline", "μῆνιν ἄειδε θεὰ"),
    ),
    Step(
        "Scan the full first line of the Iliad as a dactylic hexameter.",
        ("greek", "scan", _ILIAD_1_1),
    ),
    Step(
        "Bigger corpora and neural models fetch on demand into a local store.",
        ("data", "list"),
        max_rows=4,
    ),
    Step("Where next:"),
)

_POINTERS: tuple[tuple[str, str], ...] = (
    ("aegean repl", "every command, interactive, with completion"),
    ("aegean doctor", "check the install and cached data"),
    ("aegean --install-completion", "tab-completion for your shell"),
    ("docs:", "https://github.com/ryanpavlicek/pyaegean/wiki"),
)


def quickstart(
    ctx: typer.Context,
    no_run: bool = typer.Option(
        False, "--no-run", help="Print the tour script without executing the commands."
    ),
) -> None:
    """A guided first five minutes: eight short steps, each running a real command
    live on the bundled data (offline, no keys, nothing to download).

    Every step prints one line of context, the command as you would type it, and
    the command's real output; --no-run prints the script without executing it.
    """
    con = console()
    total = len(STEPS)
    started = time.perf_counter()
    ran = 0
    con.print(
        "aegean quickstart --no-run: the tour script (nothing is executed)."
        if no_run
        else "aegean quickstart: the first five minutes, live on bundled data, all offline.",
        style="bold",
        markup=False,
    )
    group = cast("click.Group", ctx.find_root().command)  # the top-level aegean group
    for i, step in enumerate(STEPS, start=1):
        con.print()
        con.print(f"[{i}/{total}] {step.say}", style="dim", markup=False)
        if step.args is None:
            _pointers(con)
            continue
        shown = _cmdline(step.args)
        con.print(f"$ {shown}", style="bold", markup=False)
        if no_run:
            continue
        code, out = _run_step(group, step.args)
        elided = 0
        if step.max_rows is not None:
            out, elided = _first_rows(out, step.max_rows)
        if out:
            sys.stdout.write(out if out.endswith("\n") else out + "\n")
        if elided:
            con.print(
                f"… {elided} more rows: `{shown}` prints the full table",
                style="dim",
                markup=False,
            )
        if code != 0:
            raise fail(f"the tour stopped at step {i}/{total}: `{shown}` exited {code}")
        ran += 1
    con.print()
    if no_run:
        con.print("drop --no-run to run these commands live", style="dim", markup=False)
    else:
        con.print(
            f"That was {ran} real commands in {time.perf_counter() - started:.1f}s, "
            "all offline, all bundled data.",
            style="dim",
            markup=False,
        )


def _cmdline(args: tuple[str, ...]) -> str:
    """The command as you would type it: double quotes around any argument a
    shell would mangle (spaces or the * wildcard)."""
    shown = ["aegean"]
    for a in args:
        shown.append(f'"{a}"' if (" " in a or "*" in a) else a)
    return " ".join(shown)


def _run_step(group: click.Group, args: tuple[str, ...]) -> tuple[int, str]:
    """Run one step through the root Click group, non-standalone (the repl's
    re-entry), with stdout captured. Returns (exit code, captured output).

    Depending on the Click inside typer, a non-standalone ``main`` either
    returns an ``Exit``'s code or re-raises it, so both shapes are handled."""
    buf = io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(buf):
            rv = group.main(args=list(args), prog_name="aegean", standalone_mode=False)
        if isinstance(rv, int):
            code = rv
    except typer.Exit as exc:
        code = int(exc.exit_code)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except Exception as exc:  # a step must surface one line, never a traceback
        # Click's own errors render themselves via .show(); anything else gets one
        # line. Duck-typed so it holds whether typer uses standalone or vendored Click.
        show = getattr(exc, "show", None)
        if callable(show):
            show()
        else:
            print(f"aegean: {exc}", file=sys.stderr)
        code = int(getattr(exc, "exit_code", 1))
    return code, buf.getvalue()


# A box border/rule line is drawn entirely from Unicode box-drawing glyphs
# (U+2500-257F) or the ASCII fallbacks, never letters. A body-row line opens
# with a vertical bar. Matching the character *class* rather than one glyph
# keeps the trim working across rich's box styles: the default heavy-head box
# separates the header with ``┡...┩`` where the light box uses ``├...┤``, and
# a terminal that can't render either falls back to ``+---+`` / ``|``.
_VBAR = "│┃|"
_BOXCHARS = frozenset("│┃|+=") | frozenset(chr(c) for c in range(0x2500, 0x2580))


def _is_rule(ln: str) -> bool:
    """A horizontal border/separator line: box-drawing only, at least one dash."""
    s = ln.strip()
    return bool(s) and all(ch in _BOXCHARS or ch == " " for ch in s) and s[0] not in _VBAR


def _first_rows(rendered: str, max_rows: int) -> tuple[str, int]:
    """Cut a rich table to its first ``max_rows`` body rows, keeping the bottom
    border (and anything after it), and return (trimmed text, elided row count).

    Box-agnostic: the header separator is the second rule line (after the top
    border) and the footer is the last rule line, whatever glyphs the active box
    style uses. A body row opens with a vertical bar and has content in its first
    cell; wrapped continuation lines have a blank first column and stay with
    their row. Text that does not look like a boxed table passes through
    untouched."""
    lines = rendered.splitlines()
    rules = [i for i, ln in enumerate(lines) if _is_rule(ln)]
    if len(rules) < 2:  # need at least a header separator and a bottom border
        return rendered, 0
    head, foot = rules[1], rules[-1]
    if foot <= head:
        return rendered, 0
    starts = [
        i
        for i in range(head + 1, foot)
        if lines[i][:1] in _VBAR and len(lines[i]) > 2 and lines[i][2] != " "
    ]
    if len(starts) <= max_rows:
        return rendered, 0
    kept = lines[: starts[max_rows]] + lines[foot:]
    return "\n".join(kept) + "\n", len(starts) - max_rows


def _pointers(con: Any) -> None:
    """The closing step: where to go after the tour (bold command, dim purpose)."""
    from rich.text import Text

    pad = max(len(cmd) for cmd, _ in _POINTERS) + 3
    for cmd, desc in _POINTERS:
        con.print(Text("  " + cmd.ljust(pad), style="bold") + Text(desc, style="dim"))
