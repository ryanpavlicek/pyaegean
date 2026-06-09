"""Build the MULTI-TREEBANK data bundle for the neural-lemma spike.

AGDT (train 90% / dev 10%, dev unchanged) + genuinely-NEW treebanks that AGDT does not
contain — Pedalion (Euripides, Menander, Lucian, Septuagint, papyri, ...) and Gorman's
non-AGDT authors (Demosthenes, Xenophon) — added to TRAINING only.

Leakage guard (load-bearing): AGDT already contains Thucydides/Herodotus/Lysias/Athenaeus/
Diodorus/Polybius/Plutarch, so any added sentence is DROPPED if its bare-form fingerprint
matches ANY AGDT sentence (train or dev). The dev set stays the identical AGDT held-out
10%, so the number is directly comparable to the AGDT-only run (53.4% unseen).

Sources are git-ignored scratch under %TEMP%/multitreebank. Outputs overwrite data/.
"""
from __future__ import annotations

import json
import pathlib
import re
from collections import Counter

from aegean.greek import heldout, syntax
from aegean.greek import lemmatizer as L
from aegean.greek.morphology import _bare
from aegean.greek.treebank import _clean_lemma

HOLDOUT = 0.1
OUT = pathlib.Path(__file__).parent / "data"
TMP = pathlib.Path(r"C:\Users\Ryan.Pavlicek\AppData\Local\Temp\multitreebank")
EXTRA_DIRS = [TMP / "pedalion", TMP / "gorman"]

_WORD = re.compile(r"<word\b[^>]*>")


def _attr(tag: str, name: str) -> str | None:
    m = re.search(name + r"=(['\"])(.*?)\1", tag)
    return m.group(2) if m else None


def parse_treebank(path: pathlib.Path):
    """Yield [(form, lemma), ...] per sentence — regex-based, tolerant of malformed headers."""
    text = path.read_text(encoding="utf-8", errors="replace")
    for chunk in re.split(r"<sentence\b", text)[1:]:
        chunk = chunk.split("</sentence>")[0]
        toks = []
        for wm in _WORD.finditer(chunk):
            tag = wm.group(0)
            form, lemma = _attr(tag, "form"), _attr(tag, "lemma")
            if form and lemma and not form.startswith("["):
                toks.append((form, lemma))
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
    agdt_fps = {_fp([t.form for t in tr.tokens]) for tr in trees}  # dedup vs ALL AGDT

    extra: list[list[tuple[str, str]]] = []
    skipped = 0
    per_source: Counter[str] = Counter()
    for d in EXTRA_DIRS:
        for path in sorted(d.glob("*.xml")):
            kept_here = 0
            for toks in parse_treebank(path):
                if _fp([f for f, _ in toks]) in agdt_fps:
                    skipped += 1
                    continue
                extra.append(toks)
                kept_here += 1
            per_source[path.stem] = kept_here

    # Combined edit-tree label inventory (AGDT-train + extra), pruned like lemmatizer._train.
    counts: Counter[str] = Counter()
    for tr in agdt_train:
        for t in tr.tokens:
            counts[_tree_key(t.form, t.lemma)] += 1
    for toks in extra:
        for f, lem in toks:
            counts[_tree_key(f, lem)] += 1
    kept = sorted(k for k, c in counts.items() if c >= L._MIN_TREE_COUNT and k != L._IDENTITY_KEY)
    labels = [L._IDENTITY_KEY, *kept]
    label2id = {k: i for i, k in enumerate(labels)}

    n_agdt = n_extra = 0
    with (OUT / "train.jsonl").open("w", encoding="utf-8") as f:
        for tr in agdt_train:
            forms = [t.form for t in tr.tokens]
            ids = [label2id.get(_tree_key(t.form, t.lemma), -100) for t in tr.tokens]
            f.write(json.dumps({"tokens": forms, "labels": ids}, ensure_ascii=False) + "\n")
            n_agdt += len(forms)
        for toks in extra:
            forms = [x[0] for x in toks]
            ids = [label2id.get(_tree_key(x[0], x[1]), -100) for x in toks]
            f.write(json.dumps({"tokens": forms, "labels": ids}, ensure_ascii=False) + "\n")
            n_extra += len(forms)

    sp = heldout.split_tokens(holdout=HOLDOUT)  # AGDT dev, identical to the AGDT-only run
    with (OUT / "dev.jsonl").open("w", encoding="utf-8") as f:
        for sent in sp.sentences:
            f.write(json.dumps({
                "tokens": [tk.form for tk in sent],
                "lemmas": [tk.lemma for tk in sent],
                "seen": [tk.seen for tk in sent],
                "scored": [tk.scored for tk in sent],
            }, ensure_ascii=False) + "\n")

    (OUT / "labels.json").open("w", encoding="utf-8").write(
        json.dumps({"trees": labels}, ensure_ascii=False))

    print(f"labels (edit-trees): {len(labels)}  (was 9069 on AGDT-only)")
    print(f"AGDT-train tokens: {n_agdt}")
    print(f"extra tokens kept: {n_extra}  across {len([k for k in per_source if per_source[k]])} files; "
          f"{skipped} sentences dropped as AGDT overlap")
    print(f"TOTAL train tokens: {n_agdt + n_extra}  ({(n_agdt + n_extra) / n_agdt:.2f}x AGDT-only)")
    print("per source (sentences kept):", dict(per_source))
    print(f"dev unchanged: {sum(1 for s in sp.sentences for t in s if t.scored)} scored tokens")


if __name__ == "__main__":
    main()
