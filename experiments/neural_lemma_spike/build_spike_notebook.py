"""Build spike_lemma_grebert.ipynb — GreTa SEQ2SEQ lemmatizer (run: `python build_spike_notebook.py`).

Fine-tunes bowphs/GreTa (the pretrained SOTA Ancient Greek T5, arXiv:2410.12055,
Apache-2.0) to GENERATE the lemma from the form. Generation is what beats edit-tree
classification on unseen forms (which capped at ~58%). Standard HuggingFace Seq2SeqTrainer +
optimum ONNX export — not a from-scratch build.
"""
from __future__ import annotations

import pathlib

import nbformat as nbf

nb = nbf.v4.new_notebook()
md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
cells = []

cells.append(md(
    "# pyaegean neural lemmatizer — GreTa seq2seq (SOTA route)\n"
    "\n"
    "Fine-tune **`bowphs/GreTa`** (pretrained Ancient-Greek T5, the SOTA lemmatizer) "
    "to **generate** the lemma from the form. Generation handles unseen forms where our "
    "edit-tree classifier capped at 58.2%; literature puts GreTa ~91% F1. Target: unseen > "
    "stanza's 62.8%.\n"
    "\n"
    "**Loop:** GPU runtime → Run all → **cell 6b prints `DEV lemma all/UNSEEN`** → (optionally) "
    "download `spike_model.zip`. torch/transformers used only here; inference is onnxruntime."
))

cells.append(code(
    "!nvidia-smi -L  # MUST list a GPU\n"
    "%pip -q install 'transformers>=4.46' 'datasets>=2.19' 'optimum[onnxruntime]>=1.20' "
    "accelerate sentencepiece protobuf onnx onnxruntime"
))

cells.append(md("## 0 · GPU + precision"))
cells.append(code(
    "import torch\n"
    "assert torch.cuda.is_available(), 'No GPU! Runtime > Change runtime type > GPU, reconnect.'\n"
    "USE_BF16 = torch.cuda.is_bf16_supported()\n"
    "BS = 128 if USE_BF16 else 16\n"
    "print(f'torch {torch.__version__} | CUDA {torch.version.cuda} | GPU {torch.cuda.get_device_name(0)} | bf16={USE_BF16}')"
))

cells.append(md("## 1 · Upload `spike_data.zip`"))
cells.append(code(
    "import json, zipfile, pathlib\n"
    "from google.colab import files\n"
    "up = files.upload()  # pick spike_data.zip\n"
    "zipfile.ZipFile(next(n for n in up if n.endswith('.zip'))).extractall('.')\n"
    "DATA = pathlib.Path('data') if pathlib.Path('data/train.jsonl').exists() else pathlib.Path('.')\n"
    "train_rows = [json.loads(l) for l in open(DATA / 'train.jsonl', encoding='utf-8')]\n"
    "print('form->lemma pairs:', len(train_rows), '| e.g.', train_rows[0])"
))

cells.append(md("## 2 · Tokenizer + model (`bowphs/GreTa`, T5 encoder-decoder)"))
cells.append(code(
    "from transformers import AutoTokenizer, AutoModelForSeq2SeqLM\n"
    "MODEL = 'bowphs/GreTa'\n"
    "tokenizer = AutoTokenizer.from_pretrained(MODEL)\n"
    "model = AutoModelForSeq2SeqLM.from_pretrained(MODEL)\n"
    "\n"
    "# GreTa ships a bare fast tokenizer with no registered pad/eos, and loading nulls the\n"
    "# model's pad/eos ids. config.json defines pad=0, eos=1 (standard T5) -- register them\n"
    "# on the tokenizer and restore them on both configs so padding + generation work.\n"
    "PAD_ID, EOS_ID = 0, 1\n"
    "tokenizer.pad_token = tokenizer.convert_ids_to_tokens(PAD_ID)\n"
    "tokenizer.eos_token = tokenizer.convert_ids_to_tokens(EOS_ID)\n"
    "for cfg in (model.config, model.generation_config):\n"
    "    cfg.pad_token_id = PAD_ID\n"
    "    cfg.eos_token_id = EOS_ID\n"
    "    cfg.decoder_start_token_id = PAD_ID\n"
    "assert tokenizer.pad_token_id == PAD_ID and tokenizer.eos_token_id == EOS_ID\n"
    "print('pad', repr(tokenizer.pad_token), tokenizer.pad_token_id,\n"
    "      '| eos', repr(tokenizer.eos_token), tokenizer.eos_token_id)"
))

