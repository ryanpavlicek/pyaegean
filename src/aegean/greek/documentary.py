"""Opt-in documentary-Koine post-processing levers over the neural pipeline (default-off).

Two independent, **opt-in** layers that reconcile the shipped joint neural pipeline's output
to the documentary-papyri register (the PapyGreek fold, `aegean.greek.evaluate_on_papygreek`),
without touching the model, the default pipeline, or any published number. Both are **off by
default and byte-identical to the plain pipeline when off** (a fresh session, or after
`disable_*`, produces exactly the model's own output); each is a composition layer, exactly
like `use_paradigms`, so it earns its own opt-in measured row and never silently replaces the
model's numbers.

Lever A, **coordinator reconciliation** (`use_documentary_reconciliation`). The documentary
error anatomy (see ``docs`` / the PapyGreek convention decomposition) shows the single largest
error source is the closed class of coordinating conjunctions: καί, δέ, τε, ἀλλά, ἤ, οὐδέ,
οὔτε, μηδέ, μήτε (Smyth §2163 ff., the copulative/disjunctive/adversative coordinators). The
merged training data tags these words under three incompatible conventions, so on the
out-of-domain documentary register the model drifts to the non-AGDT ``b`` pos-code (which the
AGDT→UD converter maps to UPOS ``X``) or the ``d``/adverb reading. This layer, when the surface
form is one of that closed set **and** the model emitted the clearly-wrong reading, relabels
UPOS to ``CCONJ`` and the XPOS pos-code (position 0) to ``c``, leaving every other field
untouched (the UD FEATS are re-rendered from the corrected postag so they stay consistent).
Deliberately conservative: only that closed set, only those wrong labels.

The default (conservative) form fires only on the ``X`` / ``b`` reading, which is *always*
wrong for a coordinator (there is no legitimate ``X`` coordinator), so it cannot mislabel a
correct token. The adverbial reading (``d``/ADV) is a **legitimate** tag for these forms in
the literary AGDT convention (adverbial/particle καί, δέ, τε), so folding it in
(``aggressive=True``) clobbers those correct labels on literary text (measured on the literary
dev fold to regress it heavily) and is recommended against.

Lever B, **lemma OOV rescue** (`use_documentary_lemma_rescue`). When the joint model's lemma is
the honest identity fall-through (``lemma_resolved`` is ``False`` — the model kept the surface
form because it had no analysis), this layer consults the guarded **offline** lemmatization
cascade (the bundled seed table → the opt-in UniMorph paradigm
table, when `use_paradigms` is active) for a rescue. A rescue only *replaces* an unresolved
lemma; it never overrides a lemma the model resolved, and it carries **its own** evidence class
(`aegean.greek.LemmaSource` ``SEED`` / ``PARADIGM`` — the curated offline source that
produced it), never ``NEURAL``. A rescued token keeps ``lemma_resolved=False`` in the shared
`SentenceAnalysis` so nothing downstream ever credits the neural model for an offline rescue;
the true offline source is available from `rescue_lemma`.

Both levers post-process the **active** neural pipeline, so the neural pipeline must be
activated first (`aegean.greek.use_neural_pipeline`); toggling a lever on with no pipeline
active raises. Re-activating the neural pipeline drops the wrapper — call the toggle again
after any `use_neural_pipeline` call.
"""

from __future__ import annotations

import unicodedata
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from .lemmatize import (
    LemmaSource,
    _fold_key,
    _FUNCTION_KEYS,
    _INDECLINABLE,
    _is_capitalized,
    seed_lemma_verbose,
)
from .udfeats import feats_from_xpos

if TYPE_CHECKING:
    from .joint import SentenceAnalysis

__all__ = [
    "COORDINATORS",
    "coordinator_norm",
    "disable_documentary_lemma_rescue",
    "disable_documentary_reconciliation",
    "documentary_lemma_rescue_active",
    "documentary_reconciliation_active",
    "reconcile_analysis",
    "rescue_analysis",
    "rescue_lemma",
    "use_documentary_lemma_rescue",
    "use_documentary_reconciliation",
]

