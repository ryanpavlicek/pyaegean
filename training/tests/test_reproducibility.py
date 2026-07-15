"""Focused, inference-free tests for the A17 training contracts."""

from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TRAINING = Path(__file__).resolve().parents[1]
ROOT = TRAINING.parent
sys.path.insert(0, str(TRAINING))

import reproducibility as repro  # noqa: E402


def _captured_accelerator() -> dict:
    return {
        "kind": "cuda",
        "gpu_names": ["NVIDIA A100-SXM4-80GB"],
        "gpu_count": 1,
        "gpu_memory_bytes": [85_899_345_920],
        "compute_capabilities": ["8.0"],
        "precision": "bf16",
        "cuda_runtime_version": "12.7.1",
        "torch_cuda_version": "12.8",
        "cudnn_version": "9.10.2",
        "driver_version": "600.0",
    }


def _lock() -> dict:
    return repro.load_environment_lock(TRAINING / "environment-lock.json")


def _resolver_manifest() -> dict:
    lock = _lock()
    return repro.build_resolver_manifest(
        tool_name="pip",
        tool_version="26.1",
        direct_roots=[package["name"] for package in lock["dependencies"]["packages"]],
        resolved_packages=lock["dependencies"]["packages"],
    )


def _captured_lock(
    *, resolver_file: dict | None = None, resolver_manifest: dict | None = None
) -> dict:
    lock = copy.deepcopy(_lock())
    manifest = _resolver_manifest() if resolver_manifest is None else resolver_manifest
    evidence_file = resolver_file or {"path": "training/out/resolver.json", "bytes": 1, "sha256": "e" * 64}
    lock["verification"] = {
        "state": "captured-candidate",
        "preflight_receipt_sha256": None,
    }
    lock["dependencies"]["scope"] = "training-dependency-closure"
    lock["dependencies"]["complete"] = True
    lock["dependencies"]["direct_roots"] = manifest["direct_roots"]
    lock["dependencies"]["resolver_evidence"] = {
        "file": evidence_file,
        "manifest_sha256": manifest["manifest_sha256"],
    }
    accelerator = _captured_accelerator()
    lock["accelerator"]["frozen"] = {
        field: accelerator[field]
        for field in (
            "gpu_names",
            "gpu_count",
            "gpu_memory_bytes",
            "compute_capabilities",
            "precision",
            "cuda_runtime_version",
            "torch_cuda_version",
            "cudnn_version",
            "driver_version",
        )
    }
    lock = repro.stamp_environment_lock(lock)
    repro.validate_environment_lock(lock)
    return lock


def _successful_preflight(lock: dict) -> dict:
    return repro.stamp_document(
        {
            "format": repro.PREFLIGHT_FORMAT,
            "ok": True,
            "environment_definition_sha256": lock["environment_definition_sha256"],
            "observed": {
                "python": copy.deepcopy(lock["python"]),
                "platform": copy.deepcopy(lock["platform"]),
                "packages": copy.deepcopy(lock["dependencies"]["packages"]),
                "repository": {
                    "url": "https://example.invalid/repo.git",
                    "commit": "c" * 40,
                    "dirty": False,
                },
                "accelerator": _captured_accelerator(),
            },
            "issues": [],
        },
        "preflight_sha256",
    )


def _validated_lock(
    *, resolver_file: dict | None = None, resolver_manifest: dict | None = None
) -> dict:
    captured = _captured_lock(
        resolver_file=resolver_file,
        resolver_manifest=resolver_manifest,
    )
    return repro.promote_environment_lock(captured, _successful_preflight(captured))


