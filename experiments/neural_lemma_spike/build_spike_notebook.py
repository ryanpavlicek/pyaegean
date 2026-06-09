"""Build spike_lemma_grebert.ipynb (run once: `python build_spike_notebook.py`).

H100-aware (auto-detects bf16/tf32 and scales batch size; falls back cleanly on a T4),
and uses current, non-deprecated APIs:
  - Trainer(processing_class=...)  not the deprecated tokenizer=
  - eval_strategy=                 not the deprecated evaluation_strategy=
  - optimum-cli export onnx + onnxruntime.quantization.quantize_dynamic
    (not ORTModelForTokenClassification(export=True) + ORTQuantizer)
"""
from __future__ import annotations

import pathlib

import nbformat as nbf

nb = nbf.v4.new_notebook()
md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
cells = []

cells.append(md(
    "# pyaegean neural-lemmatizer spike — GreBERTa + edit-tree head\n"
    "\n"
    "Goal: beat stanza/CLTK on the hardest column, **unseen-form lemma** "
    "(pure-Python baseline 40.3%, stanza 62.8%) — by classifying the **same edit-tree label "
    "set** the pure-Python lemmatizer uses, but from a fine-tuned Ancient-Greek transformer.\n"
    "\n"
    "**Loop:** set runtime to a **GPU** (an H100 is ideal; a T4 also works) → Run all → "
    "download `spike_model.zip` at the end → send it back for the torch-free local eval.\n"
    "\n"
    "Precision auto-detects: **bf16 + TF32 + fused AdamW + batch 64 on H100/A100**, "
    "fp16 + batch 16 on a T4. Encoder: `bowphs/GreBerta` (Apache-2.0, Ancient-Greek RoBERTa). "
    "torch/transformers are used **only here**; production inference is onnxruntime-only."
))

cells.append(code(
    "!nvidia-smi -L  # confirm the GPU (H100 ideal)\n"
    "%pip -q install 'transformers>=4.46' 'datasets>=2.19' 'optimum[onnxruntime]>=1.20' "
    "'accelerate>=0.30' onnx onnxruntime"
))

cells.append(md("## 0 · Detect GPU + precision"))
cells.append(code(
    "import torch\n"
    "gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'\n"
    "USE_BF16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()  # Ampere/Hopper+\n"
    "BS = 64 if USE_BF16 else 16\n"
    "print(f'torch {torch.__version__} | CUDA {torch.version.cuda} | GPU {gpu}')\n"
    "print(f'bf16={USE_BF16}  ->  batch_size={BS}, '\n"
    "      f'precision={\"bf16+tf32\" if USE_BF16 else \"fp16\"}')"
))

cells.append(md(
    "## 1 · Upload the data bundle\n"
    "Upload **`spike_data.zip`** (zip of `experiments/neural_lemma_spike/data/`: "
    "`train.jsonl`, `dev.jsonl`, `labels.json`)."
))
cells.append(code(
    "import json, zipfile, pathlib\n"
    "from google.colab import files\n"
    "up = files.upload()  # pick spike_data.zip\n"
    "zname = next(n for n in up if n.endswith('.zip'))\n"
    "zipfile.ZipFile(zname).extractall('.')\n"
    "DATA = pathlib.Path('data') if pathlib.Path('data/labels.json').exists() else pathlib.Path('.')\n"
    "labels = json.loads((DATA / 'labels.json').read_text(encoding='utf-8'))['trees']\n"
    "id2label = {i: k for i, k in enumerate(labels)}\n"
    "label2id = {k: i for i, k in enumerate(labels)}\n"
    "print('edit-tree labels:', len(labels))"
))

cells.append(md("## 2 · Load the training data"))
cells.append(code(
    "from datasets import Dataset\n"
    "def read_jsonl(p):\n"
    "    return [json.loads(l) for l in open(p, encoding='utf-8')]\n"
    "train_rows = read_jsonl(DATA / 'train.jsonl')\n"
    "ds = Dataset.from_list([{'tokens': r['tokens'], 'tags': r['labels']} for r in train_rows])\n"
    "print(ds)"
))

cells.append(md("## 3 · Tokenizer + model (`bowphs/GreBerta`)"))
cells.append(code(
    "from transformers import AutoTokenizer, AutoModelForTokenClassification\n"
    "MODEL = 'bowphs/GreBerta'\n"
    "tokenizer = AutoTokenizer.from_pretrained(MODEL, add_prefix_space=True)\n"
    "model = AutoModelForTokenClassification.from_pretrained(\n"
    "    MODEL, num_labels=len(labels), id2label=id2label, label2id=label2id)"
))

cells.append(md(
    "## 4 · Tokenize + align labels to the first sub-token of each word\n"
    "Label only the first sub-token of each word, `-100` (ignored by the loss) elsewhere — "
    "matching the local eval's first-subword pooling."
))
cells.append(code(
    "def align(batch):\n"
    "    enc = tokenizer(batch['tokens'], is_split_into_words=True, truncation=True,\n"
    "                    max_length=256)\n"
    "    out = []\n"
    "    for i, tags in enumerate(batch['tags']):\n"
    "        word_ids = enc.word_ids(i)\n"
    "        prev, row = None, []\n"
    "        for wid in word_ids:\n"
    "            if wid is None:\n"
    "                row.append(-100)\n"
    "            elif wid != prev:\n"
    "                row.append(tags[wid])      # already -100 for pruned tokens\n"
    "            else:\n"
    "                row.append(-100)\n"
    "            prev = wid\n"
    "        out.append(row)\n"
    "    enc['labels'] = out\n"
    "    return enc\n"
    "tok_ds = ds.map(align, batched=True, remove_columns=ds.column_names)\n"
    "tok_ds = tok_ds.train_test_split(test_size=0.02, seed=0)  # small dev for best-epoch selection\n"
    "print(tok_ds)"
))

