"""A grounded-generation eval harness: measure how faithfully the AI layer uses
its grounding — does the output *use* the evidence, and does it *avoid*
fabricating beyond it?

The generative layer is exploratory by construction, so its value rests on
**grounding fidelity**, not factual authority. This harness measures that the way
the lemmatizer is measured: fixed cases with known evidence, scored for two
things —

- **groundedness**: of the facts that the evidence supports (``must_use``), how
  many did the answer actually reference?
- **fabrication**: did the answer assert any of the things the evidence does *not*
  support (``must_avoid`` — a wrong gloss, an over-confident reading)?

Scoring is deliberately simple and transparent (case-insensitive substring
containment over the answer text) — a screen for gross failure, not a semantic
judge. Run it against any `LLMClient` (a real provider, or a deterministic stub
in tests); ``run_eval`` returns an aggregate `EvalReport`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from . import capabilities as _cap
from .client import LLMClient
from .grounding import GroundingItem

__all__ = [
    "GroundingCase",
    "CaseResult",
    "EvalReport",
    "score_text",
    "run_eval",
    "DEFAULT_CASES",
]


@dataclass(frozen=True, slots=True)
class GroundingCase:
    """One eval case: a prompt, the evidence to feed, and the facts a faithful
    answer should use / must not fabricate.

    ``kind`` picks the capability (``ask`` / ``decipher`` / ``gloss`` /
    ``summarize`` / ``translate``). ``must_use`` are strings a grounded answer
    should reference; ``must_avoid`` are strings that, if present, signal the
    model went beyond (or against) its evidence."""

    name: str
    prompt: str
    grounding: tuple[str | GroundingItem, ...] = ()
    must_use: tuple[str, ...] = ()
    must_avoid: tuple[str, ...] = ()
    kind: str = "ask"
    note: str = ""


@dataclass(frozen=True, slots=True)
class CaseResult:
    """The scored outcome of one case."""

    name: str
    used: tuple[str, ...]
    missing: tuple[str, ...]
    fabricated: tuple[str, ...]
    groundedness: float   # fraction of must_use referenced (1.0 if none required)
    clean: bool           # no must_avoid present
    text: str


@dataclass(frozen=True, slots=True)
class EvalReport:
    """Aggregate over a case set: mean groundedness and the fabrication rate
    (fraction of cases where any ``must_avoid`` appeared)."""

    cases: tuple[CaseResult, ...]
    groundedness: float
    fabrication_rate: float
    n: int = field(default=0)

    def summary(self) -> str:
        return (
            f"grounded-generation eval: {self.n} case(s) · "
            f"groundedness {self.groundedness:.2f} · "
            f"fabrication rate {self.fabrication_rate:.2f}"
        )


def score_text(text: str, case: GroundingCase) -> CaseResult:
    """Score one answer against a case (case-insensitive substring containment)."""
    low = text.lower()
    used = tuple(s for s in case.must_use if s.lower() in low)
    missing = tuple(s for s in case.must_use if s.lower() not in low)
    fabricated = tuple(s for s in case.must_avoid if s.lower() in low)
    grounded = 1.0 if not case.must_use else len(used) / len(case.must_use)
    return CaseResult(
        name=case.name,
        used=used,
        missing=missing,
        fabricated=fabricated,
        groundedness=grounded,
        clean=not fabricated,
        text=text,
    )


# How each case kind maps to a capability call (all return an ExploratoryResult).
def _invoke(case: GroundingCase, client: LLMClient) -> str:
    g = case.grounding
    if case.kind == "ask":
        return _cap.ask(case.prompt, grounding=g, client=client).text
    if case.kind == "decipher":
        return _cap.decipher_hypotheses(case.prompt, grounding=g, client=client).text
    if case.kind == "gloss":
        return _cap.gloss(case.prompt, grounding=g, client=client).text
    if case.kind == "summarize":
        return _cap.summarize(case.prompt, grounding=g, client=client).text
    if case.kind == "translate":
        return _cap.translate(case.prompt, grounding=g, client=client).text
    raise ValueError(f"unknown case kind {case.kind!r}")


def run_eval(cases: Sequence[GroundingCase], client: LLMClient) -> EvalReport:
    """Run each case through its capability with ``client`` and aggregate.

    Needs a working `LLMClient` (a provider with a key, or a stub). Returns an
    `EvalReport` with mean groundedness and the fabrication rate — the AI
    layer's analogue of the lemmatizer's held-out accuracy."""
    results = tuple(score_text(_invoke(c, client), c) for c in cases)
    n = len(results)
    groundedness = sum(r.groundedness for r in results) / n if n else 0.0
    fabrication_rate = sum(1 for r in results if r.fabricated) / n if n else 0.0
    return EvalReport(
        cases=results,
        groundedness=groundedness,
        fabrication_rate=fabrication_rate,
        n=n,
    )


# A small built-in set — illustrative, and a smoke test that a provider both uses
# its evidence and declines to go beyond it. Expand per project (the corpus,
# lexicon, and analysis layers all produce grounding these can draw on).
DEFAULT_CASES: tuple[GroundingCase, ...] = (
    GroundingCase(
        name="lsj-gloss-recall",
        prompt="What does the Greek word λόγος mean?",
        grounding=(
            GroundingItem("λόγος: computation, reckoning; account; word, speech",
                          source="lexicon:LSJ", ref="λόγος"),
        ),
        must_use=("reckoning",),
        must_avoid=("fish", "river"),
        kind="ask",
        note="should report the supplied gloss, not invent an unrelated meaning",
    ),
    GroundingCase(
        name="linear-a-total-context",
        prompt="KU-RO",
        grounding=(
            GroundingItem("KU-RO appears at the end of Haghia Triada accounts, before a numeral",
                          source="analysis:position", ref="KU-RO"),
            GroundingItem("the sum of the preceding entries equals the number after KU-RO",
                          source="analysis:balance", ref="KU-RO"),
        ),
        must_use=("total",),
        must_avoid=("deciphered", "certainly means"),
        kind="decipher",
        note="should hypothesise 'total' from the accounting evidence, stay tentative",
    ),
    GroundingCase(
        name="declines-without-evidence",
        prompt="What is the etymology of the Linear A word A-DU?",
        grounding=(),
        must_use=("insufficient",),
        must_avoid=("derives from", "cognate with", "Proto-Indo-European"),
        kind="ask",
        note="with no grounding it should say the evidence is insufficient, not invent an etymology",
    ),
)
