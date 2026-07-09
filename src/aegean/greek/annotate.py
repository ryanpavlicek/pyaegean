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
``with_evidence`` also records ``lemma_source`` and ``lemma_known`` so the review table's
"needs review" triage works (see `aegean.greek.LemmaSource`)."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from .heldout import TagSentence

if TYPE_CHECKING:
    from ..core.corpus import Corpus

__all__ = ["annotate_corpus"]


def annotate_corpus(
    corpus: "Corpus", *, tag_sentence: TagSentence | None = None, with_evidence: bool = True
) -> "Corpus":
    """Return a copy of ``corpus`` with each word token's ``lemma`` / ``upos`` annotations
    filled by the pipeline (and, when ``with_evidence``, ``lemma_source`` / ``lemma_known``).

    ``tag_sentence`` overrides the tagger (a ``forms -> [(lemma, upos)]`` callable); it carries
    no evidence class, so ``lemma_source`` is written only by the built-in paths. The default
    is the active pipeline: the neural joint model if loaded, else the offline lemmatize + POS
    baseline. Existing annotations on a token are preserved except for the keys written here."""
    from ..core.corpus import Corpus
    from ..core.model import TokenKind
    from . import joint
    from .lemmatize import LemmaSource, lemmatize_sourced, needs_review
    from .pos import pos_tag

    use_joint = tag_sentence is None and joint.active() is not None

    def _evidence(ann: dict[str, str], source: LemmaSource) -> None:
        if with_evidence:
            ann["lemma_source"] = source.value
            ann["lemma_known"] = "false" if needs_review(source) else "true"

    new_docs = []
    for doc in corpus.documents:
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
                ana = joint.analyze_sentence(forms)
                resolved = ana.lemma_resolved or (True,) * len(forms)
                for k, i in enumerate(idxs):
                    src = LemmaSource.NEURAL if resolved[k] else LemmaSource.IDENTITY
                    ann = {**doc.tokens[i].annotations, "lemma": ana.lemma[k], "upos": ana.upos[k]}
                    _evidence(ann, src)
                    new_tokens[i] = replace(doc.tokens[i], annotations=ann)
            else:
                for i in idxs:
                    form = doc.tokens[i].text
                    lemma, src = lemmatize_sourced(form)
                    ann = {**doc.tokens[i].annotations, "lemma": lemma, "upos": pos_tag(form)}
                    _evidence(ann, src)
                    new_tokens[i] = replace(doc.tokens[i], annotations=ann)
        new_docs.append(replace(doc, tokens=new_tokens))
    return Corpus(new_docs, corpus.sign_inventory, corpus.provenance, corpus.script_id)
