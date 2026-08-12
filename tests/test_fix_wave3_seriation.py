"""seriate: each solver gets the budget its own block needs, and says when it did not get there.

Both solvers settle at a rate set by the block's own size, so one budget fixed independently of the
block cannot serve both a small block and a large one. The power iteration ran out past roughly a
hundred and sixty rows and the direct eigensolver's rotations ran out past roughly a hundred and
forty, and each returned the half-finished thing it was holding: an unsettled vector, a diagonal
that is not yet a spectrum. These tests pin the replacement for both. Each budget is derived from
the block; the derived step budget's shape across its whole domain is what it is documented to be,
rise, peak, decay and floor, not simply rising; a budget the caller names is used exactly as named
and refused cleanly when it is not a budget at all; every block that already settled keeps exactly
the ordering it had; the ordering still survives permuting the input; and a block that cannot
settle says which of the reasons it is, including which of them the caller has a lever for.
"""

import math
import random
import warnings

import pytest

import aegean
from aegean.analysis import seriation
from aegean.analysis.seriation import (
    _abundance_from_corpus,
    _argsort,
    _components,
    _DENSE_SOLVER_MAX_N,
    _DERIVED_WORK_ALLOWANCE,
    _default_max_iter,
    _default_max_sweeps,
    _jacobi_eigh,
    _MIN_DERIVED_MAX_ITER,
    _MIN_DERIVED_MAX_SWEEPS,
    brainerd_robinson,
    seriate,
)

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _quiet(rows, **kwargs):
    """seriate() with the ambiguity warnings muted; the warnings have their own tests."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return seriate(rows, **kwargs)


def _battleship(n, n_types, spread):
    """A planted seriation: each type's unimodal peak marches along the assemblage sequence,
    so row order 0..n-1 is the true ordering."""
    peaks = [t * (n - 1) / (n_types - 1) for t in range(n_types)]
    return [
        [max(0.0, 10.0 - spread * abs(a - peaks[t])) for t in range(n_types)] for a in range(n)
    ]


def _dense(n, n_types, seed):
    rng = random.Random(seed)
    return [[rng.randint(1, 15) for _ in range(n_types)] for _ in range(n)]


def _content(rows, order):
    return tuple(tuple(rows[i]) for i in order)


# A planted table one block wide and past the direct solver's row limit. Its axis needs 273 power
# steps to settle: more than the 200 the old fixed budget allowed, few enough to seriate twice in
# a couple of seconds.
PLANTED_LARGE = _battleship(200, 60, 0.4)
PLANTED_LARGE_TRUTH = list(range(200))

# A block of the same kind whose axis settles only after some 1,200 steps, far enough past the old
# budget that the vector at step 200 is nowhere near the limit it is heading for.
SLOW_BLOCK = _dense(161, 10, 3)


# --------------------------------------------------------------------------- #
# the derived budget itself
# --------------------------------------------------------------------------- #


def test_derived_budget_rises_with_the_block_up_to_the_peak():
    # Over the rising stretch, and only there: more rows, more steps.
    assert _default_max_iter(161) < _default_max_iter(200) < _default_max_iter(255)


def test_derived_budget_rises_to_a_peak_then_decays_onto_the_budget_it_replaced():
    # The budget is not one shape across its domain, and what it does over the rest of the domain
    # is the opposite of what it does at the small end. Rise: every extra row buys steps.
    rising = [_default_max_iter(n) for n in range(2, 256)]
    assert rising == sorted(rising)
    assert len(set(rising)) == len(rising)  # strictly, not merely non-decreasing
    # Peak: one row count is the most generous the default is ever prepared to be.
    assert _default_max_iter(255) == 30_600
    assert max(_default_max_iter(n) for n in range(1, 6_000)) == _default_max_iter(255)
    # Decay: past the peak the work allowance decides, and every extra row costs steps.
    decaying = [_default_max_iter(n) for n in range(255, 3_156)]
    assert decaying == sorted(decaying, reverse=True)
    assert (_default_max_iter(500), _default_max_iter(1_000)) == (8_000, 2_000)
    # Floor: from 3,155 rows the allowance has fallen through the floor, and a block that large
    # gets exactly the fixed budget the derived one replaced, not one step more.
    assert _default_max_iter(3_154) > _MIN_DERIVED_MAX_ITER
    for n in (3_155, 3_162, 10_000, 1_000_000):
        assert _default_max_iter(n) == _MIN_DERIVED_MAX_ITER == 200, n


def test_derived_budget_never_falls_below_the_fixed_budget_it_replaced():
    # A block that already settled inside 200 steps stops at the same step under any larger cap,
    # so keeping the derived budget at or above 200 everywhere is what makes every previously
    # settled ordering carry over unchanged.
    for n in (1, 2, 40, 160, 161, 200, 400, 1000, 5000, 50_000):
        assert _default_max_iter(n) >= 200, n


def test_derived_budget_holds_one_block_to_a_bounded_amount_of_work():
    # A step costs work proportional to the squared row count, so a budget proportional to the
    # block alone would let one large block run for an unbounded time before reporting that it
    # never settled. Over the range where the allowance rather than the floor decides, the two
    # multiply out to no more than the allowance.
    for n in (161, 200, 255, 300, 400, 500, 1000, 2000):
        assert _default_max_iter(n) * n**2 <= _DERIVED_WORK_ALLOWANCE, n


# --------------------------------------------------------------------------- #
# what the derived budget buys: a block that could not settle now settles
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def planted_settled():
    """The planted block seriated at the derived budget; several tests read the same result."""
    return _quiet(PLANTED_LARGE)


def test_a_large_block_settles_by_default_where_the_old_fixed_budget_ran_out(planted_settled):
    stopped_short = _quiet(PLANTED_LARGE, max_iter=200)
    assert stopped_short.iterations == 200  # the budget was spent, not the convergence test met
    assert stopped_short.ambiguous is True

    assert planted_settled.ambiguous is False
    assert 200 < planted_settled.iterations <= _default_max_iter(200)
    # And the settled axis recovers the planted sequence, up to the inherent reversal.
    assert list(planted_settled.order) in (PLANTED_LARGE_TRUTH, PLANTED_LARGE_TRUTH[::-1])


def test_the_default_returns_the_axis_the_data_determines_not_a_way_station():
    # This block needs some 1,200 steps, so at 200 the iteration was still a long way from the
    # vector it was heading for, and the ordering read off it was not the answer.
    settled = _quiet(SLOW_BLOCK)
    assert settled.ambiguous is False
    assert settled.iterations > 200
    assert _quiet(SLOW_BLOCK, max_iter=200).order != settled.order


# --------------------------------------------------------------------------- #
# a budget the caller names is the budget the caller gets
# --------------------------------------------------------------------------- #


def test_an_explicit_budget_is_spent_and_never_exceeded():
    # The budget this block's size would derive settles it outright, so a derived budget standing
    # in for a smaller named one would show up here as an iteration count past what was named.
    assert _default_max_iter(200) > 1_000
    for budget in (50, 100, 200):
        held = _quiet(PLANTED_LARGE, max_iter=budget)
        assert held.iterations == budget, budget
        # Stopped short of the step where this block settles, so still undetermined.
        assert held.ambiguous is True, budget


def test_naming_the_derived_budget_is_the_same_as_naming_nothing(planted_settled):
    named = _quiet(PLANTED_LARGE, max_iter=_default_max_iter(200))
    assert named.order == planted_settled.order
    assert named.iterations == planted_settled.iterations
    assert named.ambiguous == planted_settled.ambiguous


def test_once_settled_a_far_larger_budget_cannot_move_the_answer(planted_settled):
    # What makes the settled ordering the answer rather than a way-station: more steps change
    # nothing, because the iteration stopped when it had stopped moving.
    generous = _quiet(PLANTED_LARGE, max_iter=100_000)
    assert generous.order == planted_settled.order
    assert generous.iterations == planted_settled.iterations


def test_a_non_positive_budget_is_still_refused_cleanly():
    for bad in (0, -1, -10_000):
        with pytest.raises(ValueError, match="max_iter must be positive"):
            seriate(PLANTED_LARGE[:4], max_iter=bad)


# --------------------------------------------------------------------------- #
# blocks the direct solver handles are untouched by any of this
# --------------------------------------------------------------------------- #

# Every one of these is inside the direct solver's row limit, so no budget of any size reaches
# them. Shapes: planted, disconnected, blank, tied, proportionally duplicate, dense.
SMALL_CASES = {
    "battleship_12x7": _battleship(12, 7, 2.2),
    "battleship_30x9": _battleship(30, 9, 1.4),
    "two_blocks": [[10, 5, 0, 0], [8, 6, 0, 0], [0, 0, 10, 5], [0, 0, 8, 6]],
    "all_zero": [[0, 0], [0, 0], [0, 0]],
    "blank_among_real": [[0, 0, 0], [1, 2, 3], [3, 2, 1]],
    "singletons_40": [[1 if c == r else 0 for c in range(40)] for r in range(40)],
    "cycle4": [[1, 1, 0, 0], [0, 1, 1, 0], [0, 0, 1, 1], [1, 0, 0, 1]],
    "tied_rows": [[1, 0, 0], [0, 1, 0], [1, 1, 1], [1, 1, 2]],
    "prop_dupes": [[3, 0], [1, 0], [1, 1]],
    "dense_9x6": _dense(9, 6, 3),
    "dense_40x5": _dense(40, 5, 11),
}


def test_small_matrices_ignore_the_budget_entirely():
    # The mechanism by which small matrices cannot have moved: the direct solver neither reads nor
    # needs a step budget, so every budget, absent or absurd, gives one and the same result.
    for name, rows in SMALL_CASES.items():
        assert len(rows) <= _DENSE_SOLVER_MAX_N, name
        baseline = _quiet(rows)
        for budget in (1, 200, 999_999):
            other = _quiet(rows, max_iter=budget)
            assert other.order == baseline.order, (name, budget)
            assert other.components == baseline.components, (name, budget)
            assert other.ambiguous == baseline.ambiguous, (name, budget)
            assert other.iterations == baseline.iterations, (name, budget)


# The orderings these matrices produce, read off the module as committed before the budget was
# derived from the block. They pin the ordering itself, not merely its independence from a budget.
SMALL_GOLDENS = {
    "battleship_12x7": tuple(range(12)),
    "battleship_30x9": tuple(range(30)),
    "two_blocks": (0, 1, 2, 3),
    "all_zero": (0, 2, 1),
    "blank_among_real": (0, 1, 2),
    "singletons_40": tuple(range(40)),
    "cycle4": (0, 3, 1, 2),
    "tied_rows": (0, 3, 2, 1),
    "prop_dupes": (1, 0, 2),
    "dense_9x6": (6, 4, 5, 1, 3, 2, 8, 0, 7),
    "dense_40x5": (
        8, 32, 4, 28, 33, 10, 13, 14, 22, 38, 29, 15, 37, 9, 7, 3, 11, 5, 26, 36,
        30, 6, 20, 12, 0, 34, 21, 1, 39, 27, 35, 17, 2, 23, 31, 24, 19, 18, 16, 25,
    ),
}


def test_small_matrices_keep_the_orderings_they_had():
    assert set(SMALL_GOLDENS) == set(SMALL_CASES)  # no case pinned by independence alone
    for name, expected in SMALL_GOLDENS.items():
        assert _quiet(SMALL_CASES[name]).order == expected, name


def test_a_real_small_corpus_keeps_the_ordering_it_had():
    zakros = _quiet(aegean.load("lineara").filter(site="Zakros"))
    assert zakros.ordered_labels()[:6] == (
        "ZAWa38",
        "ZA11b",
        "ZAZb3",
        "ZA21b",
        "ZA6b",
        "ZA18a",
    )


# --------------------------------------------------------------------------- #
# permutation invariance still holds, on real and on large material
# --------------------------------------------------------------------------- #


def _shuffled_readings(rows, seeds, **kwargs):
    out = []
    for s in seeds:
        perm = list(range(len(rows)))
        random.Random(s).shuffle(perm)
        permuted = [rows[i] for i in perm]
        out.append((s, _content(permuted, _quiet(permuted, **kwargs).order)))
    return out


def test_real_linear_a_sample_is_still_invariant_under_twenty_shuffles():
    docs = sorted(aegean.load("lineara").documents, key=lambda d: d.id)[:60]
    matrix, _labels, _types = _abundance_from_corpus(docs)
    base = _content(matrix, _quiet(matrix).order)
    for seed, reading in _shuffled_readings(matrix, range(20)):
        assert reading == base or reading == tuple(reversed(base)), seed


def test_large_planted_block_is_invariant_under_shuffles_at_the_derived_budget(planted_settled):
    base = _content(PLANTED_LARGE, planted_settled.order)
    for seed, reading in _shuffled_readings(PLANTED_LARGE, range(3)):
        assert reading == base or reading == tuple(reversed(base)), seed


# --------------------------------------------------------------------------- #
# what an unsettled block says about itself
# --------------------------------------------------------------------------- #


def test_a_block_stopped_by_its_budget_names_the_budget_as_the_reason():
    with pytest.warns(UserWarning) as caught:
        seriate(PLANTED_LARGE, max_iter=200)
    messages = [str(w.message) for w in caught]
    assert any("axis undetermined for 200 of 200 rows" in m for m in messages)
    # The actionable half: not the similarity's fault, and here is the lever.
    budget = [m for m in messages if "max_iter" in m]
    assert budget, messages
    assert "step budget" in budget[0]
    assert "200 of 200 rows" in budget[0]


def test_a_settled_block_says_nothing_about_the_budget():
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning on data this ordinary would be noise
        settled = seriate(PLANTED_LARGE)
    assert settled.ambiguous is False


def test_a_genuinely_undetermined_block_is_not_blamed_on_the_budget():
    # A four-cycle has a repeated Fiedler eigenvalue: no budget can single out an axis there, and
    # the report must not send the caller off to raise one.
    cycle = SMALL_CASES["cycle4"]
    with pytest.warns(UserWarning) as caught:
        seriate(cycle)
    messages = [str(w.message) for w in caught]
    assert any("axis undetermined for 4 of 4 rows" in m for m in messages)
    assert not any("max_iter" in m for m in messages), messages


# --------------------------------------------------------------------------- #
# the direct solver's own budget: derived from the block, and honest when it runs out
# --------------------------------------------------------------------------- #


def _laplacian(rows):
    """The block Laplacian the seriation builds, for a matrix that is one connected block."""
    sim = brainerd_robinson(rows)
    assert len(_components(sim)) == 1  # otherwise the solver never sees this matrix whole
    n = len(sim)
    row_sum = [sum(row) for row in sim]
    return [[(row_sum[i] if i == j else 0.0) - sim[i][j] for j in range(n)] for i in range(n)]


# Forty identical rows. Every pair scores the full 200, so the block Laplacian is exactly
# 8000*I - 200*J, whose spectrum is 0 once (the constant vector) and 8000 thirty-nine times. Hand
# computable, so what the rotations return can be checked against the answer rather than against
# themselves.
IDENTICAL_40 = [[1.0, 2.0, 3.0]] * 40
IDENTICAL_40_SPECTRUM = [0.0] + [8_000.0] * 39

# Rows differing in the fourth decimal: the slowest family found for these rotations, needing
# about one sweep per row where planted, dense and chain tables need about a third of one.
NEAR_IDENTICAL = {n: [[1.0, 1.0] if i % 2 else [1.0, 1.001] for i in range(n)] for n in (30, 50)}

# A chain of forty assemblages, each sharing a type with its neighbours. Where identical rows are
# numerically forgiving, this block is what an unfinished solve gets wrong: three sweeps in, the
# second-smallest entry left on the diagonal is nowhere near the block's Fiedler eigenvalue and
# the vector standing beside it points somewhere else entirely.
CHAIN_40 = [[1 if abs(c - r) <= 1 else 0 for c in range(40)] for r in range(40)]


def _fiedler_of(matrix, **kwargs):
    """What the direct solver offers as the seriation axis: the second-smallest pair."""
    vals, vecs, sweeps, separated = _jacobi_eigh(matrix, **kwargs)
    rank = sorted(range(len(vals)), key=lambda k: vals[k])
    return vals[rank[1]], vecs[rank[1]], sweeps, separated


def test_the_direct_solver_returns_the_spectrum_it_promises_when_its_rotations_finish():
    eigvals, eigvecs, sweeps, separated = _jacobi_eigh(_laplacian(IDENTICAL_40))
    assert separated is True
    assert sweeps < _default_max_sweeps(40)
    assert sorted(eigvals) == pytest.approx(IDENTICAL_40_SPECTRUM, abs=1e-6)
    for vec in eigvecs:
        assert math.sqrt(sum(x * x for x in vec)) == pytest.approx(1.0)


def test_the_direct_solver_reports_rotations_its_budget_cut_short():
    laplacian = _laplacian(CHAIN_40)
    value, axis, sweeps, separated = _fiedler_of(laplacian, max_sweeps=3)
    assert (sweeps, separated) == (3, False)
    finished_value, finished_axis, _sweeps, finished = _fiedler_of(laplacian)
    assert finished is True
    # Reporting it is not pedantry. Cut short, what is offered as the Fiedler eigenvalue is
    # several times the block's real one, the vector beside it is a different direction, and so
    # the ordering read off it is a different ordering.
    assert finished_value == pytest.approx(2.46325, rel=1e-4)
    assert value > 3 * finished_value
    apart = min(
        sum((a - b) ** 2 for a, b in zip(axis, finished_axis, strict=True)),
        sum((a + b) ** 2 for a, b in zip(axis, finished_axis, strict=True)),
    )
    assert apart > 1.0  # unit vectors, so 2.0 is as far apart as two of them get
    assert _argsort(axis) not in (_argsort(finished_axis), _argsort(finished_axis)[::-1])


def test_a_solve_given_no_sweeps_at_all_reports_what_it_did_not_do():
    # The flag is a statement about the matrix, not about the budget having been spent: a matrix
    # already diagonal is separated after no sweeps at all, and one that is not, is not.
    laplacian = _laplacian(CHAIN_40)
    eigvals, _vecs, sweeps, separated = _jacobi_eigh(laplacian, max_sweeps=0)
    assert (sweeps, separated) == (0, False)
    assert eigvals == [row[i] for i, row in enumerate(laplacian)]  # the diagonal, untouched
    assert _jacobi_eigh([[2.0, 0.0], [0.0, 5.0]], max_sweeps=0)[2:] == (0, True)


def test_the_sweep_budget_derives_from_the_block_and_never_drops_below_its_predecessor():
    # A block that finished under the fixed hundred stops at the same sweep under any larger
    # budget, so keeping the derived budget at or above it everywhere is what carries every
    # previously finished solve over unchanged.
    assert _default_max_sweeps(3) == _default_max_sweeps(33) == _MIN_DERIVED_MAX_SWEEPS == 100
    assert _default_max_sweeps(34) == 102
    rising = [_default_max_sweeps(n) for n in range(34, _DENSE_SOLVER_MAX_N + 1)]
    assert rising == sorted(rising)
    assert len(set(rising)) == len(rising)
    for n in range(1, _DENSE_SOLVER_MAX_N + 1):
        assert _default_max_sweeps(n) >= _MIN_DERIVED_MAX_SWEEPS, n


def test_the_derived_sweep_budget_covers_the_slowest_family_measured():
    needed = {}
    for n, rows in NEAR_IDENTICAL.items():
        _vals, _vecs, sweeps, separated = _jacobi_eigh(_laplacian(rows))
        assert separated is True, n
        assert sweeps * 2 <= _default_max_sweeps(n), (n, sweeps)  # headroom, not a near miss
        needed[n] = sweeps
    # What this family needs rises with the block, so no budget fixed independently of the matrix
    # can serve both ends of the row range this solver declares: at the rate measured here, the
    # top of that range needs more sweeps than the fixed hundred the derived budget replaced.
    assert needed[50] > needed[30]
    assert needed[50] / 50 * _DENSE_SOLVER_MAX_N > _MIN_DERIVED_MAX_SWEEPS


def test_a_block_the_direct_solver_could_not_finish_is_not_blamed_on_max_iter(monkeypatch):
    rows = SMALL_CASES["battleship_30x9"]
    assert _quiet(rows).ambiguous is False  # control: with its own budget this block is settled
    monkeypatch.setattr(seriation, "_default_max_sweeps", lambda n: 1)
    with pytest.warns(UserWarning) as caught:
        result = seriation.seriate(rows)
    assert result.ambiguous is True
    messages = [str(w.message) for w in caught]
    assert any("axis undetermined for 30 of 30 rows" in m for m in messages)
    sweeps = [m for m in messages if "sweep budget" in m]
    assert sweeps, messages
    assert "30 of 30 rows" in sweeps[0]
    # The half of the report that has to be true: this is not the budget the caller sets, so the
    # message must not send them off to raise the one they can.
    assert "max_iter" in sweeps[0]
    assert "is not the lever" in sweeps[0]
    # And it really is not the lever: naming any budget leaves the block exactly as undetermined.
    with pytest.warns(UserWarning) as after:
        raised = seriation.seriate(rows, max_iter=1_000_000)
    assert any("sweep budget" in str(w.message) for w in after)
    assert raised.ambiguous is True
    assert raised.order == result.order


def test_raising_the_sweep_budget_cannot_move_a_block_that_already_finished(monkeypatch):
    # The direct path's half of the compatibility claim: a solve that stopped because it had
    # finished stops at the same sweep however much budget it is given, so the ordering, the
    # blocks, the ambiguity report and the sweep count all carry over untouched.
    baseline = {name: _quiet(rows) for name, rows in SMALL_CASES.items()}
    monkeypatch.setattr(seriation, "_default_max_sweeps", lambda n: 100_000)
    for name, rows in SMALL_CASES.items():
        other = _quiet(rows)
        assert other.order == baseline[name].order, name
        assert other.components == baseline[name].components, name
        assert other.ambiguous == baseline[name].ambiguous, name
        assert other.iterations == baseline[name].iterations, name
        assert other.similarity == baseline[name].similarity, name


# --------------------------------------------------------------------------- #
# a budget has to be a budget
# --------------------------------------------------------------------------- #


def test_a_budget_that_is_not_an_integer_is_refused_by_name():
    for bad in ("200", 1.5, 200.0, float("inf"), float("nan"), True, False, [200], object()):
        with pytest.raises(TypeError, match="max_iter must be a positive int or None"):
            seriate(PLANTED_LARGE[:4], max_iter=bad)


def test_the_refusal_names_the_type_it_was_handed():
    with pytest.raises(TypeError, match="got str"):
        seriate(PLANTED_LARGE[:4], max_iter="200")
    with pytest.raises(TypeError, match="got float"):
        seriate(PLANTED_LARGE[:4], max_iter=float("inf"))


def test_no_budget_at_all_is_still_how_the_default_is_asked_for(planted_settled):
    explicit_none = _quiet(PLANTED_LARGE, max_iter=None)
    # Absolutely, not merely relative to omitting the argument: ``None`` buys the budget derived
    # from this block, which is what carries it past the fixed budget the derived one replaced.
    assert explicit_none.ambiguous is False
    assert _MIN_DERIVED_MAX_ITER < explicit_none.iterations <= _default_max_iter(200)
    assert explicit_none.order == planted_settled.order
    assert explicit_none.iterations == planted_settled.iterations
