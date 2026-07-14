"""The neural Greek pipeline — one model for tags, morphology, trees, and lemmas.

The opt-in ``[neural]`` backend's flagship: a jointly-trained GreBerta encoder with
token-classification heads (UPOS + the 9 AGDT postag positions), biaffine arc/relation
scorers decoded by a single-root MST (`aegean.greek.mst`), and an edit-script lemma head
composed with a train-only lookup. Trained leakage-clean on AGDT + Gorman + Pedalion
(1.41M tokens); measured on the UD Ancient Greek (Perseus) test fold at UPOS 97.0,
UFeats 96.0, lemma 94.3, XPOS 93.5, UAS 90.2, and LAS 85.6. See
``docs/benchmarks.md`` for the protocol, seeds, comparisons, and bootstrap CIs;
shipped-artifact numbers are re-measured through this module and recorded there).

Inference is **torch-free** (onnxruntime + tokenizers + numpy — the ``[neural]`` extra),
imported only on activation, so ``import aegean`` stays instant. The model bundle (ONNX +
tokenizer + label maps + lemma scripts/lookup) is fetched-to-cache on first use, never
bundled; it derives from CC BY-SA treebanks, so the *model* ships under CC BY-SA while
the wheel stays Apache-2.0.

Once `use_neural_pipeline` is active, the standard functions consult it:
`aegean.greek.pos_tags` / `pos_tag`, `aegean.greek.parse` (which then returns **UD**
relations rather than the arc-eager baseline's Prague labels), and
`aegean.greek.lemmatize`. Sentence-level calls run the encoder once for everything;
`analyze_sentence` exposes the full joint analysis directly.
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, cast

from ..data import fetch, versions
from . import _ort
from .lemmatize import LemmaSource, lemma_verified
from .mst import decode_mst
from . import neural_preprocessing as _prep
from .neural_contract import (
    AnalysisReceipt,
    ModelBundleError,
    ModelBundleManifest,
    ReceiptMismatchError,
)
from .udfeats import feats_from_xpos
from .confidence import (
    AbstentionPolicy,
    CalibrationEntry,
    CalibrationRegistry,
    ConfidenceResult,
    SentenceConfidence,
    TokenConfidence,
    UNAVAILABLE_CONFIDENCE,
    UNAVAILABLE_MISSING_CALIBRATION,
)

__all__ = [
    "AnalysisReceipt",
    "ModelBundleError",
    "ModelBundleManifest",
    "NeuralPipelineNotLoadedError",
    "NeuralInputTooLongError",
    "NeuralWindowingError",
    "ReceiptMismatchError",
    "SentenceAnalysis",
    "TokenConfidence",
    "SentenceConfidence",
    "active",
    "analyze_sentence",
    "analyze_sentences",
    "iter_analyze_sentences",
    "disable_neural_pipeline",
    "neural_backend_info",
    "use_neural_pipeline",
]

# Registered in aegean.data._REMOTE; fetched + extracted to the cache on first use.
_DATASET = "grc-joint"
LongInputMode = Literal["strict", "partial", "windowed"]
_STREAM_CONFIDENCE_UNSET = object()
_STREAM_CONFIDENCE_CONTEXT: ContextVar[Any] = ContextVar(
    "pyaegean_stream_confidence_context", default=_STREAM_CONFIDENCE_UNSET
)


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


def _compose_lemma_detail(
    form: str, upos: str, script_id: int, model: "_JointModel"
) -> tuple[str, bool, LemmaSource, str]:
    """The dev-preferred ``lookup-first`` composition, with an honesty flag: returns
    ``(lemma, resolved, source)``. ``resolved`` is True when a real analysis was found: a
    (form|UPOS) or form lookup, a predicted non-identity edit script, or a lowercase
    lookup — and False for the identity fall-through (the form itself). A lemma that
    equals the surface form is still ``resolved=True`` when it came from a lookup (a
    nominative singular is a genuine analysis), so callers must not infer the source
    from a string compare."""
    from .lemmatizer import apply_tree

    value, resolved, path = _prep.compose_lemma_detail(
        form,
        upos,
        script_id,
        lookup_form_upos=model.lookup_form_upos,
        lookup_form=model.lookup_form,
        lookup_lower=model.lookup_lower,
        trees=model.trees,
        apply_edit_script=apply_tree,
    )
    source = {
        "edit_script": LemmaSource.NEURAL_EDIT,
        "identity_fallback": LemmaSource.IDENTITY,
    }.get(path, LemmaSource.NEURAL_LOOKUP)
    return value, resolved, source, path


def _compose_lemma(
    form: str, upos: str, script_id: int, model: "_JointModel"
) -> tuple[str, bool, LemmaSource]:
    """Backward-compatible lemma composition tuple without internal branch metadata."""

    lemma, resolved, source, _path = _compose_lemma_detail(form, upos, script_id, model)
    return lemma, resolved, source


def _confidence_context(
    with_probs: bool,
    *,
    domain: str | None = None,
    policy: AbstentionPolicy | None = None,
) -> dict[str, Any] | None:
    """Resolve confidence inputs without changing the no-confidence path."""
    if (domain is not None or policy is not None) and not with_probs:
        raise ValueError("confidence domain/policy requires with_probs=True")
    if not with_probs:
        return None
    captured = _STREAM_CONFIDENCE_CONTEXT.get()
    if captured is not _STREAM_CONFIDENCE_UNSET:
        if not isinstance(captured, dict):  # pragma: no cover - private invariant
            raise RuntimeError("invalid captured stream confidence context")
        if captured.get("domain") != domain or captured.get("policy") != policy:
            raise RuntimeError("captured stream confidence scope changed during analysis")
        return cast(dict[str, Any], captured)
    from . import calibrate

    legacy, registry = calibrate._active_state()
    if legacy is None and registry is None:
        raise calibrate.UncalibratedConfidenceError(
            "uncalibrated confidence is not exposed; load or fit a calibration first "
            "(aegean.greek.use_calibration())."
        )
    return {"legacy": legacy, "registry": registry, "domain": domain, "policy": policy}


@contextmanager
def _bind_stream_confidence_context(
    context: dict[str, Any] | None,
) -> Iterator[None]:
    """Bind one captured calibration only for a synchronous backend call."""

    if context is None:
        yield
        return
    token = _STREAM_CONFIDENCE_CONTEXT.set(context)
    try:
        yield
    finally:
        _STREAM_CONFIDENCE_CONTEXT.reset(token)


def _model_id(model: Any) -> str:
    manifest = getattr(model, "manifest", None)
    value = getattr(manifest, "model_id", None)
    return value if isinstance(value, str) and value.strip() else "legacy"


def _resolve_confidence_entry(
    model: Any,
    context: dict[str, Any] | None,
    task: str,
    source: str | None = "neural",
) -> tuple[CalibrationEntry | None, str | None, Any | None]:
    if context is None:
        return None, UNAVAILABLE_CONFIDENCE, None
    registry = context.get("registry")
    if not isinstance(registry, CalibrationRegistry):
        return None, UNAVAILABLE_MISSING_CALIBRATION, None
    resolved = registry.resolve(
        _model_id(model), task, source, context.get("domain")
    )
    if resolved.entry is None:
        return None, resolved.reason or UNAVAILABLE_MISSING_CALIBRATION, resolved
    return resolved.entry, None, resolved


def _confidence_result(
    model: Any,
    context: dict[str, Any] | None,
    task: str,
    value: float | None,
    *,
    entry: CalibrationEntry | None = None,
    reason: str | None = None,
    source: str | None = "neural",
    resolution: Any | None = None,
) -> ConfidenceResult:
    if value is None or entry is None:
        return ConfidenceResult(
            task=task,
            value=None,
            reason=reason or UNAVAILABLE_CONFIDENCE,
            model=_model_id(model) if context is not None else None,
            source=source,
            domain=(context or {}).get("domain"),
            scope=resolution.scope if resolution is not None else None,
        )
    if entry.n is None or entry.n <= 0 or (entry.ece is None and entry.brier is None):
        return ConfidenceResult(
            task=task,
            value=None,
            reason="insufficient_calibration_evidence",
            calibration_id=entry.calibration_id,
            scope=resolution.scope if resolution is not None else None,
            model=_model_id(model),
            source=source,
            domain=(context or {}).get("domain"),
            n=entry.n,
            ece=entry.ece,
            brier=entry.brier,
        )
    return ConfidenceResult(
        task=task,
        value=value,
        calibration_id=entry.calibration_id,
        scope=(resolution.scope if resolution is not None else (
            "global_fallback" if entry.fallback and entry.source is None and entry.domain is None else
            "source_fallback" if entry.fallback and entry.source is None else
            "domain_fallback" if entry.fallback else "exact"
        )),
        model=_model_id(model),
        source=source,
        domain=(context or {}).get("domain"),
        n=entry.n,
        ece=entry.ece,
        brier=entry.brier,
    )


def _policy_decision(
    policy: AbstentionPolicy | None, result: ConfidenceResult | None
) -> Any:
    return None if policy is None or result is None else policy.decide(result.task, result.value)


def _entry_probability(
    entry: CalibrationEntry | None,
    logits: Any = None,
    raw_probability: float | None = None,
    *,
    np: Any,
    selected_index: int | None = None,
) -> float | None:
    if entry is None:
        return None
    from . import calibrate

    if entry.calibrator == "temperature":
        if logits is None or entry.temperature is None:
            return None
        if selected_index is None:
            return float(calibrate.top1_confidence(logits, entry.temperature, np=np))
        probabilities = calibrate.temperature_softmax(logits, entry.temperature, np=np)
        return float(probabilities[selected_index])
    if raw_probability is None:
        return None
    return float(entry.calibrate(raw_probability))


def _sentence_confidence(
    model: Any,
    context: dict[str, Any] | None,
    raw_components: list[dict[str, float]],
) -> SentenceConfidence | None:
    if context is None:
        return None
    required = ("upos", "xpos", "lemma", "head", "relation")
    if not raw_components:
        result = _confidence_result(model, context, "sentence", None, reason="empty_sentence")
        return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))
    values: list[float] = []
    for item in raw_components:
        if not item or any(name not in item for name in ("upos", "xpos", "lemma", "head")):
            result = _confidence_result(model, context, "sentence", None, reason="partial_token")
            return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))
        values.extend(item[name] for name in ("upos", "xpos", "lemma", "head"))
        if "relation" not in item and item.get("forced_root"):
            continue
        if "relation" not in item:
            result = _confidence_result(model, context, "sentence", None, reason="missing_relation")
            return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))
        values.append(item["relation"])
    entry, reason, resolution = _resolve_confidence_entry(model, context, "sentence")
    if entry is None:
        result = _confidence_result(
            model, context, "sentence", None, reason=reason or UNAVAILABLE_MISSING_CALIBRATION
        )
        return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))
    if entry.calibrator != "logit_affine":
        result = _confidence_result(model, context, "sentence", None, reason="unsupported_calibrator")
        return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))
    if any(value < 0.0 or value > 1.0 or not math.isfinite(value) for value in values):
        result = _confidence_result(model, context, "sentence", None, reason="invalid_raw_aggregate")
        return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))
    raw = (
        0.0
        if any(value == 0.0 for value in values)
        else math.exp(math.fsum(math.log(value) for value in values))
    )
    value = float(entry.calibrate(raw))
    result = _confidence_result(model, context, "sentence", value, entry=entry, resolution=resolution)
    return SentenceConfidence(result, required, _policy_decision(context.get("policy"), result))


def _unavailable_sentence_confidence(
    model: Any, context: dict[str, Any], reason: str
) -> SentenceConfidence:
    """Build an explicit sentence-level unavailable record for structural failures."""

    result = _confidence_result(model, context, "sentence", None, reason=reason)
    return SentenceConfidence(
        result,
        ("upos", "xpos", "lemma", "head", "relation"),
        _policy_decision(context.get("policy"), result),
    )


def _long_input_mode(value: str) -> LongInputMode:
    if value not in ("strict", "partial", "windowed"):
        raise ValueError(
            f"long_input must be 'strict', 'partial', or 'windowed', got {value!r}"
        )
    return value  # type: ignore[return-value]


class _JointModel:
    """A loaded joint ONNX model + tokenizer + label maps + lemma scripts/lookup."""

    def __init__(
        self,
        model_dir: Path,
        *,
        asset_sha256: str | None = None,
        asset_sha256_enforced: bool = False,
    ) -> None:
        try:
            import numpy as np
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ModuleNotFoundError as e:  # pragma: no cover - import guard
            raise NeuralPipelineNotLoadedError(
                "the neural pipeline needs the optional dependencies: "
                "pip install 'pyaegean[neural]'"
            ) from e
        self._np = np
        if not (model_dir / "model.onnx").exists():
            # tolerate an archive packed with a single top-level directory
            nested = [d for d in model_dir.iterdir() if d.is_dir()]
            if len(nested) == 1 and (nested[0] / "model.onnx").exists():
                model_dir = nested[0]
        # The manifest and every listed member are validated before ONNX Runtime parses
        # model bytes. A corrupt or incompatible bundle therefore fails at activation,
        # never after producing a partially configured analysis.
        self.manifest = ModelBundleManifest.load(
            model_dir,
            asset_sha256=asset_sha256,
            asset_sha256_enforced=asset_sha256_enforced,
        )
        try:
            _prep.validate_manifest_contract(self.manifest)
        except ValueError as exc:
            raise ModelBundleError(str(exc)) from exc
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        # Provider policy lives in one place (_ort.resolve_providers): the published
        # numbers are measured on CPU; a GPU provider is a throughput convenience.
        # (Resolve providers before the session so a bad PYAEGEAN_ORT_PROVIDERS value
        # surfaces its own ValueError, not the "model corrupt" message below.)
        providers = _ort.resolve_providers()
        model_path = model_dir / "model.onnx"
        try:
            self._sess = ort.InferenceSession(str(model_path), opts, providers=providers)
        except Exception as e:
            # A corrupt/truncated model.onnx (an interrupted extract, disk corruption, or a
            # legacy pre-0.29 extract cache that fetch() trusts without re-hashing) makes
            # onnxruntime raise a bare protobuf/parse error naming nothing actionable — and
            # it is the largest file in the bundle, so the likeliest to be truncated. Say
            # what it is and how to re-fetch, mirroring the tokenizer.json wrapper below.
            raise NeuralPipelineNotLoadedError(
                f"could not load the joint model at {model_path} (onnxruntime: {e}) — "
                f"the cached model looks corrupt or incompletely downloaded. Re-fetch it: "
                f"run `aegean data remove {_DATASET}` and retry, or call "
                f"use_neural_pipeline(force=True)."
            ) from e
        actual_outputs = tuple(output.name for output in self._sess.get_outputs())
        if set(actual_outputs) != set(self.manifest.output_heads):
            raise ModelBundleError(
                "model.onnx output heads disagree with the bundle manifest: "
                f"expected {list(self.manifest.output_heads)!r}, got {list(actual_outputs)!r}"
            )
        try:
            self._tok = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        except Exception as e:
            # an old tokenizers release fails on the shipped tokenizer.json format with a
            # bare Rust serde error that names nothing actionable; say what fixes it.
            raise NeuralPipelineNotLoadedError(
                "could not load the model's tokenizer.json — usually an outdated "
                "tokenizers package: pip install 'tokenizers>=0.20'"
            ) from e
        spec = json.loads((model_dir / "labels.json").read_text(encoding="utf-8"))
        maps: dict[str, dict[str, int]] = spec["maps"]
        self.inv = {h: {i: lab for lab, i in m.items()} for h, m in maps.items()}
        scripts: list[str] = json.loads(
            (model_dir / "lemma-scripts.json").read_text(encoding="utf-8")
        )
        self.trees = [json.loads(k) for k in scripts]
        lookup = json.loads((model_dir / "lemma-lookup.json").read_text(encoding="utf-8"))
        self.lookup_form: dict[str, str] = lookup["form"]
        self.lookup_form_upos: dict[str, str] = lookup["form_upos"]
        self.lookup_lower: dict[str, str] = lookup["form_lower"]

    def _encode(self, words: list[str]) -> tuple[list[int], list[int], list[int]]:
        """Tokenize one pre-tokenized sentence → ``(subword ids, first-subword position
        per kept word, kept word indices)``. The tokenizer manifest owns the subword
        maximum. At most ``max_subwords`` input words are presented to the tokenizer,
        which bounds pathological partial-mode input without changing any coverable
        prefix (each non-empty pretokenized word needs at least one subword). If right
        truncation cuts through the final word, that incomplete word is removed from the
        kept set; strict mode must refuse it and partial mode must never label a fragment
        as a complete token prediction."""
        alignment = _prep.align_pretokenized(
            self._tok, words, self.manifest.max_subwords
        )
        return (
            list(alignment.input_ids),
            list(alignment.first_subword_positions),
            list(alignment.kept_indices),
        )

    def _run(self, words: list[str]) -> dict[str, Any]:
        """One encoder pass over a pre-tokenized sentence → raw arrays + word bookkeeping."""
        np = self._np
        ids, word_pos, kept = self._encode(words)
        feed = {
            "input_ids": np.array([ids], dtype=np.int64),
            "attention_mask": np.ones((1, len(ids)), dtype=np.int64),
            "word_pos": np.array([word_pos or [0]], dtype=np.int64),
        }
        names = [o.name for o in self._sess.get_outputs()]
        outs = dict(zip(names, self._sess.run(None, feed)))
        outs["_word_pos"] = word_pos
        outs["_kept"] = kept
        return outs

    def _run_batch(self, batch: list[list[str]]) -> list[dict[str, Any]]:
        """One padded encoder pass over several non-empty sentences → per-sentence
        output dicts shaped exactly like `_run`'s.

        Rows are padded to the batch's max subword/word lengths with attention-mask
        zeros; the biaffine and per-token heads score each position independently, so
        pad rows never influence a real token, and `_decode` reads only the real
        ``:nw`` slice of every array. Padding changes float reduction order in the
        batched matmuls, so batched logits can differ from the single pass at machine
        precision — batching is a throughput convenience, never the recorded protocol."""
        np = self._np
        encoded = [self._encode(words) for words in batch]
        max_len = max(len(ids) for ids, _, _ in encoded)
        max_words = max(max((len(wp) for _, wp, _ in encoded), default=0), 1)
        n = len(batch)
        input_ids = np.zeros((n, max_len), dtype=np.int64)
        attention_mask = np.zeros((n, max_len), dtype=np.int64)
        word_pos = np.zeros((n, max_words), dtype=np.int64)
        for b, (ids, wp, _kept) in enumerate(encoded):
            input_ids[b, : len(ids)] = ids
            attention_mask[b, : len(ids)] = 1
            row = wp or [0]  # mirror _run's empty-word_pos feed fallback
            word_pos[b, : len(row)] = row
        feed = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "word_pos": word_pos,
        }
        names = [o.name for o in self._sess.get_outputs()]
        outs = dict(zip(names, self._sess.run(None, feed)))
        results: list[dict[str, Any]] = []
        for b, (_ids, wp, kept) in enumerate(encoded):
            one: dict[str, Any] = {name: arr[b : b + 1] for name, arr in outs.items()}
            one["_word_pos"] = wp
            one["_kept"] = kept
            results.append(one)
        return results

    @property
    def max_subwords(self) -> int:
        """The manifest-declared subword limit."""
        manifest = getattr(self, "manifest", None)
        return manifest.max_subwords if manifest is not None else 256

    def _receipt(
        self,
        *,
        input_tokens: int,
        analyzed_tokens: int,
        truncated: bool,
        windowed: bool = False,
        context: dict[str, Any] | None = None,
    ) -> AnalysisReceipt | None:
        manifest = getattr(self, "manifest", None)
        session = getattr(self, "_sess", None)
        if manifest is None or session is None or not hasattr(session, "get_providers"):
            return None
        return AnalysisReceipt.create(
            manifest,
            execution_providers=tuple(session.get_providers()),
            input_tokens=input_tokens,
            analyzed_tokens=analyzed_tokens,
            truncated=truncated,
            windowed=windowed,
            calibration_sha256=(
                context["registry"].sha256
                if context is not None and isinstance(context.get("registry"), CalibrationRegistry)
                else None
            ),
            confidence_policy_sha256=(
                context["policy"].sha256
                if context is not None and context.get("policy") is not None
                else None
            ),
        )

    def _window_body_budget(self) -> int:
        """Return the manifest subword budget available to complete input words."""
        manifest = getattr(self, "manifest", None)
        policy = getattr(manifest, "special_token_policy", None)
        if manifest is not None and policy != _prep.SPECIAL_TOKEN_POLICY:
            raise NeuralWindowingError(
                "windowed neural analysis requires the validated two-token policy "
                f"{_prep.SPECIAL_TOKEN_POLICY}"
            )
        budget = self.max_subwords - 2  # <s> and </s> are validated by the manifest.
        if budget < 1:
            raise NeuralWindowingError(
                f"model subword limit {self.max_subwords} cannot hold two special tokens "
                "and a complete input word"
            )
        return budget

    def _full_word_lengths(self, words: list[str]) -> list[int]:
        """Measure every word with an untruncated clone of the active tokenizer."""
        tok = getattr(self, "_tok", None)
        if tok is None:
            raise NeuralWindowingError("windowed neural analysis has no tokenizer")
        clone: Any = None
        # Tokenizer.from_str is the tokenizers API's independent clone operation.  The
        # fallbacks keep the test/fake backend contract small without mutating the live
        # tokenizer, whose truncation policy is still used by ordinary inference.
        try:
            from tokenizers import Tokenizer

            if hasattr(tok, "to_str"):
                clone = Tokenizer.from_str(tok.to_str())
        except Exception:
            clone = None
        if clone is None and hasattr(tok, "clone"):
            try:
                clone = tok.clone()
            except Exception:
                clone = None
        if clone is None:
            import copy

            try:
                clone = copy.deepcopy(tok)
            except Exception as exc:  # pragma: no cover - defensive fake/runtime guard
                raise NeuralWindowingError(
                    "could not clone the tokenizer for untruncated window measurement"
                ) from exc
        try:
            no_truncation = getattr(clone, "no_truncation")
            no_truncation()
        except (AttributeError, TypeError) as exc:
            raise NeuralWindowingError(
                "tokenizer cannot disable truncation for whole-word window measurement"
            ) from exc
        try:
            enc = clone.encode(words, is_pretokenized=True)
        except TypeError:
            # Small deterministic fakes often omit the keyword while preserving the
            # same pretokenized semantics.
            enc = clone.encode(words)
        word_ids = getattr(enc, "word_ids", None)
        if callable(word_ids):
            word_ids = word_ids()
        if word_ids is None:
            raise NeuralWindowingError("tokenizer did not expose complete word positions")
        lengths = [0] * len(words)
        for wid in word_ids:
            if wid is None:
                continue
            if not isinstance(wid, int) or wid < 0 or wid >= len(words):
                raise NeuralWindowingError("tokenizer returned an invalid whole-word position")
            lengths[wid] += 1
        if any(length < 1 for length in lengths):
            raise NeuralWindowingError(
                "windowed neural analysis cannot preserve a complete word boundary: "
                "the untruncated tokenizer produced no subwords for an input token"
            )
        return lengths

    @staticmethod
    def _pack_windows(lengths: list[int], budget: int) -> list[tuple[int, int]]:
        """Pack complete-word windows with a subword-bounded suffix overlap."""
        if any(length > budget for length in lengths):
            raise NeuralWindowingError(
                "windowed neural analysis refused an individual token whose complete "
                f"subword span exceeds the {budget}-subword body budget"
            )
        target = min(64, budget // 4)
        windows: list[tuple[int, int]] = []
        start = 0
        n = len(lengths)
        while start < n:
            used = 0
            end = start
            while end < n and used + lengths[end] <= budget:
                used += lengths[end]
                end += 1
            if end == start:  # guarded above, retained as a clean boundary error
                raise NeuralWindowingError(
                    "windowed neural analysis cannot place a complete token in a model window"
                )
            windows.append((start, end))
            if end == n:
                break

            # Prefer the largest complete suffix not exceeding the target body-subword
            # overlap.  If a single token is wider than that target, retain that one whole
            # token anyway: every boundary must overlap at least one token.
            overlap_start = end - 1
            overlap_used = lengths[overlap_start]
            while overlap_start > start:
                candidate = overlap_used + lengths[overlap_start - 1]
                if candidate > target:
                    break
                overlap_start -= 1
                overlap_used = candidate
            if overlap_start <= start or overlap_start >= end:
                raise NeuralWindowingError(
                    "windowed neural analysis cannot provide a whole-token overlap with "
                    "forward progress at a window boundary"
                )
            start = overlap_start
        return windows

    def _analyze_windowed(
        self,
        forms: list[str],
        lengths: list[int],
        windows: list[tuple[int, int]],
        *,
        calibration: Any = None,
        context: dict[str, Any] | None = None,
    ) -> SentenceAnalysis:
        """Analyze windows and reconcile owner fields plus one global dependency tree."""
        np = self._np
        # Assign owners before any window encoder pass.  This lets us process each window
        # sequentially and drop its logits immediately, keeping the 4,096-token dense cap
        # honest even for many windows.
        n = len(forms)
        owners: list[int | None] = [None] * n
        owner_scores = [-1] * n
        prefix = [0]
        for length in lengths:
            prefix.append(prefix[-1] + length)
        for wi, (ws, we) in enumerate(windows):
            for token in range(ws, we):
                score = min(prefix[token] - prefix[ws], prefix[we] - prefix[token + 1])
                # Windows were built left-to-right, so retaining an equal score gives the
                # required deterministic earlier-window tie break.
                if score > owner_scores[token]:
                    owner_scores[token] = score
                    owners[token] = wi
        if any(owner is None for owner in owners):  # pragma: no cover - packer invariant
            raise NeuralWindowingError("windowed analysis could not assign every token an owner")

        upos = ["X"] * n
        xpos = ["---------"] * n
        lemma = list(forms)
        resolved = [False] * n
        lemma_source = [LemmaSource.IDENTITY] * n
        lemma_source_path = ["identity_fallback"] * n
        verified = [False] * n
        upos_prob: list[float | None] = [None] * n
        lemma_prob: list[float | None] = [None] * n
        token_confidences: list[TokenConfidence | None] = [None] * n
        raw_components: list[dict[str, float]] = [{} for _ in range(n)]
        arc = np.full((n, n + 1), -np.inf, dtype=np.float32)
        # Relation IDs are bounded by the validated manifest label map.  A compact int16
        # candidate grid avoids an R x N² float tensor; -1 means no finite relation score.
        relation_count = len(self.inv["deprel"])
        if relation_count > int(np.iinfo(np.int16).max):
            raise NeuralWindowingError(
                "windowed neural analysis cannot compact a relation map larger than int16"
            )
        rel_ids = np.full((n, n + 1), -1, dtype=np.int16)
        window_relation_entry, window_relation_reason, window_relation_resolution = (
            _resolve_confidence_entry(self, context, "relation")
            if context is not None
            else (None, None, None)
        )
        window_relation_temperature: float | None = None
        if (
            window_relation_entry is not None
            and window_relation_entry.calibrator == "temperature"
            and window_relation_entry.temperature is not None
        ):
            window_relation_temperature = window_relation_entry.temperature
        rel_raw_probs = (
            np.full((n, n + 1), np.nan, dtype=np.float32)
            if context is not None
            else None
        )
        rel_cal_probs = (
            np.full((n, n + 1), np.nan, dtype=np.float32)
            if context is not None
            and window_relation_temperature is not None
            else None
        )

        for wi, (ws, we) in enumerate(windows):
            chunk = forms[ws:we]
            raw = self._run(chunk)
            if raw.get("_kept") != list(range(we - ws)):
                raise NeuralWindowingError(
                    "windowed tokenizer failed to return every complete word in a window"
                )
            local = self._decode(chunk, raw, calibration=calibration, context=context)
            if local.analyzed != (True,) * len(chunk):
                raise NeuralWindowingError(
                    "windowed neural analysis produced an incomplete window decode"
                )
            local_arc = np.asarray(raw["arc"][0], dtype=np.float32)
            local_rel = np.asarray(raw["rel"][0])
            for local_i, token in enumerate(range(ws, we)):
                if owners[token] != wi:
                    continue
                upos[token] = local.upos[local_i]
                xpos[token] = local.xpos[local_i]
                lemma[token] = local.lemma[local_i]
                resolved[token] = local.lemma_resolved[local_i]
                lemma_source[token] = local.lemma_source[local_i]
                if local.lemma_source_path:
                    lemma_source_path[token] = local.lemma_source_path[local_i]
                verified[token] = local.lemma_verified[local_i]
                if local.upos_prob:
                    upos_prob[token] = local.upos_prob[local_i]
                if local.lemma_script_prob:
                    lemma_prob[token] = local.lemma_script_prob[local_i]
                if context is not None:
                    from . import calibrate

                    local_sp = raw["_word_pos"][local_i]
                    # Window outputs retain the same local word ordering; raw task values
                    # are stored as one scalar per owned token until global MST selection.
                    raw_upos = float(
                        calibrate.top1_confidence(
                            raw["upos"][0, local_sp], 1.0, np=np
                        )
                    )
                    raw_x = [
                        float(
                            calibrate.top1_confidence(
                                raw[f"x{x_index}"][0, local_sp], 1.0, np=np
                            )
                        )
                        for x_index in range(9)
                    ]
                    raw_components[token].update(
                        {
                            "upos": raw_upos,
                            "xpos": float(np.prod(raw_x, dtype=np.float64)),
                            "lemma": float(
                                calibrate.top1_confidence(raw["lemma"][0, local_i], 1.0, np=np)
                            ),
                        }
                    )
                    token_confidences[token] = replace(
                        local.token_confidences[local_i], index=token
                    )
                for local_head, score in enumerate(local_arc[local_i]):
                    global_head = 0 if local_head == 0 else ws + local_head
                    if global_head < 0 or global_head > n:
                        continue
                    arc[token, global_head] = score
                    rel_vector = np.asarray(local_rel[:, local_i, local_head])
                    if np.isfinite(rel_vector).any():
                        rel_ids[token, global_head] = np.int16(rel_vector.argmax())
                        if context is not None and rel_raw_probs is not None:
                            safe_rel = np.where(np.isfinite(rel_vector), rel_vector, -1.0e30)
                            rel_raw_probs[token, global_head] = float(
                                calibrate.top1_confidence(safe_rel, 1.0, np=np)
                            )
                            if rel_cal_probs is not None and window_relation_temperature is not None:
                                rel_cal_probs[token, global_head] = float(
                                    calibrate.top1_confidence(
                                        safe_rel, window_relation_temperature, np=np
                                    )
                                )
            # Explicitly release the large per-window arrays before the next encoder pass.
            del raw, local, local_arc, local_rel

        if not np.isfinite(arc).any(axis=1).all():
            raise NeuralWindowingError(
                "windowed neural analysis did not observe at least one finite arc for "
                "every dependent"
            )
        try:
            heads = decode_mst(arc)
        except Exception as exc:  # pragma: no cover - defensive decoder guard
            raise NeuralWindowingError("global windowed dependency decoding failed") from exc
        if len(heads) != n or heads.count(0) != 1:
            raise NeuralWindowingError(
                "global windowed dependency decoding did not produce exactly one root"
            )
        for dep, head_value in enumerate(heads):
            if head_value < 0 or head_value > n or head_value == dep + 1:
                raise NeuralWindowingError("global windowed decoder selected an invalid arc")
            if not np.isfinite(arc[dep, head_value]):
                raise NeuralWindowingError(
                    "global windowed decoder selected an unobserved or non-finite arc"
                )
        # The MST decoder promises an arborescence; retain a cheap explicit cycle check as
        # a safety assertion because malformed all--inf candidate matrices must never leak.
        for start in range(n):
            seen: set[int] = set()
            node = start + 1
            while node:
                if node in seen:
                    raise NeuralWindowingError("global windowed dependency tree contains a cycle")
                seen.add(node)
                node = heads[node - 1]

        deprel: list[str] = ["dep"] * n
        for dep, head_value in enumerate(heads):
            if head_value == 0:
                deprel[dep] = "root"
                continue
            relation_id = int(rel_ids[dep, head_value])
            if relation_id < 0:
                raise NeuralWindowingError(
                    "global windowed decoder selected an arc without an observed relation"
                )
            deprel[dep] = self.inv["deprel"][relation_id]
        if context is not None:
            from . import calibrate

            for dep, head_value in enumerate(heads):
                arc_row = arc[dep]
                safe_arc = np.where(np.isfinite(arc_row), arc_row, -1.0e30)
                raw_head = float(
                    calibrate.temperature_softmax(safe_arc, 1.0, np=np)[head_value]
                )
                raw_components[dep]["head"] = raw_head
                if head_value == 0:
                    raw_components[dep]["forced_root"] = 1.0
                else:
                    if rel_raw_probs is None:
                        raise NeuralWindowingError(
                            "windowed confidence relation grid was not allocated"
                        )
                    raw_components[dep]["relation"] = float(rel_raw_probs[dep, head_value])
                existing = token_confidences[dep]
                if existing is None:
                    continue
                head_entry, head_reason, head_resolution = _resolve_confidence_entry(self, context, "head")
                head_value_cal = _entry_probability(
                    head_entry, safe_arc, raw_head, np=np, selected_index=head_value
                )
                head_result = _confidence_result(
                    self, context, "head", head_value_cal,
                    entry=head_entry, reason=head_reason, resolution=head_resolution,
                )
                if head_value == 0:
                    relation_result = _confidence_result(
                        self, context, "relation", None, reason="forced_root"
                    )
                else:
                    relation_entry = window_relation_entry
                    relation_reason = window_relation_reason
                    relation_resolution = window_relation_resolution
                    relation_value = (
                        float(rel_cal_probs[dep, head_value])
                        if rel_cal_probs is not None
                        else _entry_probability(
                            relation_entry,
                            raw_probability=raw_components[dep]["relation"],
                            np=np,
                        )
                    )
                    relation_result = _confidence_result(
                        self,
                        context,
                        "relation",
                        relation_value,
                        entry=relation_entry,
                        reason=relation_reason,
                        resolution=relation_resolution,
                    )
                updated_results = (
                    existing.upos,
                    existing.xpos,
                    existing.feats,
                    existing.lemma,
                    head_result,
                    relation_result,
                )
                decisions = tuple(
                    decision
                    for result in updated_results
                    if (decision := _policy_decision(context.get("policy"), result)) is not None
                )
                token_confidences[dep] = replace(
                    existing,
                    index=dep,
                    head=head_result,
                    relation=relation_result,
                    policy=decisions,
                )
            if any(item is None for item in token_confidences):
                raise NeuralWindowingError(
                    "windowed confidence decode did not produce every owner token"
                )
            token_confidences_final = tuple(
                cast(TokenConfidence, item) for item in token_confidences
            )
            sentence_confidence = _sentence_confidence(self, context, raw_components)
        else:
            token_confidences_final = ()
            sentence_confidence = None
        warning = (
            "windowed neural analysis: complete-word overlapping windows; token tags, "
            "lemmas, and confidence use the farthest-boundary owner (earlier on ties), "
            "and dependencies use one global observed-arc MST",
        )
        return SentenceAnalysis(
            tokens=tuple(forms),
            upos=tuple(upos),
            xpos=tuple(xpos),
            feats=tuple(feats_from_xpos(x) for x in xpos),
            head=tuple(heads),
            deprel=tuple(deprel),
            lemma=tuple(lemma),
            lemma_resolved=tuple(resolved),
            upos_prob=tuple(upos_prob) if calibration is not None or context is not None else (),
            lemma_script_prob=tuple(lemma_prob) if calibration is not None or context is not None else (),
            lemma_source=tuple(lemma_source),
            lemma_source_path=tuple(lemma_source_path) if context is not None else (),
            lemma_verified=tuple(verified),
            analyzed=(True,) * n,
            complete=True,
            truncated=False,
            warnings=warning,
            token_confidences=token_confidences_final,
            sentence_confidence=sentence_confidence,
            receipt=self._receipt(
                input_tokens=n,
                analyzed_tokens=n,
                truncated=False,
                windowed=True,
                context=context,
            ),
        )

    def analyze(
        self,
        words: list[str],
        *,
        with_probs: bool = False,
        long_input: LongInputMode = "strict",
        domain: str | None = None,
        policy: AbstentionPolicy | None = None,
    ) -> SentenceAnalysis:
        """Analyze one pre-tokenized sentence.

        ``with_probs=False`` (the default) leaves ``upos_prob`` /
        ``lemma_script_prob`` empty ``()`` and preserves the historical predictions.
        ``with_probs=True`` fills them with calibrated top-1 confidences, and REQUIRES a
        loaded calibration (`aegean.greek.use_calibration`): with none loaded it raises
        `UncalibratedConfidenceError` rather than exposing a raw softmax.

        ``long_input="strict"`` refuses any sentence the manifest-declared subword
        budget cannot cover. ``"partial"`` retains all tokens but explicitly marks
        uncovered placeholders through ``complete``, ``analyzed``, and ``warnings``.
        ``"windowed"`` uses safe complete-word overlap windows and one global observed-arc
        tree; pathological or unsupported boundaries raise ``NeuralWindowingError``."""
        mode = _long_input_mode(long_input)
        context = _confidence_context(with_probs, domain=domain, policy=policy)
        calibration = None if context is None else context.get("legacy")
        forms = _prep.normalize_tokens(words)
        if not forms:
            return SentenceAnalysis(
                (), (), (), (), (), (), (), (), analyzed=(),
                sentence_confidence=(
                    _unavailable_sentence_confidence(self, context, "empty_sentence")
                    if context is not None
                    else None
                ),
                receipt=self._receipt(
                    input_tokens=0, analyzed_tokens=0, truncated=False, context=context
                ),
            )
        if mode == "windowed":
            # Refuse pathological input before cloning/tokenizing the complete sentence or
            # allocating any dense model/global-arc arrays.
            char_count = sum(len(form) for form in forms)
            if len(forms) > 4096 or char_count > 1_000_000:
                raise NeuralWindowingError(
                    "windowed neural analysis refuses inputs above its safety cap "
                    f"(4096 tokens and 1,000,000 characters; got {len(forms)} tokens and "
                    f"{char_count} characters)"
                )
            budget = self._window_body_budget()
            lengths = self._full_word_lengths(forms)
            if sum(lengths) <= budget:
                # Preserve ordinary in-limit output and receipt bytes exactly.
                return self._decode(forms, self._run(forms), calibration=calibration, context=context)
            windows = self._pack_windows(lengths, budget)
            return self._analyze_windowed(forms, lengths, windows, calibration=calibration, context=context)
        raw = self._run(forms)
        analyzed_tokens = len(raw["_kept"])
        truncated = analyzed_tokens != len(forms)
        if truncated and mode == "strict":
            raise NeuralInputTooLongError(
                input_tokens=len(forms),
                analyzed_tokens=analyzed_tokens,
                max_subwords=self.max_subwords,
            )
        return self._decode(forms, raw, calibration=calibration, context=context)

    def analyze_batch(
        self,
        sentences: list[list[str]],
        *,
        with_probs: bool = False,
        long_input: LongInputMode = "strict",
        domain: str | None = None,
        policy: AbstentionPolicy | None = None,
    ) -> list[SentenceAnalysis]:
        """Analyses of several sentences, one padded encoder pass per call.

        Produces the same fields as ``[self.analyze(s) for s in sentences]``; only the number of ONNX calls
        differs. Sequential per-sentence analysis is the recorded benchmark protocol
        (see `_run_batch` on float reduction order); batching is a throughput
        convenience. ``with_probs`` behaves as in `analyze` (calibration required).
        Windowed mode is always sequential and delegates to ``analyze`` so chunk size
        cannot change owner or tree reconciliation."""
        mode = _long_input_mode(long_input)
        if mode == "windowed":
            # Window reconciliation is intentionally sequential: chunking must never alter
            # owner assignment, global arc candidates, or the resulting tree.
            return [
                self.analyze(words, with_probs=with_probs, long_input="windowed", domain=domain, policy=policy)
                for words in sentences
            ]
        context = _confidence_context(with_probs, domain=domain, policy=policy)
        calibration = None if context is None else context.get("legacy")
        norm = [_prep.normalize_tokens(words) for words in sentences]
        out: list[SentenceAnalysis] = [
            SentenceAnalysis(
                (), (), (), (), (), (), (), (), analyzed=(),
                sentence_confidence=(
                    _unavailable_sentence_confidence(self, context, "empty_sentence")
                    if context is not None
                    else None
                ),
                receipt=self._receipt(
                    input_tokens=0, analyzed_tokens=0, truncated=False, context=context
                ),
            )
            for _ in norm
        ]
        live = [i for i, forms in enumerate(norm) if forms]
        if live:
            results = self._run_batch([norm[i] for i in live])
            if len(results) != len(live):
                raise RuntimeError(
                    "joint batch backend returned "
                    f"{len(results)} result(s) for {len(live)} non-empty sentence(s)"
                )
            for i, res in zip(live, results):
                analyzed_tokens = len(res["_kept"])
                if analyzed_tokens != len(norm[i]) and mode == "strict":
                    raise NeuralInputTooLongError(
                        input_tokens=len(norm[i]),
                        analyzed_tokens=analyzed_tokens,
                        max_subwords=self.max_subwords,
                    )
                out[i] = self._decode(norm[i], res, calibration=calibration, context=context)
        return out

    def _validate_stream_options(
        self,
        *,
        with_probs: bool,
        long_input: LongInputMode,
        domain: str | None,
        policy: AbstentionPolicy | None,
    ) -> dict[str, Any] | None:
        """Capture real-backend confidence state before a one-shot source is consumed."""

        _long_input_mode(long_input)
        context = _confidence_context(with_probs, domain=domain, policy=policy)
        if context is None:
            return None
        # Legacy Calibration owns mutable dictionaries despite being a frozen dataclass;
        # clone it so later caller mutation cannot change a live stream. Registry entries
        # are immutable too, but round-trip them for the same ownership guarantee.
        from .calibrate import Calibration

        legacy = context.get("legacy")
        registry = context.get("registry")
        return {
            **context,
            "legacy": (
                Calibration.from_dict(legacy.to_dict()) if legacy is not None else None
            ),
            "registry": (
                CalibrationRegistry.from_dict(registry.to_dict())
                if registry is not None
                else None
            ),
        }

    def _decode(
        self,
        forms: list[str],
        out: dict[str, Any],
        *,
        calibration: Any = None,
        context: dict[str, Any] | None = None,
    ) -> SentenceAnalysis:
        """Decode one sentence's raw arrays (from `_run`, or one `_run_batch` slice).

        When ``calibration`` is a `Calibration`, per-token calibrated top-1 confidences
        are computed from the SAME logits the argmax reads (no second pass) and returned
        in ``upos_prob`` / ``lemma_script_prob``; with ``calibration=None`` those fields
        stay empty ``()`` and the result is byte-identical to the pre-feature decode."""
        n = len(forms)
        np = self._np
        word_pos: list[int] = out["_word_pos"]
        kept: list[int] = out["_kept"]
        nw = len(kept)

        upos = ["X"] * n
        xpos = ["---------"] * n
        head = [0 if i == 0 else 1 for i in range(n)]
        rel = ["root" if i == 0 else "dep" for i in range(n)]
        lemma = list(forms)
        # default False = the identity fall-through (truncated / undecoded tokens keep
        # the surface form, which is not a real analysis)
        resolved = [False] * n
        lemma_source = [LemmaSource.IDENTITY] * n
        lemma_source_path = ["identity_fallback"] * n
        verified = [False] * n
        analyzed = [False] * n
        # None = a token with no model logits to read (an undecoded truncation fallback);
        # a float only for decoded words, and only when a calibration is active.
        upos_prob: list[float | None] = [None] * n
        lemma_prob: list[float | None] = [None] * n
        token_confidences: list[TokenConfidence] = []
        raw_components: list[dict[str, float]] = [{} for _ in range(n)]
        if context is not None or calibration is not None:
            from . import calibrate

        if nw:
            heads_w = decode_mst(out["arc"][0, :nw, : nw + 1])
            rel_scores = out["rel"][0]                      # [R, W, W+1]
            lem_ids = out["lemma"][0].argmax(-1)            # [W]
            t_upos = t_lemma = 1.0
            if calibration is not None:
                from . import calibrate  # local: numpy-lazy, keeps the no-probs path clean

                t_upos = calibration.temperature["upos"]
                t_lemma = calibration.temperature["lemma"]
            for wi, w in enumerate(kept):
                analyzed[w] = True
                sp = word_pos[wi]
                upos[w] = self.inv["upos"][int(out["upos"][0, sp].argmax())]
                xpos[w] = "".join(
                    self.inv[f"x{i}"][int(out[f"x{i}"][0, sp].argmax())] for i in range(9)
                )
                head[w] = heads_w[wi]
                rel[w] = self.inv["deprel"][int(rel_scores[:, wi, heads_w[wi]].argmax())]
                if head[w] == 0:
                    rel[w] = "root"
                lemma[w], resolved[w], lemma_source[w], lemma_source_path[w] = _compose_lemma_detail(
                    forms[w], upos[w], int(lem_ids[wi]), self
                )
                verified[w] = lemma_verified(lemma_source[w])
                if calibration is not None:
                    # Same logit vectors the argmaxes above read — temperature-scaled.
                    upos_prob[w] = float(
                        calibrate.top1_confidence(out["upos"][0, sp], t_upos, np=self._np)
                    )
                    lemma_prob[w] = float(
                        calibrate.top1_confidence(out["lemma"][0, wi], t_lemma, np=self._np)
                    )
                if context is not None:
                    upos_logits = out["upos"][0, sp]
                    raw_upos = float(calibrate.top1_confidence(upos_logits, 1.0, np=self._np))
                    upos_entry, upos_reason, upos_resolution = _resolve_confidence_entry(self, context, "upos")
                    upos_value = _entry_probability(upos_entry, upos_logits, raw_upos, np=self._np)
                    upos_result = _confidence_result(
                        self, context, "upos", upos_value,
                        entry=upos_entry, reason=upos_reason, resolution=upos_resolution,
                    )

                    raw_x: list[float] = []
                    for x_index in range(9):
                        x_logits = out[f"x{x_index}"][0, sp]
                        raw_x.append(float(calibrate.top1_confidence(x_logits, 1.0, np=self._np)))
                    raw_xpos = float(np.prod(raw_x, dtype=np.float64))
                    raw_feats = float(np.prod(raw_x[1:], dtype=np.float64))
                    xpos_entry, xpos_reason, xpos_resolution = _resolve_confidence_entry(self, context, "xpos")
                    feats_entry, feats_reason, feats_resolution = _resolve_confidence_entry(self, context, "feats")
                    xpos_value = _entry_probability(xpos_entry, raw_probability=raw_xpos, np=self._np)
                    feats_value = _entry_probability(feats_entry, raw_probability=raw_feats, np=self._np)
                    xpos_result = _confidence_result(
                        self, context, "xpos", xpos_value,
                        entry=xpos_entry, reason=xpos_reason or (
                            "unsupported_calibrator" if xpos_entry is not None and xpos_entry.calibrator != "logit_affine" else None
                        ), resolution=xpos_resolution,
                    )
                    feats_result = _confidence_result(
                        self, context, "feats", feats_value,
                        entry=feats_entry, reason=feats_reason or (
                            "unsupported_calibrator" if feats_entry is not None and feats_entry.calibrator != "logit_affine" else None
                        ), resolution=feats_resolution,
                    )

                    lemma_entry, lemma_reason, lemma_resolution = _resolve_confidence_entry(
                        self, context, "lemma", lemma_source_path[w]
                    )
                    lemma_logits = out["lemma"][0, wi]
                    raw_lemma = float(calibrate.top1_confidence(lemma_logits, 1.0, np=self._np))
                    lemma_value = _entry_probability(lemma_entry, lemma_logits, raw_lemma, np=self._np)
                    lemma_result = _confidence_result(
                        self, context, "lemma", lemma_value,
                        entry=lemma_entry, reason=lemma_reason,
                        source=lemma_source_path[w], resolution=lemma_resolution,
                    )
                    if calibration is None:
                        # Preserve the historical flat fields as a compatibility view
                        # of the structured registry result for v2-only activation.
                        upos_prob[w] = upos_result.value
                        lemma_prob[w] = lemma_result.value

                    arc_row = out["arc"][0, wi, : nw + 1]
                    selected_head = heads_w[wi]
                    safe_arc_row = np.where(np.isfinite(arc_row), arc_row, -1.0e30)
                    raw_head_vector = calibrate.temperature_softmax(safe_arc_row, 1.0, np=self._np)
                    raw_head = float(raw_head_vector[selected_head])
                    head_entry, head_reason, head_resolution = _resolve_confidence_entry(self, context, "head")
                    head_value = _entry_probability(
                        head_entry,
                        safe_arc_row,
                        raw_head,
                        np=self._np,
                        selected_index=selected_head,
                    )
                    head_result = _confidence_result(
                        self, context, "head", head_value,
                        entry=head_entry, reason=head_reason, resolution=head_resolution,
                    )

                    if selected_head == 0:
                        relation_result = _confidence_result(
                            self, context, "relation", None, reason="forced_root"
                        )
                    else:
                        rel_logits = rel_scores[:, wi, selected_head]
                        raw_relation = float(
                            calibrate.top1_confidence(rel_logits, 1.0, np=self._np)
                        )
                        relation_entry, relation_reason, relation_resolution = _resolve_confidence_entry(
                            self, context, "relation"
                        )
                        relation_value = _entry_probability(
                            relation_entry, rel_logits, raw_relation, np=self._np
                        )
                        relation_result = _confidence_result(
                            self, context, "relation", relation_value,
                            entry=relation_entry, reason=relation_reason, resolution=relation_resolution,
                        )
                    results = {
                        "upos": upos_result,
                        "xpos": xpos_result,
                        "feats": feats_result,
                        "lemma": lemma_result,
                        "head": head_result,
                        "relation": relation_result,
                    }
                    decisions = tuple(
                        decision
                        for result in results.values()
                        if (decision := _policy_decision(context.get("policy"), result)) is not None
                    )
                    token_confidences.append(
                        TokenConfidence(
                            index=w,
                            upos=upos_result,
                            xpos=xpos_result,
                            feats=feats_result,
                            lemma=lemma_result,
                            head=head_result,
                            relation=relation_result,
                            policy=decisions,
                        )
                    )
                    raw_components[w] = {
                        "upos": raw_upos,
                        "xpos": raw_xpos,
                        "lemma": raw_lemma,
                        "head": raw_head,
                        **(
                            {"relation": raw_relation}
                            if selected_head != 0
                            else {"forced_root": 1.0}
                        ),
                    }
        # exactly one root, even with truncation fallbacks in play
        roots = [i for i in range(n) if head[i] == 0]
        repaired: set[int] = set()
        first = roots[0] if roots else 0
        for i in roots[1:]:
            head[i] = first + 1
            rel[i] = "parataxis"
            repaired.add(i)
        if not roots:
            head[0], rel[0] = 0, "root"
            repaired.add(0)
        if context is not None:
            known = {item.index: item for item in token_confidences}
            normalized_confidences: list[TokenConfidence] = []
            for index in range(n):
                existing = known.get(index)
                if existing is not None:
                    if index in repaired:
                        repaired_head = _confidence_result(
                            self, context, "head", None, reason="post_decode_repair"
                        )
                        repaired_relation = _confidence_result(
                            self, context, "relation", None, reason="post_decode_repair"
                        )
                        repaired_results = (
                            existing.upos,
                            existing.xpos,
                            existing.feats,
                            existing.lemma,
                            repaired_head,
                            repaired_relation,
                        )
                        decisions = tuple(
                            decision
                            for result in repaired_results
                            if (decision := _policy_decision(context.get("policy"), result)) is not None
                        )
                        existing = replace(
                            existing,
                            head=repaired_head,
                            relation=repaired_relation,
                            policy=decisions,
                        )
                    normalized_confidences.append(existing)
                    continue
                unavailable = {
                    name: _confidence_result(
                        self, context, name, None, reason="partial_token"
                    )
                    for name in ("upos", "xpos", "feats", "lemma", "head", "relation")
                }
                decisions = tuple(
                    decision
                    for result in unavailable.values()
                    if (decision := _policy_decision(context.get("policy"), result)) is not None
                )
                normalized_confidences.append(
                    TokenConfidence(
                        index=index,
                        upos=unavailable["upos"],
                        xpos=unavailable["xpos"],
                        feats=unavailable["feats"],
                        lemma=unavailable["lemma"],
                        head=unavailable["head"],
                        relation=unavailable["relation"],
                        policy=decisions,
                    )
                )
            token_confidences = normalized_confidences
        truncated = not all(analyzed)
        warning = (
            (
                f"partial neural analysis: {sum(analyzed)} of {n} tokens fit the "
                f"{self.max_subwords}-subword model limit; tokens marked analyzed=False "
                "carry placeholders, not predictions"
            ),
        ) if truncated else ()
        sentence_confidence = None
        if context is not None:
            sentence_confidence = _sentence_confidence(self, context, raw_components)
            if repaired:
                sentence_confidence = _unavailable_sentence_confidence(
                    self, context, "post_decode_repair"
                )
        return SentenceAnalysis(
            tokens=tuple(forms), upos=tuple(upos), xpos=tuple(xpos),
            feats=tuple(feats_from_xpos(x) for x in xpos),
            head=tuple(head), deprel=tuple(rel), lemma=tuple(lemma),
            lemma_resolved=tuple(resolved),
            upos_prob=tuple(upos_prob) if calibration is not None or context is not None else (),
            lemma_script_prob=tuple(lemma_prob) if calibration is not None or context is not None else (),
            lemma_source=tuple(lemma_source),
            lemma_source_path=tuple(lemma_source_path) if context is not None else (),
            lemma_verified=tuple(verified),
            analyzed=tuple(analyzed),
            complete=not truncated,
            truncated=truncated,
            warnings=warning,
            token_confidences=tuple(token_confidences) if context is not None else (),
            sentence_confidence=sentence_confidence,
            receipt=self._receipt(
                input_tokens=n,
                analyzed_tokens=sum(analyzed),
                truncated=truncated,
                context=context,
            ),
        )


# Private compatibility hook for older internal tests that injected a fake backend by
# assigning ``joint._ACTIVE``. Production activation no longer writes it: the backend is
# owned by the default `GreekPipeline` instance. Remove this shim after downstream private
# users have migrated to explicit instances.
_UNSET = object()
_ACTIVE: Any = _UNSET


def _require_neural_extra() -> None:
    """Probe the ``[neural]`` extra BEFORE fetching, so a user who never installed it is
    told to ``pip install 'pyaegean[neural]'`` rather than to retry a ~173 MB download.

    The same import guard lives in `_JointModel.__init__`, but that runs only after
    `fetch` succeeds — on a fresh machine with no cached model the missing-extra message
    would otherwise be unreachable (a missing model would surface as a network/fetch error
    first). Extra presence is a cheap, purely-local fact, so this check is free."""
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        from tokenizers import Tokenizer  # noqa: F401
    except ModuleNotFoundError as e:
        raise NeuralPipelineNotLoadedError(
            "the neural pipeline needs the optional dependencies: "
            "pip install 'pyaegean[neural]'"
        ) from e


def _load_neural_backend(
    *, force: bool = False, expected_receipt: AnalysisReceipt | None = None
) -> _JointModel:
    """Load and validate one neural backend without changing facade state."""
    _require_neural_extra()
    asset = versions()["fetched"][_DATASET]
    model_dir = fetch(_DATASET, force=force)
    candidate = _JointModel(
        model_dir,
        asset_sha256=asset["sha256"] or None,
        asset_sha256_enforced=bool(asset["sha256_enforced"]),
    )
    if expected_receipt is not None:
        current = candidate._receipt(input_tokens=0, analyzed_tokens=0, truncated=False)
        if current is None:  # pragma: no cover - a real _JointModel always has a receipt
            raise ReceiptMismatchError("loaded neural runtime did not produce an analysis receipt")
        expected_receipt.assert_same_runtime(current)
    return candidate


def use_neural_pipeline(
    *, force: bool = False, expected_receipt: AnalysisReceipt | None = None
) -> None:
    """Activate the default neural pipeline facade (tags, morphology, trees, lemmas).

    Fetches the model bundle to the cache on first use — never bundled in the wheel —
    then loads it via onnxruntime. Requires the ``[neural]`` extra
    (``pip install 'pyaegean[neural]'``). Once active, `aegean.greek.pos_tags` /
    `pos_tag`, `aegean.greek.parse` (UD relations), and `aegean.greek.lemmatize`
    all use it; `analyze_sentence` returns the full joint analysis in one call.

    Pass ``expected_receipt`` to require the exact model, artifact, package/runtime
    versions, provider, profile, and preprocessing identity from a prior analysis.
    A mismatch raises `ReceiptMismatchError` before the candidate becomes active.

    Raises `NeuralPipelineNotLoadedError` if the optional dependencies are missing
    (checked before any download), and `aegean.data.DataNotAvailableError` if the
    download fails (set ``PYAEGEAN_GRC_JOINT_URL`` to fetch from your own mirror)."""
    global _ACTIVE
    from .runtime import GreekPipeline, _set_default_pipeline

    # A few older private callers assigned ``joint._ACTIVE`` directly.  A real
    # activation supersedes that compatibility shim so stale test state cannot
    # mask the newly selected default instance.
    _ACTIVE = _UNSET
    _set_default_pipeline(
        GreekPipeline._from_backend(
            _load_neural_backend(force=force, expected_receipt=expected_receipt)
        )
    )
    # Documentary levers are process-level opt-ins. Disabling the neural
    # backend temporarily must not leave their introspection flags true while
    # silently dropping their post-processing when a new backend is selected.
    from . import documentary

    documentary._sync()


def disable_neural_pipeline() -> None:
    """Deactivate the neural pipeline; every function falls back to its prior cascade."""
    global _ACTIVE
    from .runtime import GreekPipeline, _set_default_pipeline

    _ACTIVE = _UNSET
    _set_default_pipeline(GreekPipeline())


def active() -> _JointModel | None:
    """The bound instance's joint model, or the default facade model."""
    # An explicitly bound ``GreekPipeline`` owns the backend for the duration of
    # that call.  The legacy ``_ACTIVE`` assignment shim is retained for older
    # tests and private users, but it must never override an explicit instance.
    from .runtime import _bound_pipeline, _active_backend, default_pipeline

    bound = _bound_pipeline()
    if bound is not None and (bound is not default_pipeline() or _ACTIVE is _UNSET):
        return cast("_JointModel | None", bound._backend)
    if _ACTIVE is not _UNSET:  # private compatibility injection only
        return cast("_JointModel | None", _ACTIVE)
    return _active_backend()


