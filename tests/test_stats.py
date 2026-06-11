"""The corpus-statistics layer: dispersion (Gries' DP), keyness, bootstrap (offline)."""

from __future__ import annotations

import math

import pytest

from aegean.analysis import stats
from aegean.core.model import Document, DocumentMeta, Token, TokenKind


def _doc(doc_id: str, words: list[str], site: str = "") -> Document:
    tokens = [Token(w, TokenKind.WORD, tuple(w.split("-")), None, 0, i) for i, w in enumerate(words)]
    return Document(
        id=doc_id, script_id="linearb", tokens=tokens,
        lines=[list(range(len(tokens)))] if tokens else [],
        meta=DocumentMeta(site=site),
    )


# ── dispersion ──────────────────────────────────────────────────────────────


def test_dp_concentrated_vs_even():
    # 5 documents of equal size (10 words each); "ku-ro" only in the first one.
    docs = [_doc(f"D{i}", ["ku-ro" if i == 0 else "pa-ro"] * 10) for i in range(5)]
    d = stats.dispersion(docs, "ku-ro")
    # all occurrences in one of five equal parts: DP = ½(|1−0.2| + 4·|0−0.2|) = 0.8
    assert d.frequency == 10 and d.range == 1 and d.parts == 5
    assert d.dp == pytest.approx(0.8)
    assert d.dp_norm == pytest.approx(0.8 / (1 - 0.2))  # = 1.0, the attainable max

    even = stats.dispersion(docs, "pa-ro")
    # "pa-ro" fills 4 of 5 equal parts evenly: v=(0,¼,¼,¼,¼) vs s=0.2 → DP = 0.2
    assert even.dp == pytest.approx(0.2)
    assert even.dp_norm < d.dp_norm


def test_dp_perfectly_proportional_is_zero():
    # one word distributed exactly as the document sizes predict
    docs = [
        _doc("A", ["ku-ro"] * 2 + ["x"] * 2),   # size 4, 2 hits  (half the corpus, half the hits)
        _doc("B", ["ku-ro"] * 1 + ["x"] * 1),   # size 2, 1 hit
        _doc("C", ["ku-ro"] * 1 + ["x"] * 1),   # size 2, 1 hit
    ]
    assert stats.dispersion(docs, "ku-ro").dp == pytest.approx(0.0)


def test_dispersion_unknown_item_raises():
    with pytest.raises(ValueError, match="does not occur"):
        stats.dispersion([_doc("A", ["pa-ro"])], "nope")


def test_dispersions_ranking_and_filters():
    docs = [_doc(f"D{i}", (["to-so"] if i == 0 else []) + ["pa-ro"] * 3) for i in range(4)]
    rows = stats.dispersions(docs, min_frequency=2)
    assert [r.item for r in rows] == ["pa-ro"]  # "to-so" (freq 1) filtered out
    assert rows[0].dp_norm < 0.2
    top = stats.dispersions(docs, min_frequency=1, top=1)
    assert len(top) == 1


def test_dispersion_signs_kind():
    docs = [_doc("A", ["ku-ro"]), _doc("B", ["ku-ni-su"])]
    d = stats.dispersion(docs, "ku", kind="signs")
    assert d.frequency == 2 and d.range == 2


# ── keyness ────────────────────────────────────────────────────────────────


def test_keyness_matches_hand_computed_g2():
    target = [_doc("T", ["ka-ko"] * 8 + ["x"] * 92)]      # 8/100
    reference = [_doc("R", ["ka-ko"] * 2 + ["x"] * 98)]   # 2/100
    row = next(r for r in stats.keyness(target, reference) if r.item == "ka-ko")
    # direct 4-cell G² on (8, 92, 2, 98)
    o = [8, 92, 2, 98]
    e = [100 * 10 / 200, 100 * 190 / 200, 100 * 10 / 200, 100 * 190 / 200]
    g2 = 2 * sum(oi * math.log(oi / ei) for oi, ei in zip(o, e, strict=True))
    assert row.log_likelihood == pytest.approx(g2)
    assert row.log_ratio == pytest.approx(math.log2((8 / 100) / (2 / 100)))  # = 2 doublings
    assert 0 < row.p_value < 0.05


