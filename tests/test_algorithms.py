"""Golden-fixture parity for the ported workbench algorithms.

Asserts the Python port against the SAME expected values the TypeScript
workbench asserts (``tests/fixtures/golden/algorithms.json``), so the two
implementations cannot silently diverge.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from aegean.analysis import (
    CONSERVATIVE_PHONETIC_SCHEME,
    DEFAULT_PHONETIC_SCHEME,
    align_phonetic,
    align_sequences,
    build_phonetic_classes,
    chi_squared_2x2,
    chi_squared_p_value,
    describe_phonetic_scheme,
    extract_root,
    find_morphological_clusters,
    fishers_exact,
    is_numeral_token,
    log_likelihood_ratio_2x2,
    phonetic_distance,
    reference_key,
    sequence_distance,
    sequence_similarity,
    wilson_interval,
)
from aegean.scripts.lineara.phonetic import word_to_phonetic

GOLDEN = json.loads(
    (Path(__file__).parent / "fixtures" / "golden" / "algorithms.json").read_text(
        encoding="utf-8"
    )
)


# ── phonetic transcription / root ────────────────────────────────────────────
@pytest.mark.parametrize("case", GOLDEN["word_to_phonetic"])
def test_word_to_phonetic(case):
    assert word_to_phonetic(case["word"], case["overrides"] or None) == case["expected"]


@pytest.mark.parametrize("case", GOLDEN["extract_root"])
def test_extract_root(case):
    assert extract_root(case["word"]) == case["expected"]


@pytest.mark.parametrize("case", GOLDEN["reference_key"])
def test_reference_key(case):
    assert reference_key(case["word"], case["strip"]) == case["expected"]


def test_describe_phonetic_scheme():
    assert (
        describe_phonetic_scheme(DEFAULT_PHONETIC_SCHEME)
        == GOLDEN["describe_phonetic_scheme"]["default"]
    )


# ── phonetic distance ────────────────────────────────────────────────────────
@pytest.mark.parametrize("case", GOLDEN["phonetic_distance"])
def test_phonetic_distance(case):
    assert phonetic_distance(case["a"], case["b"]) == pytest.approx(
        case["expected"], abs=case["tol"]
    )


# ── phoneme alignment ────────────────────────────────────────────────────────
@pytest.mark.parametrize("case", GOLDEN["align_ops"])
def test_align_phonetic_ops(case):
    ops = [c.op for c in align_phonetic(case["a"], case["b"])]
    assert ops == case["expected"]


def test_align_phonetic_indel_labels():
    assert "ins" in [c.op for c in align_phonetic("ka", "kla")]
    assert "del" in [c.op for c in align_phonetic("kla", "ka")]


# ── phonetic class schemes (mutation-hardening parity) ───────────────────────
def _class_with(classes, c):
    for g in classes.consonant_classes:
        if c in g:
            return g
    return ()


def test_default_scheme_layers_contested_phonemes():
    cl = build_phonetic_classes(DEFAULT_PHONETIC_SCHEME)
    assert "ṯ" in _class_with(cl, "t")  # interdentals → dental
    assert "ḥ" in _class_with(cl, "k")  # pharyngeal ḥ → velar
    assert "ž" in _class_with(cl, "s")  # voiced postalveolar → sibilant


def test_conservative_scheme_excludes_contested_phonemes():
    cl = build_phonetic_classes(CONSERVATIVE_PHONETIC_SCHEME)
    assert "ṯ" not in _class_with(cl, "t")
    assert "ḥ" not in _class_with(cl, "k")
    assert "ž" not in _class_with(cl, "s")


def test_interdentals_routed_to_sibilant():
    cl = build_phonetic_classes(replace(DEFAULT_PHONETIC_SCHEME, interdentals="sibilant"))
    assert "ṯ" in _class_with(cl, "s")
    assert "ṯ" not in _class_with(cl, "t")


# ── collocation statistics ───────────────────────────────────────────────────
@pytest.mark.parametrize("case", GOLDEN["collocation"]["chi_squared"])
def test_chi_squared(case):
    assert chi_squared_2x2(
        case["joint"], case["countA"], case["countB"], case["total"]
    ) == pytest.approx(case["expected"], abs=case["tol"])


@pytest.mark.parametrize("case", GOLDEN["collocation"]["log_likelihood"])
def test_log_likelihood(case):
    assert log_likelihood_ratio_2x2(
        case["joint"], case["countA"], case["countB"], case["total"]
    ) == pytest.approx(case["expected"], abs=case["tol"])


@pytest.mark.parametrize("case", GOLDEN["collocation"]["p_value"])
def test_chi_squared_p_value(case):
    assert chi_squared_p_value(case["x"]) == pytest.approx(case["expected"], abs=case["tol"])


@pytest.mark.parametrize("case", GOLDEN["collocation"]["fisher"])
def test_fishers_exact(case):
    assert fishers_exact(
        case["joint"], case["countA"], case["countB"], case["total"]
    ) == pytest.approx(case["expected"], abs=case["tol"])


@pytest.mark.parametrize(
    "joint, count_a, count_b, total",
    [
        (5, 3, 5, 10),  # joint > count_a  → implied a12 = count_a - joint < 0
        (5, 5, 3, 10),  # joint > count_b  → implied a21 = count_b - joint < 0
        (3, 5, 5, 6),  # a22 = total - count_a - count_b + joint = -1 < 0
    ],
)
def test_fishers_exact_impossible_table_returns_one(joint, count_a, count_b, total):
    """An impossible 2×2 table (an implied cell count is negative) has no
    admissible hypergeometric support; ``fishers_exact`` returns its documented
    degenerate value 1.0 rather than raising a ``math.lgamma`` domain error.
    Mirrors the graceful 0.0 that ``chi_squared_2x2`` / ``log_likelihood_ratio_2x2``
    already return on the same inputs via the shared ``_cells`` guard."""
    # Hand check (joint=5, count_a=3): a12 = 3 - 5 = -2 < 0, so the table cannot
    # be realized; the test is degenerate and the two-sided p-value is 1.0.
    assert fishers_exact(joint, count_a, count_b, total) == 1.0
    # And χ²/G² stay graceful (0.0) on the very same impossible inputs.
    assert chi_squared_2x2(joint, count_a, count_b, total) == 0.0
    assert log_likelihood_ratio_2x2(joint, count_a, count_b, total) == 0.0


def test_fishers_exact_valid_table_unchanged():
    """The guard fix must not perturb a genuine result: the canonical fully
    associated 5/5/5/10 table still yields the hand-verified two-sided
    hypergeometric p-value. The two extreme tables k=0 and k=5 each have
    probability 1/C(10,5) = 1/252, both ≤ the observed (k=5) probability, so the
    two-sided sum is 2/252 ≈ 0.007937."""
    assert fishers_exact(5, 5, 5, 10) == pytest.approx(2.0 / 252.0, abs=1e-9)


def test_wilson_interval_brackets_and_bounds():
    lo, hi = wilson_interval(5, 10)
    assert 0 <= lo < 0.5 < hi <= 1
    assert wilson_interval(0, 0) == (0.0, 1.0)


# ── sequence distance / similarity ───────────────────────────────────────────
@pytest.mark.parametrize("case", GOLDEN["sequence"])
def test_sequence(case):
    assert sequence_distance(case["a"], case["b"]) == case["dist"]
    assert sequence_similarity(case["a"], case["b"]) == pytest.approx(case["sim"], abs=1e-12)


# ── word-level multiple-sequence alignment ───────────────────────────────────
@pytest.mark.parametrize("case", GOLDEN["align_sequences"])
def test_align_sequences(case):
    result = [list(pos) for pos in align_sequences([list(s) for s in case["seqs"]])]
    assert result == [list(pos) for pos in case["expected"]]


# ── numeral-token recognition ────────────────────────────────────────────────
def test_is_numeral_token():
    assert is_numeral_token("123")
    assert is_numeral_token("≈")
    assert not is_numeral_token("KU-RO")
    assert not is_numeral_token("")


# ── morphological clustering ─────────────────────────────────────────────────
@pytest.mark.parametrize("case", GOLDEN["morphology"])
def test_morphology(case):
    clusters = find_morphological_clusters(case["input"], **case["opts"])
    got = [
        {
            "stem": c.stem,
            "members": sorted(m.word for m in c.members),
            "suffixes": sorted(c.suffixes),
            "total_count": c.total_count,
        }
        for c in clusters
    ]
    want = [
        {
            "stem": e["stem"],
            "members": sorted(e["members"]),
            "suffixes": sorted(e["suffixes"]),
            "total_count": e["total_count"],
        }
        for e in case["expected"]
    ]
    assert sorted(got, key=lambda d: d["stem"]) == sorted(want, key=lambda d: d["stem"])
