"""Hybrid translation with local, provisional Greek analysis and lexicon evidence.

The zero-dependency baseline provides limited rule/lookup analyses; an explicitly
activated neural pipeline supplies model predictions, including morphology and
syntax. Backend identity, field provenance and degraded coverage accompany the
evidence shown to the model. Repeatable computation does not establish linguistic
correctness. Source annotations and scholarly decisions can be supplied explicitly.

``morphology`` supplies token analyses, a clause skeleton when available, and idiom
matches. ``full`` adds optional concise dictionary candidates; ``lemma`` retains the
legacy lemma lines and optional LSJ glosses; ``none`` disables automatic grounding.
No mode guarantees correct contextual readings or translation quality. Strict and
best-effort failure policies remain explicit, and no backend is loaded implicitly.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Literal, get_args

if TYPE_CHECKING:
    from ..greek.pipeline import TokenRecord
    from ..greek.runtime import GreekPipeline

from ..ai import translate as _ai_translate
from ..ai import verify_translation as _ai_verify_translation
from ..ai.capabilities import _validate_source_context, _validate_translation_max_tokens
from ..ai.client import ExploratoryResult, LLMClient
from ..ai.client import get_client as _get_client
from ..ai.grounding import GroundingItem, as_item, content_glosses
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
# Aspect=Imp) never collide; aspect tags retain the supplying dataset's convention.
_FEAT_SHORT = {
    ("Case", "Nom"): "nom", ("Case", "Gen"): "gen", ("Case", "Dat"): "dat",
    ("Case", "Acc"): "acc", ("Case", "Voc"): "voc",
    ("Number", "Sing"): "sg", ("Number", "Plur"): "pl", ("Number", "Dual"): "du",
    ("Gender", "Masc"): "m", ("Gender", "Fem"): "f", ("Gender", "Neut"): "n",
    ("Voice", "Act"): "active", ("Voice", "Mid"): "middle", ("Voice", "Pass"): "passive",
    ("Tense", "Pres"): "pres", ("Tense", "Past"): "past-tag", ("Tense", "Fut"): "fut",
    ("Tense", "Aor"): "aorist-form", ("Tense", "Pqp"): "pluperf",
    ("VerbForm", "Fin"): "finite", ("VerbForm", "Inf"): "infinitive",
    ("VerbForm", "Part"): "participle",
    ("Mood", "Ind"): "ind", ("Mood", "Sub"): "subj", ("Mood", "Opt"): "opt",
    ("Mood", "Imp"): "imper",
    ("Person", "1"): "1st", ("Person", "2"): "2nd", ("Person", "3"): "3rd",
}

# Order in which morphological features are rendered on a token line.
_FEAT_KEYS = (
    "Case", "Number", "Gender", "Voice", "Tense", "Aspect", "Mood", "VerbForm", "Person"
)

_CLAUSE_RELATIONS = frozenset({"ccomp", "xcomp", "advcl", "acl", "csubj", "parataxis"})
_MAX_CLAUSE_PREDICATES = 12
_MAX_ROLE_TOKENS = 8
_MAX_CLAUSE_MARKERS = 4


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
    Unknown values fall back to lower-case; absent features are skipped. ``Past``
    remains a morphological tag: without an aspect or a more specific tense tag,
    it does not establish an aorist form, let alone temporal past."""
    if not feats or feats == "_":
        return ""
    parsed = dict(kv.split("=", 1) for kv in feats.split("|") if "=" in kv)
    out: list[str] = []
    for k in keys:
        v = parsed.get(k)
        if v is None:
            continue
        out.append(f"Aspect={v}" if k == "Aspect" else _FEAT_SHORT.get((k, v), v.lower()))
    return " ".join(out)


