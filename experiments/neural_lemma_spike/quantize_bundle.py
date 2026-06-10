"""Quantize the exported fp32 ONNX seq2seq to int8 and assemble the shippable bundle.

The export notebook produces fp32 ONNX — correct but ~960 MB and ~375 ms/form on CPU.
Per-channel int8 dynamic quantization cuts that to ~232 MB and ~123 ms/form with **no
measured quality loss** (generate==lookup held at 17/20, the three diffs being proper-noun
case that the hybrid's lookup answers anyway). Per-channel matters: per-tensor int8 is what
collapsed the earlier edit-tree classifier.

Quantization-time deps only (not package deps): onnxruntime, onnx, sympy.

    python quantize_bundle.py <fp32_dir_or_tar.gz> [out=grc-lemma-neural.tar.gz]

The input holds encoder_model.onnx, decoder_model.onnx, tokenizer.json, lookup.json.gz (the
export notebook's fp32 bundle). Emits the int8 tar.gz (files at the archive root) + its sha256
to pin in aegean.data._REMOTE.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import shutil
import sys
import tarfile
import tempfile

from onnxruntime.quantization import QuantType, quantize_dynamic

_ONNX = ("encoder_model.onnx", "decoder_model.onnx")
_COPY = ("tokenizer.json", "lookup.json.gz")


def main() -> None:
    arg = pathlib.Path(sys.argv[1])
    out_tar = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "grc-lemma-neural.tar.gz")
    work = pathlib.Path(tempfile.mkdtemp())

    if arg.is_dir():
        src = arg
    else:
        src = work / "fp32"
        with tarfile.open(arg) as tf:
            tf.extractall(src)

    bundle = work / "int8"
    bundle.mkdir(parents=True, exist_ok=True)
    for fn in _ONNX:
        quantize_dynamic(str(src / fn), str(bundle / fn),
                         weight_type=QuantType.QInt8, per_channel=True)
        print(f"{fn}: {(bundle / fn).stat().st_size // 1024 // 1024} MB")
    for fn in _COPY:
        shutil.copy(src / fn, bundle / fn)

    with tarfile.open(out_tar, "w:gz") as tf:
        for fn in sorted(os.listdir(bundle)):
            tf.add(bundle / fn, arcname=fn)  # arcname=fn -> files at the archive root
    sha = hashlib.sha256(out_tar.read_bytes()).hexdigest()
    print(f"{out_tar}  {out_tar.stat().st_size // 1024 // 1024} MB  sha256={sha}")


if __name__ == "__main__":
    main()
