"""Footprint guard for pyaegean — replaces the old "<3 MB wheel" check.

That byte cap was theater: the wheel is ~170 KB (the package ships only code + tiny JSON),
so it could never fail, while it said nothing about the invariants that actually define the
niche. This guards those instead:

  1. import-clean  `import aegean` pulls in NO heavy third-party module.
  2. import-fast   cold `import aegean` (fastest of several subprocess runs, after one
     unmeasured warmup that absorbs .pyc compilation and OS file-cache effects) stays
     under a generous bound.
  3. nothing-heavy-bundled (with --wheel)  the wheel is code + JSON only — no binaries — with
     a soft accident tripwire that only catches a mistaken large-file commit, not a policy ceiling.

Usage:
  python scripts/check_footprint.py                 # checks 1+2 (run after a CORE-only install)
  python scripts/check_footprint.py --wheel dist/*.whl   # check 3
"""

from __future__ import annotations

import argparse
import glob
import subprocess
import sys
import zipfile

HEAVY = [
    "pandas", "numpy", "scipy", "lxml", "anthropic", "openai", "google",
    "torch", "onnxruntime", "tokenizers", "transformers", "geopandas", "shapely",
    "textual", "markdown_it",
]
# Stdlib modules Pyodide unvendors (must be loadPackage'd separately). `import aegean` must
# not pull these at import time, or the package fails to import in the browser demo. sqlite3
# is the one that bit us: a top-level `import sqlite3` in the opt-in cache made `import aegean`
# raise under Pyodide. It's always present in normal CPython, so this doubles as a regression
# sentinel — if `import aegean` starts importing it again, it shows up in sys.modules here.
# (ssl/urllib are already pulled by the fetch layer at init but stay off this list: the demo
# loads them via micropip before importing aegean, so they don't break it — see Limitations.)
STDLIB_OPTIONAL = ["sqlite3"]
# Generous: steady-state `import aegean` is ~300 ms; a real regression (one top-level
# pandas/numpy import) costs several hundred more and still trips this.
IMPORT_MS_BOUND = 500.0
WHEEL_SOFT_BYTES = 5 * 1024 * 1024
HEAVY_EXT = (".gz", ".so", ".pyd", ".dll", ".bin", ".onnx", ".npy", ".npz", ".pt", ".h5", ".parquet")


def check_import_clean() -> None:
    code = (
        "import sys, aegean\n"
        f"watch = {(HEAVY + STDLIB_OPTIONAL)!r}\n"
        "bad = [m for m in watch if any(k == m or k.startswith(m + '.') for k in sys.modules)]\n"
        "print('loaded on import: ' + (', '.join(bad) if bad else 'none'))\n"
        "sys.exit(1 if bad else 0)"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())
    if r.returncode != 0:
        raise SystemExit(
            "FAIL import-clean: `import aegean` loaded a heavy or non-portable-stdlib module "
            "(or errored)"
        )
    print("OK  import-clean")


def _import_ms() -> float:
    """One cold-subprocess `import aegean`, in milliseconds."""
    r = subprocess.run(
        [sys.executable, "-c",
         "import time; t = time.perf_counter(); import aegean; "
         "print((time.perf_counter() - t) * 1000)"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise SystemExit("FAIL import-fast: import errored\n" + r.stderr)
    return float(r.stdout.strip().splitlines()[-1])


def check_import_fast() -> None:
    # The very first import after an install pays one-off costs (.pyc compilation, a cold
    # OS file cache) that say nothing about import-time work in the code — a 645 ms
    # first-run median was observed against a ~290 ms steady state. Warm up once,
    # unmeasured, then gate on the *fastest* of five samples: machine load only ever adds
    # time, so the minimum tracks the code's real import cost (timeit's rationale), while
    # a genuine regression (say a top-level pandas import) raises even the minimum.
    _import_ms()
    samples = [_import_ms() for _ in range(5)]
    best = min(samples)
    print(f"cold import best {best:.0f} ms (bound {IMPORT_MS_BOUND:.0f}); samples {[round(s) for s in samples]}")
    if best > IMPORT_MS_BOUND:
        raise SystemExit(f"FAIL import-fast: {best:.0f} ms > {IMPORT_MS_BOUND:.0f} ms")
    print("OK  import-fast")


def check_wheel(pattern: str) -> None:
    matches = glob.glob(pattern)
    if not matches:
        raise SystemExit(f"FAIL: no wheel matching {pattern}")
    whl = matches[0]
    with zipfile.ZipFile(whl) as z:
        infos = z.infolist()
    heavy = [i.filename for i in infos if i.filename.lower().endswith(HEAVY_EXT)]
    total = sum(i.file_size for i in infos)
    print(f"wheel {whl}: {total // 1024} KB uncompressed, {len(infos)} files")
    if heavy:
        raise SystemExit("FAIL nothing-heavy-bundled — wheel contains binaries:\n  " + "\n  ".join(heavy))
    if total > WHEEL_SOFT_BYTES:
        raise SystemExit(f"FAIL: wheel {total // 1024} KB over the {WHEEL_SOFT_BYTES // 1024} KB accident tripwire")
    print("OK  nothing-heavy-bundled")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wheel", help="path or glob to a built wheel (runs check 3 only)")
    args = ap.parse_args()
    if args.wheel:
        check_wheel(args.wheel)
    else:
        check_import_clean()
        check_import_fast()


if __name__ == "__main__":
    main()
