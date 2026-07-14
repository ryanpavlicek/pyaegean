"""Stage E: export the trained joint checkpoint to the shipped ONNX artifact.

Exports the JointParser (encoder + 10 tagging heads + biaffine arc/relation + lemma
head) to a single ONNX graph with dynamic axes, quantizes it to int8, and applies the
**quantization gate**: both variants are evaluated on dev THROUGH the package's own
inference module (`aegean.greek.joint._JointModel`) — the exact code path users run —
and int8 ships only if it costs ≤ --gate points (default 0.3) on every headline metric
(UPOS / LAS / lemma) versus the fp32 export; otherwise the fp32 graph ships.

Output under --out:
    <model-id>/               the artifact directory (model.onnx + tokenizer.json +
                              labels.json + lemma-scripts.json + lemma-lookup.json +
                              manifest.json)
    <model-id>.tar.gz         the release asset, registered by URL + SHA-256 under a
                              new data key
    gate-report.json          dev metrics: torch vs onnx-fp32 vs onnx-int8

Usage:  python training/export_onnx.py --checkpoint training/out/full/model \
            --model-id grc-joint-v4-dev1
        (needs the Stage D+ data dir for the dev fold: --data-dir training/data)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import tarfile
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent))
from train_full import load_jsonl  # noqa: E402
from train_parser import TAG_HEADS, JointParser  # noqa: E402

from aegean.greek.joint import _JointModel  # noqa: E402
from aegean.greek import neural_preprocessing as prep  # noqa: E402
from aegean.greek.neural_contract import (  # noqa: E402
    ModelBundleError,
    prepare_schema1_artifact_dir,
    validate_artifact_metadata,
    validate_joint_checkpoint_sidecars,
    write_schema1_manifest,
)

_DEFAULT_MODEL_LICENSE = (
    "CC BY-SA 4.0; derived from AGDT (CC BY-SA 3.0), "
    "Gorman (CC BY-SA 4.0), and Pedalion (CC BY-SA 4.0)"
)


class _ExportWrapper(torch.nn.Module):
    """Flatten JointParser's outputs into named tensors for ONNX export."""

    def __init__(self, model: JointParser) -> None:
        super().__init__()
        self.model = model

    def forward(self, input_ids, attention_mask, word_pos):  # noqa: ANN001
        tag_logits, arc, rel, lem = self.model(input_ids, attention_mask, word_pos)
        return (tag_logits["upos"], *(tag_logits[f"x{i}"] for i in range(9)), arc, rel, lem)


