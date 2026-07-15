"""Typed confidence propagation through the public Greek pipeline (no model I/O)."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import pytest

from aegean import greek
from aegean._view import pipeline_rows_from_records
from aegean.core.model import Token, TokenKind
from aegean.greek.confidence import (
    AbstentionPolicy,
    ConfidenceResult,
    SentenceConfidence,
    TokenConfidence,
)
from aegean.greek.joint import SentenceAnalysis
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.pipeline import (
    TokenRecord,
    _analyze_bound,
    _invalidate_sentence_confidence,
    _invalidate_token_lemma_confidence,
)
from aegean.greek.runtime import GreekPipeline


def _result(
    task: str,
    value: float,
    *,
    domain: str | None,
    source: str = "neural",
) -> ConfidenceResult:
    return ConfidenceResult(
        task=task,
        value=value,
        calibration_id="a" * 64,
        scope="exact",
        model="test-model",
        source=source,
        domain=domain,
        n=20,
        ece=0.05,
    )


def _analysis(
    words: list[str],
    *,
    domain: str | None,
    policy: AbstentionPolicy | None,
    rescue_first: bool = False,
) -> SentenceAnalysis:
    n = len(words)
    confidences: list[TokenConfidence] = []
    for index in range(n):
        upos = _result("upos", 0.60 + index / 100, domain=domain)
        lemma = _result("lemma", 0.80 + index / 100, domain=domain)
        decisions = (
            ()
            if policy is None
            else (policy.decide("upos", upos.value), policy.decide("lemma", lemma.value))
        )
        confidences.append(
            TokenConfidence(index=index, upos=upos, lemma=lemma, policy=decisions)
        )
    sentence_result = _result("sentence", 0.75, domain=domain)
    sentence_confidence = SentenceConfidence(
        sentence_result,
        ("upos", "lemma"),
        None if policy is None else policy.decide("sentence", sentence_result.value),
    )
    lemmas = list(words)
    sources = [LemmaSource.NEURAL_EDIT] * n
    resolved = [True] * n
    overrides = [""] * n
    if rescue_first and n:
        lemmas[0] = "rescued-lemma"
        sources[0] = LemmaSource.SEED
        resolved[0] = False
        overrides[0] = LemmaSource.SEED.value
    return SentenceAnalysis(
        tokens=tuple(words),
        upos=tuple("PUNCT" if word == "." else "NOUN" for word in words),
        xpos=("n--------",) * n,
        feats=("_",) * n,
        head=(0,) * n,
        deprel=("root",) * n,
        lemma=tuple(lemmas),
        lemma_resolved=tuple(resolved),
        upos_prob=tuple(0.6 + index / 100 for index in range(n)),
        lemma_script_prob=tuple(0.8 + index / 100 for index in range(n)),
        lemma_source_override=tuple(overrides),
        lemma_source=tuple(sources),
        lemma_source_path=tuple(
            "identity_fallback" if word == "." else "edit_script" for word in words
        ),
        lemma_verified=(False,) * n,
        token_confidences=tuple(reversed(confidences)),
        sentence_confidence=sentence_confidence,
        analyzed=(True,) * n,
    )


class _ConfidenceBackend:
    def __init__(self, marker: str, *, rescue_first: bool = False) -> None:
        self.marker = marker
        self.rescue_first = rescue_first
        self.calls: list[tuple[str | None, AbstentionPolicy | None]] = []
        self.manifest = SimpleNamespace(
            model_id="test-model",
            dataset="test-dataset",
            manifest_sha256="b" * 64,
            tokenizer_revision="c" * 64,
            annotation_profile="test-profile",
            normalization="NFC",
            segmentation="pretokenized",
            preprocessing_version="test-preprocessing-v1",
        )
        self.runtime_variant = SimpleNamespace(
            label="default",
            award_sha256="d" * 64,
            qualification_sha256="e" * 64,
        )
        self._sess = SimpleNamespace(get_providers=lambda: ["CPUExecutionProvider"])

    def analyze(
        self,
        words: list[str],
        *,
        with_probs: bool = False,
        long_input: str = "strict",
        domain: str | None = None,
        policy: AbstentionPolicy | None = None,
    ) -> SentenceAnalysis:
        del long_input
        self.calls.append((domain, policy))
        return _analysis(
            words,
            domain=domain,
            policy=policy,
            rescue_first=self.rescue_first and with_probs,
        )

    def analyze_batch(
        self,
        sentences: list[list[str]],
        *,
        with_probs: bool = False,
        long_input: str = "strict",
        domain: str | None = None,
        policy: AbstentionPolicy | None = None,
    ) -> list[SentenceAnalysis]:
        return [
            self.analyze(
                words,
                with_probs=with_probs,
                long_input=long_input,
                domain=domain,
                policy=policy,
            )
            for words in sentences
        ]


def _instance(marker: str, *, rescue_first: bool = False) -> tuple[GreekPipeline, _ConfidenceBackend]:
    backend = _ConfidenceBackend(marker, rescue_first=rescue_first)
    return GreekPipeline._from_backend(backend), backend


def _policy(name: str = "test") -> AbstentionPolicy:
    return AbstentionPolicy(
        {"upos": 0.7, "lemma": 0.7, "sentence": 0.7},
        name=name,
    )


def test_greek_reexports_complete_confidence_surface() -> None:
    from aegean.greek import confidence

    for name in confidence.__all__:
        assert getattr(greek, name) is getattr(confidence, name)
    assert greek.use_calibration_registry is greek.calibrate.use_calibration_registry
    assert greek.active_registry is greek.calibrate.active_registry


def test_module_facades_preserve_legacy_default_duck_call_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.greek import runtime

    calls: list[tuple[str, Any]] = []

    class LegacyFacade:
        def analyze(
            self,
            text: str,
            *,
            parse: bool,
            with_confidence: bool,
            long_input: str,
            document_id: str,
            sentence_policy: str,
            segmenter: object,
        ) -> list[TokenRecord]:
            calls.append(("text", text))
            return []

        def analyze_tokens(
            self,
            tokens: object,
            *,
            parse: bool,
            with_confidence: bool,
            long_input: str,
            document_id: str,
            sentence_policy: str,
            segmenter: object,
        ) -> list[TokenRecord]:
            calls.append(("tokens", tokens))
            return []

    monkeypatch.setattr(runtime, "default_pipeline", lambda: LegacyFacade())
    token = Token("α", TokenKind.WORD, 0)
    assert greek.pipeline("α") == []
    assert greek.pipeline_tokens([token]) == []
    assert calls == [("text", "α"), ("tokens", [token])]


def test_module_facades_forward_explicit_confidence_keywords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.greek import runtime

    calls: list[tuple[str, dict[str, Any]]] = []

    class ConfidenceFacade:
        def analyze(self, text: str, **kwargs: Any) -> list[TokenRecord]:
            calls.append((text, kwargs))
            return []

        def analyze_tokens(
            self, tokens: list[Token], **kwargs: Any
        ) -> list[TokenRecord]:
            calls.append((tokens[0].text, kwargs))
            return []

    monkeypatch.setattr(runtime, "default_pipeline", lambda: ConfidenceFacade())
    policy = _policy()
    token = Token("α", TokenKind.WORD, 0)
    greek.pipeline(
        "α",
        with_confidence=True,
        confidence_domain="papyri",
        confidence_policy=policy,
    )
    greek.pipeline_tokens(
        [token],
        with_confidence=True,
        confidence_domain="inscriptions",
        confidence_policy=policy,
    )
    assert calls[0][1]["confidence_domain"] == "papyri"
    assert calls[0][1]["confidence_policy"] is policy
    assert calls[1][1]["confidence_domain"] == "inscriptions"
    assert calls[1][1]["confidence_policy"] is policy


def test_pipeline_maps_typed_confidence_by_index_and_invalidates_overrides() -> None:
    instance, backend = _instance("mapped", rescue_first=True)
    policy = _policy()
    records = instance.analyze(
        "α β.",
        with_confidence=True,
        confidence_domain="papyri",
        confidence_policy=policy,
    )

    assert backend.calls == [("papyri", policy)]
    assert [record.token_confidence.index for record in records] == [0, 1, 2]
    assert [record.token_confidence.upos.value for record in records] == [0.60, 0.61, 0.62]

    rescued = records[0]
    assert rescued.lemma == "rescued-lemma"
    assert rescued.lemma_source is LemmaSource.SEED
    assert rescued.lemma_source_path is None
    assert rescued.lemma_confidence is None
    assert rescued.token_confidence.lemma.value is None
    assert rescued.token_confidence.lemma.reason == "unsupported_source"
    assert rescued.token_confidence.lemma.source == "seed"
    assert rescued.token_confidence.upos.value == 0.60
    lemma_decision = next(
        decision for decision in rescued.token_confidence.policy if decision.task == "lemma"
    )
    assert lemma_decision.action == "unavailable"
    assert lemma_decision.policy_sha256 == policy.sha256

    punctuation = records[-1]
    assert punctuation.lemma_source is LemmaSource.PUNCT
    assert punctuation.lemma_source_path is None
    assert punctuation.token_confidence.lemma.value is None
    assert punctuation.token_confidence.lemma.source == "punct"

    assert all(record.sentence_confidence is None for record in records[:-1])
    assert punctuation.sentence_confidence is not None
    assert punctuation.sentence_confidence.result.value is None
    assert punctuation.sentence_confidence.result.reason == "non_neural_lemma_output"
    assert punctuation.sentence_confidence.result.source == "mixed_non_neural_output"
    assert punctuation.sentence_confidence.policy is not None
    assert punctuation.sentence_confidence.policy.action == "unavailable"


def test_punctuation_alone_invalidates_sentence_confidence() -> None:
    instance, _backend = _instance("punctuation")
    policy = _policy()
    records = instance.analyze(
        "α.",
        with_confidence=True,
        confidence_domain="literary",
        confidence_policy=policy,
    )
    assert records[0].sentence_confidence is None
    final = records[-1]
    assert final.lemma_source is LemmaSource.PUNCT
    assert final.sentence_confidence is not None
    assert final.sentence_confidence.result.value is None
    assert final.sentence_confidence.result.reason == "non_neural_lemma_output"
    assert final.sentence_confidence.result.source == "mixed_non_neural_output"


def test_invalidation_preserves_custom_policy_hashes_and_specific_unavailability() -> None:
    policy = _policy("wrapped")
    upos = _result("upos", 0.9, domain="papyri")
    lemma = _result("lemma", 0.8, domain="papyri")
    token = TokenConfidence(
        index=0,
        upos=upos,
        lemma=lemma,
        policy=(policy.decide("upos", upos.value), policy.decide("lemma", lemma.value)),
    )
    invalid_token = _invalidate_token_lemma_confidence(
        token,
        source=LemmaSource.PUNCT,
        confidence_domain=None,
        confidence_policy=None,
    )
    upos_decision = next(item for item in invalid_token.policy if item.task == "upos")
    lemma_decision = next(item for item in invalid_token.policy if item.task == "lemma")
    assert invalid_token.upos is token.upos
    assert upos_decision is token.policy[0]
    assert lemma_decision.action == "unavailable"
    assert lemma_decision.policy_sha256 == policy.sha256

    sentence_result = _result("sentence", 0.85, domain="papyri")
    sentence = SentenceConfidence(
        sentence_result,
        ("upos", "lemma"),
        policy.decide("sentence", sentence_result.value),
    )
    invalid_sentence = _invalidate_sentence_confidence(
        sentence,
        confidence_policy=None,
        reason="non_neural_lemma_output",
        source="mixed_non_neural_output",
    )
    assert invalid_sentence.policy is not None
    assert invalid_sentence.policy.action == "unavailable"
    assert invalid_sentence.policy.policy_sha256 == policy.sha256
    assert invalid_sentence.result.source == "mixed_non_neural_output"

    already_unavailable = ConfidenceResult(
        task="lemma",
        value=None,
        reason="offline_lemma_override",
        model="test-model",
        source="seed",
        domain="papyri",
    )
    already_token = TokenConfidence(
        index=0,
        lemma=already_unavailable,
        policy=(policy.decide("lemma", None),),
    )
    assert (
        _invalidate_token_lemma_confidence(
            already_token,
            source=LemmaSource.SEED,
            confidence_domain="papyri",
            confidence_policy=None,
        )
        is already_token
    )


def test_structured_rows_are_opt_in_and_use_stable_to_dict() -> None:
    plain = TokenRecord(0, 1, "α", "NOUN", "α", LemmaSource.ATTESTED)
    rows = pipeline_rows_from_records([plain])
    expected = [
        {
            "sentence": 0,
            "index": 1,
            "text": "α",
            "upos": "NOUN",
            "lemma": "α",
            "lemma_source": "attested",
            "lemma_resolved": True,
            "lemma_verified": False,
            "review_recommended": False,
            "lemma_known": True,
            "head": None,
            "relation": None,
            "xpos": None,
            "feats": None,
            "neural_analyzed": None,
            "analysis_complete": True,
            "analysis_warning": None,
            "analysis_receipt": None,
            "boundary_policy": None,
            "boundary_policy_id": None,
            "boundary_provenance": None,
            "boundary_confidence": None,
            "boundary_start_char": None,
            "boundary_end_char": None,
        }
    ]
    assert json.dumps(rows, ensure_ascii=False, separators=(",", ":")) == json.dumps(
        expected, ensure_ascii=False, separators=(",", ":")
    )
    assert "token_confidence" not in rows[0]
    assert "sentence_confidence" not in rows[0]

    token_confidence = TokenConfidence(index=0, upos=_result("upos", 0.9, domain=None))
    sentence_confidence = SentenceConfidence(
        _result("sentence", 0.8, domain=None), ("upos",)
    )
    structured = pipeline_rows_from_records(
        [
            TokenRecord(
                0,
                1,
                "α",
                "NOUN",
                "α",
                LemmaSource.NEURAL_EDIT,
                lemma_source_path="edit_script",
                token_confidence=token_confidence,
                sentence_confidence=sentence_confidence,
            )
        ]
    )[0]
    assert structured["token_confidence"] == token_confidence.to_dict()
    assert structured["sentence_confidence"] == sentence_confidence.to_dict()
    assert structured["lemma_source_path"] == "edit_script"


def test_all_public_pipeline_entry_points_reject_policy_without_confidence() -> None:
    instance, _backend = _instance("reject")
    policy = _policy()
    token = Token("α", TokenKind.WORD, 0)
    calls = (
        lambda: greek.pipeline("α", confidence_policy=policy),
        lambda: greek.pipeline_tokens([token], confidence_policy=policy),
        lambda: _analyze_bound("α", confidence_policy=policy),
        lambda: instance.analyze("α", confidence_policy=policy),
        lambda: instance.analyze_tokens([token], confidence_policy=policy),
        lambda: instance.analyze_sentence(["α"], confidence_policy=policy),
        lambda: instance.analyze_sentences([["α"]], confidence_policy=policy),
    )
    for call in calls:
        with pytest.raises(ValueError, match="confidence policy requires"):
            call()

    domain_calls = (
        lambda: greek.pipeline("α", confidence_domain="papyri"),
        lambda: greek.pipeline_tokens([token], confidence_domain="papyri"),
        lambda: _analyze_bound("α", confidence_domain="papyri"),
        lambda: instance.analyze("α", confidence_domain="papyri"),
        lambda: instance.analyze_tokens([token], confidence_domain="papyri"),
        lambda: instance.analyze_sentence(["α"], confidence_domain="papyri"),
        lambda: instance.analyze_sentences([["α"]], confidence_domain="papyri"),
    )
    for call in domain_calls:
        with pytest.raises(ValueError, match="confidence domain requires"):
            call()


def test_direct_and_batched_instance_methods_map_public_confidence_names() -> None:
    instance, backend = _instance("direct")
    policy = _policy()
    typed = instance.analyze_tokens(
        [Token("δ", TokenKind.WORD, 0)],
        with_confidence=True,
        confidence_domain="tokens",
        confidence_policy=policy,
    )
    direct = instance.analyze_sentence(
        ["α"],
        with_probs=True,
        confidence_domain="inscriptions",
        confidence_policy=policy,
    )
    sequential = instance.analyze_sentences(
        [["β"]],
        with_probs=True,
        confidence_domain="papyri",
        confidence_policy=policy,
    )
    batched = instance.analyze_sentences(
        [["γ"]],
        batch_size=1,
        with_probs=True,
        confidence_domain="literary",
        confidence_policy=policy,
    )
    assert typed[0].token_confidence is not None
    assert typed[0].token_confidence.upos is not None
    assert typed[0].token_confidence.upos.domain == "tokens"
    assert direct.token_confidences[0].upos.domain == "inscriptions"
    assert sequential[0].token_confidences[0].upos.domain == "papyri"
    assert batched[0].token_confidences[0].upos.domain == "literary"
    assert backend.calls == [
        ("tokens", policy),
        ("inscriptions", policy),
        ("papyri", policy),
        ("literary", policy),
    ]


def test_confidence_domain_and_policy_remain_instance_local() -> None:
    left, left_backend = _instance("left")
    right, right_backend = _instance("right")
    left_policy = _policy("left")
    right_policy = _policy("right")

    def run(
        instance: GreekPipeline, domain: str, policy: AbstentionPolicy
    ) -> tuple[str | None, str]:
        record = instance.analyze(
            "α",
            with_confidence=True,
            confidence_domain=domain,
            confidence_policy=policy,
        )[0]
        assert record.token_confidence is not None
        assert record.token_confidence.upos is not None
        decision = next(
            item for item in record.token_confidence.policy if item.task == "upos"
        )
        return record.token_confidence.upos.domain, decision.policy_sha256

    with ThreadPoolExecutor(max_workers=2) as pool:
        left_future = pool.submit(run, left, "left-domain", left_policy)
        right_future = pool.submit(run, right, "right-domain", right_policy)
        left_result = left_future.result()
        right_result = right_future.result()

    assert left_result == ("left-domain", left_policy.sha256)
    assert right_result == ("right-domain", right_policy.sha256)
    assert left_backend.calls == [("left-domain", left_policy)]
    assert right_backend.calls == [("right-domain", right_policy)]