# --- the closed coordinator set -------------------------------------------------------
#
# The coordinating conjunctions (Smyth §2163 ff.): the copulative καί / τε / (negative) οὐδέ /
# οὔτε / μηδέ / μήτε, the disjunctive ἤ, and the adversative δέ / ἀλλά. A deliberately CLOSED
# set — no subordinators (ἐπεί, ἐπειδή, καθώς) and no particles (μή, δή) — so the layer only
# ever touches words whose canonical AGDT tag is the conjunction pos-code ``c`` / UPOS CCONJ.
_COORDINATOR_FORMS: tuple[str, ...] = (
    "καί", "δέ", "τε", "ἀλλά", "ἤ", "οὐδέ", "οὔτε", "μηδέ", "μήτε",
    # the standard elided forms (the final vowel + its accent dropped before a vowel)
    "δ'", "τ'", "ἀλλ'", "οὐδ'", "οὔτ'", "μηδ'", "μήτ'",
)

_GRAVE = "̀"       # combining grave accent (running-text notation of a final acute)
_ACUTE = "́"       # combining acute accent
_UNDERDOT = "̣"    # combining dot below: the Leiden "uncertain letter" apparatus mark
_PSILI = "̓"       # combining comma above: smooth breathing on a vowel, OR a coronis
_DASIA = "̔"       # combining reversed comma above: rough breathing on a vowel
# The true elision marks seen in the corpora: the modifier apostrophe (U+02BC), the Greek
# koronis (U+1FBD), the right single quote (U+2019), and the ASCII apostrophe. The GREEK
# NUMERAL SIGN keraia (U+0374, which NFD-decomposes to U+02B9) and a bare U+02B9 prime are
# DELIBERATELY excluded: they mark a Milesian numeral (δʹ = 4, τʹ = 300), not an elision, so
# folding them to an apostrophe would relabel those numerals as the elided coordinator δ' / τ'.
_APOSTROPHES = frozenset("ʼ᾽’'")
_CANON_APOSTROPHE = "'"
_VOWELS = frozenset("αεηιουω")


def coordinator_norm(form: str) -> str:
    """Normalize a surface form for closed-set coordinator matching.

    Accent- and breathing-**sensitive** (so ἀλλά 'but' is never confused with ἄλλα 'other
    things', nor ἤ 'or' with the article ἡ), but robust to the running-text and epigraphic
    surface: it lowercases, folds a grave accent to the acute (Smyth §155 — the grave is only
    the running-text notation of a final acute), drops the Leiden underdot (the "uncertain
    letter" mark that peppers documentary readings, e.g. κα̣ὶ), and canonicalizes the several
    elision marks (the modifier apostrophe, the koronis, and a coronis written as a
    comma-above on a consonant) to a single apostrophe, so δʼ / δ᾽ / δ̓ all match δ'."""
    nfd = unicodedata.normalize("NFD", form.strip().lower())
    out: list[str] = []
    prev_base = ""
    for ch in nfd:
        if ch == _UNDERDOT:
            continue
        if ch == _GRAVE:
            out.append(_ACUTE)
            continue
        if ch in _APOSTROPHES:
            out.append(_CANON_APOSTROPHE)
            continue
        if ch in (_PSILI, _DASIA):
            # A comma/reversed-comma above sitting on a CONSONANT (other than ρ, which takes a
            # rough breathing) is a coronis = an elision mark, so ἀλλ̓ / δ̓ read as ἀλλ' / δ';
            # on a vowel it is a genuine breathing and is kept.
            if prev_base and prev_base not in _VOWELS and prev_base != "ρ":
                out.append(_CANON_APOSTROPHE)
            else:
                out.append(ch)
            continue
        if not unicodedata.combining(ch):
            prev_base = ch
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


