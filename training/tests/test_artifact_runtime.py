"""Offline runtime and whole-path tests for integrated artifact qualification."""

from __future__ import annotations

import copy
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
TRAINING = REPO / "training"
TRAINING_TESTS = TRAINING / "tests"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(TRAINING))
sys.path.insert(0, str(TRAINING_TESTS))

import artifact_qualification as qualification  # noqa: E402
import artifact_runtime as runtime  # noqa: E402
import development_manifest as manifest_mod  # noqa: E402
import model_selection as selection_mod  # noqa: E402
import run_development_evaluation as development_runner  # noqa: E402
import test_artifact_qualification as qualification_fixtures  # noqa: E402
import test_run_development_evaluation as runner_fixtures  # noqa: E402
from aegean.greek.neural_contract import write_schema1_manifest  # noqa: E402
from tests.test_a13_export_contract import _write_legal_bundle  # noqa: E402


class _Session:
    def __init__(self, providers: list[str]) -> None:
        self._providers = providers

    def get_providers(self) -> list[str]:
        return list(self._providers)


class _Backend:
    def __init__(self, provider: str, *, drift: bool = False) -> None:
        self._sess = _Session([provider])
        self._drift = drift

    def analyze(self, forms: list[str], *, long_input: str = "windowed") -> object:
        assert long_input == "windowed"
        return SimpleNamespace(
            lemma=["wrong" if self._drift else form for form in forms],
            upos=["NOUN"] * len(forms),
            xpos=["n--------"] * len(forms),
            feats=["Case=Nom|Gender=Masc|Number=Sing"] * len(forms),
            head=[0] * len(forms),
            deprel=["root"] * len(forms),
        )


def _bundle(root: Path, model_id: str = "grc-joint-v4-fixture") -> Path:
    root.mkdir()
    _write_legal_bundle(root)
    write_schema1_manifest(
        root,
        model_id=model_id,
        annotation_profile="pyaegean-canonical-v1",
        normalization="NFC",
        segmentation="pretokenized",
        preprocessing_version="pyaegean-neural-preprocessing-v1",
        variant="fp32",
    )
    return root


