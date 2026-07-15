"""Award evidence-backed neural runtime labels from artifact operational records.

This module never runs inference and never exposes private development scores.  It
validates a passing optimization decision, the exact candidate/reference runtime
records bound to that decision, and additional same-environment repetitions required
by the frozen runtime-variant policy. The resulting report contains operational comparisons and
content identities only; it cannot make an unavailable package registry entry loadable
by itself.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:  # The training directory is also executed directly as a script directory.
    from . import artifact_qualification as qualification
    from . import development_manifest as manifest_mod
except ImportError:  # pragma: no cover - exercised by ``python training/foo.py``
    import artifact_qualification as qualification  # type: ignore[no-redef]
    import development_manifest as manifest_mod  # type: ignore[no-redef]

__all__ = [
    "AWARD_FORMAT",
    "AWARD_STATUS",
    "POLICY_FORMAT",
    "POLICY_STATUS",
    "VariantAwardError",
    "build_award",
    "load_award",
    "load_policy",
    "validate_award",
    "validate_policy",
    "verify_award",
]

POLICY_FORMAT = "pyaegean-runtime-variant-policy/1"
POLICY_STATUS = "selection-policy-not-performance-evidence"
AWARD_FORMAT = "pyaegean-runtime-variant-award/1"
AWARD_STATUS = "artifact-operational-selection-not-task-score"
_LABELS = ("fast", "compact", "balanced")
_MAX_JSON_BYTES = 8 * 1024 * 1024


class VariantAwardError(ValueError):
    """Raised when runtime-label policy or award evidence is invalid."""


def _exact_fields(value: Mapping[str, Any], expected: set[str], *, where: str) -> None:
    actual = set(value)
    if actual != expected:
        raise VariantAwardError(
            f"{where} fields differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _mapping(value: Any, *, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise VariantAwardError(f"{where} must be an object")
    return value


def _string(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise VariantAwardError(f"{where} must be a non-empty trimmed string")
    return value


def _sha256(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise VariantAwardError(f"{where} must be a lowercase SHA-256 string")
    return value


def _positive_int(value: Any, *, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise VariantAwardError(f"{where} must be a positive integer")
    return value


def _nonnegative_int(value: Any, *, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise VariantAwardError(f"{where} must be a non-negative integer")
    return value


def _ratio(value: Any, *, where: str, optional: bool = False) -> float | None:
    if value is None and optional:
        return None
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) <= 0.0
    ):
        suffix = " or null" if optional else ""
        raise VariantAwardError(f"{where} must be a positive finite number{suffix}")
    return float(value)


def _reject_duplicates(where: str):
    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise VariantAwardError(f"duplicate JSON key in {where}: {key!r}")
            result[key] = value
        return result

    return hook


def _load_json(path: str | Path, *, where: str) -> dict[str, Any]:
    source = Path(path)
    try:
        size = source.stat().st_size
        if not 2 <= size <= _MAX_JSON_BYTES:
            raise VariantAwardError(
                f"{where} size {size} is outside 2..{_MAX_JSON_BYTES} bytes"
            )
        blob = source.read_bytes()
        if len(blob) != size:
            raise VariantAwardError(f"{where} changed while it was being read")
        value = json.loads(
            blob.decode("utf-8"),
            object_pairs_hook=_reject_duplicates(where),
        )
    except VariantAwardError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VariantAwardError(f"could not read {where}: {exc}") from exc
    if not isinstance(value, dict):
        raise VariantAwardError(f"{where} must be a JSON object")
    return value


def validate_policy(policy: Mapping[str, Any]) -> None:
    """Validate the exact, content-addressed runtime-label policy."""

    policy = _mapping(policy, where="variant policy")
    _exact_fields(
        policy,
        {
            "format",
            "policy_id",
            "claim_status",
            "qualification_gate_sha256",
            "measurement_profile_id",
            "labels",
            "policy_sha256",
        },
        where="variant policy",
    )
    if policy["format"] != POLICY_FORMAT or policy["claim_status"] != POLICY_STATUS:
        raise VariantAwardError("unknown runtime variant policy format/claim status")
    _string(policy["policy_id"], where="variant policy.policy_id")
    _sha256(
        policy["qualification_gate_sha256"],
        where="variant policy.qualification_gate_sha256",
    )
    _string(
        policy["measurement_profile_id"],
        where="variant policy.measurement_profile_id",
    )
    labels = _mapping(policy["labels"], where="variant policy.labels")
    _exact_fields(labels, set(_LABELS), where="variant policy.labels")
    record_fields = {
        "operational_runs",
        "max_artifact_size_ratio",
        "max_median_latency_ratio",
        "max_median_peak_resident_memory_ratio",
        "minimum_runs_below_reference_median_latency",
    }
    for label in _LABELS:
        record = _mapping(labels[label], where=f"variant policy.labels.{label}")
        _exact_fields(record, record_fields, where=f"variant policy.labels.{label}")
        runs = _positive_int(
            record["operational_runs"],
            where=f"variant policy.labels.{label}.operational_runs",
        )
        for field in (
            "max_artifact_size_ratio",
            "max_median_latency_ratio",
            "max_median_peak_resident_memory_ratio",
        ):
            _ratio(record[field], where=f"variant policy.labels.{label}.{field}", optional=True)
        minimum = _nonnegative_int(
            record["minimum_runs_below_reference_median_latency"],
            where=(
                f"variant policy.labels.{label}."
                "minimum_runs_below_reference_median_latency"
            ),
        )
        if minimum > runs:
            raise VariantAwardError(
                f"variant policy label {label!r} requires more improvements than runs"
            )
        if not any(record[field] is not None for field in record_fields if field.startswith("max_")):
            raise VariantAwardError(f"variant policy label {label!r} has no measured threshold")
    try:
        manifest_mod.verify_document(policy, "policy_sha256")
    except Exception as exc:
        raise VariantAwardError(f"runtime variant policy digest mismatch: {exc}") from exc


def load_policy(path: str | Path) -> dict[str, Any]:
    """Load a bounded, duplicate-safe, digest-verified policy."""

    policy = _load_json(path, where="runtime variant policy")
    validate_policy(policy)
    return policy


def _manifest_file_sha(evidence: Mapping[str, Any]) -> str:
    files = evidence["artifact"]["files"]
    for entry in files:
        if entry["path"] == "manifest.json":
            return _sha256(entry["sha256"], where="artifact manifest file digest")
    raise VariantAwardError("operational artifact does not list manifest.json")


def _qualification_binding(value: Any, *, where: str) -> Mapping[str, Any]:
    binding = _mapping(value, where=where)
    _exact_fields(
        binding,
        {
            "model_identity",
            "report_sha256",
            "prediction_sha256",
            "operational_evidence_sha256",
        },
        where=where,
    )
    _string(binding["model_identity"], where=f"{where}.model_identity")
    for field in (
        "report_sha256",
        "prediction_sha256",
        "operational_evidence_sha256",
    ):
        _sha256(binding[field], where=f"{where}.{field}")
    return binding


def _cpu_passes(evidence: Mapping[str, Any]) -> bool:
    return any(
        entry["provider"] == "CPUExecutionProvider" and entry["status"] == "pass"
        for entry in evidence["provider_matrix"]
    )


def _validate_series(
    values: Sequence[Mapping[str, Any]],
    *,
    expected_runs: int,
    expected_identity: str,
    expected_manifest: str,
    expected_profile: str,
    where: str,
) -> list[Mapping[str, Any]]:
    if isinstance(values, (str, bytes)) or len(values) != expected_runs:
        raise VariantAwardError(
            f"{where} must contain exactly {expected_runs} operational record(s)"
        )
    result = list(values)
    digests: list[str] = []
    artifact_identity: tuple[Any, ...] | None = None
    for index, evidence in enumerate(result):
        try:
            qualification.validate_operational_evidence(evidence)
        except Exception as exc:
            raise VariantAwardError(f"invalid {where}[{index}]: {exc}") from exc
        if evidence["profile_id"] != expected_profile:
            raise VariantAwardError(f"{where}[{index}] uses a different measurement profile")
        if evidence["development_manifest_sha256"] != expected_manifest:
            raise VariantAwardError(f"{where}[{index}] uses a different development manifest")
        artifact = evidence["artifact"]
        if artifact["identity"] != expected_identity:
            raise VariantAwardError(f"{where}[{index}] uses a different model identity")
        if not _cpu_passes(evidence):
            raise VariantAwardError(f"{where}[{index}] lacks a passing CPU provider probe")
        current_identity = (
            artifact["directory_sha256"],
            artifact["model_sha256"],
            artifact["artifact_size_bytes"],
            artifact["model_size_bytes"],
            _manifest_file_sha(evidence),
        )
        if artifact_identity is None:
            artifact_identity = current_identity
        elif current_identity != artifact_identity:
            raise VariantAwardError(f"{where} records identify different artifact bytes")
        digests.append(evidence["evidence_sha256"])
    if len(set(digests)) != len(digests):
        raise VariantAwardError(f"{where} repeats an operational evidence record")
    return sorted(result, key=lambda item: item["evidence_sha256"])


def _identity(values: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    first = values[0]
    artifact = first["artifact"]
    return {
        "model_identity": artifact["identity"],
        "artifact_directory_sha256": artifact["directory_sha256"],
        "model_sha256": artifact["model_sha256"],
        "bundle_manifest_sha256": _manifest_file_sha(first),
        "operational_evidence_sha256": [
            item["evidence_sha256"] for item in values
        ],
    }


def _measurements(
    reference: Sequence[Mapping[str, Any]],
    candidate: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    def series(values: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], list[float]]:
        artifact_bytes = int(values[0]["artifact"]["artifact_size_bytes"])
        latencies = sorted(float(item["timing"]["latency_ms_per_100_tokens"]) for item in values)
        peaks = sorted(int(item["memory"]["peak_resident_bytes"]) for item in values)
        return (
            {
                "artifact_size_bytes": artifact_bytes,
                "median_latency_ms_per_100_tokens": float(statistics.median(latencies)),
                "median_peak_resident_memory_bytes": float(statistics.median(peaks)),
            },
            latencies,
        )

    ref, _ = series(reference)
    cand, cand_latencies = series(candidate)
    ref_latency = float(ref["median_latency_ms_per_100_tokens"])
    return {
        "operational_runs": len(reference),
        "reference": ref,
        "candidate": cand,
        "artifact_size_ratio": (
            int(cand["artifact_size_bytes"]) / int(ref["artifact_size_bytes"])
        ),
        "median_latency_ratio": (
            float(cand["median_latency_ms_per_100_tokens"]) / ref_latency
        ),
        "median_peak_resident_memory_ratio": (
            float(cand["median_peak_resident_memory_bytes"])
            / float(ref["median_peak_resident_memory_bytes"])
        ),
        "candidate_runs_below_reference_median_latency": sum(
            value < ref_latency for value in cand_latencies
        ),
    }


def _check(field: str, value: float | int, maximum: float | int) -> dict[str, Any]:
    return {
        "field": field,
        "value": value,
        "maximum": maximum,
        "passed": value <= maximum,
    }


def build_award(
    *,
    policy: Mapping[str, Any],
    label: str,
    qualification_report: Mapping[str, Any],
    reference_operational: Sequence[Mapping[str, Any]],
    candidate_operational: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rebuild and stamp one operational label decision."""

    validate_policy(policy)
    if label not in _LABELS:
        raise VariantAwardError(f"runtime variant label must be one of {list(_LABELS)!r}")
    try:
        qualification.validate_qualification_report(qualification_report)
    except Exception as exc:
        raise VariantAwardError(f"invalid artifact qualification report: {exc}") from exc
    if qualification_report["gate_sha256"] != policy["qualification_gate_sha256"]:
        raise VariantAwardError("artifact qualification report uses a different gate")
    if qualification_report["profile_id"] != "optimization":
        raise VariantAwardError("runtime labels require an optimization qualification")
    reference_binding = _qualification_binding(
        qualification_report["reference"], where="artifact qualification.reference"
    )
    candidate_binding = _qualification_binding(
        qualification_report["candidate"], where="artifact qualification.candidate"
    )

    rule = policy["labels"][label]
    runs = int(rule["operational_runs"])
    development_manifest = qualification_report["development_manifest_sha256"]
    profile = policy["measurement_profile_id"]
    reference = _validate_series(
        reference_operational,
        expected_runs=runs,
        expected_identity=reference_binding["model_identity"],
        expected_manifest=development_manifest,
        expected_profile=profile,
        where="reference operational evidence",
    )
    candidate = _validate_series(
        candidate_operational,
        expected_runs=runs,
        expected_identity=candidate_binding["model_identity"],
        expected_manifest=development_manifest,
        expected_profile=profile,
        where="candidate operational evidence",
    )
    reference_digests = {item["evidence_sha256"] for item in reference}
    candidate_digests = {item["evidence_sha256"] for item in candidate}
    if reference_binding["operational_evidence_sha256"] not in reference_digests:
        raise VariantAwardError("qualification-bound reference evidence is absent from the series")
    if candidate_binding["operational_evidence_sha256"] not in candidate_digests:
        raise VariantAwardError("qualification-bound candidate evidence is absent from the series")
    environments = [item["environment"] for item in (*reference, *candidate)]
    if any(environment != environments[0] for environment in environments[1:]):
        raise VariantAwardError("runtime label measurements do not share one exact environment")

    measurements = _measurements(reference, candidate)
    checks = [
        {
            "field": "a20_qualification",
            "value": bool(qualification_report["qualified"]),
            "maximum": True,
            "passed": bool(qualification_report["qualified"]),
        }
    ]
    thresholds = (
        ("artifact_size_ratio", "max_artifact_size_ratio"),
        ("median_latency_ratio", "max_median_latency_ratio"),
        (
            "median_peak_resident_memory_ratio",
            "max_median_peak_resident_memory_ratio",
        ),
    )
    for measurement, threshold in thresholds:
        maximum = rule[threshold]
        if maximum is not None:
            checks.append(_check(measurement, float(measurements[measurement]), float(maximum)))
    minimum = int(rule["minimum_runs_below_reference_median_latency"])
    if minimum:
        actual = int(measurements["candidate_runs_below_reference_median_latency"])
        checks.append(
            {
                "field": "candidate_runs_below_reference_median_latency",
                "value": actual,
                "minimum": minimum,
                "passed": actual >= minimum,
            }
        )
    failures = sorted(check["field"] for check in checks if not check["passed"])
    report = {
        "format": AWARD_FORMAT,
        "claim_status": AWARD_STATUS,
        "label": label,
        "policy_sha256": policy["policy_sha256"],
        "qualification_sha256": qualification_report["qualification_sha256"],
        "qualification_gate_sha256": qualification_report["gate_sha256"],
        "development_manifest_sha256": development_manifest,
        "measurement_profile_id": profile,
        "reference": _identity(reference),
        "candidate": _identity(candidate),
        "measurements": measurements,
        "checks": checks,
        "failures": failures,
        "awarded": not failures,
    }
    stamped = manifest_mod.stamp_document(report, "award_sha256")
    validate_award(stamped)
    return stamped


