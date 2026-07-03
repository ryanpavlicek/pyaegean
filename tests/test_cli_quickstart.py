"""``aegean quickstart``: the guided tour runs its steps live and offline with the
real command outputs present (the HT13 tablet's KU-RO line, the Iliad 1.1 DDSDDS
scansion pattern), step output is byte-identical to invoking the command
directly, ``--no-run`` prints the script without executing anything, the long
``data list`` table is cut to its first rows, and the step list stays pinned."""

from __future__ import annotations

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean.cli import _quickstart  # noqa: E402
from aegean.cli._quickstart import STEPS, _first_rows  # noqa: E402

runner = CliRunner()

# Iliad 1.1 scans dactyl-dactyl-spondee-dactyl-dactyl (DDSDDS): the real
# `aegean greek scan` pattern line the tour must reproduce.
DDSDDS = "—⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×"


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    from aegean.cli import _build_app

    a = _build_app()  # quickstart is registered in _build_app
    return a


@pytest.fixture(scope="module")
def tour(app):  # type: ignore[no-untyped-def]
    """One full live run, shared by the output-verifying tests."""
    return runner.invoke(app, ["quickstart"])


def _slice(out: str, step: int) -> str:
    """The output between this step's banner and the next one's."""
    part = out.split(f"[{step}/{len(STEPS)}]")[1]
    if step < len(STEPS):
        part = part.split(f"[{step + 1}/{len(STEPS)}]")[0]
    return part


# ── the live tour: exit 0, offline, the known outputs really appear ─────────
def test_tour_runs_exit_zero(tour) -> None:  # type: ignore[no-untyped-def]
    assert tour.exit_code == 0, tour.output


def test_tour_prints_every_step_banner(tour) -> None:  # type: ignore[no-untyped-def]
    for i in range(1, len(STEPS) + 1):
        assert f"[{i}/{len(STEPS)}]" in tour.output


def test_show_step_has_the_real_ht13_tablet(tour) -> None:  # type: ignore[no-untyped-def]
    part = _slice(tour.output, 2)
    assert "$ aegean show lineara HT13" in part
    assert "KU-RO" in part  # the tablet's own total line, from the real command
    assert "Haghia Triada" in part


def test_balance_step_reconciles_the_ku_ro_total(tour) -> None:  # type: ignore[no-untyped-def]
    part = _slice(tour.output, 3)
    assert "KU-RO" in part  # the marker column of the real balance table
    assert "stated" in part and "computed" in part


def test_search_step_finds_pattern_matches(tour) -> None:  # type: ignore[no-untyped-def]
    part = _slice(tour.output, 4)
    assert '$ aegean search lineara "KU-*-RO"' in part
    assert "word(s)" in part  # the real results table title


def test_pipeline_step_lemmatizes_the_iliad_opening(tour) -> None:  # type: ignore[no-untyped-def]
    part = _slice(tour.output, 5)
    assert "μῆνιν" in part and "μῆνις" in part  # token and its lemma, per-token record


def test_scan_step_shows_the_ddsdds_hexameter(tour) -> None:  # type: ignore[no-untyped-def]
    part = _slice(tour.output, 6)
    assert DDSDDS in part
    assert "hexameter" in part


def test_data_step_is_cut_to_first_rows(tour) -> None:  # type: ignore[no-untyped-def]
    part = _slice(tour.output, 7)
    assert "fetchable datasets" in part
    assert "abbott-smith" in part  # the first row (alphabetical) is shown
    assert "workbench-app" not in part  # the last row is elided
    assert "more rows" in part and "aegean data list" in part  # the honest cut note


def test_closing_step_names_the_pointers(tour) -> None:  # type: ignore[no-untyped-def]
    part = _slice(tour.output, 8)
    assert "aegean repl" in part
    assert "aegean doctor" in part
    assert "--install-completion" in part
    assert "https://github.com/ryanpavlicek/pyaegean/wiki" in part


def test_step_output_is_byte_identical_to_a_direct_invocation(app, tour) -> None:  # type: ignore[no-untyped-def]
    """The tour never fakes output: a step's block is exactly what the command
    prints when invoked directly (same app, same capture)."""
    for args in (["show", "lineara", "HT13"], ["greek", "scan", _quickstart._ILIAD_1_1]):
        direct = runner.invoke(app, args)
        assert direct.exit_code == 0, direct.output
        assert direct.stdout in tour.stdout


