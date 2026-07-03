"""Grand-total reconciliation, the negative-value glyph, and the third-surface
(MCP) accounting parity.

Four fixes pinned by known-answer / parity assertions:

1. **PO-TO-KU-RO reconciles against the KU-RO subtotals, not an empty section.**
   ``check_balances`` used to keep a single running-items list and reset it at
   *both* KU-RO totals and PO-TO-KU-RO grand totals, so a grand total that
   followed subtotals summed an already-emptied list and reported
   ``computed_sum = 0``. It now carries a separate list of the stated subtotals
   and sums those (plus any trailing un-subtotalled items) for the grand total,
   mirroring the workbench. HT122b's grand total reconciles to 65 (its one KU-RO
   subtotal), not 0.
2. **format_value keeps the sign of a negative value** (a discrepancy rendered
   for a reader): -1.5 renders "-1½", not the positive "½".
3. **The MCP balance tool routes through aegean._view**, so the MCP surface, the
   CLI, and the TUI emit the identical row for every total (the grand-total fix
   included).
4. **data_status guards a broken/racing store entry** so it returns a clean
   result rather than raising on a dangling path.

The deliberate leading-item-less-total convention (ARKH2's KU-RA, every stated
total yields a check) is preserved and re-pinned here.
"""

from __future__ import annotations

import pytest

import aegean
from aegean import mcp_server as m
from aegean._view import balance_rows
from aegean.analysis import balance_check
from aegean.core.model import Document
from aegean.core.numerals import (
    check_balances,
    format_value,
    parse_account_lines,
)
from aegean.scripts.lineara.loader import classify


@pytest.fixture(scope="module")
def corpus():  # type: ignore[no-untyped-def]
    return aegean.load("lineara")


def _doc(raw_lines: list[list[str]]) -> Document:
    tokens = []
    lines = []
    pos = 0
    for li, line in enumerate(raw_lines):
        idx = []
        for w in line:
            tokens.append(classify(w, li, pos))
            idx.append(pos)
            pos += 1
        lines.append(idx)
    return Document(id="X", script_id="lineara", tokens=tokens, lines=lines)


# ── 1. the grand-total reconciliation bug ────────────────────────────────────


def test_ht122b_grand_total_sums_the_kuro_subtotal(corpus) -> None:  # type: ignore[no-untyped-def]
    """HT122b: five items (7,2,2,2,2), then ``KU-RO 65``, then ``PO-TO-KU-RO 97``.

    The grand total reconciles against the stated KU-RO subtotal (65), so
    computed_sum = 65 over one subtotal, difference = 65 - 97 = -32. The bug reset
    the running list at the KU-RO line and left the grand total summing nothing
    (computed_sum 0, difference -97)."""
    checks = balance_check(corpus.get("HT122b"))
    assert len(checks) == 2

    kuro, grand = checks
    assert kuro.marker == "KU-RO"
    assert kuro.stated_total == 65
    assert kuro.computed_sum == 15  # the five raw items 7+2+2+2+2
    assert kuro.item_count == 5

    assert grand.marker == "PO-TO-KU-RO"
    assert grand.stated_total == 97
    assert grand.computed_sum == 65  # the one KU-RO subtotal, NOT 0
    assert grand.item_count == 1
    assert grand.difference == -32
    assert not grand.balances


def test_ht131b_grand_total_without_a_subtotal_sums_trailing_items(corpus) -> None:  # type: ignore[no-untyped-def]
    """HT131b has a ``PO-TO-KU-RO 451½`` but no KU-RO subtotal, so the grand total
    reconciles against the two trailing items (30 + 2 = 32) directly. This path
    was already correct and must stay so after the fix."""
    (grand,) = balance_check(corpus.get("HT131b"))
    assert grand.marker == "PO-TO-KU-RO"
    assert grand.stated_total == pytest.approx(451.5)
    assert grand.computed_sum == 32
    assert grand.item_count == 2
    assert grand.difference == pytest.approx(-419.5)


