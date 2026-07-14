"""The confidence seam end-to-end, through the stubbed joint model (no ONNX).

Three dimensions, all offline (the tests/test_joint.py stub pattern + a synthetic
Calibration):

- **default-off byte-identity**: `analyze` without the feature is byte-identical to a
  build without it (the two new fields stay empty ``()``); ``pipeline`` / ``explain``
  default output is unchanged.
- **raises-without-calibration**: asking for confidence with the pipeline active but no
  calibration loaded raises `UncalibratedConfidenceError` at every entry point — a raw
  softmax is never exposed.
- **the calibrated path**: with a synthetic calibration loaded, the surfaced confidence
  is the temperature-scaled top-1 softmax of the SAME logits the argmax reads (proven by
  recomputing it independently), undecoded tokens carry ``None``, lookup/identity lemmas
  carry no lemma confidence, and `explain_pipeline` shows the calibrated phrase.
"""

from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")

from aegean.greek import calibrate, joint  # noqa: E402
from aegean.greek.calibrate import Calibration  # noqa: E402
from aegean.greek.lemmatize import LemmaSource  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_state():
    joint._ACTIVE = None
    calibrate.disable_calibration()
    yield
    joint._ACTIVE = None
    calibrate.disable_calibration()


def _synthetic_calibration(t_upos: float = 1.0, t_lemma: float = 1.0) -> Calibration:
    return Calibration(
        temperature={"upos": t_upos, "lemma": t_lemma},
        fitted_on="synthetic (unit test)", date="2026-07-11",
        ece_before={"upos": 0.0, "lemma": 0.0}, ece_after={"upos": 0.0, "lemma": 0.0},
        n={"upos": 0, "lemma": 0},
    )


# ── a controllable stub whose exact logits the test knows ────────────────────
def _controllable_stub(upos_logits, lemma_logits, *, kept=None):
    """A _JointModel whose _run emits the given per-word UPOS + lemma-script logits.

    ``upos_logits[w]`` is the length-4 UPOS logit vector for word ``w``; ``lemma_logits[w]``
    its script-head logit vector. ``kept`` (default: all words) is the decoded-word index
    list, so a truncation fallback (a word with no logits) can be simulated."""
    m = object.__new__(joint._JointModel)
    m._np = np
    m.inv = {"upos": {0: "DET", 1: "NOUN", 2: "VERB", 3: "X"},
             "deprel": {0: "det", 1: "nsubj", 2: "root", 3: "dep"}}
    for i in range(9):
        m.inv[f"x{i}"] = {0: "-", 1: "l", 2: "n", 3: "v"}
    n_scripts = len(lemma_logits[0])
    m.trees = [["sub", f"lem{k}"] for k in range(n_scripts)]
    m.lookup_form = {}
    m.lookup_form_upos = {}
    m.lookup_lower = {}

    def fake_run(words):
        n = len(words)
        keep = list(range(n)) if kept is None else list(kept)
        nw = len(keep)
        word_pos = [k + 1 for k in keep]  # 1 subword per kept word after <s>
        seq = n + 2
        upos = np.full((1, seq, 4), -9.0)
        for j, w in enumerate(keep):
            upos[0, word_pos[j], :] = upos_logits[w]
        out = {"upos": upos}
        for i in range(9):
            xa = np.full((1, seq, 4), -9.0)
            for j in range(nw):
                xa[0, word_pos[j], 0] = 9.0
            out[f"x{i}"] = xa
        arc = np.full((1, nw, nw + 1), -9.0)
        rel = np.full((1, 4, nw, nw + 1), -9.0)
        for j in range(nw):
            h = j + 2 if j < nw - 1 else 0
            arc[0, j, h] = 9.0
            rel[0, min(j, 2) if j < nw - 1 else 2, j, h] = 9.0
        out["arc"] = arc
        out["rel"] = rel
        lem = np.zeros((1, nw, n_scripts))
        for j, w in enumerate(keep):
            lem[0, j, :] = lemma_logits[w]
        out["lemma"] = lem
        out["_word_pos"] = word_pos
        out["_kept"] = keep
        return out

    m._run = fake_run  # type: ignore[method-assign]
    return m


# reuse the canonical stub (ὁ / λόγος / ἐστί → NEURAL / IDENTITY / NEURAL) for the surface
def _stub_model():
    from test_joint import _stub_model as base

    return base()


