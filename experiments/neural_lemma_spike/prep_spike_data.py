"""Prepare the data bundle for the neural-lemmatizer spike.

Reuses pyaegean's own machinery so the neural model trains and decodes over the SAME
edit-tree label set as the pure-Python lemmatizer (apples-to-apples):
  - lemmatizer.build_tree / _key  -> the edit-tree label inventory (the softmax classes)
  - syntax.load_gold_trees        -> AGDT gold (forms + lemmas + the by-sentence order)
  - heldout.split_tokens          -> the identical leakage-free dev split + seen/scored flags

Outputs (data/):
  - labels.json   {"trees": [edit-tree-key, ...]}  (label id == list index; id 0 == identity)
  - train.jsonl   one sentence/line: {"tokens": [forms], "labels": [label_id|-100]}
  - dev.jsonl     one sentence/line: {"tokens": [forms], "lemmas": [cleaned gold],
                                      "seen": [bool], "scored": [bool]}

The neural head is a token classifier over labels.json; -100 marks train tokens whose gold
edit-tree was pruned (ignored by the loss, exactly as the pure-Python reranker can't reach
them). dev.jsonl carries the gold lemma + seen flag so the local eval can reproduce
heldout's lemma_all / lemma_unseen columns.
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter

from aegean.greek import heldout, syntax
from aegean.greek import lemmatizer as L
from aegean.greek.treebank import _clean_lemma

HOLDOUT = 0.1
OUT = pathlib.Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)


def _tree_key(form: str, lemma: str) -> str:
    return L._key(L.build_tree(L._norm(form), L._norm(_clean_lemma(lemma))))


def main() -> None:
    trees = syntax.load_gold_trees()
    cut = max(1, int(len(trees) * (1 - HOLDOUT)))
    train_trees = trees[:cut]

    # Edit-tree label inventory from TRAIN tokens only (pruned like lemmatizer._train).
    counts: Counter[str] = Counter()
    for tr in train_trees:
        for t in tr.tokens:
            counts[_tree_key(t.form, t.lemma)] += 1
    kept = sorted(k for k, c in counts.items() if c >= L._MIN_TREE_COUNT and k != L._IDENTITY_KEY)
    labels = [L._IDENTITY_KEY, *kept]
    label2id = {k: i for i, k in enumerate(labels)}

    n_tok = n_lab = 0
    with (OUT / "train.jsonl").open("w", encoding="utf-8") as f:
        for tr in train_trees:
            forms = [t.form for t in tr.tokens]
            ids = []
            for t in tr.tokens:
                k = _tree_key(t.form, t.lemma)
                ids.append(label2id.get(k, -100))
                n_tok += 1
                n_lab += int(k in label2id)
            f.write(json.dumps({"tokens": forms, "labels": ids}, ensure_ascii=False) + "\n")

    sp = heldout.split_tokens(holdout=HOLDOUT)
    n_dev = n_dev_unseen = 0
    with (OUT / "dev.jsonl").open("w", encoding="utf-8") as f:
        for sent in sp.sentences:
            f.write(
                json.dumps(
                    {
                        "tokens": [tk.form for tk in sent],
                        "lemmas": [tk.lemma for tk in sent],  # already _clean_lemma'd by heldout
                        "seen": [tk.seen for tk in sent],
                        "scored": [tk.scored for tk in sent],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            for tk in sent:
                if tk.scored:
                    n_dev += 1
                    n_dev_unseen += int(not tk.seen)

    (OUT / "labels.json").open("w", encoding="utf-8").write(
        json.dumps({"trees": labels}, ensure_ascii=False)
    )

    print(f"labels (edit-trees): {len(labels)}")
    print(f"train sentences: {len(train_trees)}  tokens: {n_tok}  labeled: {n_lab} "
          f"({n_lab / n_tok:.1%}; rest -100/ignored)")
    print(f"dev scored tokens: {n_dev}  unseen: {n_dev_unseen} ({n_dev_unseen / n_dev:.1%})")
    print(f"baseline to beat — pure-Python lemma_unseen 40.3%, stanza/CLTK 62.8%")
    print("wrote:", OUT / "train.jsonl", OUT / "dev.jsonl", OUT / "labels.json")


if __name__ == "__main__":
    main()