def test_synthetic_grand_total_sums_two_subtotals() -> None:
    """A two-section tablet: [GRA 4][KU-RO 4][VIN 9][KU-RO 9][PO-TO-KU-RO 13].

    The grand total sums the two stated subtotals (4 + 9 = 13) and balances; the
    raw items are not double-counted."""
    checks = check_balances(
        parse_account_lines(
            [
                ["GRA", "4"],
                ["KU-RO", "4"],
                ["VIN", "9"],
                ["KU-RO", "9"],
                ["PO-TO-KU-RO", "13"],
            ]
        )
    )
    assert [c.marker for c in checks] == ["KU-RO", "KU-RO", "PO-TO-KU-RO"]
    grand = checks[-1]
    assert grand.computed_sum == 13
    assert grand.item_count == 2  # two subtotals, not the two raw items
    assert grand.difference == 0
    assert grand.balances


def test_grand_total_mixes_subtotal_and_trailing_items() -> None:
    """[GRA 4][KU-RO 4][VIN 9][PO-TO-KU-RO 13]: one closed subtotal (4) plus one
    trailing item (9) never given its own KU-RO. The grand total sums both."""
    checks = check_balances(
        parse_account_lines(
            [["GRA", "4"], ["KU-RO", "4"], ["VIN", "9"], ["PO-TO-KU-RO", "13"]]
        )
    )
    grand = checks[-1]
    assert grand.marker == "PO-TO-KU-RO"
    assert grand.computed_sum == 13  # subtotal 4 + trailing item 9
    assert grand.item_count == 2
    assert grand.balances


def test_leading_grand_total_yields_zero_item_check() -> None:
    """A grand total with nothing before it reports a zero-item section (the same
    every-stated-total-is-a-check convention KU-RO/KU-RA follow), not a crash."""
    (grand,) = check_balances(parse_account_lines([["PO-TO-KU-RO", "50"]]))
    assert grand.computed_sum == 0
    assert grand.item_count == 0
    assert grand.difference == -50
    assert not grand.balances


# ── the preserved leading-item-less-total convention (must not regress) ───────


def test_arkh2_leading_kura_still_reports_zero_item_section(corpus) -> None:  # type: ignore[no-untyped-def]
    """ARKH2's KU-RA heads its list; the deliberate convention (every stated total
    yields a check, so a leading total is a zero-item section) is preserved by the
    grand-total fix, which must not import the workbench's drop-empty-total rule."""
    (check,) = balance_check(corpus.get("ARKH2"))
    assert check.marker == "KU-RA"
    assert check.stated_total == 5
    assert check.item_count == 0
    assert check.computed_sum == 0
    assert not check.balances


def test_corpus_wide_grand_total_markers_unchanged(corpus) -> None:  # type: ignore[no-untyped-def]
    """The grand-total fix changes HT122b's computed sum but flips no balance and
    adds/removes no check: exactly the two PO-TO-KU-RO tablets, both still off."""
    grand = [
        (doc.id, ch)
        for doc in corpus
        for ch in balance_check(doc)
        if ch.marker == "PO-TO-KU-RO"
    ]
    assert sorted(doc_id for doc_id, _ in grand) == ["HT122b", "HT131b"]
    assert all(not ch.balances for _, ch in grand)


# ── 2. format_value keeps a negative sign ────────────────────────────────────


def test_format_value_negative_fraction_keeps_sign() -> None:
    """A negative discrepancy renders with its sign and whole part: math.floor of
    -1.5 is -2, so the naive path both lost the sign and mis-rendered the whole."""
    assert format_value(-0.5) == "-½"
    assert format_value(-1.5) == "-1½"
    assert format_value(-1.75) == "-1¾"
    assert format_value(-2.25) == "-2¼"
    # the unknown-fraction decimal fallback keeps the sign too
    assert format_value(-2.51) == "-2.51"
    # positives and integers are unchanged
    assert format_value(0.5) == "½"
    assert format_value(31.75) == "31¾"
    assert format_value(5) == "5"
    assert format_value(-5) == "-5"


def test_format_value_round_trips_the_common_fractions() -> None:
    """Property: for each recognised fraction f, format_value(±(2+f)) renders the
    whole part 2 with the sign attached (not swallowed by floor)."""
    for frac, glyph in ((0.5, "½"), (0.25, "¼"), (0.75, "¾")):
        assert format_value(2 + frac) == f"2{glyph}"
        assert format_value(-(2 + frac)) == f"-2{glyph}"


# ── 3. the MCP balance tool routes through _view (third-surface parity) ───────