def validate_award(report: Mapping[str, Any]) -> None:
    """Validate a content-addressed award without its reconstruction inputs."""

    report = _mapping(report, where="runtime variant award")
    _exact_fields(
        report,
        {
            "format",
            "claim_status",
            "label",
            "policy_sha256",
            "qualification_sha256",
            "qualification_gate_sha256",
            "development_manifest_sha256",
            "measurement_profile_id",
            "reference",
            "candidate",
            "measurements",
            "checks",
            "failures",
            "awarded",
            "award_sha256",
        },
        where="runtime variant award",
    )
    if report["format"] != AWARD_FORMAT or report["claim_status"] != AWARD_STATUS:
        raise VariantAwardError("unknown runtime variant award format/claim status")
    if report["label"] not in _LABELS:
        raise VariantAwardError("runtime variant award has an invalid label")
    for field in (
        "policy_sha256",
        "qualification_sha256",
        "qualification_gate_sha256",
        "development_manifest_sha256",
        "award_sha256",
    ):
        _sha256(report[field], where=f"runtime variant award.{field}")
    _string(report["measurement_profile_id"], where="award measurement_profile_id")
    for side in ("reference", "candidate"):
        identity = _mapping(report[side], where=f"award.{side}")
        _exact_fields(
            identity,
            {
                "model_identity",
                "artifact_directory_sha256",
                "model_sha256",
                "bundle_manifest_sha256",
                "operational_evidence_sha256",
            },
            where=f"award.{side}",
        )
        _string(identity["model_identity"], where=f"award.{side}.model_identity")
        for field in (
            "artifact_directory_sha256",
            "model_sha256",
            "bundle_manifest_sha256",
        ):
            _sha256(identity[field], where=f"award.{side}.{field}")
        digests = identity["operational_evidence_sha256"]
        if not isinstance(digests, list) or not digests:
            raise VariantAwardError(f"award.{side} operational digests must be non-empty")
        for digest in digests:
            _sha256(digest, where=f"award.{side}.operational_evidence_sha256")
        if digests != sorted(set(digests)):
            raise VariantAwardError(f"award.{side} operational digests must be sorted and unique")
    measurements = _mapping(report["measurements"], where="award.measurements")
    _exact_fields(
        measurements,
        {
            "operational_runs",
            "reference",
            "candidate",
            "artifact_size_ratio",
            "median_latency_ratio",
            "median_peak_resident_memory_ratio",
            "candidate_runs_below_reference_median_latency",
        },
        where="award.measurements",
    )
    runs = _positive_int(
        measurements["operational_runs"], where="award.measurements.operational_runs"
    )
    summary_fields = {
        "artifact_size_bytes",
        "median_latency_ms_per_100_tokens",
        "median_peak_resident_memory_bytes",
    }
    for side in ("reference", "candidate"):
        summary = _mapping(measurements[side], where=f"award.measurements.{side}")
        _exact_fields(summary, summary_fields, where=f"award.measurements.{side}")
        _positive_int(
            summary["artifact_size_bytes"],
            where=f"award.measurements.{side}.artifact_size_bytes",
        )
        _ratio(
            summary["median_latency_ms_per_100_tokens"],
            where=f"award.measurements.{side}.median_latency_ms_per_100_tokens",
        )
        _ratio(
            summary["median_peak_resident_memory_bytes"],
            where=f"award.measurements.{side}.median_peak_resident_memory_bytes",
        )
        if len(report[side]["operational_evidence_sha256"]) != runs:
            raise VariantAwardError(
                f"award.{side} operational digest count differs from operational_runs"
            )
    for field in (
        "artifact_size_ratio",
        "median_latency_ratio",
        "median_peak_resident_memory_ratio",
    ):
        _ratio(measurements[field], where=f"award.measurements.{field}")
    expected_ratios = {
        "artifact_size_ratio": (
            measurements["candidate"]["artifact_size_bytes"]
            / measurements["reference"]["artifact_size_bytes"]
        ),
        "median_latency_ratio": (
            measurements["candidate"]["median_latency_ms_per_100_tokens"]
            / measurements["reference"]["median_latency_ms_per_100_tokens"]
        ),
        "median_peak_resident_memory_ratio": (
            measurements["candidate"]["median_peak_resident_memory_bytes"]
            / measurements["reference"]["median_peak_resident_memory_bytes"]
        ),
    }
    for field, expected_ratio in expected_ratios.items():
        if measurements[field] != expected_ratio:
            raise VariantAwardError(
                f"award measurement {field!r} differs from its public summaries"
            )
    below = _nonnegative_int(
        measurements["candidate_runs_below_reference_median_latency"],
        where="award.measurements.candidate_runs_below_reference_median_latency",
    )
    if below > runs:
        raise VariantAwardError(
            "candidate runs below the reference median exceed operational_runs"
        )

    checks = report["checks"]
    if not isinstance(checks, list) or not checks:
        raise VariantAwardError("runtime variant award checks must be non-empty")
    failed: list[str] = []
    fields: list[str] = []
    for index, raw in enumerate(checks):
        check = _mapping(raw, where=f"award.checks[{index}]")
        if set(check) not in (
            {"field", "value", "maximum", "passed"},
            {"field", "value", "minimum", "passed"},
        ):
            raise VariantAwardError(f"award.checks[{index}] has invalid fields")
        field = _string(check["field"], where=f"award.checks[{index}].field")
        fields.append(field)
        if not isinstance(check["passed"], bool):
            raise VariantAwardError(f"award.checks[{index}].passed must be boolean")
        if field == "a20_qualification":
            if not isinstance(check["value"], bool) or check.get("maximum") is not True:
                raise VariantAwardError("the artifact qualification check is malformed")
            expected_passed = check["value"] is True
        elif "maximum" in check:
            value = _ratio(check["value"], where=f"award.checks[{index}].value")
            maximum = _ratio(
                check["maximum"], where=f"award.checks[{index}].maximum"
            )
            if field not in measurements or measurements[field] != value:
                raise VariantAwardError(
                    f"award check {field!r} differs from the recorded measurement"
                )
            expected_passed = value <= maximum
        else:
            value = _nonnegative_int(
                check["value"], where=f"award.checks[{index}].value"
            )
            minimum = _nonnegative_int(
                check["minimum"], where=f"award.checks[{index}].minimum"
            )
            if field not in measurements or measurements[field] != value:
                raise VariantAwardError(
                    f"award check {field!r} differs from the recorded measurement"
                )
            expected_passed = value >= minimum
        if check["passed"] is not expected_passed:
            raise VariantAwardError(f"award check {field!r} decision is inconsistent")
        if not check["passed"]:
            failed.append(field)
    if len(fields) != len(set(fields)):
        raise VariantAwardError("runtime variant award check fields must be unique")
    failures = report["failures"]
    if not isinstance(failures, list) or failures != sorted(set(failures)):
        raise VariantAwardError("runtime variant award failures must be sorted and unique")
    if failures != sorted(failed):
        raise VariantAwardError("runtime variant award failures differ from failed checks")
    if not isinstance(report["awarded"], bool) or report["awarded"] != (not failures):
        raise VariantAwardError("runtime variant award decision differs from its failures")
    try:
        manifest_mod.verify_document(report, "award_sha256")
    except Exception as exc:
        raise VariantAwardError(f"runtime variant award digest mismatch: {exc}") from exc


