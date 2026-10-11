"""Fill a Greek corpus's per-token annotations from the analysis pipeline.

The review workflow (`aegean.io.review`) exports and re-imports a corpus's
``Token.annotations``; for a corpus that has none yet (any imported text, unlike the
gold-annotated NT), this runs the tagger/lemmatizer over its word tokens and writes the
lemma, POS, and the lemma's evidence class back onto each token, aligned 1:1 (it tags the
document's existing word tokens directly, never re-tokenizing). The result is a new corpus;
the input is not mutated.

Word tokens are grouped by their physical line; punctuation and numerals remain untouched.
Opt-in ``with_dependencies`` analyzes complete neural document token groups, preserves
punctuation in the dependency index domain, and persists morphology, syntax, and receipts.
With built-in annotation, ``with_evidence`` also records exact ``lemma_source``, ``lemma_resolved``,
``lemma_verified``, and ``review_recommended`` fields so review triage does not overload
one boolean. The deprecated ``lemma_known`` compatibility annotation remains during its
deprecation cycle (see `aegean.greek.LemmaSource`)."""

from __future__ import annotations

import json
from dataclasses import replace
from uuid import uuid4
from typing import TYPE_CHECKING, Callable, Literal

from .heldout import TagSentence

if TYPE_CHECKING:
    from ..core.corpus import Corpus

__all__ = ["annotate_corpus"]

_PREDICTION_EVIDENCE_KEYS = frozenset({
    "lemma_source", "lemma_resolved", "lemma_verified", "review_recommended", "lemma_known",
    "upos_verified",
    "neural_analyzed", "analysis_complete", "analysis_warning",
    "analysis_receipt", "analysis_generation", "analysis_kind", "analysis_configuration",
})


def _prediction_annotations(
    annotations: dict[str, str], *, lemma: str, upos: str,
    replaced: tuple[str, ...] = ("lemma", "upos"),
) -> dict[str, str]:
    """Start a fresh prediction while retaining unrelated source and review-history fields."""
    ann = {
        key: value for key, value in annotations.items()
        if key not in _PREDICTION_EVIDENCE_KEYS
    }
    # A review approves a particular analysis, including its context/source. A
    # fresh prediction must not inherit that approval even if the strings agree.
    # Keep the decision details and audit history available for comparison, while
    # marking only the fields this annotator replaces as no longer current.
    for field in replaced:
        ann.pop(f"{field}_verified", None)
        decision_key = f"{field}_review_decision"
        if decision_key in ann:
            ann[decision_key] = "stale"
    ann.update(lemma=lemma, upos=upos)
    return ann