cells.append(md("## 3 · Tokenize (form -> input_ids, lemma -> labels)"))
cells.append(code(
    "from datasets import Dataset\n"
    "ML = 32\n"
    "# Force eos on targets if the tokenizer doesn't (so the model learns to stop); inputs use\n"
    "# the tokenizer's natural output, identical at train + inference time.\n"
    "APPEND_EOS = tokenizer(text_target='abc')['input_ids'][-1] != EOS_ID\n"
    "def prep(b):\n"
    "    enc = tokenizer(b['form'], max_length=ML, truncation=True)\n"
    "    lab = tokenizer(text_target=b['lemma'], max_length=ML - APPEND_EOS, truncation=True)['input_ids']\n"
    "    enc['labels'] = [x + [EOS_ID] for x in lab] if APPEND_EOS else lab\n"
    "    return enc\n"
    "COLS = ['form', 'lemma', 'src']\n"
    "ds_all = Dataset.from_list(train_rows).map(prep, batched=True, remove_columns=COLS).train_test_split(test_size=4000, seed=0)\n"
    "seen = set(); gold_rows = []  # deduped treebank pairs — the convention anchor for phase 2\n"
    "for r in train_rows:\n"
    "    k = (r['form'], r['lemma'])\n"
    "    if r['src'] == 'treebank' and k not in seen:\n"
    "        seen.add(k); gold_rows.append(r)\n"
    "ds_gold = Dataset.from_list(gold_rows).map(prep, batched=True, remove_columns=COLS).train_test_split(test_size=4000, seed=0)\n"
    "print('APPEND_EOS', APPEND_EOS, '| phase1 train', len(ds_all['train']), '| phase2 gold train', len(ds_gold['train']))"
))

cells.append(md(
    "## 4 · Two-stage fine-tune (breadth, then convention)\n"
    "**Phase 1** trains on the full gold-majority mix (treebank + Wiktionary paradigms) to learn "
    "broad morphology. **Phase 2** fine-tunes on the treebank pairs only, at a low LR, to re-anchor "
    "the AGDT lemma conventions the dev set is scored against — recovering the exact-match that the "
    "broad mix alone trades away. T5 uses **bf16, not fp16** (fp16 overflows); falls back to fp32 on "
    "a T4. Watch `exact` climb within each phase."
))
cells.append(code(
    "import numpy as np\n"
    "from transformers import (Seq2SeqTrainer, Seq2SeqTrainingArguments,\n"
    "                          DataCollatorForSeq2Seq)\n"
    "collator = DataCollatorForSeq2Seq(tokenizer, model=model)\n"
    "def compute_metrics(ep):\n"
    "    preds, labels = ep\n"
    "    preds = np.where(preds != -100, preds, tokenizer.pad_token_id)\n"
    "    labels = np.where(labels != -100, labels, tokenizer.pad_token_id)\n"
    "    dp = tokenizer.batch_decode(preds, skip_special_tokens=True)\n"
    "    dl = tokenizer.batch_decode(labels, skip_special_tokens=True)\n"
    "    return {'exact': float(np.mean([a.strip() == b.strip() for a, b in zip(dp, dl)]))}\n"
    "def make_args(out, epochs, lr):\n"
    "    return Seq2SeqTrainingArguments(\n"
    "        output_dir=out, learning_rate=lr, lr_scheduler_type='cosine',\n"
    "        per_device_train_batch_size=BS, per_device_eval_batch_size=BS*2,\n"
    "        num_train_epochs=epochs, weight_decay=0.01, warmup_ratio=0.06,\n"
    "        bf16=USE_BF16, fp16=False, tf32=USE_BF16, optim='adamw_torch_fused',\n"
    "        dataloader_num_workers=2, predict_with_generate=True, generation_max_length=ML,\n"
    "        eval_strategy='epoch', save_strategy='epoch', save_total_limit=1,\n"
    "        load_best_model_at_end=True, metric_for_best_model='exact', greater_is_better=True,\n"
    "        logging_steps=200, report_to='none')\n"
    "def run(ds, out, epochs, lr):\n"
    "    Seq2SeqTrainer(model=model, args=make_args(out, epochs, lr),\n"
    "                   train_dataset=ds['train'], eval_dataset=ds['test'],\n"
    "                   data_collator=collator, processing_class=tokenizer,\n"
    "                   compute_metrics=compute_metrics).train()\n"
    "run(ds_all, 'out1', 6, 3e-4)   # phase 1: breadth (gold-majority mix)\n"
    "run(ds_gold, 'out2', 5, 5e-5)  # phase 2: re-anchor AGDT conventions (gold only, low LR)\n"
    "model.save_pretrained('out_model'); tokenizer.save_pretrained('out_model')"
))

