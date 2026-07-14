"""Correctness tests for A3's frozen overlapping-window reconciliation contract."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from aegean.greek import joint
from aegean.greek import calibrate
from aegean.greek.confidence import AbstentionPolicy, CalibrationEntry, CalibrationRegistry


class _Encoding:
    def __init__(self, words: list[str]) -> None:
        self.word_ids = [None]
        for i, word in enumerate(words):
            self.word_ids.extend([i] * len(word))
        self.word_ids.append(None)


class _Tokenizer:
    def clone(self) -> "_Tokenizer":
        return _Tokenizer()

    def no_truncation(self) -> None:
        return None

    def encode(self, words: list[str], *, is_pretokenized: bool = True) -> _Encoding:
        del is_pretokenized
        return _Encoding(words)


def _model(max_subwords: int = 8, *, vary_windows: bool = True) -> joint._JointModel:
    m = object.__new__(joint._JointModel)
    m._np = np
    m._tok = _Tokenizer()
    m.manifest = SimpleNamespace(
        max_subwords=max_subwords,
        special_token_policy="roberta:<s>:0:</s>:2",
        model_id="fake-window-model",
        dataset="fake",
        asset_sha256=None,
        asset_sha256_enforced=False,
        manifest_sha256="0" * 64,
        schema_version=1,
        tokenizer_revision="tok",
        annotation_profile="test",
        normalization="NFC",
        segmentation="pretokenized",
        preprocessing_version="test",
    )
    m.inv = {"upos": {i: f"U{i}" for i in range(8)}, "deprel": {0: "dep"}}
    for i in range(9):
        m.inv[f"x{i}"] = {0: "-"}
    m.trees = []
    m.lookup_form = {}
    m.lookup_form_upos = {}
    m.lookup_lower = {}

    class _Session:
        def get_providers(self) -> list[str]:
            return ["CPUExecutionProvider"]

    m._sess = _Session()
    calls = 0

    def run(words: list[str]) -> dict[str, object]:
        nonlocal calls
        call = calls
        calls += 1
        n = len(words)
        word_pos: list[int] = []
        position = 1
        for word in words:
            word_pos.append(position)
            position += len(word)
        seq = position + 1
        tags = np.zeros((1, seq, 8))
        tags[:, :, min(call, 7) if vary_windows else 0] = (
            float(call + 1) if vary_windows else 1.0
        )
        out: dict[str, object] = {"upos": tags}
        for i in range(9):
            out[f"x{i}"] = np.zeros((1, seq, 1))
        arc = np.full((1, n, n + 1), -9.0)
        rel = np.full((1, 1, n, n + 1), -9.0)
        for dep in range(n):
            head = dep if dep else 0  # local previous token, or ROOT for local first
            if dep:
                arc[0, dep, head] = 9.0
                rel[0, 0, dep, head] = 9.0
            else:
                arc[0, dep, 0] = 9.0
                rel[0, 0, dep, 0] = 9.0
        out["arc"] = arc
        out["rel"] = rel
        out["lemma"] = np.zeros((1, n, 1))
        out["_word_pos"] = word_pos
        out["_kept"] = list(range(n))
        return out

    m._run = run  # type: ignore[method-assign]
    return m


def _registry(*, relation_temperature: float = 1.0) -> CalibrationRegistry:
    entries = [
        CalibrationEntry(
            model="fake-window-model",
            task="upos",
            source="neural",
            temperature=1.0,
            n=10,
            ece=0.1,
        ),
        CalibrationEntry(
            model="fake-window-model",
            task="head",
            source="neural",
            temperature=1.0,
            n=10,
            ece=0.1,
        ),
        CalibrationEntry(
            model="fake-window-model",
            task="relation",
            source="neural",
            temperature=relation_temperature,
            n=10,
            ece=0.1,
        ),
        CalibrationEntry(
            model="fake-window-model",
            task="lemma",
            source="identity_fallback",
            temperature=1.0,
            n=10,
            ece=0.1,
        ),
        *(
            CalibrationEntry(
                model="fake-window-model",
                task=task,
                source="neural",
                calibrator="logit_affine",
                parameters={"slope": 1.0, "intercept": 0.0},
                n=10,
                ece=0.1,
            )
            for task in ("xpos", "feats")
        ),
        CalibrationEntry(
            model="fake-window-model",
            task="sentence",
            source="neural",
            calibrator="logit_affine",
            parameters={"slope": 1.0, "intercept": 0.0},
            n=10,
            ece=0.1,
        ),
    ]
    return CalibrationRegistry(tuple(entries))


def test_pack_windows_keeps_complete_words_and_progress() -> None:
    assert joint._JointModel._pack_windows([2] * 8, 6) == [
        (0, 3),
        (2, 5),
        (4, 7),
        (6, 8),
    ]


def test_windowed_owner_mapping_global_tree_and_receipt() -> None:
    ana = _model().analyze(["aa"] * 8, long_input="windowed")
    assert ana.upos == ("U0", "U0", "U0", "U1", "U1", "U2", "U2", "U3")
    assert ana.head == (0, 1, 2, 3, 4, 5, 6, 7)
    assert ana.deprel == ("root",) + ("dep",) * 7
    assert ana.complete and not ana.truncated and ana.analyzed == (True,) * 8
    assert ana.receipt is not None and ana.receipt.windowed is True
    assert "global observed-arc MST" in ana.warnings[0]


def test_windowed_tie_prefers_earlier_owner() -> None:
    ana = _model().analyze(["aa"] * 8, long_input="windowed")
    # Tokens 2, 4, and 6 are in two equally distant windows. Their tags come from the
    # earlier call, not from whichever window was analyzed last.
    assert (ana.upos[2], ana.upos[4], ana.upos[6]) == ("U0", "U1", "U2")


def test_single_fitting_window_preserves_ordinary_receipt() -> None:
    ana = _model().analyze(["aa", "bb"], long_input="windowed")
    assert ana.receipt is not None and ana.receipt.windowed is False
    assert ana.warnings == ()


def test_windowed_batch_is_sequential_parity() -> None:
    m = _model(vary_windows=False)
    sentences = [["aa"] * 8, ["aa", "bb"]]
    assert m.analyze_batch(sentences, long_input="windowed") == [
        _model(vary_windows=False).analyze(sentence, long_input="windowed")
        for sentence in sentences
    ]


def test_global_arc_allocation_is_compact_float32(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[tuple[int, ...], object]] = []

    class _NumpyProxy:
        def __getattr__(self, name: str) -> object:
            return getattr(np, name)

        def full(self, shape: tuple[int, ...], fill: object, **kwargs: object) -> np.ndarray:
            captured.append((tuple(shape), kwargs.get("dtype")))
            return np.full(shape, fill, **kwargs)

    m = _model()
    m._np = _NumpyProxy()  # type: ignore[assignment]
    m.analyze(["aa"] * 8, long_input="windowed")
    assert ((8, 9), np.dtype("float32")) in captured
    assert ((8, 9), np.dtype("int16")) in captured
    assert captured.count(((8, 9), np.dtype("float32"))) == 1
    assert ((8, 9), np.dtype("float64")) not in captured


def test_windowed_safety_cap_rejects_before_tokenizer(monkeypatch: pytest.MonkeyPatch) -> None:
    m = _model()
    monkeypatch.setattr(
        m,
        "_full_word_lengths",
        lambda _words: pytest.fail("full tokenizer must not run for hostile input"),
    )
    with pytest.raises(joint.NeuralWindowingError, match="4096"):
        m.analyze(["a"] * 4097, long_input="windowed")


def test_windowed_refuses_giant_individual_token() -> None:
    with pytest.raises(joint.NeuralWindowingError, match="individual token"):
        _model().analyze(["a" * 7, "a"], long_input="windowed")


def test_invalid_windowed_mode_is_clean() -> None:
    with pytest.raises(ValueError, match="windowed"):
        _model().analyze(["aa"], long_input="nope")  # type: ignore[arg-type]


def test_encode_drops_a_word_split_by_right_truncation() -> None:
    class Encoding:
        ids = [0, 10, 11, 20, 21, 2]
        word_ids = [None, 0, 0, 1, 1, None]
        overflowing = [SimpleNamespace(word_ids=[None, 1, 1, 2, None])]

    class Tokenizer:
        def encode(self, words: list[str], *, is_pretokenized: bool) -> Encoding:
            assert words == ["alpha", "cut", "tail"] and is_pretokenized
            return Encoding()

    m = object.__new__(joint._JointModel)
    m._tok = Tokenizer()
    m.manifest = SimpleNamespace(max_subwords=6)
    ids, positions, kept = m._encode(["alpha", "cut", "tail"])
    assert ids == [0, 10, 11, 2]
    assert positions == [1]
    assert kept == [0]


def test_window_confidence_comes_from_the_same_owner_as_the_tag() -> None:
    from aegean.greek import calibrate

    m = _model()
    words = ["aa"] * 8
    lengths = m._full_word_lengths(words)
    windows = m._pack_windows(lengths, m._window_body_budget())
    calibration = SimpleNamespace(temperature={"upos": 1.0, "lemma": 1.0})
    ana = m._analyze_windowed(words, lengths, windows, calibration=calibration)

    owner_calls = [0, 0, 0, 1, 1, 2, 2, 3]
    expected = []
    for call in owner_calls:
        logits = np.zeros(8)
        logits[min(call, 7)] = float(call + 1)
        expected.append(calibrate.top1_confidence(logits, 1.0, np=np))
    assert ana.upos_prob == pytest.approx(expected)
    assert ana.lemma_script_prob == pytest.approx([1.0] * 8)


def test_window_v2_registry_keeps_flat_fields_and_global_policy_indices() -> None:
    policy = AbstentionPolicy({"head": 0.5, "relation": 0.5})
    calibrate.use_calibration_registry(_registry())
    try:
        ana = _model().analyze(["aa"] * 8, with_probs=True, long_input="windowed", policy=policy)
    finally:
        calibrate.disable_calibration()
    assert len(ana.upos_prob) == 8 and all(value is not None for value in ana.upos_prob)
    assert len(ana.lemma_script_prob) == 8 and all(
        value is not None for value in ana.lemma_script_prob
    )
    assert [item.index for item in ana.token_confidences] == list(range(8))
    for item in ana.token_confidences:
        decisions = {decision.task: decision for decision in item.policy}
        assert len(decisions) == len(item.policy)
        assert decisions["head"].confidence == item.head.value
        assert decisions["head"].threshold == 0.5


def test_window_relation_temperature_uses_selected_global_head() -> None:
    m = _model()
    m.inv["deprel"] = {0: "dep", 1: "obj"}
    original_run = m._run

    def run(words: list[str]) -> dict[str, object]:
        output = original_run(words)
        relation = np.asarray(output["rel"])
        output["rel"] = np.concatenate((relation, np.zeros_like(relation)), axis=1)
        return output

    m._run = run  # type: ignore[method-assign]
    calibrate.use_calibration_registry(_registry(relation_temperature=2.0))
    try:
        ana = m.analyze(["aa"] * 8, with_probs=True, long_input="windowed")
    finally:
        calibrate.disable_calibration()
    expected = calibrate.top1_confidence(np.asarray([9.0, 0.0]), 2.0, np=np)
    observed = [
        item.relation.value
        for item in ana.token_confidences
        if item.relation is not None and item.relation.available
    ]
    assert observed and observed == pytest.approx([expected] * len(observed))
