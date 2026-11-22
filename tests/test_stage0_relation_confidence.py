"""Stage 0 regression tests for emitted non-root relation confidence scoring.

Verifies that when a non-root arc's unconstrained relation argmax is ``"root"``
(which the decoder suppresses via ``_best_non_root_relation``), both the standard
``_decode`` path and the multi-window ``_analyze_windowed`` path compute raw,
temperature-scaled, logit-affine, and sentence-aggregate confidences from the
emitted non-root relation rather than the suppressed ``"root"`` label, while
keeping ``head == 0`` as explicit ``forced_root`` unavailable.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

import pytest

np = pytest.importorskip("numpy")

from aegean.greek import calibrate, joint  # noqa: E402
from aegean.greek.confidence import CalibrationEntry, CalibrationRegistry  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_calibration() -> Any:
    calibrate.disable_calibration()
    yield
    calibrate.disable_calibration()


class _FakeTokenizer:
    def no_truncation(self) -> None:
        return None

    def encode(self, words: list[str], is_pretokenized: bool = True) -> Any:
        del is_pretokenized
        return SimpleNamespace(word_ids=list(range(len(words))))


def _relation_stub(*, rel_logits_non_root: list[float], max_subwords: int = 16) -> Any:
    """Build a stub _JointModel with 3 deprel labels: 0='root', 1='obj', 2='obl'.

    Word 0 is forced to attach to root (head=0). Every other word attaches to the
    previous word (local_head = local_i) and receives ``rel_logits_non_root``.
    """
    m = object.__new__(joint._JointModel)
    m._np = np
    m._tok = _FakeTokenizer()
    m.manifest = SimpleNamespace(
        model_id="test-model",
        max_subwords=max_subwords,
        special_token_policy="roberta:<s>:0:</s>:2",
    )
    m.inv = {
        "upos": {0: "VERB", 1: "NOUN"},
        "deprel": {0: "root", 1: "obj", 2: "obl"},
    }
    for i in range(9):
        m.inv[f"x{i}"] = {0: "-", 1: "v"}
    m.trees = [["sub", "lem0"]]
    m.lookup_form = {}
    m.lookup_form_upos = {}
    m.lookup_lower = {}

    def fake_run(words: list[str]) -> dict[str, Any]:
        nw = len(words)
        keep = list(range(nw))
        word_pos = [k + 1 for k in keep]
        seq = nw + 2

        upos = np.full((1, seq, 2), -8.0, dtype=np.float64)
        for j in range(nw):
            upos[0, word_pos[j], 0] = 8.0

        out: dict[str, Any] = {"upos": upos}
        for i in range(9):
            xa = np.full((1, seq, 2), -8.0, dtype=np.float64)
            for j in range(nw):
                xa[0, word_pos[j], 0] = 8.0
            out[f"x{i}"] = xa

        arc = np.full((1, nw, nw + 1), -8.0, dtype=np.float64)
        rel = np.full((1, 3, nw, nw + 1), -8.0, dtype=np.float64)
        for j in range(nw):
            # Word 0 prefers ROOT (head 0); later words attach to word j-1 (head j).
            head_idx = 0 if j == 0 else j
            arc[0, j, head_idx] = 8.0
            if head_idx == 0:
                rel[0, :, j, 0] = np.array([8.0, -8.0, -8.0], dtype=np.float64)
            else:
                rel[0, :, j, head_idx] = np.array(rel_logits_non_root, dtype=np.float64)

        lem = np.full((1, nw, 1), 8.0, dtype=np.float64)
        out["arc"] = arc
        out["rel"] = rel
        out["lemma"] = lem
        out["_word_pos"] = word_pos
        out["_kept"] = keep
        return out

    m._run = fake_run  # type: ignore[method-assign]
    return m


def _registry(
    *,
    relation_calibrator: str = "temperature",
    relation_temp: float | None = 1.0,
    relation_params: tuple[tuple[str, float], ...] = (),
) -> CalibrationRegistry:
    entries = [
        CalibrationEntry(model="test-model", task="upos", source="neural", temperature=1.0, n=100, ece=0.01),
        CalibrationEntry(
            model="test-model",
            task="xpos",
            source="neural",
            calibrator="logit_affine",
            parameters=(("slope", 1.0), ("intercept", 0.0)),
            n=100,
            ece=0.01,
        ),
        CalibrationEntry(
            model="test-model",
            task="feats",
            source="neural",
            calibrator="logit_affine",
            parameters=(("slope", 1.0), ("intercept", 0.0)),
            n=100,
            ece=0.01,
        ),
        CalibrationEntry(
            model="test-model", task="lemma", source="edit_script", temperature=1.0, n=100, ece=0.01
        ),
        CalibrationEntry(model="test-model", task="head", source="neural", temperature=1.0, n=100, ece=0.01),
        CalibrationEntry(
            model="test-model",
            task="relation",
            source="neural",
            calibrator=relation_calibrator,
            temperature=relation_temp,
            parameters=relation_params,
            n=100,
            ece=0.01,
        ),
        CalibrationEntry(
            model="test-model",
            task="sentence",
            source="neural",
            calibrator="logit_affine",
            parameters=(("slope", 1.0), ("intercept", 0.0)),
            n=100,
            ece=0.01,
        ),
    ]
    return CalibrationRegistry(entries=tuple(entries))


@pytest.mark.parametrize("long_input,words,max_subwords", [
    ("strict", ["εἶπε", "λόγον"], 16),
    ("windowed", ["εἶπε", "λόγον", "καλόν", "μέγαν"], 5),
])
@pytest.mark.parametrize("temperature", [1.0, 2.0])
def test_non_root_relation_confidence_scores_emitted_label_temperature(
    long_input: str,
    words: list[str],
    max_subwords: int,
    temperature: float,
) -> None:
    # Synthetic 3-label vector where suppressed "root" dominates (p≈0.9362 at T=1)
    # while emitted non-root "obj" has p≈0.0466 at T=1.
    logits = [3.0, 0.0, -1.0]
    expected_probs = calibrate.temperature_softmax(logits, temperature, np=np)
    expected_suppressed = float(expected_probs[0])
    expected_emitted = float(expected_probs[1])
    if temperature == 1.0:
        assert math.isclose(expected_suppressed, 0.93623955, rel_tol=1e-5)
        assert math.isclose(expected_emitted, 0.04661262, rel_tol=1e-5)

    calibrate.use_calibration_registry(
        _registry(relation_calibrator="temperature", relation_temp=temperature)
    )
    model = _relation_stub(rel_logits_non_root=logits, max_subwords=max_subwords)
    result = model.analyze(words, with_probs=True, long_input=long_input)

    # Word 0 is the unique root and retains explicit forced_root unavailable provenance.
    assert result.head[0] == 0
    assert result.deprel[0] == "root"
    assert result.token_confidences[0].relation is not None
    assert result.token_confidences[0].relation.value is None
    assert result.token_confidences[0].relation.reason == "forced_root"

    # Non-root dependents emit "obj" and report the probability of "obj", not "root".
    for idx in range(1, len(words)):
        assert result.head[idx] != 0
        assert result.deprel[idx] == "obj"
        rel_conf = result.token_confidences[idx].relation
        assert rel_conf is not None and rel_conf.value is not None
        assert math.isclose(rel_conf.value, expected_emitted, rel_tol=1e-6)
        assert not math.isclose(rel_conf.value, expected_suppressed, rel_tol=1e-2)

    # Sentence confidence must aggregate the emitted non-root raw probabilities (~0.0466^(n-1)),
    # not the suppressed "root" probabilities (~0.9362^(n-1)).
    assert result.sentence_confidence is not None
    assert result.sentence_confidence.result.value is not None
    raw_emitted = float(calibrate.temperature_softmax(logits, 1.0, np=np)[1])
    raw_suppressed = float(calibrate.temperature_softmax(logits, 1.0, np=np)[0])
    sent_val = result.sentence_confidence.result.value
    assert sent_val <= raw_emitted ** (len(words) - 1) + 1e-4
    assert sent_val < (raw_suppressed ** (len(words) - 1)) * 0.25


@pytest.mark.parametrize("long_input,words,max_subwords", [
    ("strict", ["εἶπε", "λόγον"], 16),
    ("windowed", ["εἶπε", "λόγον", "καλόν", "μέγαν"], 5),
])
def test_non_root_relation_confidence_scores_emitted_label_logit_affine(
    long_input: str,
    words: list[str],
    max_subwords: int,
) -> None:
    logits = [3.0, 0.0, -1.0]
    expected_raw = float(calibrate.temperature_softmax(logits, 1.0, np=np)[1])

    calibrate.use_calibration_registry(
        _registry(
            relation_calibrator="logit_affine",
            relation_temp=None,
            relation_params=(("slope", 1.0), ("intercept", 0.0)),
        )
    )
    model = _relation_stub(rel_logits_non_root=logits, max_subwords=max_subwords)
    result = model.analyze(words, with_probs=True, long_input=long_input)

    assert result.token_confidences[0].relation is not None
    assert result.token_confidences[0].relation.value is None
    assert result.token_confidences[0].relation.reason == "forced_root"

    for idx in range(1, len(words)):
        assert result.deprel[idx] == "obj"
        rel_conf = result.token_confidences[idx].relation
        assert rel_conf is not None and rel_conf.value is not None
        assert math.isclose(rel_conf.value, expected_raw, rel_tol=1e-6)
