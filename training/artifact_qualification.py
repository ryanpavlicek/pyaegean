"""Fail-closed qualification for exported and optimized Greek model artifacts.

The module is deliberately independent of model conversion and inference.  It
recomputes development reports from gold plus prediction artifacts, compares every
protected selection-policy metric and decoded output field, validates operational
measurements, and emits one content-addressed qualification decision.  Development
evidence is not a published benchmark claim.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:  # The training directory is also used directly as a script directory.
    from . import development_manifest as manifest_mod
    from . import development_report as report_mod
    from . import model_selection as selection_mod
except ImportError:  # pragma: no cover - exercised by ``python training/foo.py``
    import development_manifest as manifest_mod  # type: ignore[no-redef]
    import development_report as report_mod  # type: ignore[no-redef]
    import model_selection as selection_mod  # type: ignore[no-redef]

__all__ = [
    "CLAIM_STATUS",
    "EVIDENCE_FORMAT",
    "GATE_FORMAT",
    "QualificationError",
    "REPORT_FORMAT",
    "build_qualification_report",
    "load_gate",
    "load_operational_evidence",
    "load_qualification_report",
    "stamp_gate",
    "stamp_operational_evidence",
    "validate_gate",
    "validate_operational_evidence",
    "validate_qualification_report",
    "verify_qualification_report",
]

GATE_FORMAT = "pyaegean-artifact-qualification-gate/1"
EVIDENCE_FORMAT = "pyaegean-artifact-operational-evidence/1"
REPORT_FORMAT = "pyaegean-artifact-qualification-report/1"
CLAIM_STATUS = "development-only-not-published"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OUTPUT_FIELDS = ("upos", "xpos", "ufeats", "lemma", "head", "deprel")
_TOKEN_FIELDS = {
    "upos": "upos",
    "xpos": "xpos",
    "ufeats": "feats",
    "lemma": "lemma",
    "head": "head",
    "deprel": "deprel",
}
_MAX_GATE_BYTES = 1024 * 1024
_MAX_REPORT_BYTES = 8 * 1024 * 1024


class QualificationError(ValueError):
    """Raised when artifact qualification input or evidence is invalid."""


def _exact_fields(value: Mapping[str, Any], expected: set[str], *, where: str) -> None:
    actual = set(value)
    if actual != expected:
        raise QualificationError(
            f"{where} fields differ (missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)})"
        )


def _mapping(value: Any, *, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise QualificationError(f"{where} must be an object")
    return value


def _string(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise QualificationError(f"{where} must be a non-empty string")
    return value


def _sha256(value: Any, *, where: str) -> str:
    result = _string(value, where=where)
    if not _SHA256.fullmatch(result):
        raise QualificationError(f"{where} must be a lowercase SHA-256")
    return result


def _number(value: Any, *, where: str, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QualificationError(f"{where} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise QualificationError(f"{where} must be finite and at least {minimum}")
    return result


def _positive_integer(value: Any, *, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise QualificationError(f"{where} must be a positive integer")
    return value


def _boolean(value: Any, *, where: str) -> bool:
    if not isinstance(value, bool):
        raise QualificationError(f"{where} must be a boolean")
    return value


def _validate_fraction_map(value: Any, *, where: str) -> None:
    mapping = _mapping(value, where=where)
    if set(mapping) != set(_OUTPUT_FIELDS):
        raise QualificationError(f"{where} must contain exactly {list(_OUTPUT_FIELDS)!r}")
    for field in _OUTPUT_FIELDS:
        number = _number(mapping[field], where=f"{where}.{field}")
        if number > 1.0:
            raise QualificationError(f"{where}.{field} must not exceed 1")


def validate_gate(gate: Mapping[str, Any], *, verify_digest: bool = True) -> None:
    """Validate an artifact gate and its development/selection evidence bindings."""

    _exact_fields(
        gate,
        {
            "format",
            "gate_id",
            "claim_status",
            "development_manifest_sha256",
            "selection_gate_sha256",
            "measurement",
            "profiles",
            "gate_sha256",
        },
        where="gate",
    )
    if gate.get("format") != GATE_FORMAT:
        raise QualificationError("unknown artifact qualification gate format")
    _string(gate.get("gate_id"), where="gate.gate_id")
    if gate.get("claim_status") != CLAIM_STATUS:
        raise QualificationError("gate claim status must remain development-only-not-published")
    _sha256(gate.get("development_manifest_sha256"), where="gate.development_manifest_sha256")
    _sha256(gate.get("selection_gate_sha256"), where="gate.selection_gate_sha256")

    measurement = _mapping(gate.get("measurement"), where="gate.measurement")
    _exact_fields(
        measurement,
        {
            "profile_id",
            "execution_provider",
            "mode",
            "long_input",
            "warmup_items",
            "timed_scope",
            "memory_sample_interval_ms",
            "provider_probe_items",
        },
        where="gate.measurement",
    )
    _string(measurement.get("profile_id"), where="gate.measurement.profile_id")
    if measurement.get("execution_provider") != "CPUExecutionProvider":
        raise QualificationError("canonical qualification provider must be CPUExecutionProvider")
    if measurement.get("mode") != "sequential":
        raise QualificationError("canonical qualification mode must be sequential")
    if measurement.get("long_input") != "windowed":
        raise QualificationError("canonical qualification must use complete windowed input")
    if measurement.get("timed_scope") != "complete-development-manifest":
        raise QualificationError("qualification timing must cover the complete development manifest")
    _positive_integer(measurement.get("warmup_items"), where="gate.measurement.warmup_items")
    _positive_integer(
        measurement.get("memory_sample_interval_ms"),
        where="gate.measurement.memory_sample_interval_ms",
    )
    if measurement.get("provider_probe_items") != ["shortest", "median", "longest"]:
        raise QualificationError("provider probes must use shortest/median/longest items")

    profiles = _mapping(gate.get("profiles"), where="gate.profiles")
    if set(profiles) != {"export", "optimization"}:
        raise QualificationError("gate must define exactly export and optimization profiles")
    for profile_id, raw_profile in profiles.items():
        profile = _mapping(raw_profile, where=f"gate.profiles.{profile_id}")
        _exact_fields(
            profile,
            {
                "transform",
                "metric_regression_scale",
                "max_prediction_disagreement_fraction",
                "required_providers",
                "optional_providers",
                "max_artifact_size_bytes",
                "max_latency_ms_per_100_tokens",
                "max_peak_resident_memory_bytes",
                "require_smaller_than_reference",
            },
            where=f"gate.profiles.{profile_id}",
        )
        transform = _string(profile.get("transform"), where=f"gate.profiles.{profile_id}.transform")
        expected_transform = "framework-export" if profile_id == "export" else "artifact-optimization"
        if transform != expected_transform:
            raise QualificationError(
                f"gate.profiles.{profile_id}.transform must be {expected_transform!r}"
            )
        scale = _number(
            profile.get("metric_regression_scale"),
            where=f"gate.profiles.{profile_id}.metric_regression_scale",
        )
        if profile_id == "export" and scale != 0.0:
            raise QualificationError("export metric regression scale must be zero")
        if profile_id == "optimization" and scale != 1.0:
            raise QualificationError(
                "optimization must retain the full selection-policy regression ceilings"
            )
        _validate_fraction_map(
            profile.get("max_prediction_disagreement_fraction"),
            where=f"gate.profiles.{profile_id}.max_prediction_disagreement_fraction",
        )
        if profile_id == "export" and any(
            float(value) != 0.0
            for value in profile["max_prediction_disagreement_fraction"].values()
        ):
            raise QualificationError("export output parity must be exact")
        for provider_field in ("required_providers", "optional_providers"):
            providers = profile.get(provider_field)
            if (
                not isinstance(providers, list)
                or any(not isinstance(provider, str) or not provider for provider in providers)
                or providers != sorted(set(providers))
            ):
                raise QualificationError(
                    f"gate.profiles.{profile_id}.{provider_field} must be sorted unique strings"
                )
        if "CPUExecutionProvider" not in profile["required_providers"]:
            raise QualificationError("CPUExecutionProvider must be required")
        if set(profile["required_providers"]) & set(profile["optional_providers"]):
            raise QualificationError("required and optional providers must be disjoint")
        _positive_integer(
            profile.get("max_artifact_size_bytes"),
            where=f"gate.profiles.{profile_id}.max_artifact_size_bytes",
        )
        _number(
            profile.get("max_latency_ms_per_100_tokens"),
            where=f"gate.profiles.{profile_id}.max_latency_ms_per_100_tokens",
            minimum=1e-12,
        )
        _positive_integer(
            profile.get("max_peak_resident_memory_bytes"),
            where=f"gate.profiles.{profile_id}.max_peak_resident_memory_bytes",
        )
        smaller = _boolean(
            profile.get("require_smaller_than_reference"),
            where=f"gate.profiles.{profile_id}.require_smaller_than_reference",
        )
        if smaller != (profile_id == "optimization"):
            raise QualificationError(
                "only the optimization profile may require a smaller artifact"
            )
    _sha256(gate.get("gate_sha256"), where="gate.gate_sha256")
    if verify_digest:
        try:
            manifest_mod.verify_document(gate, "gate_sha256")
        except Exception as exc:
            raise QualificationError(f"qualification gate digest mismatch: {exc}") from exc


def stamp_gate(gate: Mapping[str, Any]) -> dict[str, Any]:
    """Return a canonical digest-stamped gate."""

    stamped = dict(manifest_mod.stamp_document(gate, "gate_sha256"))
    validate_gate(stamped)
    return stamped


def _duplicate_guard(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise QualificationError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load_json(path: str | Path, *, maximum_bytes: int, where: str) -> dict[str, Any]:
    target = Path(path)
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise QualificationError(f"cannot read {where} {target}: {exc}") from exc
    if len(raw) > maximum_bytes:
        raise QualificationError(f"{where} exceeds the {maximum_bytes}-byte input limit")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_duplicate_guard)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise QualificationError(f"invalid {where} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise QualificationError(f"{where} must be a JSON object")
    return value


def load_gate(path: str | Path) -> dict[str, Any]:
    """Load and validate a gate without accepting duplicate keys or oversized input."""

    gate = _load_json(path, maximum_bytes=_MAX_GATE_BYTES, where="qualification gate")
    validate_gate(gate)
    return gate


def validate_operational_evidence(evidence: Mapping[str, Any], *, verify_digest: bool = True) -> None:
    """Validate one runtime-generated artifact/latency/memory/provider record."""

    _exact_fields(
        evidence,
        {
            "format",
            "claim_status",
            "profile_id",
            "development_manifest_sha256",
            "artifact",
            "timing",
            "memory",
            "provider_matrix",
            "environment",
            "evidence_sha256",
        },
        where="operational evidence",
    )
    if evidence.get("format") != EVIDENCE_FORMAT:
        raise QualificationError("unknown operational evidence format")
    if evidence.get("claim_status") != CLAIM_STATUS:
        raise QualificationError("operational evidence must remain development-only")
    _string(evidence.get("profile_id"), where="operational evidence.profile_id")
    _sha256(
        evidence.get("development_manifest_sha256"),
        where="operational evidence.development_manifest_sha256",
    )
    artifact = _mapping(evidence.get("artifact"), where="operational evidence.artifact")
    _exact_fields(
        artifact,
        {
            "identity",
            "directory_sha256",
            "model_sha256",
            "artifact_size_bytes",
            "model_size_bytes",
            "files",
        },
        where="operational evidence.artifact",
    )
    _string(artifact.get("identity"), where="operational evidence.artifact.identity")
    _sha256(artifact.get("directory_sha256"), where="operational evidence.artifact.directory_sha256")
    _sha256(artifact.get("model_sha256"), where="operational evidence.artifact.model_sha256")
    artifact_bytes = _positive_integer(
        artifact.get("artifact_size_bytes"),
        where="operational evidence.artifact.artifact_size_bytes",
    )
    model_bytes = _positive_integer(
        artifact.get("model_size_bytes"),
        where="operational evidence.artifact.model_size_bytes",
    )
    if model_bytes > artifact_bytes:
        raise QualificationError("model bytes cannot exceed total artifact bytes")
    files = artifact.get("files")
    if not isinstance(files, list) or not files:
        raise QualificationError("operational evidence.artifact.files must be non-empty")
    seen: set[str] = set()
    total = 0
    for index, raw_file in enumerate(files):
        entry = _mapping(raw_file, where=f"operational evidence.artifact.files[{index}]")
        _exact_fields(entry, {"path", "bytes", "sha256"}, where=f"artifact.files[{index}]")
        name = _string(entry.get("path"), where=f"artifact.files[{index}].path")
        if Path(name).name != name or name in seen:
            raise QualificationError("artifact file paths must be unique flat names")
        seen.add(name)
        total += _positive_integer(entry.get("bytes"), where=f"artifact.files[{index}].bytes")
        _sha256(entry.get("sha256"), where=f"artifact.files[{index}].sha256")
    if total != artifact_bytes or not {"model.onnx", "manifest.json"}.issubset(seen):
        raise QualificationError("artifact file accounting differs from artifact_size_bytes")

    timing = _mapping(evidence.get("timing"), where="operational evidence.timing")
    _exact_fields(
        timing,
        {
            "mode",
            "long_input",
            "warmup_items",
            "timed_items",
            "timed_tokens",
            "elapsed_ns",
            "latency_ms_per_100_tokens",
        },
        where="operational evidence.timing",
    )
    if timing.get("mode") != "sequential" or timing.get("long_input") != "windowed":
        raise QualificationError("operational timing must be sequential and windowed")
    for field in ("warmup_items", "timed_items", "timed_tokens", "elapsed_ns"):
        _positive_integer(timing.get(field), where=f"operational evidence.timing.{field}")
    latency = _number(
        timing.get("latency_ms_per_100_tokens"),
        where="operational evidence.timing.latency_ms_per_100_tokens",
        minimum=1e-12,
    )
    derived_latency = int(timing["elapsed_ns"]) / 1_000_000 * 100 / int(timing["timed_tokens"])
    if not math.isclose(latency, derived_latency, rel_tol=1e-12, abs_tol=1e-12):
        raise QualificationError("latency normalization differs from elapsed time/token count")

    memory = _mapping(evidence.get("memory"), where="operational evidence.memory")
    _exact_fields(
        memory,
        {
            "method",
            "sample_interval_ms",
            "baseline_resident_bytes",
            "peak_resident_bytes",
            "incremental_peak_bytes",
        },
        where="operational evidence.memory",
    )
    _string(memory.get("method"), where="operational evidence.memory.method")
    _positive_integer(memory.get("sample_interval_ms"), where="operational evidence.memory.sample_interval_ms")
    baseline = _positive_integer(
        memory.get("baseline_resident_bytes"),
        where="operational evidence.memory.baseline_resident_bytes",
    )
    peak = _positive_integer(
        memory.get("peak_resident_bytes"),
        where="operational evidence.memory.peak_resident_bytes",
    )
    incremental = _number(
        memory.get("incremental_peak_bytes"),
        where="operational evidence.memory.incremental_peak_bytes",
    )
    if peak < baseline or int(incremental) != peak - baseline:
        raise QualificationError("resident-memory accounting is inconsistent")

    matrix = evidence.get("provider_matrix")
    if not isinstance(matrix, list) or not matrix:
        raise QualificationError("operational evidence.provider_matrix must be non-empty")
    providers: list[str] = []
    for index, raw_provider in enumerate(matrix):
        entry = _mapping(raw_provider, where=f"provider_matrix[{index}]")
        _exact_fields(
            entry,
            {
                "provider",
                "required",
                "available",
                "status",
                "session_providers",
                "prediction_sha256",
                "cpu_disagreement_fraction",
                "error",
            },
            where=f"provider_matrix[{index}]",
        )
        provider = _string(entry.get("provider"), where=f"provider_matrix[{index}].provider")
        providers.append(provider)
        required = _boolean(entry.get("required"), where=f"provider_matrix[{index}].required")
        available = _boolean(entry.get("available"), where=f"provider_matrix[{index}].available")
        status = entry.get("status")
        if status not in {"pass", "unavailable", "fail"}:
            raise QualificationError(f"provider_matrix[{index}].status is invalid")
        sessions = entry.get("session_providers")
        if not isinstance(sessions, list) or any(not isinstance(value, str) or not value for value in sessions):
            raise QualificationError(f"provider_matrix[{index}].session_providers is malformed")
        if status == "pass":
            if not available or provider not in sessions:
                raise QualificationError(f"provider_matrix[{index}] pass does not use its provider")
            _sha256(entry.get("prediction_sha256"), where=f"provider_matrix[{index}].prediction_sha256")
            _validate_fraction_map(
                entry.get("cpu_disagreement_fraction"),
                where=f"provider_matrix[{index}].cpu_disagreement_fraction",
            )
            if entry.get("error") is not None:
                raise QualificationError(f"provider_matrix[{index}] pass cannot contain an error")
        elif status == "unavailable":
            if available or required or entry.get("prediction_sha256") is not None:
                raise QualificationError(f"provider_matrix[{index}] unavailable state is inconsistent")
            if sessions or entry.get("cpu_disagreement_fraction") is not None or entry.get("error") is not None:
                raise QualificationError(f"provider_matrix[{index}] unavailable state has extra evidence")
        else:
            if (not available and not required) or not isinstance(entry.get("error"), str) or not entry["error"]:
                raise QualificationError(
                    f"provider_matrix[{index}] failure must record an error; "
                    "an unavailable provider may fail only when required"
                )
            if entry.get("prediction_sha256") is not None or entry.get("cpu_disagreement_fraction") is not None:
                raise QualificationError(f"provider_matrix[{index}] failure cannot contain prediction evidence")
    if providers != sorted(set(providers)):
        raise QualificationError("provider matrix must be sorted and unique")

    environment = _mapping(evidence.get("environment"), where="operational evidence.environment")
    _exact_fields(
        environment,
        {"python", "platform", "machine", "processor", "onnxruntime", "numpy", "tokenizers"},
        where="operational evidence.environment",
    )
    for field in environment:
        _string(environment[field], where=f"operational evidence.environment.{field}")
    _sha256(evidence.get("evidence_sha256"), where="operational evidence.evidence_sha256")
    if verify_digest:
        try:
            manifest_mod.verify_document(evidence, "evidence_sha256")
        except Exception as exc:
            raise QualificationError(f"operational evidence digest mismatch: {exc}") from exc


def stamp_operational_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Return canonical digest-stamped operational evidence."""

    stamped = dict(manifest_mod.stamp_document(evidence, "evidence_sha256"))
    validate_operational_evidence(stamped)
    return stamped


