"""Quantize the shipped fp32 grc-joint ONNX to the int8-weight + fp16 artifact (lossless, ~3x smaller).

Why this recipe: full int8 (with quantized activations) collapses the GreBerta encoder -- its
activation outliers can't be quantized (every dynamic/static int8 recipe drops UPOS 97 -> ~16-32,
LAS 86 -> ~1-13). The fix is to never quantize activations: weight-only int8 on the MatMul nodes
(the encoder/attention/FFN bulk) via MatMulNBits, plus fp16 on everything else -- crucially the
~160 MB word-embedding table (60% of the model), which weight-only quantization doesn't touch. This
is lossless on UD Perseus test (UPOS/UFeats/lemma identical to 2 dp; UAS/LAS within +/-0.02) and
cuts model.onnx from 556 MB to 182 MB (tar.gz 518 -> 173 MB).

It is a post-hoc transform of the PUBLIC fp32 asset -- no training checkpoint needed. Runs on CPU.

    python training/quantize_grc_joint.py <fp32_dir | grc-joint.tar.gz> [--out training/out/quantize]

Quantization-time deps only (not package deps): onnxruntime, onnx, onnx_ir, onnxconverter_common.
Emits grc-joint.tar.gz + its sha256 to pin in aegean.data._REMOTE.

NOTE: the 8-bit MatMulNBits CPU kernel needs a recent onnxruntime; bump the [neural] extra's floor
to the version this artifact is validated against (see the floor probe in the cut notes).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
from pathlib import Path

import onnx
from onnxconverter_common import float16
from onnxruntime.quantization.matmul_nbits_quantizer import MatMulNBitsQuantizer

_SIDECARS = ("tokenizer.json", "labels.json", "lemma-scripts.json", "lemma-lookup.json")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", help="the fp32 artifact directory, or grc-joint.tar.gz")
    ap.add_argument("--out", default=str(Path(__file__).parent / "out" / "quantize"))
    args = ap.parse_args()

    work = Path(tempfile.mkdtemp())
    src = Path(args.src)
    if src.is_dir():
        srcdir = src
    else:
        srcdir = work / "fp32"
        with tarfile.open(src) as tf:
            tf.extractall(srcdir)

    out = Path(args.out)
    art = out / "grc-joint"
    art.mkdir(parents=True, exist_ok=True)
    for f in _SIDECARS:
        shutil.copy(srcdir / f, art / f)

    # 1. weight-only int8 on the MatMul nodes (activations stay fp32 -> no encoder collapse).
    tmp = work / "w8.onnx"
    q = MatMulNBitsQuantizer(str(srcdir / "model.onnx"), bits=8, block_size=128, is_symmetric=True)
    q.process()
    try:
        q.model.save_model_to_file(str(tmp), use_external_data_format=False)
    except Exception:
        onnx.save(getattr(q.model, "model", q.model), str(tmp))

    # 2. fp16 everything else -- the ~160 MB embedding table that weight-only doesn't reach.
    m16 = float16.convert_float_to_float16(onnx.load(str(tmp)), keep_io_types=True)
    onnx.save(m16, str(art / "model.onnx"))
    print(f"quantized model.onnx = {(art/'model.onnx').stat().st_size/1e6:.0f} MB", flush=True)

    manifest = {
        "name": "grc-joint",
        "variant": "int8-weight+fp16",
        "model_name": "bowphs/GreBerta",
        "quantization": "weight-only int8 (MatMulNBits, block 128, symmetric) + fp16 elsewhere",
        "license": "CC BY-SA 4.0 — derived from AGDT (CC BY-SA 3.0), "
                   "Gorman (CC BY-SA 4.0), Pedalion (CC BY-SA 4.0)",
        "files": {},
    }
    for f in sorted(art.iterdir()):
        manifest["files"][f.name] = {  # type: ignore[index]
            "bytes": f.stat().st_size,
            "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
        }
    (art / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    tar = out / "grc-joint.tar.gz"
    with tarfile.open(tar, "w:gz") as t:
        for f in sorted(art.iterdir()):
            t.add(f, arcname=f.name)  # flat: files at the archive root
    sha = hashlib.sha256(tar.read_bytes()).hexdigest()
    print(f"\nrelease asset: {tar}  ({tar.stat().st_size/1e6:.0f} MB)\nsha256: {sha}\n"
          f"Pin this sha256 + the release URL in aegean/data/__init__.py ('grc-joint').")


if __name__ == "__main__":
    main()
