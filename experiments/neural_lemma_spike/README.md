# Neural-lemmatizer spike

An experiment to answer one question before investing in a full neural backend: **can a
torch-free transformer beat stanza/CLTK on pyaegean's hardest column — unseen-form
lemmatization?**

| approach | lemma, all (held-out AGDT) | lemma, **unseen forms** |
| --- | --- | --- |
| pure-Python lemmatizer (current default) | — | 40.3% |
| edit-tree classifier on GreBERTa (multi-treebank) | 88.9% | 58.2% *(architectural cap)* |
| stanza / CLTK grc | 87.3% | **62.8%** |
| **seq2seq target** | — | **> 62.8%** |

We already beat stanza on overall lemma accuracy (88.9% vs 87.3%). The remaining gap is
**unseen forms**, where edit-tree *classification* plateaued near 58%: it can only reuse
edit-patterns it saw in training. The SOTA Ancient-Greek lemmatizer (GreTa,
[arXiv:2410.12055](https://arxiv.org/abs/2410.12055), ~91% F1) instead **generates** the
lemma character-by-character with a seq2seq T5, which composes novel transformations for
forms it never saw. This spike fine-tunes the pretrained, Apache-2.0 `bowphs/GreTa` on plain
`form → lemma` pairs and measures the same unseen column on the same leakage-free split.

## Files
- `build_seq2seq_data.py` — builds `data/{train.jsonl,dev.jsonl}`: **unique `form→lemma`
  pairs** from AGDT-train + AGDT-disjoint treebanks (Pedalion + Gorman's non-AGDT authors),
  deduped by sentence-fingerprint against *all* of AGDT so dev can't leak; dev is the
  identical held-out AGDT tokens (so the number stays comparable to the edit-tree runs).
- `spike_lemma_grebert.ipynb` — the Colab notebook (fine-tune GreTa → eval by generation →
  export ONNX → download). Regenerate with `build_spike_notebook.py`.
- `eval_seq2seq.py` — local confirmation: loads the optimum-exported ONNX and reproduces the
  `DEV lemma all/UNSEEN` number via onnxruntime.
- `build_multi_treebank_data.py`, `eval_spike.py`, `prep_spike_data.py` — the prior edit-tree
  spike (kept for reference; that route capped at 58.2% unseen).
- `data/`, `spike_data.zip`, model artifacts — git-ignored (regenerate with the build scripts).

## How to run

1. **Build the data** (already run): `python build_seq2seq_data.py` → re-zip `data/` as
   `spike_data.zip` (~1 MB).
2. **Colab.** Upload `spike_lemma_grebert.ipynb` → **Runtime → Change runtime type → GPU** →
   **Run all** → upload `spike_data.zip` when prompted. It fine-tunes GreTa (~minutes on an
   H100), and **cell 6b prints `DEV lemma — all X% UNSEEN Y%`** — that is the answer.
3. **(Optional) local confirmation.** Download `spike_model.zip`, unzip next to `data/`:
   ```
   pip install "optimum[onnxruntime]" transformers sentencepiece
   python eval_seq2seq.py --model <unzipped_onnx_dir> --dev data/dev.jsonl
   ```

## Decision rule
- **Unseen lemma clears 62.8%** → green-light the opt-in `[neural]` backend: GreTa as the
  production lemmatizer (ONNX, fetched-to-cache, never bundled), with the pure-Python
  rule/edit-tree lemmatizer staying the zero-dependency default.
- **It doesn't** → the edit-tree backend (already beating stanza overall) stands; we reconsider
  the unseen column separately.

## Notes / risks
- **Precision:** T5 trains in **bf16, not fp16** (fp16 overflows on T5); the notebook falls back
  to fp32 on a non-bf16 GPU. The headline number comes from the fp32/bf16 model — quantize
  per-channel only for production (per-tensor int8 collapsed the earlier classifier head).
- **Torch-free runtime:** `eval_seq2seq.py` uses optimum (which pulls torch) for a robust
  dev-time check. The *shipped* path needs a hand-rolled numpy greedy-decode loop over the
  encoder/decoder ONNX so torch never enters the dependency set — a production task, not this spike.
- **Licensing (for a *shipped* model later, not this spike):** train only on the non-NC stack —
  AGDT (CC BY-SA 3.0), Gorman (CC0), Pedalion (CC BY-SA 4.0). A shipped model would carry
  CC BY-SA + attribution; the core wheel stays Apache-2.0 because the model is fetched, never bundled.
