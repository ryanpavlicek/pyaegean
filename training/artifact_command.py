"""Shared staging and qualification helpers for conversion commands."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any


class ArtifactCommandError(RuntimeError):
    """Raised when staging, qualification, promotion, or archiving fails."""


def add_qualification_arguments(
    parser: argparse.ArgumentParser, *, require_reference_operational: bool
) -> None:
    training = Path(__file__).parent
    parser.add_argument(
        "--qualification-gate",
        type=Path,
        default=training / "artifact-qualification-gate-v3.json",
    )
    parser.add_argument(
        "--selection-gate",
        type=Path,
        default=training / "model-selection-gate-v3.json",
    )
    parser.add_argument(
        "--development-manifest",
        type=Path,
        default=training / "results" / "development-source-manifest.json",
    )
    parser.add_argument("--perseus-dev-source", required=True, type=Path)
    parser.add_argument("--papygreek-tagging-source", required=True, type=Path)
    parser.add_argument("--papygreek-parse-source", required=True, type=Path)
    parser.add_argument("--reference-report", required=True, type=Path)
    parser.add_argument("--reference-predictions", required=True, type=Path)
    parser.add_argument(
        "--reference-operational",
        required=require_reference_operational,
        type=Path,
    )


def validate_qualification_paths(args: argparse.Namespace) -> None:
    fields = (
        "qualification_gate",
        "selection_gate",
        "development_manifest",
        "perseus_dev_source",
        "papygreek_tagging_source",
        "papygreek_parse_source",
        "reference_report",
        "reference_predictions",
    )
    if getattr(args, "reference_operational", None) is not None:
        fields = (*fields, "reference_operational")
    missing = [str(getattr(args, field)) for field in fields if not getattr(args, field).is_file()]
    if missing:
        raise ArtifactCommandError(f"qualification input files do not exist: {missing}")


def staging_artifact(out: Path, artifact_name: str) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    final = out / artifact_name
    archive = out / f"{artifact_name}.tar.gz"
    if final.exists() or archive.exists():
        raise ArtifactCommandError(
            f"refusing to replace final artifact/archive; choose a new identity: {artifact_name}"
        )
    staging_root = Path(tempfile.mkdtemp(prefix=f".{artifact_name}.staging-", dir=out))
    artifact = staging_root / artifact_name
    artifact.mkdir()
    return staging_root, artifact


def qualification_output(out: Path, artifact_name: str, profile: str) -> Path:
    evidence = out / "qualification" / f"{artifact_name}-{profile}"
    if evidence.exists():
        raise ArtifactCommandError(
            f"refusing stale qualification output: {evidence}; choose a new identity"
        )
    evidence.mkdir(parents=True)
    return evidence


def run_qualification(
    *,
    args: argparse.Namespace,
    artifact_dir: Path,
    profile: str,
    output_dir: Path,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).with_name("artifact_runtime.py")),
        "--artifact-dir",
        str(artifact_dir),
        "--profile",
        profile,
        "--gate",
        str(args.qualification_gate),
        "--selection-gate",
        str(args.selection_gate),
        "--manifest",
        str(args.development_manifest),
        "--perseus-dev-source",
        str(args.perseus_dev_source),
        "--papygreek-tagging-source",
        str(args.papygreek_tagging_source),
        "--papygreek-parse-source",
        str(args.papygreek_parse_source),
        "--reference-report",
        str(args.reference_report),
        "--reference-predictions",
        str(args.reference_predictions),
        "--output-dir",
        str(output_dir),
    ]
    if args.reference_operational is not None:
        command.extend(("--reference-operational", str(args.reference_operational)))
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise ArtifactCommandError(f"could not start isolated qualification: {exc}") from exc
    stdout = completed.stdout.strip()
    summary: dict[str, Any] | None = None
    if stdout:
        try:
            value = json.loads(stdout.splitlines()[-1])
            if isinstance(value, dict):
                summary = value
        except json.JSONDecodeError:
            summary = None
    if completed.returncode != 0 or summary is None or summary.get("qualified") is not True:
        detail = completed.stderr.strip() or stdout or f"exit status {completed.returncode}"
        raise ArtifactCommandError(
            f"artifact qualification failed; staged artifact remains at {artifact_dir}: {detail}"
        )
    return summary


def promote_artifact(staging_root: Path, artifact: Path, final: Path) -> None:
    if final.exists():
        raise ArtifactCommandError(f"final artifact appeared during qualification: {final}")
    try:
        os.replace(artifact, final)
        staging_root.rmdir()
    except OSError as exc:
        raise ArtifactCommandError(f"could not promote qualified artifact: {exc}") from exc


def archive_artifact(artifact: Path, target: Path) -> None:
    temporary = target.with_name(f".{target.name}.tmp")
    if temporary.exists():
        raise ArtifactCommandError(f"refusing stale archive temporary file: {temporary}")
    try:
        with temporary.open("xb") as raw, gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, mtime=0
        ) as compressed, tarfile.open(
            fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT
        ) as archive:
            for path in sorted(artifact.iterdir(), key=lambda item: item.name):
                if path.is_symlink() or not path.is_file():
                    raise ArtifactCommandError(
                        f"cannot archive non-regular artifact entry: {path.name}"
                    )
                info = tarfile.TarInfo(path.name)
                info.size = path.stat().st_size
                info.mode = 0o644
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                with path.open("rb") as source:
                    archive.addfile(info, source)
        os.replace(temporary, target)
    except (ArtifactCommandError, OSError, tarfile.TarError) as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, ArtifactCommandError):
            raise
        raise ArtifactCommandError(f"could not archive qualified artifact: {exc}") from exc


def remove_empty_staging(staging_root: Path) -> None:
    """Remove an empty staging root after a handled pre-artifact failure."""

    try:
        if staging_root.is_dir() and not any(staging_root.iterdir()):
            staging_root.rmdir()
    except OSError:
        pass


def copy_runtime_sidecars(source: Path, target: Path) -> None:
    for name in ("tokenizer.json", "labels.json", "lemma-scripts.json", "lemma-lookup.json"):
        try:
            shutil.copy2(source / name, target / name)
        except OSError as exc:
            raise ArtifactCommandError(f"could not copy runtime sidecar {name}: {exc}") from exc