def _replace_active_backend(backend: Any | None) -> None:
    """Replace the default facade backend, preserving the private injection shim."""
    global _ACTIVE
    if _ACTIVE is not _UNSET:
        _ACTIVE = backend
        return
    from .runtime import _replace_default_backend

    _replace_default_backend(backend)


def analyze_sentence(
    words: list[str],
    *,
    with_probs: bool = False,
    long_input: LongInputMode = "strict",
    domain: str | None = None,
    policy: AbstentionPolicy | None = None,
) -> SentenceAnalysis:
    """The full joint analysis of one pre-tokenized sentence (raises if not active).

    ``with_probs=True`` additionally fills the calibrated confidence fields and requires
    a loaded calibration. ``long_input`` is strict by default; partial mode returns
    explicit coverage status and warnings, while windowed mode reconciles complete-word
    overlap windows with one global observed-arc tree (see `_JointModel.analyze`)."""
    if (domain is not None or policy is not None) and not with_probs:
        raise ValueError("confidence domain/policy requires with_probs=True")
    model = active()
    if model is None:
        raise NeuralPipelineNotLoadedError(
            "neural pipeline not loaded — call aegean.greek.use_neural_pipeline() first"
        )
    # Keep the default call byte-identical to the historical signature (positional
    # ``words`` only), so existing callers and test stubs are unaffected; only a
    # confidence request threads the keyword through.
    if with_probs or long_input != "strict" or domain is not None or policy is not None:
        kwargs: dict[str, Any] = {"with_probs": with_probs, "long_input": long_input}
        if domain is not None:
            kwargs["domain"] = domain
        if policy is not None:
            kwargs["policy"] = policy
        return model.analyze(words, **kwargs)
    return model.analyze(words)


