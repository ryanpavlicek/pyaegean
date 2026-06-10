"""Build export_production_model.ipynb — train the SHIPPED gold-only lemmatizer and package it.

Single-phase, gold-only (the 76.3% recipe; Wiktionary/two-stage/rescoring tested negative),
trained on ALL gold now that measurement is done. Exports the ONNX encoder/decoder via optimum
and assembles the `grc-lemma-neural` bundle the package fetches: encoder_model.onnx,
decoder_model.onnx, tokenizer.json, lookup.json.gz — tarred with files at the root so it
unpacks straight into the cache dir.

Run: `python build_export_notebook.py`.
"""
from __future__ import annotations

import pathlib

import nbformat as nbf

nb = nbf.v4.new_notebook()
md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
cells = []

cells.append(md(
    "# Export the shipped Greek neural lemmatizer (`grc-lemma-neural`)\n"
    "\n"
    "Trains the gold-only GreTa seq2seq (the 76.3%-unseen recipe) on **all** gold, exports ONNX, "
    "and packages the bundle `pyaegean`'s `[neural]` backend fetches. **Run all** on a GPU runtime, "
    "then upload the downloaded `grc-lemma-neural.tar.gz` to a GitHub release and report its sha256."
))

cells.append(code(
    "!nvidia-smi -L\n"
    "%pip -q install 'transformers>=4.46' 'datasets>=2.19' 'optimum[onnxruntime]>=1.20' "
    "accelerate sentencepiece protobuf onnx onnxruntime"
))

cells.append(md("## 0 · GPU + precision"))
cells.append(code(
    "import torch\n"
    "assert torch.cuda.is_available(), 'No GPU! Runtime > Change runtime type > GPU, reconnect.'\n"
    "USE_BF16 = torch.cuda.is_bf16_supported()\n"
    "BS = 128 if USE_BF16 else 16\n"
    "print(f'torch {torch.__version__} | GPU {torch.cuda.get_device_name(0)} | bf16={USE_BF16}')"
))

cells.append(md("## 1 · Upload `prod_data.zip` (prod_train.jsonl + lookup.json.gz)"))
cells.append(code(
    "import json, zipfile, pathlib\n"
    "from google.colab import files\n"
    "up = files.upload()  # pick prod_data.zip\n"
    "zipfile.ZipFile(next(n for n in up if n.endswith('.zip'))).extractall('.')\n"
    "DATA = pathlib.Path('data') if pathlib.Path('data/prod_train.jsonl').exists() else pathlib.Path('.')\n"
    "train_rows = [json.loads(l) for l in open(DATA / 'prod_train.jsonl', encoding='utf-8')]\n"
    "print('form->lemma pairs:', len(train_rows))"
))

cells.append(md("## 2 · Tokenizer + model (`bowphs/GreTa`), with pad/eos registered"))
cells.append(code(
    "from transformers import AutoTokenizer, AutoModelForSeq2SeqLM\n"
    "MODEL = 'bowphs/GreTa'\n"
    "tokenizer = AutoTokenizer.from_pretrained(MODEL)\n"
    "model = AutoModelForSeq2SeqLM.from_pretrained(MODEL)\n"
    "PAD_ID, EOS_ID = 0, 1  # GreTa ships a bare tokenizer; config.json defines pad=0, eos=1\n"
    "tokenizer.pad_token = tokenizer.convert_ids_to_tokens(PAD_ID)\n"
    "tokenizer.eos_token = tokenizer.convert_ids_to_tokens(EOS_ID)\n"
    "for cfg in (model.config, model.generation_config):\n"
    "    cfg.pad_token_id = PAD_ID; cfg.eos_token_id = EOS_ID; cfg.decoder_start_token_id = PAD_ID\n"
    "assert tokenizer.pad_token_id == PAD_ID and tokenizer.eos_token_id == EOS_ID"
))

cells.append(md("## 3 · Tokenize (force eos on targets)"))
cells.append(code(
    "from datasets import Dataset\n"
    "ML = 32\n"
    "APPEND_EOS = tokenizer(text_target='abc')['input_ids'][-1] != EOS_ID\n"
    "def prep(b):\n"
    "    enc = tokenizer(b['form'], max_length=ML, truncation=True)\n"
    "    lab = tokenizer(text_target=b['lemma'], max_length=ML - APPEND_EOS, truncation=True)['input_ids']\n"
    "    enc['labels'] = [x + [EOS_ID] for x in lab] if APPEND_EOS else lab\n"
    "    return enc\n"
    "ds = Dataset.from_list(train_rows).map(prep, batched=True, remove_columns=['form', 'lemma'])\n"
    "ds = ds.train_test_split(test_size=2000, seed=0)  # small slice for monitoring only\n"
    "print('APPEND_EOS', APPEND_EOS, '| train', len(ds['train']))"
))

