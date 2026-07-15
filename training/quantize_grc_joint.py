"""Create and qualify an optimized Greek joint ONNX candidate.

The transform applies 8-bit symmetric MatMulNBits weights and converts remaining
eligible graph values to fp16 while keeping I/O types stable.  The command makes no
speed or accuracy assumption from that recipe: it stages the result and runs the
complete A20 optimization profile against a qualified fp32 reference.  Only a
passing artifact receives a final directory and archive.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
import tarfile
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from artifact_command import (  # noqa: E402
    ArtifactCommandError,
    add_qualification_arguments,
    archive_artifact,
    copy_runtime_sidecars,
    promote_artifact,
    qualification_output,
    run_qualification,
    staging_artifact,
    validate_qualification_paths,
)
from artifact_qualification import (  # noqa: E402
    QualificationError,
    load_operational_evidence,
)
from artifact_runtime import ArtifactRuntimeError, artifact_record  # noqa: E402

from aegean.greek.neural_contract import (  # noqa: E402
    ModelBundleError,
    ModelBundleManifest,
    validate_artifact_metadata,
    write_schema1_manifest,
)

_MAX_ARCHIVE_MEMBER_BYTES = 2_000_000_000
_MAX_ARCHIVE_FILES = 64
_MAX_ARCHIVE_TOTAL_BYTES = 2_000_000_000


@contextlib.contextmanager
def _source_directory(source: Path) -> Iterator[Path]:
    if source.is_dir():
        yield source
        return
    if not source.is_file():
        raise ArtifactCommandError(f"source artifact does not exist: {source}")
    with tempfile.TemporaryDirectory(prefix="pyaegean-quantize-source-") as temporary:
        root = Path(temporary)
        try:
            with tarfile.open(source, "r:*") as archive:
                members = archive.getmembers()
                if not members or len(members) > _MAX_ARCHIVE_FILES:
                    raise ArtifactCommandError(
                        f"source archive must contain 1..{_MAX_ARCHIVE_FILES} flat files"
                    )
                names: set[str] = set()
                total_size = 0
                for member in members:
                    if (
                        not member.isfile()
                        or Path(member.name).name != member.name
                        or member.name in names
                        or member.size < 1
                        or member.size > _MAX_ARCHIVE_MEMBER_BYTES
                    ):
                        raise ArtifactCommandError(
                            f"unsafe or invalid source archive member: {member.name!r}"
                        )
                    names.add(member.name)
                    total_size += member.size
                    if total_size > _MAX_ARCHIVE_TOTAL_BYTES:
                        raise ArtifactCommandError(
                            "source archive exceeds the total uncompressed-size limit"
                        )
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ArtifactCommandError(
                            f"cannot read source archive member: {member.name!r}"
                        )
                    remaining = member.size
                    with (root / member.name).open("xb") as target:
                        while remaining:
                            chunk = stream.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise ArtifactCommandError(
                                    f"source archive member size differs for {member.name!r}"
                                )
                            target.write(chunk)
                            remaining -= len(chunk)
        except (OSError, tarfile.TarError) as exc:
            raise ArtifactCommandError(f"cannot unpack source artifact: {exc}") from exc
        yield root


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", type=Path, help="qualified fp32 artifact directory or archive")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "out" / "quantize")
    parser.add_argument(
        "--model-id",
        required=True,
        help="new optimized candidate identity; cannot reuse grc-joint-v3",
    )
    add_qualification_arguments(parser, require_reference_operational=True)
    return parser


def _artifact_metadata(source: Path) -> dict[str, Any]:
    try:
        raw = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactCommandError(f"invalid source manifest: {exc}") from exc
    if not isinstance(raw, dict):
        raise ArtifactCommandError("source manifest must be a JSON object")
    allowed = ("model_name", "model_revision", "epochs", "license", "training_receipt_sha256")
    return validate_artifact_metadata({field: raw[field] for field in allowed if field in raw})


def _convert_model(source: Path, intermediate: Path, target: Path) -> None:
    try:
        import onnx
        from onnxconverter_common import float16
        from onnxruntime.quantization.matmul_nbits_quantizer import MatMulNBitsQuantizer
    except ImportError as exc:
        raise ArtifactCommandError(
            "quantization requires the A20 conversion environment with onnx, "
            "onnxconverter-common, and onnxruntime installed"
        ) from exc

    quantizer = MatMulNBitsQuantizer(
        str(source / "model.onnx"),
        bits=8,
        block_size=128,
        is_symmetric=True,
    )
    quantizer.process()
    try:
        quantizer.model.save_model_to_file(str(intermediate), use_external_data_format=False)
    except Exception:
        onnx.save(getattr(quantizer.model, "model", quantizer.model), str(intermediate))
    optimized = float16.convert_float_to_float16(
        onnx.load(str(intermediate)), keep_io_types=True
    )
    onnx.save(optimized, str(target))


def _verify_reference_artifact(source: Path, evidence_path: Path) -> None:
    try:
        evidence = load_operational_evidence(evidence_path)
        record = artifact_record(source)
    except (QualificationError, ArtifactRuntimeError) as exc:
        raise ArtifactCommandError(f"invalid optimization reference artifact: {exc}") from exc
    if record != evidence["artifact"]:
        raise ArtifactCommandError(
            "source artifact differs from --reference-operational evidence"
        )


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.model_id in {"grc-joint", "grc-joint-v3"}:
        parser.error("--model-id must be a new identity, not grc-joint or grc-joint-v3")
    if not args.model_id or Path(args.model_id).name != args.model_id:
        parser.error("--model-id must be one non-empty path-safe component")
    try:
        validate_qualification_paths(args)
        staging_root, artifact = staging_artifact(args.out, args.model_id)
        evidence = qualification_output(args.out, args.model_id, "optimization")
        with _source_directory(args.src) as source:
            bundle = ModelBundleManifest.load(source)
            _verify_reference_artifact(source, args.reference_operational)
            metadata = bundle.to_dict()
            artifact_metadata = _artifact_metadata(source)
            copy_runtime_sidecars(source, artifact)

            intermediate = staging_root / "weights-int8.onnx"
            _convert_model(source, intermediate, artifact / "model.onnx")
            intermediate.unlink(missing_ok=True)
            write_schema1_manifest(
                artifact,
                model_id=args.model_id,
                metadata=metadata,
                artifact_metadata=artifact_metadata,
                variant="int8-weight+fp16",
            )

        qualification_summary = run_qualification(
            args=args,
            artifact_dir=artifact,
            profile="optimization",
            output_dir=evidence,
        )
        final = args.out / args.model_id
        promote_artifact(staging_root, artifact, final)
        archive = args.out / f"{args.model_id}.tar.gz"
        archive_artifact(final, archive)
        result = {
            "model_id": args.model_id,
            "variant": "int8-weight+fp16",
            "source_model_id": bundle.model_id,
            "artifact": str(final),
            "archive": {
                "path": str(archive),
                "bytes": archive.stat().st_size,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            },
            "qualification": qualification_summary,
        }
        report_path = args.out / f"{args.model_id}-optimization-report.json"
        report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    except (
        ArtifactCommandError,
        ModelBundleError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
