"""Contract tests for explicit, immutable confidence review policies."""

from __future__ import annotations

import json

import pytest

from aegean.greek.confidence import (
    AbstentionPolicy,
    ConfidenceResult,
    PolicyDecision,
    SentenceConfidence,
    TokenConfidence,
)


def test_policy_boundary_hash_and_round_trip(tmp_path):
    policy = AbstentionPolicy({"upos": 0.75, "lemma": 0.50}, name="dev-review")
    assert policy.decide("upos", None).action == "unavailable"
    assert policy.decide("upos", None).reason == "confidence_unavailable"
    assert policy.decide("upos", 0.75).action == "accept"  # p >= threshold
    assert policy.decide("upos", 0.7499).action == "review"
    assert policy.decide("xpos", 0.99).action == "unavailable"
    assert policy.decide("xpos", 0.99).reason == "no_threshold_for_task"

    # Canonical order and the immutable policy identity survive JSON round-trip.
    encoded = policy.to_dict()
    assert encoded["sha256"] == policy.sha256
    assert AbstentionPolicy.from_dict(json.loads(policy.canonical)).sha256 == policy.sha256
    p = tmp_path / "policy.json"
    policy.save(p)
    assert AbstentionPolicy.load(p) == policy
    with pytest.raises(TypeError):
        policy.threshold_map["upos"] = 0.0  # type: ignore[index]


@pytest.mark.parametrize(
    "bad",
    [
        {"upos": None},
        {"upos": float("nan")},
        {"upos": 1.1},
        {"upos": -0.1},
    ],
)
def test_policy_rejects_missing_nonfinite_or_out_of_range_thresholds(bad):
    with pytest.raises(ValueError):
        AbstentionPolicy(bad)


def test_policy_rejects_tampered_or_malformed_json(tmp_path):
    policy = AbstentionPolicy({"upos": 0.5})
    payload = policy.to_dict()
    payload["thresholds"]["upos"] = 0.6
    with pytest.raises(ValueError, match="sha256"):
        AbstentionPolicy.from_dict(payload)
    malformed = tmp_path / "bad.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid abstention policy JSON"):
        AbstentionPolicy.load(malformed)


def test_typed_token_and_sentence_confidence_round_trip_is_strict():
    digest = "a" * 64
    upos = ConfidenceResult(
        task="upos",
        value=0.8,
        calibration_id=digest,
        scope="exact",
        model="m",
        source="neural",
        domain="prose",
        n=10,
        ece=0.1,
    )
    policy = AbstentionPolicy({"upos": 0.75, "sentence": 0.8})
    token = TokenConfidence(index=2, upos=upos, policy=(policy.decide("upos", 0.8),))
    assert TokenConfidence.from_dict(token.to_dict()) == token
    sentence_result = ConfidenceResult(
        task="sentence",
        value=0.9,
        calibration_id=digest,
        scope="exact",
        model="m",
        source="neural",
        domain="prose",
        n=10,
        ece=0.1,
    )
    sentence = SentenceConfidence(
        sentence_result,
        ("upos", "xpos", "lemma", "head", "relation"),
        policy.decide("sentence", 0.9),
    )
    assert SentenceConfidence.from_dict(sentence.to_dict()) == sentence
    with pytest.raises(ValueError, match="invalid fields"):
        TokenConfidence.from_dict({"index": 0})
    with pytest.raises(ValueError, match="sentence"):
        SentenceConfidence(sentence_result, (), policy.decide("upos", 0.8))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"action": "accept", "confidence": None, "threshold": 0.5},
        {"action": "accept", "confidence": 0.8, "threshold": None},
        {"action": "review", "confidence": None, "threshold": 0.5},
        {"action": "review", "confidence": 0.2, "threshold": None},
    ],
)
def test_policy_decision_available_actions_require_evidence(kwargs):
    with pytest.raises(ValueError):
        PolicyDecision(
            task="upos",
            reason=None,
            policy_sha256="a" * 64,
            **kwargs,
        )


@pytest.mark.parametrize(
    "action,confidence,threshold",
    [("accept", 0.4, 0.5), ("review", 0.8, 0.5)],
)
def test_policy_decision_action_matches_threshold(action, confidence, threshold):
    with pytest.raises(ValueError, match="threshold"):
        PolicyDecision(
            task="upos",
            action=action,
            confidence=confidence,
            threshold=threshold,
            reason=None,
            policy_sha256="a" * 64,
        )


def test_unavailable_records_reject_blank_reasons():
    with pytest.raises(ValueError, match="reason"):
        PolicyDecision(
            task="upos",
            action="unavailable",
            confidence=None,
            threshold=None,
            reason="   ",
            policy_sha256="a" * 64,
        )
    with pytest.raises(ValueError, match="reason"):
        ConfidenceResult(task="upos", value=None, reason="   ")


def test_policy_decision_from_dict_rejects_missing_evidence():
    policy = AbstentionPolicy({"upos": 0.5})
    payload = policy.decide("upos", 0.8).to_dict()
    payload["confidence"] = None
    with pytest.raises(ValueError, match="confidence"):
        TokenConfidence.from_dict(
            {
                "index": 0,
                "upos": None,
                "xpos": None,
                "feats": None,
                "lemma": None,
                "head": None,
                "relation": None,
                "policy": [payload],
            }
        )


def test_token_policy_tasks_are_unique_and_match_confidence_fields():
    policy = AbstentionPolicy({"upos": 0.5, "lemma": 0.5})
    upos = policy.decide("upos", 0.8)
    lemma = policy.decide("lemma", 0.8)
    with pytest.raises(ValueError, match="unique"):
        TokenConfidence(index=0, policy=(upos, upos))
    with pytest.raises(ValueError, match="token confidence"):
        TokenConfidence(index=0, policy=(lemma,))


def test_token_and_sentence_policy_decisions_cannot_be_tampered():
    digest = "a" * 64
    upos = ConfidenceResult(
        task="upos", value=0.8, calibration_id=digest, scope="exact", model="m", n=10, ece=0.1
    )
    policy = AbstentionPolicy({"upos": 0.75})
    tampered = PolicyDecision(
        task="upos",
        action="accept",
        confidence=0.9,
        threshold=0.75,
        reason=None,
        policy_sha256=policy.sha256,
    )
    with pytest.raises(ValueError, match="disagrees"):
        TokenConfidence(index=0, upos=upos, policy=(tampered,))
    lemma = ConfidenceResult(
        task="lemma", value=0.8, calibration_id=digest, scope="exact", model="m", n=10, ece=0.1
    )
    other = AbstentionPolicy({"lemma": 0.5})
    with pytest.raises(ValueError, match="one policy hash"):
        TokenConfidence(
            index=0,
            upos=upos,
            lemma=lemma,
            policy=(policy.decide("upos", 0.8), other.decide("lemma", 0.8)),
        )

    sentence_result = ConfidenceResult(
        task="sentence", value=0.9, calibration_id=digest, scope="exact", model="m", n=10, ece=0.1
    )
    sentence_policy = AbstentionPolicy({"sentence": 0.8})
    sentence_tampered = PolicyDecision(
        task="sentence",
        action="accept",
        confidence=0.8,
        threshold=0.8,
        reason=None,
        policy_sha256=sentence_policy.sha256,
    )
    with pytest.raises(ValueError, match="disagrees"):
        SentenceConfidence(sentence_result, (), sentence_tampered)