def _materialize_run(tmp_path: Path) -> tuple[dict, Path, dict]:
    manifest = _resolver_manifest()
    manifest_path = tmp_path / "training" / "out" / "resolver-manifest.json"
    lock_path = tmp_path / "training" / "environment-lock.json"
    config_path = tmp_path / "training" / "run-config.json"
    dataset_path = tmp_path / "training" / "data" / "full.jsonl"
    output_path = tmp_path / "training" / "out" / "weights.safetensors"
    for path in (manifest_path, lock_path, config_path, dataset_path, output_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    repro.write_json_document(manifest_path, manifest)
    resolver_file = repro.file_record(manifest_path, root=tmp_path)
    lock = _validated_lock(resolver_file=resolver_file, resolver_manifest=manifest)
    repro.write_json_document(lock_path, lock)
    config_path.write_text('{"epochs":4,"seed":7}\n', encoding="utf-8")
    dataset_path.write_text('{"forms":["λόγος"]}\n', encoding="utf-8")
    output_path.write_bytes(b"fixed artifact bytes")

    receipt = repro.build_run_receipt(
        run={
            "id": "fixture-run",
            "status": "completed",
            "started_utc": "2026-07-14T10:00:00Z",
            "finished_utc": "2026-07-14T10:01:00Z",
            "command": ["python", "training/train_full.py", "--seed", "7"],
            "config": repro.file_record(config_path, root=tmp_path),
            "seed": 7,
        },
        repository={
            "url": "https://github.com/ryanpavlicek/pyaegean.git",
            "commit": "a" * 40,
            "dirty": False,
        },
        environment={
            "lock": repro.file_record(lock_path, root=tmp_path),
            "lock_sha256": lock["lock_sha256"],
            "dependency_scope": lock["dependencies"]["scope"],
            "dependency_inventory_complete": lock["dependencies"]["complete"],
            "preflight_receipt_sha256": lock["verification"]["preflight_receipt_sha256"],
            "packages": lock["dependencies"]["packages"],
        },
        backbone=lock["backbone"],
        corpora=[
            {
                "name": "agdt",
                "repository": "https://example.invalid/agdt.git",
                "commit": "b" * 40,
            }
        ],
        datasets=[repro.file_record(dataset_path, root=tmp_path)],
        outputs=[repro.file_record(output_path, root=tmp_path)],
        hardware={
            "platform": "Linux-6.6.0",
            "machine": "x86_64",
            "cpu": "fixture cpu",
            "gpu": "NVIDIA A100-SXM4-80GB",
            "gpu_count": 1,
            "gpu_memory_bytes": lock["accelerator"]["frozen"]["gpu_memory_bytes"][0],
            "driver_version": lock["accelerator"]["frozen"]["driver_version"],
            "cuda_runtime_version": lock["accelerator"]["frozen"]["cuda_runtime_version"],
            "torch_cuda_version": lock["accelerator"]["frozen"]["torch_cuda_version"],
            "cudnn_version": lock["accelerator"]["frozen"]["cudnn_version"],
            "compute_capability": lock["accelerator"]["frozen"]["compute_capabilities"][0],
            "precision": lock["accelerator"]["frozen"]["precision"],
        },
        environment_lock=lock,
    )
    return receipt, output_path, lock


def test_contract_schemas_are_committed_json_documents() -> None:
    environment = json.loads(
        (TRAINING / "contracts" / "environment-lock.schema.json").read_text(encoding="utf-8")
    )
    receipt = json.loads(
        (TRAINING / "contracts" / "run-receipt.schema.json").read_text(encoding="utf-8")
    )
    resolver = json.loads(
        (TRAINING / "contracts" / "resolver-manifest.schema.json").read_text(encoding="utf-8")
    )
    preflight = json.loads(
        (TRAINING / "contracts" / "preflight.schema.json").read_text(encoding="utf-8")
    )
    assert environment["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert environment["properties"]["format"]["const"] == repro.ENVIRONMENT_LOCK_FORMAT
    assert receipt["properties"]["format"]["const"] == repro.RUN_RECEIPT_FORMAT
    assert resolver["properties"]["format"]["const"] == repro.RESOLVER_MANIFEST_FORMAT
    assert preflight["properties"]["format"]["const"] == repro.PREFLIGHT_FORMAT
    assert environment["additionalProperties"] is False
    assert receipt["additionalProperties"] is False


def test_committed_lock_is_content_addressed_and_explicitly_unverified() -> None:
    lock = _lock()
    assert lock["verification"] == {
        "state": "unverified-template",
        "preflight_receipt_sha256": None,
    }
    assert lock["dependencies"]["scope"] == "direct-requirements"
    assert lock["dependencies"]["complete"] is False
    assert lock["dependencies"]["resolver_evidence"] is None
    assert lock["accelerator"]["frozen"]["driver_version"] is None
    assert lock["accelerator"]["frozen"]["cudnn_version"] is None
    assert lock["lock_sha256"] == repro.document_sha256(lock, "lock_sha256")
    assert lock["environment_definition_sha256"] == repro.environment_definition_sha256(lock)
    assert len(lock["backbone"]["revision"]) == 40
    assert lock["backbone"]["revision_type"] == "git-commit"
    assert lock["backbone"]["tokenizer_revision"] == lock["backbone"]["revision"]


def test_canonical_json_is_order_independent_and_rejects_non_finite_numbers() -> None:
    left = {"β": [2, 1], "a": {"z": True}}
    right = {"a": {"z": True}, "β": [2, 1]}
    assert repro.canonical_json(left) == repro.canonical_json(right)
    assert repro.canonical_sha256(left) == repro.canonical_sha256(right)
    with pytest.raises(repro.ContractError, match="canonical JSON"):
        repro.canonical_sha256({"loss": math.nan})


def test_lock_rejects_mutable_revisions_ranges_and_tampering() -> None:
    lock = _lock()

    mutable = copy.deepcopy(lock)
    mutable["backbone"]["revision"] = "main"
    with pytest.raises(repro.ContractError, match="Git commit"):
        repro.validate_environment_lock(mutable, verify_digest=False)

    ranged = copy.deepcopy(lock)
    ranged["dependencies"]["packages"][0]["version"] = ">=1.0"
    with pytest.raises(repro.ContractError, match="exact version"):
        repro.validate_environment_lock(ranged, verify_digest=False)

    tampered = copy.deepcopy(lock)
    tampered["python"]["version"] = "3.12.12"
    with pytest.raises(repro.ContractError, match="digest mismatch"):
        repro.validate_environment_lock(tampered)


def test_captured_lock_requires_complete_closure_or_full_environment() -> None:
    lock = copy.deepcopy(_lock())
    lock["verification"] = {
        "state": "captured-candidate",
        "preflight_receipt_sha256": None,
    }
    lock = repro.stamp_environment_lock(lock)
    with pytest.raises(repro.ContractError, match="complete training dependency closure"):
        repro.validate_environment_lock(lock)


def test_file_records_are_relative_and_detect_changed_bytes(tmp_path: Path) -> None:
    data = tmp_path / "data" / "rows.jsonl"
    data.parent.mkdir()
    data.write_bytes(b"one\n")
    record = repro.file_record(data, root=tmp_path)
    assert record == {
        "path": "data/rows.jsonl",
        "bytes": 4,
        "sha256": repro.sha256_file(data),
    }
    repro.verify_file_record(record, root=tmp_path)
    data.write_bytes(b"two\n")
    with pytest.raises(repro.ContractError, match="SHA-256 mismatch"):
        repro.verify_file_record(record, root=tmp_path)

    outside = tmp_path.parent / "outside-a17.txt"
    outside.write_text("outside", encoding="utf-8")
    try:
        with pytest.raises(repro.ContractError, match="outside repository root"):
            repro.file_record(outside, root=tmp_path)
    finally:
        outside.unlink()


def test_run_receipt_binds_lock_inputs_outputs_and_hardware(tmp_path: Path) -> None:
    receipt, output_path, lock = _materialize_run(tmp_path)
    assert receipt["receipt_sha256"] == repro.document_sha256(receipt, "receipt_sha256")
    repro.validate_run_receipt(receipt, environment_lock=lock)
    repro.verify_receipt_files(receipt, root=tmp_path)

    output_path.write_bytes(b"changed artifact")
    with pytest.raises(repro.ContractError, match="mismatch"):
        repro.verify_receipt_files(receipt, root=tmp_path)


def test_run_receipt_rejects_dirty_or_lock_divergent_runs(tmp_path: Path) -> None:
    receipt, _, lock = _materialize_run(tmp_path)

    dirty = copy.deepcopy(receipt)
    dirty["repository"]["dirty"] = True
    dirty = repro.stamp_document(dirty, "receipt_sha256")
    with pytest.raises(repro.ContractError, match="clean repository"):
        repro.validate_run_receipt(dirty, environment_lock=lock)

    different_packages = copy.deepcopy(receipt)
    different_packages["environment"]["packages"][0]["version"] = "1.11.0"
    different_packages = repro.stamp_document(different_packages, "receipt_sha256")
    with pytest.raises(repro.ContractError, match="differ from the environment lock"):
        repro.validate_run_receipt(different_packages, environment_lock=lock)

    different_driver = copy.deepcopy(receipt)
    different_driver["hardware"]["driver_version"] = "999.0"
    different_driver = repro.stamp_document(different_driver, "receipt_sha256")
    with pytest.raises(repro.ContractError, match="hardware.driver_version differs"):
        repro.validate_run_receipt(different_driver, environment_lock=lock)

    different_torch_cuda = copy.deepcopy(receipt)
    different_torch_cuda["hardware"]["torch_cuda_version"] = "13.0"
    different_torch_cuda = repro.stamp_document(different_torch_cuda, "receipt_sha256")
    with pytest.raises(repro.ContractError, match="hardware.torch_cuda_version differs"):
        repro.validate_run_receipt(different_torch_cuda, environment_lock=lock)

    unsupported_gpu = copy.deepcopy(receipt)
    unsupported_gpu["hardware"]["gpu"] = "NVIDIA H100"
    unsupported_gpu = repro.stamp_document(unsupported_gpu, "receipt_sha256")
    with pytest.raises(repro.ContractError, match="allocation policy"):
        repro.validate_run_receipt(unsupported_gpu, environment_lock=lock)

    with pytest.raises(repro.ContractError, match="clean-machine validated"):
        repro.validate_run_receipt(receipt, environment_lock=_lock())

    tampered = copy.deepcopy(receipt)
    tampered["hardware"]["precision"] = "fp16"
    with pytest.raises(repro.ContractError, match="digest mismatch"):
        repro.validate_run_receipt(tampered)


def test_preflight_is_content_addressed_and_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = _captured_lock()
    monkeypatch.setattr(repro.platform, "python_implementation", lambda: lock["python"]["implementation"])
    monkeypatch.setattr(repro.platform, "python_version", lambda: lock["python"]["version"])
    monkeypatch.setattr(repro.platform, "system", lambda: lock["platform"]["system"])
    monkeypatch.setattr(repro.platform, "release", lambda: lock["platform"]["release"])
    monkeypatch.setattr(repro.platform, "machine", lambda: lock["platform"]["machine"])
    monkeypatch.setattr(
        repro.platform,
        "libc_ver",
        lambda: (lock["platform"]["libc"]["name"], lock["platform"]["libc"]["version"]),
    )
    monkeypatch.setattr(
        repro,
        "capture_packages",
        lambda names: lock["dependencies"]["packages"],
    )
    monkeypatch.setattr(
        repro,
        "capture_all_packages",
        lambda: pytest.fail("closure preflight must ignore unrelated installed packages"),
    )
    monkeypatch.setattr(repro, "verify_resolver_evidence", lambda lock, root: _resolver_manifest())
    monkeypatch.setattr(
        repro,
        "capture_repository",
        lambda root: {"url": "https://example.invalid/repo.git", "commit": "c" * 40, "dirty": False},
    )
    accelerator = _captured_accelerator()
    monkeypatch.setattr(repro, "capture_accelerator", lambda: accelerator)

    report = repro.preflight_environment(lock, repository_root=ROOT)
    assert report["ok"] is True
    assert report["issues"] == []
    assert report["preflight_sha256"] == repro.document_sha256(report, "preflight_sha256")
    assert report["environment_definition_sha256"] == lock["environment_definition_sha256"]
    exact = repro.preflight_environment(
        lock, repository_root=ROOT, expected_repository_commit="c" * 40
    )
    assert exact["ok"] is True
    wrong_commit = repro.preflight_environment(
        lock, repository_root=ROOT, expected_repository_commit="d" * 40
    )
    assert wrong_commit["ok"] is False
    assert "repository commit differs from the required candidate commit" in wrong_commit["issues"]

    promoted = repro.promote_environment_lock(lock, report)
    assert promoted["verification"]["state"] == "validated"
    assert promoted["verification"]["preflight_receipt_sha256"] == report["preflight_sha256"]
    assert promoted["environment_definition_sha256"] == lock["environment_definition_sha256"]
    assert promoted["lock_sha256"] != lock["lock_sha256"]

    monkeypatch.setattr(
        repro,
        "capture_packages",
        lambda names: [
            {**package, "version": "0.0"} if package["name"] == "torch" else package
            for package in lock["dependencies"]["packages"]
        ],
    )
    report = repro.preflight_environment(lock, repository_root=ROOT)
    assert report["ok"] is False
    assert "installed training dependency closure differs from environment lock" in report["issues"]


def test_unverified_template_and_unapproved_gpu_fail_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = _lock()
    monkeypatch.setattr(repro.platform, "python_implementation", lambda: template["python"]["implementation"])
    monkeypatch.setattr(repro.platform, "python_version", lambda: template["python"]["version"])
    monkeypatch.setattr(repro.platform, "system", lambda: template["platform"]["system"])
    monkeypatch.setattr(repro.platform, "release", lambda: template["platform"]["release"])
    monkeypatch.setattr(repro.platform, "machine", lambda: template["platform"]["machine"])
    monkeypatch.setattr(
        repro.platform,
        "libc_ver",
        lambda: (template["platform"]["libc"]["name"], template["platform"]["libc"]["version"]),
    )
    monkeypatch.setattr(
        repro,
        "capture_packages",
        lambda names: template["dependencies"]["packages"],
    )
    monkeypatch.setattr(
        repro,
        "capture_repository",
        lambda root: {"url": "https://example.invalid/repo.git", "commit": "c" * 40, "dirty": False},
    )
    monkeypatch.setattr(
        repro,
        "capture_accelerator",
        lambda: {
            "kind": "cuda",
            "gpu_names": ["NVIDIA H100"],
            "gpu_count": 1,
            "gpu_memory_bytes": [85_899_345_920],
            "compute_capabilities": ["9.0"],
            "precision": "bf16",
            "cuda_runtime_version": "12.8",
            "torch_cuda_version": "12.8",
            "cudnn_version": "9.99.0",
            "driver_version": "600.0",
        },
    )
    report = repro.preflight_environment(template, repository_root=ROOT)
    assert report["ok"] is False
    assert "environment lock dependency inventory is incomplete" in report["issues"]
    assert "environment lock is an unverified template" in report["issues"]
    assert "allocated GPU is outside the preferred/fallback policy" in report["issues"]


def test_resolver_evidence_binds_complete_closure_and_rejects_divergence(
    tmp_path: Path,
) -> None:
    manifest = _resolver_manifest()
    manifest_path = tmp_path / "training" / "out" / "resolver-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    repro.write_json_document(manifest_path, manifest)
    evidence_file = repro.file_record(manifest_path, root=tmp_path)
    lock = _captured_lock(resolver_file=evidence_file, resolver_manifest=manifest)
    assert repro.verify_resolver_evidence(lock, root=tmp_path) == manifest

    divergent = copy.deepcopy(lock)
    divergent["dependencies"]["packages"][0]["version"] = "0.0"
    divergent = repro.stamp_environment_lock(divergent)
    repro.validate_environment_lock(divergent)
    with pytest.raises(repro.ContractError, match="packages differ from resolver evidence"):
        repro.verify_resolver_evidence(divergent, root=tmp_path)

    missing = copy.deepcopy(lock)
    missing["dependencies"]["resolver_evidence"] = None
    missing = repro.stamp_environment_lock(missing)
    with pytest.raises(repro.ContractError, match="resolver_evidence must be an object"):
        repro.validate_environment_lock(missing)


def test_promotion_rejects_mismatched_definition_receipt() -> None:
    candidate = _captured_lock()
    report = _successful_preflight(candidate)
    report["environment_definition_sha256"] = "d" * 64
    report = repro.stamp_document(report, "preflight_sha256")
    with pytest.raises(repro.ContractError, match="different environment definition"):
        repro.promote_environment_lock(candidate, report)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda report: report.__setitem__("observed", {}), "missing required fields"),
        (
            lambda report: report["observed"]["packages"][0].__setitem__(
                "version", "999.0"
            ),
            "packages differ",
        ),
        (
            lambda report: report["observed"]["repository"].__setitem__("dirty", True),
            "clean repository",
        ),
        (
            lambda report: report["observed"].__setitem__("accelerator", None),
            "observe an accelerator",
        ),
        (
            lambda report: report["observed"]["accelerator"].__setitem__(
                "gpu_names", ["NVIDIA H100"]
            ),
            "preferred/fallback policy",
        ),
        (
            lambda report: report["observed"]["accelerator"].__setitem__(
                "driver_version", "999.0"
            ),
            "accelerator.driver_version differs",
        ),
    ],
)
def test_promotion_rejects_fabricated_or_divergent_observations(
    mutation: object,
    message: str,
) -> None:
    candidate = _captured_lock()
    report = _successful_preflight(candidate)
    assert callable(mutation)
    mutation(report)
    report = repro.stamp_document(report, "preflight_sha256")
    with pytest.raises(repro.ContractError, match=message):
        repro.promote_environment_lock(candidate, report)


