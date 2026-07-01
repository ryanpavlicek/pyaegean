"""Coverage backfill for previously untested public surface (the correctness-test rule).

Four gaps, each verified against a known answer or invariant, all offline:

- ``greek.bootstrap_ud`` on the bundled 2-sentence UD fixture (the evaluator is fetched
  once and cached; the test skips only if it is unavailable offline, the test_ud pattern);
- ``viz.plot_correspondence_analysis`` on a block-structured table (Agg backend, asserting
  the drawn points, labels, and sign structure, not merely that it runs);
- the 0.14.4 gazetteer trust-pass coordinates, pinned so a drifted bundled coordinate is
  caught without network (the weekly Pleiades check needs network; this does not);
- the ``use_neural_lemmatizer`` activation wiring, with the fetch + model loader stubbed
  (the routing tests in test_neural_lemmatizer.py inject ``_ACTIVE`` directly, so the
  public entry point itself had no coverage).
"""

from __future__ import annotations

from pathlib import Path

import pytest

CONLLU = Path(__file__).parent / "fixtures" / "ud" / "sample-ud-test.conllu"


# --- bootstrap_ud on the bundled fixture ------------------------------------------


def _require_evaluator() -> None:
    """Fetch the official conll18 evaluator once; skip if offline (the test_ud pattern)."""
    from aegean.data import cache_dir
    from aegean.greek.ud import _CACHE_SUBDIR

    if not (cache_dir() / _CACHE_SUBDIR / "conll18_ud_eval.py").exists():
        try:
            from aegean.greek.ud import _eval_module

            _eval_module()
        except Exception as exc:
            pytest.skip(f"official evaluator unavailable offline: {exc}")


def test_bootstrap_ud_brackets_point_estimate_and_is_seeded() -> None:
    _require_evaluator()
    from aegean.greek.ud import bootstrap_ud, evaluate_on_ud

    res = bootstrap_ud(source=CONLLU, parse=False, n_resamples=60, seed=7)
    # without a parser, uas/las are dropped from the default metric set
    assert set(res) == {"upos", "xpos", "ufeats", "lemma"}
    point = evaluate_on_ud("perseus", "test", source=CONLLU, parse=False)
    for metric, ci in res.items():
        assert ci.n_resamples == 60 and ci.level == 0.95, metric
        # the band brackets the full-fold statistic (a token-weighted mean of the
        # per-sentence accuracies, so it lies within the resample extremes)
        assert 0.0 <= ci.low <= ci.estimate <= ci.high <= 1.0, metric
        # ``estimate`` is the full-fold score itself, not a resample mean
        assert ci.estimate == pytest.approx(point[metric]), metric
    # deterministic under a fixed seed
    assert bootstrap_ud(source=CONLLU, parse=False, n_resamples=60, seed=7) == res


# --- plot_correspondence_analysis --------------------------------------------------


def _block_ca():  # type: ignore[no-untyped-def]
    """A 4×4 block-structured CA (the test_multivariate fixture): r0/r1 pair with A/B."""
    from aegean.analysis.multivariate import correspondence_analysis

    ca = correspondence_analysis(
        ["r0", "r1", "r2", "r3"],
        ["A", "B", "C", "D"],
        [[30, 25, 1, 2], [28, 31, 2, 1], [1, 2, 33, 27], [2, 1, 26, 30]],
    )
    assert ca is not None
    return ca


def test_plot_correspondence_analysis_draws_points_and_labels() -> None:
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    from aegean.viz import plot_correspondence_analysis

    ca = _block_ca()
    ax = plot_correspondence_analysis(ca)
    try:
        # two scatter layers, drawn columns-first then rows, one point per CA point
        col_pts, row_pts = ax.collections[0], ax.collections[1]
        assert len(col_pts.get_offsets()) == len(ca.cols) == 4
        assert len(row_pts.get_offsets()) == len(ca.rows) == 4
        # the percentile layout keeps every plotted point inside the [-1, 1]² box
        for x, y in [*col_pts.get_offsets(), *row_pts.get_offsets()]:
            assert -1.0 <= float(x) <= 1.0 and -1.0 <= float(y) <= 1.0
        # the block structure survives the scaling: r0/r1 on one side of axis 1,
        # r2/r3 on the other (per-axis scaling never flips a sign)
        rx = [float(x) for x, _ in row_pts.get_offsets()]
        assert rx[0] * rx[1] > 0 and rx[2] * rx[3] > 0 and rx[0] * rx[2] < 0
        # every row and (label_top >= n_cols) every column is labelled
        assert {t.get_text() for t in ax.texts} == {"r0", "r1", "r2", "r3", "A", "B", "C", "D"}
        assert "% of inertia" in ax.get_title()
    finally:
        import matplotlib.pyplot as plt

        plt.close("all")