#: The closed coordinator set, normalized (see `coordinator_norm`). Membership is the first of
#: the two conditions Lever A requires (the second is a wrong model label). A Milesian numeral
#: written with the keraia (δʹ = 4, τʹ = 300; U+0374 → U+02B9) is deliberately NOT a member: the
#: numeral sign is not an elision mark (see `_APOSTROPHES`), so δʹ never collapses onto δ'.
COORDINATORS: frozenset[str] = frozenset(coordinator_norm(f) for f in _COORDINATOR_FORMS)

# The pos-code drift readings. ``b`` (→ UPOS X after the AGDT→UD conversion) is ALWAYS wrong
# for a coordinator, so the conservative default corrects it; ``d`` (→ ADV) is a legitimate
# adverbial reading of these forms in the literary convention and is only folded in by the
# aggressive variant (measured to regress literary text heavily — it clobbers the many
# correctly-tagged adverbial coordinators).
_WRONG_POSCODES_CONSERVATIVE = frozenset("b")
_WRONG_POSCODES_AGGRESSIVE = frozenset("bd")


def _coordinator_mislabeled(upos: str, xpos: str, *, aggressive: bool) -> bool:
    """Whether the model's UPOS/XPOS for a (already coordinator-matched) form is the wrong
    reading Lever A corrects: the ``X`` / ``b`` drift always; additionally the ``ADV`` / ``d``
    drift when ``aggressive`` (which risks a legitimate adverbial reading)."""
    poscode = xpos[0] if xpos else "-"
    if upos == "X" or poscode in _WRONG_POSCODES_CONSERVATIVE:
        return True
    if aggressive and (upos == "ADV" or poscode in _WRONG_POSCODES_AGGRESSIVE):
        return True
    return False


def reconcile_analysis(ana: SentenceAnalysis, *, aggressive: bool = False) -> SentenceAnalysis:
    """Return ``ana`` with Lever A (coordinator reconciliation) applied — a NEW
    `SentenceAnalysis`, or ``ana`` unchanged when nothing fires.

    For each token whose surface form is in `COORDINATORS` and whose model reading is the
    wrong one (`_coordinator_mislabeled`), UPOS becomes ``CCONJ`` and the XPOS pos-code
    (position 0) becomes ``c``; the UD FEATS are re-rendered from the corrected postag so they
    stay consistent, and any calibrated ``upos_prob`` for that token is cleared to ``None``
    (a deterministic relabel is not a calibrated model prediction). Every other field is
    untouched. Pure and side-effect-free (used by the eval wrapper and directly by tests)."""
    if not ana.tokens:
        return ana
    upos = list(ana.upos)
    xpos = list(ana.xpos)
    feats = list(ana.feats)
    uprob = list(ana.upos_prob) if ana.upos_prob else None
    changed = False
    for i, tok in enumerate(ana.tokens):
        if coordinator_norm(tok) in COORDINATORS and _coordinator_mislabeled(
            upos[i], xpos[i], aggressive=aggressive
        ):
            upos[i] = "CCONJ"
            tail = xpos[i][1:] if len(xpos[i]) >= 1 else "--------"
            xpos[i] = "c" + tail
            feats[i] = feats_from_xpos(xpos[i])
            if uprob is not None:
                uprob[i] = None
            changed = True
    if not changed:
        return ana
    return replace(
        ana,
        upos=tuple(upos),
        xpos=tuple(xpos),
        feats=tuple(feats),
        upos_prob=tuple(uprob) if uprob is not None else ana.upos_prob,
    )


