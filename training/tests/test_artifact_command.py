"""Staging, fail-closed promotion, and archive-input tests for artifact commands."""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

TRAINING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING))

import artifact_command as command  # noqa: E402
import quantize_grc_joint as quantize  # noqa: E402


def test_qualification_arguments_default_to_current_decoder_gates() -> None:
    parser = argparse.ArgumentParser()
    command.add_qualification_arguments(parser, require_reference_operational=False)

    qualification = parser.get_default("qualification_gate")
    selection = parser.get_default("selection_gate")

    assert qualification.name == "artifact-qualification-gate-v2.json"
    assert selection.name == "model-selection-gate-v2.json"


def _args(tmp_path: Path) -> argparse.Namespace:
    paths = {}
    for name in (
        "qualification_gate",
        "selection_gate",
        "development_manifest",
        "perseus_dev_source",
        "papygreek_tagging_source",
        "papygreek_parse_source",
        "reference_report",
        "reference_predictions",
    ):
        path = tmp_path / f"{name}.json"
        path.write_text("{}", encoding="utf-8")
        paths[name] = path
    return argparse.Namespace(**paths, reference_operational=None)


def test_rejected_qualification_never_promotes_or_archives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging, artifact = command.staging_artifact(tmp_path, "candidate")
    (artifact / "model.onnx").write_bytes(b"candidate")
    evidence = command.qualification_output(tmp_path, "candidate", "export")
    summary = {"qualified": False, "failures": ["prediction disagreement lemma"]}
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 2, stdout=json.dumps(summary), stderr=""
        ),
    )
    with pytest.raises(command.ArtifactCommandError, match="qualification failed"):
        command.run_qualification(
            args=_args(tmp_path),
            artifact_dir=artifact,
            profile="export",
            output_dir=evidence,
        )
    assert artifact.is_dir()
    assert not (tmp_path / "candidate").exists()
    assert not (tmp_path / "candidate.tar.gz").exists()
    assert staging.is_dir()


def test_passing_qualification_can_promote_then_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging, artifact = command.staging_artifact(tmp_path, "candidate")
    (artifact / "model.onnx").write_bytes(b"candidate")
    evidence = command.qualification_output(tmp_path, "candidate", "export")
    summary = {"qualified": True, "qualification_sha256": "a" * 64}
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout=json.dumps(summary), stderr=""
        ),
    )
    assert command.run_qualification(
        args=_args(tmp_path),
        artifact_dir=artifact,
        profile="export",
        output_dir=evidence,
    ) == summary
    final = tmp_path / "candidate"
    command.promote_artifact(staging, artifact, final)
    archive = tmp_path / "candidate.tar.gz"
    command.archive_artifact(final, archive)
    repeated = tmp_path / "candidate-repeat.tar.gz"
    command.archive_artifact(final, repeated)
    assert final.is_dir() and archive.is_file()
    assert archive.read_bytes() == repeated.read_bytes()
    with tarfile.open(archive) as opened:
        assert opened.getnames() == ["model.onnx"]


def test_source_archive_rejects_traversal_and_links(tmp_path: Path) -> None:
    archive = tmp_path / "hostile.tar.gz"
    with tarfile.open(archive, "w:gz") as opened:
        traversal = tarfile.TarInfo("../model.onnx")
        traversal.size = 1
        opened.addfile(traversal, io.BytesIO(b"x"))
    with pytest.raises(command.ArtifactCommandError, match="unsafe or invalid"):
        with quantize._source_directory(archive):
            pytest.fail("hostile archive was accepted")


def test_optimization_source_must_match_reference_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = {"identity": "fp32", "directory_sha256": "a" * 64}
    evidence = {"artifact": dict(record)}
    monkeypatch.setattr(quantize, "load_operational_evidence", lambda path: evidence)
    monkeypatch.setattr(quantize, "artifact_record", lambda path: dict(record))
    quantize._verify_reference_artifact(tmp_path, tmp_path / "evidence.json")

    record["directory_sha256"] = "b" * 64
    with pytest.raises(command.ArtifactCommandError, match="differs"):
        quantize._verify_reference_artifact(tmp_path, tmp_path / "evidence.json")


def test_staging_refuses_existing_final_or_archive(tmp_path: Path) -> None:
    (tmp_path / "candidate").mkdir()
    with pytest.raises(command.ArtifactCommandError, match="refusing to replace"):
        command.staging_artifact(tmp_path, "candidate")


def test_archive_rejects_nested_entries(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "nested").mkdir()
    with pytest.raises(command.ArtifactCommandError, match="non-regular"):
        command.archive_artifact(artifact, tmp_path / "artifact.tar.gz")
    assert not (tmp_path / "artifact.tar.gz").exists()


@pytest.mark.parametrize("script", ["export_onnx.py", "quantize_grc_joint.py"])
def test_conversion_help_does_not_require_heavy_toolchain(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, str(TRAINING / script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--model-id" in completed.stdout