def test_plot_correspondence_analysis_label_top_takes_heaviest() -> None:
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    from aegean.viz import plot_correspondence_analysis

    ca = _block_ca()
    ax = plot_correspondence_analysis(ca, label_top=2)
    try:
        heaviest = {p.label for p in sorted(ca.cols, key=lambda p: -p.mass)[:2]}
        assert {t.get_text() for t in ax.texts} == {"r0", "r1", "r2", "r3"} | heaviest
    finally:
        import matplotlib.pyplot as plt

        plt.close("all")


# --- the 0.14.4 gazetteer trust pass, pinned offline --------------------------------

# The corrected coordinates from the trust pass (validated against the Pleiades
# reprPoints). scripts/check_gazetteer.py re-validates against Pleiades weekly over the
# network; this pin catches a drifted *bundled* value with no network at all.
_TRUST_PASS = {
    "Zominthos": (35.249, 24.887),
    "Kythera": (36.23, 23.029),
    "Pylos": (36.952, 21.66),
    "Cyprus": (34.995, 33.222),
    "Margiana": (37.663, 62.191),
}


def test_gazetteer_trust_pass_coordinates_pinned() -> None:
    from aegean.geo import site_coordinates

    coords = site_coordinates()
    assert len(coords) == 56
    assert sum(1 for s in coords.values() if s.pleiades) == 40
    assert [n for n, s in coords.items() if s.is_contested] == ["Margiana"]
    for site, (lat, lon) in _TRUST_PASS.items():
        sc = coords[site]
        assert sc.lat == pytest.approx(lat, abs=5e-3), site
        assert sc.lon == pytest.approx(lon, abs=5e-3), site


# --- use_neural_lemmatizer activation wiring ----------------------------------------


class _StubNeural:
    """Stands in for a loaded ONNX model: records the constructor dir and predict calls."""

    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self.calls: list[str] = []

    def predict(self, form: str) -> str:
        self.calls.append(form)
        return {"νόμου": "νόμος"}.get(form, form)


def test_use_neural_lemmatizer_activates_and_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    import aegean.greek as greek
    from aegean.greek import joint, treebank
    from aegean.greek import neural_lemmatizer as nl

    fetched: list[tuple[str, bool]] = []

    def fake_fetch(name: str, *, force: bool = False) -> Path:
        fetched.append((name, force))
        return Path("stub-model-dir")

    monkeypatch.setattr(nl, "fetch", fake_fetch)
    monkeypatch.setattr(nl, "_NeuralModel", _StubNeural)
    # quiet the higher-priority backends so the cascade reaches the neural tier,
    # and record _ACTIVE so monkeypatch restores it after the test
    monkeypatch.setattr(joint, "_ACTIVE", None)
    monkeypatch.setattr(treebank, "_ACTIVE", None)
    monkeypatch.setattr(nl, "_ACTIVE", None)

    greek.use_neural_lemmatizer()
    model = nl.active()
    assert isinstance(model, _StubNeural)
    assert fetched == [(nl._DATASET, False)]  # the pinned asset, no force
    assert model.model_dir == Path("stub-model-dir")  # the fetched dir reaches the loader
    # lemmatize() now routes through the activated backend
    assert greek.lemmatize("νόμου") == "νόμος"
    assert model.calls == ["νόμου"]
    # force=True is passed through to the fetch (a re-download, a fresh model)
    greek.use_neural_lemmatizer(force=True)
    assert fetched[-1] == (nl._DATASET, True)
    assert isinstance(nl.active(), _StubNeural) and nl.active() is not model
    # deactivation restores the offline cascade: the stub is no longer consulted
    greek.disable_neural_lemmatizer()
    assert nl.active() is None
    n_calls = len(model.calls)
    greek.lemmatize("νόμου")
    assert len(model.calls) == n_calls