# ── default-off byte-identity ────────────────────────────────────────────────
def test_analyze_default_is_byte_identical_and_probs_empty():
    m = _controllable_stub([[2.0, 0, 0, 0], [0, 1.0, 0, 0]], [[1.0, 0.5], [0.3, 0.9]])
    words = ["a", "b"]
    default = m.analyze(words)
    assert default.upos_prob == () and default.lemma_script_prob == ()
    # with_probs=False is exactly the default path
    assert m.analyze(words, with_probs=False) == default
    # and confidence does not alter predictions or epistemic/coverage metadata
    assert default.complete is True and default.truncated is False
    assert default.analyzed == (True, True)
    assert default.lemma_source == (
        LemmaSource.NEURAL_EDIT,
        LemmaSource.NEURAL_EDIT,
    )


def test_empty_sentence_has_empty_prob_fields():
    m = _controllable_stub([[1.0, 0, 0, 0]], [[1.0, 0.0]])
    assert m.analyze([]) == joint.SentenceAnalysis((), (), (), (), (), (), (), ())


# ── raises without a calibration ─────────────────────────────────────────────
def test_with_probs_without_calibration_raises_everywhere():
    m = _stub_model()
    joint._ACTIVE = m
    with pytest.raises(calibrate.UncalibratedConfidenceError, match="uncalibrated"):
        m.analyze(["ὁ"], with_probs=True)
    with pytest.raises(calibrate.UncalibratedConfidenceError):
        m.analyze_batch([["ὁ"]], with_probs=True)
    with pytest.raises(calibrate.UncalibratedConfidenceError):
        joint.analyze_sentence(["ὁ"], with_probs=True)
    with pytest.raises(calibrate.UncalibratedConfidenceError):
        joint.analyze_sentences([["ὁ"]], batch_size=2, with_probs=True)

    from aegean.greek.explain import explain_pipeline
    from aegean.greek.pipeline import pipeline

    with pytest.raises(calibrate.UncalibratedConfidenceError):
        pipeline("ὁ λόγος", with_confidence=True)
    with pytest.raises(calibrate.UncalibratedConfidenceError):
        explain_pipeline("ὁ λόγος", with_confidence=True)


def test_stream_captures_calibration_before_global_state_changes():
    logits = [[2.0, 0.0, 0.0, 0.0]]
    lemma_logits = [[1.0, 0.5]]
    m = _controllable_stub(logits, lemma_logits)
    joint._ACTIVE = m
    calibrate.use_calibration(_synthetic_calibration(1.5, 1.5))
    stream = joint.iter_analyze_sentences(
        (["a"] for _ in range(2)), with_probs=True
    )

    first = next(stream)
    calibrate.use_calibration(_synthetic_calibration(9.0, 9.0))
    second = next(stream)

    assert first.upos_prob == second.upos_prob
    assert first.lemma_script_prob == second.lemma_script_prob
    assert first.upos_prob[0] == pytest.approx(
        float(calibrate.top1_confidence(np.array(logits[0]), 1.5))
    )
    assert first.upos_prob[0] != pytest.approx(
        float(calibrate.top1_confidence(np.array(logits[0]), 9.0))
    )


# ── the calibrated path: same logits, temperature applied ────────────────────
def test_probs_are_the_temperature_scaled_top1_of_the_same_logits():
    upos_logits = [[2.0, 0.0, 0.0, 0.0], [0.0, 1.5, 0.0, 0.0]]
    lemma_logits = [[1.0, 0.5], [0.3, 0.9]]
    m = _controllable_stub(upos_logits, lemma_logits)
    t_upos, t_lemma = 1.7, 2.3
    calibrate.use_calibration(_synthetic_calibration(t_upos, t_lemma))

    ana = m.analyze(["a", "b"], with_probs=True)
    for w in range(2):
        exp_u = float(calibrate.top1_confidence(np.array(upos_logits[w]), t_upos))
        exp_l = float(calibrate.top1_confidence(np.array(lemma_logits[w]), t_lemma))
        assert ana.upos_prob[w] == pytest.approx(exp_u)
        assert ana.lemma_script_prob[w] == pytest.approx(exp_l)
    # and the argmax-derived labels are unchanged by scaling (T never moves the argmax)
    assert ana.upos == ("DET", "NOUN")


def test_undecoded_token_carries_none_confidence():
    # word 1 is not in `kept` (a truncation fallback): no logits -> None confidence
    m = _controllable_stub([[2.0, 0, 0, 0], [0, 1.0, 0, 0]], [[1.0, 0.5], [0.3, 0.9]], kept=[0])
    calibrate.use_calibration(_synthetic_calibration())
    ana = m.analyze(["a", "b"], with_probs=True, long_input="partial")
    assert ana.upos_prob[0] is not None and ana.lemma_script_prob[0] is not None
    assert ana.upos_prob[1] is None and ana.lemma_script_prob[1] is None
    assert ana.upos[1] == "X"  # the honest truncation fallback