cells.append(md(
    "## 4 · Fine-tune (single-phase, the 76.3% recipe)\n"
    "T5 uses **bf16, not fp16**; ~10 epochs on all gold, a few minutes on an H100."
))
cells.append(code(
    "import numpy as np\n"
    "from transformers import (Seq2SeqTrainer, Seq2SeqTrainingArguments, DataCollatorForSeq2Seq)\n"
    "collator = DataCollatorForSeq2Seq(tokenizer, model=model)\n"
    "def compute_metrics(ep):\n"
    "    preds, labels = ep\n"
    "    preds = np.where(preds != -100, preds, tokenizer.pad_token_id)\n"
    "    labels = np.where(labels != -100, labels, tokenizer.pad_token_id)\n"
    "    dp = tokenizer.batch_decode(preds, skip_special_tokens=True)\n"
    "    dl = tokenizer.batch_decode(labels, skip_special_tokens=True)\n"
    "    return {'exact': float(np.mean([a.strip() == b.strip() for a, b in zip(dp, dl)]))}\n"
    "args = Seq2SeqTrainingArguments(\n"
    "    output_dir='out', learning_rate=3e-4, lr_scheduler_type='cosine',\n"
    "    per_device_train_batch_size=BS, per_device_eval_batch_size=BS*2,\n"
    "    num_train_epochs=10, weight_decay=0.01, warmup_ratio=0.06,\n"
    "    bf16=USE_BF16, fp16=False, tf32=USE_BF16, optim='adamw_torch_fused',\n"
    "    dataloader_num_workers=2, predict_with_generate=True, generation_max_length=ML,\n"
    "    eval_strategy='epoch', save_strategy='epoch', save_total_limit=1,\n"
    "    load_best_model_at_end=True, metric_for_best_model='exact', greater_is_better=True,\n"
    "    logging_steps=200, report_to='none')\n"
    "Seq2SeqTrainer(model=model, args=args, train_dataset=ds['train'], eval_dataset=ds['test'],\n"
    "               data_collator=collator, processing_class=tokenizer,\n"
    "               compute_metrics=compute_metrics).train()\n"
    "model.save_pretrained('out_model'); tokenizer.save_pretrained('out_model')"
))

cells.append(md("## 5 · Export ONNX (encoder + decoder)"))
cells.append(code(
    "!optimum-cli export onnx --model out_model --task text2text-generation onnx\n"
    "import os\n"
    "print(sorted(os.listdir('onnx')))\n"
    "assert os.path.exists('onnx/decoder_model.onnx'), \\\n"
    "    'no decoder_model.onnx (the no-past decoder the torch-free loop needs) — retry export with --no-post-process'"
))

cells.append(md(
    "## 6 · Assemble + download `grc-lemma-neural.tar.gz`\n"
    "The four files the package loads, tarred at the archive root so it unpacks straight into the "
    "cache. **Report the printed sha256** — I pin it in the data layer."
))
cells.append(code(
    "import os, shutil, tarfile, hashlib\n"
    "B = 'grc-lemma-neural'\n"
    "os.makedirs(B, exist_ok=True)\n"
    "for fn in ['encoder_model.onnx', 'decoder_model.onnx', 'tokenizer.json']:\n"
    "    shutil.copy(os.path.join('onnx', fn), os.path.join(B, fn))\n"
    "shutil.copy(str(DATA / 'lookup.json.gz'), os.path.join(B, 'lookup.json.gz'))\n"
    "with tarfile.open(B + '.tar.gz', 'w:gz') as tf:\n"
    "    for fn in sorted(os.listdir(B)):\n"
    "        tf.add(os.path.join(B, fn), arcname=fn)  # arcname=fn -> files at archive root\n"
    "sz = os.path.getsize(B + '.tar.gz') // (1024 * 1024)\n"
    "sha = hashlib.sha256(open(B + '.tar.gz', 'rb').read()).hexdigest()\n"
    "print(f'{B}.tar.gz  {sz} MB\\nsha256={sha}')\n"
    "files.download(B + '.tar.gz')"
))

cells.append(md(
    "## Next\n"
    "1. Upload `grc-lemma-neural.tar.gz` to a GitHub release on `ryanpavlicek/pyaegean`.\n"
    "2. Report the **sha256** and the release asset URL — I pin them in `aegean.data._REMOTE`.\n"
    "3. Then `pip install 'pyaegean[neural]'` + `greek.use_neural_lemmatizer()` fetches and runs it."
))

nb["cells"] = cells
out = pathlib.Path(__file__).parent / "export_production_model.ipynb"
nbf.write(nb, out)
print("wrote", out)
