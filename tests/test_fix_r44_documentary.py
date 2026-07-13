"""Regression tests for the R44 documentary-lever fixes (`aegean.greek.documentary` + consumers).

All offline (no 173 MB model): hand-built `SentenceAnalysis` values plus a tiny fake inner model
installed as ``joint._ACTIVE`` — the test_documentary_levers idiom — so every assertion checks a
transformed OUTPUT against a known-correct answer.

FIX 1 — the GREEK NUMERAL SIGN keraia (U+0374, whose NFD is U+02B9) was in the elision-apostrophe
set, so a Milesian numeral δʹ (=4) / τʹ (=300) canonicalized onto the elided coordinator δ' / τ'
and Lever A would relabel it CCONJ. Neither codepoint may match `COORDINATORS` now; the four real
elision marks still do.

FIX 2 — `use_documentary_lemma_rescue`'s docstring claimed a ``seed → rules → paradigm`` cascade,
but `rescue_lemma` deliberately excludes the rules tier (measured break-even/net-negative).

FIX 3 — a Lever B rescue kept ``lemma_resolved=False`` and discarded the SEED/PARADIGM source, so
every consumer derived `LemmaSource.IDENTITY` with the self-contradictory ``surface form
unchanged`` note even though the shown lemma differed from the surface. The additive
``SentenceAnalysis.lemma_source_override`` channel now carries the offline source; the three
consumers (`pipeline` / `lemmatize_sourced` / `annotate_corpus`) surface SEED / PARADIGM,
needs_review False, and the default-off path stays byte-identical.
"""

from __future__ import annotations

import unicodedata
from dataclasses import replace

import pytest

import aegean
from aegean.core.model import Document, Token, TokenKind
from aegean.greek import documentary as D
from aegean.greek import joint, paradigms
from aegean.greek.annotate import annotate_corpus
from aegean.greek.explain import explain_pipeline
from aegean.greek.joint import SentenceAnalysis
from aegean.greek.lemmatize import LemmaSource, lemmatize_sourced
from aegean.greek.paradigms import ParadigmLexicon
from aegean.greek.pipeline import pipeline

KERAIA = "ʹ"   # GREEK NUMERAL SIGN (the Milesian numeral mark; NFD → U+02B9)
PRIME = "ʹ"    # MODIFIER LETTER PRIME (the NFD target of the keraia)


@pytest.fixture(autouse=True)
def _clean_state():
    """Every test starts and ends with all levers off and no model / paradigm installed."""
    D.disable_documentary_reconciliation()
    D.disable_documentary_lemma_rescue()
    saved, saved_par = joint._ACTIVE, paradigms._ACTIVE
    joint._ACTIVE = None
    paradigms._ACTIVE = None
    yield
    D.disable_documentary_reconciliation()
    D.disable_documentary_lemma_rescue()
    joint._ACTIVE, paradigms._ACTIVE = saved, saved_par


# ── a fake inner joint model (no ONNX) ────────────────────────────────────────
class _FakeInner:
    """Stands in for `joint._JointModel`: returns a fixed analysis for any input."""

    def __init__(self, analysis: SentenceAnalysis) -> None:
        self._analysis = analysis

    def analyze(self, words: list[str], *, with_probs: bool = False) -> SentenceAnalysis:
        return self._analysis

    def analyze_batch(
        self, sentences: list[list[str]], *, with_probs: bool = False
    ) -> list[SentenceAnalysis]:
        return [self._analysis for _ in sentences]


def _unresolved(tokens: list[str], lemmas: list[str]) -> SentenceAnalysis:
    """An analysis whose every token is the honest identity fall-through (unresolved)."""
    n = len(tokens)
    return SentenceAnalysis(
        tokens=tuple(tokens),
        upos=tuple("NOUN" for _ in range(n)),
        xpos=tuple("n-s---mg-" for _ in range(n)),
        feats=tuple("Case=Gen|Gender=Masc|Number=Sing" for _ in range(n)),
        head=tuple(0 if i == 0 else 1 for i in range(n)),
        deprel=tuple("root" if i == 0 else "dep" for i in range(n)),
        lemma=tuple(lemmas),
        lemma_resolved=tuple(False for _ in range(n)),
    )