cells.append(md(
    "## 5 · Fine-tune (H100-tuned; keeps the best epoch by dev token-accuracy)\n"
    "On an H100 this is a few minutes for 4 epochs; on a T4, longer. `load_best_model_at_end` "
    "uses the dev split so extra epochs can't overfit the kept checkpoint."
))
cells.append(code(
    "import numpy as np\n"
    "from transformers import TrainingArguments, Trainer, DataCollatorForTokenClassification\n"
    "collator = DataCollatorForTokenClassification(tokenizer)\n"
    "def metrics(p):\n"
    "    preds = p.predictions[0] if isinstance(p.predictions, tuple) else p.predictions\n"
    "    preds = np.argmax(preds, axis=-1)\n"
    "    gold = p.label_ids\n"
    "    m = gold != -100\n"
    "    return {'tok_acc': float((preds[m] == gold[m]).mean())}\n"
    "args = TrainingArguments(\n"
    "    output_dir='out', learning_rate=3e-5,\n"
    "    per_device_train_batch_size=BS, per_device_eval_batch_size=BS * 2,\n"
    "    num_train_epochs=4, weight_decay=0.01, warmup_ratio=0.06,\n"
    "    bf16=USE_BF16, fp16=not USE_BF16,    # bf16 on H100/A100, fp16 on T4\n"
    "    tf32=USE_BF16,                        # TF32 matmuls on Ampere+ (no-op on T4)\n"
    "    optim='adamw_torch_fused',            # fused optimizer — faster on CUDA\n"
    "    dataloader_num_workers=2,\n"
    "    eval_strategy='epoch', save_strategy='epoch', save_total_limit=1,\n"
    "    load_best_model_at_end=True, metric_for_best_model='tok_acc', greater_is_better=True,\n"
    "    logging_steps=50, report_to='none')\n"
    "trainer = Trainer(model=model, args=args, train_dataset=tok_ds['train'],\n"
    "                  eval_dataset=tok_ds['test'], data_collator=collator,\n"
    "                  processing_class=tokenizer, compute_metrics=metrics)  # processing_class, not tokenizer=\n"
    "trainer.train()\n"
    "trainer.save_model('out_model'); tokenizer.save_pretrained('out_model')\n"
    "print('in-notebook token-accuracy is a sanity check only; the real lemma number is the\\n'\n"
    "      'local torch-free eval_spike.py on dev.jsonl')"
))

cells.append(md(
    "## 6 · Export to ONNX + int8 quantize (current optimum / onnxruntime APIs)\n"
    "`optimum-cli export onnx` then `onnxruntime.quantization.quantize_dynamic`. If quantization "
    "errors on this version, the fp32 export ships instead — `eval_spike.py` runs either."
))
cells.append(code(
    "import os\n"
    "!optimum-cli export onnx --model out_model --task token-classification onnx_fp32\n"
    "onnx_path = 'onnx_fp32/model.onnx'\n"
    "try:\n"
    "    from onnxruntime.quantization import quantize_dynamic, QuantType\n"
    "    quantize_dynamic('onnx_fp32/model.onnx', 'onnx_fp32/model_int8.onnx', weight_type=QuantType.QInt8)\n"
    "    onnx_path = 'onnx_fp32/model_int8.onnx'\n"
    "    print('int8 quantized ->', onnx_path)\n"
    "except Exception as e:\n"
    "    print('quantization skipped (' + str(e)[:160] + '); shipping fp32')\n"
    "for f in sorted(os.listdir('onnx_fp32')):\n"
    "    print(f, os.path.getsize(os.path.join('onnx_fp32', f)) // 1024, 'KB')"
))

cells.append(md("## 7 · Package + download `spike_model.zip`"))
cells.append(code(
    "import shutil\n"
    "pathlib.Path('ship').mkdir(exist_ok=True)\n"
    "shutil.copy(onnx_path, 'ship/model.onnx')\n"
    "shutil.copy('onnx_fp32/tokenizer.json', 'ship/tokenizer.json')\n"
    "shutil.copy(str(DATA / 'labels.json'), 'ship/labels.json')\n"
    "shutil.make_archive('spike_model', 'zip', 'ship')\n"
    "print('model.onnx', os.path.getsize('ship/model.onnx') // (1024 * 1024), 'MB')\n"
    "files.download('spike_model.zip')"
))

cells.append(md(
    "## Next\n"
    "Send back `spike_model.zip`. Local, torch-free:\n"
    "```\n"
    "pip install onnxruntime tokenizers numpy\n"
    "python eval_spike.py --model model.onnx --tokenizer tokenizer.json \\\n"
    "                     --labels data/labels.json --dev data/dev.jsonl\n"
    "```\n"
    "Success = **unseen lemma > 62.8%** on our own split → green-light the full multi-task backend."
))

nb["cells"] = cells
out = pathlib.Path(__file__).parent / "spike_lemma_grebert.ipynb"
nbf.write(nb, out)
print("wrote", out)
