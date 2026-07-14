"""Correctness tests for the two opt-in documentary-Koine levers (`aegean.greek.documentary`).

Both levers are opt-in post-processing layers over the neural pipeline. These tests never load
the 173 MB model: they exercise the pure lever functions on hand-built `SentenceAnalysis`
values (so every assertion checks the transformed OUTPUT against a known-correct answer) and
the toggle/wrapper lifecycle against a tiny fake model installed as ``joint._ACTIVE``.

Covered: default-off byte-identity; Lever A fires only on the closed coordinator set AND a
wrong model label (and its conservative-vs-aggressive boundary, plus the ἀλλά/ἄλλα and ἤ/ἡ
accent-collision safety); Lever B never overrides a resolved lemma and carries its own offline
evidence class (SEED / PARADIGM, never NEURAL; the ending rules deliberately excluded); the toggle on/off round-trip restores
byte-identical output.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from aegean.greek import documentary as D
from aegean.greek import joint, paradigms
from aegean.greek.confidence import (
    AbstentionPolicy,
    ConfidenceResult,
    SentenceConfidence,
    TokenConfidence,
)
from aegean.greek.joint import SentenceAnalysis
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.paradigms import ParadigmLexicon


# --- a tiny fake joint model (no ONNX, no 173 MB fetch) ------------------------------------


class _FakeModel:
    """Minimal stand-in for `joint._JointModel`: returns a caller-supplied analysis and carries
    an arbitrary attribute to prove the wrapper delegates unknown attributes."""

    def __init__(self, analysis: SentenceAnalysis) -> None:
        self._analysis = analysis
        self.lookup_form = {"marker": "sentinel"}  # an arbitrary delegated attribute

    def analyze(self, words: list[str], *, with_probs: bool = False) -> SentenceAnalysis:
        return self._analysis

    def analyze_batch(
        self, sentences: list[list[str]], *, with_probs: bool = False
    ) -> list[SentenceAnalysis]:
        return [self._analysis for _ in sentences]


def _analysis(
    tokens, upos, xpos, lemma, resolved
) -> SentenceAnalysis:
    n = len(tokens)
    return SentenceAnalysis(
        tokens=tuple(tokens),
        upos=tuple(upos),
        xpos=tuple(xpos),
        feats=tuple("_" for _ in range(n)),
        head=tuple(0 if i == 0 else 1 for i in range(n)),
        deprel=tuple("root" if i == 0 else "dep" for i in range(n)),
        lemma=tuple(lemma),
        lemma_resolved=tuple(resolved),
    )


def _confidence(task: str) -> ConfidenceResult:
    return ConfidenceResult(
        task=task,
        value=0.8,
        calibration_id="a" * 64,
        scope="exact",
        model="test-model",
        source="neural",
        domain="papyri",
        n=10,
        ece=0.1,
    )


def _with_confidence(ana: SentenceAnalysis) -> SentenceAnalysis:
    tasks = ("upos", "xpos", "feats", "lemma")
    policy = AbstentionPolicy({task: 0.5 for task in (*tasks, "sentence")})
    tokens = tuple(
        TokenConfidence(
            index=index,
            upos=_confidence("upos"),
            xpos=_confidence("xpos"),
            feats=_confidence("feats"),
            lemma=_confidence("lemma"),
            policy=tuple(policy.decide(task, 0.8) for task in tasks),
        )
        for index in range(len(ana.tokens))
    )
    sentence_result = _confidence("sentence")
    return replace(
        ana,
        token_confidences=tokens,
        sentence_confidence=SentenceConfidence(
            sentence_result,
            ("upos", "xpos", "lemma"),
            policy.decide("sentence", sentence_result.value),
        ),
    )


@pytest.fixture(autouse=True)
def _clean_state():
    """Every test starts and ends with all levers off and no model installed."""
    D.disable_documentary_reconciliation()
    D.disable_documentary_lemma_rescue()
    saved = joint._ACTIVE
    saved_par = paradigms._ACTIVE
    joint._ACTIVE = None
    paradigms._ACTIVE = None
    yield
    D.disable_documentary_reconciliation()
    D.disable_documentary_lemma_rescue()
    joint._ACTIVE = saved
    paradigms._ACTIVE = saved_par


# --- the closed coordinator set + its normalization ---------------------------------------


def test_coordinator_set_members_and_size():
    """The closed set is the nine coordinating conjunctions (Smyth §2163 ff.) plus the seven
    standard elided forms — and nothing else."""
    for citation in ("καί", "δέ", "τε", "ἀλλά", "ἤ", "οὐδέ", "οὔτε", "μηδέ", "μήτε"):
        assert D.coordinator_norm(citation) in D.COORDINATORS
    assert len(D.COORDINATORS) == 16  # 9 citation + 7 elided


@pytest.mark.parametrize(
    "surface,expected",
    [
        ("καὶ", True),        # running-text grave folds to the acute citation
        ("κα̣ὶ", True),        # Leiden underdot stripped
        ("δʼ", True),          # modifier-apostrophe elision
        ("δ᾽", True),          # koronis elision
        ("δ̓", True),          # coronis written as comma-above on a consonant
        ("ἀλλὰ", True),
        ("ἤ", True),
        ("ἄλλα", False),       # 'other things' — accent on the first α, NOT the coordinator ἀλλά
        ("ἡ", False),          # the article — NOT the disjunction ἤ
        ("ἦ", False),          # 'truly/was' — NOT ἤ
        ("ἐπεί", False),       # a subordinator, deliberately excluded
        ("λόγου", False),
    ],
)
def test_coordinator_norm_membership(surface, expected):
    """Membership is accent/breathing-sensitive (so ἀλλά≠ἄλλα, ἤ≠ἡ) yet robust to graves,
    underdots, and the several elision marks."""
    assert (D.coordinator_norm(surface) in D.COORDINATORS) is expected


# --- Lever A: coordinator reconciliation --------------------------------------------------


def test_reconcile_fires_only_on_coordinator_and_wrong_label():
    """Conservative Lever A relabels a coordinator the model tagged X/b, leaves a correctly
    tagged coordinator alone, leaves the adverbial (d/ADV) reading alone, and never touches a
    non-coordinator even when it is mistagged."""
    ana = _analysis(
        tokens=["καὶ", "δέ", "τε", "ἡ", "λόγου"],
        upos=["X", "CCONJ", "ADV", "X", "NOUN"],
        xpos=["b--------", "c--------", "d--------", "b--------", "n-s---mg-"],
        lemma=["καὶ", "δέ", "τε", "ἡ", "λόγου"],
        resolved=[True, True, True, True, True],
    )
    r = D.reconcile_analysis(ana, aggressive=False)
    # token 0: coordinator + X/b -> reconciled
    assert (r.upos[0], r.xpos[0]) == ("CCONJ", "c--------")
    # token 1: coordinator already correct -> untouched
    assert (r.upos[1], r.xpos[1]) == ("CCONJ", "c--------")
    # token 2: coordinator but adverbial (d/ADV) -> conservative leaves it
    assert (r.upos[2], r.xpos[2]) == ("ADV", "d--------")
    # token 3: the article ἡ mistagged X -> NOT a coordinator, untouched
    assert (r.upos[3], r.xpos[3]) == ("X", "b--------")
    # token 4: a noun -> untouched
    assert (r.upos[4], r.xpos[4]) == ("NOUN", "n-s---mg-")


def test_reconcile_aggressive_folds_in_the_adverbial_drift():
    """The aggressive variant additionally relabels the d/ADV reading (the one that risks
    clobbering a legitimate adverbial coordinator on literary text)."""
    ana = _analysis(
        tokens=["τε"], upos=["ADV"], xpos=["d--------"], lemma=["τε"], resolved=[True]
    )
    assert D.reconcile_analysis(ana, aggressive=False).upos == ("ADV",)
    assert D.reconcile_analysis(ana, aggressive=True).upos == ("CCONJ",)
    assert D.reconcile_analysis(ana, aggressive=True).xpos == ("c--------",)


def test_reconcile_rerenders_feats_from_the_corrected_postag():
    """The UD FEATS are re-derived from the corrected postag so they stay consistent (a
    coordinator carries no morphology → ``_``)."""
    ana = _analysis(
        tokens=["καὶ"], upos=["X"], xpos=["b--------"], lemma=["καὶ"], resolved=[True]
    )
    r = D.reconcile_analysis(ana, aggressive=False)
    assert r.feats == ("_",)


def test_reconcile_clears_stale_upos_probability_on_a_relabel():
    """A calibrated ``upos_prob`` is a model prediction; a deterministic relabel clears it to
    None (the reconciled label is not a calibrated model output)."""
    ana = replace(
        _analysis(
            tokens=["καὶ", "λόγου"], upos=["X", "NOUN"],
            xpos=["b--------", "n-s---mg-"], lemma=["καὶ", "λόγου"], resolved=[True, True],
        ),
        upos_prob=(0.4, 0.99),
    )
    r = D.reconcile_analysis(ana, aggressive=False)
    assert r.upos_prob[0] is None      # relabeled token: cleared
    assert r.upos_prob[1] == 0.99      # untouched token: preserved


def test_reconcile_invalidates_typed_task_and_sentence_confidence():
    ana = _with_confidence(
        _analysis(
            tokens=["καὶ", "λόγου"],
            upos=["X", "NOUN"],
            xpos=["b--------", "n-s---mg-"],
            lemma=["καὶ", "λόγος"],
            resolved=[True, True],
        )
    )
    result = D.reconcile_analysis(ana)
    changed = result.token_confidences[0]
    untouched = result.token_confidences[1]
    for task in ("upos", "xpos", "feats"):
        confidence = getattr(changed, task)
        assert confidence.value is None
        assert confidence.reason == "documentary_reconciliation"
        decision = next(item for item in changed.policy if item.task == task)
        assert decision.action == "unavailable" and decision.confidence is None
    assert changed.lemma == ana.token_confidences[0].lemma
    assert untouched == ana.token_confidences[1]
    assert result.sentence_confidence is not None
    assert result.sentence_confidence.result.reason == "documentary_reconciliation"


def test_reconcile_no_op_returns_same_object():
    """When nothing fires the analysis is returned unchanged (byte-identical, same object)."""
    ana = _analysis(
        tokens=["λόγου"], upos=["NOUN"], xpos=["n-s---mg-"], lemma=["λόγου"], resolved=[True]
    )
    assert D.reconcile_analysis(ana) is ana


# --- Lever B: lemma OOV rescue ------------------------------------------------------------


def test_rescue_lemma_sources():
    """`rescue_lemma` returns each offline source correctly, and None for a true OOV."""
    assert D.rescue_lemma("δέ") == ("δέ", LemmaSource.SEED)          # seed / function word
    # the ending-rule tier is deliberately NOT part of the rescue (measured: break-even on
    # documentary, net-negative on literary); a rules-only recoverable form stays an honest miss
    assert D.rescue_lemma("νόμου") is None
    assert D.rescue_lemma("ξζψβ") is None                            # unrescuable OOV


def test_rescue_lemma_paradigm_source():
    """With a paradigm table active, an irregular form the seed and rules miss is rescued
    under the PARADIGM class (never NEURAL)."""
    paradigms._ACTIVE = ParadigmLexicon({"γυναικός": [{"lemma": "γυνή", "pos": "n"}]})
    rescued = D.rescue_lemma("γυναικός")
    assert rescued == ("γυνή", LemmaSource.PARADIGM)


def test_rescue_never_overrides_a_resolved_lemma():
    """Only an unresolved (identity fall-through) lemma is rescued; a resolved neural lemma is
    left exactly as the model produced it, and a rescued token keeps ``lemma_resolved=False``
    so nothing downstream ever credits the neural model for an offline rescue."""
    ana = _analysis(
        tokens=["κυρίου", "κυρίου"],
        upos=["NOUN", "NOUN"], xpos=["n-s---mg-", "n-s---mg-"],
        lemma=["ΜΟΝΤΕΛΟ", "κυρίου"],   # token0: a (dummy) resolved model lemma; token1: identity
        resolved=[True, False],
    )
    r = D.rescue_analysis(ana)
    assert r.lemma[0] == "ΜΟΝΤΕΛΟ"          # resolved -> untouched
    assert r.lemma[1] == "κύριος"            # unresolved -> rescued by the seed table
    assert r.lemma_resolved == (True, False)  # rescue does not flip the honesty flag -> never NEURAL


def test_rescue_invalidates_typed_lemma_and_sentence_confidence():
    ana = _with_confidence(
        _analysis(
            tokens=["λόγος", "κυρίου"],
            upos=["NOUN", "NOUN"],
            xpos=["n-s---mn-", "n-s---mg-"],
            lemma=["λόγος", "κυρίου"],
            resolved=[True, False],
        )
    )
    result = D.rescue_analysis(ana)
    assert result.token_confidences[0] == ana.token_confidences[0]
    rescued = result.token_confidences[1]
    assert rescued.lemma is not None
    assert rescued.lemma.value is None
    assert rescued.lemma.reason == "offline_lemma_override"
    assert rescued.lemma.source == "seed"
    lemma_policy = next(item for item in rescued.policy if item.task == "lemma")
    assert lemma_policy.action == "unavailable" and lemma_policy.confidence is None
    assert result.sentence_confidence is not None
    assert result.sentence_confidence.result.reason == "offline_lemma_override"


def test_rescue_no_op_when_nothing_unresolved_or_no_flags():
    """Nothing to rescue → the analysis is returned unchanged; and with no lemma_resolved
    tuple (a model that does not report it) nothing can fire."""
    ana = _analysis(
        tokens=["κυρίου"], upos=["NOUN"], xpos=["n-s---mg-"], lemma=["κύριος"], resolved=[True]
    )
    assert D.rescue_analysis(ana) is ana
    no_flag = replace(ana, lemma_resolved=())
    assert D.rescue_analysis(no_flag) is no_flag


def test_documentary_wrapper_forwards_confidence_scope_and_policy():
    analysis = _analysis(
        tokens=["λόγος"],
        upos=["NOUN"],
        xpos=["n-s---mn-"],
        lemma=["λόγος"],
        resolved=[True],
    )
    calls: list[tuple[str | None, AbstentionPolicy | None]] = []

    class ConfidenceModel:
        def analyze(
            self,
            words: list[str],
            *,
            with_probs: bool,
            long_input: str,
            domain: str | None,
            policy: AbstentionPolicy | None,
        ) -> SentenceAnalysis:
            assert words == ["λόγος"] and with_probs and long_input == "strict"
            calls.append((domain, policy))
            return analysis

        def analyze_batch(
            self,
            sentences: list[list[str]],
            *,
            with_probs: bool,
            long_input: str,
            domain: str | None,
            policy: AbstentionPolicy | None,
        ) -> list[SentenceAnalysis]:
            assert sentences == [["λόγος"]] and with_probs and long_input == "strict"
            calls.append((domain, policy))
            return [analysis]

    policy = AbstentionPolicy({"lemma": 0.5})
    wrapped = D._DocumentaryModel(ConfidenceModel())
    assert wrapped.analyze(
        ["λόγος"], with_probs=True, domain="papyri", policy=policy
    ) is analysis
    assert wrapped.analyze_batch(
        [["λόγος"]], with_probs=True, domain="papyri", policy=policy
    ) == [analysis]
    assert calls == [("papyri", policy), ("papyri", policy)]


# --- default-off byte-identity + toggle lifecycle (through the wrapper) --------------------


def _default_analysis():
    # a coordinator the model mistagged X/b AND an unresolved rescuable lemma: both levers WOULD
    # fire if active, so an unchanged result proves the default path is untouched.
    return _analysis(
        tokens=["καὶ", "κυρίου"],
        upos=["X", "NOUN"], xpos=["b--------", "n-s---mg-"],
        lemma=["καὶ", "κυρίου"], resolved=[True, False],
    )


def test_default_off_is_byte_identical():
    """With no lever active no wrapper is installed and the pipeline sees the model's own
    output unchanged (the exact same object)."""
    base = _default_analysis()
    model = _FakeModel(base)
    joint._ACTIVE = model
    assert joint.active() is model  # no wrapper installed by default
    assert joint.active().analyze(["καὶ", "κυρίου"]) is base


def test_toggle_installs_and_removes_the_wrapper_and_round_trips():
    """Toggling a lever on installs the composition wrapper (so joint.active() reflects the
    lever); toggling every lever off removes it and restores byte-identical output."""
    base = _default_analysis()
    model = _FakeModel(base)
    joint._ACTIVE = model

    D.use_documentary_reconciliation()
    assert isinstance(joint.active(), D._DocumentaryModel)
    assert joint.active().lookup_form == {"marker": "sentinel"}  # delegates unknown attributes
    on = joint.active().analyze(["καὶ", "κυρίου"])
    assert on.upos[0] == "CCONJ"  # Lever A applied through the wrapper

    D.use_documentary_lemma_rescue()
    both = joint.active().analyze(["καὶ", "κυρίου"])
    assert both.upos[0] == "CCONJ" and both.lemma[1] == "κύριος"  # both levers applied

    D.disable_documentary_reconciliation()
    assert isinstance(joint.active(), D._DocumentaryModel)  # still wrapped: rescue remains on
    rescue_only = joint.active().analyze(["καὶ", "κυρίου"])
    assert rescue_only.upos[0] == "X" and rescue_only.lemma[1] == "κύριος"

    D.disable_documentary_lemma_rescue()
    assert joint.active() is model  # wrapper removed once no lever remains
    assert joint.active().analyze(["καὶ", "κυρίου"]) == base  # byte-identical again


def test_analyze_batch_applies_levers_through_the_wrapper():
    """The batched path the fold evaluators use also routes through the levers."""
    model = _FakeModel(_default_analysis())
    joint._ACTIVE = model
    D.use_documentary_reconciliation()
    out = joint.active().analyze_batch([["καὶ", "κυρίου"], ["καὶ", "κυρίου"]])
    assert all(a.upos[0] == "CCONJ" for a in out)


def test_toggle_requires_an_active_pipeline():
    """The levers post-process the neural pipeline; toggling one on with no pipeline active is
    a clean error, not a silent no-op."""
    joint._ACTIVE = None
    with pytest.raises(joint.NeuralPipelineNotLoadedError):
        D.use_documentary_reconciliation()
    with pytest.raises(joint.NeuralPipelineNotLoadedError):
        D.use_documentary_lemma_rescue()
    # disable is always safe
    D.disable_documentary_reconciliation()
    assert D.documentary_reconciliation_active() is False


def test_active_introspection_flags():
    model = _FakeModel(_default_analysis())
    joint._ACTIVE = model
    assert D.documentary_reconciliation_active() is False
    D.use_documentary_reconciliation()
    assert D.documentary_reconciliation_active() is True
    assert D.documentary_lemma_rescue_active() is False
    D.use_documentary_lemma_rescue()
    assert D.documentary_lemma_rescue_active() is True