def _tense_interpretation_note(feats: str | None) -> str:
    """Explain the limit of a Greek tense tag without inferring a tense or time."""
    if not feats or feats == "_":
        return ""
    parsed = dict(kv.split("=", 1) for kv in feats.split("|") if "=" in kv)
    tense = parsed.get("Tense")
    notes: list[str] = []
    if tense == "Past":
        notes.append("UD Past is a morphological tag; it alone does not identify Greek tense/aspect or event time")
    if "Aspect" in parsed:
        # The bundled Perseus conversion maps Greek perfect 'r' to Past+Perf,
        # and imperfect 'i' to Past+Imp. Reading Perf universally as perfective
        # would conflate the perfect with the aorist in those records.
        notes.append("Aspect tags retain the supplying dataset's convention")
    if tense is not None and (
        parsed.get("VerbForm") in {"Inf", "Part", "Ger", "Gdv"} or parsed.get("Mood") != "Ind"
    ):
        # Missing Mood is not evidence that the form is indicative. In particular,
        # an infinitive/participle may omit Mood while still carrying Tense=Past.
        notes.append("no tense-time inference outside the indicative or with unspecified mood")
    return "; ".join(notes)


def _dependency_children(rt: TokenRecord, recs: list[TokenRecord]) -> list[TokenRecord]:
    """Direct supplied dependents, scoped to the predicate's own sentence."""
    return sorted(
        (r for r in recs if r.sentence == rt.sentence and r.head == rt.index and r.relation),
        key=lambda r: r.index,
    )


def _relation_base(record: TokenRecord) -> str:
    return (record.relation or "").split(":", 1)[0]


def _coordinated_role(role: TokenRecord, recs: list[TokenRecord]) -> str:
    """Display explicit conjuncts without inventing shared or controlled subjects."""
    members: list[TokenRecord] = []
    pending = [role]
    seen: set[int] = set()
    while pending:
        member = pending.pop()
        if member.index in seen:
            continue
        seen.add(member.index)
        members.append(member)
        pending.extend(
            r for r in _dependency_children(member, recs) if _relation_base(r) == "conj"
        )
    members.sort(key=lambda r: r.index)
    shown = members[:_MAX_ROLE_TOKENS]
    result = " + ".join(r.text for r in shown)
    if len(members) > len(shown):
        result += f" + … ({len(members) - len(shown)} coordinated tokens omitted)"
    markers = sorted(
        (
            r for member in shown for r in _dependency_children(member, recs)
            if _relation_base(r) == "cc"
        ),
        key=lambda r: r.index,
    )
    if markers:
        result += " (coordination: " + ", ".join(r.text for r in markers[:_MAX_CLAUSE_MARKERS])
        if len(markers) > _MAX_CLAUSE_MARKERS:
            result += ", …"
        result += ")"
    return result


def _root_skeleton(rt: TokenRecord, recs: list[TokenRecord]) -> str:
    """Summarize one supplied predicate and its explicit dependency links.

    Copular predication retains the copula plus predicate nominal/adjective,
    including for nested clauses. No subject is moved, inherited, or inferred.
    """
    kids = _dependency_children(rt, recs)
    copulas = [r for r in kids if _relation_base(r) == "cop"]
    cop = copulas[0] if copulas else None
    parts: list[str] = []
    if cop is not None:
        kind = "predicate adjective" if rt.upos == "ADJ" else "predicate nominal"
        parts.append(f"predicate {cop.text} + {rt.lemma} ({kind})")
        if len(copulas) > 1:
            parts.append("additional copula links in supplied parse")
    else:
        pred = _readable_feats(rt.feats, "Voice", "Tense", "Aspect", "Mood", "VerbForm", "Number", "Person")
        label = "main predicate" if rt.head == 0 else "subordinate predicate"
        if _relation_base(rt) in {"conj", "parataxis"}:
            label = "coordinated predicate" if _relation_base(rt) == "conj" else "paratactic predicate"
        parts.append(f"{label} '{rt.text}' ({rt.lemma}{', ' + pred if pred else ''})")
    if rt.head != 0:
        governor = next(
            (r for r in recs if r.sentence == rt.sentence and r.index == rt.head), None
        )
        attachment = f"'{governor.text}'" if governor is not None else f"unavailable token {rt.head}"
        parts.append(f"dependency {rt.relation} → {attachment}")
    markers = [r for r in kids if _relation_base(r) == "mark"]
    if markers:
        marker_text = ", ".join(r.text for r in markers[:_MAX_CLAUSE_MARKERS])
        if len(markers) > _MAX_CLAUSE_MARKERS:
            marker_text += ", … (markers omitted)"
        parts.append(f"marked by {marker_text}")
    subjects = [r for r in kids if _relation_base(r) in {"nsubj", "csubj"}]
    if subjects:
        for subj in subjects[:_MAX_ROLE_TOKENS]:
            label = "clausal subject" if _relation_base(subj) == "csubj" else "subject"
            parts.append(f"{label} {_coordinated_role(subj, recs)}")
        if len(subjects) > _MAX_ROLE_TOKENS:
            parts.append(f"… ({len(subjects) - _MAX_ROLE_TOKENS} subject links omitted)")
    else:
        parts.append("no explicit subject in supplied parse")
    for relation, label in (("obj", "object"), ("iobj", "indirect object")):
        objects = [r for r in kids if _relation_base(r) == relation]
        parts.extend(f"{label} {_coordinated_role(obj, recs)}" for obj in objects[:_MAX_ROLE_TOKENS])
        if len(objects) > _MAX_ROLE_TOKENS:
            parts.append(f"… ({len(objects) - _MAX_ROLE_TOKENS} {label} links omitted)")
    note = _tense_interpretation_note((cop or rt).feats)
    if note:
        parts.append(note)
    return "; ".join(parts)


