"""Build the MULTI-TASK, MULTI-TREEBANK data bundle for the neural-lemma spike.

Per token it now emits the lemma edit-tree label PLUS auxiliary morphosyntactic labels —
UPOS and 7 morph dimensions (case/number/gender/tense/mood/voice/person) — so the encoder
can be trained to represent the morphology that *determines* the lemma. Auxiliary labels are
`-100` (ignored by the loss) where a feature is absent for that token.

Data: AGDT (train 90% / dev 10%, dev unchanged) + genuinely-NEW, AGDT-disjoint treebanks
(Pedalion + Gorman's non-AGDT authors), with the same bare-form dedup guard against ALL of
AGDT so the held-out dev split cannot leak. dev.jsonl carries only lemma/seen/scored — we
still evaluate lemma only.
"""
from __future__ import annotations

import json
import pathlib
import re
from collections import Counter

from aegean.greek import heldout, syntax
from aegean.greek import lemmatizer as L
from aegean.greek.morphology import _bare
from aegean.greek.treebank import _clean_lemma, decode_postag

HOLDOUT = 0.1
OUT = pathlib.Path(__file__).parent / "data"
TMP = pathlib.Path(r"C:\Users\Ryan.Pavlicek\AppData\Local\Temp\multitreebank")
EXTRA_DIRS = [TMP / "pedalion", TMP / "gorman"]

# (output-field-name, decode_postag key)
DIMS = [
    ("upos", "pos"), ("case", "case"), ("number", "number"), ("gender", "gender"),
    ("tense", "tense"), ("mood", "mood"), ("voice", "voice"), ("person", "person"),
]

_WORD = re.compile(r"<word\b[^>]*>")


def _attr(tag: str, name: str) -> str | None:
    m = re.search(name + r"=(['\"])(.*?)\1", tag)
    return m.group(2) if m else None


def parse_treebank(path: pathlib.Path):
    """Yield [(form, lemma, postag), ...] per sentence — tolerant of malformed headers."""
    text = path.read_text(encoding="utf-8", errors="replace")
    for chunk in re.split(r"<sentence\b", text)[1:]:
        chunk = chunk.split("</sentence>")[0]
        toks = []
        for wm in _WORD.finditer(chunk):
            tag = wm.group(0)
            form, lemma = _attr(tag, "form"), _attr(tag, "lemma")
            if form and lemma and not form.startswith("["):
                toks.append((form, lemma, _attr(tag, "postag") or ""))
        if toks:
            yield toks


def _fp(forms) -> tuple[str, ...]:
    return tuple(_bare(f).lower() for f in forms)


def _tree_key(form: str, lemma: str) -> str:
    return L._key(L.build_tree(L._norm(form), L._norm(_clean_lemma(lemma))))


def main() -> None:
    trees = syntax.load_gold_trees()
    cut = max(1, int(len(trees) * (1 - HOLDOUT)))
    agdt_train = trees[:cut]
    agdt_fps = {_fp([t.form for t in tr.tokens]) for tr in trees}

    # Training tokens as (form, lemma, postag), from AGDT-train + deduped extra treebanks.
    train_sents: list[list[tuple[str, str, str]]] = [
        [(t.form, t.lemma, t.postag) for t in tr.tokens] for tr in agdt_train
    ]
    n_agdt = sum(len(s) for s in train_sents)
    skipped = 0
    per_source: Counter[str] = Counter()
    for d in EXTRA_DIRS:
        for path in sorted(d.glob("*.xml")):
            for toks in parse_treebank(path):
                if _fp([f for f, _, _ in toks]) in agdt_fps:
                    skipped += 1
                    continue
                train_sents.append(toks)
                per_source[path.stem] += 1
    n_extra = sum(len(s) for s in train_sents) - n_agdt

    # Vocabularies. Lemma edit-trees: prune to count >= _MIN_TREE_COUNT (+ identity).
    tree_counts: Counter[str] = Counter()
    dim_vals: dict[str, set[str]] = {name: set() for name, _ in DIMS}
    for sent in train_sents:
        for form, lemma, postag in sent:
            tree_counts[_tree_key(form, lemma)] += 1
            feats = decode_postag(postag)
            for name, key in DIMS:
                if key in feats:
                    dim_vals[name].add(feats[key])
    kept = sorted(k for k, c in tree_counts.items() if c >= L._MIN_TREE_COUNT and k != L._IDENTITY_KEY)
    trees_vocab = [L._IDENTITY_KEY, *kept]
    tree2id = {k: i for i, k in enumerate(trees_vocab)}
    dim_vocab = {name: sorted(vals) for name, vals in dim_vals.items()}
    dim2id = {name: {v: i for i, v in enumerate(vocab)} for name, vocab in dim_vocab.items()}

    with (OUT / "train.jsonl").open("w", encoding="utf-8") as f:
        for sent in train_sents:
            row: dict[str, list] = {"tokens": [t[0] for t in sent]}
            row["lemma"] = [tree2id.get(_tree_key(t[0], t[1]), -100) for t in sent]
            feats_list = [decode_postag(t[2]) for t in sent]
            for name, key in DIMS:
                row[name] = [dim2id[name].get(ft[key], -100) if key in ft else -100 for ft in feats_list]
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    sp = heldout.split_tokens(holdout=HOLDOUT)  # AGDT dev, identical to prior runs
    with (OUT / "dev.jsonl").open("w", encoding="utf-8") as f:
        for sent in sp.sentences:
            f.write(json.dumps({
                "tokens": [tk.form for tk in sent],
                "lemmas": [tk.lemma for tk in sent],
                "seen": [tk.seen for tk in sent],
                "scored": [tk.scored for tk in sent],
            }, ensure_ascii=False) + "\n")

    (OUT / "labels.json").open("w", encoding="utf-8").write(
        json.dumps({"trees": trees_vocab, **dim_vocab}, ensure_ascii=False))

    print(f"lemma edit-trees: {len(trees_vocab)}")
    print("aux head sizes:", {name: len(v) for name, v in dim_vocab.items()})
    print(f"train tokens: {n_agdt + n_extra}  (AGDT {n_agdt} + extra {n_extra}; {skipped} overlap sentences dropped)")
    print(f"dev unchanged: {sum(1 for s in sp.sentences for t in s if t.scored)} scored tokens")


if __name__ == "__main__":
    main()