def test_batch_populates_probs_like_sequential():
    # the batch-capable stub backs `_run` and `_run_batch` with the SAME logits, so a
    # sequential/batched divergence in the prob fields would be a real padding/slicing bug
    from test_joint_batch import _batch_stub_model

    m = _batch_stub_model()
    calibrate.use_calibration(_synthetic_calibration(1.3, 1.9))
    words = ["ὁ", "λόγος", "ἐστί"]
    seq = m.analyze(list(words), with_probs=True)
    bat = m.analyze_batch([list(words)], with_probs=True)[0]
    assert bat.upos_prob == seq.upos_prob
    assert bat.lemma_script_prob == seq.lemma_script_prob
    assert all(p is not None for p in seq.upos_prob)


# ── the pipeline record surface ──────────────────────────────────────────────
def test_pipeline_confidence_fields_default_none_and_populate_on_request():
    from aegean.greek.pipeline import pipeline

    joint._ACTIVE = _stub_model()
    # default: no confidence anywhere (byte-identity with the pre-feature record)
    for r in pipeline("ὁ λόγος ἐστί"):
        assert r.upos_confidence is None and r.lemma_confidence is None

    calibrate.use_calibration(_synthetic_calibration(1.5, 1.5))
    recs = pipeline("ὁ λόγος ἐστί", with_confidence=True)
    assert [r.text for r in recs] == ["ὁ", "λόγος", "ἐστί"]
    # UPOS is always a neural prediction here -> every token has a upos_confidence
    assert all(r.upos_confidence is not None for r in recs)
    # lemma confidence is model-only: NEURAL yes, the IDENTITY fall-through (λόγος) None
    by_text = {r.text: r for r in recs}
    assert by_text["ὁ"].lemma_source is LemmaSource.NEURAL_LOOKUP
    assert by_text["ὁ"].lemma_confidence is not None
    assert by_text["ἐστί"].lemma_confidence is not None
    assert by_text["λόγος"].lemma_source is LemmaSource.IDENTITY
    assert by_text["λόγος"].lemma_confidence is None  # the evidence class speaks for it
    # confidences are probabilities
    for r in recs:
        assert 0.0 <= r.upos_confidence <= 1.0


def test_pipeline_punctuation_carries_no_lemma_confidence():
    from aegean.greek.pipeline import pipeline

    joint._ACTIVE = _stub_model()
    calibrate.use_calibration(_synthetic_calibration())
    # a PUNCT lemma is trivially its own lemma, not a model prediction -> no lemma number
    dot = [r for r in pipeline("ὁ .", with_confidence=True) if r.text == "."]
    assert dot and dot[0].lemma_source is LemmaSource.PUNCT
    assert dot[0].lemma_confidence is None


def test_pipeline_offline_confidence_is_none_not_an_error():
    from aegean.greek.pipeline import pipeline

    # no joint model, no calibration: asking for confidence is a no-op, not a raise
    joint._ACTIVE = None
    recs = pipeline("ἦν νόμου", with_confidence=True)
    assert recs and all(r.upos_confidence is None and r.lemma_confidence is None for r in recs)


# ── explain_pipeline surface ─────────────────────────────────────────────────
def test_explain_default_has_no_confidence_phrase():
    from aegean.greek.explain import explain_pipeline

    joint._ACTIVE = _stub_model()
    calibrate.use_calibration(_synthetic_calibration())
    for e in explain_pipeline("ὁ λόγος ἐστί"):  # with_confidence not requested
        assert "calibrated confidence" not in e.note


def test_explain_with_confidence_appends_the_calibrated_phrase():
    from aegean.greek.explain import explain_pipeline

    joint._ACTIVE = _stub_model()
    calibrate.use_calibration(_synthetic_calibration(1.4, 1.4))
    exps = explain_pipeline("ὁ λόγος ἐστί", with_confidence=True)
    by_token = {e.token: e for e in exps}
    # the required wording, plus the actual numbers
    assert "calibrated confidence (temperature-scaled on the UD Perseus dev fold; see Benchmarks)" in (
        by_token["ὁ"].note
    )
    assert "UPOS " in by_token["ὁ"].note and "lemma " in by_token["ὁ"].note
    # the IDENTITY token shows a UPOS confidence but no lemma number (model-only)
    assert "UPOS " in by_token["λόγος"].note and "lemma " not in by_token["λόγος"].note
    # the evidence class / review flags are unchanged by adding confidence
    assert by_token["λόγος"].needs_review is True
    assert by_token["ὁ"].lemma_source is LemmaSource.NEURAL_LOOKUP