def rescue_lemma(form: str) -> tuple[str, LemmaSource] | None:
    """The guarded **offline** lemma rescue for one form: ``(lemma, source)`` or ``None``.

    Consults the two CURATED offline sources: the bundled seed table (``SEED``), then the
    opt-in UniMorph paradigm table when `use_paradigms` is active (``PARADIGM``, gated by the
    same closed-class / indeclinable / capitalized-surface / intra-table-ambiguity guards).
    Returns ``None`` when neither recovers a citation form (the form stays an honest miss).
    Never consults the neural model, so a rescue is always an offline, grounded analysis under
    its own evidence class — never ``NEURAL``.

    The generalizing ending-stripping rules are deliberately NOT consulted here: on the OOV
    residue the neural model already left unresolved, the rules fabricate about as often as
    they fix (measured on the documentary dev fold: roughly break-even there, and net-negative
    on the literary dev fold, where they were the sole source of regressions), so the rescue
    keeps only the curated, correctly-accented tiers."""
    lemma, known = seed_lemma_verbose(form)
    if known:
        return lemma, LemmaSource.SEED
    from . import paradigms

    plex = paradigms.active()
    if plex is not None:
        key = _fold_key(form)
        if (
            key not in _FUNCTION_KEYS
            and key not in _INDECLINABLE
            and not _is_capitalized(form)
            and len(plex.lemma_options(form)) == 1
        ):
            hit = plex.lemmatize(form)
            if hit is not None:
                return hit, LemmaSource.PARADIGM
    return None


def rescue_analysis(ana: SentenceAnalysis) -> SentenceAnalysis:
    """Return ``ana`` with Lever B (lemma OOV rescue) applied — a NEW `SentenceAnalysis`, or
    ``ana`` unchanged when nothing is rescued.

    For each token the model left UNRESOLVED (``lemma_resolved`` is ``False`` — the honest
    identity fall-through), `rescue_lemma` is consulted; a hit replaces the lemma string and
    records its offline source (``SEED`` / ``PARADIGM``) in ``lemma_source_override`` at that
    index, so a consumer can surface the true grounded evidence class rather than the identity
    fall-through. A token the model resolved is never touched (the model's lemma wins), and a
    rescued token keeps ``lemma_resolved=False`` so nothing downstream ever labels an offline
    rescue as a neural prediction (the source stays offline via the override channel and
    `rescue_lemma`). Pure and side-effect-free. When the model does not report
    ``lemma_resolved`` (an empty tuple), no token can be known-unresolved, so nothing fires."""
    if not ana.tokens or not ana.lemma_resolved:
        return ana
    lemma = list(ana.lemma)
    override = [""] * len(ana.tokens)
    changed = False
    for i, resolved in enumerate(ana.lemma_resolved):
        if not resolved:
            rescued = rescue_lemma(ana.tokens[i])
            if rescued is not None:
                lemma[i] = rescued[0]
                override[i] = rescued[1].value  # the offline source: "seed" / "paradigm"
                changed = True
    if not changed:
        return ana
    return replace(ana, lemma=tuple(lemma), lemma_source_override=tuple(override))


# --- the opt-in toggles + the composition wrapper -------------------------------------
#
# The levers post-process the ACTIVE joint model's output. Rather than edit the pipeline, the
# active model is wrapped (composed from outside) with `_DocumentaryModel`, which delegates
# everything to the real model and applies whichever levers are on to each analysis. The
# wrapper reads the module flags live, so toggling a lever on/off takes effect without
# re-wrapping. When both levers are off the wrapper is removed, restoring byte-identical output.

_RECONCILE = False
_RESCUE = False
_AGGRESSIVE = False


