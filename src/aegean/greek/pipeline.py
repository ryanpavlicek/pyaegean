"""One-call convenience pipeline: text in, per-token analysis records out.

`pipeline` composes the individually-callable stages (tokenize → sentence split →
POS-tag → lemmatize → optional parse) so a complete analysis doesn't require
chaining nine functions. It uses whatever backends are **active**: activate them
first with the ``use_*`` functions (`use_treebank`, `use_tagger`, `use_lemmatizer`,
`use_neural_lemmatizer`, `use_parser`, `use_neural_pipeline`), and `pipeline`
picks the best of what's loaded per stage — exactly as the individual functions do.

With the neural pipeline active (``use_neural_pipeline()``, the ``[neural]``
extra), each sentence is analyzed in **one model pass** and every field of every
record is filled (UPOS, 9-char XPOS, UD FEATS, lemma, UD head/relation). Without
it, tagging/lemmatization use the active cascade, ``xpos``/``feats`` are ``None``,
and dependency fields are filled only when ``parse=True`` (which then requires
`use_parser` and yields AGDT/Prague relations over word tokens).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .lemmatize import (
    LemmaSource,
    lemma_resolved,
    lemma_verified,
    lemmatize_sourced,
    needs_review,
)
from .tokenize import _SENTENCE_SPLIT_RE
from .tokenize import tokenize as _tokenize

__all__ = ["TokenRecord", "pipeline"]

if TYPE_CHECKING:
    from .neural_contract import AnalysisReceipt


@dataclass(frozen=True, slots=True)
class TokenRecord:
    """One token's full analysis from `pipeline`.

    ``head`` refers to the ``index`` of another record **in the same sentence**
    (``0`` = sentence root, ``None`` = no parse). ``xpos``/``feats`` are filled
    only by the neural pipeline. ``lemma_source`` is the lemma's evidence class
    (see `LemmaSource`, one of ``attested`` / ``neural_lookup`` / ``neural_edit`` /
    ``neural`` / ``rule`` / ``seed`` / ``paradigm`` / ``identity`` / ``unresolved`` /
    ``punct`` / ``user``): whether it was
    attested in a treebank, predicted by the neural model, recovered by a rule,
    from the seed table, from a paradigm-table lookup (the opt-in UniMorph
    inflection tables, ``use_paradigms()``), an identity fall-through, unresolved,
    or punctuation. ``lemma_resolved``, ``lemma_verified``, and
    ``review_recommended`` keep resolution, human verification, and review triage
    separate. ``lemma_known`` is a deprecated compatibility alias for
    ``lemma_resolved``.

    ``upos_confidence`` / ``lemma_confidence`` are **calibrated** confidences
    (temperature-scaled on the UD Perseus dev fold; see
    `aegean.greek.calibrate`): the estimated probability the prediction is
    correct. They are ``None`` unless the neural pipeline is active, a calibration
    is loaded, AND the call set ``with_confidence=True`` — the project never
    surfaces a raw (uncalibrated) softmax. A calibrated number is model-only:
    lemmas resolved by an offline lexicon backend carry no model confidence (both
    fields stay ``None`` throughout the offline cascade, where the evidence class
    speaks). Within the neural pipeline the calibrated ``lemma_confidence`` covers
    the model's full lemma composition, including its internal training-form
    lookup, by design (the calibration target is composed-lemma correctness); it is
    ``None`` only for a token the model does not itself lemmatize (an identity
    fall-through or punctuation). The number is fitted on literary prose, so it
    carries that genre caveat."""

    sentence: int  # 0-based sentence number within the input text
    index: int  # 1-based token position within the sentence
    text: str
    upos: str
    lemma: str
    lemma_source: LemmaSource  # evidence class of the lemma
    head: int | None = None  # index of the head record; 0 = root
    relation: str | None = None  # UD (neural pipeline) or AGDT/Prague (use_parser)
    xpos: str | None = None  # 9-char positional tag (neural pipeline only)
    feats: str | None = None  # UD FEATS string (neural pipeline only)
    upos_confidence: float | None = None  # calibrated; None unless with_confidence + calibration
    lemma_confidence: float | None = None  # calibrated; model-only (see the class docstring)
    neural_analyzed: bool | None = None  # False only for an explicit partial-mode placeholder
    analysis_complete: bool = True  # sentence-level neural coverage status
    analysis_warning: str | None = None
    analysis_receipt: AnalysisReceipt | None = None

    @property
    def lemma_resolved(self) -> bool:
        """Whether the lemma is an actual decision rather than a surface fallback."""
        return lemma_resolved(self.lemma_source)

    @property
    def lemma_verified(self) -> bool:
        """Whether a human reviewer explicitly verified or corrected the lemma."""
        return lemma_verified(self.lemma_source)

    @property
    def review_recommended(self) -> bool:
        """Whether this lemma should be routed to human review."""
        return needs_review(self.lemma_source)

    @property
    def lemma_known(self) -> bool:
        """Deprecated alias for `lemma_resolved`; use the explicit epistemic fields."""
        warnings.warn(
            "TokenRecord.lemma_known is deprecated; use lemma_resolved, lemma_source, "
            "lemma_verified, and review_recommended",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.lemma_resolved


def pipeline(
    text: str,
    *,
    parse: bool = False,
    with_confidence: bool = False,
    long_input: Literal["strict", "partial"] = "strict",
) -> list[TokenRecord]:
    """Analyze ``text`` end-to-end and return one `TokenRecord` per token.

    Tokenizes (words **and** punctuation — nothing is dropped), splits into
    sentences on Greek sentence-final punctuation, POS-tags, lemmatizes, and —
    when ``parse=True`` or the neural pipeline is active — attaches dependency
    heads/relations. Backends are chosen by what is active (see the module
    docstring); the zero-dependency baseline needs no setup::

        from aegean import greek
        records = greek.pipeline("ἐν ἀρχῇ ἦν ὁ λόγος.")
        [(r.text, r.upos, r.lemma) for r in records]

    ``parse=True`` without the neural pipeline requires `use_parser` (raises
    `ParserNotLoadedError` otherwise) and parses **word** tokens only —
    punctuation records keep ``head=None``.

    ``with_confidence=True`` fills ``upos_confidence`` / ``lemma_confidence`` with
    **calibrated** confidences. This works only with the neural pipeline active
    (``use_neural_pipeline``) and requires a loaded calibration
    (``use_calibration``): with the pipeline active but no calibration it raises
    `UncalibratedConfidenceError` (a raw softmax is never exposed); on the offline
    cascade, where there is no model prediction to calibrate, the confidence fields
    simply stay ``None``. ``with_confidence=False`` (the default) leaves both ``None``.

    With the neural backend active, ``long_input="strict"`` (the default) raises
    `NeuralInputTooLongError` when a sentence exceeds the model bundle's subword limit.
    ``long_input="partial"`` retains every token but marks placeholders with
    ``neural_analyzed=False``, sets ``analysis_complete=False`` across that sentence,
    and includes ``analysis_warning`` and ``analysis_receipt``.
    """
    if long_input not in ("strict", "partial"):
        raise ValueError(f"long_input must be 'strict' or 'partial', got {long_input!r}")
    from ..core.model import TokenKind
    from . import joint, syntax

    # One tokenization pass over the whole text; sentence boundaries fall after
    # any PUNCT token containing a sentence-final mark, so punctuation tokens
    # stay in their sentence rather than being discarded.
    sents: list[list[str]] = [[]]
    word_flags: list[list[bool]] = [[]]
    for tok in _tokenize(text):
        sents[-1].append(tok.text)
        word_flags[-1].append(tok.kind is TokenKind.WORD)
        if tok.kind is TokenKind.PUNCT and _SENTENCE_SPLIT_RE.search(tok.text):
            sents.append([])
            word_flags.append([])
    if sents and not sents[-1]:
        sents.pop()
        word_flags.pop()

    records: list[TokenRecord] = []
    for s_idx, (words, is_word) in enumerate(zip(sents, word_flags)):
        if joint.active() is not None:
            ana = joint.analyze_sentence(
                words, with_probs=with_confidence, long_input=long_input
            )
            resolved = ana.lemma_resolved or (True,) * len(ana.tokens)
            override = ana.lemma_source_override  # Lever B offline-rescue sources, else ()
            for i in range(len(ana.tokens)):
                if not is_word[i]:
                    source = LemmaSource.PUNCT  # a punctuation/number token is its own lemma
                elif ana.lemma_source:
                    source = ana.lemma_source[i]
                elif resolved[i]:
                    source = LemmaSource.NEURAL
                elif override and override[i]:
                    # an opt-in Lever B offline rescue: a grounded SEED / PARADIGM lemma the
                    # model left unresolved, never NEURAL and never a review-bait identity
                    source = LemmaSource(override[i])
                else:
                    source = LemmaSource.IDENTITY  # the model returned the surface unchanged
                # A calibrated confidence is model-only: UPOS is always a neural prediction
                # here. The lemma confidence is surfaced whenever the model itself produced
                # the lemma (LemmaSource.NEURAL is the model's full composition, INCLUDING
                # its internal training-form lookup); an identity fall-through / punctuation
                # carry no calibrated number (the evidence class speaks for them).
                upos_conf = ana.upos_prob[i] if ana.upos_prob else None
                lemma_conf = (
                    ana.lemma_script_prob[i]
                    if ana.lemma_script_prob
                    and source
                    in (
                        LemmaSource.NEURAL,
                        LemmaSource.NEURAL_LOOKUP,
                        LemmaSource.NEURAL_EDIT,
                    )
                    else None
                )
                records.append(
                    TokenRecord(
                        sentence=s_idx, index=i + 1, text=ana.tokens[i],
                        upos=ana.upos[i], lemma=ana.lemma[i], lemma_source=source,
                        head=ana.head[i], relation=ana.deprel[i],
                        xpos=ana.xpos[i], feats=ana.feats[i],
                        upos_confidence=upos_conf, lemma_confidence=lemma_conf,
                        neural_analyzed=ana.analyzed[i] if ana.analyzed else True,
                        analysis_complete=ana.complete,
                        analysis_warning=ana.warnings[0] if ana.warnings else None,
                        analysis_receipt=ana.receipt,
                    )
                )
            continue

        from .pos import pos_tag, pos_tags

        # Joining the tokens with spaces re-tokenizes to exactly these tokens
        # (each was a maximal tokenizer match), so the tagger sees full context.
        sent_str = " ".join(words)
        tags = pos_tags(sent_str)
        if len(tags) != len(words):  # defensive: fall back to per-token tagging
            tags = [(w, pos_tag(w)) for w in words]
        heads: dict[int, tuple[int, str]] = {}  # token position → (head record index, rel)
        if parse:
            # the baseline parser works over word tokens only (same word regex
            # as the tokenizer), so its 1-based ids map onto the WORD records
            word_positions = [i for i, w in enumerate(is_word) if w]
            tree = syntax.parse(sent_str)  # raises ParserNotLoadedError if not loaded
            for k, dep in enumerate(tree.tokens):
                if k >= len(word_positions):
                    break  # defensive: tokenizer/parser disagreement
                rec_head = 0 if dep.head == 0 else word_positions[dep.head - 1] + 1
                heads[word_positions[k]] = (rec_head, dep.relation)
        for i, (tok_text, tag) in enumerate(tags):
            if is_word[i]:
                lemma, source = lemmatize_sourced(tok_text)
            else:
                lemma, source = tok_text, LemmaSource.PUNCT  # a punct/number token is its own lemma
            head, rel = heads.get(i, (None, None))
            records.append(
                TokenRecord(
                    sentence=s_idx, index=i + 1, text=tok_text,
                    upos=tag, lemma=lemma, lemma_source=source, head=head, relation=rel,
                )
            )
    return records