# ── FIX 1: the keraia numeral sign is not an elision mark ─────────────────────
@pytest.mark.parametrize("num", ["δ", "τ"])
@pytest.mark.parametrize("mark", [KERAIA, PRIME], ids=["keraia-U+0374", "prime-U+02B9"])
def test_milesian_numeral_is_not_a_coordinator(num: str, mark: str) -> None:
    """δʹ (=4) / τʹ (=300) with EITHER the keraia or a bare prime must not match the coordinator
    set — the numeral sign is not an elision, so it never collapses onto δ' / τ'."""
    assert D.coordinator_norm(num + mark) not in D.COORDINATORS


@pytest.mark.parametrize(
    "mark",
    ["'", "’", "ʼ", "᾽"],
    ids=["ascii", "U+2019", "U+02BC", "U+1FBD"],
)
@pytest.mark.parametrize("stem", ["δ", "τ", "ἀλλ"])
def test_genuine_elision_still_matches(stem: str, mark: str) -> None:
    """A genuinely elided coordinator (δ' / τ' / ἀλλ') written with any of the four real
    elision marks still matches the coordinator set."""
    assert D.coordinator_norm(stem + mark) in D.COORDINATORS


def test_keraia_is_preserved_not_folded_to_an_apostrophe() -> None:
    """The numeral sign survives normalization (kept as the U+02B9 prime), so δʹ stays δʹ
    instead of becoming the elided δ'."""
    normed = D.coordinator_norm("δ" + KERAIA)
    assert "'" not in normed
    assert PRIME in unicodedata.normalize("NFD", normed)


def test_coordinator_set_size_unchanged() -> None:
    """Excluding the numeral sign does not perturb the closed set: 9 citation + 7 elided forms."""
    assert len(D.COORDINATORS) == 16


# ── FIX 2: the rescue docstring matches the actual cascade ────────────────────
def test_rescue_docstring_matches_actual_cascade() -> None:
    """`rescue_lemma` consults seed → paradigm only (the rules tier is deliberately excluded);
    the toggle's docstring must not advertise a rules tier it never uses."""
    doc = D.use_documentary_lemma_rescue.__doc__ or ""
    assert "seed → the opt-in paradigm table" in doc
    assert "seed → rules → the opt-in paradigm table" not in doc  # the excluded rules tier


# ── FIX 3: Lever B rescues carry SEED / PARADIGM, never IDENTITY ──────────────
def test_pipeline_surfaces_seed_rescue_and_leaves_unrescuable_as_identity() -> None:
    """A rescued unresolved token surfaces its grounded SEED source (not IDENTITY); an
    unrescuable OOV in the same sentence still reads IDENTITY / needs review."""
    joint._ACTIVE = _FakeInner(_unresolved(["κυρίου", "ξζψβ"], ["κυρίου", "ξζψβ"]))
    D.use_documentary_lemma_rescue()
    r0, r1 = pipeline("κυρίου ξζψβ")
    # rescued by the seed table: grounded, not a review-bait identity fall-through
    assert (r0.text, r0.lemma, r0.lemma_source) == ("κυρίου", "κύριος", LemmaSource.SEED)
    assert r0.lemma_resolved is True
    # unrescuable OOV: unchanged IDENTITY / needs review
    assert (r1.text, r1.lemma, r1.lemma_source) == ("ξζψβ", "ξζψβ", LemmaSource.IDENTITY)
    assert r1.lemma_resolved is False


def test_pipeline_surfaces_paradigm_rescue() -> None:
    """With a paradigm table active, an irregular form the seed misses is rescued under the
    PARADIGM class (never NEURAL, never IDENTITY)."""
    paradigms._ACTIVE = ParadigmLexicon({"γυναικός": [{"lemma": "γυνή", "pos": "n"}]})
    joint._ACTIVE = _FakeInner(_unresolved(["γυναικός"], ["γυναικός"]))
    D.use_documentary_lemma_rescue()
    (r,) = pipeline("γυναικός")
    assert (r.lemma, r.lemma_source) == ("γυνή", LemmaSource.PARADIGM)
    assert r.lemma_resolved is True