class _DocumentaryModel:
    """Wraps an active joint model, applying the opt-in documentary levers to its output.

    Presents the same ``analyze`` / ``analyze_batch`` surface the neural pipeline consumes and
    delegates every other attribute to the wrapped model, so `aegean.greek.joint.active` (and
    thus `pipeline`, `pipeline_conllu`, and the UD/PapyGreek evaluators) transparently sees the
    reconciled/rescued analyses. It applies whichever levers are currently on, so it is
    installed once and reads the toggles live."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    def _apply(self, ana: SentenceAnalysis) -> SentenceAnalysis:
        if _RECONCILE:
            ana = reconcile_analysis(ana, aggressive=_AGGRESSIVE)
        if _RESCUE:
            ana = rescue_analysis(ana)
        return ana

    def analyze(self, words: list[str], *, with_probs: bool = False) -> SentenceAnalysis:
        return self._apply(self.inner.analyze(words, with_probs=with_probs))

    def analyze_batch(
        self, sentences: list[list[str]], *, with_probs: bool = False
    ) -> list[SentenceAnalysis]:
        return [self._apply(a) for a in self.inner.analyze_batch(sentences, with_probs=with_probs)]

    def __getattr__(self, name: str) -> Any:
        # Every attribute the wrapper does not define (lookup tables, the ONNX session, label
        # maps, …) is served from the wrapped model. `inner` is set in __init__ so it is found
        # in __dict__ and never routes here (no recursion).
        return getattr(self.inner, name)


def _require_active() -> Any:
    """The active raw joint model, unwrapping our own wrapper; raise if none is active."""
    from . import joint

    active: Any = joint.active()  # Any: the wrapper composes outside joint's declared type
    if active is None:
        raise joint.NeuralPipelineNotLoadedError(
            "the documentary levers post-process the neural pipeline; activate it first with "
            "aegean.greek.use_neural_pipeline()."
        )
    return active.inner if isinstance(active, _DocumentaryModel) else active


def _sync() -> None:
    """Install or remove the wrapper so `joint.active()` reflects the current toggles."""
    from . import joint

    active: Any = joint.active()  # Any: the wrapper composes outside joint's declared type
    if active is None:
        return
    wrapped = isinstance(active, _DocumentaryModel)
    want = _RECONCILE or _RESCUE
    if want and not wrapped:
        # Install our composition wrapper as the active model. joint._ACTIVE is typed
        # _JointModel | None; the wrapper is deliberately duck-typed (composed from outside).
        joint._ACTIVE = _DocumentaryModel(active)  # type: ignore[assignment]
    elif not want and wrapped:
        joint._ACTIVE = active.inner


def use_documentary_reconciliation(*, aggressive: bool = False) -> None:
    """Activate Lever A: closed-class coordinator reconciliation over the neural output.

    Requires the neural pipeline to be active (raises `NeuralPipelineNotLoadedError`
    otherwise). ``aggressive=False`` (the default, recommended) corrects only the ``X`` / ``b``
    drift, which is always wrong for a coordinator and so cannot mislabel literary text.
    ``aggressive=True`` additionally folds in the ``ADV`` / ``d`` drift, which clobbers the
    legitimate adverbial reading (measured to regress the literary dev fold heavily).
    Default-off and byte-identical to the plain pipeline until called; `disable_*`
    restores that."""
    global _RECONCILE, _AGGRESSIVE
    _require_active()
    _RECONCILE = True
    _AGGRESSIVE = aggressive
    _sync()


def disable_documentary_reconciliation() -> None:
    """Deactivate Lever A; remove the wrapper if no lever remains active."""
    global _RECONCILE
    _RECONCILE = False
    _sync()


def documentary_reconciliation_active() -> bool:
    """Whether Lever A (coordinator reconciliation) is currently active."""
    return _RECONCILE


def use_documentary_lemma_rescue() -> None:
    """Activate Lever B: offline lemma OOV rescue over the neural output.

    Requires the neural pipeline to be active (raises `NeuralPipelineNotLoadedError`
    otherwise). When the model leaves a lemma unresolved, the guarded offline cascade
    (seed → the opt-in paradigm table) is consulted for a rescue; a rescue never
    overrides a resolved neural lemma and carries its own offline evidence class (see
    `rescue_lemma`). Default-off and byte-identical to the plain pipeline until called;
    `disable_*` restores that."""
    global _RESCUE
    _require_active()
    _RESCUE = True
    _sync()


def disable_documentary_lemma_rescue() -> None:
    """Deactivate Lever B; remove the wrapper if no lever remains active."""
    global _RESCUE
    _RESCUE = False
    _sync()


def documentary_lemma_rescue_active() -> bool:
    """Whether Lever B (lemma OOV rescue) is currently active."""
    return _RESCUE
