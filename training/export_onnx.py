"""Export a trained Greek joint checkpoint to a qualified fp32 ONNX artifact.

The command writes into a private staging directory, exports the graph, validates
its schema-1 bundle, then runs the complete A20 development, parity, provider,
latency, memory, and size gate in an isolated process.  Only a passing artifact is
promoted to ``<out>/<model-id>`` and archived.  Optimization is a separate command
(``quantize_grc_joint.py``) with its own gate profile.

Example::

    python training/export_onnx.py \
      --checkpoint training/out/full/model \
      --model-id grc-joint-v4-candidate \
      --perseus-dev-source training/data/grc_perseus-ud-dev.conllu \
      --papygreek-tagging-source training/data/papygreek-dev-tagging.conllu \
      --papygreek-parse-source training/data/papygreek-dev-parse.conllu \
      --reference-report training/out/RUN/development-report.json \
      --reference-predictions training/out/RUN/predictions-<sha>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from artifact_command import (  # noqa: E402
    ArtifactCommandError,
    add_qualification_arguments,
    archive_artifact,
    promote_artifact,
    qualification_output,
    run_qualification,
    staging_artifact,
    validate_qualification_paths,
)
from aegean.greek import neural_preprocessing as prep  # noqa: E402
from aegean.greek.neural_contract import (  # noqa: E402
    ModelBundleError,
    validate_artifact_metadata,
    validate_joint_checkpoint_sidecars,
    write_schema1_manifest,
)

_DEFAULT_MODEL_LICENSE = (
    "CC BY-SA 4.0; derived from AGDT (CC BY-SA 3.0), "
    "Gorman (CC BY-SA 4.0), and Pedalion (CC BY-SA 4.0)"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, type=Path, help="trained model directory")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "out" / "export")
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument(
        "--model-id",
        required=True,
        help="explicit non-v3 candidate identity (for example grc-joint-v4-candidate)",
    )
    add_qualification_arguments(parser, require_reference_operational=False)
    return parser


def _export_graph(
    *,
    checkpoint: Path,
    artifact: Path,
    checkpoint_spec: object,
    opset: int,
) -> None:
    try:
        import torch
        from train_parser import TAG_HEADS, JointParser
    except ImportError as exc:
        raise ArtifactCommandError(
            "export requires the A20 training environment with torch and transformers installed"
        ) from exc

    class ExportWrapper(torch.nn.Module):
        """Flatten JointParser outputs into stable named ONNX tensors."""

        def __init__(self, model: object) -> None:
            super().__init__()
            self.model = model

        def forward(self, input_ids, attention_mask, word_pos):  # noqa: ANN001
            tag_logits, arc, rel, lem = self.model(input_ids, attention_mask, word_pos)
            return (
                tag_logits["upos"],
                *(tag_logits[f"x{i}"] for i in range(9)),
                arc,
                rel,
                lem,
            )

    model = JointParser(
        checkpoint_spec.model_name,
        {head: len(checkpoint_spec.maps[head]) for head in TAG_HEADS},
        n_rels=len(checkpoint_spec.maps["deprel"]),
        n_scripts=checkpoint_spec.n_scripts,
    )
    model.load_state_dict(torch.load(checkpoint / "joint_full.pt", map_location="cpu"))
    model.eval()

    wrapper = ExportWrapper(model)
    example_ids = torch.ones(1, 12, dtype=torch.long)
    example_mask = torch.ones(1, 12, dtype=torch.long)
    example_positions = torch.tensor([[1, 3, 5, 7]], dtype=torch.long)
    output_names = ["upos", *(f"x{i}" for i in range(9)), "arc", "rel", "lemma"]
    dynamic_axes = {
        "input_ids": {0: "batch", 1: "subwords"},
        "attention_mask": {0: "batch", 1: "subwords"},
        "word_pos": {0: "batch", 1: "words"},
        **{head: {0: "batch", 1: "subwords"} for head in TAG_HEADS},
        "arc": {0: "batch", 1: "words", 2: "candidate_heads"},
        "rel": {0: "batch", 2: "words", 3: "candidate_heads"},
        "lemma": {0: "batch", 1: "words"},
    }
    torch.onnx.export(
        wrapper,
        (example_ids, example_mask, example_positions),
        str(artifact / "model.onnx"),
        input_names=["input_ids", "attention_mask", "word_pos"],
        output_names=output_names,
        dynamic_axes=dynamic_axes,
        opset_version=opset,
        dynamo=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.model_id in {"grc-joint", "grc-joint-v3"}:
        parser.error("--model-id must be a new identity, not grc-joint or grc-joint-v3")
    if not args.model_id or Path(args.model_id).name != args.model_id:
        parser.error("--model-id must be one non-empty path-safe component")
    if args.opset < 1:
        parser.error("--opset must be a positive integer")
    try:
        validate_qualification_paths(args)
        required = (
            "joint_full.pt",
            "labels.json",
            "lemma-lookup.json",
            "lemma-scripts.json",
            "tokenizer.json",
        )
        missing = [name for name in required if not (args.checkpoint / name).is_file()]
        if missing:
            raise ArtifactCommandError(f"checkpoint is missing required files: {missing}")
        spec = json.loads((args.checkpoint / "labels.json").read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise ArtifactCommandError("checkpoint labels.json must be a JSON object")
        checkpoint_spec = prep.validate_joint_checkpoint_spec(spec)
        export_metadata = prep.load_checkpoint_metadata(args.checkpoint, spec)
        validate_joint_checkpoint_sidecars(args.checkpoint, export_metadata)
        artifact_metadata: dict[str, object] = {
            "model_name": checkpoint_spec.model_name,
            "license": spec.get("license", _DEFAULT_MODEL_LICENSE),
        }
        for field in ("model_revision", "epochs", "training_receipt_sha256"):
            if field in spec:
                artifact_metadata[field] = spec[field]
        artifact_metadata = validate_artifact_metadata(artifact_metadata)
        staging_root, artifact = staging_artifact(args.out, args.model_id)
        evidence = qualification_output(args.out, args.model_id, "export")
    except (
        ArtifactCommandError,
        ModelBundleError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        parser.error(str(exc))

    try:
        _export_graph(
            checkpoint=args.checkpoint,
            artifact=artifact,
            checkpoint_spec=checkpoint_spec,
            opset=args.opset,
        )
        for name in ("labels.json", "lemma-scripts.json", "lemma-lookup.json", "tokenizer.json"):
            shutil.copy2(args.checkpoint / name, artifact / name)
        write_schema1_manifest(
            artifact,
            model_id=args.model_id,
            metadata=export_metadata,
            artifact_metadata=artifact_metadata,
            variant="fp32",
        )
        qualification_summary = run_qualification(
            args=args,
            artifact_dir=artifact,
            profile="export",
            output_dir=evidence,
        )
        final = args.out / args.model_id
        promote_artifact(staging_root, artifact, final)
        archive = args.out / f"{args.model_id}.tar.gz"
        archive_artifact(final, archive)
        result = {
            "model_id": args.model_id,
            "variant": "fp32",
            "artifact": str(final),
            "archive": {
                "path": str(archive),
                "bytes": archive.stat().st_size,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            },
            "qualification": qualification_summary,
        }
        report_path = args.out / f"{args.model_id}-export-report.json"
        report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    except Exception as exc:
        if isinstance(exc, (ArtifactCommandError, ModelBundleError, OSError, ValueError)):
            parser.error(str(exc))
        raise
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
