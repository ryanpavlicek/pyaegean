"""Coverage backfill for three public ``aegean.analysis`` functions that the
existing suite left without a *direct* correctness test:

- ``collocation.pmi_interval`` — untested (no prior reference anywhere in tests).
- ``align.add_sequence``      — only exercised transitively through
  ``align_sequences`` golden cases; the ``prior_n`` gap-padding path is never
  isolated. Tested here directly against hand-traced Needleman-Wunsch output.
- ``accounting.account_lines`` — untested (only the downstream ``balance_check``
  and the unrelated ``core.numerals.parse_account_lines`` were covered).

Every expected value below is hand-derived from the algorithm's definition (the
Wilson-interval closed form, the NW scoring rules, the line->token-text mapping)
or asserted as a true invariant, never copied from the function's own output.
"""

from __future__ import annotations

import math

import pytest

from aegean.analysis.accounting import account_lines
from aegean.analysis.align import add_sequence, align_sequences
from aegean.analysis.collocation import pmi_interval
from aegean.core.model import Document, Token, TokenKind


# ── collocation.pmi_interval ─────────────────────────────────────────────────


def _wilson_closed_form(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Independent Wilson score interval (Wilson 1927), written from the formula
    so the assertion does not lean on the production ``wilson_interval``."""
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def test_pmi_interval_matches_hand_derived_bounds():
    # joint=5, count_a=count_b=10, total=100. The marginals give
    # pa = pb = 0.1, so denom = pa*pb = 0.01. The interval is the Wilson band on
    # the joint probability mapped through log2(p_j / denom).
    wlo, whi = _wilson_closed_form(5, 100)  # ≈ (0.021543, 0.111752)
    denom = (10 / 100) * (10 / 100)
    exp_lo = math.log2(wlo / denom)  # ≈ 1.107243
    exp_hi = math.log2(whi / denom)  # ≈ 3.482228
    lo, hi = pmi_interval(5, 10, 10, 100)
    assert lo == pytest.approx(exp_lo, abs=1e-12)
    assert hi == pytest.approx(exp_hi, abs=1e-12)


def test_pmi_interval_brackets_the_point_pmi():
    # The Wilson band brackets p̂ = joint/total, so the PMI interval must bracket
    # the plug-in PMI = log2((joint/total) / (pa*pb)) for any non-degenerate table.
    joint, a, b, total = 7, 20, 15, 200
    point = math.log2((joint / total) / ((a / total) * (b / total)))
    lo, hi = pmi_interval(joint, a, b, total)
    assert lo <= point <= hi
    assert lo < hi  # a non-degenerate band has positive width


def test_pmi_interval_zero_joint_floors_low_at_minus_20():
    # joint=0 => Wilson lower bound is 0 => log2(0) is -inf, documented to clamp
    # to the finite floor -20.0; the upper bound stays finite and real.
    lo, hi = pmi_interval(0, 10, 10, 100)
    assert lo == -20.0
    assert math.isfinite(hi)


def test_pmi_interval_degenerate_margin_is_unbounded():
    # A zero total or a zero marginal leaves PMI undefined: (-inf, +inf).
    assert pmi_interval(0, 0, 0, 0) == (-math.inf, math.inf)
    assert pmi_interval(2, 0, 3, 10) == (-math.inf, math.inf)
    assert pmi_interval(2, 3, 0, 10) == (-math.inf, math.inf)


def test_pmi_interval_narrows_as_total_grows():
    # Holding the proportions fixed (joint/total, pa, pb identical), a larger
    # sample shrinks the Wilson band and therefore the PMI band: monotone.
    small = pmi_interval(5, 10, 10, 100)
    big = pmi_interval(50, 100, 100, 1000)
    assert (big[1] - big[0]) < (small[1] - small[0])


# ── align.add_sequence ───────────────────────────────────────────────────────
# Word-level Needleman-Wunsch with GAP=-1, MATCH=+2, MISmatch=0. A column's
# representative word (for scoring against the incoming seq) is its first
# non-None entry. Expected columns are hand-traced from those scores below.


def test_add_sequence_identical_is_all_matches():
    # Prior alignment of ['A','B','C'] (one sequence). Adding the identical
    # sequence takes the all-diagonal path (3 matches, score 6).
    aln = [["A"], ["B"], ["C"]]
    assert add_sequence(aln, ["A", "B", "C"], 1) == [
        ["A", "A"],
        ["B", "B"],
        ["C", "C"],
    ]


def test_add_sequence_insertion_opens_gap_in_prior_columns():
    # Prior has A,C; the new seq inserts B between them. Best score: match A
    # (+2), new column for B with a gap over the prior column ([None,'B'], -1),
    # match C (+2) = 3, beating any substitution path.
    assert add_sequence([["A"], ["C"]], ["A", "B", "C"], 1) == [
        ["A", "A"],
        [None, "B"],
        ["C", "C"],
    ]


def test_add_sequence_deletion_opens_gap_in_new_sequence():
    # Mirror: prior has A,B,C; the new seq omits B, so B's column gets a gap on
    # the new-sequence side (['B', None]).
    assert add_sequence([["A"], ["B"], ["C"]], ["A", "C"], 1) == [
        ["A", "A"],
        ["B", None],
        ["C", "C"],
    ]


def test_add_sequence_substitution_column_beats_double_gap():
    # Prior A,B,C; new A,X,C. Aligning B<->X as a mismatch column scores
    # 2+0+2 = 4, beating the two-gap detour (2-1-1+2 = 2), so the B/X
    # substitution is preferred over splitting them apart.
    assert add_sequence([["A"], ["B"], ["C"]], ["A", "X", "C"], 1) == [
        ["A", "A"],
        ["B", "X"],
        ["C", "C"],
    ]


def test_add_sequence_new_column_padded_with_prior_n_gaps():
    # With two prior sequences (width-2 columns, prior_n=2), a brand-new leading
    # word Z must open a fresh column padded with exactly two None gaps before Z.
    aln = [["A", "A"], ["C", "C"]]
    assert add_sequence(aln, ["Z", "A", "C"], 2) == [
        [None, None, "Z"],
        ["A", "A", "A"],
        ["C", "C", "C"],
    ]


def test_align_sequences_three_way_uses_add_sequence_progressively():
    # The public progressive driver composes add_sequence: the short middle seq
    # (A,C) must carry a None gap exactly where B is missing.
    result = align_sequences([["A", "B", "C"], ["A", "C"], ["A", "B", "C"]])
    assert result == [
        ["A", "A", "A"],
        ["B", None, "B"],
        ["C", "C", "C"],
    ]


def test_align_sequences_empty_input_is_empty():
    assert align_sequences([]) == []


# ── accounting.account_lines ─────────────────────────────────────────────────


def _doc(tokens: list[Token], lines: list[list[int]]) -> Document:
    return Document(id="X", script_id="lineara", tokens=tokens, lines=lines)


def test_account_lines_maps_line_indices_to_token_texts():
    # Two physical lines: [GRA 10] and [KU-RO 10]. account_lines must regroup the
    # flat token list back into per-line text lists exactly as the lines index.
    toks = [
        Token("GRA", TokenKind.LOGOGRAM, ("GRA",), None, 0, 0),
        Token("10", TokenKind.NUMERAL, ("10",), None, 0, 1),
        Token("KU-RO", TokenKind.WORD, ("KU", "RO"), None, 1, 2),
        Token("10", TokenKind.NUMERAL, ("10",), None, 1, 3),
    ]
    doc = _doc(toks, [[0, 1], [2, 3]])
    assert account_lines(doc) == [["GRA", "10"], ["KU-RO", "10"]]


def test_account_lines_follows_index_order_not_token_order():
    # Lines reference tokens by index; account_lines must emit texts in the
    # index order given (here deliberately permuted), proving it indexes rather
    # than slices the flat list.
    toks = [
        Token("GRA", TokenKind.LOGOGRAM, ("GRA",), None, 0, 0),
        Token("10", TokenKind.NUMERAL, ("10",), None, 0, 1),
        Token("KU-RO", TokenKind.WORD, ("KU", "RO"), None, 0, 2),
        Token("5", TokenKind.NUMERAL, ("5",), None, 0, 3),
    ]
    doc = _doc(toks, [[3, 0], [2, 1]])
    assert account_lines(doc) == [["5", "GRA"], ["KU-RO", "10"]]


def test_account_lines_no_lines_is_empty():
    toks = [Token("A-B", TokenKind.WORD, ("A", "B"), None, 0, 0)]
    assert account_lines(_doc(toks, [])) == []


def test_account_lines_preserves_partition_and_token_multiset():
    # Invariant: the flattened result is exactly the token texts in the order
    # the lines enumerate them, and the per-line lengths match the lines index.
    toks = [
        Token(f"T{i}", TokenKind.WORD, (f"T{i}",), None, 0, i) for i in range(6)
    ]
    lines = [[0, 1, 2], [3], [4, 5]]
    out = account_lines(_doc(toks, lines))
    assert [len(line) for line in out] == [len(idx) for idx in lines]
    flat = [text for line in out for text in line]
    assert flat == [toks[i].text for idx in lines for i in idx]
