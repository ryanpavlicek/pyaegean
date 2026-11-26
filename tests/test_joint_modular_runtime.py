"""Tests for modularized joint.py internals and instance-scoped GreekPipeline options."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np
import pytest

from aegean.greek import calibrate, documentary, joint, lemma_rerank
from aegean.greek.joint import (
    NeuralPipelineNotLoadedError,
    SentenceAnalysis,
)
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.model_variants import variant_registry_sha256
from aegean.greek.runtime import GreekPipeline, GreekPipelineConfig


def _dummy_config() -> GreekPipelineConfig:
    return GreekPipelineConfig(
        schema_version=2,
        backend="neural",
        model_id="grc-joint-v3",
        dataset="grc-joint",
        runtime_variant="default",
        variant_registry_sha256=variant_registry_sha256(),
        variant_award_sha256="c" * 64,
        qualification_sha256="d" * 64,
        bundle_manifest_sha256="a" * 64,
        tokenizer_revision="b" * 64,
        annotation_profile="agdt-ud-v3",
        normalization="NFC",
        segmentation="pretokenized",
        preprocessing_version="v3",
        execution_providers=("CPUExecutionProvider",),
    )


class _RerankDocBackend:
    """Lightweight deterministic neural backend stub exercising post-processors."""

    def __init__(self) -> None:
        self.manifest = SimpleNamespace(
            model_id="grc-joint-v3",
            dataset="grc-joint",
            manifest_sha256="a" * 64,
            tokenizer_revision="b" * 64,
            annotation_profile="agdt-ud-v3",
            normalization="NFC",
            segmentation="pretokenized",
            preprocessing_version="v3",
            max_subwords=256,
        )
        self.runtime_variant = SimpleNamespace(
            label="default",
            award_sha256="c" * 64,
            qualification_sha256="d" * 64,
        )
        self._sess = SimpleNamespace(get_providers=lambda: ["CPUExecutionProvider"])
        # Train-only lookup tables used by TrainOnlyLemmaIndex.from_model()
        self.lookup_form = {"λογου": "λόγος", "καί": "καί"}
        self.lookup_form_upos = {"λογου|NOUN": "λόγος", "καί|CCONJ": "καί"}
        self.lookup_lower = {"λογου": "λόγος", "καί": "καί"}
        self.trees: list[dict[str, object]] = []
        self._np = np

    def analyze(
        self,
        words: list[str],
        *,
        with_probs: bool = False,
        long_input: str = "strict",
        domain: str | None = None,
        policy: object = None,
    ) -> SentenceAnalysis:
        del long_input
        context = joint._confidence_context(with_probs, domain=domain, policy=policy)
        upos = []
        xpos = []
        lemmas = []
        resolved = []
        sources = []
        for w in words:
            if w == "καί":
                # Simulate documentary X / b drift so Lever A has work to do.
                upos.append("X")
                xpos.append("b--------")
                lemmas.append("καί")
                resolved.append(True)
                sources.append(LemmaSource.NEURAL_LOOKUP)
            elif w == "λόγου":
                # Simulate an OOV spelling miss (diacritic-stripped "λογου" is in train lookup).
                upos.append("NOUN")
                xpos.append("n-s---mg-")
                lemmas.append("λόγου")
                resolved.append(False)
                sources.append(LemmaSource.IDENTITY)
            else:
                # Unresolved form that offline seed table can rescue ("κυρίου" -> "κύριος").
                upos.append("NOUN")
                xpos.append("n-s---mg-")
                lemmas.append(w)
                resolved.append(False)
                sources.append(LemmaSource.IDENTITY)
        n = len(words)
        return SentenceAnalysis(
            tokens=tuple(words),
            upos=tuple(upos),
            xpos=tuple(xpos),
            feats=("_",) * n,
            head=tuple(0 if i == 0 else 1 for i in range(n)),
            deprel=tuple("root" if i == 0 else "dep" for i in range(n)),
            lemma=tuple(lemmas),
            lemma_resolved=tuple(resolved),
            upos_prob=((0.95,) * n) if context is not None else (),
            lemma_script_prob=((0.90,) * n) if context is not None else (),
            lemma_source=tuple(sources),
            lemma_verified=(False,) * n,
            analyzed=(True,) * n,
        )

    def analyze_batch(
        self,
        sentences: list[list[str]],
        *,
        with_probs: bool = False,
        long_input: str = "strict",
        domain: str | None = None,
        policy: object = None,
    ) -> list[SentenceAnalysis]:
        return [
            self.analyze(s, with_probs=with_probs, long_input=long_input, domain=domain, policy=policy)
            for s in sentences
        ]

    def _validate_stream_options(
        self,
        *,
        with_probs: bool,
        long_input: str,
        domain: str | None,
        policy: object,
    ) -> dict[str, object] | None:
        joint._long_input_mode(long_input)
        return joint._confidence_context(with_probs, domain=domain, policy=policy)


def test_joint_module_preserves_public_and_internal_exports() -> None:
    """Modularizing joint.py into _joint_* submodules must keep all re-exports intact."""
    for name in (
        "SentenceAnalysis",
        "NeuralPipelineNotLoadedError",
        "NeuralInputTooLongError",
        "NeuralWindowingError",
        "use_neural_pipeline",
        "disable_neural_pipeline",
        "active",
        "analyze_sentence",
        "analyze_sentences",
        "iter_analyze_sentences",
        "neural_backend_info",
        "_JointModel",
        "_ACTIVE",
        "_UNSET",
        "_capture_top_lemma_edits",
        "_extract_top_k_edits_for_word",
        "_best_non_root_relation",
        "_compose_lemma",
        "_compose_lemma_detail",
        "_confidence_context",
        "_bind_stream_confidence_context",
        "_copy_stream_sentence",
        "_stream_backend",
    ):
        assert hasattr(joint, name), f"missing export {name} on aegean.greek.joint"


def test_instance_scoped_oov_and_documentary_options_do_not_mutate_globals() -> None:
    """GreekPipeline.with_options() composes post-processors without touching module globals."""
    assert not lemma_rerank.oov_lemma_reranker_active()
    assert not documentary.documentary_reconciliation_active()
    assert not documentary.documentary_lemma_rescue_active()

    base = GreekPipeline._from_backend(_RerankDocBackend(), config=_dummy_config())
    doc_pipe = base.with_options(
        oov_reranker="unique",
        documentary_reconciliation=True,
        documentary_lemma_rescue=True,
    )

    assert not base.oov_reranker_active
    assert not base.documentary_reconciliation_active
    assert not base.documentary_lemma_rescue_active
    assert doc_pipe.oov_reranker_active
    assert doc_pipe.documentary_reconciliation_active
    assert doc_pipe.documentary_lemma_rescue_active

    # Module globals remain untouched.
    assert not lemma_rerank.oov_lemma_reranker_active()
    assert not documentary.documentary_reconciliation_active()
    assert not documentary.documentary_lemma_rescue_active()

    # Plain pipeline keeps raw backend predictions.
    raw = base.analyze_sentence(["καί", "λόγου", "κυρίου"])
    assert raw.upos[0] == "X"
    assert raw.lemma[1] == "λόγου"
    assert raw.lemma_resolved[1] is False
    assert raw.lemma[2] == "κυρίου"

    # Configured pipeline applies OOV reranker + Lever A + Lever B independently.
    enhanced = doc_pipe.analyze_sentence(["καί", "λόγου", "κυρίου"])
    assert enhanced.upos[0] == "CCONJ"
    assert enhanced.lemma[1] == "λόγος"
    assert enhanced.lemma_resolved[1] is True
    assert enhanced.lemma[2] == "κύριος"
    assert enhanced.lemma_source_override[2] == LemmaSource.SEED.value

    # Streaming preserves stacked wrappers cleanly.
    streamed = list(doc_pipe.iter_analyze_sentences([["καί", "λόγου", "κυρίου"]]))
    assert len(streamed) == 1
    assert streamed[0].upos[0] == "CCONJ"
    assert streamed[0].lemma[1] == "λόγος"
    assert streamed[0].lemma[2] == "κύριος"

    # Turning options back off restores plain behavior sharing the same base backend.
    plain_again = doc_pipe.with_options(
        oov_reranker=False,
        documentary_reconciliation=False,
        documentary_lemma_rescue=False,
    )
    assert plain_again._backend is base._backend
    assert plain_again.analyze_sentence(["καί"]).upos[0] == "X"


def test_instance_scoped_calibration_isolation_and_concurrency() -> None:
    """Two pipelines can run concurrently with independent calibration states."""
    prev_cal = calibrate.active()
    prev_reg = calibrate.active_registry()
    calibrate.disable_calibration()
    try:
        base = GreekPipeline._from_backend(_RerankDocBackend(), config=_dummy_config())
        calibrated = base.with_options(calibration_registry=True)
        disabled = base.with_options(calibration_registry=False)

        assert calibrated.calibration_active is True
        assert disabled.calibration_active is False
        # Global calibration remains disabled.
        assert calibrate.active() is None
        assert calibrate.active_registry() is None

        # Calibrated instance succeeds with_probs=True without global activation.
        res = calibrated.analyze_sentence(["λόγου"], with_probs=True)
        assert res.upos_prob == (0.95,)

        # Disabled instance raises even when global calibration IS enabled.
        calibrate.use_calibration_registry()
        assert disabled.calibration_active is False
        with pytest.raises(calibrate.UncalibratedConfidenceError):
            disabled.analyze_sentence(["λόγου"], with_probs=True)

        # Concurrent execution across threads keeps calibration & post-processing isolated.
        calibrate.disable_calibration()
        plain = base.with_options(calibration=False)
        enhanced = base.with_options(
            documentary_reconciliation=True,
            calibration_registry=True,
        )

        def run_plain() -> list[str]:
            out = []
            for _ in range(10):
                with pytest.raises(calibrate.UncalibratedConfidenceError):
                    plain.analyze_sentence(["καί", "λόγου"], with_probs=True)
                out.append(plain.analyze_sentence(["καί", "λόγου"]).upos[0])
            return out

        def run_enhanced() -> list[tuple[str, float | None, float | None]]:
            out = []
            for _ in range(10):
                ana = enhanced.analyze_sentence(["καί", "λόγου"], with_probs=True)
                # Reconciled token clears neural UPOS prob (None); untouched token keeps 0.95.
                out.append((ana.upos[0], ana.upos_prob[0], ana.upos_prob[1]))
            return out

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_plain = pool.submit(run_plain)
            f_enh = pool.submit(run_enhanced)
            assert set(f_plain.result()) == {"X"}
            assert set(f_enh.result()) == {("CCONJ", None, 0.95)}

        # Stream captures instance calibration synchronously even if global state changes.
        stream = enhanced.iter_analyze_sentences([["καί", "λόγου"], ["λόγου"]], with_probs=True)
        assert calibrate.active_registry() is None
        items = list(stream)
        assert items[0].upos_prob == (None, 0.95)
        assert items[1].upos_prob == (0.95,)
    finally:
        calibrate.disable_calibration()
        if prev_cal is not None:
            calibrate.use_calibration(prev_cal)
        elif prev_reg is not None:
            calibrate.use_calibration_registry(prev_reg)


def test_option_validation_errors() -> None:
    """Invalid option combinations fail clearly before backend mutation."""
    baseline = GreekPipeline()
    with pytest.raises(NeuralPipelineNotLoadedError):
        baseline.with_options(oov_reranker="weighted")
    with pytest.raises(NeuralPipelineNotLoadedError):
        baseline.with_options(documentary_reconciliation=True)

    neural = GreekPipeline._from_backend(_RerankDocBackend(), config=_dummy_config())
    with pytest.raises(ValueError, match="not both"):
        neural.with_options(calibration=True, calibration_registry=True)
    with pytest.raises(ValueError, match="requires documentary_reconciliation=True"):
        neural.with_options(documentary_reconciliation_aggressive=True)
    with pytest.raises(ValueError, match="unknown OOV lemma reranker preset"):
        neural.with_options(oov_reranker="bogus")


def test_joint_model_serializes_concurrent_session_runs() -> None:
    """_JointModel._run and _run_batch must serialize ONNX session calls across threads.

    Guards against CUDAExecutionProvider stream/arena races that corrupt logits when
    multiple threads share one InferenceSession.
    """
    import threading
    import time

    from aegean.greek.joint import _JointModel

    class _MiniNP:
        int64 = int

        @staticmethod
        def array(data: object, dtype: object = None) -> object:
            return data

        @staticmethod
        def ones(shape: tuple[int, int], dtype: object = None) -> list[list[int]]:
            return [[1] * shape[1] for _ in range(shape[0])]

        @staticmethod
        def zeros(shape: tuple[int, int], dtype: object = None) -> _MiniMatrix:
            return _MiniMatrix(shape[0], shape[1])

    class _MiniMatrix:
        def __init__(self, rows: int, cols: int) -> None:
            self.data = [[0] * cols for _ in range(rows)]

        def __setitem__(self, key: tuple[int, slice], value: list[int] | int) -> None:
            r, sl = key
            if isinstance(value, int):
                count = len(range(*sl.indices(len(self.data[r]))))
                self.data[r][sl] = [value] * count
            else:
                self.data[r][sl] = value

        def __getitem__(self, sl: slice) -> list[list[int]]:
            return self.data[sl]

    class _NonReentrantSession:
        def __init__(self) -> None:
            self._probe = threading.Lock()
            self.in_flight = 0
            self.max_in_flight = 0
            self.calls = 0

        def run(self, _outputs: object, feed: dict[str, object]) -> list[list[int]]:
            with self._probe:
                self.in_flight += 1
                self.calls += 1
                if self.in_flight > self.max_in_flight:
                    self.max_in_flight = self.in_flight
                overlap = self.in_flight > 1
            try:
                assert not overlap, "concurrent InferenceSession.run() overlap detected"
                time.sleep(0.01)
                n_rows = len(feed["input_ids"].data) if isinstance(feed["input_ids"], _MiniMatrix) else 1
                return [[0] * n_rows]
            finally:
                with self._probe:
                    self.in_flight -= 1

    model = object.__new__(_JointModel)
    model._np = _MiniNP
    model._sess = _NonReentrantSession()
    model._output_names = ("upos",)
    model._session_lock = threading.RLock()
    model._encode = lambda words: ([1, 2, 3], [1], [0])  # type: ignore[method-assign]

    with ThreadPoolExecutor(max_workers=4) as pool:
        f_single = [pool.submit(model._run, ["λόγος"]) for _ in range(8)]
        f_batch = [pool.submit(model._run_batch, [["λόγος"], ["θεός"]]) for _ in range(4)]
        for fut in f_single + f_batch:
            fut.result()

    assert model._sess.calls == 12
    assert model._sess.max_in_flight == 1

    # Test fakes built via object.__new__ without _session_lock still work cleanly.
    del model._session_lock
    res = model._run(["λόγος"])
    assert res["_kept"] == [0]


def test_neural_lemmatizer_serializes_concurrent_generate() -> None:
    """_NeuralModel._generate must serialize ONNX encoder/decoder calls across threads."""
    import threading
    import time

    from aegean.greek.neural_lemmatizer import _EOS_ID, _NeuralModel

    class _MiniArray:
        def __init__(self, rows: list[list[int]]) -> None:
            self.rows = rows

        def __getitem__(self, key: object) -> object:
            if isinstance(key, tuple) and len(key) == 2:
                r, c = key
                if isinstance(c, slice):
                    return self.rows[r][c]
                return _ArgMax(self.rows[r][c])
            return self.rows[key]  # type: ignore[index]

    class _ArgMax:
        def __init__(self, val: int) -> None:
            self._v = val

        def argmax(self) -> int:
            return self._v

    class _MiniNP:
        int64 = int

        @staticmethod
        def array(data: list[list[int]], dtype: object = None) -> _MiniArray:
            return _MiniArray(data)

        @staticmethod
        def ones_like(arr: _MiniArray) -> _MiniArray:
            return _MiniArray([[1] * len(r) for r in arr.rows])

        @staticmethod
        def concatenate(items: list[object], axis: int = 1) -> _MiniArray:
            a, b = items
            assert isinstance(a, _MiniArray) and isinstance(b, list)
            return _MiniArray([a.rows[0] + b[0]])

    class _MiniTok:
        def encode(self, _form: str) -> object:
            return type("_Enc", (), {"ids": [5, 6]})()

        def decode(self, ids: list[int], skip_special_tokens: bool = True) -> str:
            return "λόγος"

    probe = threading.Lock()
    state = {"in_flight": 0, "max_in_flight": 0}

    class _NonReentrantSubSession:
        def __init__(self, *, is_dec: bool) -> None:
            self._is_dec = is_dec

        def run(self, _outputs: object, _feed: dict[str, object]) -> list[object]:
            with probe:
                state["in_flight"] += 1
                if state["in_flight"] > state["max_in_flight"]:
                    state["max_in_flight"] = state["in_flight"]
                overlap = state["in_flight"] > 1
            try:
                assert not overlap, "concurrent GreTa ONNX session overlap detected"
                time.sleep(0.01)
                if self._is_dec:
                    return [_MiniArray([[_EOS_ID]])]
                return [[[0.0]]]
            finally:
                with probe:
                    state["in_flight"] -= 1

    model = object.__new__(_NeuralModel)
    model._np = _MiniNP
    model._tok = _MiniTok()
    model._enc = _NonReentrantSubSession(is_dec=False)
    model._dec = _NonReentrantSubSession(is_dec=True)
    model._dec_in = {"input_ids", "encoder_hidden_states", "encoder_attention_mask"}
    model._lookup = {}
    model._session_lock = threading.RLock()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(model._generate, ["λόγοι"] * 8))

    assert results == ["λόγος"] * 8
    assert state["max_in_flight"] == 1

