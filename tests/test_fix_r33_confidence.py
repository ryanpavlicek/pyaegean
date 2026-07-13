"""Regression tests for the R33 confidence contract fixes.

Three pinned behaviours, matching the corrected prose in ``aegean.greek.pipeline`` /
``aegean._view`` / the ``aegean greek`` CLI ``--confidence`` help:

1. **The calibrated lemma confidence covers the model's internal training-form lookup.**
   Within the neural pipeline a lemma resolved by the model's internal ``lookup_form`` /
   ``lookup_form_upos`` table is ``LemmaSource.NEURAL_LOOKUP`` and carries a float calibrated
   confidence, *even when the lemma equals the surface form* (a nominative), because the
   calibration target is composed-lemma correctness (script + train-only lookup). Only a
   lemma the model does not itself produce (an identity fall-through / punctuation) carries
   ``None``. Proven deterministically with a lookup-populated stub and, when the shipped
   model is cached, through the real ``grc-joint`` bundle.

2. **The offline cascade is a clean no-op for confidence** (no model to calibrate): both
   fields stay ``None``, never a raise.

3. **The bundled calibration ships and loads**; a *corrupt* or *partial* bundled
   calibration raises `UncalibratedConfidenceError` with actionable guidance (never a raw
   ``JSONDecodeError`` / ``ValueError``, never a fall-back to an uncalibrated softmax).
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _isolate_state():
    """Save/restore the default runtime, compatibility shim, and calibration."""
    from aegean.greek import calibrate, joint, runtime

    prev_active = joint._ACTIVE
    prev_pipeline = runtime.default_pipeline()
    prev_cal = calibrate.active()
    joint._ACTIVE = None
    calibrate.disable_calibration()
    yield
    joint._ACTIVE = prev_active
    runtime._set_default_pipeline(prev_pipeline)
    if prev_cal is None:
        calibrate.disable_calibration()
    else:
        calibrate.use_calibration(prev_cal)


def _synthetic_calibration(t_upos: float = 1.5, t_lemma: float = 1.5):
    from aegean.greek.calibrate import Calibration

    return Calibration(
        temperature={"upos": t_upos, "lemma": t_lemma},
        fitted_on="synthetic (unit test)", date="2026-07-11",
        ece_before={"upos": 0.0, "lemma": 0.0}, ece_after={"upos": 0.0, "lemma": 0.0},
        n={"upos": 0, "lemma": 0},
    )


def _make_lookup_stub(lookup_form):
    """A `_JointModel` whose lemmas resolve via a populated internal training-form lookup.

    ``m.trees`` is empty, so a word absent from ``lookup_form`` gets the honest identity
    fall-through (``resolved=False``); a word present in ``lookup_form`` is composed by the
    lookup (``resolved=True``), which is the model's internal training-form lookup path."""
    import numpy as np

    from aegean.greek import joint

    m = object.__new__(joint._JointModel)
    m._np = np
    m.inv = {"upos": {0: "DET", 1: "NOUN", 2: "VERB", 3: "X"},
             "deprel": {0: "det", 1: "nsubj", 2: "root", 3: "dep"}}
    for i in range(9):
        m.inv[f"x{i}"] = {0: "-", 1: "l", 2: "n", 3: "v"}
    m.trees = []  # no edit scripts: non-lookup words fall through to the honest identity
    m.lookup_form = dict(lookup_form)
    m.lookup_form_upos = {}
    m.lookup_lower = {}

    def fake_run(words):
        n = len(words)
        keep = list(range(n))
        word_pos = [k + 1 for k in keep]  # one subword per word after <s>
        seq = n + 2
        upos = np.full((1, seq, 4), -9.0)
        for j in keep:
            upos[0, word_pos[j], 1] = 3.0  # a clear NOUN peak
        out = {"upos": upos}
        for i in range(9):
            xa = np.full((1, seq, 4), -9.0)
            for j in range(n):
                xa[0, word_pos[j], 0] = 9.0
            out[f"x{i}"] = xa
        nw = n
        arc = np.full((1, nw, nw + 1), -9.0)
        rel = np.full((1, 4, nw, nw + 1), -9.0)
        for j in range(nw):
            h = j + 2 if j < nw - 1 else 0
            arc[0, j, h] = 9.0
            rel[0, min(j, 2) if j < nw - 1 else 2, j, h] = 9.0
        out["arc"] = arc
        out["rel"] = rel
        out["lemma"] = np.tile(np.array([2.0, 0.0]), (nw, 1))[None, :, :]  # (1, nw, 2)
        out["_word_pos"] = word_pos
        out["_kept"] = keep
        return out

    m._run = fake_run  # type: ignore[method-assign]
    return m


