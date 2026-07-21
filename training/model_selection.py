"""Declarative, content-addressed model-candidate selection.

The selector consumes verified development reports.  It never runs a model and it
never accepts caller-supplied accuracy values: aggregate and slice scores are
recomputed from the report's integer item counts.  All inputs and the resulting
decision remain development-only evidence.
"""

from __future__ import annotations

import argparse
import copy
import functools
import json
import math
import os
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:  # focused tests import training helpers as top-level modules
    from development_manifest import (
        ManifestError,
        canonical_json,
        document_sha256,
        load_document as load_manifest_document,
        stamp_document,
        verify_manifest,
    )
    from development_report import REPORT_FORMAT, verify_report
except ImportError:  # pragma: no cover - package-style import for tooling
    from .development_manifest import (
        ManifestError,
        canonical_json,
        document_sha256,
        load_document as load_manifest_document,
        stamp_document,
        verify_manifest,
    )
    from .development_report import REPORT_FORMAT, verify_report


GATE_FORMAT = "pyaegean-model-selection-gate/1"
CANDIDATE_FORMAT = "pyaegean-model-candidate/1"
RESULT_FORMAT = "pyaegean-model-selection-result/1"
CLAIM_STATUS = "development-only-not-published"
METRICS = ("upos", "xpos", "ufeats", "lemma", "uas", "las", "clas")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_GATE_BYTES = 1024 * 1024
_MAX_CANDIDATE_BYTES = 128 * 1024 * 1024
_TIE_FIELDS = {
    "weighted_target_gain",
    "worst_protected_delta",
    "artifact_size_bytes",
    "latency_ms_per_100_tokens",
    "candidate_id",
}


class GateError(ValueError):
    """Raised when a gate, candidate, or selection result violates its contract."""


def _exact_fields(value: Mapping[str, Any], expected: set[str], *, where: str) -> None:
    actual = set(value)
    if actual != expected:
        raise GateError(
            f"{where} fields differ (missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)})"
        )