def test_candidate_capture_uses_resolver_closure_and_live_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = _lock()
    manifest = _resolver_manifest()
    monkeypatch.setattr(
        repro,
        "capture_packages",
        lambda names: manifest["resolved_packages"],
    )
    monkeypatch.setattr(repro.platform, "python_implementation", lambda: "CPython")
    monkeypatch.setattr(repro.platform, "python_version", lambda: "3.12.99")
    monkeypatch.setattr(repro.platform, "system", lambda: "Linux")
    monkeypatch.setattr(repro.platform, "release", lambda: "fixture-kernel")
    monkeypatch.setattr(repro.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(repro.platform, "libc_ver", lambda: ("glibc", "2.99"))
    accelerator = _captured_accelerator()
    candidate = repro.capture_candidate_environment_lock(
        template,
        resolver_manifest=manifest,
        resolver_file={"path": "training/out/resolver.json", "bytes": 1, "sha256": "e" * 64},
        accelerator=accelerator,
    )
    assert candidate["verification"]["state"] == "captured-candidate"
    assert candidate["python"]["version"] == "3.12.99"
    assert candidate["dependencies"]["packages"] == manifest["resolved_packages"]
    assert candidate["dependencies"]["direct_roots"] == manifest["direct_roots"]
    assert candidate["accelerator"]["frozen"] == {
        field: accelerator[field]
        for field in (
            "gpu_names",
            "gpu_count",
            "gpu_memory_bytes",
            "compute_capabilities",
            "precision",
            "cuda_runtime_version",
            "torch_cuda_version",
            "cudnn_version",
            "driver_version",
        )
    }
    assert candidate["environment_definition_sha256"] == repro.environment_definition_sha256(
        candidate
    )

    unsupported = copy.deepcopy(accelerator)
    unsupported["gpu_names"] = ["NVIDIA H100"]
    with pytest.raises(repro.ContractError, match="preferred/fallback policy"):
        repro.capture_candidate_environment_lock(
            template,
            resolver_manifest=manifest,
            resolver_file={
                "path": "training/out/resolver.json",
                "bytes": 1,
                "sha256": "e" * 64,
            },
            accelerator=unsupported,
        )


def test_pip_report_normalization_records_tool_roots_and_complete_list() -> None:
    packages = _lock()["dependencies"]["packages"]
    direct = {package["name"] for package in packages}
    report = {
        "pip_version": "26.1",
        "install": [
            {
                "metadata": {"name": package["name"], "version": package["version"]},
                "requested": package["name"] in direct,
            }
            for package in packages
        ],
    }
    manifest = repro.resolver_manifest_from_pip_report(report)
    assert manifest["tool"] == {"name": "pip", "version": "26.1"}
    assert manifest["direct_roots"] == sorted(direct)
    assert manifest["resolved_packages"] == packages
    assert manifest["manifest_sha256"] == repro.document_sha256(
        manifest, "manifest_sha256"
    )


def test_accelerator_captures_runtime_and_torch_build_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_torch = SimpleNamespace(
        version=SimpleNamespace(cuda="12.8"),
        cuda=SimpleNamespace(
            is_available=lambda: True,
            device_count=lambda: 1,
            get_device_name=lambda index: "NVIDIA A100-SXM4-80GB",
            get_device_properties=lambda index: SimpleNamespace(total_memory=85_899_345_920),
            get_device_capability=lambda index: (8, 0),
            is_bf16_supported=lambda: True,
        ),
        backends=SimpleNamespace(cudnn=SimpleNamespace(version=lambda: 91002)),
    )
    monkeypatch.setattr(repro.importlib, "import_module", lambda name: fake_torch)
    monkeypatch.setattr(repro, "capture_cuda_runtime_version", lambda: "12.7.1")
    monkeypatch.setattr(
        repro.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="600.0\n", stderr=""),
    )
    observed = repro.capture_accelerator()
    assert observed["cuda_runtime_version"] == "12.7.1"
    assert observed["torch_cuda_version"] == "12.8"
    assert observed["cuda_runtime_version"] != observed["torch_cuda_version"]


