"""Fill a Greek corpus's per-token annotations from the analysis pipeline.

The review workflow (`aegean.io.review`) exports and re-imports a corpus's
``Token.annotations``; for a corpus that has none yet (any imported text, unlike the
gold-annotated NT), this runs the tagger/lemmatizer over its word tokens and writes the
lemma, POS, and the lemma's evidence class back onto each token, aligned 1:1 (it tags the
document's existing word tokens directly, never re-tokenizing). The result is a new corpus;
the input is not mutated.

Word tokens are grouped by their line for context (the unit each corpus already provides);
punctuation and numerals are left untouched. With the neural joint pipeline active, each
line is analyzed in one pass; otherwise the zero-dependency lemmatize + POS baseline is used.
``with_evidence`` also records exact ``lemma_source``, ``lemma_resolved``,
``lemma_verified``, and ``review_recommended`` fields so review triage does not overload
one boolean. The deprecated ``lemma_known`` compatibility annotation remains during its
deprecation cycle (see `aegean.greek.LemmaSource`)."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Callable, Literal

from .heldout import TagSentence

if TYPE_CHECKING:
    from ..core.corpus import Corpus

__all__ = ["annotate_corpus"]


def annotate_corpus(
    corpus: "Corpus",
    *,
    tag_sentence: TagSentence | None = None,
    with_evidence: bool = True,
    long_input: Literal["strict", "partial", "windowed"] = "strict",
    progress: Callable[[int, int], None] | None = None,
) -> "Corpus":
    """Return a copy of ``corpus`` with each word token's ``lemma`` / ``upos`` annotations
    filled by the pipeline (plus explicit lemma provenance/review fields when
    ``with_evidence``).

    ``tag_sentence`` overrides the tagger (a ``forms -> [(lemma, upos)]`` callable); it carries
    no evidence class, so ``lemma_source`` is written only by the built-in paths. The default
    is the active pipeline: the neural joint model if loaded, else the offline lemmatize + POS
    baseline. Existing annotations on a token are preserved except for the keys written here.
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
    from .pos import pos_tag

    use_joint = tag_sentence is None and joint.active() is not None
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
            # Compatibility field retained through its deprecation cycle.
            ann["lemma_known"] = "false" if needs_review(source) else "true"

    total = len(corpus.documents)
    new_docs = []
    for done, doc in enumerate(corpus.documents, start=1):
        new_tokens = list(doc.tokens)
        groups: dict[int, list[int]] = {}
        for i, tok in enumerate(doc.tokens):
            if tok.kind is TokenKind.WORD:
                groups.setdefault(tok.line_no if tok.line_no is not None else 0, []).append(i)
        for idxs in groups.values():
            forms = [doc.tokens[i].text for i in idxs]
            if tag_sentence is not None:
                for i, (lemma, upos) in zip(idxs, tag_sentence(forms)):
                    ann = {**doc.tokens[i].annotations, "lemma": lemma, "upos": upos}
                    new_tokens[i] = replace(doc.tokens[i], annotations=ann)
            elif use_joint:
                ana = joint.analyze_sentence(forms, long_input=long_input)
                resolved = ana.lemma_resolved or (True,) * len(forms)
                override = ana.lemma_source_override  # Lever B offline-rescue sources, else ()
                for k, i in enumerate(idxs):
                    if ana.lemma_source:
                        src = ana.lemma_source[k]
                    elif resolved[k]:
                        src = LemmaSource.NEURAL
                    elif override and override[k]:
                        src = LemmaSource(override[k])  # grounded SEED / PARADIGM offline rescue
                    else:
                        src = LemmaSource.IDENTITY
                    ann = {**doc.tokens[i].annotations, "lemma": ana.lemma[k], "upos": ana.upos[k]}
                    _evidence(ann, src)
                    if with_evidence:
                        ann["neural_analyzed"] = (
                            "true" if not ana.analyzed or ana.analyzed[k] else "false"
                        )
                        ann["analysis_complete"] = "true" if ana.complete else "false"
                        if ana.warnings:
                            ann["analysis_warning"] = ana.warnings[0]
                    new_tokens[i] = replace(doc.tokens[i], annotations=ann)
            else:
                for i in idxs:
                    form = doc.tokens[i].text
                    lemma, src = lemmatize_sourced(form)
                    ann = {**doc.tokens[i].annotations, "lemma": lemma, "upos": pos_tag(form)}
                    _evidence(ann, src)
                    new_tokens[i] = replace(doc.tokens[i], annotations=ann)
        new_docs.append(replace(doc, tokens=new_tokens))
        if progress is not None:
            progress(done, total)
    return Corpus(new_docs, corpus.sign_inventory, corpus.provenance, corpus.script_id)
