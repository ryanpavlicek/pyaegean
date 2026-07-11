"""Calibration math + record, pinned by output contract (hand-computed / property).

Covers the whole `aegean.greek.calibrate` surface:
- ``temperature_softmax`` / ``top1_confidence`` against hand-computed softmax values,
  and the invariant that a temperature never moves the argmax;
- ``ece`` against a hand-computed small case (and the p==1.0 last-bin edge);
- ``fit_temperature`` as a property test: an overconfident head fits T>1 and lowers
  ECE/NLL; a well-calibrated head fits T≈1;
- ``Calibration`` JSON round-trip (to_dict/from_dict + save/load) and its validation;
- adversarial inputs: temperature<=0, NaN/inf logits, empty fold, shape mismatch,
  bad bracket, n_bins<1 — a clean error, never a raw traceback or silent wrong number;
- ``use_calibration`` / ``disable_calibration`` / ``active`` from a Calibration, a
  dict, and a path, plus the bundled-default load-failure error (missing install).
"""

from __future__ import annotations

import math

import pytest

np = pytest.importorskip("numpy")

from aegean.greek import calibrate  # noqa: E402
from aegean.greek.calibrate import (  # noqa: E402
    Calibration,
    UncalibratedConfidenceError,
    ece,
    fit_temperature,
    temperature_softmax,
    top1_confidence,
)


@pytest.fixture(autouse=True)
def _reset_active():
    calibrate.disable_calibration()
    yield
    calibrate.disable_calibration()


# ── temperature_softmax / top1_confidence: hand-computed ─────────────────────
def test_temperature_softmax_hand_computed():
    # softmax([2, 0]) = [e^2, 1] / (e^2 + 1)
    p = temperature_softmax([2.0, 0.0], 1.0)
    denom = math.exp(2.0) + 1.0
    assert p[0] == pytest.approx(math.exp(2.0) / denom)
    assert p[1] == pytest.approx(1.0 / denom)
    assert float(p.sum()) == pytest.approx(1.0)

    # T=2 flattens: softmax([1, 0])
    p2 = temperature_softmax([2.0, 0.0], 2.0)
    denom2 = math.exp(1.0) + 1.0
    assert p2[0] == pytest.approx(math.exp(1.0) / denom2)  # ≈ 0.731059


def test_top1_confidence_hand_computed_and_shapes():
    assert float(top1_confidence([2.0, 0.0], 1.0)) == pytest.approx(
        math.exp(2.0) / (math.exp(2.0) + 1.0)
    )
    # 2-D: one confidence per row
    conf = top1_confidence([[2.0, 0.0], [0.0, 0.0]], 1.0)
    assert conf.shape == (2,)
    assert float(conf[1]) == pytest.approx(0.5)  # a tie is 0.5


def test_temperature_never_moves_the_argmax():
    logits = np.array([[0.2, 3.1, -1.0, 2.9]])
    a1 = int(temperature_softmax(logits, 0.3).argmax(-1)[0])
    a2 = int(temperature_softmax(logits, 8.0).argmax(-1)[0])
    assert a1 == a2 == 1  # only confidence changes, never the predicted label


def test_temperature_softmax_rejects_non_positive_temperature():
    for bad in (0.0, -1.0, -0.5):
        with pytest.raises(ValueError, match="temperature must be"):
            temperature_softmax([1.0, 2.0], bad)
    with pytest.raises(ValueError, match="finite"):
        temperature_softmax([1.0, 2.0], float("nan"))


# ── ece: hand-computed ───────────────────────────────────────────────────────
def test_ece_hand_computed_two_bins():
    # bins over [0,1] with n_bins=2: 0.1 -> bin0, 0.9 -> bin1
    # bin0: conf .1, acc 0 -> gap .1 (weight 1/2); bin1: conf .9, acc 1 -> gap .1 (weight 1/2)
    assert ece([0.1, 0.9], [0, 1], n_bins=2) == pytest.approx(0.1)


def test_ece_single_bin_and_perfect():
    # four items in one bin: conf .6, acc .75 -> ECE .15
    assert ece([0.6, 0.6, 0.6, 0.6], [1, 1, 1, 0], n_bins=5) == pytest.approx(0.15)
    # perfectly calibrated (and p==1.0 lands in the last bin, not out of range)
    assert ece([0.0, 1.0], [0, 1], n_bins=2) == pytest.approx(0.0)


def test_ece_empty_is_zero_and_validates_inputs():
    assert ece([], [], n_bins=10) == 0.0
    with pytest.raises(ValueError, match="same length"):
        ece([0.1, 0.2], [1], n_bins=5)
    with pytest.raises(ValueError, match="non-finite"):
        ece([0.1, float("nan")], [1, 0], n_bins=5)
    with pytest.raises(ValueError, match="n_bins"):
        ece([0.5], [1], n_bins=0)


# ── fit_temperature: property tests ──────────────────────────────────────────
def _nll(logits, correct, t):
    conf = top1_confidence(np.asarray(logits), t)
    c = np.clip(conf, 1e-12, 1 - 1e-12)
    y = np.asarray(correct, dtype=float)
    return float(-(y * np.log(c) + (1 - y) * np.log(1 - c)).mean())