def test_cuda_runtime_prefers_active_wheel_over_system_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheel_library = Path("C:/venv/nvidia/cuda_runtime/lib/libcudart.so.12")

    class Distribution:
        files = [Path("nvidia/cuda_runtime/lib/libcudart.so.12")]

        @staticmethod
        def locate_file(relative: Path) -> Path:
            assert relative.name == "libcudart.so.12"
            return wheel_library

    class VersionFunction:
        argtypes: object = None
        restype: object = None

        @staticmethod
        def __call__(pointer: object) -> int:
            pointer._obj.value = 12080  # type: ignore[attr-defined]
            return 0

    class Runtime:
        cudaRuntimeGetVersion = VersionFunction()

    seen: list[str] = []

    def load(candidate: object) -> Runtime:
        seen.append(str(candidate))
        if str(candidate) != str(wheel_library):
            raise OSError("wrong runtime")
        return Runtime()

    monkeypatch.setattr(repro.importlib.metadata, "distribution", lambda name: Distribution())
    monkeypatch.setattr(repro.importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(repro.ctypes.util, "find_library", lambda name: "system-libcudart.so")
    monkeypatch.setattr(repro.ctypes, "CDLL", load)
    assert repro.capture_cuda_runtime_version() == "12.8.0"
    assert seen == [str(wheel_library)]