# ── --no-run: the script prints, nothing executes ────────────────────────────
def test_no_run_prints_the_script_without_executing(app) -> None:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["quickstart", "--no-run"])
    assert res.exit_code == 0, res.output
    out = res.output
    # every step banner and every command line, as typed
    for i in range(1, len(STEPS) + 1):
        assert f"[{i}/{len(STEPS)}]" in out
    assert "$ aegean info lineara" in out
    assert "$ aegean show lineara HT13" in out
    assert "$ aegean balance lineara ht13" in out
    assert '$ aegean search lineara "KU-*-RO"' in out
    assert '$ aegean greek pipeline "μῆνιν ἄειδε θεὰ"' in out
    assert "$ aegean data list" in out
    # ... but no command ran: no tables, no tablet content, no scansion, no datasets
    assert "│" not in out and "└" not in out
    assert "KU-MA-RO" not in out
    assert "μῆνις" not in out
    assert "⏑" not in out
    assert "fetchable datasets" not in out
    # the closing pointers are script, not execution: still shown
    assert "aegean doctor" in out
    assert "https://github.com/ryanpavlicek/pyaegean/wiki" in out
    assert "drop --no-run" in out


# ── the step list is pinned ──────────────────────────────────────────────────
def test_step_list_is_pinned() -> None:
    assert [s.args for s in STEPS] == [
        ("info", "lineara"),
        ("show", "lineara", "HT13"),
        ("balance", "lineara", "ht13"),
        ("search", "lineara", "KU-*-RO"),
        ("greek", "pipeline", "μῆνιν ἄειδε θεὰ"),
        ("greek", "scan", "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"),
        ("data", "list"),
        None,
    ]
    assert len(STEPS) == 8
    assert sum(1 for s in STEPS if s.args is not None) == 7
    # only the data list step is row-capped
    assert [s.max_rows for s in STEPS if s.max_rows is not None] == [4]


# ── _first_rows: known-answer trim of a boxed table ──────────────────────────
SYNTHETIC_TABLE = (
    "  title\n"
    "┌────┬────┐\n"
    "│ a  │ b  │\n"
    "├────┼────┤\n"
    "│ r1 │ x  │\n"
    "│    │ y  │\n"  # wrapped continuation: stays with r1, not a new row
    "│ r2 │ z  │\n"
    "│ r3 │ w  │\n"
    "└────┴────┘\n"
)


def test_first_rows_trims_and_counts() -> None:
    trimmed, elided = _first_rows(SYNTHETIC_TABLE, 2)
    assert elided == 1
    assert "r1" in trimmed and "y" in trimmed and "r2" in trimmed  # kept rows intact
    assert "r3" not in trimmed  # the third row is gone
    assert trimmed.endswith("└────┴────┘\n")  # the box is closed by the real border


def test_first_rows_leaves_short_tables_and_plain_text_alone() -> None:
    assert _first_rows(SYNTHETIC_TABLE, 3) == (SYNTHETIC_TABLE, 0)
    assert _first_rows("no table here\n", 2) == ("no table here\n", 0)


@pytest.mark.parametrize("safe_box", [True, False])
def test_first_rows_trims_across_box_styles(safe_box) -> None:
    # rich's default heavy-head box separates the header with ┡━┩ while the
    # light/safe box uses ├─┤; the row trim must work for both (a terminal that
    # renders heavy-head made a full untrimmed table leak in CI once).
    import io

    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    from aegean.cli._quickstart import _first_rows

    buf = io.StringIO()
    con = Console(file=buf, width=100, safe_box=safe_box)
    t = Table(title="datasets")
    for col in ("name", "note"):
        t.add_column(col)
    for i in range(12):
        t.add_row(Text(f"row-{i:02d}"), Text("a note that may wrap at narrow widths " * 2))
    con.print(t)
    trimmed, elided = _first_rows(buf.getvalue(), 4)
    assert elided == 8  # 12 rows, first 4 kept
    assert "row-00" in trimmed and "row-03" in trimmed
    assert "row-04" not in trimmed and "row-11" not in trimmed
