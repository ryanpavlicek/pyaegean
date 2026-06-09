# Neural-lemmatizer spike

A one-afternoon experiment to answer a single question before investing in a full neural
backend: **can a torch-free ONNX transformer beat stanza/CLTK on pyaegean's hardest column —
unseen-form lemmatization?**

| | lemma (unseen forms), held-out AGDT |
| --- | --- |
| pure-Python lemmatizer (current) | 40.3% |
| stanza / CLTK grc | 62.8% |
| **spike target** | **> 62.8%** |

The spike reuses pyaegean's own machinery so it's apples-to-apples: the **same edit-tree label
set** (`lemmatizer.build_tree`/`apply_tree`), the **same leakage-free split** (`heldout`), and
the **same gold lemmas**. Only the *scorer* changes — a fine-tuned `bowphs/GreBerta` (Apache-2.0)
token classifier instead of the averaged perceptron. No production code is touched.

## Files
- `prep_spike_data.py` — builds `data/{train.jsonl,dev.jsonl,labels.json}` from the cached AGDT. **Already run.**
- `spike_lemma_grebert.ipynb` — the Colab notebook (fine-tune → ONNX → int8 → download).
- `eval_spike.py` — torch-free local eval (onnxruntime + tokenizers) reproducing `heldout`'s lemma columns.
- `build_spike_notebook.py` — regenerates the notebook.
- `data/`, `spike_data.zip`, downloaded model artifacts — git-ignored (regenerate with `prep_spike_data.py`).

## How to run

1. **Colab (you).** Open <https://colab.research.google.com> → upload `spike_lemma_grebert.ipynb`
   → **Runtime → Change runtime type → T4 GPU** → **Run all**. When prompted, upload
   `experiments/neural_lemma_spike/spike_data.zip` (already built, ~2.8 MB). It fine-tunes
   (~minutes–1–2 h), exports ONNX, int8-quantizes, and downloads **`spike_model.zip`**.
2. **Send `spike_model.zip` back.**
3. **Local eval (me).** Unzip it next to `data/`, then:
   ```
   pip install onnxruntime tokenizers numpy        # NO torch
   python eval_spike.py --model model.onnx --tokenizer tokenizer.json \
                        --labels data/labels.json --dev data/dev.jsonl
   ```
   It prints `neural lemma: all X% UNSEEN Y%` and a verdict vs the 62.8% bar.

## Decision rule
- **Unseen lemma clears ~62.8%** → green-light the full multi-task `[neural]` backend
  (shared GreBERTa encoder + POS + UFeats + edit-tree lemma + later a biaffine parser),
  shipped as an opt-in extra with the ONNX model fetched-to-cache.
- **It doesn't** → one afternoon spent, not three weeks; we reconsider.

## Notes / risks
- **Encoder:** `bowphs/GreBerta` is Apache-2.0 and monolingual Ancient Greek. If the HF id or API
  has drifted, the notebook's model/quantization cells are where to adjust; paste any error back.
- **Tokenizer round-trip:** the local eval loads the saved `tokenizer.json` via the standalone
  `tokenizers` lib (no `transformers`). If accuracy looks implausibly low, a pre-tokenization
  mismatch between training and the torch-free path is the prime suspect.
- **Licensing (for a *shipped* model later, not this spike):** train only on the non-NC stack —
  AGDT (CC BY-SA 3.0), Gorman via `perseids-publications/gorman-trees` (CC0), Pedalion
  (CC BY-SA 4.0). Avoid UD_Perseus / UD_PROIEL (CC BY-NC-SA). A shipped model would carry
  CC BY-SA 4.0 + attribution; the core wheel stays Apache-2.0 because the model is fetched, never bundled.
- This spike trains on AGDT only — enough to test the thesis; the full corpus merge comes later.