def test_fit_temperature_flattens_an_overconfident_head():
    # identical peaked logits (top-1 conf ≈ 0.9526 at T=1) but only 50% correct:
    # the fit must raise T (lower the confidence toward the accuracy) and cut ECE.
    logits = np.tile(np.array([3.0, 0.0]), (200, 1))
    correct = np.array([1, 0] * 100)
    t = fit_temperature(logits, correct)
    assert t > 1.5
    before = ece(top1_confidence(logits, 1.0), correct)
    after = ece(top1_confidence(logits, t), correct)
    assert after < before
    assert _nll(logits, correct, t) <= _nll(logits, correct, 1.0) + 1e-9


def test_fit_temperature_leaves_a_calibrated_head_near_one():
    # logits whose top-1 conf is exactly 0.7, with 70% correct -> already calibrated.
    a = math.log(0.7 / 0.3)  # softmax([a, 0]).max() == 0.7
    logits = np.tile(np.array([a, 0.0]), (100, 1))
    correct = np.array([1] * 70 + [0] * 30)
    t = fit_temperature(logits, correct)
    assert 0.8 < t < 1.25
    assert ece(top1_confidence(logits, t), correct) == pytest.approx(0.0, abs=0.02)


def test_fit_temperature_adversarial_inputs():
    good = np.array([[2.0, 0.0], [1.0, 3.0]])
    with pytest.raises(ValueError, match="empty fold"):
        fit_temperature(np.empty((0, 2)), np.empty((0,)))
    with pytest.raises(ValueError, match="non-finite"):
        fit_temperature(np.array([[float("nan"), 0.0], [1.0, 2.0]]), [1, 0])
    with pytest.raises(ValueError, match="same number of items"):
        fit_temperature(good, [1, 0, 1])
    with pytest.raises(ValueError, match="2-D"):
        fit_temperature(np.array([1.0, 2.0, 3.0]), [1])
    with pytest.raises(ValueError, match="bracket"):
        fit_temperature(good, [1, 0], bracket=(2.0, 1.0))
    with pytest.raises(ValueError, match="bracket"):
        fit_temperature(good, [1, 0], bracket=(-1.0, 5.0))


# ── Calibration record: round-trip + validation ──────────────────────────────
def _sample_calibration() -> Calibration:
    return Calibration(
        temperature={"upos": 1.42, "lemma": 2.07},
        fitted_on="UD Ancient Greek-Perseus dev (grc-joint-v3, CPU)",
        date="2026-07-11",
        ece_before={"upos": 0.031, "lemma": 0.058},
        ece_after={"upos": 0.009, "lemma": 0.017},
        n={"upos": 22135, "lemma": 22135},
        notes="test fixture",
    )


def test_calibration_json_round_trip_dict_and_file(tmp_path):
    cal = _sample_calibration()
    assert Calibration.from_dict(cal.to_dict()) == cal
    p = tmp_path / "calibration.json"
    cal.save(p)
    assert Calibration.load(p) == cal
    # to_dict is JSON-ready (no numpy/enum leaks) and keeps full precision
    import json

    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["temperature"]["upos"] == pytest.approx(1.42)
    assert d["n"]["lemma"] == 22135


def test_calibration_validation():
    with pytest.raises(ValueError, match="missing a temperature"):
        Calibration(temperature={"upos": 1.0})  # no lemma head
    with pytest.raises(ValueError, match="finite positive"):
        Calibration(temperature={"upos": 0.0, "lemma": 1.0})
    with pytest.raises(ValueError, match="finite positive"):
        Calibration(temperature={"upos": -1.0, "lemma": 1.0})
    with pytest.raises(ValueError, match="finite positive"):
        Calibration(temperature={"upos": float("nan"), "lemma": 1.0})


# ── use_calibration / disable_calibration / active ───────────────────────────
def test_use_calibration_from_object_dict_and_path(tmp_path):
    cal = _sample_calibration()
    assert calibrate.active() is None

    assert calibrate.use_calibration(cal) is cal
    assert calibrate.active() is cal

    calibrate.disable_calibration()
    assert calibrate.active() is None

    got = calibrate.use_calibration(cal.to_dict())
    assert got == cal and calibrate.active() == cal

    p = tmp_path / "c.json"
    cal.save(p)
    calibrate.disable_calibration()
    from_path = calibrate.use_calibration(str(p))
    assert from_path == cal and calibrate.active() == cal


def test_bundled_default_missing_raises_clearly(monkeypatch):
    # The bundled calibration.json ships and loads; if the install is broken so the file
    # is missing, the no-arg form must fail loudly with actionable guidance, not fall
    # back to an uncalibrated number.
    import aegean.data as data

    def _missing(*parts):
        raise FileNotFoundError("no such bundled file")

    monkeypatch.setattr(data, "load_bundled_json", _missing)
    with pytest.raises(UncalibratedConfidenceError, match="bundled calibration could not be loaded"):
        calibrate.use_calibration()
    assert calibrate.active() is None  # nothing was loaded