# ── (1) the calibrated lemma confidence covers the internal training-form lookup ──
def test_lookup_composed_lemma_carries_float_confidence_even_when_identical_surface():
    pytest.importorskip("numpy")
    import unicodedata

    from aegean.greek import calibrate, joint
    from aegean.greek.lemmatize import LemmaSource
    from aegean.greek.pipeline import pipeline

    # "λόγος" is resolved by the internal training-form lookup to a lemma EQUAL to its
    # surface form (a nominative); "ὁ" is absent from the lookup, so it is an identity
    # fall-through. The lookup lemma must still carry a calibrated number.
    logos = unicodedata.normalize("NFC", "λόγος")
    joint._ACTIVE = _make_lookup_stub({logos: logos})
    calibrate.use_calibration(_synthetic_calibration(1.3, 1.9))

    recs = {r.text: r for r in pipeline("ὁ λόγος", with_confidence=True)}
    assert set(recs) == {"ὁ", "λόγος"}

    lookup = recs["λόγος"]
    assert lookup.lemma == logos                         # composed by the lookup
    assert lookup.lemma_source is LemmaSource.NEURAL_LOOKUP  # exact branch, not IDENTITY
    assert isinstance(lookup.lemma_confidence, float)     # ...and it carries confidence
    assert 0.0 <= lookup.lemma_confidence <= 1.0

    ident = recs["ὁ"]
    assert ident.lemma_source is LemmaSource.IDENTITY
    assert ident.lemma_confidence is None                 # the evidence class speaks for it
    # UPOS is always a neural prediction here -> both tokens carry a UPOS confidence
    assert isinstance(lookup.upos_confidence, float)
    assert isinstance(ident.upos_confidence, float)


def test_real_grc_joint_lookup_lemma_has_float_confidence():
    pytest.importorskip("numpy")
    pytest.importorskip("onnxruntime")
    pytest.importorskip("tokenizers")

    from aegean import data

    spec = data._REMOTE.get("grc-joint")
    if spec is None or not data.is_downloaded(spec, data.cache_dir()):
        pytest.skip("grc-joint model is not cached (would trigger a ~173 MB download)")

    from aegean.greek import calibrate, joint, use_neural_pipeline

    use_neural_pipeline()
    m = joint.active()
    assert m is not None and m.lookup_form, "the shipped model ships a form lookup"
    calibrate.use_calibration()  # the shipped bundled default calibration

    # Find a lookup key that decodes to a single kept token, then confirm the composed
    # lemma came from the internal lookup and carries a float calibrated confidence.
    picked = None
    for key in list(m.lookup_form)[:400]:
        if not key or " " in key:
            continue
        ana = m.analyze([key], with_probs=True)
        if ana.lemma_resolved and ana.lemma_resolved[0] and ana.lemma_script_prob[0] is not None:
            picked = (key, ana)
            break
    assert picked is not None, "no lookup key decoded to a single token"
    key, ana = picked

    expected = m.lookup_form_upos.get(f"{key}|{ana.upos[0]}") or m.lookup_form.get(key)
    assert ana.lemma[0] == expected            # composed by the internal training-form lookup
    assert ana.lemma_resolved[0] is True
    assert isinstance(ana.lemma_script_prob[0], float)
    assert 0.0 <= ana.lemma_script_prob[0] <= 1.0
    assert isinstance(ana.upos_prob[0], float)


# ── (1b) the offline cascade is a clean no-op for confidence ──────────────────────
def test_offline_pipeline_confidence_is_none_and_never_raises():
    from aegean.greek import joint
    from aegean.greek.pipeline import pipeline

    joint._ACTIVE = None  # the offline cascade: no model to calibrate
    recs = pipeline("ἦν νόμου", with_confidence=True)
    assert recs
    assert all(r.upos_confidence is None and r.lemma_confidence is None for r in recs)


# ── (3) the bundled calibration ships and loads ───────────────────────────────────
def test_bundled_calibration_ships_and_loads():
    from aegean.greek import calibrate

    cal = calibrate.use_calibration()  # no arg -> the shipped bundled default
    assert set(cal.temperature) == set(calibrate.HEADS)
    assert all(t > 0 for t in cal.temperature.values())
    assert calibrate.active() is cal


# ── (2) a corrupt / partial bundled calibration fails loudly ──────────────────────
def test_corrupt_bundled_calibration_raises_uncalibrated(monkeypatch):
    import aegean.data as data
    from aegean.greek import calibrate

    def _corrupt(*parts):
        raise json.JSONDecodeError("Expecting value", "", 0)

    monkeypatch.setattr(data, "load_bundled_json", _corrupt)
    with pytest.raises(calibrate.UncalibratedConfidenceError, match="could not be loaded"):
        calibrate.use_calibration()
    assert calibrate.active() is None  # nothing was loaded; no uncalibrated fall-back


def test_partial_bundled_calibration_missing_lemma_head_raises(monkeypatch):
    import aegean.data as data
    from aegean.greek import calibrate

    def _partial(*parts):
        return {"temperature": {"upos": 1.34}}  # the 'lemma' temperature head dropped

    monkeypatch.setattr(data, "load_bundled_json", _partial)
    with pytest.raises(calibrate.UncalibratedConfidenceError, match="could not be loaded"):
        calibrate.use_calibration()
    assert calibrate.active() is None
