"""Hybrid translation: lexicon/morphology grounding → LLM.

Builds grounding evidence from the package's own tooling (deterministic Greek
morphology and dependency syntax, optionally gated content-word LSJ glosses;
Linear A sign→sound transliteration), then hands the text plus that evidence to
`aegean.ai.translate`. The grounding step is deterministic and local; the
translation itself is generative and returned as an exploratory, provenanced
`ExploratoryResult`.

Greek grounding has several **modes** (see `grounding_for`). The default,
``"morphology"``, grounds the model in deterministic morphology and syntax (lemma,
part of speech, case/voice/tense, and a clause skeleton from the dependency parse)
and adds **no** dictionary glosses: morphology, voice, case-role, and syntactic structure
are facts the toolkit computes reliably and that a model can use directly. It also adds a
gloss of any **idiom** present (``ai.idiom_glosses``): a non-compositional multiword
expression is the one error class per-token morphology cannot reach, since the words'
lemmas and case only reinforce the wrong literal reading, and the curated idiom lexicon
matches deterministically with a low false-positive rate, so it rides with the safe
default. ``"full"`` keeps those morphology and idiom lines and adds a gloss layer in the
configuration that helps rather than hurts: glosses sourced from a **concise,
common-sense-first** dictionary cascade (Middle Liddell, Cunliffe for Homer, Abbott-Smith /
Dodson for the NT), cleaned, and gated to the text's rare content words (see
`ai.grounding.content_glosses` with ``source="cascade"``).
That source matters: a first-sense gloss from the historical LSJ lexicon is often the
archaic meaning (καιρός, βίος), so asserting it injects errors, whereas a concise dictionary
leads with the common sense and helps most exactly on the rare vocabulary a model is likely
to miss. ``"none"`` adds no grounding.

The older ``"lemma"`` mode (lemma lines plus gated content-word LSJ glosses) is retained
unchanged for back-compatibility; its glosses are the deliberately selective LSJ ones (see
`ai.grounding.content_glosses` with the default ``source="lsj"``): only low-polysemy content
words, where the dominant-sense gloss is reliable, leaving highly polysemous words to the
model.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Literal, get_args

if TYPE_CHECKING:
    from ..greek.pipeline import TokenRecord
    from ..greek.runtime import GreekPipeline

from ..ai import translate as _ai_translate
from ..ai import verify_translation as _ai_verify_translation
from ..ai.client import ExploratoryResult, LLMClient
from ..ai.client import get_client as _get_client
from ..ai.grounding import GroundingItem, content_glosses
from ..ai.idioms import idiom_glosses

_SOURCE_NAMES = {"greek": "Ancient Greek", "lineara": "Linear A"}

GroundingMode = Literal["morphology", "lemma", "full", "none"]
GroundingFailure = Literal["best-effort", "strict"]
GreekLongInput = Literal["strict", "partial", "windowed"]


class GroundingError(RuntimeError):
    """Required local grounding failed under the explicit ``"strict"`` policy.

    The persisted/public message names the failed stage without copying arbitrary
    exception text. The original exception remains available as ``__cause__``.
    """

    def __init__(
        self,
        *,
        stage: str,
        script: str,
        backend: str | None,
        config: dict[str, Any] | None,
    ) -> None:
        self.stage = stage
        self.script = script
        self.backend = backend
        self.config = config
        selected = f" {backend}" if backend else ""
        super().__init__(f"{script} grounding failed during {stage} with the selected{selected} backend")


@dataclass(frozen=True, slots=True)
class _GroundingOutcome:
    items: list[GroundingItem]
    runtime: dict[str, Any]

# Content parts of speech worth a clause role / rarity flag.
_CONTENT_POS = frozenset({"NOUN", "VERB", "ADJ", "ADV", "PROPN"})

# UD FEATS values → short, readable forms for the per-token morphology line. Keyed by
# (feature, value) so identical values under different features (Mood=Imp imperative vs
# Aspect=Imp imperfect) never collide; an unmapped value falls back to lower-case.
_FEAT_SHORT = {
    ("Case", "Nom"): "nom", ("Case", "Gen"): "gen", ("Case", "Dat"): "dat",
    ("Case", "Acc"): "acc", ("Case", "Voc"): "voc",
    ("Number", "Sing"): "sg", ("Number", "Plur"): "pl", ("Number", "Dual"): "du",
    ("Gender", "Masc"): "m", ("Gender", "Fem"): "f", ("Gender", "Neut"): "n",
    ("Voice", "Act"): "active", ("Voice", "Mid"): "middle", ("Voice", "Pass"): "passive",
    ("Tense", "Pres"): "pres", ("Tense", "Past"): "past", ("Tense", "Fut"): "fut",
    ("Tense", "Aor"): "aor", ("Tense", "Pqp"): "pluperf",
    ("Mood", "Ind"): "ind", ("Mood", "Sub"): "subj", ("Mood", "Opt"): "opt",
    ("Mood", "Imp"): "imper",
    ("Person", "1"): "1st", ("Person", "2"): "2nd", ("Person", "3"): "3rd",
}

# Order in which morphological features are rendered on a token line.
_FEAT_KEYS = ("Case", "Number", "Gender", "Voice", "Tense", "Mood", "Person")


def _rich_lemmatizer_active(greek_pipeline: GreekPipeline | None = None) -> bool:
    """Whether a lemmatizer better than the bundled seed table is loaded — the
    treebank, neural pipeline, GreTa, or edit-tree backend. Lexical grounding on rare
    or inflected forms depends on one of these being active."""
    if greek_pipeline is not None:
        # An explicit instance is isolated from every legacy module-level backend.
        return greek_pipeline.neural_active
    from ..greek import joint, lemmatizer, neural_lemmatizer, treebank

    return any(m.active() is not None for m in (joint, treebank, neural_lemmatizer, lemmatizer))


def _selected_pipeline(
    greek_pipeline: GreekPipeline | None,
) -> tuple[GreekPipeline, Literal["explicit", "module-default"]]:
    """Resolve and type-check the Greek analysis owner without loading a backend."""
    from ..greek.runtime import GreekPipeline, default_pipeline

    if greek_pipeline is None:
        return default_pipeline(), "module-default"
    if not isinstance(greek_pipeline, GreekPipeline):
        raise TypeError("greek_pipeline must be a GreekPipeline or None")
    return greek_pipeline, "explicit"


def _pipeline_runtime(
    pipeline: GreekPipeline,
    selection: Literal["explicit", "module-default"],
) -> dict[str, Any]:
    """JSON-ready pipeline identity for a result trace.

    A module-default baseline may also consult the legacy ``use_*`` compatibility
    cascade, which is intentionally outside `GreekPipelineConfig`; label that boundary
    rather than claiming the config describes more than it does.
    """
    runtime: dict[str, Any] = {
        "selection": selection,
        "backend": pipeline.config.backend,
        "config": pipeline.config.to_dict(),
    }
    if selection == "module-default":
        runtime["note"] = (
            "module-default config identifies its owned backend; active legacy use_* "
            "extensions are outside GreekPipelineConfig"
        )
    return runtime


def _validate_failure_policy(value: str) -> GroundingFailure:
    if value not in get_args(GroundingFailure):
        valid = ", ".join(repr(policy) for policy in get_args(GroundingFailure))
        raise ValueError(f"unknown grounding failure policy {value!r}; valid policies: {valid}")
    return value  # type: ignore[return-value]


def _readable_feats(feats: str | None, *keys: str) -> str:
    """Render selected UD FEATS values as a compact, readable string.

    ``_readable_feats("Case=Acc|Number=Sing", "Case", "Number")`` → ``"acc sg"``.
    Unknown values fall back to lower-case; absent features are skipped."""
    if not feats or feats == "_":
        return ""
    parsed = dict(kv.split("=", 1) for kv in feats.split("|") if "=" in kv)
    out: list[str] = []
    for k in keys:
        v = parsed.get(k)
        if v is None:
            continue
        out.append(_FEAT_SHORT.get((k, v), v.lower()))
    return " ".join(out)


def _root_skeleton(rt: TokenRecord, recs: list[TokenRecord]) -> str:
    """The clause skeleton for one sentence root ``rt`` and its dependents.

    Two predicate shapes are distinguished from the dependency parse:

    - **Copular clause.** In UD a non-verbal predicate is the root and the copula
      (``εἰμί``) hangs off it as a ``cop`` dependent (``ὁ θεὸς ἀγαθός ἐστιν`` →
      root ``ἀγαθός``, ``cop`` ``ἐστιν``). A naive "root is the predicate" reading
      drops the copula and, when the root sits inside a prepositional phrase
      (``ἐν ἀρχῇ ἦν ὁ λόγος`` → root ``ἀρχῇ``, ``case`` ``ἐν``), mislabels a
      PP-internal noun the main predicate. Here the copula and the predicate
      nominal/adjective are presented together, e.g.
      ``predicate ἦν + ἀρχή (predicate nominal)``.
    - **Verbal clause.** The root is the lexical predicate verb; subject and object
      are reported as before (``γράφει`` → ``main predicate γράφει; subject …``)."""
    kids = [r for r in recs if r.head == rt.index and r.relation]
    by_rel = {r.relation: r for r in kids}
    cop = by_rel.get("cop")
    parts: list[str] = []
    if cop is not None:
        # Non-verbal (copular) predication: lead with the copula + the predicate
        # nominal/adjective so the copula is never dropped and a PP-internal noun is
        # never called the predicate.
        kind = "predicate adjective" if rt.upos == "ADJ" else "predicate nominal"
        parts.append(f"predicate {cop.text} + {rt.lemma} ({kind})")
    else:
        pred = _readable_feats(rt.feats, "Voice", "Tense", "Number", "Person")
        parts.append(f"main predicate '{rt.text}' ({rt.lemma}{', ' + pred if pred else ''})")
    subj = by_rel.get("nsubj")
    if subj is not None:
        parts.append(f"subject {subj.text}")
    obj = by_rel.get("obj")
    if obj is not None:
        parts.append(f"object {obj.text}")
    return "; ".join(parts)


def _clause_skeleton(recs: list[TokenRecord]) -> str:
    """A readable clause skeleton across every sentence root in ``recs``, or ``""``.

    Each root (``head == 0``) that heads a clause becomes one ``;``-joined clause,
    and clauses are joined with `` | ``. Roots that are neither a content predicate
    (VERB / ADJ / NOUN) nor a copular predicate are skipped. Pure (no I/O); the parse
    is supplied by the caller, which keeps the copular-vs-verbal logic unit-testable."""
    clauses: list[str] = []
    for rt in recs:
        if rt.head != 0:
            continue
        has_cop = any(r.head == rt.index and r.relation == "cop" for r in recs)
        if rt.upos not in {"VERB", "ADJ", "NOUN"} and not has_cop:
            continue
        clauses.append(_root_skeleton(rt, recs))
    return " | ".join(clauses)


def _analysis_records(
    text: str,
    *,
    pipeline: GreekPipeline,
    parse: bool,
    long_input: GreekLongInput,
    failure_policy: GroundingFailure,
    failures: list[dict[str, str]],
) -> list[TokenRecord]:
    """Run the required Greek analysis with explicit degradation semantics."""

    def failed(stage: str, exc: Exception) -> None:
        failures.append({"stage": stage, "error_type": type(exc).__name__})
        if failure_policy == "strict":
            raise GroundingError(
                stage=stage,
                script="greek",
                backend=pipeline.config.backend,
                config=pipeline.config.to_dict(),
            ) from exc

    try:
        records = pipeline.analyze(text, parse=parse, long_input=long_input)
    except Exception as exc:
        stage = "morphology and dependency analysis" if parse else "morphology analysis"
        failed(stage, exc)
        if not parse:
            return []
        try:
            records = pipeline.analyze(text, parse=False, long_input=long_input)
        except Exception as fallback_exc:
            failed("morphology fallback analysis", fallback_exc)
            return []

    if any(
        not record.analysis_complete or record.neural_analyzed is False
        for record in records
    ):
        failures.append(
            {"stage": "analysis coverage", "error_type": "IncompleteAnalysis"}
        )
        if failure_policy == "strict":
            raise GroundingError(
                stage="analysis coverage",
                script="greek",
                backend=pipeline.config.backend,
                config=pipeline.config.to_dict(),
            )
    return records


def _morphology_items(
    text: str, *, analysis: list[TokenRecord] | None = None
) -> list[GroundingItem]:
    """Deterministic morphology + syntax grounding for Greek, no dictionary glosses.

    Produces, in order: an optional clause-skeleton line from the dependency parse
    (predicate plus subject/object, with copular clauses presented as copula +
    predicate nominal/adjective rather than dropping the copula; see `_clause_skeleton`),
    one compact line per non-punct token (``word = lemma (pos, readable-morph)``), and an
    optional rare-word flag line. ``analysis`` is normally produced once by the selected
    `GreekPipeline` and reused by morphology, idiom, rarity, and gloss grounding."""
    if analysis is None:
        pipeline, _selection = _selected_pipeline(None)
        analysis = _analysis_records(
            text,
            pipeline=pipeline,
            parse=True,
            long_input="strict",
            failure_policy="best-effort",
            failures=[],
        )

    out: list[GroundingItem] = []

    skeleton = _clause_skeleton(analysis)
    if skeleton:
        out.append(
            GroundingItem(
                "Clause skeleton: " + skeleton,
                source="analysis:syntax",
                ref="clause",
            )
        )

    # One compact morphology line per non-punctuation token.
    for r in analysis:
        if r.upos == "PUNCT":
            continue
        morph = _readable_feats(r.feats, *_FEAT_KEYS)
        body = f"{r.text} = {r.lemma} ({r.upos.lower()}{', ' + morph if morph else ''})"
        out.append(GroundingItem(body, source="analysis:morphology", ref=r.text))

    rare_line = _rare_word_line(text, analysis=analysis)
    if rare_line:
        out.append(
            GroundingItem(
                "Rare / easily-mistranslated words: " + rare_line,
                source="analysis:rarity",
                ref="rare",
            )
        )
    return out


def _rare_word_line(text: str, *, analysis: list[TokenRecord] | None = None) -> str:
    """Comma-joined rare/uncommon content words in ``text``, or ``""``.

    Rarity is measured against a previously fetched full Greek NT reference corpus.
    The bundled two-book sample is not representative and is never used for frequency
    claims. Best-effort: if the full corpus or computation is unavailable, returns
    ``""`` rather than raising — the rest of the morphology grounding still stands."""
    try:
        from ..greek import terminology_rarity
        from ..scripts.greek.nt import _load_cached_full_nt

        reference = _load_cached_full_nt()
        if reference is None:
            return ""
        if analysis is not None:
            import math

            from ..greek.rarity import _corpus_lemma_freqs, _label, _norm

            frequencies = _corpus_lemma_freqs(reference)
            maximum = max(frequencies.values(), default=0)
            denominator = math.log1p(maximum) or 1.0
            ranked: list[tuple[float, str]] = []
            for record in analysis:
                if record.upos == "PUNCT":
                    continue
                count = frequencies.get(_norm(record.lemma), 0)
                if _label(count) == "common":
                    continue
                rarity = 1.0 - math.log1p(count) / denominator
                ranked.append((rarity, record.text))
            ranked.sort(key=lambda item: -item[0])
            return ", ".join(dict.fromkeys(word for _rarity, word in ranked[:4]))
        result = terminology_rarity(text, reference)
    except Exception:
        return ""
    rare = [w.word for w in result.hardest(4) if w.label != "common"]
    return ", ".join(dict.fromkeys(rare))  # dedupe, preserve order


def _greek_grounding(
    text: str,
    *,
    mode: GroundingMode = "morphology",
    glosses: bool = True,
    pipeline: GreekPipeline,
    long_input: GreekLongInput,
    failure_policy: GroundingFailure,
    failures: list[dict[str, str]],
) -> list[GroundingItem]:
    # Reject an unknown mode loudly: a typo ("morfology") must never silently fall
    # through to the legacy lemma branch and change the grounding behavior.
    if mode not in get_args(GroundingMode):
        valid = ", ".join(repr(m) for m in get_args(GroundingMode))
        raise ValueError(f"unknown grounding mode {mode!r}; valid modes: {valid}")

    if mode == "none":
        return []

    records = _analysis_records(
        text,
        pipeline=pipeline,
        parse=mode in ("morphology", "full"),
        long_input=long_input,
        failure_policy=failure_policy,
        failures=failures,
    )

    if mode in ("morphology", "full"):
        out = _morphology_items(text, analysis=records)
        # Idiom glosses ride with the morphology grounding in both modes. A
        # non-compositional multiword expression is the one error class per-token
        # morphology cannot reach (its lemmas/case only reinforce the literal reading), and
        # the curated lexicon matches deterministically with a low false-positive rate on
        # exact surface match, so it belongs in the safe default, not gated like sense
        # glosses. Best-effort: empty when no idiom is present. Source tag lexicon:idiom.
        out.extend(idiom_glosses(text, analysis=records))
        if mode == "full" and glosses:
            # The validated-best gloss layer: a concise, common-sense-first dictionary
            # cascade (never LSJ-first-sense), cleaned, and gated to the rare content words
            # (where a gloss helps). Best-effort: empty if no concise dictionary is loaded.
            out.extend(
                content_glosses(
                    text, source="cascade", rarity_gate=True, analysis=records
                )
            )
        return out

    # mode == "lemma": the original lemma-line format, driven by the selected pipeline.
    out = [
        GroundingItem(
            f"{record.text} → lemma {record.lemma}",
            source="lemmatizer",
            ref=record.text,
        )
        for record in records
        if record.upos != "PUNCT" and record.lemma_resolved
    ]
    if glosses:
        # Gated LSJ glosses for content words — best-effort, empty without greek.use_lsj().
        out.extend(content_glosses(text, analysis=records))
    return out


def _lineara_grounding(text: str) -> list[GroundingItem]:
    from ..scripts.lineara.phonetic import word_to_phonetic

    return [
        GroundingItem(f"{w} → /{word_to_phonetic(w)}/", source="transliteration", ref=w)
        for w in text.split()
        if "-" in w
    ]


def _build_grounding(
    text: str,
    script: str,
    *,
    mode: GroundingMode,
    glosses: bool,
    greek_pipeline: GreekPipeline | None,
    greek_long_input: GreekLongInput,
    grounding_failure: GroundingFailure,
) -> _GroundingOutcome:
    """Build prompt evidence plus separate, non-prompt runtime provenance."""
    failure_policy = _validate_failure_policy(grounding_failure)
    if greek_long_input not in get_args(GreekLongInput):
        valid = ", ".join(repr(mode) for mode in get_args(GreekLongInput))
        raise ValueError(
            f"unknown Greek long-input mode {greek_long_input!r}; valid modes: {valid}"
        )
    failures: list[dict[str, str]] = []

    if script == "greek":
        pipeline, selection = _selected_pipeline(greek_pipeline)
        if greek_long_input != "strict" and not pipeline.neural_active:
            raise ValueError(
                f"greek_long_input={greek_long_input!r} requires a neural Greek pipeline"
            )
        items = _greek_grounding(
            text,
            mode=mode,
            glosses=glosses,
            pipeline=pipeline,
            long_input=greek_long_input,
            failure_policy=failure_policy,
            failures=failures,
        )
        return _GroundingOutcome(
            items,
            {
                "script": script,
                "mode": mode,
                "long_input": greek_long_input,
                "failure_policy": failure_policy,
                "pipeline": _pipeline_runtime(pipeline, selection),
                "failures": failures,
            },
        )

    if greek_pipeline is not None:
        raise ValueError("greek_pipeline is only valid when script='greek'")
    if greek_long_input != "strict":
        raise ValueError("greek_long_input is only valid when script='greek'")

    if script == "lineara":
        try:
            items = _lineara_grounding(text)
        except Exception as exc:
            failures.append(
                {"stage": "Linear A transliteration", "error_type": type(exc).__name__}
            )
            if failure_policy == "strict":
                raise GroundingError(
                    stage="Linear A transliteration",
                    script=script,
                    backend=None,
                    config=None,
                ) from exc
            items = []
    else:
        items = []
    return _GroundingOutcome(
        items,
        {
            "script": script,
            "mode": mode,
            "failure_policy": failure_policy,
            "pipeline": None,
            "failures": failures,
        },
    )


def grounding_for(
    text: str,
    script: str,
    *,
    mode: GroundingMode = "morphology",
    glosses: bool = True,
    greek_pipeline: GreekPipeline | None = None,
    greek_long_input: GreekLongInput = "strict",
    grounding_failure: GroundingFailure = "best-effort",
) -> list[GroundingItem]:
    """Local, deterministic grounding evidence for ``text`` in ``script`` — each item
    tagged with its source (``analysis:morphology`` / ``analysis:syntax`` /
    ``analysis:rarity`` / ``lexicon:idiom`` / ``lemmatizer`` / ``lexicon:LSJ`` /
    ``transliteration``) so the result's `trace()` shows where the grounding came from.

    For ``greek``, ``mode`` selects the grounding style:

    - ``"morphology"`` (default, recommended): deterministic morphology and syntax —
      a per-token line (lemma, part of speech, case/voice/tense) plus a clause skeleton
      (main predicate, subject, object) from the dependency parse, and a rare-word flag.
      **No dictionary glosses**, but it does include a gloss of any **idiom** present (a
      curated, non-compositional multiword expression matched on surface/lemma; source
      ``lexicon:idiom``). Morphology, voice, case-role, and structure are facts the toolkit
      computes reliably and a model can use directly; an auto-selected dictionary gloss can
      surface the wrong or an archaic sense and mislead the model, so this mode omits those.
      An idiom gloss is different: the phrase is non-compositional, so the literal token
      reading is *itself* the error, and the lexicon match is deterministic and
      low-false-positive, which is why it rides with the default.
    - ``"full"``: the ``"morphology"`` lines (including idiom glosses) **and** a gloss layer
      in the configuration
      that helps. Glosses come from a concise, common-sense-first dictionary cascade
      (Middle Liddell, Cunliffe for Homer, Abbott-Smith / Dodson for the NT), cleaned, and
      gated to the rare content words. **Not** LSJ-first-sense: that historical lexicon
      orders senses etymologically, so its lead sense is often the archaic meaning and
      asserting it injects errors; a concise dictionary leads with the common sense and
      helps most on the rare vocabulary a model is likely to miss. Source tag
      ``lexicon:concise``. Best-effort: the glosses are simply absent if no concise
      dictionary is loaded (``greek.use_lexicon("middle-liddell")`` etc.).
    - ``"lemma"``: the lemma-line grounding plus gated content-word LSJ glosses (the prior
      default; retained unchanged for back-compatibility). Source tag ``lexicon:LSJ``.
    - ``"none"``: no grounding.

    Any other ``mode`` raises ``ValueError`` naming the valid modes (a typo must not
    silently change the grounding style).

    ``glosses`` is retained for back-compatibility and is **superseded by** ``mode``:
    it only affects the gloss-bearing modes (``"lemma"``, ``"full"``), where
    ``glosses=False`` drops the glosses (lemma-only / morphology-only). It has no effect
    on ``"morphology"`` (already gloss-free) or ``"none"``.

    ``greek_pipeline`` may be an isolated `GreekPipeline`; when omitted, the historical
    module-default facade remains in use. Passing it for a non-Greek script raises
    ``ValueError`` rather than silently ignoring it. ``greek_long_input`` selects the
    neural sentence contract: strict refusal (the default), explicitly incomplete
    ``"partial"`` output, or reconciled ``"windowed"`` analysis. It is also rejected for
    a non-Greek script rather than ignored. ``grounding_failure`` is
    ``"best-effort"`` by default: required analysis failures yield the evidence still
    available. ``"strict"`` instead raises `GroundingError` on a required analysis or
    transliteration failure. Missing optional dictionaries, the optional rarity corpus,
    and an unmatched idiom are normal absences under either policy.

    The ``"morphology"`` grounding uses the active backends (``greek.pipeline(text,
    parse=True)``): with `use_neural_pipeline` active it carries the neural model's
    predicted morphology and a UD parse; without it, rule-based POS and lemmas still
    populate the token lines and the clause skeleton is simply omitted. Backend-analysis
    failures degrade to fewer or no grounding items under the default policy; strict mode
    raises before a translation provider can be called. Invalid arguments always raise.
    """
    return _build_grounding(
        text,
        script,
        mode=mode,
        glosses=glosses,
        greek_pipeline=greek_pipeline,
        greek_long_input=greek_long_input,
        grounding_failure=grounding_failure,
    ).items


def translate(
    text: str,
    *,
    script: str = "greek",
    target: str = "English",
    mode: GroundingMode = "morphology",
    glosses: bool = True,
    verify: bool = False,
    greek_pipeline: GreekPipeline | None = None,
    greek_long_input: GreekLongInput = "strict",
    grounding_failure: GroundingFailure = "best-effort",
    client: LLMClient | None = None,
) -> ExploratoryResult:
    """Translate ``text`` (a ``greek`` or ``lineara`` string) into ``target``,
    grounded in locally-derived morphology/lexicon/transliteration evidence.

    Exploratory: the grounding is real, the translation is a model hypothesis —
    especially for undeciphered Linear A.

    For ``greek``, ``mode`` (default ``"morphology"``) selects the grounding style; see
    `grounding_for`. The default grounds the model in deterministic morphology and
    syntax (lemma, part of speech, case/voice/tense, clause skeleton) plus a gloss of any
    non-compositional idiom present (``ai.idiom_glosses``), with **no** dictionary glosses
    on ordinary words. Use ``mode="full"`` to add, on top of those morphology lines, a
    gloss layer sourced from a concise, common-sense-first dictionary cascade (Middle
    Liddell, Cunliffe, Abbott-Smith / Dodson), cleaned and gated to the rare content words:
    a concise dictionary leads with the common sense and helps most on rare vocabulary,
    whereas an LSJ-first-sense gloss is often the archaic meaning and misleads. Use
    ``mode="lemma"`` for the older lemma-line plus gated LSJ-gloss grounding, or
    ``mode="none"`` for no grounding. An unrecognized ``mode`` raises ``ValueError``
    naming the valid modes.

    ``glosses`` is retained for back-compatibility and is superseded by ``mode``: it only
    affects the gloss-bearing modes (``"lemma"``, ``"full"``), where ``glosses=False``
    drops the glosses.

    ``greek_pipeline`` selects an isolated `GreekPipeline` for every Greek analysis
    decision used by the grounding. ``None`` preserves the module-default compatibility
    facade. ``greek_long_input`` explicitly selects strict, partial, or overlapping-window
    neural analysis and remains strict by default. ``grounding_failure="best-effort"``
    keeps available evidence when required analysis fails; ``"strict"`` raises
    `GroundingError` before any provider call.

    ``verify`` (Greek only) runs a **translate-then-check-and-repair** pass instead of a
    single grounded call. The text is first translated **raw**, with no grounding in the
    prompt, so the local analysis cannot bias the draft. The full grounding (morphology,
    idiom glosses, and concise glosses, as for ``mode="full"``) is then supplied to a
    second call that checks the draft against it and corrects only definite contradictions
    (wrong voice, subject or object, case relation, a rare word's or idiom's sense, an
    omission or addition), keeping the draft where it is already right. Because the
    grounding only ever reaches the checker, it cannot bias the initial draft; a wrong
    analysis can still mislead the repair step, so the pass is only as sound as the
    grounding it checks against. This reduces definite errors, most on hard text, at the
    cost of a second model call, so it is worth reaching for on hard or high-stakes
    passages and skipping on routine ones. It supersedes ``mode`` for Greek (the checker
    always sees the full grounding); for non-Greek scripts it has no effect and the
    normal single call is used.

    Coverage of rare or inflected forms (and the clause skeleton) depends on the active
    backends, so a warning is raised when only the baseline seed table is loaded (call
    ``aegean.greek.use_treebank()``, or ``use_neural_pipeline()`` for contextual,
    model-predicted morphology and a UD parse, first).
    """
    effective_mode: GroundingMode = "full" if verify and script == "greek" else mode
    outcome = _build_grounding(
        text,
        script,
        mode=effective_mode,
        glosses=glosses,
        greek_pipeline=greek_pipeline,
        greek_long_input=greek_long_input,
        grounding_failure=grounding_failure,
    )
    if (
        script == "greek"
        and effective_mode != "none"
        and not _rich_lemmatizer_active(greek_pipeline)
    ):
        warnings.warn(
            "Grounded Greek translation is using the baseline lemmatizer; morphology and "
            "lexical grounding will miss many rare or inflected forms and the clause "
            "skeleton will be omitted. Call aegean.greek.use_treebank() (or "
            "aegean.greek.use_neural_pipeline() for contextual, model-predicted morphology "
            "and a dependency parse) first for fuller grounding.",
            stacklevel=2,
        )
    source = _SOURCE_NAMES.get(script, script)
    if verify and script == "greek":
        # Translate-then-check-and-repair. Resolve one client so both calls share a
        # provider/model, then translate raw (empty grounding, so the analysis cannot
        # bias the draft) and check that draft against the full grounding.
        c = client if client is not None else _get_client()
        draft = _ai_translate(text, source=source, target=target, grounding=(), client=c)
        result = _ai_verify_translation(
            text,
            draft.text,
            source=source,
            target=target,
            grounding=outcome.items,
            client=c,
        )
    else:
        result = _ai_translate(
            text,
            source=source,
            target=target,
            grounding=outcome.items,
            client=client,
        )
    return replace(result, grounding_runtime=outcome.runtime)


__all__ = [
    "GroundingError",
    "GroundingFailure",
    "GreekLongInput",
    "grounding_for",
    "translate",
]