def _copy_stream_sentence(sentence: Iterable[str], *, sentence_index: int) -> list[str]:
    """Own and validate one source sentence without retaining the caller's container."""

    if isinstance(sentence, (str, bytes)):
        raise TypeError(
            f"sentence {sentence_index} must be an iterable of token strings, not "
            f"{type(sentence).__name__}"
        )
    try:
        words = list(sentence)
    except TypeError as exc:
        raise TypeError(
            f"sentence {sentence_index} must be an iterable of token strings"
        ) from exc
    for token_index, word in enumerate(words):
        if not isinstance(word, str):
            raise TypeError(
                f"sentence {sentence_index} token {token_index} must be a string, "
                f"not {type(word).__name__}"
            )
    return words


def _stream_backend(model: Any) -> Any:
    """Capture optional wrapper state so one stream has one analysis configuration."""

    snapshot = getattr(model, "_snapshot_for_stream", None)
    return snapshot() if callable(snapshot) else model


def iter_analyze_sentences(
    sentences: Iterable[Iterable[str]],
    *,
    batch_size: int | None = None,
    with_probs: bool = False,
    long_input: LongInputMode = "strict",
    domain: str | None = None,
    policy: AbstentionPolicy | None = None,
) -> Iterator[SentenceAnalysis]:
    """Yield joint analyses lazily from a pre-tokenized sentence iterable.

    The active backend and its opt-in wrapper state are captured when this function is
    called, before the source is touched. ``batch_size=None`` pulls and yields one sentence
    at a time. A positive integer pulls at most that many sentences, analyzes one
    transactional chunk, then yields it in source order. Pausing or closing the returned
    iterator never pulls another sentence. Once iteration begins, it takes ownership of
    that source iterator for cleanup: closing the result also calls a source ``close()``
    when one is provided.

    Memory therefore does not grow with the number of source sentences: it is bounded by
    one result/chunk plus the largest individual sentence. Results from completed chunks
    remain valid if a later source or backend operation fails. A failed chunk yields
    nothing, is not retried, and propagates the original backend/source exception. Every
    yielded ``SentenceAnalysis`` keeps its own unmodified receipt.

    ``batch_size=None`` (the default) analyzes each sentence with its own encoder pass —
    identical to calling `analyze_sentence` in a loop, and the code path the published
    benchmark numbers are measured on (plain CPU, ``CPUExecutionProvider``). A positive
    int runs padded chunks of that many sentences through the encoder (one ONNX call per
    chunk), a throughput convenience producing the same analyses; batched matmuls can
    reorder float reductions, so it is never used for the recorded protocol. ``with_probs``
    behaves as in `analyze_sentence` (calibration required). Strict and partial modes
    apply independently per sentence; windowed mode is always sequential inside the
    captured backend, so batch chunking cannot change owner or global-tree reconciliation.

    This is sentence-level streaming only. Raw-text analysis, corpus annotation, and
    CoNLL-U serialization retain their collecting contracts.
    """
    if (domain is not None or policy is not None) and not with_probs:
        raise ValueError("confidence domain/policy requires with_probs=True")
    _long_input_mode(long_input)
    if batch_size is not None:
        if not isinstance(batch_size, int) or isinstance(batch_size, bool):
            raise TypeError(
                f"batch_size must be a positive integer or None, got {batch_size!r}"
            )
        if batch_size < 1:
            raise ValueError(f"batch_size must be a positive integer, got {batch_size!r}")
    if isinstance(sentences, (str, bytes)):
        raise TypeError("sentences must be an iterable of token-string iterables")
    model = active()
    if model is None:
        raise NeuralPipelineNotLoadedError(
            "neural pipeline not loaded — call aegean.greek.use_neural_pipeline() first"
        )
    model = _stream_backend(model)
    method_name = "analyze" if batch_size is None else "analyze_batch"
    if not callable(getattr(model, method_name, None)):
        raise TypeError(f"active neural backend does not provide callable {method_name}()")
    captured_confidence: dict[str, Any] | None = None
    preflight = getattr(model, "_validate_stream_options", None)
    if callable(preflight):
        captured = preflight(
            with_probs=with_probs,
            long_input=long_input,
            domain=domain,
            policy=policy,
        )
        if isinstance(captured, dict):
            captured_confidence = captured

    use_options = (
        with_probs or long_input != "strict" or domain is not None or policy is not None
    )
    kwargs: dict[str, Any] = {"with_probs": with_probs, "long_input": long_input}
    if domain is not None:
        kwargs["domain"] = domain
    if policy is not None:
        kwargs["policy"] = policy

    def _iterator() -> Iterator[SentenceAnalysis]:
        source = iter(sentences)
        sentence_index = 0
        try:
            if batch_size is None:
                for sentence in source:
                    source_index = sentence_index
                    words = _copy_stream_sentence(
                        sentence, sentence_index=source_index
                    )
                    expected_tokens = tuple(_prep.normalize_tokens(words))
                    sentence_index += 1
                    with _bind_stream_confidence_context(captured_confidence):
                        analysis = (
                            model.analyze(words, **kwargs)
                            if use_options
                            else model.analyze(words)
                        )
                    if not isinstance(analysis, SentenceAnalysis):
                        raise TypeError(
                            "joint backend result at source index "
                            f"{source_index} must be SentenceAnalysis, not "
                            f"{type(analysis).__name__}"
                        )
                    if analysis.tokens != expected_tokens:
                        raise RuntimeError(
                            "joint backend did not preserve source order at index "
                            f"{source_index}: expected tokens {expected_tokens!r}, "
                            f"got {analysis.tokens!r}"
                        )
                    yield analysis
                return

            while True:
                chunk_start = sentence_index
                chunk: list[list[str]] = []
                for _ in range(batch_size):
                    try:
                        sentence = next(source)
                    except StopIteration:
                        break
                    chunk.append(
                        _copy_stream_sentence(sentence, sentence_index=sentence_index)
                    )
                    sentence_index += 1
                if not chunk:
                    return
                # Do not retain the producer's last sentence object in addition to the
                # owned copies in this chunk while results are yielded.
                del sentence
                expected_batch = [
                    tuple(_prep.normalize_tokens(words)) for words in chunk
                ]
                with _bind_stream_confidence_context(captured_confidence):
                    analyses = (
                        model.analyze_batch(chunk, **kwargs)
                        if use_options
                        else model.analyze_batch(chunk)
                    )
                if not isinstance(analyses, list):
                    raise TypeError(
                        "joint batch backend must return a list of SentenceAnalysis values"
                    )
                if len(analyses) != len(chunk):
                    chunk_end = chunk_start + len(chunk) - 1
                    raise RuntimeError(
                        "joint batch backend returned "
                        f"{len(analyses)} result(s) for {len(chunk)} sentence(s) "
                        f"at source indices {chunk_start}..{chunk_end}"
                    )
                for offset, analysis in enumerate(analyses):
                    if not isinstance(analysis, SentenceAnalysis):
                        raise TypeError(
                            "joint batch backend result at source index "
                            f"{chunk_start + offset} must be SentenceAnalysis, not "
                            f"{type(analysis).__name__}"
                        )
                    expected_tokens = expected_batch[offset]
                    if analysis.tokens != expected_tokens:
                        raise RuntimeError(
                            "joint batch backend did not preserve source order at index "
                            f"{chunk_start + offset}: expected tokens {expected_tokens!r}, "
                            f"got {analysis.tokens!r}"
                        )
                chunk_size = len(chunk)
                yield from analyses
                # `yield from` has completed: release this entire chunk before pulling
                # the next one, keeping live token ownership at one batch rather than two.
                del analysis, analyses, chunk, expected_batch, expected_tokens
                if chunk_size < batch_size:
                    return
        finally:
            primary_error = sys.exc_info()[1]
            try:
                close = getattr(source, "close", None)
            except BaseException:
                if primary_error is None:
                    raise
                close = None
            if callable(close):
                try:
                    close()
                except BaseException:
                    # Never replace a backend/source failure or consumer GeneratorExit
                    # with a secondary cleanup error. On ordinary exhaustion, however,
                    # a source's failing close remains visible to the caller.
                    if primary_error is None:
                        raise

    return _iterator()


