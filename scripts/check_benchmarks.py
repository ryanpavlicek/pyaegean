"""Re-measure the drift-prone benchmark rows against the published-claims registry.

The offline (pure-Python) stack changes with the code, so its published numbers can drift
silently while the docs stay green: this script re-runs those rows and fails if any cell
moved from ``training/results/published-claims.json``. It complements
``tests/test_benchmark_claims.py`` (which pins docs == registry, offline and per-PR): the
test catches a doc/registry divergence instantly; this catches a registry/reality
divergence. Run it weekly (CI) and at the pre-cut gate whenever the offline tagger,
lemmatizer, parser, treebank data, or scoring path changed.

The neural rows are deliberately NOT re-measured here: they are pinned by an immutable
sha256 release asset (a new model is a new asset name), so they cannot drift without an
explicit asset change, and re-running them needs a ~173 MB fetch.

Needs the network on first run (UD folds, the agdt-derived backends, the NT corpus fetch
to cache). Exit 0 = every cell reproduces; exit 1 = drift, with a per-cell report.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Sequence

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOLERANCE = 0.005  # published cells are 2-decimal; anything past rounding noise is drift


def _parse_args(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog=(
            "Running with no options or --measure performs the network-backed offline "
            "benchmark remeasurement."
        ),
    )
    parser.add_argument(
        "--measure",
        action="store_true",
        help="explicitly request the remeasurement (also the default action)",
    )
    parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    _parse_args(argv)
    claims = json.loads(
        (ROOT / "training/results/published-claims.json").read_text(encoding="utf-8")
    )
    failures: list[str] = []

    from aegean import greek

    # ── the offline UD/PROIEL baseline table ─────────────────────────────────
    greek.use_treebank()
    greek.use_tagger()
    greek.use_lemmatizer()
    greek.use_parser()
    for fold_key, treebank in (("perseus_test", "perseus"), ("proiel_test", "proiel")):
        expected = claims["offline_baseline_ud"][fold_key]
        result = greek.evaluate_on_ud(treebank, "test")
        for metric, want in expected.items():
            got = round(result[metric] * 100, 2)
            status = "ok" if abs(got - want) <= TOLERANCE else "DRIFT"
            print(f"{status:5}  offline {treebank} test {metric}: measured {got} vs published {want}")
            if status == "DRIFT":
                failures.append(f"offline {treebank} {metric}: {want} -> {got}")

    # ── the offline lemmatizer's NT number (the wiki/Limitations ~66% claim) ──
    # This row's protocol is NO backends active (the bare seed + rule layer), so the
    # backends the baseline table just activated must be switched off first — with them
    # left on, lemmatize() answers from the treebank and measures the wrong protocol.
    from aegean.greek.lemmatizer import disable_lemmatizer
    from aegean.greek.syntax import disable_parser
    from aegean.greek.tagger import disable_tagger
    from aegean.greek.treebank import disable_treebank

    disable_treebank()
    disable_tagger()
    disable_lemmatizer()
    disable_parser()

    from aegean.greek import morphology
    from aegean.greek.nt_eval import evaluate_on_nt

    def offline_tag(forms: list[str]) -> list[tuple[str, str]]:
        return [(greek.lemmatize(f), morphology.best_pos(f) or "X") for f in forms]

    nt = evaluate_on_nt(offline_tag)
    want = claims["offline_nt_lemma"]["lemma"]
    got = round(nt["lemma"] * 100, 2)
    status = "ok" if abs(got - want) <= TOLERANCE else "DRIFT"
    print(f"{status:5}  offline NT lemma: measured {got} vs published {want} (n={int(nt['n'])})")
    if status == "DRIFT":
        failures.append(f"offline NT lemma: {want} -> {got}")

    if failures:
        print(
            "\nFAIL  published numbers no longer reproduce — re-measure, then update "
            "training/results/published-claims.json AND every doc cell in the same commit:"
        )
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK  every re-measured cell matches the published registry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
