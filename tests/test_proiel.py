"""Tests for the PROIEL out-of-AGDT neutral evaluator (offline; uses a local fixture).

The real evaluation downloads the PROIEL Greek treebank (CC BY-NC-SA, eval-only) — these
tests exercise the parser, lemma/POS normalization, and scoring on a small local fixture,
so they run with no network (like the AGDT held-out and syntax tests)."""

from __future__ import annotations

from pathlib import Path

from aegean.greek.proiel import evaluate_on_proiel, load_proiel_gold

FIXTURE = str(Path(__file__).parent / "fixtures" / "proiel")


def test_load_gold_parses_tokens_and_skips_empties() -> None:
    sents = load_proiel_gold(source_dir=FIXTURE)
    assert len(sents) == 2
    s0 = sents[0]
    assert len(s0) == 2  # the empty/null token (no form/lemma) is dropped
    assert [t.form for t in s0] == ["Βίβλος", "Ἰησοῦ"]
    assert [t.lemma for t in s0] == ["βίβλος", "Ἰησοῦς"]  # surface form vs lemma
    assert all(t.seen is False for s in sents for t in s)  # PROIEL is wholly unseen


def test_homograph_suffix_stripped() -> None:
    lemmas = [t.lemma for s in load_proiel_gold(source_dir=FIXTURE) for t in s]
    assert "εἰμί" in lemmas and "καί" in lemmas  # εἰμί#1 / καί#1 → suffix removed
    assert not any("#" in lemma for lemma in lemmas)


def test_pos_reconciled_to_pyaegean_tagset() -> None:
    by_form = {t.form: t.upos for s in load_proiel_gold(source_dir=FIXTURE) for t in s}
    assert by_form["Ἰησοῦ"] == "NOUN"  # Ne (proper noun → PROPN) collapsed to NOUN
    assert by_form["ὅτι"] == "CCONJ"  # G- (subjunction → SCONJ) collapsed to CCONJ
    assert by_form["ἐστιν"] == "VERB"


def test_evaluate_perfect_tagger_scores_one() -> None:
    gold = {t.form: (t.lemma, t.upos) for s in load_proiel_gold(source_dir=FIXTURE) for t in s}

    def perfect(forms: list[str]) -> list[tuple[str, str]]:
        return [gold[f] for f in forms]

    r = evaluate_on_proiel(perfect, source_dir=FIXTURE)
    assert r["lemma"] == 1.0 and r["pos"] == 1.0
    assert r["n"] == 5  # five word tokens (none are PUNCT/NUM)


def test_pos_reconciliation_is_symmetric() -> None:
    # A tagger that emits NOUN for the proper noun (pyaegean's convention) must score
    # correct — PROPN is reconciled to NOUN on the gold side too, not penalized.
    gold = {t.form: (t.lemma, t.upos) for s in load_proiel_gold(source_dir=FIXTURE) for t in s}

    def noun_for_propn(forms: list[str]) -> list[tuple[str, str]]:
        return [(gold[f][0], "NOUN" if f == "Ἰησοῦ" else gold[f][1]) for f in forms]

    assert evaluate_on_proiel(noun_for_propn, source_dir=FIXTURE)["pos"] == 1.0


def test_evaluate_wrong_tagger_scores_zero() -> None:
    def wrong(forms: list[str]) -> list[tuple[str, str]]:
        return [("ERR", "X") for _ in forms]

    r = evaluate_on_proiel(wrong, source_dir=FIXTURE)
    assert r["lemma"] == 0.0 and r["pos"] == 0.0
