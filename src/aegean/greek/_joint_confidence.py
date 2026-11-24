"""Internal calibrated-confidence resolution helpers for the neural Greek pipeline."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, cast

from .confidence import (
    AbstentionPolicy,
    CalibrationEntry,
    CalibrationRegistry,
    ConfidenceResult,
    SentenceConfidence,
    UNAVAILABLE_CONFIDENCE,
    UNAVAILABLE_MISSING_CALIBRATION,
)

_STREAM_CONFIDENCE_UNSET = object()
_STREAM_CONFIDENCE_CONTEXT: ContextVar[Any] = ContextVar(
    "pyaegean_stream_confidence_context", default=_STREAM_CONFIDENCE_UNSET
)


def _confidence_context(
    with_probs: bool,
    *,
    domain: str | None = None,
    policy: AbstentionPolicy | None = None,
) -> dict[str, Any] | None:
    """Resolve confidence inputs without changing the no-confidence path."""
    if (domain is not None or policy is not None) and not with_probs:
        raise ValueError("confidence domain/policy requires with_probs=True")
    if not with_probs:
        return None
    captured = _STREAM_CONFIDENCE_CONTEXT.get()
    if captured is not _STREAM_CONFIDENCE_UNSET:
        if not isinstance(captured, dict):  # pragma: no cover - private invariant
            raise RuntimeError("invalid captured stream confidence context")
        if captured.get("domain") != domain or captured.get("policy") != policy:
            raise RuntimeError("captured stream confidence scope changed during analysis")
        return cast(dict[str, Any], captured)
    from . import calibrate

    legacy, registry = calibrate._active_state()
    if legacy is None and registry is None:
        raise calibrate.UncalibratedConfidenceError(
            "uncalibrated confidence is not exposed; load or fit a calibration first "
            "(aegean.greek.use_calibration())."
        )
    return {"legacy": legacy, "registry": registry, "domain": domain, "policy": policy}


@contextmanager
def _bind_stream_confidence_context(
    context: dict[str, Any] | None,
) -> Iterator[None]:
    """Bind one captured calibration only for a synchronous backend call."""

    if context is None:
        yield
        return
    token = _STREAM_CONFIDENCE_CONTEXT.set(context)
    try:
        yield
    finally:
        _STREAM_CONFIDENCE_CONTEXT.reset(token)


def _model_id(model: Any) -> str:
    manifest = getattr(model, "manifest", None)
    value = getattr(manifest, "model_id", None)
    return value if isinstance(value, str) and value.strip() else "legacy"


def _resolve_confidence_entry(
    model: Any,
    context: dict[str, Any] | None,
    task: str,
    source: str | None = "neural",
) -> tuple[CalibrationEntry | None, str | None, Any | None]:
    if context is None:
        return None, UNAVAILABLE_CONFIDENCE, None
    registry = context.get("registry")
    if not isinstance(registry, CalibrationRegistry):
        return None, UNAVAILABLE_MISSING_CALIBRATION, None
    resolved = registry.resolve(
        _model_id(model), task, source, context.get("domain")
    )
    if resolved.entry is None:
        return None, resolved.reason or UNAVAILABLE_MISSING_CALIBRATION, resolved
    return resolved.entry, None, resolved


def _confidence_result(
    model: Any,
    context: dict[str, Any] | None,
    task: str,
    value: float | None,
    *,
    entry: CalibrationEntry | None = None,
    reason: str | None = None,
    source: str | None = "neural",
    resolution: Any | None = None,
) -> ConfidenceResult:
    if value is None or entry is None:
        return ConfidenceResult(
            task=task,
            value=None,
            reason=reason or UNAVAILABLE_CONFIDENCE,
            model=_model_id(model) if context is not None else None,
            source=source,
            domain=(context or {}).get("domain"),
            scope=resolution.scope if resolution is not None else None,
        )
    if entry.n is None or entry.n <= 0 or (entry.ece is None and entry.brier is None):
        return ConfidenceResult(
            task=task,
            value=None,
            reason="insufficient_calibration_evidence",
            calibration_id=entry.calibration_id,
            scope=resolution.scope if resolution is not None else None,
            model=_model_id(model),
            source=source,
            domain=(context or {}).get("domain"),
            n=entry.n,
            ece=entry.ece,
            brier=entry.brier,
        )
    return ConfidenceResult(
        task=task,
        value=value,
        calibration_id=entry.calibration_id,
        scope=(resolution.scope if resolution is not None else (
            "global_fallback" if entry.fallback and entry.source is None and entry.domain is None else
            "source_fallback" if entry.fallback and entry.source is None else
            "domain_fallback" if entry.fallback else "exact"
        )),
        model=_model_id(model),
        source=source,
        domain=(context or {}).get("domain"),
        n=entry.n,
        ece=entry.ece,
        brier=entry.brier,
    )


def _policy_decision(
    policy: AbstentionPolicy | None, result: ConfidenceResult | None
) -> Any:
    return None if policy is None or result is None else policy.decide(result.task, result.value)


def _entry_probability(
    entry: CalibrationEntry | None,
    logits: Any = None,
    raw_probability: float | None = None,
    *,
    np: Any,
    selected_index: int | None = None,
) -> float | None:
    if entry is None:
        return None
    from . import calibrate

    if entry.calibrator == "temperature":
        if logits is None or entry.temperature is None:
            return None
        if selected_index is None:
            return float(calibrate.top1_confidence(logits, entry.temperature, np=np))
        probabilities = calibrate.temperature_softmax(logits, entry.temperature, np=np)
        return float(probabilities[selected_index])
    if raw_probability is None:
        return None
    return float(entry.calibrate(raw_probability))


def _sentence_confidence(
    model: Any,
    context: dict[str, Any] | None,
    raw_components: list[dict[str, float]],
) -> SentenceConfidence | None:
    if context is None:
        return None
    required = ("upos", "xpos", "lemma", "head", "relation")
    if not raw_components:
        result = _confidence_result(model, context, "sentence", None, reason="empty_sentence")
        return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))
    values: list[float] = []
    for item in raw_components:
        if not item or any(name not in item for name in ("upos", "xpos", "lemma", "head")):
            result = _confidence_result(model, context, "sentence", None, reason="partial_token")
            return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))
        values.extend(item[name] for name in ("upos", "xpos", "lemma", "head"))
        if "relation" not in item and item.get("forced_root"):
            continue
        if "relation" not in item:
            result = _confidence_result(model, context, "sentence", None, reason="missing_relation")
            return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))
        values.append(item["relation"])
    entry, reason, resolution = _resolve_confidence_entry(model, context, "sentence")
    if entry is None:
        result = _confidence_result(
            model, context, "sentence", None, reason=reason or UNAVAILABLE_MISSING_CALIBRATION
        )
        return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))
    if entry.calibrator != "logit_affine":
        result = _confidence_result(model, context, "sentence", None, reason="unsupported_calibrator")
        return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))
    if any(value < 0.0 or value > 1.0 or not math.isfinite(value) for value in values):
        result = _confidence_result(model, context, "sentence", None, reason="invalid_raw_aggregate")
        return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))
    raw = (
        0.0
        if any(value == 0.0 for value in values)
        else math.exp(math.fsum(math.log(value) for value in values))
    )
    value = float(entry.calibrate(raw))
    result = _confidence_result(model, context, "sentence", value, entry=entry, resolution=resolution)
    return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))


def _unavailable_sentence_confidence(
    model: Any, context: dict[str, Any], reason: str
) -> SentenceConfidence:
    """Build an explicit sentence-level unavailable record for structural failures."""

    result = _confidence_result(model, context, "sentence", None, reason=reason)
    return SentenceConfidence(
        result,
        ("upos", "xpos", "lemma", "head", "relation"),
        _policy_decision(context.get("policy"), result),
    )