def verify_award(
    report: Mapping[str, Any],
    **inputs: Any,
) -> None:
    """Independently rebuild one award from policy and operational evidence."""

    validate_award(report)
    rebuilt = build_award(**inputs)
    if rebuilt != report:
        raise VariantAwardError("runtime variant award does not reproduce from its evidence")


def load_award(path: str | Path) -> dict[str, Any]:
    """Load a bounded, duplicate-safe, digest-verified award."""

    award = _load_json(path, where="runtime variant award")
    validate_award(award)
    return award


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Award one evidence-backed neural runtime variant label.",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path(__file__).with_name("runtime-variant-policy-v1.json"),
    )
    parser.add_argument("--label", choices=_LABELS, required=True)
    parser.add_argument("--qualification", type=Path, required=True)
    parser.add_argument(
        "--reference-operational",
        type=Path,
        action="append",
        required=True,
        help="Repeat exactly as many times as the selected label policy requires.",
    )
    parser.add_argument(
        "--candidate-operational",
        type=Path,
        action="append",
        required=True,
        help="Repeat exactly as many times as the selected label policy requires.",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.output.exists():
            raise VariantAwardError(f"refusing to replace existing award: {args.output}")
        policy = load_policy(args.policy)
        decision = qualification.load_qualification_report(args.qualification)
        reference = [
            qualification.load_operational_evidence(path)
            for path in args.reference_operational
        ]
        candidate = [
            qualification.load_operational_evidence(path)
            for path in args.candidate_operational
        ]
        award = build_award(
            policy=policy,
            label=args.label,
            qualification_report=decision,
            reference_operational=reference,
            candidate_operational=candidate,
        )
        manifest_mod.write_document(award, args.output, digest_field="award_sha256")
    except (VariantAwardError, qualification.QualificationError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "label": award["label"],
                "awarded": award["awarded"],
                "award_sha256": award["award_sha256"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0 if award["awarded"] else 1


if __name__ == "__main__":  # pragma: no cover - exercised by subprocess tests
    raise SystemExit(main())