def load_operational_evidence(path: str | Path) -> dict[str, Any]:
    """Load bounded, duplicate-safe, digest-verified operational evidence."""

    evidence = _load_json(path, maximum_bytes=_MAX_REPORT_BYTES, where="operational evidence")
    validate_operational_evidence(evidence)
    return evidence


def _prediction_sha256(predictions: Mapping[str, Any]) -> str:
    return hashlib.sha256(manifest_mod.canonical_json(predictions).encode("utf-8")).hexdigest()


def _rebuild_report(
    report: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    gold: Mapping[str, Any],
    predictions: Mapping[str, Any],
    where: str,
) -> None:
    try:
        report_mod.verify_report(report, manifest)
        if report["run"]["prediction_sha256"] != _prediction_sha256(predictions):
            raise QualificationError(f"{where} prediction digest differs from its artifact")
        protocol = report["protocol"]
        rebuilt = report_mod.build_report(
            manifest=manifest,
            gold_sentences=gold,
            predictions=predictions,
            run=report["run"],
            n_resamples=int(protocol["n_resamples"]),
            level=float(protocol["level"]),
            seed=int(protocol["seed"]),
        )
    except QualificationError:
        raise
    except Exception as exc:
        raise QualificationError(f"could not verify {where}: {exc}") from exc
    if rebuilt != report:
        raise QualificationError(f"{where} does not reproduce from gold and predictions")


