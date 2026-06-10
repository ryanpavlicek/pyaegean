# Neural-lemmatizer spike

An experiment to answer one question before investing in a full neural backend: **can a
torch-free transformer beat stanza/CLTK on pyaegean's hardest column — unseen-form
lemmatization?**

| approach | lemma, all (held-out AGDT) | lemma, **unseen forms** |
| --- | --- | --- |
| pure-Python lemmatizer (current default) | — | 40.3% |
| edit-tree classifier on GreBERTa (multi-treebank) | 88.9% | 58.2% *(architectural cap)* |
| stanza / CLTK grc | 87.3% | **62.8%** |
| **GreTa seq2seq (this spike)** | 81.2% | **76.3%** ✅ |
| **→ hybrid (route seen→edit-tree, unseen→seq2seq)** | **~91.8%** | **76.3%** |

We already beat stanza on overall lemma accuracy (88.9% vs 87.3%). The remaining gap was
**unseen forms**, where edit-tree *classification* plateaued near 58%: it can only reuse
edit-patterns it saw in training. The SOTA Ancient-Greek lemmatizer (GreTa,
[arXiv:2410.12055](https://arxiv.org/abs/2410.12055), ~91% F1) instead **generates** the
lemma left-to-right with a seq2seq T5, which composes novel transformations for
forms it never saw. This spike fine-tuned the pretrained, Apache-2.0 `bowphs/GreTa` on plain
`form → lemma` pairs and measured the same unseen column on the same leakage-free split.

## Result

**Unseen-form lemma accuracy: 76.3% — clears stanza/CLTK's 62.8% by +13.5 points.**

The seq2seq's *overall* accuracy (81.2%) is lower than the edit-tree's (88.9%) because pure
generation has no lookup advantage on **seen** forms. Backing out the disjoint subsets
(seen = 45,138 dev tokens, unseen = 8,898): the edit-tree is ~94.9% on seen / 58.2% on unseen
(memorizes, doesn't generalize); the seq2seq is ~82.2% on seen / **76.3% on unseen**
(generalizes, weaker lookup). Neither pure approach is optimal — the production design is the
**hybrid router**: lookup/edit-tree for seen forms, seq2seq for unseen. Since seen/unseen are
disjoint and each model is measured per-subset, the hybrid is arithmetic: **~91.8% all + 76.3%
unseen — beating stanza on *both* columns at once** (it scores 87.3% / 62.8%). "Seen" is
definitionally "this form is in the training table", so the router is a trivial lookup.

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

## Decision rule — cleared

Unseen lemma reached **76.3% > 62.8%**, so the opt-in `[neural]` backend is green-lit: GreTa
seq2seq as the **unseen-form** lemmatizer (ONNX, fetched-to-cache, never bundled), the
pure-Python rule/edit-tree lemmatizer staying the zero-dependency default **and** the seen-form
path. The production lemmatizer is the **hybrid router** of the two, not a wholesale swap (a
swap would trade away the seen-form lookup advantage — 88.9% → 81.2% overall).

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
