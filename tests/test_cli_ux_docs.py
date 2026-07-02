"""Documentation-parity guards for the CLI surface.

Two behavior-level tests that keep the published claims true:

1. **Group-help-map parity**: for the root app and every command group
   (greek/analyze/data/db/ai), every registered, non-hidden command name is
   visible in that group's rendered ``--help``. Rendered wide (COLUMNS=200) so
   rich cannot wrap mid-token; the assertion compares command *lists*, never
   option strings, so an 80-col CI wrap cannot produce a false failure. A new
   command that is registered but somehow invisible in help fails here.

2. **The top-level --json claim**: the root help promises ``--json`` on every
   *data-producing* command. The test walks the whole command tree and pins the
   exact set of commands without ``--json`` to the known non-data-producing
   exceptions (file/image/database writers, the plain text transforms, and the
   interactive/server commands), in both directions: a data command that loses
   ``--json`` fails, and an exception that gains it must be consciously removed
   from the list.
"""

from __future__ import annotations

from typing import Any, Iterator

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean.cli import _build_app  # noqa: E402

runner = CliRunner()


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


@pytest.fixture(scope="module")
def root(app):  # type: ignore[no-untyped-def]
    return typer.main.get_command(app)


def _subcommands(cmd: Any) -> dict[str, Any] | None:
    """The click subcommand mapping of a group, or None for a leaf command.

    Duck-typed (click 8.4 merged the Group/Command hierarchy under typer's
    shim, so isinstance(click.Group) is unreliable).
    """
    return getattr(cmd, "commands", None) or None


def _walk_leaves(cmd: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    subs = _subcommands(cmd)
    if subs:
        for name, sub in subs.items():
            yield from _walk_leaves(sub, path + (name,))
    else:
        yield path, cmd


def _groups(root: Any) -> dict[tuple[str, ...], Any]:
    """Every group in the tree as {invocation path tuple: click group}."""
    found: dict[tuple[str, ...], Any] = {(): root}
    for name, sub in (_subcommands(root) or {}).items():
        if _subcommands(sub):
            found[(name,)] = sub
    return found


# ── 1. group-help-map parity ─────────────────────────────────────────────────
def test_every_group_help_lists_every_registered_command(app, root) -> None:  # type: ignore[no-untyped-def]
    groups = _groups(root)
    # the documented group set: a new group must be picked up automatically,
    # and the known five plus the root must all be present
    assert {p for p in groups if p} >= {("greek",), ("analyze",), ("data",), ("db",), ("ai",)}
    for path, group in groups.items():
        res = runner.invoke(app, [*path, "--help"], env={"COLUMNS": "200"})
        assert res.exit_code == 0, f"{' '.join(path) or 'root'} --help failed"
        visible = [name for name, cmd in (_subcommands(group) or {}).items() if not cmd.hidden]
        assert visible, f"group {' '.join(path) or 'root'} registers no visible commands"
        missing = [name for name in visible if name not in res.output]
        assert not missing, (
            f"`aegean {' '.join(path)} --help` does not show its registered "
            f"command(s) {missing}"
        )


def test_group_one_liners_in_root_help_name_every_group(app, root) -> None:  # type: ignore[no-untyped-def]
    """The root command map must show each group row (the group name itself)."""
    res = runner.invoke(app, ["--help"], env={"COLUMNS": "200"})
    assert res.exit_code == 0
    for path in _groups(root):
        if path:
            assert path[0] in res.output


# ── 2. the top-level --json claim ────────────────────────────────────────────
# Commands that legitimately have no --json, by reason:
#   file/DB/image writers whose output IS the file .... export, plot, db build,
#                                                       db add, data fetch
#   plain text transforms (stdout is the datum) ....... greek normalize,
#                                                       greek betacode,
#                                                       greek strip, greek ipa
#   interactive / long-running server ................. repl, workbench
_NON_DATA_PRODUCING = {
    ("export",),
    ("plot",),
    ("repl",),
    ("workbench",),
    ("data", "fetch"),
    ("db", "build"),
    ("db", "add"),
    ("greek", "normalize"),
    ("greek", "betacode"),
    ("greek", "strip"),
    ("greek", "ipa"),
}


def _has_json(cmd: Any) -> bool:
    return any("--json" in p.opts for p in cmd.params)


def test_root_help_json_claim_matches_the_actual_surface(root) -> None:  # type: ignore[no-untyped-def]
    # the promise, as worded in cli/__init__.py
    assert "data-producing command takes --json" in (root.help or "")
    # and the behavior: the commands lacking --json are exactly the known
    # non-data-producing set (both directions, so neither can drift silently)
    without_json = {path for path, cmd in _walk_leaves(root) if not _has_json(cmd)}
    assert without_json == _NON_DATA_PRODUCING, (
        "the '--json on every data-producing command' claim drifted: "
        f"newly missing --json: {sorted(without_json - _NON_DATA_PRODUCING)}; "
        f"gained --json (remove from the exception list): "
        f"{sorted(_NON_DATA_PRODUCING - without_json)}"
    )


def test_every_data_producing_command_emits_parseable_json_for_a_sample(app) -> None:  # type: ignore[no-untyped-def]
    """Spot-verify the claim end to end on one command per group (offline)."""
    import json

    for argv in (
        ["info", "lineara", "--json"],
        ["greek", "syllabify", "εἰσφέρω", "--json"],
        ["analyze", "distance", "KU-RO", "KI-RO", "--json"],
        ["data", "list", "--json"],
    ):
        res = runner.invoke(app, argv)
        assert res.exit_code == 0, f"{argv} exited {res.exit_code}"
        try:
            text = res.stdout  # this click separates stdout from stderr
        except (ValueError, AttributeError):
            text = res.output
        payload = json.loads(text)
        assert payload, f"{argv} emitted empty JSON"