def analyze_sentences(
    sentences: Iterable[Iterable[str]],
    *,
    batch_size: int | None = None,
    with_probs: bool = False,
    long_input: LongInputMode = "strict",
    domain: str | None = None,
    policy: AbstentionPolicy | None = None,
) -> list[SentenceAnalysis]:
    """Collect `iter_analyze_sentences` into a list for compatibility.

    Use `iter_analyze_sentences` when output memory must remain bounded or results should
    become visible incrementally. This collector still returns the historical list, but it
    no longer materializes a second complete copy of the input before analysis starts.
    """

    return list(
        iter_analyze_sentences(
            sentences,
            batch_size=batch_size,
            with_probs=with_probs,
            long_input=long_input,
            domain=domain,
            policy=policy,
        )
    )


def neural_backend_info() -> dict[str, Any]:
    """Which ONNX Runtime execution providers the neural pipeline can and does use.

    Returns ``{"model", "available_providers", "active_providers"}``: ``model`` is the
    joint model's dataset name (the pinned ``grc-joint`` release asset);
    ``available_providers`` is what the installed onnxruntime offers (``None`` when the
    ``[neural]`` extra is not installed); ``active_providers`` is what the live joint
    session actually runs on (``session.get_providers()``), or ``None`` when the
    pipeline is not active. Never fetches, never raises for a missing extra.

    The published benchmark numbers are measured on ``CPUExecutionProvider``; GPU
    execution (``PYAEGEAN_ORT_PROVIDERS``, or auto-detected CUDA/DirectML) is a
    throughput convenience, and the int8-quantized models may partition only partially
    onto a GPU provider."""
    available: list[str] | None = None
    try:
        import onnxruntime as ort
    except ImportError:
        pass
    else:
        available = list(ort.get_available_providers())
    active_providers: list[str] | None = None
    model = active()
    if model is not None:
        active_providers = list(model._sess.get_providers())
    return {
        "model": _DATASET,
        "available_providers": available,
        "active_providers": active_providers,
    }
