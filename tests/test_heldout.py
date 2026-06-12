"""The fair, leakage-free held-out AGDT evaluator.

Offline: uses the synthetic agdt-dep fixture. NOTE the fixture is tiny (2 sentences /
8 tokens) — these tests only prove the harness runs, partitions seen/unseen correctly,
cleans gold lemmas, and excludes PUNCT/NUM. The real headline number needs the full
opt-in AGDT download.
"""

from __future__ import annotations

import pathlib

from aegean.greek import heldout

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "agdt-dep"


def test_split_partitions_seen_and_unseen() -> None:
    sp = heldout.split_tokens(source_dir=str(FIXTURE_DIR), holdout=0.5)
    # 2 fixture sentences, holdout 0.5 → 1 train / 1 dev sentence.
    assert len(sp.sentences) == 1
    toks = [t for s in sp.sentences for t in s]
    # dev sentence 2 is θεὸς/ἦν/ὁ/λόγος; only ὁ also occurs in train sentence 1.
    seen = {t.form for t in toks if t.seen}
    unseen = {t.form for t in toks if not t.seen}
    assert "ὁ" in seen
    assert {"θεὸς", "ἦν", "λόγος"} <= unseen


def test_score_returns_auditable_metrics() -> None:
    sp = heldout.split_tokens(source_dir=str(FIXTURE_DIR), holdout=0.5)
    tagger = heldout.isolated(lambda f: f, lambda f: "NOUN")  # identity lemma, constant POS
    m = heldout.score(tagger, split=sp)
    assert set(m) >= {
        "lemma_all", "pos_all", "lemma_unseen", "pos_unseen", "n_all", "n_seen", "n_unseen",
    }
    assert m["n_all"] == m["n_seen"] + m["n_unseen"]
    assert 0.0 <= m["pos_all"] <= 1.0
    assert 0.0 <= m["lemma_unseen"] <= 1.0
    # constant "NOUN" gets the two NOUN tokens (θεὸς, λόγος) but not ἦν(VERB)/ὁ(DET)
    assert 0.0 < m["pos_all"] < 1.0


def test_gold_lemmas_cleaned_and_punct_excluded() -> None:
    sp = heldout.split_tokens(source_dir=str(FIXTURE_DIR), holdout=0.5)
    toks = [t for s in sp.sentences for t in s]
    assert all(not any(ch.isdigit() for ch in t.lemma) for t in toks)  # homonym digits stripped
    assert all(t.scored == (t.upos not in {"PUNCT", "NUM"}) for t in toks)


def test_compare_scores_two_taggers_on_one_split() -> None:
    good = heldout.isolated(lambda f: f, lambda f: "NOUN")
    bad = heldout.isolated(lambda f: f, lambda f: "X")
    res = heldout.compare(good, bad, source_dir=str(FIXTURE_DIR), holdout=0.5, labels=("pyaegean", "cltk"))
    assert set(res) == {"pyaegean", "cltk"}
    assert res["pyaegean"]["pos_all"] >= res["cltk"]["pos_all"]