def _clause_skeleton(recs: list[TokenRecord]) -> str:
    """Bounded summary of roots and explicit subordinate/coordinated predicates.

    A dependency relation licenses inclusion; lexical knowledge never repairs
    the parse. All token/head comparisons stay within the token's sentence.
    """
    predicates: list[TokenRecord] = []
    for rt in sorted(recs, key=lambda r: (r.sentence, r.head != 0, r.index)):
        kids = _dependency_children(rt, recs)
        has_cop = any(_relation_base(r) == "cop" for r in kids)
        has_subject = any(_relation_base(r) in {"nsubj", "csubj"} for r in kids)
        is_predicate = rt.upos in {"VERB", "AUX", "ADJ", "NOUN", "PROPN"} or has_cop
        if rt.head == 0 and is_predicate:
            predicates.append(rt)
        elif rt.head is not None and rt.relation and is_predicate:
            relation = _relation_base(rt)
            if relation in _CLAUSE_RELATIONS or (
                relation == "conj" and (rt.upos in {"VERB", "AUX"} or has_cop or has_subject)
            ):
                predicates.append(rt)
    clauses = [_root_skeleton(rt, recs) for rt in predicates[:_MAX_CLAUSE_PREDICATES]]
    if len(predicates) > len(clauses):
        clauses.append(f"… ({len(predicates) - len(clauses)} further predicates omitted)")
    return " | ".join(clauses)


