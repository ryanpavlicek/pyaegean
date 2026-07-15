"""Correctness, adversarial, and journey tests for artifact qualification."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

TRAINING = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TRAINING))
sys.path.insert(0, str(TESTS))

import artifact_qualification as qualification  # noqa: E402
import development_manifest as manifest_mod  # noqa: E402
import development_report as report_mod  # noqa: E402
import model_selection as selection_mod  # noqa: E402
import test_development_report as report_fixtures  # noqa: E402


def _selection_gate(manifest_sha256: str) -> dict[str, object]:
    return selection_mod.stamp_gate(
        {
            "format": selection_mod.GATE_FORMAT,
            "gate_id": "fixture-selection-v1",
            "claim_status": selection_mod.CLAIM_STATUS,
            "development_manifest_sha256": manifest_sha256,
            "decoder": {
                "identity": "fixture-release-mst",
                "mode": "sequential",
                "long_input": "windowed",
            },
            "protected_metrics": [
                {"metric": "lemma", "slice": "source/fixture", "max_regression": 0.0001},
                {"metric": "las", "slice": "source/fixture", "max_regression": 0.0001},
            ],
            "target_metrics": [
                {"metric": "lemma", "slice": "source/fixture", "weight": 0.5},
                {"metric": "las", "slice": "source/fixture", "weight": 0.5},
            ],
            "operational_limits": {
                "profile_id": "fixture",
                "max_artifact_size_bytes": 1000000000,
                "max_latency_ms_per_100_tokens": 10000.0,
            },
            "promotion": {
                "minimum_weighted_target_gain": 0.0,
                "require_pareto_non_dominated": True,
            },
            "tie_breaking": [
                {"field": "weighted_target_gain", "direction": "descending"},
                {"field": "worst_protected_delta", "direction": "descending"},
                {"field": "latency_ms_per_100_tokens", "direction": "ascending"},
                {"field": "artifact_size_bytes", "direction": "ascending"},
                {"field": "candidate_id", "direction": "ascending"},
            ],
        }
    )


def _gate(manifest_sha256: str, selection_sha256: str) -> dict[str, object]:
    exact = {field: 0.0 for field in ("upos", "xpos", "ufeats", "lemma", "head", "deprel")}
    bounded = {field: 0.001 for field in exact}
    common = {
        "required_providers": ["CPUExecutionProvider"],
        "optional_providers": ["CUDAExecutionProvider"],
        "max_artifact_size_bytes": 1000,
        "max_latency_ms_per_100_tokens": 100.0,
        "max_peak_resident_memory_bytes": 1000,
    }
    return qualification.stamp_gate(
        {
            "format": qualification.GATE_FORMAT,
            "gate_id": "fixture-artifact-gate-v1",
            "claim_status": qualification.CLAIM_STATUS,
            "development_manifest_sha256": manifest_sha256,
            "selection_gate_sha256": selection_sha256,
            "measurement": {
                "profile_id": "pyaegean-cpu-sequential-complete-dev-v1",
                "execution_provider": "CPUExecutionProvider",
                "mode": "sequential",
                "long_input": "windowed",
                "warmup_items": 1,
                "timed_scope": "complete-development-manifest",
                "memory_sample_interval_ms": 10,
                "provider_probe_items": ["shortest", "median", "longest"],
            },
            "profiles": {
                "export": {
                    "transform": "framework-export",
                    "metric_regression_scale": 0.0,
                    "max_prediction_disagreement_fraction": exact,
                    **common,
                    "require_smaller_than_reference": False,
                },
                "optimization": {
                    "transform": "artifact-optimization",
                    "metric_regression_scale": 1.0,
                    "max_prediction_disagreement_fraction": bounded,
                    **common,
                    "require_smaller_than_reference": True,
                },
            },
        }
    )


def _report(
    manifest: dict[str, object], predictions: dict[str, list[dict[str, object]]], identity: str
) -> dict[str, object]:
    gold, _ = report_fixtures._inputs(4)
    run = report_fixtures._run(predictions)
    run["model"]["identity"] = identity
    run["decoder"]["identity"] = "fixture-release-mst"
    return report_mod.build_report(
        manifest=manifest,
        gold_sentences=gold,
        predictions=predictions,
        run=run,
        n_resamples=9,
    )


def _operational(
    manifest_sha256: str, *, identity: str, size: int = 120, latency: float = 10.0
) -> dict[str, object]:
    elapsed_ns = int(latency * 1_000_000)
    return qualification.stamp_operational_evidence(
        {
            "format": qualification.EVIDENCE_FORMAT,
            "claim_status": qualification.CLAIM_STATUS,
            "profile_id": "pyaegean-cpu-sequential-complete-dev-v1",
            "development_manifest_sha256": manifest_sha256,
            "artifact": {
                "identity": identity,
                "directory_sha256": "a" * 64,
                "model_sha256": "b" * 64,
                "artifact_size_bytes": size,
                "model_size_bytes": 100,
                "files": [
                    {"path": "labels.json", "bytes": size - 101, "sha256": "c" * 64},
                    {"path": "manifest.json", "bytes": 1, "sha256": "e" * 64},
                    {"path": "model.onnx", "bytes": 100, "sha256": "b" * 64},
                ],
            },
            "timing": {
                "mode": "sequential",
                "long_input": "windowed",
                "warmup_items": 1,
                "timed_items": 4,
                "timed_tokens": 100,
                "elapsed_ns": elapsed_ns,
                "latency_ms_per_100_tokens": latency,
            },
            "memory": {
                "method": "fixture-rss",
                "sample_interval_ms": 10,
                "baseline_resident_bytes": 100,
                "peak_resident_bytes": 150,
                "incremental_peak_bytes": 50,
            },
            "provider_matrix": [
                {
                    "provider": "CPUExecutionProvider",
                    "required": True,
                    "available": True,
                    "status": "pass",
                    "session_providers": ["CPUExecutionProvider"],
                    "prediction_sha256": "d" * 64,
                    "cpu_disagreement_fraction": {
                        field: 0.0
                        for field in ("upos", "xpos", "ufeats", "lemma", "head", "deprel")
                    },
                    "error": None,
                },
                {
                    "provider": "CUDAExecutionProvider",
                    "required": False,
                    "available": False,
                    "status": "unavailable",
                    "session_providers": [],
                    "prediction_sha256": None,
                    "cpu_disagreement_fraction": None,
                    "error": None,
                },
            ],
            "environment": {
                "python": "3.14.0",
                "platform": "fixture",
                "machine": "fixture",
                "processor": "fixture",
                "onnxruntime": "1.23.0",
                "numpy": "2.0.0",
                "tokenizers": "0.20.0",
            },
        }
    )


def _fixture() -> dict[str, object]:
    manifest = report_fixtures._manifest(4)
    selection = _selection_gate(str(manifest["manifest_sha256"]))
    gate = _gate(str(manifest["manifest_sha256"]), str(selection["gate_sha256"]))
    gold, predictions = report_fixtures._inputs(4)
    reference_predictions = copy.deepcopy(predictions)
    candidate_predictions = copy.deepcopy(predictions)
    return {
        "gate": gate,
        "selection_gate": selection,
        "manifest": manifest,
        "profile_id": "export",
        "gold": gold,
        "reference_report": _report(manifest, reference_predictions, "torch-candidate"),
        "reference_predictions": reference_predictions,
        "candidate_report": _report(manifest, candidate_predictions, "onnx-candidate"),
        "candidate_predictions": candidate_predictions,
        "candidate_operational": _operational(
            str(manifest["manifest_sha256"]), identity="onnx-candidate"
        ),
        "reference_operational": None,
    }


def test_frozen_gate_binds_a18_a19_and_schema() -> None:
    gate = qualification.load_gate(TRAINING / "artifact-qualification-gate-v1.json")
    selection = selection_mod.load_gate(TRAINING / "model-selection-gate-v1.json")
    manifest = manifest_mod.load_document(
        TRAINING / "results" / "development-source-manifest.json",
        verify=True,
        digest_field="manifest_sha256",
    )
    schema = json.loads(
        (TRAINING / "contracts" / "artifact-qualification-gate.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["properties"]["format"]["const"] == qualification.GATE_FORMAT
    assert gate["selection_gate_sha256"] == selection["gate_sha256"]
    assert gate["development_manifest_sha256"] == manifest["manifest_sha256"]
    assert all(
        value == 0.0
        for value in gate["profiles"]["export"]["max_prediction_disagreement_fraction"].values()
    )
    assert all(
        value == pytest.approx(0.001)
        for value in gate["profiles"]["optimization"][
            "max_prediction_disagreement_fraction"
        ].values()
    )


def test_exact_export_journey_qualifies_and_reverifies() -> None:
    inputs = _fixture()
    result = qualification.build_qualification_report(**inputs)
    assert result["qualified"] is True
    assert result["failures"] == []
    assert all(check["passed"] for check in result["metric_checks"])
    assert all(check["disagreements"] == 0 for check in result["prediction_parity"])
    qualification.verify_qualification_report(result, **inputs)


def test_bad_artifact_is_rejected_for_compensating_output_drift() -> None:
    inputs = _fixture()
    candidate = copy.deepcopy(inputs["candidate_predictions"])
    candidate["src/doc/s0"][0]["lemma"] = "wrong"
    # Offset the raw accuracy loss with a correction elsewhere. Aggregate accuracy
    # can therefore stay equal, while output parity must still reject the artifact.
    reference = inputs["reference_predictions"]
    reference["src/doc/s1"][0]["lemma"] = "wrong"
    inputs["reference_report"] = _report(inputs["manifest"], reference, "torch-candidate")
    inputs["candidate_predictions"] = candidate
    inputs["candidate_report"] = _report(inputs["manifest"], candidate, "onnx-candidate")
    result = qualification.build_qualification_report(**inputs)
    assert result["qualified"] is False
    assert "prediction disagreement lemma" in result["failures"]
    lemma = next(check for check in result["prediction_parity"] if check["field"] == "lemma")
    assert lemma["disagreements"] == 2
    assert lemma["fraction"] == pytest.approx(0.5)


def test_optimization_requires_smaller_reference_and_respects_limits() -> None:
    inputs = _fixture()
    inputs["profile_id"] = "optimization"
    inputs["reference_operational"] = _operational(
        str(inputs["manifest"]["manifest_sha256"]), identity="torch-candidate", size=120
    )
    inputs["candidate_operational"] = _operational(
        str(inputs["manifest"]["manifest_sha256"]), identity="onnx-candidate", size=120
    )
    result = qualification.build_qualification_report(**inputs)
    assert result["qualified"] is False
    assert "operational limit smaller_than_reference" in result["failures"]


def test_runtime_evidence_must_bind_to_report_identity_and_digest() -> None:
    inputs = _fixture()
    changed = copy.deepcopy(inputs["candidate_operational"])
    changed["artifact"]["identity"] = "unrelated-candidate"
    inputs["candidate_operational"] = qualification.stamp_operational_evidence(changed)
    with pytest.raises(qualification.QualificationError, match="identity/digest"):
        qualification.build_qualification_report(**inputs)


def test_rebuild_refuses_a_restamped_but_false_development_report() -> None:
    inputs = _fixture()
    changed = copy.deepcopy(inputs["candidate_report"])
    changed["items"][0]["metrics"]["lemma"]["numerator"] = 0
    changed["items"][0]["metrics"]["lemma"]["value"] = 0.0
    changed["metrics"]["lemma"]["numerator"] -= 1
    changed["metrics"]["lemma"]["value"] = changed["metrics"]["lemma"]["numerator"] / changed[
        "metrics"
    ]["lemma"]["denominator"]
    changed = manifest_mod.stamp_document(changed, "report_sha256")
    inputs["candidate_report"] = changed
    with pytest.raises(qualification.QualificationError, match="verify|reproduce|report"):
        qualification.build_qualification_report(**inputs)


def test_gate_loader_rejects_duplicate_keys_and_oversized_input(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"format":"a","format":"b"}', encoding="utf-8")
    with pytest.raises(qualification.QualificationError, match="duplicate JSON key"):
        qualification.load_gate(duplicate)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"{" + b" " * (1024 * 1024) + b"}")
    with pytest.raises(qualification.QualificationError, match="input limit"):
        qualification.load_gate(oversized)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda gate: gate["profiles"]["export"].__setitem__(
                "metric_regression_scale", 1.0
            ),
            "export metric regression",
        ),
        (
            lambda gate: gate["measurement"].__setitem__("mode", "batched"),
            "sequential",
        ),
        (
            lambda gate: gate["profiles"]["optimization"][
                "required_providers"
            ].remove("CPUExecutionProvider"),
            "CPUExecutionProvider",
        ),
    ],
)
def test_gate_rejects_weakened_or_implicit_policy(mutation: object, message: str) -> None:
    gate = copy.deepcopy(_fixture()["gate"])
    assert callable(mutation)
    mutation(gate)
    gate = manifest_mod.stamp_document(gate, "gate_sha256")
    with pytest.raises(qualification.QualificationError, match=message):
        qualification.validate_gate(gate)
