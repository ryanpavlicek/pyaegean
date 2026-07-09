"""Which Greek word forms the active lemmatizer cannot resolve: the contribution surface.

`missing_forms` walks a corpus and returns the distinct lexical (`WORD`) forms whose
lemma the lemmatizer could not ground, an ``UNRESOLVED`` baseline miss or, when a backend
returns the surface form unchanged, an ``IDENTITY`` fall-through (the two classes
`aegean.greek.needs_review` flags). Each row carries a total occurrence count and one
representative attestation (document id + position), so a frequent unresolved form is an
obvious candidate for a curated lemma or morphology addition (the "Good first
contributions" menu in CONTRIBUTING). It is the read-only bridge from the per-token
evidence class (`aegean.greek.LemmaSource`) to a sourced data contribution.

The result reflects the CURRENTLY-active lemmatizer: with no backend loaded it is the
zero-dependency offline baseline (a true miss is ``UNRESOLVED``); loading the neural joint
pipeline or a treebank lexicon changes which forms resolve. The walk does not mutate the
corpus and is deterministic: documents are visited in corpus order, tokens in document
order, and rows are sorted by descending count then by form.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.corpus import Corpus

__all__ = ["MissingForm", "missing_forms"]


@dataclass(frozen=True, slots=True)
class MissingForm:
    """One unresolved Greek word form and where to find it.

    - ``form`` — the surface word exactly as it appears in the corpus.
    - ``count`` — how many `WORD` tokens with this exact surface the lemmatizer left
      unresolved (needs review).
    - ``example_doc_id`` — the document id of the first occurrence, in corpus order.
    - ``example_position`` — that token's position: its `Token.position`, or its index
      within the document's token stream when ``position`` is unset.
    """

    form: str
    count: int
    example_doc_id: str
    example_position: int


def missing_forms(corpus: "Corpus", *, limit: int = 0) -> list[MissingForm]:
    """The distinct Greek word forms the active lemmatizer cannot resolve, most frequent first.

    Walks every lexical (`WORD`) token of ``corpus``, lemmatizes each with
    `aegean.greek.lemmatize_sourced`, and keeps the forms whose evidence class needs review
    (`aegean.greek.needs_review`: ``UNRESOLVED`` or ``IDENTITY``). Returns one `MissingForm`
    per distinct surface form with its total count and its first attestation, sorted by
    descending count then by form so the order is stable. ``limit`` caps the number of rows
    returned; ``0`` (the default) returns all of them.

    Read-only (the corpus is never mutated) and zero-dependency. Each distinct form is
    lemmatized once and the verdict cached, so the cost is one lemmatize per distinct word.
    The result reflects whichever lemmatizer is active: the offline baseline by default, or
    a loaded neural / treebank backend.
    """
    from ..core.model import TokenKind
    from .lemmatize import lemmatize_sourced, needs_review

    counts: dict[str, int] = {}
    example: dict[str, tuple[str, int]] = {}
    verdict: dict[str, bool] = {}  # per-form cache of the needs-review decision

    for doc in corpus.documents:
        for i, tok in enumerate(doc.tokens):
            if tok.kind is not TokenKind.WORD:
                continue
            form = tok.text
            flagged = verdict.get(form)
            if flagged is None:
                _, source = lemmatize_sourced(form)
                flagged = needs_review(source)
                verdict[form] = flagged
            if not flagged:
                continue
            counts[form] = counts.get(form, 0) + 1
            if form not in example:
                pos = tok.position if tok.position is not None else i
                example[form] = (doc.id, pos)

    rows = [
        MissingForm(
            form=form,
            count=count,
            example_doc_id=example[form][0],
            example_position=example[form][1],
        )
        for form, count in counts.items()
    ]
    rows.sort(key=lambda m: (-m.count, m.form))
    if limit > 0:
        rows = rows[:limit]
    return rows