def annotate_corpus(
    corpus: "Corpus",
    *,
    tag_sentence: TagSentence | None = None,
    with_evidence: bool = True,
    with_dependencies: bool = False,
    long_input: Literal["strict", "partial", "windowed"] = "strict",
    progress: Callable[[int, int], None] | None = None,
) -> "Corpus":
    """Return a copy of ``corpus`` with each word token's ``lemma`` / ``upos`` annotations
    filled by the pipeline (plus opt-in neural morphology/syntax and receipt identity,
    and explicit lemma provenance/review fields when
    ``with_evidence``).

    ``tag_sentence`` overrides the tagger (a ``forms -> [(lemma, upos)]`` callable); it carries
    no evidence class, so ``lemma_source`` is written only by the built-in paths. The default
    is the active pipeline: the neural joint model if loaded, else the offline lemmatize + POS
    baseline. Each word's new lemma/POS replaces the prior prediction and clears its
    lemma evidence and neural coverage fields, even when the predicted strings agree.
    Built-in paths record fresh evidence only when ``with_evidence=True``; custom
    ``tag_sentence`` or ``with_evidence=False`` leaves those fields absent. Unrelated
    keys, such as source morphology, and review history remain. Field-level lemma
    and POS review decisions become ``stale``; their reviewer details are retained
    as history. Baseline/custom reviews of unchanged source morphology remain current;
    ``with_dependencies=True`` requires the active neural pipeline and replaces
    morphology/syntax for complete token groups, invalidating their decisions too.
    Every actual invocation records a fresh analysis generation, even for identical outputs;
    no-op review export or review replay does not generate an analysis. Unknown model
    identity is explicit for baseline/custom paths. Keep the original
    corpus separately when comparing source annotations with these predictions.
    Neural input is strict by default. Pass ``long_input="partial"`` only when explicitly
    marked placeholder annotations are useful, or ``long_input="windowed"`` to reconcile
    supported long lines from overlapping whole-word windows; inspect
    ``analysis_complete`` and the analysis receipt in either non-default mode.
    ``progress`` is called as ``progress(done, total)`` once per document (a large corpus under
    the neural pipeline is a long run)."""
    from ..core.corpus import Corpus
    from ..core.model import TokenKind
    from . import joint
    from .lemmatize import (
        LemmaSource,
        lemma_resolved,
        lemma_verified,
        lemmatize_sourced,
        needs_review,
    )
    from .pipeline import _select_token_form, pipeline_tokens
    from .pos import pos_tag

    use_joint = tag_sentence is None and joint.active() is not None
    # Generation describes an actual invocation, not just a content hash. Re-running
    # the same model with identical outputs still requires a fresh review snapshot.
    generation = uuid4().hex
    kind = "neural" if use_joint else "custom" if tag_sentence is not None else "baseline"
    configuration = json.dumps({
        "annotator": "aegean.greek.annotate_corpus", "with_evidence": with_evidence,
        "long_input": long_input, "with_dependencies": with_dependencies,
        "replaced_fields": ["lemma", "upos", "morph", "feats", "head", "deprel", "xpos"]
        if with_dependencies else ["lemma", "upos"], "custom_callable_identity": "unknown" if tag_sentence is not None else None,
    }, sort_keys=True, separators=(",", ":"))

    def _identity(ann: dict[str, str], receipt: str = "unknown") -> None:
        ann.update(analysis_generation=generation, analysis_kind=kind,
                   analysis_configuration=configuration, analysis_receipt=receipt)
    if with_dependencies and not use_joint:
        raise ValueError("with_dependencies=True requires the active neural Greek pipeline")
    if long_input != "strict" and not use_joint:
        raise ValueError(
            f"long_input={long_input!r} requires the active neural Greek pipeline"
        )

    def _evidence(ann: dict[str, str], source: LemmaSource) -> None:
        if with_evidence:
            ann["lemma_source"] = source.value
            ann["lemma_resolved"] = "true" if lemma_resolved(source) else "false"
            ann["lemma_verified"] = "true" if lemma_verified(source) else "false"
            ann["review_recommended"] = "true" if needs_review(source) else "false"
            # Existing deprecated field; new code uses the explicit evidence fields above.
            ann["lemma_known"] = "false" if needs_review(source) else "true"

    total = len(corpus.documents)
    new_docs = []
    for done, doc in enumerate(corpus.documents, start=1):
        new_tokens = list(doc.tokens)
        groups: dict[int, list[int]] = {}
        if use_joint and with_dependencies and any(tok.kind is TokenKind.WORD for tok in doc.tokens):
            # Keep the complete parse domain, including punctuation and source
            # sentences spanning physical lines. The pipeline owns segmentation.
            groups[0] = list(range(len(doc.tokens)))
        else:
            for i, tok in enumerate(doc.tokens):
                if tok.kind is TokenKind.WORD:
                    groups.setdefault(tok.line_no if tok.line_no is not None else 0, []).append(i)
        for idxs in groups.values():
            selected = [_select_token_form(doc.tokens[i]) for i in idxs]
            forms = [form for form, _ in selected]
            if tag_sentence is not None:
                tagged = list(tag_sentence(forms))
                if len(tagged) != len(idxs):
                    raise ValueError(
                        "tag_sentence returned a different token count than the input"
                    )
                for i, (lemma, upos), (_, form_state) in zip(idxs, tagged, selected):
                    ann = _prediction_annotations(
                        doc.tokens[i].annotations, lemma=lemma, upos=upos,
                    )
                    _identity(ann)
                    new_tokens[i] = replace(
                        doc.tokens[i], annotations=ann, form_state=form_state
                    )
            elif use_joint:
                analyzed = pipeline_tokens(
                    [doc.tokens[i] for i in idxs],
                    long_input=long_input,
                    document_id=f"{doc.id}:line-{idxs[0] if idxs else 0}",
                )
                if len(analyzed) != len(idxs):
                    raise ValueError(
                        "typed-token analysis returned a different token count than the input"
                    )
                for rec, i in zip(analyzed, idxs):
                    ann = _prediction_annotations(
                        doc.tokens[i].annotations, lemma=rec.lemma, upos=rec.upos,
                        replaced=("lemma", "upos", "morph", "feats", "head", "deprel", "xpos")
                        if with_dependencies else ("lemma", "upos"),
                    )
                    if with_dependencies:
                        # Complete-token syntax owns these outputs; ordinary lemma/POS
                        # annotation continues to preserve source morphology and parses.
                        for key in ("morph", "feats", "head", "deprel", "xpos"):
                            ann.pop(key, None)
                        for key, value in (("feats", rec.feats), ("head", rec.head),
                                           ("deprel", rec.relation), ("xpos", rec.xpos)):
                            if value is not None:
                                ann[key] = str(value)
                        ann["dependency_sentence_id"] = f"{doc.id}:analysis-sentence:{rec.sentence}"
                        ann["dependency_index"] = str(rec.index)
                    _identity(ann, rec.analysis_receipt.to_json() if rec.analysis_receipt is not None else "unknown")
                    _evidence(ann, rec.lemma_source)
                    if with_evidence and use_joint:
                        ann["neural_analyzed"] = (
                            "true" if rec.neural_analyzed is not False else "false"
                        )
                        ann["analysis_complete"] = (
                            "true" if rec.analysis_complete else "false"
                        )
                        if rec.analysis_warning:
                            ann["analysis_warning"] = rec.analysis_warning
                    new_tokens[i] = replace(
                        doc.tokens[i], annotations=ann, form_state=rec.form_state
                    )
            else:
                # Preserve the established rule-based annotation contract: the
                # pre-A6 path tagged each word independently.  The typed form is
                # additive input selection, not permission to switch the default
                # annotator to the contextual ``pos_tags`` path.
                for i, (form, form_state) in zip(idxs, selected, strict=True):
                    lemma, source = lemmatize_sourced(form)
                    ann = _prediction_annotations(
                        doc.tokens[i].annotations, lemma=lemma, upos=pos_tag(form),
                    )
                    _evidence(ann, source)
                    _identity(ann)
                    new_tokens[i] = replace(
                        doc.tokens[i], annotations=ann, form_state=form_state
                    )
        new_docs.append(replace(doc, tokens=new_tokens))
        if progress is not None:
            progress(done, total)
    return Corpus(new_docs, corpus.sign_inventory, corpus.provenance, corpus.script_id)
