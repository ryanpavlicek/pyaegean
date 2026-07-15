"""Runtime-label award policy and reconstruction tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from training import artifact_qualification as qualification
from training import development_manifest as manifest_mod
from training import runtime_variant_award as award_mod
from aegean.greek.model_variants import NeuralRuntimeVariant, _validate_variant_award

ROOT = Path(__file__).resolve().parents[2]
TRAINING = ROOT / "training"
POLICY_PATH = TRAINING / "runtime-variant-policy-v1.json"
ENVIRONMENT = {
    "python": "3.14.3",
    "platform": "test-platform",
    "machine": "x86_64",
    "processor": "test-cpu",
    "onnxruntime": "1.24.2",
    "numpy": "2.4.1",
    "tokenizers": "0.22.2",
}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _operational(
    identity: str,
    *,
    artifact_bytes: int,
    latency: int,
    peak: int,
    run: int,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    model_bytes = artifact_bytes * 3 // 4
    manifest_bytes = artifact_bytes - model_bytes
    model_sha = _digest(f"{identity}-model")
    record = {
        "format": qualification.EVIDENCE_FORMAT,
        "claim_status": qualification.CLAIM_STATUS,
        "profile_id": "pyaegean-cpu-sequential-complete-dev-v1",
        "development_manifest_sha256": "b" * 64,
        "artifact": {
            "identity": identity,
            "directory_sha256": _digest(f"{identity}-directory"),
            "model_sha256": model_sha,
            "artifact_size_bytes": artifact_bytes,
            "model_size_bytes": model_bytes,
            "files": [
                {"path": "manifest.json", "bytes": manifest_bytes, "sha256": _digest(f"{identity}-manifest")},
                {"path": "model.onnx", "bytes": model_bytes, "sha256": model_sha},
            ],
        },
        "timing": {
            "mode": "sequential",
            "long_input": "windowed",
            "warmup_items": 3,
            "timed_items": 10,
            "timed_tokens": 100,
            "elapsed_ns": latency * 1_000_000,
            "latency_ms_per_100_tokens": float(latency),
        },
        "memory": {
            "method": "test",
            "sample_interval_ms": 10,
            "baseline_resident_bytes": 1000,
            "peak_resident_bytes": peak,
            "incremental_peak_bytes": peak - 1000,
        },
        "provider_matrix": [
            {
                "provider": "CPUExecutionProvider",
                "required": True,
                "available": True,
                "status": "pass",
                "session_providers": ["CPUExecutionProvider"],
                "prediction_sha256": _digest(f"{identity}-prediction-{run}"),
                "cpu_disagreement_fraction": {
                    "upos": 0.0,
                    "xpos": 0.0,
                    "ufeats": 0.0,
                    "lemma": 0.0,
                    "head": 0.0,
                    "deprel": 0.0,
                },
                "error": None,
            }
        ],
        "environment": dict(environment or ENVIRONMENT),
    }
    return qualification.stamp_operational_evidence(record)


def _series(
    identity: str,
    *,
    artifact_bytes: int,
    latencies: list[int],
    peaks: list[int],
) -> list[dict[str, Any]]:
    return [
        _operational(
            identity,
            artifact_bytes=artifact_bytes,
            latency=latency,
            peak=peak,
            run=index,
        )
        for index, (latency, peak) in enumerate(zip(latencies, peaks, strict=True))
    ]


def _qualification(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    *,
    qualified: bool = True,
) -> dict[str, Any]:
    failures = [] if qualified else ["protected regression upos@aggregate"]
    report = {
        "format": qualification.REPORT_FORMAT,
        "claim_status": qualification.CLAIM_STATUS,
        "gate_sha256": "d1d451aa87ce5f9128c325ca60d7a06b4a7dc4b9f28f46701c77c097ab3094e3",
        "selection_gate_sha256": "a" * 64,
        "development_manifest_sha256": "b" * 64,
        "profile_id": "optimization",
        "reference": {
            "model_identity": reference["artifact"]["identity"],
            "report_sha256": "c" * 64,
            "prediction_sha256": "d" * 64,
            "operational_evidence_sha256": reference["evidence_sha256"],
        },
        "candidate": {
            "model_identity": candidate["artifact"]["identity"],
            "report_sha256": "e" * 64,
            "prediction_sha256": "f" * 64,
            "operational_evidence_sha256": candidate["evidence_sha256"],
        },
        "metric_checks": [],
        "prediction_parity": [],
        "operational_checks": [],
        "provider_checks": [],
        "failures": failures,
        "qualified": qualified,
    }
    return manifest_mod.stamp_document(report, "qualification_sha256")


def _inputs(
    label: str,
    *,
    reference_size: int = 100,
    candidate_size: int = 90,
    reference_latencies: list[int] | None = None,
    candidate_latencies: list[int] | None = None,
    reference_peaks: list[int] | None = None,
    candidate_peaks: list[int] | None = None,
    qualified: bool = True,
) -> dict[str, Any]:
    runs = 1 if label == "compact" else 5
    reference_latencies = reference_latencies or [100] * runs
    candidate_latencies = candidate_latencies or [90] * runs
    reference_peaks = reference_peaks or [2000] * runs
    candidate_peaks = candidate_peaks or [2000] * runs
    reference = _series(
        "reference-model",
        artifact_bytes=reference_size,
        latencies=reference_latencies,
        peaks=reference_peaks,
    )
    candidate = _series(
        "candidate-model",
        artifact_bytes=candidate_size,
        latencies=candidate_latencies,
        peaks=candidate_peaks,
    )
    return {
        "policy": award_mod.load_policy(POLICY_PATH),
        "label": label,
        "qualification_report": _qualification(
            reference[0], candidate[0], qualified=qualified
        ),
        "reference_operational": reference,
        "candidate_operational": candidate,
    }


def test_policy_and_contract_schemas_are_content_addressed() -> None:
    policy = award_mod.load_policy(POLICY_PATH)
    assert policy["labels"]["fast"]["operational_runs"] == 5
    assert policy["labels"]["compact"]["max_artifact_size_ratio"] == 0.9
    assert policy["labels"]["balanced"]["max_median_latency_ratio"] == 1.05
    for name in ("runtime-variant-policy.schema.json", "runtime-variant-award.schema.json"):
        assert json.loads((TRAINING / "contracts" / name).read_text(encoding="utf-8"))["type"] == "object"


@pytest.mark.parametrize(
    ("candidate_size", "awarded"),
    [(90, True), (91, False)],
)
def test_compact_label_uses_the_exact_size_boundary(
    candidate_size: int, awarded: bool
) -> None:
    inputs = _inputs("compact", candidate_size=candidate_size)
    report = award_mod.build_award(**inputs)
    assert report["awarded"] is awarded
    assert report["measurements"]["artifact_size_ratio"] == candidate_size / 100
    award_mod.verify_award(report, **inputs)


def test_fast_label_requires_median_gain_and_four_runs_below_reference_median() -> None:
    passing = _inputs(
        "fast",
        candidate_latencies=[90, 90, 90, 90, 100],
    )
    report = award_mod.build_award(**passing)
    assert report["awarded"] is True
    assert report["measurements"]["median_latency_ratio"] == 0.9
    assert report["measurements"]["candidate_runs_below_reference_median_latency"] == 4

    consistency_failure = _inputs(
        "fast",
        candidate_latencies=[90, 90, 90, 100, 100],
    )
    failed = award_mod.build_award(**consistency_failure)
    assert failed["awarded"] is False
    assert "candidate_runs_below_reference_median_latency" in failed["failures"]

    median_failure = _inputs("fast", candidate_latencies=[91, 91, 91, 91, 91])
    failed = award_mod.build_award(**median_failure)
    assert failed["failures"] == ["median_latency_ratio"]


def test_balanced_label_bounds_size_latency_and_memory_at_declared_edges() -> None:
    passing = _inputs(
        "balanced",
        candidate_latencies=[105] * 5,
        candidate_peaks=[2100] * 5,
    )
    report = award_mod.build_award(**passing)
    assert report["awarded"] is True
    assert report["measurements"]["median_latency_ratio"] == 1.05
    assert report["measurements"]["median_peak_resident_memory_ratio"] == 1.05

    failed = award_mod.build_award(
        **_inputs("balanced", candidate_peaks=[2101] * 5)
    )
    assert failed["failures"] == ["median_peak_resident_memory_ratio"]


def test_award_is_order_independent_and_contains_no_private_task_values() -> None:
    inputs = _inputs("fast")
    first = award_mod.build_award(**inputs)
    reordered = dict(inputs)
    reordered["reference_operational"] = list(reversed(inputs["reference_operational"]))
    reordered["candidate_operational"] = list(reversed(inputs["candidate_operational"]))
    assert award_mod.build_award(**reordered) == first
    serialized = json.dumps(first, sort_keys=True)
    for forbidden in ("metric_checks", "prediction_parity", '"upos"', '"lemma"'):
        assert forbidden not in serialized
    assert set(first["measurements"]["reference"]) == {
        "artifact_size_bytes",
        "median_latency_ms_per_100_tokens",
        "median_peak_resident_memory_bytes",
    }
    assert set(first["measurements"]["candidate"]) == set(
        first["measurements"]["reference"]
    )

    runtime_record = NeuralRuntimeVariant(
        label="fast",
        availability="available",
        model_id=first["candidate"]["model_identity"],
        dataset="candidate-model-data",
        asset_sha256="1" * 64,
        bundle_manifest_sha256=first["candidate"]["bundle_manifest_sha256"],
        award_sha256=first["award_sha256"],
        qualification_sha256=first["qualification_sha256"],
    )
    _validate_variant_award(first, runtime_record)


def test_award_rejects_unbound_repeated_or_mixed_environment_evidence() -> None:
    inputs = _inputs("fast")
    repeated = dict(inputs)
    repeated["candidate_operational"] = [inputs["candidate_operational"][0]] * 5
    with pytest.raises(award_mod.VariantAwardError, match="repeats"):
        award_mod.build_award(**repeated)

    mixed = dict(inputs)
    candidates = list(inputs["candidate_operational"])
    candidates[-1] = _operational(
        "candidate-model",
        artifact_bytes=90,
        latency=90,
        peak=2000,
        run=99,
        environment={**ENVIRONMENT, "processor": "other-cpu"},
    )
    mixed["candidate_operational"] = candidates
    with pytest.raises(award_mod.VariantAwardError, match="one exact environment"):
        award_mod.build_award(**mixed)

    unbound = dict(inputs)
    unbound["qualification_report"] = _qualification(
        inputs["reference_operational"][0],
        _operational(
            "candidate-model",
            artifact_bytes=90,
            latency=90,
            peak=2000,
            run=100,
        ),
    )
    with pytest.raises(award_mod.VariantAwardError, match="bound candidate"):
        award_mod.build_award(**unbound)

    malformed = dict(inputs)
    malformed_report = dict(inputs["qualification_report"])
    malformed_report["candidate"] = {
        "model_identity": "candidate-model",
        "operational_evidence_sha256": inputs["candidate_operational"][0]["evidence_sha256"],
    }
    malformed["qualification_report"] = manifest_mod.stamp_document(
        malformed_report, "qualification_sha256"
    )
    with pytest.raises(award_mod.VariantAwardError, match="fields differ"):
        award_mod.build_award(**malformed)


def test_unqualified_a20_decision_produces_a_non_award_and_tamper_needs_rebuild() -> None:
    inputs = _inputs("compact", qualified=False)
    report = award_mod.build_award(**inputs)
    assert report["awarded"] is False
    assert report["failures"] == ["a20_qualification"]

    passing = _inputs("compact")
    report = award_mod.build_award(**passing)
    tampered = dict(report)
    tampered["measurements"] = dict(report["measurements"])
    tampered["measurements"]["candidate_runs_below_reference_median_latency"] = 0
    tampered = manifest_mod.stamp_document(tampered, "award_sha256")
    award_mod.validate_award(tampered)
    with pytest.raises(award_mod.VariantAwardError, match="does not reproduce"):
        award_mod.verify_award(tampered, **passing)

    inconsistent = dict(report)
    inconsistent["measurements"] = dict(report["measurements"])
    inconsistent["measurements"]["artifact_size_ratio"] = 0.1
    inconsistent = manifest_mod.stamp_document(inconsistent, "award_sha256")
    with pytest.raises(award_mod.VariantAwardError, match="public summaries"):
        award_mod.validate_award(inconsistent)


def test_policy_loader_rejects_duplicate_and_oversized_json(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"format":"a","format":"b"}', encoding="utf-8")
    with pytest.raises(award_mod.VariantAwardError, match="duplicate"):
        award_mod.load_policy(duplicate)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"{" + b" " * (8 * 1024 * 1024) + b"}")
    with pytest.raises(award_mod.VariantAwardError, match="outside"):
        award_mod.load_policy(oversized)


def test_award_command_help_has_no_heavy_runtime_dependency() -> None:
    result = subprocess.run(
        [sys.executable, str(TRAINING / "runtime_variant_award.py"), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--candidate-operational" in result.stdout
