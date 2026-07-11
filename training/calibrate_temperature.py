"""Fit + measure the joint model's confidence calibration on the UD Ancient Greek folds.

This is the recorded protocol behind the shipped `aegean.greek.calibrate.Calibration`: it
fits ONE scalar temperature per model head on the **UD Perseus dev fold** (never test),
measures the Expected Calibration Error before and after, and then runs a **one-shot,
report-only** ECE on the Perseus test fold (no fitting there) as the generalization check.
Everything is written, full-precision, to ``training/results/calibration-<date>.json``.

What is calibrated, per head, and against what target
-----------------------------------------------------
The confidence pyaegean surfaces is the **top-1 (max) softmax probability** of a head; a
temperature ``T`` rescales the logits (``softmax(z / T)``) to make that number honest —
i.e. so that among tokens the model reports at ~p confidence, ~p are actually correct. ``T``
is fitted to minimize the binary negative log-likelihood of the top-1 confidence against a
per-token correctness bit.

- **UPOS head**: correctness = the predicted (argmax) UPOS tag equals gold. The UPOS logits
  are only 15-wide, so they are materialized and fitted with the library
  ``aegean.greek.calibrate.fit_temperature`` (grid + golden-section refine).

- **lemma head — the design choice**: the model's lemma is *composed* (a train-only lookup,
  else the predicted edit script; see ``joint._compose_lemma``), so there is no single "gold
  edit-script id" to calibrate a raw script-classification against without reconstructing the
  training lookup — too deep, and not what a user reads. Instead we calibrate the **prob of
  the argmax edit-script** (the script head's top-1 softmax) against whether the **composed
  lemma matched gold** — the correctness a user actually cares about. So the lemma confidence
  is a calibrated *proxy*: "how sure is the model's lemma", measured on composed-lemma
  correctness, not on script-id correctness. Because the script head is 15k-wide (too large
  to materialize for a whole fold), its temperature is fitted on a geometric grid of the same
  binary-NLL objective, evaluated streaming during the single model pass (T=1.0 is a grid
  point, so ECE-before is exact); the fitted T is the grid minimizer.

Both heads' ECE is measured on the identical (top-1 confidence, correct) pairs used to fit,
so fit and evaluation are coherent.

Protocol notes: CPU, ``analyze``/``_run_batch`` with ``batch_size=32`` (the 0.33.0 batch
path is prediction-identical to sequential on this model; batching here only speeds the pass,
it does not enter a published number). The **dev fold** is used for FITTING; the **test fold**
is scored once, report-only. The fitted temperature is fold-specific literary prose (Perseus),
so the calibration carries a genre caveat.

Usage (run with ``python -u`` so the progress prints are not buffered):

    python -u training/calibrate_temperature.py [--limit N] [--dev-only] [--out PATH]

``--limit N`` fits/reports on the first N sentences of each fold (a fast does-it-move check);
``--dev-only`` skips the test-fold generalization pass.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aegean.data import fetch  # noqa: E402
from aegean.greek import calibrate  # noqa: E402
from aegean.greek.joint import _JointModel, _compose_lemma  # noqa: E402
from aegean.greek.ud import load_conllu, ud_path  # noqa: E402

_DATASET = "grc-joint"
_BATCH = 32
# A geometric grid for the streaming lemma-head fit; 1.0 is added so ECE-before is an exact
# column. Range covers the usual over-confidence regime (optimal T typically ~1.2-2.5).
_LEMMA_GRID = np.unique(np.concatenate([np.geomspace(0.5, 8.0, 40), [1.0]])).astype(np.float64)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _reliability_bins(probs: np.ndarray, correct: np.ndarray, n_bins: int = 15) -> list[dict]:
    """Per-bin (count, mean confidence, accuracy) reliability table for the evidence file."""
    p = np.asarray(probs, dtype=np.float64)
    y = np.asarray(correct, dtype=np.float64)
    bins = np.clip((p * n_bins).astype(int), 0, n_bins - 1)
    out = []
    for b in range(n_bins):
        m = bins == b
        cnt = int(m.sum())
        out.append({
            "bin": b,
            "lo": round(b / n_bins, 4),
            "hi": round((b + 1) / n_bins, 4),
            "count": cnt,
            "mean_confidence": (round(float(p[m].mean()), 6) if cnt else None),
            "accuracy": (round(float(y[m].mean()), 6) if cnt else None),
        })
    return out


def _collect(model: _JointModel, sentences, *, need_lemma_grid: bool, lemma_temp: float | None,
             tag: str) -> dict:
    """One pass over ``sentences`` (batched), gathering per-token calibration data.

    Returns arrays for the UPOS head (materialized 15-wide logits + correctness) and, for the
    lemma head, either the streaming grid confidences (fitting, ``need_lemma_grid=True``) or
    the top-1 confidence at a fixed ``lemma_temp`` (report-only test pass)."""
    upos_logits: list[np.ndarray] = []
    upos_correct: list[int] = []
    lemma_correct: list[int] = []
    lemma_conf_grid: list[np.ndarray] = []      # [n_tokens, n_grid] when need_lemma_grid
    lemma_conf_at_t: list[float] = []           # top-1 conf at lemma_temp (report pass)

    total = len(sentences)
    t0 = time.perf_counter()
    done = 0
    for start in range(0, total, _BATCH):
        chunk = sentences[start : start + _BATCH]
        batch_forms = [[_nfc(t.form) for t in s.tokens] for s in chunk]
        # skip empty sentences the way analyze_batch does; run the rest in one pass
        live = [(i, f) for i, f in enumerate(batch_forms) if f]
        if live:
            outs = model._run_batch([f for _i, f in live])
            for (li, forms), out in zip(live, outs):
                sent = chunk[li]
                word_pos = out["_word_pos"]
                kept = out["_kept"]
                for wi, w in enumerate(kept):
                    sp = word_pos[wi]
                    uz = np.asarray(out["upos"][0, sp], dtype=np.float64)  # (15,)
                    gold = sent.tokens[w]
                    pred_upos = model.inv["upos"][int(uz.argmax())]
                    upos_logits.append(uz)
                    upos_correct.append(int(pred_upos == gold.upos))

                    sz = np.asarray(out["lemma"][0, wi], dtype=np.float64)  # (n_scripts,)
                    script_id = int(sz.argmax())
                    composed, _resolved = _compose_lemma(forms[w], pred_upos, script_id, model)
                    lemma_correct.append(int(_nfc(composed) == _nfc(gold.lemma)))
                    d = (sz - sz.max()).astype(np.float64)
                    if need_lemma_grid:
                        # top-1 confidence at every grid temperature, streaming (no 15k-wide
                        # logit ever stored for the whole fold): conf(T) = 1 / sum_k exp(d_k/T)
                        sums = np.exp(d[:, None] / _LEMMA_GRID[None, :]).sum(axis=0)
                        lemma_conf_grid.append(1.0 / sums)
                    else:
                        assert lemma_temp is not None
                        lemma_conf_at_t.append(1.0 / float(np.exp(d / lemma_temp).sum()))
        done += len(chunk)
        if start // _BATCH % 10 == 0 or done >= total:
            rate = done / max(time.perf_counter() - t0, 1e-9)
            print(f"[{tag}] {done}/{total} sentences ({rate:.0f} sent/s)", flush=True)

    return {
        "upos_logits": np.array(upos_logits) if upos_logits else np.empty((0, 15)),
        "upos_correct": np.array(upos_correct),
        "lemma_correct": np.array(lemma_correct),
        "lemma_conf_grid": (np.array(lemma_conf_grid) if lemma_conf_grid else None),
        "lemma_conf_at_t": (np.array(lemma_conf_at_t) if lemma_conf_at_t else None),
        "n_tokens": len(upos_correct),
    }


def _fit_lemma_grid(conf_grid: np.ndarray, correct: np.ndarray) -> tuple[float, int]:
    """Grid minimizer of the binary NLL of the streaming lemma-head confidences."""
    eps = 1e-12
    y = correct.astype(np.float64)
    nlls = []
    for g in range(conf_grid.shape[1]):
        c = np.clip(conf_grid[:, g], eps, 1 - eps)
        nlls.append(float(-(y * np.log(c) + (1 - y) * np.log(1 - c)).mean()))
    best = int(np.argmin(nlls))
    return float(_LEMMA_GRID[best]), best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="fit/report on the first N sentences of each fold")
    ap.add_argument("--dev-only", action="store_true", help="skip the test-fold report pass")
    ap.add_argument("--out", default=None, help="evidence JSON path (default training/results/calibration-<date>.json)")
    args = ap.parse_args()

    today = date.today().isoformat()
    out_path = Path(args.out) if args.out else (
        Path(__file__).parent / "results" / f"calibration-{today}.json"
    )

    n_dev = "?" if args.limit is None else args.limit
    print("=" * 70, flush=True)
    print("joint-model confidence calibration — UD Ancient Greek (Perseus)", flush=True)
    print(f"  fit fold : dev  (fit temperature; {n_dev} sentences)", flush=True)
    print(f"  test fold: test (report-only ECE){' [skipped]' if args.dev_only else ''}", flush=True)
    print(f"  execution: CPU, batched (_run_batch, batch_size={_BATCH})", flush=True)
    print("  estimated runtime: ~4-8 minutes on CPU (dominated by the lemma-head grid pass)", flush=True)
    print("=" * 70, flush=True)

    model_dir = fetch(_DATASET)
    model = _JointModel(model_dir)
    print(f"model loaded from {model_dir} (providers: {model._sess.get_providers()})", flush=True)

    dev = load_conllu(ud_path("perseus", "dev"))
    if args.limit is not None:
        dev = dev[: args.limit]
    print(f"dev fold: {len(dev)} sentences, {sum(len(s.tokens) for s in dev)} tokens", flush=True)

    # --- FIT on dev ---------------------------------------------------------------
    dev_data = _collect(model, dev, need_lemma_grid=True, lemma_temp=None, tag="dev/fit")

    # UPOS: the library fitter on materialized 15-wide logits
    t_upos = calibrate.fit_temperature(dev_data["upos_logits"], dev_data["upos_correct"])
    upos_conf_before = calibrate.top1_confidence(dev_data["upos_logits"], 1.0)
    upos_conf_after = calibrate.top1_confidence(dev_data["upos_logits"], t_upos)
    upos_ece_before = calibrate.ece(upos_conf_before, dev_data["upos_correct"])
    upos_ece_after = calibrate.ece(upos_conf_after, dev_data["upos_correct"])

    # lemma: grid minimizer on the streaming composed-lemma-correctness objective
    conf_grid = dev_data["lemma_conf_grid"]
    i_one = int(np.argmin(np.abs(_LEMMA_GRID - 1.0)))
    t_lemma, best_g = _fit_lemma_grid(conf_grid, dev_data["lemma_correct"])
    lemma_ece_before = calibrate.ece(conf_grid[:, i_one], dev_data["lemma_correct"])
    lemma_ece_after = calibrate.ece(conf_grid[:, best_g], dev_data["lemma_correct"])

    print(f"\nUPOS : T={t_upos:.4f}  ECE {upos_ece_before:.4f} -> {upos_ece_after:.4f} "
          f"(n={dev_data['n_tokens']})", flush=True)
    print(f"lemma: T={t_lemma:.4f}  ECE {lemma_ece_before:.4f} -> {lemma_ece_after:.4f} "
          f"(n={dev_data['n_tokens']}, composed-lemma-correctness proxy)", flush=True)

    cal = calibrate.Calibration(
        temperature={"upos": t_upos, "lemma": t_lemma},
        fitted_on=f"UD Ancient Greek-Perseus dev fold ({_DATASET} v3, CPU, batch_size={_BATCH})",
        date=today,
        ece_before={"upos": upos_ece_before, "lemma": lemma_ece_before},
        ece_after={"upos": upos_ece_after, "lemma": lemma_ece_after},
        n={"upos": dev_data["n_tokens"], "lemma": dev_data["n_tokens"]},
        notes=("Temperature scaling (top-1 confidence, binary-NLL objective). UPOS target: "
               "argmax==gold. lemma target: composed lemma (script+lookup) == gold — a "
               "calibrated proxy on the script head's top-1 prob. Literary prose (Perseus); "
               "genre caveat applies."),
    )

    evidence: dict = {
        "what": "Temperature-scaled confidence calibration for the grc-joint neural pipeline.",
        "date": today,
        "model": f"{_DATASET} v3 (int8+fp16 quantized), CPU (CPUExecutionProvider)",
        "protocol": {
            "fit_fold": "UD Ancient Greek-Perseus dev (FIT; never test)",
            "test_fold": "UD Ancient Greek-Perseus test (report-only ECE, no fitting)",
            "execution": f"CPU, _run_batch batch_size={_BATCH} (prediction-identical to sequential)",
            "objective": "minimize binary NLL of top-1 softmax confidence vs correctness",
            "upos_target": "argmax UPOS == gold UPOS",
            "lemma_target": "composed lemma (script + train-only lookup) == gold lemma "
                            "(proxy calibrated on the edit-script head's top-1 probability)",
            "lemma_fit": "geometric grid over [0.5, 8.0] (streaming; 15k-wide script logits "
                         "not materialized for the whole fold), grid minimizer",
            "upos_fit": "aegean.greek.calibrate.fit_temperature (materialized 15-wide logits, "
                        "grid + golden-section refine)",
            "n_bins_ece": 15,
            "limit": args.limit,
        },
        "temperature": {"upos": t_upos, "lemma": t_lemma},
        "dev": {
            "n_sentences": len(dev),
            "n_tokens": dev_data["n_tokens"],
            "upos": {
                "ece_before": upos_ece_before, "ece_after": upos_ece_after,
                "accuracy": float(np.mean(dev_data["upos_correct"])),
                "reliability_before": _reliability_bins(upos_conf_before, dev_data["upos_correct"]),
                "reliability_after": _reliability_bins(upos_conf_after, dev_data["upos_correct"]),
            },
            "lemma": {
                "ece_before": lemma_ece_before, "ece_after": lemma_ece_after,
                "accuracy": float(np.mean(dev_data["lemma_correct"])),
                "reliability_before": _reliability_bins(conf_grid[:, i_one], dev_data["lemma_correct"]),
                "reliability_after": _reliability_bins(conf_grid[:, best_g], dev_data["lemma_correct"]),
            },
        },
        "calibration": cal.to_dict(),
    }

    # --- report-only TEST pass ----------------------------------------------------
    if not args.dev_only:
        test = load_conllu(ud_path("perseus", "test"))
        if args.limit is not None:
            test = test[: args.limit]
        print(f"\ntest fold: {len(test)} sentences, {sum(len(s.tokens) for s in test)} tokens "
              "(report-only, no fitting)", flush=True)
        test_data = _collect(model, test, need_lemma_grid=False, lemma_temp=t_lemma, tag="test/report")
        upos_conf_test = calibrate.top1_confidence(test_data["upos_logits"], t_upos)
        upos_ece_test = calibrate.ece(upos_conf_test, test_data["upos_correct"])
        lemma_conf_test = test_data["lemma_conf_at_t"]
        lemma_ece_test = calibrate.ece(lemma_conf_test, test_data["lemma_correct"])
        # ECE-before on test at T=1 for the record (the raw model, never surfaced)
        upos_ece_test_raw = calibrate.ece(
            calibrate.top1_confidence(test_data["upos_logits"], 1.0), test_data["upos_correct"])
        print(f"TEST UPOS : ECE@T=1 {upos_ece_test_raw:.4f} -> ECE@T={t_upos:.3f} {upos_ece_test:.4f}",
              flush=True)
        print(f"TEST lemma: ECE@T={t_lemma:.3f} {lemma_ece_test:.4f} (composed-lemma proxy)", flush=True)
        evidence["test"] = {
            "n_sentences": len(test),
            "n_tokens": test_data["n_tokens"],
            "upos": {
                "ece_at_T1_raw": upos_ece_test_raw, "ece_after": upos_ece_test,
                "accuracy": float(np.mean(test_data["upos_correct"])),
                "reliability_after": _reliability_bins(upos_conf_test, test_data["upos_correct"]),
            },
            "lemma": {
                "ece_after": lemma_ece_test,
                "accuracy": float(np.mean(test_data["lemma_correct"])),
                "reliability_after": _reliability_bins(lemma_conf_test, test_data["lemma_correct"]),
            },
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {out_path}", flush=True)
    print("integrator: after review, drop the 'calibration' block into "
          "src/aegean/data/bundled/greek/calibration.json to ship the bundled default.", flush=True)


if __name__ == "__main__":
    main()