def _mapping(value: Any, *, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GateError(f"{where} must be an object")
    return value


def _string(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise GateError(f"{where} must be a non-empty string")
    return value


def _sha256(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise GateError(f"{where} must be a lowercase SHA-256")
    return value


def _number(value: Any, *, where: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GateError(f"{where} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise GateError(f"{where} must be finite and at least {minimum}")
    return result


def _optional_number(value: Any, *, where: str) -> float | None:
    return None if value is None else _number(value, where=where)


def _same_number(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1e-15)


def _positive_integer(value: Any, *, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GateError(f"{where} must be a positive integer")
    return value


def _metric_key(value: Any, *, where: str) -> tuple[str, str]:
    entry = _mapping(value, where=where)
    metric = _string(entry.get("metric"), where=f"{where}.metric")
    if metric not in METRICS:
        raise GateError(f"{where}.metric is unknown")
    slice_id = _string(entry.get("slice"), where=f"{where}.slice")
    return metric, slice_id


def validate_gate(gate: Mapping[str, Any], *, verify_digest: bool = True) -> None:
    """Validate a frozen selection gate and, by default, its canonical digest."""

    gate = _mapping(gate, where="gate")
    _exact_fields(
        gate,
        {
            "format",
            "gate_id",
            "claim_status",
            "development_manifest_sha256",
            "decoder",
            "protected_metrics",
            "target_metrics",
            "operational_limits",
            "promotion",
            "tie_breaking",
            "gate_sha256",
        },
        where="gate",
    )
    if gate["format"] != GATE_FORMAT:
        raise GateError(f"unsupported gate format: {gate['format']!r}")
    _string(gate["gate_id"], where="gate.gate_id")
    if gate["claim_status"] != CLAIM_STATUS:
        raise GateError("gate.claim_status must remain development-only-not-published")
    _sha256(
        gate["development_manifest_sha256"],
        where="gate.development_manifest_sha256",
    )

    decoder = _mapping(gate["decoder"], where="gate.decoder")
    _exact_fields(decoder, {"identity", "mode", "long_input"}, where="gate.decoder")
    _string(decoder["identity"], where="gate.decoder.identity")
    if decoder["mode"] != "sequential":
        raise GateError("gate.decoder.mode must be sequential")
    if decoder["long_input"] != "windowed":
        raise GateError("gate.decoder.long_input must be windowed")

    protected = gate["protected_metrics"]
    if not isinstance(protected, list) or not protected:
        raise GateError("gate.protected_metrics must be a non-empty array")
    protected_keys: list[tuple[str, str]] = []
    for index, raw in enumerate(protected):
        where = f"gate.protected_metrics[{index}]"
        entry = _mapping(raw, where=where)
        _exact_fields(entry, {"metric", "slice", "max_regression"}, where=where)
        protected_keys.append(_metric_key(entry, where=where))
        regression = _number(
            entry["max_regression"], where=f"{where}.max_regression", minimum=0.0
        )
        if regression > 1.0:
            raise GateError(f"{where}.max_regression must not exceed 1")
    if len(protected_keys) != len(set(protected_keys)):
        raise GateError("gate.protected_metrics contains duplicate metric/slice entries")

    targets = gate["target_metrics"]
    if not isinstance(targets, list) or not targets:
        raise GateError("gate.target_metrics must be a non-empty array")
    target_keys: list[tuple[str, str]] = []
    weights: list[float] = []
    for index, raw in enumerate(targets):
        where = f"gate.target_metrics[{index}]"
        entry = _mapping(raw, where=where)
        _exact_fields(entry, {"metric", "slice", "weight"}, where=where)
        key = _metric_key(entry, where=where)
        target_keys.append(key)
        weights.append(_number(entry["weight"], where=f"{where}.weight", minimum=0.0))
        if weights[-1] == 0.0:
            raise GateError(f"{where}.weight must be positive")
        if key not in protected_keys:
            raise GateError(f"{where} must also be protected")
    if len(target_keys) != len(set(target_keys)):
        raise GateError("gate.target_metrics contains duplicate metric/slice entries")
    if not math.isclose(sum(weights), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise GateError("gate.target_metrics weights must sum to 1")

    limits = _mapping(gate["operational_limits"], where="gate.operational_limits")
    _exact_fields(
        limits,
        {"profile_id", "max_artifact_size_bytes", "max_latency_ms_per_100_tokens"},
        where="gate.operational_limits",
    )
    _string(limits["profile_id"], where="gate.operational_limits.profile_id")
    _positive_integer(
        limits["max_artifact_size_bytes"],
        where="gate.operational_limits.max_artifact_size_bytes",
    )
    _number(
        limits["max_latency_ms_per_100_tokens"],
        where="gate.operational_limits.max_latency_ms_per_100_tokens",
        minimum=0.0,
    )
    if float(limits["max_latency_ms_per_100_tokens"]) == 0.0:
        raise GateError("gate latency limit must be positive")

    promotion = _mapping(gate["promotion"], where="gate.promotion")
    _exact_fields(
        promotion,
        {"minimum_weighted_target_gain", "require_pareto_non_dominated"},
        where="gate.promotion",
    )
    _number(
        promotion["minimum_weighted_target_gain"],
        where="gate.promotion.minimum_weighted_target_gain",
    )
    if promotion["require_pareto_non_dominated"] is not True:
        raise GateError("gate promotion must require a non-dominated candidate")

    tie_breaking = gate["tie_breaking"]
    if not isinstance(tie_breaking, list) or len(tie_breaking) != len(_TIE_FIELDS):
        raise GateError("gate.tie_breaking must declare all five deterministic fields")
    seen_ties: list[str] = []
    for index, raw in enumerate(tie_breaking):
        where = f"gate.tie_breaking[{index}]"
        entry = _mapping(raw, where=where)
        _exact_fields(entry, {"field", "direction"}, where=where)
        field = _string(entry["field"], where=f"{where}.field")
        if field not in _TIE_FIELDS or field in seen_ties:
            raise GateError(f"{where}.field is unknown or duplicated")
        direction = entry["direction"]
        expected_direction = (
            "ascending"
            if field in {"artifact_size_bytes", "latency_ms_per_100_tokens", "candidate_id"}
            else "descending"
        )
        if direction != expected_direction:
            raise GateError(f"{where}.direction must be {expected_direction}")
        seen_ties.append(field)
    if seen_ties[-1] != "candidate_id":
        raise GateError("gate.tie_breaking must end with ascending candidate_id")

    recorded = _sha256(gate["gate_sha256"], where="gate.gate_sha256")
    if verify_digest:
        actual = document_sha256(gate, "gate_sha256")
        if recorded != actual:
            raise GateError(
                f"gate digest mismatch: expected {recorded}, recomputed {actual}"
            )


def stamp_gate(gate: Mapping[str, Any]) -> dict[str, Any]:
    """Return a canonical-digest-stamped copy of an otherwise complete gate."""

    stamped = dict(stamp_document(gate, "gate_sha256"))
    validate_gate(stamped)
    return stamped


def _duplicate_guard(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GateError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: str | Path, *, maximum_bytes: int, where: str) -> dict[str, Any]:
    target = Path(path)
    try:
        size = target.stat().st_size
        if size > maximum_bytes:
            raise GateError(f"{where} exceeds the {maximum_bytes}-byte input limit")
        raw = target.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicate_guard,
            parse_constant=lambda token: (_ for _ in ()).throw(
                GateError(f"{where} contains non-finite JSON number {token}")
            ),
        )
    except GateError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read {where} {target}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError(f"{where} must contain a JSON object")
    return value


def load_gate(path: str | Path) -> dict[str, Any]:
    """Load and verify a frozen gate with hostile-input safeguards."""

    gate = _load_json(path, maximum_bytes=_MAX_GATE_BYTES, where="gate")
    validate_gate(gate)
    return gate


def validate_candidate(
    candidate: Mapping[str, Any],
    *,
    gate: Mapping[str, Any] | None = None,
    manifest: Mapping[str, Any] | None = None,
) -> None:
    """Validate a candidate descriptor and its embedded development report."""

    candidate = _mapping(candidate, where="candidate")
    _exact_fields(
        candidate,
        {
            "format",
            "candidate_id",
            "gate_sha256",
            "training_run_receipt_sha256",
            "report",
            "operational",
            "candidate_sha256",
        },
        where="candidate",
    )
    if candidate["format"] != CANDIDATE_FORMAT:
        raise GateError(f"unsupported candidate format: {candidate['format']!r}")
    candidate_id = _string(candidate["candidate_id"], where="candidate.candidate_id")
    gate_sha = _sha256(candidate["gate_sha256"], where="candidate.gate_sha256")
    _sha256(
        candidate["training_run_receipt_sha256"],
        where="candidate.training_run_receipt_sha256",
    )
    report = _mapping(candidate["report"], where="candidate.report")
    try:
        verify_report(report, manifest=manifest)
    except Exception as exc:
        raise GateError(f"candidate report is invalid: {exc}") from exc
    if report.get("format") != REPORT_FORMAT:
        raise GateError("candidate uses an unsupported development-report format")
    run = _mapping(report.get("run"), where="candidate.report.run")
    model = _mapping(run.get("model"), where="candidate.report.run.model")
    if model.get("identity") != candidate_id:
        raise GateError("candidate_id must equal the development report model identity")

    operational = _mapping(candidate["operational"], where="candidate.operational")
    _exact_fields(
        operational,
        {"profile_id", "artifact_size_bytes", "latency_ms_per_100_tokens"},
        where="candidate.operational",
    )
    _string(operational["profile_id"], where="candidate.operational.profile_id")
    _positive_integer(
        operational["artifact_size_bytes"],
        where="candidate.operational.artifact_size_bytes",
    )
    latency = _number(
        operational["latency_ms_per_100_tokens"],
        where="candidate.operational.latency_ms_per_100_tokens",
        minimum=0.0,
    )
    if latency == 0.0:
        raise GateError("candidate latency must be positive")

    recorded = _sha256(candidate["candidate_sha256"], where="candidate.candidate_sha256")
    actual = document_sha256(candidate, "candidate_sha256")
    if recorded != actual:
        raise GateError(
            f"candidate digest mismatch: expected {recorded}, recomputed {actual}"
        )
    if gate is not None:
        validate_gate(gate)
        if gate_sha != gate["gate_sha256"]:
            raise GateError("candidate is bound to a different selection gate")
        if report.get("manifest_sha256") != gate["development_manifest_sha256"]:
            raise GateError("candidate report is bound to a different development manifest")
        if run.get("decoder") != gate["decoder"]:
            raise GateError("candidate report decoder differs from the selection gate")
        if operational["profile_id"] != gate["operational_limits"]["profile_id"]:
            raise GateError("candidate operational profile differs from the selection gate")
    if manifest is not None:
        try:
            verify_manifest(manifest)
        except Exception as exc:
            raise GateError(f"development manifest is invalid: {exc}") from exc
        manifest_sha = manifest.get("manifest_sha256")
        if gate is not None and manifest_sha != gate["development_manifest_sha256"]:
            raise GateError("development manifest differs from the selection gate")


def stamp_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Return a digest-stamped copy of a candidate descriptor."""

    stamped = dict(stamp_document(candidate, "candidate_sha256"))
    validate_candidate(stamped)
    return stamped


def load_candidate(
    path: str | Path,
    *,
    gate: Mapping[str, Any] | None = None,
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load and verify a candidate descriptor and embedded report."""

    candidate = _load_json(
        path, maximum_bytes=_MAX_CANDIDATE_BYTES, where="candidate descriptor"
    )
    validate_candidate(candidate, gate=gate, manifest=manifest)
    return candidate


def _oov_token_value(report: Mapping[str, Any], metric: str) -> float | None:
    """Per-token accuracy over out-of-vocabulary tokens from the error anatomy.

    The ``oov`` item slice covers every sentence that contains at least one OOV
    token, so a slice-summed metric there is whole-sentence accuracy over
    OOV-containing sentences, most of whose tokens are in vocabulary. The overall
    error anatomy already counts the true per-OOV-token hits, so this reads that
    band directly (``upos_correct`` / ``lemma_correct`` over ``tokens``).
    """
    anatomy = report.get("error_anatomy")
    overall = anatomy.get("overall") if isinstance(anatomy, Mapping) else None
    bands = overall.get("frequency_bands") if isinstance(overall, Mapping) else None
    band = bands.get("oov") if isinstance(bands, Mapping) else None
    if not isinstance(band, Mapping):
        return None
    tokens = band.get("tokens")
    correct = band.get(f"{metric}_correct")
    if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens <= 0:
        return None
    if not isinstance(correct, int) or isinstance(correct, bool) or not 0 <= correct <= tokens:
        return None
    return correct / tokens


def _metric_value(report: Mapping[str, Any], metric: str, slice_id: str) -> float | None:
    if slice_id == "aggregate":
        entry = _mapping(
            _mapping(report.get("metrics"), where="report.metrics").get(metric),
            where=f"report.metrics.{metric}",
        )
        value = entry.get("value")
        return None if value is None else _number(value, where=f"report.metrics.{metric}.value")
    if slice_id == "oov-token":
        return _oov_token_value(report, metric)
    numerator = 0
    denominator = 0
    for raw_item in report.get("items", []):
        item = _mapping(raw_item, where="report item")
        if slice_id not in item.get("slice_ids", []):
            continue
        metrics = _mapping(item.get("metrics"), where="report item.metrics")
        entry = _mapping(metrics.get(metric), where=f"report item.metrics.{metric}")
        if entry.get("value") is None:
            continue
        numerator += int(entry["numerator"])
        denominator += int(entry["denominator"])
    return numerator / denominator if denominator else None


def _candidate_analysis(
    candidate: Mapping[str, Any],
    baseline: Mapping[str, Any],
    gate: Mapping[str, Any],
) -> dict[str, Any]:
    report = _mapping(candidate["report"], where="candidate.report")
    baseline_report = _mapping(baseline["report"], where="baseline.report")
    failures: list[str] = []
    protected_checks: list[dict[str, Any]] = []
    protected_deltas: list[float] = []
    for raw in gate["protected_metrics"]:
        entry = _mapping(raw, where="protected metric")
        metric, slice_id = str(entry["metric"]), str(entry["slice"])
        candidate_value = _metric_value(report, metric, slice_id)
        baseline_value = _metric_value(baseline_report, metric, slice_id)
        if candidate_value is None or baseline_value is None:
            failures.append(f"unavailable protected metric {metric}@{slice_id}")
            delta = None
            passed = False
        else:
            delta = candidate_value - baseline_value
            protected_deltas.append(delta)
            passed = delta >= -float(entry["max_regression"])
            if not passed:
                failures.append(f"protected regression {metric}@{slice_id}")
        protected_checks.append(
            {
                "metric": metric,
                "slice": slice_id,
                "candidate": candidate_value,
                "baseline": baseline_value,
                "delta": delta,
                "max_regression": float(entry["max_regression"]),
                "passed": passed,
            }
        )

    target_values: list[dict[str, Any]] = []
    weighted_gain = 0.0
    pareto_vector: list[float] = []
    for raw in gate["target_metrics"]:
        entry = _mapping(raw, where="target metric")
        metric, slice_id = str(entry["metric"]), str(entry["slice"])
        candidate_value = _metric_value(report, metric, slice_id)
        baseline_value = _metric_value(baseline_report, metric, slice_id)
        if candidate_value is None or baseline_value is None:
            failures.append(f"unavailable target metric {metric}@{slice_id}")
            delta = None
        else:
            delta = candidate_value - baseline_value
            weighted_gain += float(entry["weight"]) * delta
            pareto_vector.append(candidate_value)
        target_values.append(
            {
                "metric": metric,
                "slice": slice_id,
                "candidate": candidate_value,
                "baseline": baseline_value,
                "delta": delta,
                "weight": float(entry["weight"]),
            }
        )

    operational = _mapping(candidate["operational"], where="candidate.operational")
    limits = _mapping(gate["operational_limits"], where="gate.operational_limits")
    if int(operational["artifact_size_bytes"]) > int(limits["max_artifact_size_bytes"]):
        failures.append("artifact size exceeds gate limit")
    if float(operational["latency_ms_per_100_tokens"]) > float(
        limits["max_latency_ms_per_100_tokens"]
    ):
        failures.append("latency exceeds gate limit")
    if weighted_gain < float(gate["promotion"]["minimum_weighted_target_gain"]):
        failures.append("weighted target gain is below the promotion floor")

    return {
        "candidate_id": candidate["candidate_id"],
        "candidate_sha256": candidate["candidate_sha256"],
        "report_sha256": report["report_sha256"],
        "training_run_receipt_sha256": candidate["training_run_receipt_sha256"],
        "eligible": not failures,
        "failures": sorted(set(failures)),
        "protected_checks": protected_checks,
        "target_values": target_values,
        "weighted_target_gain": weighted_gain,
        "worst_protected_delta": min(protected_deltas) if protected_deltas else None,
        "operational": copy.deepcopy(operational),
        "pareto_front": None,
        "_pareto_vector": pareto_vector,
    }


def _dominates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_values = left["_pareto_vector"]
    right_values = right["_pareto_vector"]
    return all(a >= b for a, b in zip(left_values, right_values, strict=True)) and any(
        a > b for a, b in zip(left_values, right_values, strict=True)
    )


def _assign_pareto_fronts(entries: list[dict[str, Any]]) -> None:
    remaining = list(entries)
    front = 0
    while remaining:
        current = [
            entry
            for entry in remaining
            if not any(
                other is not entry and _dominates(other, entry) for other in remaining
            )
        ]
        if not current:  # pragma: no cover - finite strict dominance is acyclic
            raise GateError("could not construct Pareto fronts")
        for entry in current:
            entry["pareto_front"] = front
        remaining = [entry for entry in remaining if entry not in current]
        front += 1


def _compare_entries(
    left: Mapping[str, Any], right: Mapping[str, Any], tie_breaking: Sequence[Mapping[str, Any]]
) -> int:
    left_front = int(left["pareto_front"])
    right_front = int(right["pareto_front"])
    if left_front != right_front:
        return -1 if left_front < right_front else 1
    for rule in tie_breaking:
        field = str(rule["field"])
        if field in {"artifact_size_bytes", "latency_ms_per_100_tokens"}:
            left_value = left["operational"][field]
            right_value = right["operational"][field]
        else:
            left_value = left[field]
            right_value = right[field]
        if left_value == right_value:
            continue
        ascending = rule["direction"] == "ascending"
        if left_value < right_value:
            return -1 if ascending else 1
        return 1 if ascending else -1
    return 0


def _order_entries(
    entries: Sequence[dict[str, Any]],
    tie_breaking: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    def comparator(left: dict[str, Any], right: dict[str, Any]) -> int:
        return _compare_entries(left, right, tie_breaking)

    return sorted(entries, key=functools.cmp_to_key(comparator))


def select_candidates(
    *,
    gate: Mapping[str, Any],
    manifest: Mapping[str, Any],
    baseline: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Apply one frozen gate and return a content-addressed deterministic decision."""

    validate_gate(gate)
    try:
        verify_manifest(manifest)
    except Exception as exc:
        raise GateError(f"development manifest is invalid: {exc}") from exc
    if manifest.get("manifest_sha256") != gate["development_manifest_sha256"]:
        raise GateError("development manifest differs from the selection gate")
    validate_candidate(baseline, gate=gate, manifest=manifest)
    if not candidates:
        raise GateError("selection requires at least one candidate")
    candidate_ids: list[str] = []
    analyses: list[dict[str, Any]] = []
    for candidate in candidates:
        validate_candidate(candidate, gate=gate, manifest=manifest)
        candidate_id = str(candidate["candidate_id"])
        if candidate_id == baseline["candidate_id"]:
            raise GateError("candidate IDs must differ from the baseline ID")
        candidate_ids.append(candidate_id)
        analyses.append(_candidate_analysis(candidate, baseline, gate))
    if len(candidate_ids) != len(set(candidate_ids)):
        raise GateError("candidate IDs must be unique")

    eligible = [entry for entry in analyses if entry["eligible"]]
    _assign_pareto_fronts(eligible)
    ordered = _order_entries(eligible, gate["tie_breaking"])
    if gate["promotion"]["require_pareto_non_dominated"]:
        selectable = [entry for entry in ordered if entry["pareto_front"] == 0]
    else:  # validation currently rejects this, kept explicit for readable result logic
        selectable = ordered
    ranking = [entry["candidate_id"] for entry in ordered]
    rejected = sorted(
        (entry for entry in analyses if not entry["eligible"]),
        key=lambda entry: entry["candidate_id"],
    )
    for entry in analyses:
        entry.pop("_pareto_vector")
    result = dict(stamp_document(
        {
            "format": RESULT_FORMAT,
            "claim_status": CLAIM_STATUS,
            "gate_sha256": gate["gate_sha256"],
            "baseline": {
                "candidate_id": baseline["candidate_id"],
                "candidate_sha256": baseline["candidate_sha256"],
                "report_sha256": baseline["report"]["report_sha256"],
                "training_run_receipt_sha256": baseline["training_run_receipt_sha256"],
            },
            "ranking": ranking,
            "candidates": ordered + rejected,
            "selected_candidate_id": selectable[0]["candidate_id"] if selectable else None,
        },
        "result_sha256",
    ))
    verify_selection_result(result, gate=gate)
    return result


def verify_selection_result(
    result: Mapping[str, Any], *, gate: Mapping[str, Any] | None = None
) -> None:
    """Verify the closed result shape and its canonical digest."""

    result = _mapping(result, where="selection result")
    _exact_fields(
        result,
        {
            "format",
            "claim_status",
            "gate_sha256",
            "baseline",
            "ranking",
            "candidates",
            "selected_candidate_id",
            "result_sha256",
        },
        where="selection result",
    )
    if result["format"] != RESULT_FORMAT or result["claim_status"] != CLAIM_STATUS:
        raise GateError("selection result format or claim status is invalid")
    gate_sha = _sha256(result["gate_sha256"], where="selection result.gate_sha256")
    if gate is not None:
        validate_gate(gate)
        if gate_sha != gate["gate_sha256"]:
            raise GateError("selection result is bound to a different gate")
    baseline = _mapping(result["baseline"], where="selection result.baseline")
    _exact_fields(
        baseline,
        {
            "candidate_id",
            "candidate_sha256",
            "report_sha256",
            "training_run_receipt_sha256",
        },
        where="selection result.baseline",
    )
    _string(baseline["candidate_id"], where="selection result.baseline.candidate_id")
    for field in ("candidate_sha256", "report_sha256", "training_run_receipt_sha256"):
        _sha256(baseline[field], where=f"selection result.baseline.{field}")
    ranking = result["ranking"]
    candidates = result["candidates"]
    if (
        not isinstance(ranking, list)
        or any(not isinstance(item, str) or not item for item in ranking)
        or len(ranking) != len(set(ranking))
    ):
        raise GateError("selection result ranking is malformed")
    if not isinstance(candidates, list) or not candidates:
        raise GateError("selection result candidates must be a non-empty array")
    candidate_ids = []
    pareto_vectors: dict[str, list[float]] = {}
    for index, raw in enumerate(candidates):
        where = f"selection result.candidates[{index}]"
        entry = _mapping(raw, where=f"selection result.candidates[{index}]")
        _exact_fields(
            entry,
            {
                "candidate_id",
                "candidate_sha256",
                "report_sha256",
                "training_run_receipt_sha256",
                "eligible",
                "failures",
                "protected_checks",
                "target_values",
                "weighted_target_gain",
                "worst_protected_delta",
                "operational",
                "pareto_front",
            },
            where=where,
        )
        candidate_ids.append(_string(entry["candidate_id"], where=f"{where}.candidate_id"))
        for field in (
            "candidate_sha256",
            "report_sha256",
            "training_run_receipt_sha256",
        ):
            _sha256(entry[field], where=f"{where}.{field}")
        if not isinstance(entry["eligible"], bool):
            raise GateError("selection result candidate eligibility must be boolean")
        failures = entry["failures"]
        if (
            not isinstance(failures, list)
            or any(not isinstance(failure, str) or not failure for failure in failures)
            or failures != sorted(set(failures))
        ):
            raise GateError("selection result candidate failures must be sorted and unique")
        if entry["eligible"] != (not failures):
            raise GateError("selection result candidate eligibility differs from failures")

        protected_checks = entry["protected_checks"]
        if not isinstance(protected_checks, list) or not protected_checks:
            raise GateError(f"{where}.protected_checks must be a non-empty array")
        protected_keys: list[tuple[str, str]] = []
        protected_deltas: list[float] = []
        derived_failures: list[str] = []
        for check_index, raw_check in enumerate(protected_checks):
            check_where = f"{where}.protected_checks[{check_index}]"
            check = _mapping(raw_check, where=check_where)
            _exact_fields(
                check,
                {
                    "metric",
                    "slice",
                    "candidate",
                    "baseline",
                    "delta",
                    "max_regression",
                    "passed",
                },
                where=check_where,
            )
            key = _metric_key(check, where=check_where)
            protected_keys.append(key)
            candidate_value = _optional_number(
                check["candidate"], where=f"{check_where}.candidate"
            )
            baseline_value = _optional_number(
                check["baseline"], where=f"{check_where}.baseline"
            )
            delta = _optional_number(check["delta"], where=f"{check_where}.delta")
            maximum = _number(
                check["max_regression"],
                where=f"{check_where}.max_regression",
                minimum=0.0,
            )
            if maximum > 1.0:
                raise GateError(f"{check_where}.max_regression must not exceed 1")
            if not isinstance(check["passed"], bool):
                raise GateError(f"{check_where}.passed must be boolean")
            if candidate_value is None or baseline_value is None:
                if delta is not None or check["passed"]:
                    raise GateError(f"{check_where} availability fields disagree")
                derived_failures.append(f"unavailable protected metric {key[0]}@{key[1]}")
            else:
                expected_delta = candidate_value - baseline_value
                if delta is None or not _same_number(delta, expected_delta):
                    raise GateError(f"{check_where}.delta differs from its values")
                protected_deltas.append(delta)
                expected_passed = delta >= -maximum
                if check["passed"] != expected_passed:
                    raise GateError(f"{check_where}.passed differs from its regression bound")
                if not expected_passed:
                    derived_failures.append(f"protected regression {key[0]}@{key[1]}")
        if len(protected_keys) != len(set(protected_keys)):
            raise GateError(f"{where}.protected_checks contains duplicates")

        target_values = entry["target_values"]
        if not isinstance(target_values, list) or not target_values:
            raise GateError(f"{where}.target_values must be a non-empty array")
        target_keys: list[tuple[str, str]] = []
        weighted_gain = 0.0
        pareto_vector: list[float] = []
        for target_index, raw_target in enumerate(target_values):
            target_where = f"{where}.target_values[{target_index}]"
            target = _mapping(raw_target, where=target_where)
            _exact_fields(
                target,
                {"metric", "slice", "candidate", "baseline", "delta", "weight"},
                where=target_where,
            )
            key = _metric_key(target, where=target_where)
            target_keys.append(key)
            candidate_value = _optional_number(
                target["candidate"], where=f"{target_where}.candidate"
            )
            baseline_value = _optional_number(
                target["baseline"], where=f"{target_where}.baseline"
            )
            delta = _optional_number(target["delta"], where=f"{target_where}.delta")
            weight = _number(
                target["weight"], where=f"{target_where}.weight", minimum=0.0
            )
            if weight == 0.0:
                raise GateError(f"{target_where}.weight must be positive")
            if candidate_value is None or baseline_value is None:
                if delta is not None:
                    raise GateError(f"{target_where}.delta must be unavailable")
                derived_failures.append(f"unavailable target metric {key[0]}@{key[1]}")
            else:
                expected_delta = candidate_value - baseline_value
                if delta is None or not _same_number(delta, expected_delta):
                    raise GateError(f"{target_where}.delta differs from its values")
                weighted_gain += weight * delta
                pareto_vector.append(candidate_value)
        if len(target_keys) != len(set(target_keys)):
            raise GateError(f"{where}.target_values contains duplicates")
        recorded_gain = _number(
            entry["weighted_target_gain"], where=f"{where}.weighted_target_gain"
        )
        if not _same_number(recorded_gain, weighted_gain):
            raise GateError(f"{where}.weighted_target_gain differs from target values")
        recorded_worst = _optional_number(
            entry["worst_protected_delta"], where=f"{where}.worst_protected_delta"
        )
        expected_worst = min(protected_deltas) if protected_deltas else None
        if (recorded_worst is None) != (expected_worst is None) or (
            recorded_worst is not None
            and expected_worst is not None
            and not _same_number(recorded_worst, expected_worst)
        ):
            raise GateError(f"{where}.worst_protected_delta differs from protected values")

        operational = _mapping(entry["operational"], where=f"{where}.operational")
        _exact_fields(
            operational,
            {"profile_id", "artifact_size_bytes", "latency_ms_per_100_tokens"},
            where=f"{where}.operational",
        )
        _string(operational["profile_id"], where=f"{where}.operational.profile_id")
        _positive_integer(
            operational["artifact_size_bytes"],
            where=f"{where}.operational.artifact_size_bytes",
        )
        latency = _number(
            operational["latency_ms_per_100_tokens"],
            where=f"{where}.operational.latency_ms_per_100_tokens",
            minimum=0.0,
        )
        if latency == 0.0:
            raise GateError(f"{where}.operational latency must be positive")

        if gate is not None:
            expected_protected = [
                (str(item["metric"]), str(item["slice"]))
                for item in gate["protected_metrics"]
            ]
            expected_targets = [
                (str(item["metric"]), str(item["slice"]))
                for item in gate["target_metrics"]
            ]
            if protected_keys != expected_protected or target_keys != expected_targets:
                raise GateError(f"{where} metric order differs from the gate")
            for check, policy in zip(
                protected_checks, gate["protected_metrics"], strict=True
            ):
                if not _same_number(
                    float(check["max_regression"]), float(policy["max_regression"])
                ):
                    raise GateError(f"{where} protected bound differs from the gate")
            for target, policy in zip(target_values, gate["target_metrics"], strict=True):
                if not _same_number(float(target["weight"]), float(policy["weight"])):
                    raise GateError(f"{where} target weight differs from the gate")
            limits = gate["operational_limits"]
            if operational["profile_id"] != limits["profile_id"]:
                derived_failures.append("operational profile differs from gate")
            if operational["artifact_size_bytes"] > limits["max_artifact_size_bytes"]:
                derived_failures.append("artifact size exceeds gate limit")
            if latency > limits["max_latency_ms_per_100_tokens"]:
                derived_failures.append("latency exceeds gate limit")
            if recorded_gain < gate["promotion"]["minimum_weighted_target_gain"]:
                derived_failures.append("weighted target gain is below the promotion floor")
            if failures != sorted(set(derived_failures)):
                raise GateError(f"{where}.failures differs from the gate decision")

        pareto_vectors[str(entry["candidate_id"])] = pareto_vector
        if entry["eligible"]:
            if not isinstance(entry["pareto_front"], int) or entry["pareto_front"] < 0:
                raise GateError("eligible selection result candidate needs a Pareto front")
        elif entry["pareto_front"] is not None:
            raise GateError("ineligible selection result candidate cannot have a Pareto front")
    if len(candidate_ids) != len(set(candidate_ids)):
        raise GateError("selection result candidate IDs must be unique")
    eligible_ids = [entry["candidate_id"] for entry in candidates if entry["eligible"]]
    if ranking != eligible_ids:
        raise GateError("selection result ranking differs from eligible candidate order")
    if gate is not None:
        eligible_entries = [entry for entry in candidates if entry["eligible"]]
        expected_entries: list[dict[str, Any]] = [
            copy.deepcopy(dict(entry)) for entry in eligible_entries
        ]
        for entry in expected_entries:
            entry["pareto_front"] = None
            entry["_pareto_vector"] = pareto_vectors[str(entry["candidate_id"])]
        _assign_pareto_fronts(expected_entries)
        expected_entries = _order_entries(expected_entries, gate["tie_breaking"])
        if [entry["candidate_id"] for entry in expected_entries] != ranking or any(
            expected["pareto_front"] != actual["pareto_front"]
            for expected, actual in zip(expected_entries, eligible_entries, strict=True)
        ):
            raise GateError("selection result Pareto ranking differs from the gate")
    selected = result["selected_candidate_id"]
    expected_selected = ranking[0] if ranking else None
    if selected != expected_selected:
        raise GateError("selection result selected candidate differs from the ranking")
    recorded = _sha256(result["result_sha256"], where="selection result.result_sha256")
    actual = document_sha256(result, "result_sha256")
    if recorded != actual:
        raise GateError(
            f"selection result digest mismatch: expected {recorded}, recomputed {actual}"
        )


def _write_result(path: str | Path, result: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_json(result).encode("utf-8") + b"\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        gate = load_gate(args.gate)
        manifest = load_manifest_document(
            args.manifest, verify=True, digest_field="manifest_sha256"
        )
        verify_manifest(manifest)
        baseline = load_candidate(
            args.baseline, gate=gate, manifest=manifest
        )
        candidates = [
            load_candidate(path, gate=gate, manifest=manifest)
            for path in args.candidate
        ]
        result = select_candidates(
            gate=gate,
            manifest=manifest,
            baseline=baseline,
            candidates=candidates,
        )
        _write_result(args.output, result)
    except (GateError, ManifestError) as exc:
        print(f"model selection failed: {exc}", file=sys.stderr)
        return 2
    print(canonical_json({"ok": True, "output": str(args.output), "selected_candidate_id": result["selected_candidate_id"], "result_sha256": result["result_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CANDIDATE_FORMAT",
    "CLAIM_STATUS",
    "GATE_FORMAT",
    "METRICS",
    "RESULT_FORMAT",
    "GateError",
    "load_candidate",
    "load_gate",
    "main",
    "select_candidates",
    "stamp_candidate",
    "stamp_gate",
    "validate_candidate",
    "validate_gate",
    "verify_selection_result",
]
