"""Shared types, exceptions, and small decode helpers for the neural Greek pipeline."""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Literal

from . import neural_preprocessing as _prep
from .confidence import SentenceConfidence, TokenConfidence
from .lemmatize import LemmaSource
from .neural_contract import AnalysisReceipt

LongInputMode = Literal["strict", "partial", "windowed"]

_TOP_LEMMA_EDIT_STATE: ContextVar[
    tuple[int, list[tuple[tuple[tuple[str, float], ...], ...]]] | None
] = ContextVar("pyaegean_top_lemma_edit_state", default=None)


@contextmanager
def _capture_top_lemma_edits(
    k: int = 10,
) -> Iterator[list[tuple[tuple[tuple[str, float], ...], ...]]]:
    """Internal scoped capture for top-K neural lemma edit predictions.

    Active only when the weighted OOV lemma reranker requests top-K neural edit
    candidates; ordinary inference never sets this contextvar and incurs zero
    extra work.
    """
    captured: list[tuple[tuple[tuple[str, float], ...], ...]] = []
    token = _TOP_LEMMA_EDIT_STATE.set((k, captured))
    try:
        yield captured
    finally:
        _TOP_LEMMA_EDIT_STATE.reset(token)


def _extract_top_k_edits_for_word(
    form: str,
    logits_row: Any,
    trees: Sequence[Any],
    np: Any,
    k: int,
) -> tuple[tuple[str, float], ...]:
    """Return top-K ``(predicted_lemma, probability)`` edit-script candidates for one token."""
    if k <= 0 or not trees:
        return ()
    row = np.asarray(logits_row, dtype=np.float64)
    if row.ndim != 1 or row.size == 0 or not np.isfinite(row).all():
        return ()
    from .lemmatizer import apply_tree

    shifted = row - float(row.max())
    probs = np.exp(shifted)
    total = float(probs.sum())
    if total <= 0.0 or not math.isfinite(total):
        return ()
    probs = probs / total
    n_avail = min(len(trees), int(row.size))
    kk = min(k, n_avail)
    if kk < n_avail:
        top_idx = np.argpartition(probs[:n_avail], -kk)[-kk:]
        top_idx = top_idx[np.argsort(-probs[top_idx], kind="mergesort")]
    else:
        top_idx = np.argsort(-probs[:n_avail], kind="mergesort")
    probe = _prep._strip_editorial_apparatus(form)
    out: list[tuple[str, float]] = []
    for idx in top_idx:
        ti = int(idx)
        pred_l = apply_tree(trees[ti], probe)
        if pred_l and pred_l != "_":
            out.append((pred_l, float(probs[ti])))
    return tuple(out)


class NeuralPipelineNotLoadedError(RuntimeError):
    """Raised when the neural pipeline is used before `use_neural_pipeline`, or when
    the ``[neural]`` extra (onnxruntime/tokenizers/numpy) is not installed."""


class NeuralInputTooLongError(ValueError):
    """Raised when strict neural analysis cannot cover every input token."""

    def __init__(self, *, input_tokens: int, analyzed_tokens: int, max_subwords: int) -> None:
        self.input_tokens = input_tokens
        self.analyzed_tokens = analyzed_tokens
        self.max_subwords = max_subwords
        super().__init__(
            f"neural analysis would be incomplete: {analyzed_tokens} of {input_tokens} tokens "
            f"fit the model's {max_subwords}-subword limit. Split the sentence, or pass "
            "long_input='partial' and inspect SentenceAnalysis.complete/analyzed, or "
            "long_input='windowed' for safe complete-word overlap windows."
        )


class NeuralWindowingError(ValueError):
    """Raised when safe overlapping-window analysis cannot be supported.

    Windowed inference is deliberately conservative: pathological inputs are refused
    before tokenizer/dense allocation, and every window must contain complete words with
    a useful overlap and at least one observed arc for each dependent.
    """