def _oov_token_value(report: Mapping[str, Any], metric: str) -> float | None:
    """Per-token accuracy over out-of-vocabulary tokens from the error anatomy.

    The ``oov`` item slice is whole sentences that contain any OOV token, so a
    slice-summed metric there dilutes OOV-token accuracy with the in-vocabulary
    tokens of those sentences. The overall error anatomy counts the true
    per-OOV-token hits, so this reads that band directly.
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
        value = report["metrics"][metric]["value"]
        return None if value is None else float(value)
    if slice_id == "oov-token":
        return _oov_token_value(report, metric)
    numerator = 0
    denominator = 0
    for raw_item in report["items"]:
        item = _mapping(raw_item, where="report item")
        if slice_id not in item["slice_ids"]:
            continue
        entry = item["metrics"][metric]
        if entry["value"] is None:
            continue
        numerator += int(entry["numerator"])
        denominator += int(entry["denominator"])
    return numerator / denominator if denominator else None


def _prediction_parity(
    reference: Mapping[str, Any], candidate: Mapping[str, Any], limits: Mapping[str, Any]
) -> list[dict[str, Any]]:
    if list(reference) != list(candidate):
        raise QualificationError("reference and candidate prediction item IDs/order differ")
    counts = {field: [0, 0] for field in _OUTPUT_FIELDS}
    for item_id in reference:
        reference_tokens = reference[item_id]
        candidate_tokens = candidate[item_id]
        if not isinstance(reference_tokens, list) or not isinstance(candidate_tokens, list):
            raise QualificationError(f"predictions for {item_id!r} must be token lists")
        if len(reference_tokens) != len(candidate_tokens):
            raise QualificationError(f"prediction token cardinality differs for {item_id!r}")
        for index, (left, right) in enumerate(zip(reference_tokens, candidate_tokens, strict=True)):
            if not isinstance(left, Mapping) or not isinstance(right, Mapping):
                raise QualificationError(f"prediction token {item_id!r}/{index} is not an object")
            if left.get("form") != right.get("form") or left.get("id") != right.get("id"):
                raise QualificationError(f"prediction token alignment differs for {item_id!r}/{index}")
            for field, token_field in _TOKEN_FIELDS.items():
                counts[field][1] += 1
                counts[field][0] += int(left.get(token_field) != right.get(token_field))
    result: list[dict[str, Any]] = []
    for field in _OUTPUT_FIELDS:
        disagreements, compared = counts[field]
        fraction = disagreements / compared if compared else 0.0
        maximum = float(limits[field])
        result.append(
            {
                "field": field,
                "compared": compared,
                "disagreements": disagreements,
                "fraction": fraction,
                "maximum_fraction": maximum,
                "passed": fraction <= maximum,
            }
        )
    return result


def _validate_bindings(
    gate: Mapping[str, Any], selection_gate: Mapping[str, Any], manifest: Mapping[str, Any]
) -> None:
    try:
        validate_gate(gate)
        selection_mod.validate_gate(selection_gate)
        manifest_mod.verify_manifest(manifest)
        manifest_mod.verify_document(manifest, "manifest_sha256")
    except Exception as exc:
        raise QualificationError(f"invalid gate/manifest binding input: {exc}") from exc
    if gate["selection_gate_sha256"] != selection_gate["gate_sha256"]:
        raise QualificationError("qualification gate is bound to a different selection gate")
    if gate["development_manifest_sha256"] != manifest["manifest_sha256"]:
        raise QualificationError("qualification gate is bound to a different development manifest")
    if selection_gate["development_manifest_sha256"] != manifest["manifest_sha256"]:
        raise QualificationError("selection gate is bound to a different development manifest")


def build_qualification_report(
    *,
    gate: Mapping[str, Any],
    selection_gate: Mapping[str, Any],
    manifest: Mapping[str, Any],
    profile_id: str,
    gold: Mapping[str, Any],
    reference_report: Mapping[str, Any],
    reference_predictions: Mapping[str, Any],
    candidate_report: Mapping[str, Any],
    candidate_predictions: Mapping[str, Any],
    candidate_operational: Mapping[str, Any],
    reference_operational: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Recompute all evidence and return a stamped qualification decision."""

    _validate_bindings(gate, selection_gate, manifest)
    profiles = _mapping(gate["profiles"], where="gate.profiles")
    if profile_id not in profiles:
        raise QualificationError(f"unknown qualification profile {profile_id!r}")
    profile = _mapping(profiles[profile_id], where=f"gate.profiles.{profile_id}")
    _rebuild_report(
        reference_report,
        manifest=manifest,
        gold=gold,
        predictions=reference_predictions,
        where="reference development report",
    )
    _rebuild_report(
        candidate_report,
        manifest=manifest,
        gold=gold,
        predictions=candidate_predictions,
        where="candidate development report",
    )
    decoder = selection_gate["decoder"]
    for where, report in (("reference", reference_report), ("candidate", candidate_report)):
        if report["run"]["decoder"] != decoder:
            raise QualificationError(
                f"{where} report decoder differs from the selection-gate decoder"
            )

    validate_operational_evidence(candidate_operational)
    if candidate_operational["profile_id"] != gate["measurement"]["profile_id"]:
        raise QualificationError("candidate operational measurement profile differs from the gate")
    if candidate_operational["development_manifest_sha256"] != manifest["manifest_sha256"]:
        raise QualificationError("candidate operational evidence uses a different manifest")
    candidate_model = candidate_report["run"]["model"]
    if (
        candidate_operational["artifact"]["identity"] != candidate_model["identity"]
        or candidate_operational["artifact"]["directory_sha256"]
        != candidate_model["asset_sha256"]
    ):
        raise QualificationError(
            "candidate operational artifact differs from the candidate report identity/digest"
        )
    for field in ("preprocessing", "output_profile"):
        if candidate_report["run"][field] != reference_report["run"][field]:
            raise QualificationError(
                f"candidate {field} contract differs from the reference report"
            )
    if reference_operational is not None:
        validate_operational_evidence(reference_operational)
        if reference_operational["development_manifest_sha256"] != manifest["manifest_sha256"]:
            raise QualificationError("reference operational evidence uses a different manifest")
        if reference_operational["profile_id"] != gate["measurement"]["profile_id"]:
            raise QualificationError("reference operational measurement profile differs from the gate")
        reference_model = reference_report["run"]["model"]
        if (
            reference_operational["artifact"]["identity"] != reference_model["identity"]
            or reference_operational["artifact"]["directory_sha256"]
            != reference_model["asset_sha256"]
        ):
            raise QualificationError(
                "reference operational artifact differs from the reference report identity/digest"
            )

    failures: list[str] = []
    metric_checks: list[dict[str, Any]] = []
    scale = float(profile["metric_regression_scale"])
    for raw in selection_gate["protected_metrics"]:
        entry = _mapping(raw, where="selection protected metric")
        metric = str(entry["metric"])
        slice_id = str(entry["slice"])
        reference_value = _metric_value(reference_report, metric, slice_id)
        candidate_value = _metric_value(candidate_report, metric, slice_id)
        maximum = float(entry["max_regression"]) * scale
        delta = (
            None
            if reference_value is None or candidate_value is None
            else candidate_value - reference_value
        )
        passed = delta is not None and delta >= -maximum
        if not passed:
            failures.append(f"protected regression {metric}@{slice_id}")
        metric_checks.append(
            {
                "metric": metric,
                "slice": slice_id,
                "reference": reference_value,
                "candidate": candidate_value,
                "delta": delta,
                "max_regression": maximum,
                "passed": passed,
            }
        )

    parity = _prediction_parity(
        reference_predictions,
        candidate_predictions,
        profile["max_prediction_disagreement_fraction"],
    )
    failures.extend(
        f"prediction disagreement {entry['field']}" for entry in parity if not entry["passed"]
    )

    artifact_bytes = int(candidate_operational["artifact"]["artifact_size_bytes"])
    latency = float(candidate_operational["timing"]["latency_ms_per_100_tokens"])
    peak_memory = int(candidate_operational["memory"]["peak_resident_bytes"])
    operational_checks = [
        {
            "field": "artifact_size_bytes",
            "value": artifact_bytes,
            "maximum": int(profile["max_artifact_size_bytes"]),
            "passed": artifact_bytes <= int(profile["max_artifact_size_bytes"]),
        },
        {
            "field": "latency_ms_per_100_tokens",
            "value": latency,
            "maximum": float(profile["max_latency_ms_per_100_tokens"]),
            "passed": latency <= float(profile["max_latency_ms_per_100_tokens"]),
        },
        {
            "field": "peak_resident_memory_bytes",
            "value": peak_memory,
            "maximum": int(profile["max_peak_resident_memory_bytes"]),
            "passed": peak_memory <= int(profile["max_peak_resident_memory_bytes"]),
        },
    ]
    if profile["require_smaller_than_reference"]:
        if reference_operational is None:
            raise QualificationError("optimization qualification requires reference operational evidence")
        reference_bytes = int(reference_operational["artifact"]["artifact_size_bytes"])
        operational_checks.append(
            {
                "field": "smaller_than_reference",
                "value": artifact_bytes,
                "maximum": reference_bytes - 1,
                "passed": artifact_bytes < reference_bytes,
            }
        )
    for check in operational_checks:
        if not check["passed"]:
            failures.append(f"operational limit {check['field']}")

    required = set(profile["required_providers"])
    provider_checks: list[dict[str, Any]] = []
    by_provider = {
        str(entry["provider"]): entry for entry in candidate_operational["provider_matrix"]
    }
    for provider in sorted(required | set(profile["optional_providers"])):
        entry = by_provider.get(provider)
        if entry is None:
            passed = False
            status = "missing"
        else:
            status = str(entry["status"])
            passed = (
                status == "pass"
                if provider in required
                else status in {"pass", "unavailable"}
            )
            if status == "pass":
                for field, fraction in entry["cpu_disagreement_fraction"].items():
                    if float(fraction) > float(profile["max_prediction_disagreement_fraction"][field]):
                        passed = False
        if not passed:
            failures.append(f"provider compatibility {provider}")
        provider_checks.append(
            {
                "provider": provider,
                "required": provider in required,
                "status": status,
                "passed": passed,
            }
        )

    report: dict[str, Any] = {
        "format": REPORT_FORMAT,
        "claim_status": CLAIM_STATUS,
        "gate_sha256": gate["gate_sha256"],
        "selection_gate_sha256": selection_gate["gate_sha256"],
        "development_manifest_sha256": manifest["manifest_sha256"],
        "profile_id": profile_id,
        "reference": {
            "model_identity": reference_report["run"]["model"]["identity"],
            "report_sha256": reference_report["report_sha256"],
            "prediction_sha256": _prediction_sha256(reference_predictions),
            "operational_evidence_sha256": (
                None if reference_operational is None else reference_operational["evidence_sha256"]
            ),
        },
        "candidate": {
            "model_identity": candidate_report["run"]["model"]["identity"],
            "report_sha256": candidate_report["report_sha256"],
            "prediction_sha256": _prediction_sha256(candidate_predictions),
            "operational_evidence_sha256": candidate_operational["evidence_sha256"],
        },
        "metric_checks": metric_checks,
        "prediction_parity": parity,
        "operational_checks": operational_checks,
        "provider_checks": provider_checks,
        "failures": sorted(set(failures)),
        "qualified": not failures,
    }
    stamped = dict(manifest_mod.stamp_document(report, "qualification_sha256"))
    _validate_report_shape(stamped)
    return stamped