def _analysis_records(
    text: str,
    *,
    pipeline: GreekPipeline,
    parse: bool,
    long_input: GreekLongInput,
    failure_policy: GroundingFailure,
    failures: list[dict[str, str]],
    coverage: dict[str, Any] | None = None,
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

    words = [record for record in records if record.upos != "PUNCT"]
    usable = [record for record in words if record.neural_analyzed is not False]
    parsed = [record for record in usable if record.head is not None and record.relation]
    if coverage is not None:
        coverage.update({
            "tokens": len(words),
            "analyzed_tokens": len(usable),
            "complete_tokens": sum(record.analysis_complete for record in usable),
            "lemma_tokens": sum(record.lemma_resolved for record in usable),
            "feature_tokens": sum(record.feats is not None for record in usable),
            "dependency_tokens": len(parsed),
        })
    if parse and len(parsed) != len(usable) and not failures:
        failed("dependency analysis", RuntimeError("required dependency fields unavailable"))
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
    """Local morphology + syntax predictions for Greek, no dictionary glosses.

    Produces, in order: an optional bounded dependency summary including subordinate
    predicates and explicitly coordinated subjects, one readable line per non-punct
    token retaining raw UD features, and an optional rare-word flag line. Tense labels
    describe morphology; they do not establish temporal past in nonindicatives.
    ``analysis`` is normally produced once by the selected
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

    usable = [record for record in analysis if record.neural_analyzed is not False]
    skeleton = _clause_skeleton(usable)
    if skeleton:
        out.append(
            GroundingItem(
                "Clause skeleton: predicted dependency links; " + skeleton
                + ". Attachments may be wrong; implicit, controlled, or shared subjects are not inferred.",
                source="analysis:syntax",
                ref="clause",
                status="predicted",
                provenance={
                    "fields": ["sentence", "index", "head", "relation", "upos", "lemma", "feats"],
                    "scope": "supplied sentence-local dependency links and explicit conjuncts",
                    "inferred_subjects": False,
                    "limits": {
                        "predicates": _MAX_CLAUSE_PREDICATES,
                        "role_tokens": _MAX_ROLE_TOKENS,
                        "markers": _MAX_CLAUSE_MARKERS,
                    },
                },
            )
        )

    # One compact morphology line per non-punctuation token.
    for r in usable:
        if r.upos == "PUNCT":
            continue
        morph = _readable_feats(r.feats, *_FEAT_KEYS)
        body = f"{r.text} = {r.lemma} ({r.upos.lower()}{', ' + morph if morph else ''})"
        if r.feats and r.feats != "_":
            body += f"; UD FEATS: {r.feats}"
        note = _tense_interpretation_note(r.feats)
        if note:
            body += "; " + note
        out.append(GroundingItem(
            body, source="analysis:morphology", ref=r.text, status="predicted",
            provenance={
                "lemma_source": r.lemma_source.value,
                "sentence": r.sentence,
                "index": r.index,
                "raw_feats": r.feats,
                "head": r.head,
                "relation": r.relation,
                "field_status": {"lemma": "human-reviewed" if r.lemma_verified else "predicted",
                                 "upos": "predicted", "feats": "predicted" if r.feats is not None else "unavailable",
                                 "head": "predicted" if r.head is not None else "unavailable",
                                 "relation": "predicted" if r.relation else "unavailable"},
                "lemma_resolved": r.lemma_resolved,
                "review_recommended": r.review_recommended,
                "analysis_complete": r.analysis_complete,
            },
        ))

    rare_line = _rare_word_line(text, analysis=usable)
    if rare_line:
        out.append(
            GroundingItem(
                "Rare / easily-mistranslated words: " + rare_line,
                source="analysis:rarity",
                ref="rare",
                status="derived",
                provenance={"reference": "cached full Greek NT", "depends_on": "predicted lemmas"},
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
    coverage: dict[str, Any],
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
        coverage=coverage,
    )
    records = [record for record in records if record.neural_analyzed is not False]

    if mode in ("morphology", "full"):
        out = _morphology_items(text, analysis=records)
        # Idiom matches are dictionary candidates, not verified contextual readings.
        out.extend(idiom_glosses(text, analysis=records))
        if mode == "full" and glosses:
            # Optional concise dictionary candidates; their contextual suitability
            # still requires interpretation. Empty if no dictionary is loaded.
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
            status="human-reviewed" if record.lemma_verified else "predicted",
            provenance={"field": "lemma", "lemma_source": record.lemma_source.value,
                        "analysis_complete": record.analysis_complete},
        )
        for record in records
        if record.upos != "PUNCT" and record.lemma_resolved and record.neural_analyzed is not False
    ]
    if glosses:
        # Gated LSJ glosses for content words — best-effort, empty without greek.use_lsj().
        out.extend(content_glosses(text, analysis=records))
    return out


def _lineara_grounding(text: str) -> list[GroundingItem]:
    from ..scripts.lineara.phonetic import word_to_phonetic

    return [
        GroundingItem(f"{w} → /{word_to_phonetic(w)}/", source="transliteration", ref=w,
                      status="derived", provenance={"scope": "sign transliteration, not decipherment"})
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
    """Build evidence with a compact availability summary and full runtime provenance."""
    failure_policy = _validate_failure_policy(grounding_failure)
    if greek_long_input not in get_args(GreekLongInput):
        valid = ", ".join(repr(mode) for mode in get_args(GreekLongInput))
        raise ValueError(
            f"unknown Greek long-input mode {greek_long_input!r}; valid modes: {valid}"
        )
    failures: list[dict[str, str]] = []

    if script == "greek":
        pipeline, selection = _selected_pipeline(greek_pipeline)
        coverage: dict[str, Any] = {"tokens": None, "analyzed_tokens": 0, "complete_tokens": 0,
                    "lemma_tokens": 0, "feature_tokens": 0, "dependency_tokens": 0}
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
            coverage=coverage,
        )
        required = [] if mode == "none" else ["morphology"]
        if mode in {"morphology", "full"}:
            required.append("dependencies")
        missing = []
        if mode != "none":
            total = coverage["tokens"]
            if not coverage["analyzed_tokens"] and failures:
                missing.append("morphology")
            if mode in {"morphology", "full"}:
                if total is None or coverage["feature_tokens"] < total:
                    missing.append("morphological features")
                if total is None or coverage["dependency_tokens"] < total:
                    missing.append("dependencies")
            if total is not None and coverage["complete_tokens"] < total:
                missing.append("complete analysis coverage")
            summary = (
                f"Greek analysis backend: {pipeline.config.backend} ({selection}); "
                f"required stages: {', '.join(required)}; "
                f"coverage: {coverage['analyzed_tokens']}/{total if total is not None else 'unknown'} tokens analyzed, "
                f"{coverage['feature_tokens']} with morphological features, "
                f"{coverage['dependency_tokens']} with dependencies; "
                f"missing stages: {', '.join(missing) or 'none'}; "
                f"operation: {'degraded' if failures or missing else 'complete'}. "
                "Analyses are provisional; resolved lemmas and absent review flags do not certify correctness."
            )
            items.insert(0, GroundingItem(summary, source="analysis:availability", status="runtime"))
        return _GroundingOutcome(
            items,
            {
                "script": script,
                "mode": mode,
                "long_input": greek_long_input,
                "failure_policy": failure_policy,
                "pipeline": _pipeline_runtime(pipeline, selection),
                "failures": failures,
                "required_stages": required,
                "missing_stages": missing,
                "coverage": coverage,
                "degraded": bool(failures or missing),
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
    """Build local evidence with status and provenance visible in prompts and traces.

    Greek modes are ``morphology`` (token analyses, optional clause skeleton and
    idiom matches), ``full`` (adds concise dictionary candidates), ``lemma``
    (lemma lines and optional gated LSJ glosses), and ``none`` (no automatic
    evidence). ``glosses=False`` omits dictionary candidates in full/lemma modes.
    Dictionary matches and grammatical predictions can be wrong in context.

    A leading availability item reports the selected backend, required stages,
    missing stages and token coverage. Per-token evidence distinguishes lemma
    source, resolution and review triage from human verification. The baseline
    is a limited rule/lookup backend; it is never silently upgraded to neural.
    A neural backend must be activated explicitly on ``greek_pipeline`` or the
    module-default facade. No model or dictionary is downloaded by this function.

    ``greek_pipeline=None`` retains the module-default compatibility facade; an
    explicit instance owns analysis in isolation. ``greek_long_input`` selects
    strict, partial or windowed neural analysis. ``grounding_failure='strict'``
    raises `GroundingError` on required analysis failure before a provider call;
    best-effort retains available evidence and reports degradation. Missing
    optional dictionaries/rarity corpora and unmatched idioms are normal absences.
    Invalid modes, failure policies and script/backend combinations raise.
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
    style: Literal["annotated", "concise"] = "annotated",
    source_context: str | None = None,
    max_tokens: int = 2048,
    greek_pipeline: GreekPipeline | None = None,
    greek_long_input: GreekLongInput = "strict",
    grounding_failure: GroundingFailure = "best-effort",
    grounding: Iterable[str | GroundingItem] = (),
    client: LLMClient | None = None,
) -> ExploratoryResult:
    """Translate with local provisional evidence, returning an exploratory result.

    See `grounding_for` for modes, backend selection and failure policies.
    ``grounding`` accepts additional `GroundingItem` evidence, including explicit
    source annotations and field-level review decisions from
    ``ai.annotation_evidence``. Its status/provenance reaches the provider along
    with automatic predictions; it does not implicitly replace or certify them.
    ``mode='none'`` disables automatic grounding but retains supplied evidence.

    ``style='annotated'`` includes model-reported uncertainty and correction
    details in labeled output; ``'concise'`` keeps the reading short while
    retaining those details in ``data``, JSON and ``trace()``. For structured
    responses, ``text`` contains only the translation. Unstructured provider
    responses remain available verbatim and are explicitly marked as such.

    ``source_context`` supplies surrounding text, speaker labels, or cited source
    notes separately from the passage to translate. Both drafting and checking
    receive the same context and retain it exactly in ``data['source_context']``.
    Only ``text`` is analyzed and translated; context is untrusted source material,
    not instructions. No surrounding text is fetched or inferred automatically.
    ``max_tokens`` sets a positive output-token allowance for each provider call
    (default 2,048); it does not trigger retries or format-repair requests.

    ``verify=True`` (Greek only) generates an ungrounded draft then asks the same
    provider to check it against full grounding and supplied evidence. A wrong
    analysis can still mislead the repair. Grounding cannot bias the initial draft
    because the first model call receives no grounding. It remains exploratory,
    is not independent scholarly verification, and has no guarantee of improving
    semantic quality. The original draft, including its notes and provenance,
    remains available as ``result.draft``. Corrections and their reasons are
    model reports, not accepted human review decisions. Qualified raters are
    needed to evaluate translation quality.

    Strict grounding failures stop before either provider call. Best-effort
    degradation and limited baseline coverage are reported through warnings,
    prompt evidence, ``grounding_runtime``, and labeled/trace output. Model and
    dictionary activation remains opt-in; no downloads occur here.
    """
    if style not in ("annotated", "concise"):
        raise ValueError("style must be annotated or concise")
    _validate_source_context(source_context)
    _validate_translation_max_tokens(max_tokens)
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
    # Explicit source annotations and field-level scholarly decisions supplement
    # predictions; the provider sees their distinct status and supporting details.
    supplied = [as_item(item) for item in grounding if str(item)]
    outcome.items.extend(supplied)
    if (
        script == "greek"
        and effective_mode != "none"
        and not _rich_lemmatizer_active(greek_pipeline)
    ):
        warnings.warn(
            "Grounded Greek translation is using the baseline lemmatizer; rule/lookup "
            "lemmas and POS are limited and provisional. Call aegean.greek.use_treebank() (or "
            "aegean.greek.use_neural_pipeline() for contextual, model-predicted morphology "
            "and a dependency parse) first for fuller grounding.",
            stacklevel=2,
        )
    if outcome.runtime.get("degraded"):
        stages = ", ".join(outcome.runtime.get("missing_stages", ())) or "local analysis"
        warnings.warn(
            f"Greek grounding is degraded with the selected {outcome.runtime['pipeline']['backend']} "
            f"backend; unavailable or incomplete: {stages}. See grounding_runtime for coverage "
            "and failed stages; predictions remain provisional.",
            stacklevel=2,
        )
    source = _SOURCE_NAMES.get(script, script)
    if verify and script == "greek":
        # Translate-then-check-and-repair. Resolve one client so both calls share a
        # provider/model, then translate raw (empty grounding, so the analysis cannot
        # bias the draft) and check that draft against the full grounding.
        c = client if client is not None else _get_client()
        draft = _ai_translate(
            text, source=source, target=target, grounding=(), style=style, client=c,
            source_context=source_context,
            max_tokens=max_tokens,
        )
        result = _ai_verify_translation(
            text,
            draft,
            source=source,
            target=target,
            grounding=outcome.items,
            style=style,
            source_context=source_context,
            max_tokens=max_tokens,
            client=c,
        )
    else:
        result = _ai_translate(
            text,
            source=source,
            target=target,
            grounding=outcome.items,
            style=style,
            source_context=source_context,
            max_tokens=max_tokens,
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
