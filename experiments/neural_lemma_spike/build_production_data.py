"""Build the SHIPPABLE production lemmatizer data.

Now that measurement is done, the shipped model trains on ALL gold (no held-out split) and
on gold ONLY — Wiktionary and the recipe tweaks tested negative (see README's experiment
ledger). Two outputs feed the production bundle:

  prod_train.jsonl  — unique {form, lemma} over all AGDT + Pedalion + Gorman (the 76.3% recipe,
                      trained on everything since there is no dev split to protect in production).
  lookup.json.gz    — {form: majority_lemma} over the same gold tokens; the hybrid answers seen
                      forms from this table and only generates for the rest.
"""
from __future__ import annotations

import gzip
import json
import pathlib
from collections import Counter, defaultdict

from aegean.greek import syntax
from aegean.greek.treebank import _clean_lemma

from build_seq2seq_data import EXTRA_DIRS, _nfc, _ok, parse_treebank

OUT = pathlib.Path(__file__).parent / "data"


def main() -> None:
    pairs: set[tuple[str, str]] = set()
    lemma_counts: dict[str, Counter[str]] = defaultdict(Counter)
    n_tokens = 0

    def add(form: str, lemma: str) -> None:
        nonlocal n_tokens
        n_tokens += 1
        f, lm = _nfc(form), _clean_lemma(lemma)
        if _ok(f, lm):
            pairs.add((f, lm))
            lemma_counts[f][lm] += 1

    for tr in syntax.load_gold_trees():  # ALL of AGDT (no holdout)
        for t in tr.tokens:
            add(t.form, t.lemma)
    for d in EXTRA_DIRS:
        for path in sorted(d.glob("*.xml")):
            for toks in parse_treebank(path):
                for f, lm in toks:
                    add(f, lm)

    lookup = {form: counts.most_common(1)[0][0] for form, counts in lemma_counts.items()}

    OUT.mkdir(exist_ok=True)
    with (OUT / "prod_train.jsonl").open("w", encoding="utf-8") as fh:
        for f, lm in sorted(pairs):
            fh.write(json.dumps({"form": f, "lemma": lm}, ensure_ascii=False) + "\n")
    with gzip.open(OUT / "lookup.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(lookup, fh, ensure_ascii=False)

    print(f"production data: {len(pairs)} unique pairs from {n_tokens} gold tokens; "
          f"lookup covers {len(lookup)} forms")


if __name__ == "__main__":
    main()