def _validate_report_shape(report: Mapping[str, Any]) -> None:
    _exact_fields(
        report,
        {
            "format",
            "claim_status",
            "gate_sha256",
            "selection_gate_sha256",
            "development_manifest_sha256",
            "profile_id",
            "reference",
            "candidate",
            "metric_checks",
            "prediction_parity",
            "operational_checks",
            "provider_checks",
            "failures",
            "qualified",
            "qualification_sha256",
        },
        where="qualification report",
    )
    if report.get("format") != REPORT_FORMAT or report.get("claim_status") != CLAIM_STATUS:
        raise QualificationError("invalid qualification report format/claim status")
    for field in (
        "gate_sha256",
        "selection_gate_sha256",
        "development_manifest_sha256",
        "qualification_sha256",
    ):
        _sha256(report.get(field), where=f"qualification report.{field}")
    if report.get("profile_id") not in {"export", "optimization"}:
        raise QualificationError("invalid qualification report profile")
    if not isinstance(report.get("failures"), list) or any(
        not isinstance(value, str) or not value for value in report["failures"]
    ):
        raise QualificationError("qualification report failures are malformed")
    if report["failures"] != sorted(set(report["failures"])):
        raise QualificationError("qualification report failures must be sorted and unique")
    if report.get("qualified") != (not report["failures"]):
        raise QualificationError("qualification report decision differs from its failures")
    try:
        manifest_mod.verify_document(report, "qualification_sha256")
    except Exception as exc:
        raise QualificationError(f"qualification report digest mismatch: {exc}") from exc


def verify_qualification_report(
    report: Mapping[str, Any],
    **inputs: Any,
) -> None:
    """Independently rebuild a saved decision from all bound evidence."""

    _validate_report_shape(report)
    expected = build_qualification_report(**inputs)
    if expected != report:
        raise QualificationError("qualification report does not reproduce from its bound evidence")


def validate_qualification_report(report: Mapping[str, Any]) -> None:
    """Validate a saved decision envelope without rebuilding private development data.

    Full verification still requires :func:`verify_qualification_report` and all
    bound development inputs. Runtime-label selection uses this narrower seam only after matching the
    decision to independently digest-verified operational records.
    """

    _validate_report_shape(report)


def load_qualification_report(path: str | Path) -> dict[str, Any]:
    """Load the bounded-size outer report; verification still requires its evidence."""

    report = _load_json(path, maximum_bytes=_MAX_REPORT_BYTES, where="qualification report")
    _validate_report_shape(report)
    return report
