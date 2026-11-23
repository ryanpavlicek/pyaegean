"""Offline tests for OOV-gated Greek lemma candidate generation and reranking."""

from __future__ import annotations

import pytest

from aegean.greek.lemma_rerank import (
    FEATURE_NAMES,
    LemmaRerankerConfig,
    TrainOnlyLemmaIndex,
    documentary_phonetic_fold,
    extract_oov_candidates,
    fit_oov_reranker,
    preverb_candidates,
    rerank_candidates,
    rerank_oov_unique,
    score_candidates,
    strict_fold,
)


def _sample_index() -> TrainOnlyLemmaIndex:
    return TrainOnlyLemmaIndex.from_lookup_tables(
        lookup_form_upos={
            "χαίρειν|VERB": "χαίρω",
            "λόγον|NOUN": "λόγος",
            "γράφω|VERB": "γράφω",
            "γέγραφα|VERB": "γράφω",
            "κατέγραψεν|VERB": "καταγράφω",
            "καταγράφω|VERB": "καταγράφω",
            "τιμήν|NOUN": "τιμή",
            "πόλιν|NOUN": "πόλις",
            "βασιλέως|NOUN": "βασιλεύς",
        },
        lookup_lower={
            "χαίρειν": "χαίρω",
            "λόγον": "λόγος",
            "καταγράφω": "καταγράφω",
            "γράφω": "γράφω",
        },
    )


def test_strict_and_documentary_phonetic_folds() -> None:
    # Accent, lunate sigma, final sigma, iota subscript, and Leiden underdot folding
    assert strict_fold("λ̣όγοϲ") == "λογοσ"
    assert strict_fold("τῇ") == "τηι"
    assert strict_fold("ΒΑΣΙΛΕΩΣ") == "βασιλεωσ"

    # Koine itacism (ει/η/ι/οι/υ), αι->ε, ω->ο, degemination, and optional final -ν
    assert documentary_phonetic_fold("χαίρειν") == documentary_phonetic_fold("χέριν")
    assert documentary_phonetic_fold("τιμήν") == documentary_phonetic_fold("τειμί")
    assert documentary_phonetic_fold("γράμματα") == documentary_phonetic_fold("γράματα")
    assert documentary_phonetic_fold("λόγων") == documentary_phonetic_fold("λόγον")


def test_oov_unique_rescue_helps_koine_spelling_and_never_touches_exact_lookup() -> None:
    idx = _sample_index()

    # Exact neural_lookup tokens must NEVER be modified (zero lookup harm invariant).
    kept = rerank_oov_unique(
        form="χέριν",
        upos="VERB",
        baseline_lemma="other_lemma",
        baseline_source="neural_lookup",
        index=idx,
    )
    assert kept.lemma == "other_lemma"
    assert kept.changed is False
    assert kept.route == "exact_lookup"

    # OOV itacistic papyrus spelling χέριν -> χαίρω via unique phonetic fold.
    rescued = rerank_oov_unique(
        form="χέριν",
        upos="VERB",
        baseline_lemma="χέρις",
        baseline_source="neural_edit",
        index=idx,
    )
    assert rescued.lemma == "χαίρω"
    assert rescued.changed is True
    assert "phonetic_fold_unique" in rescued.route

    # Underdotted/accent-missing form λογος -> λόγος via unique strict fold.
    strict_hit = rerank_oov_unique(
        form="λ̣ογον",
        upos="NOUN",
        baseline_lemma="λογο",
        baseline_source="neural_edit",
        index=idx,
    )
    assert strict_hit.lemma == "λόγος"
    assert strict_hit.changed is True
    assert "strict_fold_unique" in strict_hit.route


def test_equivalent_edit_marginalization_and_preverb_recovery() -> None:
    idx = _sample_index()
    assert "καταγράφω" in preverb_candidates("κατέγραψα", "VERB", idx) or "καταγράφω" in preverb_candidates("κατεγραφω", "VERB", idx)

    cands = extract_oov_candidates(
        form="χέριν",
        upos="VERB",
        baseline_lemma="χέρις",
        baseline_source="neural_edit",
        index=idx,
        top_edit_predictions=[
            ("χέρις", 0.30),
            ("χαίρω", 0.22),
            ("χαίρω", 0.25),  # second distinct edit script producing the same lemma
        ],
    )
    by_lem = {c.lemma: c for c in cands}
    assert "χαίρω" in by_lem
    assert by_lem["χαίρω"].edit_prob_sum == pytest.approx(0.47)
    assert by_lem["χαίρω"].best_edit_rank == 2
    assert "phonetic_fold" in by_lem["χαίρω"].routes
    assert "neural_edit" in by_lem["χαίρω"].routes
    assert len(by_lem["χαίρω"].features) == len(FEATURE_NAMES)


def test_fit_oov_reranker_config_roundtrip_and_oov_gating() -> None:
    idx = _sample_index()
    examples = []
    # Synthetic training examples where phonetic_unique candidate is gold
    for form, upos, wrong, gold in (
        ("χέριν", "VERB", "χέρις", "χαίρω"),
        ("τειμί", "NOUN", "τειμίς", "τιμή"),
        ("λ̣ογον", "NOUN", "λογο", "λόγος"),
    ) * 5:
        cands = extract_oov_candidates(
            form=form,
            upos=upos,
            baseline_lemma=wrong,
            baseline_source="neural_edit",
            index=idx,
            top_edit_predictions=[(wrong, 0.55), (gold, 0.20)],
        )
        examples.append((cands, gold))

    cfg = fit_oov_reranker(examples, l2=0.5, max_iter=100, oov_only=True)
    # Round-trip JSON + SHA-256 verification
    reloaded = LemmaRerankerConfig.from_dict(cfg.to_dict())
    assert reloaded == cfg

    tampered = dict(cfg.to_dict())
    tampered["weights"] = [0.0] * len(FEATURE_NAMES)
    with pytest.raises(ValueError, match="sha256 mismatch"):
        LemmaRerankerConfig.from_dict(tampered)

    # Reranker selects gold on OOV example
    test_cands = extract_oov_candidates(
        form="χέριν",
        upos="VERB",
        baseline_lemma="χέρις",
        baseline_source="neural_edit",
        index=idx,
        top_edit_predictions=[("χέρις", 0.55), ("χαίρω", 0.20)],
    )
    ranked = score_candidates(test_cands, reloaded)
    assert sum(p for _, p in ranked) == pytest.approx(1.0)
    decision = rerank_candidates(
        candidates=test_cands,
        baseline_lemma="χέρις",
        baseline_source="neural_edit",
        config=reloaded,
    )
    assert decision.lemma == "χαίρω"
    assert decision.changed is True
    assert decision.posterior is not None and decision.posterior > 0.5

    # OOV-gating still protects exact neural_lookup tokens
    protected = rerank_candidates(
        candidates=test_cands,
        baseline_lemma="χέρις",
        baseline_source="neural_lookup",
        config=reloaded,
    )
    assert protected.lemma == "χέρις"
    assert protected.changed is False
    assert protected.route == "exact_lookup"