def _evaluate_dir(model_dir: Path, dev_rows: list[dict], limit: int) -> dict[str, float]:
    """Dev UPOS/LAS/lemma through the package's own inference path."""
    jm = _JointModel(model_dir)
    n = upos_ok = arcs = las = n_lem = lem_ok = 0
    for row in dev_rows[:limit]:
        ana = jm.analyze(row["tokens"])
        for i in range(len(row["tokens"])):
            n += 1
            upos_ok += int(ana.upos[i] == row["upos"][i])
            n_lem += 1
            lem_ok += int(ana.lemma[i] == row["lemma"][i])
            arcs += 1
            las += int(ana.head[i] == row["head"][i] and ana.deprel[i] == row["deprel"][i])
    return {"upos": upos_ok / n, "las": las / arcs, "lemma": lem_ok / n_lem, "n_tokens": n}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checkpoint", required=True, help="the trained model/ directory")
    ap.add_argument("--data-dir", default=str(Path(__file__).parent / "data"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "out" / "export"))
    ap.add_argument("--gate", type=float, default=0.3, help="max int8 drop, points")
    ap.add_argument("--gate-sentences", type=int, default=300,
                    help="dev sentences for the gate evaluation")
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument(
        "--model-id",
        required=True,
        help="explicit non-v3 candidate identity (for example grc-joint-v4-dev1)",
    )
    args = ap.parse_args()
    if args.model_id in {"grc-joint", "grc-joint-v3"}:
        ap.error("--model-id must be a new identity, not grc-joint or grc-joint-v3")
    if not math.isfinite(args.gate) or not 0 <= args.gate <= 100:
        ap.error("--gate must be a finite number from 0 through 100")
    if args.gate_sentences < 1:
        ap.error("--gate-sentences must be a positive integer")
    if args.opset < 1:
        ap.error("--opset must be a positive integer")

    ckpt = Path(args.checkpoint)
    out = Path(args.out)
    try:
        required = (
            "joint_full.pt",
            "labels.json",
            "lemma-lookup.json",
            "lemma-scripts.json",
            "tokenizer.json",
        )
        missing = [name for name in required if not (ckpt / name).is_file()]
        if missing:
            raise ValueError(f"checkpoint is missing required files: {missing}")
        spec = json.loads((ckpt / "labels.json").read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise ValueError("checkpoint labels.json must be a JSON object")
        checkpoint_spec = prep.validate_joint_checkpoint_spec(spec)
        export_metadata = prep.load_checkpoint_metadata(ckpt, spec)
        validate_joint_checkpoint_sidecars(ckpt, export_metadata)
        artifact_metadata: dict[str, object] = {
            "model_name": checkpoint_spec.model_name,
            "license": spec.get("license", _DEFAULT_MODEL_LICENSE),
        }
        for field in ("model_revision", "epochs", "training_receipt_sha256"):
            if field in spec:
                artifact_metadata[field] = spec[field]
        artifact_metadata = validate_artifact_metadata(artifact_metadata)
        art = prepare_schema1_artifact_dir(out, args.model_id)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, ModelBundleError) as exc:
        ap.error(str(exc))
    maps = checkpoint_spec.maps
    model = JointParser(checkpoint_spec.model_name, {h: len(maps[h]) for h in TAG_HEADS},
                        n_rels=len(maps["deprel"]), n_scripts=checkpoint_spec.n_scripts)
    model.load_state_dict(torch.load(ckpt / "joint_full.pt", map_location="cpu"))
    model.eval()

    # --- export (dynamic batch/sequence/word axes) -----------------------------------
    wrapper = _ExportWrapper(model)
    ex_ids = torch.ones(1, 12, dtype=torch.long)
    ex_mask = torch.ones(1, 12, dtype=torch.long)
    ex_pos = torch.tensor([[1, 3, 5, 7]], dtype=torch.long)
    out_names = ["upos", *(f"x{i}" for i in range(9)), "arc", "rel", "lemma"]
    dyn = {
        "input_ids": {0: "batch", 1: "subwords"},
        "attention_mask": {0: "batch", 1: "subwords"},
        "word_pos": {0: "batch", 1: "words"},
        **{head: {0: "batch", 1: "subwords"} for head in TAG_HEADS},
        "arc": {0: "batch", 1: "words", 2: "candidate_heads"},
        "rel": {0: "batch", 2: "words", 3: "candidate_heads"},
        "lemma": {0: "batch", 1: "words"},
    }
    fp32_path = art / "model.onnx"
    torch.onnx.export(
        wrapper, (ex_ids, ex_mask, ex_pos), str(fp32_path),
        input_names=["input_ids", "attention_mask", "word_pos"],
        output_names=out_names, dynamic_axes=dyn, opset_version=args.opset,
        dynamo=False,  # the legacy exporter: dynamic_axes API, no onnxscript needed
    )
    print(f"exported fp32: {fp32_path.stat().st_size / 1e6:.0f} MB", flush=True)

    # --- the artifact's sidecars (the package's _JointModel reads these) -------------
    shutil.copy(ckpt / "labels.json", art / "labels.json")
    shutil.copy(ckpt / "lemma-scripts.json", art / "lemma-scripts.json")
    shutil.copy(ckpt / "lemma-lookup.json", art / "lemma-lookup.json")
    shutil.copy(ckpt / "tokenizer.json", art / "tokenizer.json")

    # --- gate: torch-free dev evaluation of fp32 vs int8 through the package ---------
    dev_rows = load_jsonl(Path(args.data_dir) / "full-dev.jsonl")
    report: dict[str, object] = {"gate_points": args.gate,
                                 "gate_sentences": args.gate_sentences}
    # The package-path evaluation constructs _JointModel, which validates this
    # manifest before touching ONNX Runtime.  Write it before *any* evaluation.
    write_schema1_manifest(
        art,
        model_id=args.model_id,
        metadata=export_metadata,
        artifact_metadata=artifact_metadata,
        variant="fp32",
    )
    t0 = time.time()
    report["fp32"] = _evaluate_dir(art, dev_rows, args.gate_sentences)
    print(f"fp32 dev: {report['fp32']}  ({time.time()-t0:.0f}s)", flush=True)

    from onnxruntime.quantization import QuantType, quantize_dynamic

    int8_path = art / "model.int8.onnx"
    quantize_dynamic(str(fp32_path), str(int8_path), weight_type=QuantType.QInt8)
    fp32_bytes = fp32_path.stat().st_size
    # evaluate int8 by swapping it into model.onnx position temporarily
    fp32_keep = art / "model.fp32.onnx"
    fp32_path.rename(fp32_keep)
    int8_path.rename(fp32_path)
    write_schema1_manifest(
        art,
        model_id=args.model_id,
        metadata=export_metadata,
        artifact_metadata=artifact_metadata,
        variant="int8",
    )
    t0 = time.time()
    report["int8"] = _evaluate_dir(art, dev_rows, args.gate_sentences)
    print(f"int8 dev: {report['int8']}  ({time.time()-t0:.0f}s)", flush=True)

    drops = {k: (report["fp32"][k] - report["int8"][k]) * 100  # type: ignore[index]
             for k in ("upos", "las", "lemma")}
    report["drops_points"] = drops
    ship_int8 = all(d <= args.gate for d in drops.values())
    shipped_variant = "int8" if ship_int8 else "fp32"
    report["shipped"] = shipped_variant
    if ship_int8:
        fp32_keep.unlink()  # model.onnx is already the int8 graph
    else:
        fp32_path.unlink()
        fp32_keep.rename(fp32_path)
    # This final rewrite is also required after the fp32 restoration above: the
    # model.onnx digest is part of the manifest consumed by runtime activation.
    write_schema1_manifest(
        art,
        model_id=args.model_id,
        metadata=export_metadata,
        artifact_metadata=artifact_metadata,
        variant=shipped_variant,
    )
    print(f"gate: drops {drops} → shipping {report['shipped']}", flush=True)

    # --- manifest + tarball -----------------------------------------------------------
    tar_path = out / f"{args.model_id}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for f in sorted(art.iterdir()):  # pack flat: files at the archive root
            tar.add(f, arcname=f.name)
    sha = hashlib.sha256(tar_path.read_bytes()).hexdigest()
    report["tar"] = {"path": str(tar_path), "bytes": tar_path.stat().st_size,
                     "sha256": sha, "fp32_onnx_bytes": fp32_bytes}
    (out / "gate-report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    print(f"\nrelease asset: {tar_path}  ({tar_path.stat().st_size/1e6:.0f} MB)\n"
          f"sha256: {sha}\n"
          "Register this SHA-256 and release URL under a new immutable data key.")


if __name__ == "__main__":
    main()