cells.append(md(
    "## 6b · Dev lemma accuracy — GENERATE the lemma per form (the number that matters)"
))
cells.append(code(
    "import re, unicodedata\n"
    "model.eval()\n"
    "dev = [json.loads(l) for l in open(DATA / 'dev.jsonl', encoding='utf-8')]\n"
    "forms = sorted({d['form'] for d in dev if d['scored']})\n"
    "pred = {}\n"
    "B = 256\n"
    "for i in range(0, len(forms), B):\n"
    "    b = forms[i:i+B]\n"
    "    enc = tokenizer(b, return_tensors='pt', padding=True, truncation=True, max_length=ML)\n"
    "    enc.pop('token_type_ids', None)  # GreTa's tokenizer emits these; T5.generate rejects them\n"
    "    enc = enc.to(model.device)\n"
    "    with torch.no_grad():\n"
    "        g = model.generate(**enc, max_length=ML, num_beams=5, early_stopping=True)\n"
    "    for f, d in zip(b, tokenizer.batch_decode(g, skip_special_tokens=True)):\n"
    "        pred[f] = d\n"
    "def _clean(s): return re.sub(r'\\d+$', '', unicodedata.normalize('NFC', s))\n"
    "na = nu = oa = ou = 0\n"
    "for d in dev:\n"
    "    if not d['scored']: continue\n"
    "    na += 1; un = not d['seen']; nu += un\n"
    "    if _clean(pred[d['form']]) == d['lemma']: oa += 1; ou += un\n"
    "print(f'DEV lemma — all {oa/na:.1%}  UNSEEN {ou/nu:.1%}   '\n"
    "      f'(beat: stanza 62.8% unseen; edit-tree 58.2%; pure-Python 40.3%)')"
))

cells.append(md(
    "## 7 · Export ONNX (seq2seq) + download\n"
    "`optimum` exports encoder + decoder for torch-free `ORTModelForSeq2SeqLM.generate()`. The "
    "zip is large (fp32 T5) — the **cell-6b number above is the answer**; the zip is only needed "
    "for the local onnxruntime confirmation."
))
cells.append(code(
    "import os, shutil\n"
    "!optimum-cli export onnx --model out_model --task text2text-generation onnx 2>/dev/null || \\\n"
    " optimum-cli export onnx --model out_model --task text2text-generation onnx\n"
    "sz = sum(os.path.getsize(os.path.join('onnx', f)) for f in os.listdir('onnx')) // (1024*1024)\n"
    "print('onnx dir', sz, 'MB:', sorted(os.listdir('onnx')))\n"
    "shutil.make_archive('spike_model', 'zip', 'onnx')\n"
    "files.download('spike_model.zip')"
))

cells.append(md(
    "## Next\n"
    "Report cell 6b's `DEV lemma all/UNSEEN`. **Unseen > 62.8% = we beat stanza** on the clean "
    "metric (we already beat it on overall). Send `spike_model.zip` for the local onnxruntime "
    "confirmation: `python eval_seq2seq.py --model <unzipped> --dev data/dev.jsonl`."
))

nb["cells"] = cells
out = pathlib.Path(__file__).parent / "spike_lemma_grebert.ipynb"
nbf.write(nb, out)
print("wrote", out)