def test_mcp_balance_accounts_equals_view_balance_rows(corpus) -> None:  # type: ignore[no-untyped-def]
    """The MCP balance tool emits exactly aegean._view.balance_rows for HT122b, so
    the grand-total fix reaches the MCP surface identically to the CLI and TUI."""
    doc = corpus.get("HT122b")
    mcp_rows = m.balance_accounts("lineara", "HT122b")
    assert mcp_rows == balance_rows(doc)
    # and the fixed grand-total row is present with the corrected computed sum
    grand = next(r for r in mcp_rows if r["marker"] == "PO-TO-KU-RO")
    assert grand == {
        "doc": "HT122b",
        "marker": "PO-TO-KU-RO",
        "stated": 97.0,
        "computed": 65.0,
        "difference": -32.0,
        "items": 1,
        "balances": False,
    }


def test_mcp_balance_accounts_whole_corpus_flattens_view_rows(corpus) -> None:  # type: ignore[no-untyped-def]
    """Over the whole corpus the MCP rows are the per-document _view rows,
    concatenated in document order."""
    expected = [row for doc in corpus.documents for row in balance_rows(doc)]
    assert m.balance_accounts("lineara") == expected


def test_mcp_greek_pipeline_equals_view_pipeline_rows() -> None:
    """greek_pipeline routes through aegean._view.pipeline_rows, so the MCP,
    CLI, and TUI token rows are identical."""
    from aegean._view import pipeline_rows

    text = "ἐν ἀρχῇ ἦν ὁ λόγος."
    rows = m.greek_pipeline(text)
    assert rows == pipeline_rows(text)
    assert {"text", "upos", "lemma"} <= set(rows[0])
    assert rows[0]["text"] == "ἐν"


# ── 4. data_status guards a broken / racing store entry ───────────────────────


def test_on_disk_bytes_handles_absent_and_present_entries(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """_on_disk_bytes returns None for an absent entry and the true byte count for
    a file and for a directory (recursively)."""
    from aegean.mcp_server import _on_disk_bytes

    assert _on_disk_bytes(tmp_path / "missing") is None

    f = tmp_path / "one.bin"
    f.write_bytes(b"x" * 100)
    assert _on_disk_bytes(f) == 100

    d = tmp_path / "extracted"
    d.mkdir()
    (d / "a").write_bytes(b"x" * 10)
    (d / "b").write_bytes(b"x" * 20)
    assert _on_disk_bytes(d) == 30


def test_on_disk_bytes_returns_none_for_a_dangling_entry(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A store path that raises OSError on stat() (a dangling symlink, a racing
    remove) yields None instead of propagating: data_status stays a clean result."""
    from pathlib import Path

    from aegean.mcp_server import _on_disk_bytes

    dangling = tmp_path / "dangling"

    # simulate a path that exists to is_dir() as a file yet raises on stat()
    real_stat = Path.stat

    def broken_stat(self, *a, **k):  # type: ignore[no-untyped-def]
        if self == dangling:
            raise FileNotFoundError(self)
        return real_stat(self, *a, **k)

    monkeypatch.setattr(Path, "stat", broken_stat)
    assert _on_disk_bytes(dangling) is None


def test_on_disk_bytes_skips_a_file_that_vanishes_mid_walk(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A directory whose file disappears between rglob and stat still totals the
    survivors rather than raising."""
    from pathlib import Path

    from aegean.mcp_server import _on_disk_bytes

    d = tmp_path / "extracted"
    d.mkdir()
    good = d / "good"
    good.write_bytes(b"x" * 42)
    gone = d / "gone"
    gone.write_bytes(b"x" * 999)

    real_stat = Path.stat

    def racing_stat(self, *a, **k):  # type: ignore[no-untyped-def]
        if self.name == "gone":
            raise FileNotFoundError(self)
        return real_stat(self, *a, **k)

    monkeypatch.setattr(Path, "stat", racing_stat)
    assert _on_disk_bytes(d) == 42  # only the survivor counts


def test_data_status_is_a_clean_dict_over_the_real_store() -> None:
    """data_status returns a well-formed payload and never raises, whatever the
    store's on-disk state (the guard's end-to-end effect)."""
    status = m.data_status()
    assert set(status) == {"store", "datasets"}
    assert isinstance(status["datasets"], list) and status["datasets"]
    for row in status["datasets"]:
        assert {"name", "downloaded", "bytes", "size", "note", "license"} <= set(row)
        # bytes is None exactly when not downloaded; a present size is a real count
        if row["downloaded"]:
            assert isinstance(row["bytes"], int) and row["bytes"] >= 0
        else:
            assert row["bytes"] is None and row["size"] == ""
