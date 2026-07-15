"""A14 bounded-memory, backpressure, ordering, and stable-backend contracts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import gc
from itertools import count, islice
from typing import Any

import pytest

from aegean.greek import documentary, joint
from aegean.greek.neural_contract import AnalysisReceipt
from aegean.greek.runtime import GreekPipeline, GreekPipelineConfig


def _receipt(tokens: int, marker: str) -> AnalysisReceipt:
    return AnalysisReceipt(
        schema_version=1,
        source_schema_version=1,
        model_id=f"test-{marker}",
        dataset="test",
        asset_sha256=None,
        asset_sha256_enforced=False,
        bundle_manifest_sha256=None,
        bundle_schema_version=None,
        tokenizer_revision=None,
        package_version="test",
        python_version="test",
        runtime_versions=(),
        execution_providers=("test",),
        annotation_profile="canonical",
        normalization="NFC",
        segmentation="pretokenized",
        preprocessing_version="test",
        special_token_policy=None,
        max_subwords=512,
        input_tokens=tokens,
        analyzed_tokens=tokens,
        truncated=False,
        windowed=False,
    )


def _analysis(words: list[str], marker: str) -> joint.SentenceAnalysis:
    n = len(words)
    return joint.SentenceAnalysis(
        tokens=tuple(words),
        upos=("X",) * n,
        xpos=("b--------",) * n,
        feats=("_",) * n,
        head=(0,) * n,
        deprel=("root",) * n,
        lemma=tuple(f"{marker}:{word}" for word in words),
        lemma_resolved=(True,) * n,
        analyzed=(True,) * n,
        receipt=_receipt(n, marker),
    )


class _Backend:
    def __init__(self, marker: str = "backend") -> None:
        self.marker = marker
        self.calls: list[list[list[str]]] = []
        self.fail_call: int | None = None
        self.count_delta = 0
        self.bad_element = False
        self.bad_single = False
        self.reverse = False
        self.mutate_input = False
        self.options: list[dict[str, Any]] = []

    def analyze(self, words: list[str], **kwargs: Any) -> joint.SentenceAnalysis:
        self.calls.append([[*words]])
        self.options.append(kwargs)
        if self.fail_call == len(self.calls):
            raise LookupError(f"failed {self.marker}")
        if self.mutate_input:
            words.reverse()
        if self.bad_single:
            return "not-an-analysis"  # type: ignore[return-value]
        return _analysis(words, self.marker)

    def analyze_batch(
        self, sentences: list[list[str]], **kwargs: Any
    ) -> list[joint.SentenceAnalysis]:
        self.calls.append([[*words] for words in sentences])
        self.options.append(kwargs)
        if self.fail_call == len(self.calls):
            raise LookupError(f"failed {self.marker}")
        if self.mutate_input:
            sentences.reverse()
        analyses = [_analysis(words, self.marker) for words in sentences]
        if self.count_delta < 0:
            return analyses[: self.count_delta]
        if self.count_delta > 0:
            analyses.extend(
                _analysis([f"extra-{i}"], self.marker)
                for i in range(self.count_delta)
            )
        if self.bad_element:
            analyses[0] = "not-an-analysis"  # type: ignore[list-item]
        if self.reverse:
            analyses.reverse()
        return analyses


class _PreflightBackend(_Backend):
    def _validate_stream_options(self, **_kwargs: Any) -> None:
        raise RuntimeError("preflight failed")


def _pipeline(backend: _Backend) -> GreekPipeline:
    config = GreekPipelineConfig(
        schema_version=2,
        backend="neural",
        model_id=f"test-{backend.marker}",
        dataset="test",
        runtime_variant="default",
        variant_registry_sha256="9" * 64,
        variant_award_sha256="8" * 64,
        qualification_sha256="7" * 64,
        bundle_manifest_sha256=None,
        tokenizer_revision=None,
        annotation_profile="canonical",
        normalization="NFC",
        segmentation="pretokenized",
        preprocessing_version="test",
        execution_providers=("test",),
    )
    return GreekPipeline._from_backend(backend, config=config)  # type: ignore[arg-type]


def test_construction_is_lazy_and_sequential_pull_is_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    monkeypatch.setattr(joint, "_ACTIVE", backend)
    pulled = 0
    finalized = False

    def source():
        nonlocal pulled, finalized
        try:
            for word in ("a", "b", "c"):
                pulled += 1
                yield [word]
        finally:
            finalized = True

    stream = joint.iter_analyze_sentences(source())
    assert pulled == 0 and backend.calls == []
    assert next(stream).tokens == ("a",)
    assert pulled == 1 and backend.calls == [[["a"]]]
    assert next(stream).tokens == ("b",)
    assert pulled == 2
    stream.close()
    assert pulled == 2 and finalized is True


def test_batched_pull_is_bounded_and_preserves_order_and_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    monkeypatch.setattr(joint, "_ACTIVE", backend)
    pulled = 0

    def source():
        nonlocal pulled
        for words in (["same"], [], ["same"], ["last"]):
            pulled += 1
            yield words

    stream = joint.iter_analyze_sentences(source(), batch_size=3)
    assert pulled == 0
    first = next(stream)
    assert pulled == 3
    rest = list(stream)
    results = [first, *rest]
    assert [result.tokens for result in results] == [
        ("same",),
        (),
        ("same",),
        ("last",),
    ]
    assert [result.receipt.input_tokens for result in results if result.receipt] == [1, 0, 1, 1]
    assert [len(call) for call in backend.calls] == [3, 1]


def test_reused_mutable_sentence_is_copied_before_batch_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    monkeypatch.setattr(joint, "_ACTIVE", backend)
    shared = ["first"]

    def source():
        yield shared
        shared[0] = "second"
        yield shared
        shared[0] = "after"

    results = list(joint.iter_analyze_sentences(source(), batch_size=2))
    assert [result.tokens for result in results] == [("first",), ("second",)]
    assert backend.calls == [[["first"], ["second"]]]


def test_large_and_infinite_sources_never_prefetch_past_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NonRetainingBackend(_Backend):
        def __init__(self) -> None:
            super().__init__()
            self.max_batch = 0

        def analyze_batch(
            self, sentences: list[list[str]], **_kwargs: Any
        ) -> list[joint.SentenceAnalysis]:
            self.max_batch = max(self.max_batch, len(sentences))
            return [_analysis(words, self.marker) for words in sentences]

    class TrackedToken(str):
        live = 0
        maximum = 0

        def __new__(cls, value: str):
            token = super().__new__(cls, value)
            cls.live += 1
            cls.maximum = max(cls.maximum, cls.live)
            return token

        def __del__(self) -> None:
            type(self).live -= 1

    backend = NonRetainingBackend()
    monkeypatch.setattr(joint, "_ACTIVE", backend)
    pulled = 0
    yielded = 0
    maximum_ahead = 0

    def source():
        nonlocal pulled, maximum_ahead
        for i in count():
            pulled += 1
            maximum_ahead = max(maximum_ahead, pulled - yielded)
            yield [TrackedToken(str(i))]

    stream = joint.iter_analyze_sentences(source(), batch_size=7)
    for result in islice(stream, 10_000):
        assert result.tokens == (str(yielded),)
        yielded += 1
        del result
    stream.close()
    gc.collect()
    assert maximum_ahead <= 7
    assert pulled <= yielded + 7
    assert backend.max_batch == 7
    assert TrackedToken.maximum <= 7
    assert TrackedToken.live == 0


def test_source_and_backend_failures_keep_prior_chunks_transactional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    monkeypatch.setattr(joint, "_ACTIVE", backend)

    def broken_source():
        yield ["a"]
        yield ["b"]
        yield ["buffered-but-not-analyzed"]
        raise ValueError("source broke")

    stream = joint.iter_analyze_sentences(broken_source(), batch_size=2)
    assert next(stream).tokens == ("a",)
    assert next(stream).tokens == ("b",)
    with pytest.raises(ValueError, match="source broke"):
        next(stream)
    assert backend.calls == [[["a"], ["b"]]]

    failing = _Backend("failing")
    failing.fail_call = 2
    monkeypatch.setattr(joint, "_ACTIVE", failing)
    stream = joint.iter_analyze_sentences([["a"], ["b"], ["c"]], batch_size=2)
    assert [next(stream).tokens, next(stream).tokens] == [("a",), ("b",)]
    with pytest.raises(LookupError, match="failed failing"):
        next(stream)


def test_preflight_and_primary_errors_do_not_consume_or_get_masked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    touched = False

    def untouched_source():
        nonlocal touched
        touched = True
        yield ["a"]

    monkeypatch.setattr(joint, "_ACTIVE", _PreflightBackend())
    with pytest.raises(RuntimeError, match="preflight failed"):
        joint.iter_analyze_sentences(untouched_source(), with_probs=True)
    assert touched is False

    class RaisingClose:
        def __init__(self) -> None:
            self.used = False

        def __iter__(self):
            return self

        def __next__(self):
            if self.used:
                raise ValueError("primary source failure")
            self.used = True
            return ["a"]

        def close(self) -> None:
            raise RuntimeError("secondary close failure")

    monkeypatch.setattr(joint, "_ACTIVE", _Backend())
    stream = joint.iter_analyze_sentences(RaisingClose())
    assert next(stream).tokens == ("a",)
    with pytest.raises(ValueError, match="primary source failure"):
        next(stream)


@pytest.mark.parametrize("delta", [-1, 1])
def test_batch_cardinality_mismatch_yields_nothing_from_failed_chunk(
    monkeypatch: pytest.MonkeyPatch, delta: int
) -> None:
    backend = _Backend()
    backend.count_delta = delta
    monkeypatch.setattr(joint, "_ACTIVE", backend)
    stream = joint.iter_analyze_sentences([["a"], ["b"]], batch_size=2)
    with pytest.raises(RuntimeError, match=r"source indices 0\.\.1"):
        next(stream)


def test_batch_rejects_non_analysis_results_before_yield(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    backend.bad_element = True
    monkeypatch.setattr(joint, "_ACTIVE", backend)
    stream = joint.iter_analyze_sentences([["a"], ["b"]], batch_size=2)
    with pytest.raises(TypeError, match="source index 0.*SentenceAnalysis"):
        next(stream)


def test_sequential_rejects_invalid_or_mutated_backend_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = _Backend()
    invalid.bad_single = True
    monkeypatch.setattr(joint, "_ACTIVE", invalid)
    with pytest.raises(TypeError, match="source index 0.*SentenceAnalysis"):
        next(joint.iter_analyze_sentences([["a"]]))

    mutated = _Backend()
    mutated.mutate_input = True
    monkeypatch.setattr(joint, "_ACTIVE", mutated)
    with pytest.raises(RuntimeError, match="preserve source order at index 0"):
        next(joint.iter_analyze_sentences([["a", "b"]]))


def test_batch_rejects_same_length_reordered_results_before_yield(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    backend.reverse = True
    monkeypatch.setattr(joint, "_ACTIVE", backend)
    stream = joint.iter_analyze_sentences([["a"], ["b"]], batch_size=2)
    with pytest.raises(RuntimeError, match="preserve source order at index 0"):
        next(stream)


def test_batch_order_check_uses_pre_call_input_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    backend.mutate_input = True
    monkeypatch.setattr(joint, "_ACTIVE", backend)
    stream = joint.iter_analyze_sentences([["a"], ["b"]], batch_size=2)
    with pytest.raises(RuntimeError, match="preserve source order at index 0"):
        next(stream)


@pytest.mark.parametrize("bad", [True, False, 1.5, "2"])
def test_invalid_batch_size_is_rejected_before_source_consumption(
    monkeypatch: pytest.MonkeyPatch, bad: object
) -> None:
    monkeypatch.setattr(joint, "_ACTIVE", _Backend())
    touched = False

    def source():
        nonlocal touched
        touched = True
        yield ["a"]

    with pytest.raises(TypeError, match="batch_size"):
        joint.iter_analyze_sentences(source(), batch_size=bad)  # type: ignore[arg-type]
    assert touched is False


@pytest.mark.parametrize(
    ("sentences", "message"),
    [(["not-a-sentence"], "sentence 0"), ([["ok", 1]], "token 1")],
)
def test_malformed_sentence_input_is_clean(
    monkeypatch: pytest.MonkeyPatch, sentences: object, message: str
) -> None:
    monkeypatch.setattr(joint, "_ACTIVE", _Backend())
    stream = joint.iter_analyze_sentences(sentences)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=message):
        next(stream)


def test_backend_and_documentary_state_are_captured_at_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _Backend("first")
    monkeypatch.setattr(joint, "_ACTIVE", first)
    stream = joint.iter_analyze_sentences([["καὶ"]])
    monkeypatch.setattr(joint, "_ACTIVE", _Backend("second"))
    assert next(stream).lemma == ("first:καὶ",)

    monkeypatch.setattr(documentary, "_RECONCILE", True)
    monkeypatch.setattr(documentary, "_RESCUE", False)
    monkeypatch.setattr(documentary, "_AGGRESSIVE", False)
    monkeypatch.setattr(joint, "_ACTIVE", documentary._DocumentaryModel(first))
    stream = joint.iter_analyze_sentences([["καὶ"]])
    monkeypatch.setattr(documentary, "_RECONCILE", False)
    assert next(stream).upos == ("CCONJ",)


def test_documentary_rescue_captures_paradigm_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.greek import paradigms

    form = "ἀδοκίμου"

    class Lexicon:
        resource_id = "fixture-paradigms-v1"
        resource_sha256 = "f" * 64

        def lemma_options(self, value: str) -> set[str]:
            assert value == form
            return {"ἀδόκιμος"}

        def lemmatize(self, value: str) -> str:
            assert value == form
            return "ἀδόκιμος"

    class UnresolvedBackend(_Backend):
        def analyze(self, words: list[str], **_kwargs: Any) -> joint.SentenceAnalysis:
            base = _analysis(words, self.marker)
            return replace(
                base,
                lemma=tuple(words),
                lemma_resolved=(False,) * len(words),
            )

    monkeypatch.setattr(paradigms, "_ACTIVE", Lexicon())
    monkeypatch.setattr(documentary, "_RECONCILE", False)
    monkeypatch.setattr(documentary, "_RESCUE", True)
    monkeypatch.setattr(documentary, "_AGGRESSIVE", False)
    monkeypatch.setattr(
        joint, "_ACTIVE", documentary._DocumentaryModel(UnresolvedBackend())
    )
    stream = joint.iter_analyze_sentences([[form]])
    monkeypatch.setattr(paradigms, "_ACTIVE", None)
    result = next(stream)
    assert result.lemma == ("ἀδόκιμος",)
    assert result.lemma_source_override == ("paradigm",)


def test_instance_iterator_captures_backend_and_can_move_threads() -> None:
    first = _pipeline(_Backend("first"))
    second = _pipeline(_Backend("second"))
    first_stream = first.iter_analyze_sentences([["a"], ["b"]], batch_size=1)
    second_stream = second.iter_analyze_sentences([["a"], ["b"]], batch_size=1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        left, right = pool.map(list, (first_stream, second_stream))
    assert [result.lemma for result in left] == [("first:a",), ("first:b",)]
    assert [result.lemma for result in right] == [("second:a",), ("second:b",)]


@pytest.mark.parametrize("mode", ["strict", "partial", "windowed"])
def test_stream_forwards_every_analysis_mode_and_confidence_option(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from aegean.greek.confidence import AbstentionPolicy

    backend = _Backend()
    monkeypatch.setattr(joint, "_ACTIVE", backend)
    policy = AbstentionPolicy({"upos": 0.5})
    result = list(
        joint.iter_analyze_sentences(
            [["a"]],
            batch_size=1,
            with_probs=True,
            long_input=mode,  # type: ignore[arg-type]
            domain="papyri",
            policy=policy,
        )
    )
    assert result[0].tokens == ("a",)
    assert backend.options == [
        {
            "with_probs": True,
            "long_input": mode,
            "domain": "papyri",
            "policy": policy,
        }
    ]


def test_collector_is_exactly_the_streaming_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _Backend()
    monkeypatch.setattr(joint, "_ACTIVE", backend)
    sentences = [["a"], [], ["b"]]
    streamed = list(joint.iter_analyze_sentences(sentences, batch_size=2))
    backend.calls.clear()
    collected = joint.analyze_sentences(sentences, batch_size=2)
    assert collected == streamed
    assert [result.receipt.sha256 for result in collected if result.receipt] == [
        result.receipt.sha256 for result in streamed if result.receipt
    ]
