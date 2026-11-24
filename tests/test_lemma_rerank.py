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


def test_rerank_analysis_and_live_pipeline_toggle_with_documentary_composition() -> None:
    from types import SimpleNamespace

    from aegean import greek
    from aegean.greek import documentary, joint
    from aegean.greek.joint import SentenceAnalysis
    from aegean.greek.lemmatize import LemmaSource

    class _FakeJointBackend:
        manifest = SimpleNamespace(
            model_id="grc-joint-test",
            dataset="grc-joint",
            manifest_sha256="a" * 64,
            tokenizer_revision="test-tok",
            annotation_profile="pyaegean-canonical-v1",
            normalization="NFC",
            segmentation="pretokenized",
            preprocessing_version="pyaegean-neural-preprocessing-v1",
        )
        runtime_variant = SimpleNamespace(
            label="compact",
            award_sha256="b" * 64,
            qualification_sha256="c" * 64,
        )
        _sess = SimpleNamespace(get_providers=lambda: ["CPUExecutionProvider"])
        lookup_form_upos = {
            "χαίρειν|VERB": "χαίρω",
            "λόγον|NOUN": "λόγος",
            "καί|CCONJ": "καί",
        }
        lookup_form = {"χαίρειν": "χαίρω", "λόγον": "λόγος"}
        lookup_lower = {"χαίρειν": "χαίρω", "λόγον": "λόγος"}

        def analyze(self, words: list[str], **_kwargs: object) -> SentenceAnalysis:
            upos = tuple("CCONJ" if w == "καί" else ("VERB" if w == "χέριν" else "NOUN") for w in words)
            xpos = tuple("b--------" if w == "καί" else "v--------" for w in words)
            feats = tuple("_" for _ in words)
            head = tuple(0 if i == 0 else 1 for i in range(len(words)))
            deprel = tuple("root" if i == 0 else "dep" for i in range(len(words)))
            lemma = tuple("καί" if w == "καί" else ("χέρις" if w == "χέριν" else "λόγος") for w in words)
            sources = tuple(
                LemmaSource.NEURAL_EDIT if w == "χέριν" else LemmaSource.NEURAL_LOOKUP
                for w in words
            )
            resolved = tuple(True for _ in words)
            return SentenceAnalysis(
                tokens=tuple(words),
                upos=upos,
                xpos=xpos,
                feats=feats,
                head=head,
                deprel=deprel,
                lemma=lemma,
                lemma_resolved=resolved,
                lemma_source=sources,
                lemma_source_path=tuple(s.value for s in sources),
                lemma_verified=tuple(False for _ in words),
            )

        def analyze_batch(self, sentences: list[list[str]], **kwargs: object) -> list[SentenceAnalysis]:
            return [self.analyze(s, **kwargs) for s in sentences]

    # Standalone rerank_analysis preserves exact lookups and rescues OOV Koine spelling.
    fake = _FakeJointBackend()
    idx = greek.TrainOnlyLemmaIndex.from_model(fake)
    raw_ana = fake.analyze(["καί", "χέριν", "λόγον"])
    reranked = greek.rerank_analysis(raw_ana, idx)
    assert reranked.lemma == ("καί", "χαίρω", "λόγος")
    assert reranked.lemma_source_path[1] == "oov_rerank:phonetic_fold_unique_upos"
    assert reranked.lemma_verified == (False, False, False)
    assert raw_ana.lemma == ("καί", "χέρις", "λόγος")  # original immutable

    # Activating with no neural backend raises NeuralPipelineNotLoadedError.
    greek.disable_oov_lemma_reranker()
    greek.disable_documentary_reconciliation()
    greek.disable_neural_pipeline()
    with pytest.raises(joint.NeuralPipelineNotLoadedError):
        greek.use_oov_lemma_reranker()

    try:
        joint._replace_active_backend(fake)
        assert greek.oov_lemma_reranker_active() is False
        assert joint.analyze_sentence(["καί", "χέριν"]).lemma == ("καί", "χέρις")

        # Enable opt-in OOV reranker
        greek.use_oov_lemma_reranker()
        assert greek.oov_lemma_reranker_active() is True
        assert joint.analyze_sentence(["καί", "χέριν"]).lemma == ("καί", "χαίρω")

        # Works cleanly with length_bucket=True batching
        batched = joint.analyze_sentences(
            [["χέριν"], ["καί", "χέριν", "λόγον"]],
            batch_size=2,
            length_bucket=True,
        )
        assert [a.lemma for a in batched] == [("χαίρω",), ("καί", "χαίρω", "λόγος")]

        # Stream snapshot freezes the active reranker even if disabled mid-stream
        stream = joint.iter_analyze_sentences([["χέριν"], ["χέριν"]])
        first = next(stream)
        assert first.lemma == ("χαίρω",)
        greek.disable_oov_lemma_reranker()
        second = next(stream)
        assert second.lemma == ("χαίρω",)
        assert joint.analyze_sentence(["χέριν"]).lemma == ("χέρις",)

        # Composes cleanly with documentary reconciliation in either disable order
        greek.use_oov_lemma_reranker()
        documentary.use_documentary_reconciliation()
        assert greek.oov_lemma_reranker_active() is True
        assert documentary.documentary_reconciliation_active() is True
        greek.disable_oov_lemma_reranker()
        assert greek.oov_lemma_reranker_active() is False
        assert documentary.documentary_reconciliation_active() is True
        assert joint.analyze_sentence(["χέριν"]).lemma == ("χέρις",)
        documentary.disable_documentary_reconciliation()
        assert joint.active() is fake
    finally:
        greek.disable_oov_lemma_reranker()
        documentary.disable_documentary_reconciliation()
        greek.disable_neural_pipeline()