def _selection_gate(manifest_sha256: str) -> dict[str, object]:
    return selection_mod.stamp_gate(
        {
            "format": selection_mod.GATE_FORMAT,
            "gate_id": "runtime-selection-v1",
            "claim_status": selection_mod.CLAIM_STATUS,
            "development_manifest_sha256": manifest_sha256,
            "decoder": {
                "identity": "pyaegean-release-single-root-mst-v1",
                "mode": "sequential",
                "long_input": "windowed",
            },
            "protected_metrics": [
                {"metric": "lemma", "slice": "aggregate", "max_regression": 0.0001},
                {"metric": "las", "slice": "aggregate", "max_regression": 0.0001},
            ],
            "target_metrics": [
                {"metric": "lemma", "slice": "aggregate", "weight": 0.5},
                {"metric": "las", "slice": "aggregate", "weight": 0.5},
            ],
            "operational_limits": {
                "profile_id": "runtime",
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


def _reference(
    *,
    tmp_path: Path,
    manifest: dict[str, object],
    perseus: Path,
    tagging: Path,
    parsing: Path,
    environment: str,
    run_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    identity = run_identity or {
        "model": {"identity": "torch-reference", "asset_sha256": "1" * 64},
        "preprocessing": {"identity": "fixture", "config_sha256": "2" * 64},
        "output_profile": {
            "identity": "pyaegean-canonical-v1",
            "tasks": ["parsing", "tagging"],
        },
        "decoder": {
            "identity": "pyaegean-release-single-root-mst-v1",
            "mode": "sequential",
            "long_input": "windowed",
        },
    }
    return development_runner.run_development_evaluation(
        manifest=manifest,
        perseus_dev=perseus,
        papygreek_tagging=tagging,
        papygreek_parse=parsing,
        environment_receipt=environment,
        output_dir=tmp_path / "reference",
        git_revision="1" * 40,
        pipeline=lambda sentences, **kwargs: list(sentences),
        run_identity=identity,
    )


def _fixture(tmp_path: Path) -> dict[str, object]:
    manifest, perseus, tagging, parsing, environment = runner_fixtures._fixture(tmp_path)
    selection = _selection_gate(str(manifest["manifest_sha256"]))
    gate = qualification_fixtures._gate(
        str(manifest["manifest_sha256"]), str(selection["gate_sha256"])
    )
    # The real resident set is larger than the tiny unit-fixture threshold.
    gate["profiles"]["export"]["max_peak_resident_memory_bytes"] = 8 * 1024**3
    gate["profiles"]["export"]["max_artifact_size_bytes"] = 1_000_000
    gate["profiles"]["export"]["max_latency_ms_per_100_tokens"] = 100_000.0
    gate = manifest_mod.stamp_document(gate, "gate_sha256")
    qualification.validate_gate(gate)
    artifact = _bundle(tmp_path / "artifact")
    candidate_identity = runtime._run_identity(artifact, runtime.artifact_record(artifact))
    reference_identity = copy.deepcopy(candidate_identity)
    reference_identity["model"] = {
        "identity": "torch-reference",
        "asset_sha256": "1" * 64,
    }
    reference = _reference(
        tmp_path=tmp_path,
        manifest=manifest,
        perseus=perseus,
        tagging=tagging,
        parsing=parsing,
        environment=environment,
        run_identity=reference_identity,
    )
    return {
        "gate": gate,
        "selection_gate": selection,
        "manifest": manifest,
        "profile_id": "export",
        "perseus_dev": perseus,
        "papygreek_tagging": tagging,
        "papygreek_parse": parsing,
        "artifact_dir": artifact,
        "output_dir": tmp_path / "candidate",
        "reference_report": reference["report"],
        "reference_predictions": reference["predictions"],
        "git_revision": "2" * 40,
        "available_providers": ["CPUExecutionProvider"],
        "runtime_environment": {
            "python": "fixture",
            "platform": "fixture",
            "machine": "fixture",
            "processor": "fixture",
            "onnxruntime": "fixture",
            "numpy": "fixture",
            "tokenizers": "fixture",
        },
    }


def test_artifact_record_hashes_every_flat_runtime_file(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / "bundle")
    record = runtime.artifact_record(bundle)
    assert record["identity"] == "grc-joint-v4-fixture"
    assert record["model_size_bytes"] == len(b"synthetic-onnx")
    assert record["artifact_size_bytes"] == sum(
        path.stat().st_size for path in bundle.iterdir()
    )
    assert [entry["path"] for entry in record["files"]] == sorted(
        path.name for path in bundle.iterdir()
    )


def test_artifact_record_rejects_nested_or_empty_entries(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / "bundle")
    (bundle / "nested").mkdir()
    with pytest.raises(runtime.ArtifactRuntimeError, match="regular non-symlink"):
        runtime.artifact_record(bundle)


def test_reference_json_loader_rejects_duplicates_and_oversize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"record": 1, "record": 2}', encoding="utf-8")
    with pytest.raises(runtime.ArtifactRuntimeError, match="duplicate JSON key"):
        runtime._load_json(duplicate, where="reference predictions")

    oversized = tmp_path / "oversized.json"
    oversized.write_text('{"record": 1}', encoding="utf-8")
    monkeypatch.setattr(runtime, "_MAX_JSON_BYTES", 4)
    with pytest.raises(runtime.ArtifactRuntimeError, match="outside the allowed range"):
        runtime._load_json(oversized, where="reference predictions")


def test_integrated_runtime_journey_qualifies_and_reloads_evidence(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)

    def factory(path: Path, **kwargs: object) -> _Backend:
        del path, kwargs
        return _Backend(os.environ["PYAEGEAN_ORT_PROVIDERS"])

    result = runtime.qualify_artifact(**inputs, backend_factory=factory)
    assert result["qualification"]["qualified"] is True
    assert result["operational"]["timing"]["timed_items"] == 1
    assert result["operational"]["timing"]["timed_tokens"] == 1
    assert result["operational"]["artifact"]["identity"] == "grc-joint-v4-fixture"
    assert result["operational"]["provider_matrix"][0]["status"] == "pass"
    for path in result["paths"].values():
        assert Path(path).is_file()
    saved = qualification.load_qualification_report(result["paths"]["qualification"])
    assert saved == result["qualification"]


def test_fake_runtime_environment_does_not_import_optional_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = _fixture(tmp_path)
    monkeypatch.setattr(
        runtime,
        "_runtime_environment",
        lambda: pytest.fail("optional dependency discovery should not run for injected evidence"),
    )

    def factory(path: Path, **kwargs: object) -> _Backend:
        del path, kwargs
        return _Backend(os.environ["PYAEGEAN_ORT_PROVIDERS"])

    result = runtime.qualify_artifact(**inputs, backend_factory=factory)
    assert result["operational"]["environment"] == inputs["runtime_environment"]


def test_present_optional_provider_drift_is_recorded_and_blocks_export(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
    inputs["available_providers"] = ["CPUExecutionProvider", "CUDAExecutionProvider"]

    def factory(path: Path, **kwargs: object) -> _Backend:
        del path, kwargs
        provider = os.environ["PYAEGEAN_ORT_PROVIDERS"]
        return _Backend(provider, drift=provider == "CUDAExecutionProvider")

    result = runtime.qualify_artifact(**inputs, backend_factory=factory)
    assert result["qualification"]["qualified"] is False
    cuda = next(
        entry
        for entry in result["operational"]["provider_matrix"]
        if entry["provider"] == "CUDAExecutionProvider"
    )
    assert cuda["status"] == "pass"
    assert cuda["cpu_disagreement_fraction"]["lemma"] == 1.0
    assert "provider compatibility CUDAExecutionProvider" in result["qualification"]["failures"]


def test_present_optional_provider_failure_blocks_export(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
    inputs["available_providers"] = ["CPUExecutionProvider", "CUDAExecutionProvider"]

    def factory(path: Path, **kwargs: object) -> _Backend:
        del path, kwargs
        provider = os.environ["PYAEGEAN_ORT_PROVIDERS"]
        if provider == "CUDAExecutionProvider":
            raise RuntimeError("fixture CUDA failure")
        return _Backend(provider)

    result = runtime.qualify_artifact(**inputs, backend_factory=factory)
    assert result["qualification"]["qualified"] is False
    assert "provider compatibility CUDAExecutionProvider" in result["qualification"]["failures"]


def test_required_provider_failure_is_fail_closed(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
    changed_gate = copy.deepcopy(inputs["gate"])
    profile = changed_gate["profiles"]["export"]
    profile["optional_providers"] = []
    profile["required_providers"] = ["CPUExecutionProvider", "CUDAExecutionProvider"]
    inputs["gate"] = manifest_mod.stamp_document(changed_gate, "gate_sha256")

    def factory(path: Path, **kwargs: object) -> _Backend:
        del path, kwargs
        return _Backend(os.environ["PYAEGEAN_ORT_PROVIDERS"])

    result = runtime.qualify_artifact(**inputs, backend_factory=factory)
    assert result["qualification"]["qualified"] is False
    assert "provider compatibility CUDAExecutionProvider" in result["qualification"]["failures"]