def test_explain_note_does_not_claim_surface_unchanged_for_a_rescue() -> None:
    """The rescued token's explanation reports the SEED class with an accurate note — not the
    self-contradictory 'the neural pipeline returned the surface form unchanged'."""
    joint._ACTIVE = _FakeInner(_unresolved(["κυρίου"], ["κυρίου"]))
    D.use_documentary_lemma_rescue()
    (e,) = explain_pipeline("κυρίου")
    assert e.lemma == "κύριος"
    assert e.lemma_source is LemmaSource.SEED
    assert e.needs_review is False
    assert "surface form unchanged" not in e.note
    assert "seed table" in e.note


def test_lemmatize_sourced_surfaces_rescue_source() -> None:
    """The single-word cascade reports the rescue's offline evidence class, not IDENTITY."""
    joint._ACTIVE = _FakeInner(_unresolved(["κυρίου"], ["κυρίου"]))
    D.use_documentary_lemma_rescue()
    assert lemmatize_sourced("κυρίου") == ("κύριος", LemmaSource.SEED)

    paradigms._ACTIVE = ParadigmLexicon({"γυναικός": [{"lemma": "γυνή", "pos": "n"}]})
    joint._ACTIVE = _FakeInner(_unresolved(["γυναικός"], ["γυναικός"]))
    D.use_documentary_lemma_rescue()
    assert lemmatize_sourced("γυναικός") == ("γυνή", LemmaSource.PARADIGM)


def test_annotate_corpus_surfaces_rescue_source() -> None:
    """`annotate_corpus`'s joint branch writes the rescue's grounded source (seed → lemma_known
    true), while an unrescuable token stays identity → lemma_known false."""
    doc = Document(
        id="d1",
        script_id="greek",
        tokens=[
            Token("κυρίου", TokenKind.WORD, line_no=0, position=0),
            Token("ξζψβ", TokenKind.WORD, line_no=0, position=1),
        ],
        lines=[[0, 1]],
    )
    corpus = aegean.Corpus([doc], script_id="greek")
    joint._ACTIVE = _FakeInner(_unresolved(["κυρίου", "ξζψβ"], ["κυρίου", "ξζψβ"]))
    D.use_documentary_lemma_rescue()
    out = annotate_corpus(corpus)
    t0, t1 = out.documents[0].tokens
    assert t0.annotations["lemma"] == "κύριος"
    assert t0.annotations["lemma_source"] == "seed"
    assert t0.annotations["lemma_known"] == "true"
    assert t1.annotations["lemma_source"] == "identity"
    assert t1.annotations["lemma_known"] == "false"


# ── FIX 3: the additive channel + default-off byte-identity ───────────────────
def test_lemma_source_override_defaults_empty_and_preserves_equality() -> None:
    """The new field is additive: the 8-arg positional construction still works, the field
    defaults to ``()``, and an explicit empty override equals the default."""
    empty = SentenceAnalysis((), (), (), (), (), (), (), ())
    assert empty.lemma_source_override == ()
    a = SentenceAnalysis(
        tokens=("x",), upos=("X",), xpos=("---------",), feats=("_",),
        head=(0,), deprel=("root",), lemma=("x",), lemma_resolved=(True,),
    )
    assert a.lemma_source_override == ()
    assert replace(a, lemma_source_override=()) == a


def test_default_off_pipeline_and_explain_are_byte_identical() -> None:
    """With no lever active (a plain model, no wrapper) the override channel is empty and a
    genuine identity fall-through still reads IDENTITY / review with the unchanged note —
    exactly the pre-fix behavior."""
    from test_joint import _stub_model  # the canonical ὁ / λόγος / ἐστί stub

    joint._ACTIVE = _stub_model()
    # a plain analysis carries the empty override channel (the additive field's default)
    assert joint._ACTIVE.analyze(["ὁ", "λόγος", "ἐστί"]).lemma_source_override == ()

    (logos,) = [r for r in pipeline("ὁ λόγος ἐστί") if r.text == "λόγος"]
    assert logos.lemma_source is LemmaSource.IDENTITY  # the model's identity fall-through
    assert logos.lemma_resolved is False

    (e,) = [x for x in explain_pipeline("ὁ λόγος ἐστί") if x.token == "λόγος"]
    assert e.lemma_source is LemmaSource.IDENTITY
    assert e.needs_review is True
    assert "surface form unchanged" in e.note