@dataclass(frozen=True, slots=True)
class SentenceAnalysis:
    """The joint model's full analysis, coverage status, provenance, and receipt."""

    tokens: tuple[str, ...]
    upos: tuple[str, ...]
    xpos: tuple[str, ...]       # 9-char AGDT-convention positional tags
    feats: tuple[str, ...]      # UD FEATS rendered from xpos
    head: tuple[int, ...]       # 0 = root, else 1-based index into tokens
    deprel: tuple[str, ...]     # UD relations
    lemma: tuple[str, ...]
    # Per-token: True when the lemma came from a real analysis (lookup or edit-script),
    # False when it is the identity fall-through (the surface form returned unchanged).
    # Defaulted so the empty-sentence and any positional construction stay valid.
    lemma_resolved: tuple[bool, ...] = ()
    # Per-token CALIBRATED confidence, populated ONLY when a call sets ``with_probs=True``
    # AND a calibration is loaded (`aegean.greek.use_calibration`); otherwise empty ``()``,
    # so the default path is byte-identical to a build without this feature. Each value is
    # the temperature-scaled top-1 softmax probability of that head — an estimate of the
    # probability the prediction is correct (see `aegean.greek.calibrate`). ``None`` for a
    # token the model did not decode (a subword-budget truncation fallback). The project
    # never exposes a *raw* softmax: with ``with_probs=True`` and no calibration loaded,
    # `analyze` raises `UncalibratedConfidenceError` rather than filling these.
    upos_prob: tuple[float | None, ...] = ()
    lemma_script_prob: tuple[float | None, ...] = ()
    # Per-token offline-rescue evidence class, populated ONLY by Lever B
    # (`aegean.greek.documentary.rescue_analysis`) at the indices it rescues: the
    # `aegean.greek.LemmaSource` value (``"seed"`` / ``"paradigm"``) of the offline source
    # that recovered the lemma, ``""`` for a token it did not rescue. Empty ``()`` (the
    # default) means no rescue ran, so every path that does not opt into Lever B stays
    # byte-identical. A rescued token keeps ``lemma_resolved=False`` (an offline rescue is
    # never credited to the neural model); this channel lets a consumer surface the true
    # grounded source instead of the identity fall-through.
    lemma_source_override: tuple[str, ...] = ()
    # Exact decision provenance for each returned lemma. This separates a joint-model
    # frequency lookup from an edit-script prediction and from the identity fallback.
    # Empty only on legacy/custom SentenceAnalysis values that predate this field.
    lemma_source: tuple[LemmaSource, ...] = ()
    # Human verification is separate from model resolution or lexical attestation.
    lemma_verified: tuple[bool, ...] = ()
    lemma_source_path: tuple[str, ...] = ()
    token_confidences: tuple[TokenConfidence, ...] = ()
    sentence_confidence: SentenceConfidence | None = None
    # Per-token coverage plus sentence-level status. In strict mode an incomplete
    # sentence raises before a SentenceAnalysis is returned. Partial mode returns every
    # input token, marks undecoded tokens False here, and sets complete=False/truncated=True.
    analyzed: tuple[bool, ...] = ()
    complete: bool = True
    truncated: bool = False
    warnings: tuple[str, ...] = ()
    receipt: AnalysisReceipt | None = None

    @property
    def incomplete(self) -> bool:
        """Whether any input token lacks a neural analysis."""
        return not self.complete


def _best_non_root_relation(scores: "Any", labels: "Mapping[int, str] | Sequence[str]") -> int:
    """Index of the highest-scoring relation label that is not ``root``.

    UD allows exactly one ``root`` per sentence and it is the word whose HEAD is 0. The
    label head's argmax is unconstrained, so it could return ``root`` for a token
    attached to another word, producing a tree that is invalid CoNLL-U and a
    SentenceAnalysis contradicting itself (HEAD 3, DEPREL root). The head decision is
    made by the single-root MST decoder and is authoritative; the label is remapped to
    the best relation compatible with it."""
    order = list(scores.argsort()[::-1])
    for candidate in order:
        if labels[int(candidate)] != "root":
            return int(candidate)
    return int(order[0])  # a label set with nothing but root: keep the argmax


def _long_input_mode(value: str) -> LongInputMode:
    if value not in ("strict", "partial", "windowed"):
        raise ValueError(
            f"long_input must be 'strict', 'partial', or 'windowed', got {value!r}"
        )
    return value  # type: ignore[return-value]
