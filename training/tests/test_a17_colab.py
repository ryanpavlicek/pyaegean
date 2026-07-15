"""Offline contract tests for the guarded A17 Colab completion workflow."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TRAINING = Path(__file__).resolve().parents[1]
ROOT = TRAINING.parent
sys.path.insert(0, str(TRAINING))

import a17_colab as a17  # noqa: E402
import reproducibility as repro  # noqa: E402


def _accelerator() -> dict:
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


def _hardware() -> dict:
    accelerator = _accelerator()
    return {
        "platform": "Linux-6.6.0",
        "machine": "x86_64",
        "cpu": "fixture CPU",
        "gpu": accelerator["gpu_names"][0],
        "gpu_count": accelerator["gpu_count"],
        "gpu_memory_bytes": accelerator["gpu_memory_bytes"][0],
        "driver_version": accelerator["driver_version"],
        "cuda_runtime_version": accelerator["cuda_runtime_version"],
        "torch_cuda_version": accelerator["torch_cuda_version"],
        "cudnn_version": accelerator["cudnn_version"],
        "compute_capability": accelerator["compute_capabilities"][0],
        "precision": accelerator["precision"],
    }


def _run(root: Path, *argv: str) -> str:
    process = subprocess.run(
        list(argv),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return process.stdout.strip()


def test_a17_requirements_match_frozen_direct_roots() -> None:
    lock = repro.load_environment_lock(TRAINING / "environment-lock.json")
    requirements = [
        line.split("==", 1)
        for line in (TRAINING / "a17-requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [name for name, _ in requirements] == list(a17.A17_DIRECT_ROOTS)
    assert dict(requirements) == {
        package["name"]: package["version"] for package in lock["dependencies"]["packages"]
    }


def test_a17_contract_schemas_are_valid_json() -> None:
    for path in (
        TRAINING / "contracts" / "backbone-resolution.schema.json",
        TRAINING / "contracts" / "evidence-summary.schema.json",
    ):
        document = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(document, dict)


def test_reviewed_a17_evidence_is_complete_and_content_addressed() -> None:
    evidence = TRAINING / "results" / "a17-environment"
    summary = repro.load_json_document(evidence / "evidence-summary.json")
    assert repro.document_sha256(summary, "summary_sha256") == summary["summary_sha256"]
    assert [record["path"] for record in summary["artifacts"]] == [
        f"training/results/a17-environment/{name}"
        for name in a17.REVIEWED_EVIDENCE_FILENAMES
    ]
    for record in summary["artifacts"]:
        repro.verify_file_record(record, root=ROOT)

    lock = repro.load_environment_lock(evidence / "environment-lock.json")
    repro.validate_environment_lock(lock, require_validated=True)
    preflight = repro.load_json_document(evidence / "preflight.json")
    repro.validate_preflight_report(preflight, environment_lock=lock)
    assert preflight["ok"] is True
    receipt = repro.load_run_receipt(evidence / "run-receipt.json", environment_lock=lock)
    a17._verify_a17_receipt_files(receipt, root=ROOT)
    assert receipt["repository"] == preflight["observed"]["repository"]
    assert summary["source_commit"] == receipt["repository"]["commit"]
    assert summary["hardware"] == receipt["hardware"]


def test_backbone_metadata_resolution_is_exact_and_weight_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = repro.load_environment_lock(TRAINING / "environment-lock.json")
    calls: list[tuple[str, str, bool]] = []

    class FakeApi:
        def model_info(
            self, repository: str, *, revision: str, files_metadata: bool, timeout: float
        ) -> object:
            assert timeout == 30.0
            calls.append((repository, revision, files_metadata))
            files = [*a17.REQUIRED_BACKBONE_FILES, "model.safetensors"]
            return SimpleNamespace(
                sha=revision,
                siblings=[SimpleNamespace(rfilename=name) for name in files],
            )

    monkeypatch.setattr(
        a17.importlib,
        "import_module",
        lambda name: SimpleNamespace(HfApi=FakeApi),
    )
    proof = a17.resolve_backbone_metadata(lock)
    assert calls == [(lock["backbone"]["repository"], lock["backbone"]["revision"], False)]
    a17.validate_backbone_resolution(proof, environment_lock=lock)
    assert proof["resolved_revision"] == lock["backbone"]["revision"]

    tampered = copy.deepcopy(proof)
    tampered["resolved_revision"] = "f" * 40
    tampered = repro.stamp_document(tampered, "resolution_sha256")
    with pytest.raises(repro.ContractError, match="different revision"):
        a17.validate_backbone_resolution(tampered, environment_lock=lock)


def test_full_a17_evidence_and_archive_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    evidence = root / "training" / "results" / "a17-environment"
    (root / "training" / "fixtures").mkdir(parents=True)
    shutil.copy2(TRAINING / "a17-requirements.txt", root / "training" / "a17-requirements.txt")
    shutil.copy2(TRAINING / "a17-dry-run-config.json", root / "training" / "a17-dry-run-config.json")
    shutil.copy2(
        TRAINING / "fixtures" / "a17-dry-run.jsonl",
        root / "training" / "fixtures" / "a17-dry-run.jsonl",
    )
    (root / ".gitignore").write_text(
        "training/results/a17-environment/\n", encoding="utf-8", newline="\n"
    )
    _run(root.parent, "git", "init", str(root))
    _run(root, "git", "config", "user.name", "A17 Fixture")
    _run(root, "git", "config", "user.email", "a17@example.invalid")
    _run(root, "git", "remote", "add", "origin", "https://example.invalid/pyaegean.git")
    _run(root, "git", "add", ".gitignore", "training")
    _run(root, "git", "commit", "-m", "fixture")
    repository = repro.capture_repository(root)
    assert repository["dirty"] is False
    evidence.mkdir(parents=True)

    template = repro.load_environment_lock(TRAINING / "environment-lock.json")
    manifest = repro.build_resolver_manifest(
        tool_name="pip",
        tool_version="26.1",
        direct_roots=template["dependencies"]["direct_roots"],
        resolved_packages=[
            *template["dependencies"]["packages"],
            # Torch requires setuptools on Python >=3.12, so it is part of the
            # resolver closure even though pip itself was bootstrapped earlier.
            {"name": "setuptools", "version": "80.9.0"},
        ],
    )
    repro.write_json_document(evidence / "resolver-manifest.json", manifest)
    monkeypatch.setattr(
        repro,
        "capture_packages",
        lambda names: copy.deepcopy(manifest["resolved_packages"]),
    )
    monkeypatch.setattr(repro.platform, "python_implementation", lambda: "CPython")
    monkeypatch.setattr(repro.platform, "python_version", lambda: "3.12.13")
    monkeypatch.setattr(repro.platform, "system", lambda: "Linux")
    monkeypatch.setattr(repro.platform, "release", lambda: "6.6.0-a17")
    monkeypatch.setattr(repro.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(repro.platform, "libc_ver", lambda: ("glibc", "2.35"))
    candidate = repro.capture_candidate_environment_lock(
        template,
        resolver_manifest=manifest,
        resolver_file=repro.file_record(evidence / "resolver-manifest.json", root=root),
        accelerator=_accelerator(),
    )
    repro.write_json_document(evidence / "environment-candidate.json", candidate)
    preflight = repro.stamp_document(
        {
            "format": repro.PREFLIGHT_FORMAT,
            "ok": True,
            "environment_definition_sha256": candidate["environment_definition_sha256"],
            "observed": {
                "python": copy.deepcopy(candidate["python"]),
                "platform": copy.deepcopy(candidate["platform"]),
                "packages": copy.deepcopy(candidate["dependencies"]["packages"]),
                "repository": repository,
                "accelerator": _accelerator(),
            },
            "issues": [],
        },
        "preflight_sha256",
    )
    repro.write_json_document(evidence / "preflight.json", preflight)
    lock = repro.promote_environment_lock(candidate, preflight)
    repro.write_json_document(evidence / "environment-lock.json", lock)

    proof = repro.stamp_document(
        {
            "format": a17.BACKBONE_RESOLUTION_FORMAT,
            "repository": lock["backbone"]["repository"],
            "requested_revision": lock["backbone"]["revision"],
            "resolved_revision": lock["backbone"]["revision"],
            "tokenizer_revision": lock["backbone"]["tokenizer_revision"],
            "required_files": list(a17.REQUIRED_BACKBONE_FILES),
            "available_files": list(a17.REQUIRED_BACKBONE_FILES),
        },
        "resolution_sha256",
    )
    repro.write_json_document(evidence / "backbone-resolution.json", proof)

    installs = [
        {
            "metadata": {"name": package["name"], "version": package["version"]},
            "requested": package["name"] in manifest["direct_roots"],
        }
        for package in manifest["resolved_packages"]
    ]
    repro.write_json_document(
        evidence / "pip-report.json", {"pip_version": "26.1", "install": installs}
    )
    requirements_path = root / "training" / "a17-requirements.txt"
    repro.write_json_document(
        evidence / "install-command.json",
        {
            "format": "pyaegean-a17-install-command/1",
            "operation_count": 1,
            "argv": [
                "/content/pyaegean-a17-venv/bin/python",
                "-m",
                "pip",
                "install",
                "--no-cache-dir",
                "--index-url",
                "https://pypi.org/simple",
                "--extra-index-url",
                "https://download.pytorch.org/whl/cu128",
                "--report",
                "/content/pyaegean-a17/training/results/a17-environment/pip-report.json",
                "--requirement",
                "/content/pyaegean-a17/training/a17-requirements.txt",
            ],
            "requirements": a17._canonical_text_file_record(requirements_path, root=root),
        },
    )
    (evidence / "pip-check.txt").write_text(
        "No broken requirements found.\n", encoding="utf-8", newline="\n"
    )
    (evidence / "pip-freeze.txt").write_text(
        "".join(
            f"{package['name']}=={package['version']}\n"
            for package in manifest["resolved_packages"]
        )
        + "pip==26.1\n",
        encoding="utf-8",
        newline="\n",
    )
    (evidence / "nvidia-smi.txt").write_text(
        "NVIDIA-SMI 600.0\nNVIDIA A100-SXM4-80GB\n", encoding="utf-8", newline="\n"
    )
    monkeypatch.setattr(a17, "capture_run_hardware", _hardware)
    receipt = a17.run_dry_receipt(
        lock_path=evidence / "environment-lock.json",
        preflight_path=evidence / "preflight.json",
        backbone_path=evidence / "backbone-resolution.json",
        config_path=root / "training" / "a17-dry-run-config.json",
        dataset_path=root / "training" / "fixtures" / "a17-dry-run.jsonl",
        output_path=evidence / "dry-run-output.json",
        receipt_path=evidence / "run-receipt.json",
        repository_root=root,
    )
    assert receipt["repository"] == repository
    summary = a17.verify_evidence(evidence, repository_root=root)
    assert summary["source_commit"] == repository["commit"]

    first = a17.bundle_evidence(evidence, repository_root=root, output=tmp_path / "one.zip")
    second = a17.bundle_evidence(evidence, repository_root=root, output=tmp_path / "two.zip")
    assert first["archive_sha256"] == second["archive_sha256"]
    reviewed = a17.write_reviewed_evidence_summary(
        evidence, repository_root=root, output=evidence / "reviewed-evidence-summary.json"
    )
    assert [record["path"] for record in reviewed["artifacts"]] == [
        f"training/results/a17-environment/{name}"
        for name in a17.REVIEWED_EVIDENCE_FILENAMES
    ]
    assert _run(root, "git", "status", "--porcelain") == ""
