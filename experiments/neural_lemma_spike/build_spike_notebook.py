"""Build spike_lemma_grebert.ipynb (run once: `python build_spike_notebook.py`)."""
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
    "**Loop:** set runtime to **GPU** (Runtime → Change runtime type → T4) → Run all → "
    "download `spike_model.zip` at the end → send it back for the torch-free local eval.\n"
    "\n"
    "Encoder: `bowphs/GreBerta` (Apache-2.0, monolingual Ancient Greek RoBERTa). torch/transformers "
    "are used **only here in Colab**; production inference is onnxruntime-only."
))

cells.append(code(
    "!nvidia-smi -L  # confirm a GPU is attached (T4 is plenty)\n"
    "%pip -q install 'transformers>=4.40' 'datasets>=2.19' 'optimum[onnxruntime]>=1.20' "
    "'accelerate>=0.30' onnx onnxruntime"
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
    "Standard token-classification alignment: label only the first sub-token of each word, "
    "`-100` (ignored by the loss) elsewhere — matching the local eval's first-subword pooling."
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
    "tok_ds = tok_ds.train_test_split(test_size=0.02, seed=0)  # tiny in-notebook sanity split\n"
    "print(tok_ds)"
))

cells.append(md("## 5 · Fine-tune (≈3 epochs; a few GPU-minutes to ~1–2 h on T4)"))
cells.append(code(
    "import numpy as np\n"
    "from transformers import TrainingArguments, Trainer, DataCollatorForTokenClassification\n"
    "collator = DataCollatorForTokenClassification(tokenizer)\n"
    "def metrics(p):\n"
    "    preds = np.argmax(p.predictions, axis=-1)\n"
    "    gold = p.label_ids\n"
    "    m = gold != -100\n"
    "    return {'tok_acc': float((preds[m] == gold[m]).mean())}\n"
    "args = TrainingArguments(\n"
    "    output_dir='out', learning_rate=3e-5, per_device_train_batch_size=16,\n"
    "    per_device_eval_batch_size=32, num_train_epochs=3, weight_decay=0.01,\n"
    "    fp16=True, eval_strategy='epoch', save_strategy='no', logging_steps=100, report_to=[])\n"
    "trainer = Trainer(model=model, args=args, train_dataset=tok_ds['train'],\n"
    "                  eval_dataset=tok_ds['test'], data_collator=collator,\n"
    "                  tokenizer=tokenizer, compute_metrics=metrics)\n"
    "trainer.train()\n"
    "trainer.save_model('out_model'); tokenizer.save_pretrained('out_model')\n"
    "print('in-notebook token-accuracy is a sanity check only; the real lemma number is the\\n'\n"
    "      'local torch-free eval_spike.py on dev.jsonl')"
))

cells.append(md(
    "## 6 · Export to ONNX + int8 quantize\n"
    "If quantization errors out on the Colab optimum version, skip it and ship the fp32 "
    "`model.onnx` — `eval_spike.py` runs either."
))
cells.append(code(
    "from optimum.onnxruntime import ORTModelForTokenClassification\n"
    "ort_model = ORTModelForTokenClassification.from_pretrained('out_model', export=True)\n"
    "ort_model.save_pretrained('onnx_fp32')\n"
    "tokenizer.save_pretrained('onnx_fp32')\n"
    "out_dir = 'onnx_fp32'\n"
    "try:\n"
    "    from optimum.onnxruntime import ORTQuantizer\n"
    "    from optimum.onnxruntime.configuration import AutoQuantizationConfig\n"
    "    q = ORTQuantizer.from_pretrained('onnx_fp32')\n"
    "    q.quantize(save_dir='onnx_int8',\n"
    "               quantization_config=AutoQuantizationConfig.avx2(is_static=False, per_channel=False))\n"
    "    tokenizer.save_pretrained('onnx_int8')\n"
    "    out_dir = 'onnx_int8'\n"
    "    print('int8 quantized ->', out_dir)\n"
    "except Exception as e:\n"
    "    print('quantization skipped (' + str(e)[:120] + '); shipping fp32')\n"
    "import os\n"
    "for f in os.listdir(out_dir):\n"
    "    print(f, os.path.getsize(os.path.join(out_dir, f)) // 1024, 'KB')"
))

cells.append(md("## 7 · Package + download `spike_model.zip`"))
cells.append(code(
    "import glob, shutil\n"
    "onnx_file = sorted(glob.glob(out_dir + '/*.onnx'), key=os.path.getsize)[-1]\n"
    "pathlib.Path('ship').mkdir(exist_ok=True)\n"
    "shutil.copy(onnx_file, 'ship/model.onnx')\n"
    "shutil.copy(out_dir + '/tokenizer.json', 'ship/tokenizer.json')\n"
    "shutil.copy(str(DATA / 'labels.json'), 'ship/labels.json')\n"
    "shutil.make_archive('spike_model', 'zip', 'ship')\n"
    "print('model.onnx', os.path.getsize('ship/model.onnx') // (1024*1024), 'MB')\n"
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
