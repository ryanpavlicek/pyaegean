"""Build the form->lemma data bundle for the GreTa seq2seq lemmatizer.

The SOTA Ancient Greek lemmatizer (GreTa, arXiv:2410.12055) is a T5 seq2seq that
*generates* the lemma — which generalizes to unseen forms where edit-tree classification
caps out (~58%). We fine-tune the pretrained bowphs/GreTa on plain form->lemma pairs.

Train: UNIQUE (form, lemma) pairs from AGDT-train + genuinely-new, AGDT-disjoint treebanks
(Pedalion + Gorman's non-AGDT authors), deduped by sentence against ALL of AGDT so the dev
split can't leak. Dev: the identical AGDT held-out tokens (so the number stays comparable to
the edit-tree runs). Forms/lemmas are NFC (case preserved); gold lemmas are _clean_lemma'd.
"""
from __future__ import annotations

import json
import pathlib
import re
import unicodedata
from collections import Counter

from aegean.greek import heldout, syntax
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


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _fp(forms) -> tuple[str, ...]:
    return tuple(_bare(f).lower() for f in forms)


_GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")  # Greek + Greek Extended


def _ok(form: str, lemma: str) -> bool:
    return (bool(form) and bool(lemma) and len(form) <= 40 and len(lemma) <= 40
            and _GREEK.search(form) is not None)  # word-forms only (punct/numbers aren't scored)


def main() -> None:
    trees = syntax.load_gold_trees()
    cut = max(1, int(len(trees) * (1 - HOLDOUT)))
    agdt_fps = {_fp([t.form for t in tr.tokens]) for tr in trees}

    pairs: set[tuple[str, str]] = set()
    src: Counter[str] = Counter()
    for tr in trees[:cut]:
        for t in tr.tokens:
            f, lm = _nfc(t.form), _clean_lemma(t.lemma)
            if _ok(f, lm):
                pairs.add((f, lm))
                src["AGDT"] += 1
    skipped = 0
    for d in EXTRA_DIRS:
        for path in sorted(d.glob("*.xml")):
            for toks in parse_treebank(path):
                if _fp([f for f, _ in toks]) in agdt_fps:
                    skipped += 1
                    continue
                for f, lm in toks:
                    nf, nl = _nfc(f), _clean_lemma(lm)
                    if _ok(nf, nl):
                        pairs.add((nf, nl))
                        src[path.parent.name] += 1

    with (OUT / "train.jsonl").open("w", encoding="utf-8") as fh:
        for f, lm in sorted(pairs):
            fh.write(json.dumps({"form": f, "lemma": lm}, ensure_ascii=False) + "\n")

    sp = heldout.split_tokens(holdout=HOLDOUT)
    n_dev = n_un = 0
    with (OUT / "dev.jsonl").open("w", encoding="utf-8") as fh:
        for sent in sp.sentences:
            for tk in sent:
                fh.write(json.dumps({
                    "form": _nfc(tk.form), "lemma": tk.lemma,
                    "seen": tk.seen, "scored": tk.scored,
                }, ensure_ascii=False) + "\n")
                if tk.scored:
                    n_dev += 1
                    n_un += int(not tk.seen)

    print(f"unique form->lemma training pairs: {len(pairs)}  "
          f"(token contributions: {dict(src)}; {skipped} overlap sentences dropped)")
    print(f"dev tokens (per-token): scored {n_dev}, unseen {n_un}")


if __name__ == "__main__":
    main()
