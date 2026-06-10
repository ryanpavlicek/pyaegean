# training/ — model training for the WP3 accuracy program

Training-side code for the Greek NLP accuracy program (`docs/ROADMAP.md` WP3,
`docs/benchmarks.md` for the protocol + targets). Nothing in this directory ships in the
wheel; trained artifacts are published as GitHub release assets and fetched to the user
cache, never bundled.

## Stage A — encoder bake-off

**Question:** which pretrained encoder carries Stages B–E?
**Method:** identical quick UPOS fine-tune per candidate on the leakage-clean AGDT split;
decide on dev accuracy (primary), unseen-form accuracy (generalization), size/speed, and
license.

### Candidates

| Model | Arch | License | Role |
|---|---|---|---|
| `bowphs/GreBerta` | RoBERTa, grc monolingual | Apache-2.0 | **shippable candidate** |
| `bowphs/PhilBerta` | RoBERTa, grc+la+en trilingual | Apache-2.0 | **shippable candidate** |
| `pranaydeeps/Ancient-Greek-BERT` | BERT (the odyCy backbone) | **GPL-3.0** | reference point only — calibrates against the odyCy starting point; fine-tuned weights are NOT redistributable under this project's licensing |

(GreBerta/PhilBerta are the GreTa authors' encoders — same Apache-2.0 lineage as the
neural lemmatizer pyaegean already redistributes.)

### Decision rule

1. License gate first: the shipped encoder must be Apache/MIT-class (GreBerta or
   PhilBerta). Ancient-Greek-BERT's score is measured for calibration only.
2. Among shippable candidates: highest dev UPOS accuracy wins; an unseen-form accuracy
   gap > 1 point overrides a smaller overall gap (generalization is the program's brand).
3. Ties broken by size (smaller → smaller ONNX artifact in Stage E) and wall time.
4. Record the decision + all metrics tables in `docs/benchmarks.md`.

### Running it (Colab — planned hardware: G4, with A100 backup)

The expected accelerator is a **Colab G4** (NVIDIA RTX PRO 6000 Blackwell Server Edition,
96 GB), with **A100** as backup and H100 opportunistic. The script auto-detects precision:
**bf16** on Blackwell/Ampere-class GPUs (no loss scaler), fp16 on older cards, and enables
TF32 matmuls. At 96 GB, base-size encoders at the default batch are nowhere near memory
limits — expect a few minutes per candidate, not tens.

The pip install provides the `aegean` package; the `training/` scripts are deliberately
**not** in the wheel, so clone the repo for them and run them from the clone:

```bash
pip install "git+https://github.com/ryanpavlicek/pyaegean" torch transformers numpy
git clone https://github.com/ryanpavlicek/pyaegean.git pyaegean_repo

python pyaegean_repo/training/build_upos_dataset.py   # fetches AGDT + UD folds to cache; writes data/ in the clone
python pyaegean_repo/training/bakeoff_upos.py --model bowphs/GreBerta
python pyaegean_repo/training/bakeoff_upos.py --model bowphs/PhilBerta
python pyaegean_repo/training/bakeoff_upos.py --model pranaydeeps/Ancient-Greek-BERT
```

Before the Colab runtime recycles, save the result files —
`pyaegean_repo/training/out/<model>/metrics.json` (one per candidate).

Each run writes `training/out/<model>/metrics.json`. The fixed budget — 2 epochs, lr 5e-5,
effective batch 32 (native `--batch 32`), max-len 256, seed 42 — **must stay identical
across candidates**; that's the bake-off. On a faster GPU the same commands simply finish
sooner — don't retune. (Fallback only: on a 16 GB-class card, keep the budget with
`--batch 16 --grad-accum 2`, and `--precision fp16` if bf16 is unsupported.) Robustness
check, since G4 time makes it cheap: repeat the top two candidates with `--seed 7`.

Smoke-test the plumbing before a GPU session: `--limit-train 500 --epochs 1` (runs on CPU too).

### The data protocol (what build_upos_dataset.py enforces)

- **train** = AGDT minus every sentence in the UD-Perseus dev+test exclusion manifest
  (`aegean.greek.agdt_ud_overlap`; 2,443 sentences, 100% form-verified).
- **dev** = exactly the AGDT sentences behind the UD-Perseus *dev* fold — never trained
  on, stable across runs, and citable.
- The AGDT sentences behind the UD-Perseus *test* fold appear in **neither** file: final
  numbers come only from `greek.evaluate_on_ud("perseus", "test")` against a finished
  model.
- Labels are AGDT-native coarse UPOS (relative bake-off measure). The UD-convention label
  work (PROPN/SCONJ) is Stage B, where absolute UD-fold numbers start to matter.

`training/data/` and `training/out/` are gitignored — datasets rebuild deterministically
from the cache, and bake-off checkpoints are throwaway (`--save-model` exists for
debugging only). What comes back from a GPU session is the `metrics.json` files.
