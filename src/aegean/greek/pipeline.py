"""One-call convenience pipeline: text in, per-token analysis records out.

`pipeline` composes the individually-callable stages (tokenize → sentence split →
POS-tag → lemmatize → optional parse) so a complete analysis doesn't require
chaining nine functions. The module-level function uses the backends selected by
the ``use_*`` compatibility facade. Explicit `GreekPipeline` instances instead own
their neural backend and configuration; an explicit baseline ignores facade-level
backend activation, so simultaneous instance results remain isolated.

With the neural pipeline active (``use_neural_pipeline()``, the ``[neural]``
extra), each sentence is analyzed in **one model pass** and every field of every
record is filled (UPOS, 9-char XPOS, UD FEATS, lemma, UD head/relation). Without
it, tagging/lemmatization use the active cascade, ``xpos``/``feats`` are ``None``,
and dependency fields are filled only when ``parse=True`` (which then requires
`use_parser` and yields AGDT/Prague relations over word tokens).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal, Sequence

from .lemmatize import (
    LemmaSource,
    lemma_resolved,
    lemma_verified,
    lemmatize_sourced,
    needs_review,
)
from .tokenize import _SENTENCE_SPLIT_RE
from .tokenize import tokenize_aligned as _tokenize_aligned

__all__ = ["TokenRecord", "pipeline", "pipeline_tokens"]

if TYPE_CHECKING:
    from ..core.model import SourceAlignment, Token, TokenFormState
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
    carries that genre caveat. ``alignment`` maps the record to the exact input
    token, including original and normalized text, source IDs, half-open Unicode
    code-point offsets, whitespace, and normalization operations."""

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
    alignment: SourceAlignment | None = field(default=None, compare=False)
    form_state: TokenFormState | None = field(default=None, compare=False)

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
    long_input: Literal["strict", "partial", "windowed"] = "strict",
    document_id: str = "input",
) -> list[TokenRecord]:
    """Analyze text through the module-level default `GreekPipeline` instance.

    This backward-compatible facade retains the historical signature and follows
    `use_neural_pipeline()` / `disable_neural_pipeline()`. For isolated concurrent
    configurations, construct `GreekPipeline` instances and call their `analyze` method.
    Neural long-input and calibrated-confidence behavior is identical on both APIs.
    ``document_id`` scopes deterministic source and sentence identities; use a stable
    value when records will be exported or reviewed.
    """
    from .runtime import default_pipeline

    return default_pipeline().analyze(
        text,
        parse=parse,
        with_confidence=with_confidence,
        long_input=long_input,
        document_id=document_id,
    )


def pipeline_tokens(
    tokens: Sequence[Token],
    *,
    parse: bool = False,
    with_confidence: bool = False,
    long_input: Literal["strict", "partial", "windowed"] = "strict",
    document_id: str = "input",
) -> list[TokenRecord]:
    """Analyze already-tokenized core ``Token`` values without re-tokenizing them.

    A token's typed ``form_state`` chooses the analyzer input in the deterministic
    order model input, regularized, normalized, diplomatic, then legacy ``Token.text``.
    The returned record retains the token's alignment and form state; one input token
    always produces one output record.
    """
    from .runtime import default_pipeline

    return default_pipeline().analyze_tokens(
        tokens,
        parse=parse,
        with_confidence=with_confidence,
        long_input=long_input,
        document_id=document_id,
    )


def _select_token_form(token: Token) -> tuple[str, TokenFormState | None]:
    """Select and validate one typed token's deterministic analyzer form."""
    state = token.form_state
    source: Literal["diplomatic", "regularized", "normalized", "explicit"] = "diplomatic"
    if state is None:
        if not isinstance(token.text, str):
            raise TypeError("selected token form must be a string")
        if not token.text:
            raise ValueError("selected token form must be non-empty")
        return token.text, None
    elif state.model_input is not None:
        selected = state.model_input
        if state.model_input_source is None:
            raise ValueError("token form state has model_input without a source")
        source = state.model_input_source
    elif state.regularized is not None:
        selected = state.regularized
        source = "regularized"
    elif state.normalized is not None:
        selected = state.normalized
        source = "normalized"
    else:
        # An empty diplomatic field can represent an unavailable original form in a
        # partial import; retain the compatibility/display token as the final fallback.
        selected = state.diplomatic or token.text
        source = "diplomatic" if state.diplomatic else "explicit"
    if not isinstance(selected, str):
        raise TypeError("selected token form must be a string")
    if not selected:
        raise ValueError("selected token form must be non-empty")
    return selected, replace(state, model_input=selected, model_input_source=source)


