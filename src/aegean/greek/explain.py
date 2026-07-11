"""Human-readable explanations of what the analysis pipeline did, and why.

`explain_pipeline` runs :func:`aegean.greek.pipeline` and re-expresses each
`TokenRecord` as a `TokenExplanation`: the surface form, the analysis fields
(UPOS, lemma, morphological features), the lemma's evidence class
(`LemmaSource`), whether the token needs human review, and a one-line
plain-language note saying what that evidence class means. It is a rendering
layer over the records the pipeline already produces: it never re-runs a
tagger, lemmatizer, or model of its own, so the explanations cannot diverge
from what `pipeline` actually did.

Backends follow whatever is active, exactly as `pipeline` does: the
zero-dependency offline cascade by default, or the joint neural pipeline when
``use_neural_pipeline()`` has been called (the notes say so, and morphology is
filled from its FEATS output).

The source classes are the honesty surface: ``attested`` / ``neural`` /
``rule`` / ``seed`` are grounded analyses, ``identity`` / ``unresolved`` are
fall-throughs a human should verify. There are deliberately NO confidence
numbers anywhere in this output: an uncalibrated score invites false
confidence, so the evidence CLASS is the whole claim (source-class only).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .lemmatize import LemmaSource, needs_review

__all__ = ["TokenExplanation", "explain_pipeline", "render_explanations"]


# One plain-language line per evidence class. NEURAL and IDENTITY get their
# wording picked at run time so the note can say which stack produced them.
_NOTES: dict[LemmaSource, str] = {
    LemmaSource.ATTESTED: "lemma attested in the treebank lexicon",
    LemmaSource.RULE: "derived by a conservative inflection rule (ending substitution)",
    LemmaSource.SEED: "from the bundled seed table (closed-class or high-frequency form)",
    LemmaSource.UNRESOLVED: (
        "no analysis found; the normalized surface form is shown and flagged for review"
    ),
    LemmaSource.PUNCT: "punctuation or numeral; trivially its own lemma",
}
_NEURAL_JOINT = "predicted by the joint neural pipeline (one contextual model pass)"
_NEURAL_BACKEND = "predicted by an active trained lemmatizer backend"
_IDENTITY_JOINT = (
    "the neural pipeline returned the surface form unchanged; "
    "no analysis found, flagged for review"
)
_IDENTITY_BACKEND = (
    "a backend returned the surface form unchanged; no analysis found, flagged for review"
)


@dataclass(frozen=True, slots=True)
class TokenExplanation:
    """One token's analysis with its evidence class spelled out in plain language.

    ``lemma_source`` is the lemma's evidence class (see `LemmaSource`) and is
    the entire trust claim: there are deliberately no confidence numbers.
    ``needs_review`` is True for the two ungrounded classes (an ``identity``
    fall-through or an ``unresolved`` miss). ``morphology`` is the UD FEATS
    string when the neural pipeline produced one, else ``None``. ``note`` says
    in one line what the evidence class means for this token."""

    token: str
    upos: str
    lemma: str
    lemma_source: LemmaSource
    needs_review: bool
    morphology: str | None
    note: str


def explain_pipeline(text: str) -> list[TokenExplanation]:
    """Analyze ``text`` with `pipeline` and explain each token's record.

    Returns one `TokenExplanation` per token, in pipeline order: the surface
    form, UPOS, lemma, the lemma's evidence class with a plain-language note,
    whether it needs review, and the morphology (FEATS) when the neural
    pipeline filled it. Derived entirely from the `TokenRecord` fields
    `pipeline` returns, so it reflects exactly the backends that were active
    for that call (activate them first with the ``use_*`` functions). Empty
    or whitespace-only input yields an empty list.

    The evidence class is the honesty surface; there are deliberately no
    confidence numbers (source-class only)."""
    from . import joint
    from .pipeline import pipeline

    # The same backend check pipeline() itself makes; used only to word the notes.
    neural_active = joint.active() is not None
    explanations: list[TokenExplanation] = []
    for rec in pipeline(text):
        source = rec.lemma_source
        if source is LemmaSource.NEURAL:
            note = _NEURAL_JOINT if neural_active else _NEURAL_BACKEND
        elif source is LemmaSource.IDENTITY:
            note = _IDENTITY_JOINT if neural_active else _IDENTITY_BACKEND
        else:
            note = _NOTES[source]
        explanations.append(
            TokenExplanation(
                token=rec.text,
                upos=rec.upos,
                lemma=rec.lemma,
                lemma_source=source,
                needs_review=needs_review(source),
                morphology=rec.feats,
                note=note,
            )
        )
    return explanations


def render_explanations(explanations: Sequence[TokenExplanation]) -> str:
    """Render explanations as an aligned plain-text table for terminal display.

    Columns: token, upos, lemma, source, review, morphology, note. The
    ``review`` cell reads ``review`` for a token to verify and stays blank for
    a grounded one; ``morphology`` is blank when the record carried none.
    Returns ``"(no tokens)"`` for an empty list."""
    if not explanations:
        return "(no tokens)"
    header = ["token", "upos", "lemma", "source", "review", "morphology", "note"]
    rows = [
        [
            e.token,
            e.upos,
            e.lemma,
            e.lemma_source.value,
            "review" if e.needs_review else "",
            e.morphology or "",
            e.note,
        ]
        for e in explanations
    ]
    widths = [max(len(r[i]) for r in [header, *rows]) for i in range(len(header) - 1)]
    lines: list[str] = []
    for r in [header, *rows]:
        cells = [r[i].ljust(widths[i]) for i in range(len(widths))]
        lines.append(("  ".join(cells) + "  " + r[-1]).rstrip())
    return "\n".join(lines)
