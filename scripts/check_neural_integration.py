#!/usr/bin/env python3
"""Run bounded, required CPU neural checks; fetch the pinned model only with --provision.

Install ``.[dev,neural]`` first. ``PYAEGEAN_CACHE`` selects the cache base.
This runner provisions only the default neural model, never evaluation corpora.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from collections.abc import Sequence


ROOT = Path(__file__).resolve().parents[1]
TEST_FILE = ROOT / "tests" / "test_neural_integration.py"


def _prepare_model(*, provision: bool) -> None:
    from aegean import data
    from aegean.greek import joint

    joint._require_neural_extra()
    selected = joint._resolve_neural_variant("default")
    assert selected.dataset is not None
    asset = data.versions()["fetched"][selected.dataset]
    if not asset["sha256_enforced"] or asset["sha256"] != selected.asset_sha256:
        raise RuntimeError("neural checks require the default model's enforced registry pin")
    if provision:
        data.fetch(selected.dataset)
    else:
        spec = data._REMOTE[selected.dataset]
        if not data.is_downloaded(spec, data.cache_dir()):
            raise RuntimeError("neural model is not cached; rerun with --provision")


def _pytest_command() -> list[str]:
    return [
        sys.executable,
        "-m", "pytest",
        "-o", "addopts=",
        "-q",
        "-m", "neural_integration",
        "--strict-markers",
        "--require-neural-integration",
        str(TEST_FILE),
    ]


def _cpu_environment() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    env.update({
        "PYAEGEAN_ORT_PROVIDERS": "CPUExecutionProvider",
        "CUDA_VISIBLE_DEVICES": "",
        "TOKENIZERS_PARALLELISM": "false",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "PYTHONUTF8": "1",
    })
    return env


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provision", action="store_true", help="fetch the SHA-pinned default model before testing"
    )
    args = parser.parse_args(argv)
    try:
        _prepare_model(provision=args.provision)
    except Exception as exc:
        print(f"required neural integration setup failed: {exc}", file=sys.stderr)
        return 1
    try:
        result = subprocess.run(_pytest_command(), cwd=ROOT, env=_cpu_environment(), timeout=900)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"required neural integration runner failed: {exc}", file=sys.stderr)
        return 1
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