def _analyze_bound(
    text: str,
    *,
    parse: bool = False,
    with_confidence: bool = False,
    long_input: Literal["strict", "partial", "windowed"] = "strict",
    document_id: str = "input",
    typed_tokens: Sequence[Token] | None = None,
) -> list[TokenRecord]:
    """Analyze text under the `GreekPipeline` bound in the current context.

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
    ``long_input="windowed"`` explicitly opts long sentences into overlapping,
    whole-word neural windows. Token outputs come from their most central window and
    dependency arcs are reconciled once at sentence scope; successful multi-window
    output is complete and carries a window-policy warning and receipt flag.
    """
    if long_input not in ("strict", "partial", "windowed"):
        raise ValueError(
            "long_input must be 'strict', 'partial', or 'windowed', "
            f"got {long_input!r}"
        )
    from ..core.model import Token, TokenKind
    from . import joint, syntax

    if typed_tokens is not None:
        if isinstance(typed_tokens, (str, bytes)):
            raise TypeError("tokens must be a sequence of core Token values")
        typed_tokens = tuple(typed_tokens)
        if any(not isinstance(token, Token) for token in typed_tokens):
            raise TypeError("tokens must contain only core Token values")

    if long_input != "strict" and joint.active() is None:
        raise ValueError(
            f"long_input={long_input!r} requires an active neural Greek pipeline"
        )

    # One tokenization pass over the whole text; sentence boundaries fall after
    # any PUNCT token containing a sentence-final mark, so punctuation tokens
    # stay in their sentence rather than being discarded.
    sents: list[list[str]] = [[]]
    word_flags: list[list[bool]] = [[]]
    alignments: list[list[SourceAlignment | None]] = [[]]
    form_states: list[list[TokenFormState | None]] = [[]]
    if typed_tokens is None:
        source_tokens: Sequence[Token] = _tokenize_aligned(text, document_id=document_id)
        for tok in source_tokens:
            sents[-1].append(tok.text)
            word_flags[-1].append(tok.kind is TokenKind.WORD)
            alignments[-1].append(tok.alignment)
            form_states[-1].append(None)
            if tok.kind is TokenKind.PUNCT and _SENTENCE_SPLIT_RE.search(tok.text):
                sents.append([])
                word_flags.append([])
                alignments.append([])
                form_states.append([])
    else:
        for tok in typed_tokens:
            selected, state = _select_token_form(tok)
            sents[-1].append(selected)
            word_flags[-1].append(tok.kind is TokenKind.WORD)
            alignments[-1].append(tok.alignment)
            form_states[-1].append(state)
            if tok.kind is TokenKind.PUNCT and _SENTENCE_SPLIT_RE.search(selected):
                sents.append([])
                word_flags.append([])
                alignments.append([])
                form_states.append([])
    if sents and not sents[-1]:
        sents.pop()
        word_flags.pop()
        alignments.pop()
        form_states.pop()

    records: list[TokenRecord] = []
    for s_idx, (words, is_word, sentence_alignments, sentence_states) in enumerate(
        zip(sents, word_flags, alignments, form_states)
    ):
        if joint.active() is not None:
            ana = joint.analyze_sentence(
                words, with_probs=with_confidence, long_input=long_input
            )
            if len(ana.tokens) != len(words):
                raise ValueError(
                    "neural backend returned a different token count than the input "
                    f"({len(ana.tokens)} != {len(words)})"
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
                record_state = sentence_states[i]
                if record_state is not None:
                    actual_input = ana.tokens[i]
                    ops = record_state.model_input_ops
                    if actual_input != words[i] and "unicode:nfc" not in ops:
                        ops = (*ops, "unicode:nfc")
                    record_state = replace(
                        record_state,
                        model_input=actual_input,
                        model_input_ops=ops,
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
                        alignment=sentence_alignments[i],
                        form_state=record_state,
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
        if len(tags) != len(words):
            raise ValueError(
                "baseline backend returned a different token count than the input "
                f"({len(tags)} != {len(words)})"
            )
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
                    alignment=sentence_alignments[i],
                    form_state=sentence_states[i],
                )
            )
    return records