def test_keyness_direction_and_symmetry():
    a = [_doc("A", ["ku-ro"] * 6 + ["pa-ro"] * 4)]
    b = [_doc("B", ["ku-ro"] * 1 + ["pa-ro"] * 9)]
    ab = {r.item: r for r in stats.keyness(a, b, min_target=1)}
    ba = {r.item: r for r in stats.keyness(b, a, min_target=1)}
    assert ab["ku-ro"].log_ratio > 0 > ba["ku-ro"].log_ratio
    assert ab["ku-ro"].log_likelihood == pytest.approx(ba["ku-ro"].log_likelihood)
    assert ab["ku-ro"].log_ratio == pytest.approx(-ba["ku-ro"].log_ratio)


def test_keyness_zero_count_smoothing_is_finite():
    target = [_doc("T", ["qa-si-re-u"] * 5 + ["x"] * 5)]
    reference = [_doc("R", ["x"] * 10)]
    row = next(r for r in stats.keyness(target, reference) if r.item == "qa-si-re-u")
    assert math.isfinite(row.log_ratio) and row.log_ratio > 0
    assert row.reference_count == 0


def test_keyness_underuse_surfaces_via_reference_frequency():
    target = [_doc("T", ["x"] * 50)]
    reference = [_doc("R", ["di-we"] * 10 + ["x"] * 40)]
    rows = stats.keyness(target, reference)
    row = next(r for r in rows if r.item == "di-we")
    assert row.target_count == 0 and row.log_ratio < 0  # marked underuse, not dropped


def test_keyness_empty_corpus_raises():
    with pytest.raises(ValueError, match="countable"):
        stats.keyness([_doc("T", [])], [_doc("R", ["x"])])


# ── bootstrap ──────────────────────────────────────────────────────────────


def _mean_words(docs) -> float:
    return sum(len(d.tokens) for d in docs) / len(docs)


def test_bootstrap_reproducible_and_brackets_estimate():
    docs = [_doc(f"D{i}", ["w"] * n) for i, n in enumerate([2, 4, 6, 8, 10, 12])]
    ci1 = stats.bootstrap_ci(docs, _mean_words, n_resamples=499, seed=42)
    ci2 = stats.bootstrap_ci(docs, _mean_words, n_resamples=499, seed=42)
    assert ci1 == ci2  # deterministic by default
    assert ci1.estimate == pytest.approx(7.0)
    assert ci1.low <= ci1.estimate <= ci1.high
    assert ci1.low > 0


def test_bootstrap_wider_at_higher_level():
    docs = [_doc(f"D{i}", ["w"] * n) for i, n in enumerate([1, 3, 5, 7, 9, 11, 13, 15])]
    narrow = stats.bootstrap_ci(docs, _mean_words, level=0.80, seed=7)
    wide = stats.bootstrap_ci(docs, _mean_words, level=0.99, seed=7)
    assert (wide.high - wide.low) >= (narrow.high - narrow.low)


def test_bootstrap_input_validation():
    with pytest.raises(ValueError, match="at least 2"):
        stats.bootstrap_ci([_doc("A", ["w"])], _mean_words)
    docs = [_doc("A", ["w"]), _doc("B", ["w", "w"])]
    with pytest.raises(ValueError, match="level"):
        stats.bootstrap_ci(docs, _mean_words, level=1.5)


# ── coercion + CLI ─────────────────────────────────────────────────────────


def test_accepts_corpus_objects():
    import aegean

    c = aegean.load("linearb")
    rows = stats.dispersions(c, min_frequency=2, top=5)
    assert rows and all(0 <= r.dp_norm <= 1 for r in rows)


def test_cli_dispersion_and_keyness_run():
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    app = _build_app()
    runner = CliRunner()
    r = runner.invoke(app, ["dispersion", "lineara", "--top", "3", "--json"])
    assert r.exit_code == 0, r.output
    r2 = runner.invoke(app, ["keyness", "lineara", "--site", "Haghia Triada", "--top", "3", "--json"])
    assert r2.exit_code == 0, r2.output
    r3 = runner.invoke(app, ["keyness", "lineara", "--json"])  # no reference, no filter
    assert r3.exit_code == 1
