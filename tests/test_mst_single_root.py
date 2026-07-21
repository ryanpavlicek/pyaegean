"""Exactness and hostile-input tests for single-root dependency decoding."""

from __future__ import annotations

from itertools import product
from typing import Any

import pytest

np = pytest.importorskip("numpy")

from aegean.greek.mst import decode_mst  # noqa: E402


def _is_single_root_tree(heads: list[int]) -> bool:
    if heads.count(0) != 1:
        return False
    for dependent, head in enumerate(heads, start=1):
        if head < 0 or head > len(heads) or head == dependent:
            return False
        seen: set[int] = set()
        node = dependent
        while node:
            if node in seen:
                return False
            seen.add(node)
            node = heads[node - 1]
    return True


def _tree_score(scores: Any, heads: tuple[int, ...] | list[int]) -> float:
    return float(sum(scores[dependent - 1, head] for dependent, head in enumerate(heads, 1)))


def _brute_force_score(scores: Any) -> float:
    words = scores.shape[0]
    best = -np.inf
    for heads in product(range(words + 1), repeat=words):
        candidate = list(heads)
        if not _is_single_root_tree(candidate):
            continue
        if any(
            not np.isfinite(scores[dependent - 1, head])
            for dependent, head in enumerate(candidate, 1)
        ):
            continue
        best = max(best, _tree_score(scores, candidate))
    return float(best)


def test_decoder_regression_never_returns_the_original_two_root_forest() -> None:
    scores = np.array(
        [
            [0.9301221370697021, -np.inf, 0.14906825125217438, 1.5242061614990234],
            [1.3283185958862305, 0.5178317427635193, -np.inf, -0.39536401629447937],
            [0.9908871054649353, 1.2558777332305908, -2.37347149848938, -np.inf],
        ]
    )

    heads = decode_mst(scores)

    assert _is_single_root_tree(heads)
    assert _tree_score(scores, heads) == pytest.approx(_brute_force_score(scores))


def test_decoder_is_exact_for_every_binary_three_word_score_graph() -> None:
    words = 3
    edges = [
        (dependent, head)
        for dependent in range(1, words + 1)
        for head in range(words + 1)
        if head != dependent
    ]
    for weights in product((0.0, 1.0), repeat=len(edges)):
        scores = np.full((words, words + 1), -np.inf)
        for (dependent, head), weight in zip(edges, weights, strict=True):
            scores[dependent - 1, head] = weight

        heads = decode_mst(scores)

        assert _is_single_root_tree(heads)
        assert _tree_score(scores, heads) == _brute_force_score(scores)


def test_decoder_matches_brute_force_on_seeded_sparse_graphs() -> None:
    random = np.random.default_rng(20260717)
    for words in range(2, 5):
        for _ in range(50):
            scores = random.normal(size=(words, words + 1))
            scores[random.random(scores.shape) < 0.5] = -np.inf
            for dependent in range(words):
                scores[dependent, dependent + 1] = -np.inf
            # Guarantee at least one legal single-root chain in every sparse graph.
            order = random.permutation(words)
            scores[order[0], 0] = random.normal()
            for index in range(1, words):
                scores[order[index], order[index - 1] + 1] = random.normal()

            heads = decode_mst(scores)

            assert _is_single_root_tree(heads)
            assert _tree_score(scores, heads) == pytest.approx(_brute_force_score(scores))


def test_decoder_handles_empty_singleton_and_extreme_finite_scores() -> None:
    assert decode_mst(np.empty((0, 1))) == []
    assert decode_mst(np.array([[3.0, 1_000.0]])) == [0]
    scores = np.array(
        [
            [1e308, 1e308, -1e308],
            [-1e308, 1e308, -1e308],
        ]
    )
    assert decode_mst(scores) == [0, 1]


@pytest.mark.parametrize(
    "scores, message",
    [
        (np.zeros((2, 2)), "shape"),
        (np.array([[np.nan, 0.0]]), "finite values"),
        (np.array([[np.inf, 0.0]]), "finite values"),
        (np.array([["root", "self"]]), "numeric"),
        (np.array([[-np.inf, 0.0]]), "finite candidate head"),
        (
            np.array([[-np.inf, -np.inf, 1.0], [-np.inf, 1.0, -np.inf]]),
            "single-root arborescence",
        ),
    ],
)
def test_decoder_rejects_malformed_or_impossible_graphs(scores: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        decode_mst(scores)


def test_decoder_ignores_finite_self_loop_scores() -> None:
    scores = np.array([[2.0, 999.0, 0.0], [0.0, 3.0, 999.0]])

    assert decode_mst(scores) == [0, 1]


def test_decoder_is_exact_when_scale_dwarfs_root_score_differences() -> None:
    # One irrelevant huge-magnitude arc inflates the scaling denominator; the
    # single-root penalty must not absorb the O(1) ROOT-column differences.
    scores = np.array(
        [
            [0.0, -np.inf, 0.0, -np.inf],
            [1.0, 0.0, -np.inf, -np.inf],
            [-np.inf, 0.0, -1e16, -np.inf],
        ]
    )

    heads = decode_mst(scores)

    assert heads == [2, 0, 1]
    assert _tree_score(scores, heads) == pytest.approx(_brute_force_score(scores))
    # The same graph with an ordinary magnitude decodes identically.
    benign = scores.copy()
    benign[2, 2] = -10.0
    assert decode_mst(benign) == heads


def test_decoder_matches_brute_force_on_seeded_mixed_magnitude_graphs() -> None:
    random = np.random.default_rng(20260719)
    checked = 0
    for _ in range(160):
        words = int(random.integers(2, 5))
        scores = random.normal(size=(words, words + 1))
        # Repeated injections may overflow a cell; such matrices are filtered out.
        with np.errstate(over="ignore"):
            for _ in range(int(random.integers(1, words + 2))):
                dependent = int(random.integers(0, words))
                head = int(random.integers(0, words + 1))
                scores[dependent, head] *= 10.0 ** float(random.integers(-180, 180))
        if not np.isfinite(scores).all():
            continue

        heads = decode_mst(scores)

        checked += 1
        assert _is_single_root_tree(heads)
        best = _brute_force_score(scores)
        assert _tree_score(scores, heads) >= best - 1e-9 * max(1.0, abs(best))
    assert checked > 100


def test_decoder_absorption_fallback_is_deterministic() -> None:
    scores = np.array(
        [
            [0.0, -np.inf, 0.0, -np.inf],
            [1.0, 0.0, -np.inf, -np.inf],
            [-np.inf, 0.0, -1e16, -np.inf],
        ]
    )
    first = decode_mst(scores)
    assert all(decode_mst(scores) == first for _ in range(5))


def test_decoder_absorption_fallback_respects_forced_root_feasibility() -> None:
    # Word 3 can attach only to ROOT, so it is the only legal root child; the
    # huge-magnitude arc forces the exact fallback path to make that call.
    scores = np.array(
        [
            [0.0, -np.inf, -np.inf, 5.0],
            [-np.inf, 1.0, -np.inf, -np.inf],
            [1.0, -1e16, -np.inf, -np.inf],
        ]
    )

    heads = decode_mst(scores)

    assert heads == [3, 1, 0]
    assert _tree_score(scores, heads) == pytest.approx(_brute_force_score(scores))
