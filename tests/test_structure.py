"""Heuristic tablet-structure classification (port of TabletStructure's
heuristicKey). No workbench *.test.ts exists for this; these assert the
documented precedence directly and run it over the real corpus."""

from __future__ import annotations

import aegean
from aegean.analysis import CATEGORIES, classify_corpus, classify_structure
from aegean.core.model import Document, DocumentMeta
from aegean.scripts.lineara.loader import classify

_SEP = "\U00010101"


def doc(words: list[str]) -> Document:
    tokens = [classify(w, 0, i) for i, w in enumerate(words)]
    return Document(
        id="X",
        script_id="lineara",
        tokens=tokens,
        lines=[list(range(len(tokens)))] if tokens else [],
        meta=DocumentMeta(site="HT"),
    )


def test_accounting_by_kuro():
    assert classify_structure(doc(["DA-RO", "KU-RO", "5"])) == "accounting"


def test_accounting_by_numerals_and_multi():
    # numerals + more than two multi-sign words, no KU-RO
    assert classify_structure(doc(["A-B", "C-D", "E-F", "10"])) == "accounting"


def test_libation():
    assert classify_structure(doc(["JA-SA-SA-RA-ME", "A-DI"])) == "libation"


def test_kuro_outranks_libation():
    # accounting precedence is checked before libation
    assert classify_structure(doc(["JA-SA-SA-RA-ME", "KU-RO"])) == "accounting"


def test_list_by_separators():
    words = ["A-B", _SEP, "C-D", _SEP, "E-F", _SEP, "G-H", _SEP]
    assert classify_structure(doc(words)) == "list"


def test_text_extended_no_numerals():
    words = ["A-B", "C-D", "E-F", "G-H", "I-J"]  # 5 multi-sign words, no numerals
    assert classify_structure(doc(words)) == "text"


def test_other_short():
    assert classify_structure(doc(["A-B"])) == "other"


def test_classify_corpus_partitions_all_docs():
    corpus = aegean.load("lineara")
    buckets = classify_corpus(corpus)
    # Every category key present, and the partition covers the whole corpus.
    assert set(buckets) == {c.key for c in CATEGORIES}
    assert sum(len(v) for v in buckets.values()) == len(corpus)
    # Accounting is the dominant Linear A genre — sanity check it's well populated.
    assert len(buckets["accounting"]) > 100
