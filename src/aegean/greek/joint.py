"""The neural Greek pipeline — one model for tags, morphology, trees, and lemmas.

The opt-in ``[neural]`` backend's flagship: a jointly-trained GreBerta encoder with
token-classification heads (UPOS + the 9 AGDT postag positions), biaffine arc/relation
scorers decoded by a single-root MST (`aegean.greek.mst`), and an edit-script lemma head
composed with a train-only lookup. Trained leakage-clean on AGDT + Gorman + Pedalion
(1.41M tokens); measured on the UD Ancient Greek (Perseus) test fold at UPOS 97.0,
UFeats 96.0, lemma 94.3, XPOS 93.5, UAS 90.2, and LAS 85.7. See
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
from collections.abc import Iterable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from ..data import fetch, versions
from . import _joint_windowing as _windowing
from . import _ort
from . import neural_preprocessing as _prep
from ._joint_confidence import (
    _STREAM_CONFIDENCE_CONTEXT as _STREAM_CONFIDENCE_CONTEXT,
    _STREAM_CONFIDENCE_UNSET as _STREAM_CONFIDENCE_UNSET,
    _bind_stream_confidence_context as _bind_stream_confidence_context,
    _confidence_context,
    _confidence_result,
    _entry_probability,
    _model_id as _model_id,
    _policy_decision,
    _resolve_confidence_entry,
    _sentence_confidence,
    _unavailable_sentence_confidence,
)
from ._joint_streaming import (
    _copy_stream_sentence as _copy_stream_sentence,
    _stream_backend as _stream_backend,
    analyze_sentences_impl,
    iter_analyze_sentences_impl,
)
from ._joint_types import (
    _TOP_LEMMA_EDIT_STATE,
    LongInputMode as LongInputMode,
    NeuralInputTooLongError,
    NeuralPipelineNotLoadedError,
    NeuralWindowingError,
    SentenceAnalysis,
    _best_non_root_relation,
    _capture_top_lemma_edits as _capture_top_lemma_edits,
    _extract_top_k_edits_for_word,
    _long_input_mode,
)
from .confidence import (
    AbstentionPolicy,
    CalibrationRegistry,
    SentenceConfidence,
    TokenConfidence,
)
from .lemmatize import LemmaSource, lemma_verified
from .model_variants import (
    NeuralRuntimeVariant,
    NeuralVariantError,
    _resolve_neural_variant,
    neural_variants,
    variant_registry_sha256,
)
from .mst import decode_mst
from .neural_contract import (
    AnalysisReceipt,
    ModelBundleError,
    ModelBundleManifest,
    ReceiptMismatchError,
)
from .udfeats import feats_from_xpos

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


class _JointModel:
    """A loaded joint ONNX model + tokenizer + label maps + lemma scripts/lookup."""

    def __init__(
        self,
        model_dir: Path,
        *,
        asset_sha256: str | None = None,
        asset_sha256_enforced: bool = False,
        runtime_variant: NeuralRuntimeVariant | None = None,
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
        self.runtime_variant = runtime_variant
        if runtime_variant is not None:
            mismatches: list[str] = []
            if self.manifest.model_id != runtime_variant.model_id:
                mismatches.append(
                    f"model_id: registry={runtime_variant.model_id!r}, "
                    f"bundle={self.manifest.model_id!r}"
                )
            if self.manifest.dataset != runtime_variant.dataset:
                mismatches.append(
                    f"dataset: registry={runtime_variant.dataset!r}, "
                    f"bundle={self.manifest.dataset!r}"
                )
            if self.manifest.manifest_sha256 != runtime_variant.bundle_manifest_sha256:
                mismatches.append(
                    "bundle_manifest_sha256: "
                    f"registry={runtime_variant.bundle_manifest_sha256!r}, "
                    f"bundle={self.manifest.manifest_sha256!r}"
                )
            if not self.manifest.asset_sha256_enforced:
                mismatches.append("asset_sha256: fetched artifact is not SHA-256 enforced")
            elif self.manifest.asset_sha256 != runtime_variant.asset_sha256:
                mismatches.append(
                    f"asset_sha256: registry={runtime_variant.asset_sha256!r}, "
                    f"fetched={self.manifest.asset_sha256!r}"
                )
            if mismatches:
                raise ModelBundleError(
                    f"neural runtime variant {runtime_variant.label!r} does not match "
                    "the fetched bundle: " + "; ".join(mismatches)
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
                f"run `aegean data remove "
                f"{runtime_variant.dataset if runtime_variant is not None else _DATASET}` "
                "and retry, or call "
                f"use_neural_pipeline(force=True)."
            ) from e
        actual_outputs = tuple(output.name for output in self._sess.get_outputs())
        if set(actual_outputs) != set(self.manifest.output_heads):
            raise ModelBundleError(
                "model.onnx output heads disagree with the bundle manifest: "
                f"expected {list(self.manifest.output_heads)!r}, got {list(actual_outputs)!r}"
            )
        self._output_names: tuple[str, ...] = actual_outputs
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

    def _session_output_names(self) -> tuple[str, ...]:
        cached = getattr(self, "_output_names", None)
        if cached is not None:
            return cast(tuple[str, ...], cached)
        return tuple(o.name for o in self._sess.get_outputs())

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
        names = self._session_output_names()
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
        names = self._session_output_names()
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
        runtime_variant = getattr(self, "runtime_variant", None)
        receipt = AnalysisReceipt.create(
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
            runtime_variant=(
                runtime_variant.label if runtime_variant is not None else None
            ),
            variant_registry_sha256=(
                variant_registry_sha256() if runtime_variant is not None else None
            ),
            variant_award_sha256=(
                runtime_variant.award_sha256 if runtime_variant is not None else None
            ),
            qualification_sha256=(
                runtime_variant.qualification_sha256 if runtime_variant is not None else None
            ),
        )
        # The joint model emits the canonical annotation profile.  Keep this lazy
        # so loading the contract itself remains independent of the profile registry.
        from .annotation_profiles import canonical_analysis_profile

        profile = canonical_analysis_profile()
        if receipt.annotation_profile == profile.inference_annotation_profile:
            return receipt.with_analysis_profile(profile)
        # A future/custom manifest must declare its own composed output profile rather
        # than being mislabeled as the shipped canonical convention.
        return receipt

    def _window_body_budget(self) -> int:
        """Return the manifest subword budget available to complete input words."""
        return _windowing.window_body_budget(self)

    def _full_word_lengths(self, words: list[str]) -> list[int]:
        """Measure every word with an untruncated clone of the active tokenizer."""
        return _windowing.full_word_lengths(self, words)

    @staticmethod
    def _pack_windows(lengths: list[int], budget: int) -> list[tuple[int, int]]:
        """Pack complete-word windows with a subword-bounded suffix overlap."""
        return _windowing.pack_windows(lengths, budget)

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
        return _windowing.analyze_windowed(
            self,
            forms,
            lengths,
            windows,
            calibration=calibration,
            context=context,
        )

    def _extract_sentence_top_edits(
        self,
        forms: list[str],
        raw: dict[str, Any],
        k: int,
    ) -> tuple[tuple[tuple[str, float], ...], ...]:
        """Extract per-token top-K neural edit predictions for one non-windowed decode."""
        per_tok: list[tuple[tuple[str, float], ...]] = [() for _ in forms]
        kept: list[int] = raw.get("_kept", [])
        lem_mat = raw.get("lemma")
        if lem_mat is None or not kept:
            return tuple(per_tok)
        lem_rows = lem_mat[0]
        for wi, orig_idx in enumerate(kept):
            if 0 <= orig_idx < len(forms):
                per_tok[orig_idx] = _extract_top_k_edits_for_word(
                    forms[orig_idx], lem_rows[wi], self.trees, self._np, k
                )
        return tuple(per_tok)

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
        edit_capture = _TOP_LEMMA_EDIT_STATE.get()
        forms = _prep.normalize_tokens(words)
        if not forms:
            if edit_capture is not None:
                edit_capture[1].append(())
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
                raw = self._run(forms)
                if edit_capture is not None:
                    edit_capture[1].append(
                        self._extract_sentence_top_edits(forms, raw, edit_capture[0])
                    )
                return self._decode(forms, raw, calibration=calibration, context=context)
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
        if edit_capture is not None:
            edit_capture[1].append(
                self._extract_sentence_top_edits(forms, raw, edit_capture[0])
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

        Produces the same fields as ``[self.analyze(s) for s in sentences]``, one
        `SentenceAnalysis` per input sentence in the same order, but not necessarily
        the same values: a batch is padded to its longest member, and that changes
        float reduction order in the batched matmuls (see `_run_batch`), so a few
        tokens in a large run can come back with a different tag, feature, lemma, or
        arc. Sequential per-sentence analysis is the recorded benchmark protocol;
        batching is a throughput convenience, and how much its results move depends on
        the batch size and on how far the sentence lengths in a batch spread.
        ``with_probs`` behaves as in `analyze` (calibration required).
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
        edit_capture = _TOP_LEMMA_EDIT_STATE.get()
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
        batch_edits: list[tuple[tuple[tuple[str, float], ...], ...]] | None = (
            [() for _ in norm] if edit_capture is not None else None
        )
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
                if batch_edits is not None and edit_capture is not None:
                    batch_edits[i] = self._extract_sentence_top_edits(
                        norm[i], res, edit_capture[0]
                    )
                out[i] = self._decode(norm[i], res, calibration=calibration, context=context)
        if edit_capture is not None and batch_edits is not None:
            edit_capture[1].extend(batch_edits)
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
                selected_rel: int | None = None
                if head[w] == 0:
                    rel[w] = "root"
                else:
                    selected_rel = _best_non_root_relation(
                        rel_scores[:, wi, heads_w[wi]], self.inv["deprel"]
                    )
                    rel[w] = self.inv["deprel"][selected_rel]
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
                        assert selected_rel is not None
                        rel_logits = rel_scores[:, wi, selected_head]
                        safe_rel_logits = np.where(np.isfinite(rel_logits), rel_logits, -1.0e30)
                        raw_relation_vector = calibrate.temperature_softmax(
                            safe_rel_logits, 1.0, np=self._np
                        )
                        raw_relation = float(raw_relation_vector[selected_rel])
                        relation_entry, relation_reason, relation_resolution = _resolve_confidence_entry(
                            self, context, "relation"
                        )
                        relation_value = _entry_probability(
                            relation_entry,
                            safe_rel_logits,
                            raw_relation,
                            np=self._np,
                            selected_index=selected_rel,
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
    *,
    variant: str = "default",
    force: bool = False,
    expected_receipt: AnalysisReceipt | None = None,
) -> _JointModel:
    """Load and validate one neural backend without changing facade state."""
    selected = _resolve_neural_variant(variant)
    _require_neural_extra()
    assert selected.dataset is not None
    assert selected.asset_sha256 is not None
    assets = versions()["fetched"]
    try:
        asset = assets[selected.dataset]
    except KeyError as exc:
        raise NeuralVariantError(
            f"neural runtime variant {variant!r} names unregistered dataset "
            f"{selected.dataset!r}"
        ) from exc
    if not asset["sha256_enforced"] or asset["sha256"] != selected.asset_sha256:
        raise NeuralVariantError(
            f"neural runtime variant {variant!r} requires the exact enforced data-registry pin"
        )
    model_dir = fetch(selected.dataset, force=force)
    candidate = _JointModel(
        model_dir,
        asset_sha256=asset["sha256"] or None,
        asset_sha256_enforced=bool(asset["sha256_enforced"]),
        runtime_variant=selected,
    )
    if expected_receipt is not None:
        current = candidate._receipt(input_tokens=0, analyzed_tokens=0, truncated=False)
        if current is None:  # pragma: no cover - a real _JointModel always has a receipt
            raise ReceiptMismatchError("loaded neural runtime did not produce an analysis receipt")
        expected_receipt.assert_same_runtime(current)
    return candidate


def use_neural_pipeline(
    *,
    variant: str = "default",
    force: bool = False,
    expected_receipt: AnalysisReceipt | None = None,
) -> None:
    """Activate the default neural pipeline facade (tags, morphology, trees, lemmas).

    Fetches the model bundle to the cache on first use — never bundled in the wheel —
    then loads it via onnxruntime. Requires the ``[neural]`` extra
    (``pip install 'pyaegean[neural]'``). Once active, `aegean.greek.pos_tags` /
    `pos_tag`, `aegean.greek.parse` (UD relations), and `aegean.greek.lemmatize`
    all use it; `analyze_sentence` returns the full joint analysis in one call.

    ``variant`` selects an evidence-bound runtime label. The default remains the
    release-selected artifact; a reserved label fails before dependency checks or
    network access rather than silently falling back. Pass ``expected_receipt`` to
    require the exact model, artifact, package/runtime
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
            _load_neural_backend(
                variant=variant,
                force=force,
                expected_receipt=expected_receipt,
            )
        )
    )
    # Documentary levers are process-level opt-ins. Disabling the neural
    # backend temporarily must not leave their introspection flags true while
    # silently dropping their post-processing when a new backend is selected.
    from . import documentary, lemma_rerank

    documentary._sync()
    lemma_rerank._sync()


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
    chunk). That is a throughput convenience, not a free one: each chunk is padded to its
    longest sentence, which reorders float reductions in the batched matmuls, so a few
    tokens in a large run can be tagged, lemmatized, or attached differently than the
    sequential path tags them. The result is therefore not prediction-identical and is
    never used for the recorded protocol; a batched score should not be compared with a
    sequential one. ``with_probs``
    behaves as in `analyze_sentence` (calibration required). Strict and partial modes
    apply independently per sentence; windowed mode is always sequential inside the
    captured backend, so batch chunking cannot change owner or global-tree reconciliation.

    This is sentence-level streaming only. Raw-text analysis, corpus annotation, and
    CoNLL-U serialization retain their collecting contracts.
    """
    return iter_analyze_sentences_impl(
        sentences,
        active_fn=active,
        batch_size=batch_size,
        with_probs=with_probs,
        long_input=long_input,
        domain=domain,
        policy=policy,
    )


def analyze_sentences(
    sentences: Iterable[Iterable[str]],
    *,
    batch_size: int | None = None,
    length_bucket: bool = False,
    with_probs: bool = False,
    long_input: LongInputMode = "strict",
    domain: str | None = None,
    policy: AbstentionPolicy | None = None,
) -> list[SentenceAnalysis]:
    """Collect `iter_analyze_sentences` into a list for compatibility.

    Use `iter_analyze_sentences` when output memory must remain bounded or results should
    become visible incrementally. This collector still returns the historical list, but it
    no longer materializes a second complete copy of the input before analysis starts.

    Every argument keeps its meaning there, ``batch_size`` included: the default of one
    encoder pass per sentence is the sequential path the published numbers are measured
    on, and a positive int trades prediction-identity for throughput. Passing
    ``length_bucket=True`` with ``batch_size > 1`` (and non-windowed ``long_input``)
    groups similarly sized sentences into each padded batch to reduce padding waste and
    restores the exact original input order before returning.
    """
    return analyze_sentences_impl(
        sentences,
        iter_fn=iter_analyze_sentences,
        batch_size=batch_size,
        length_bucket=length_bucket,
        with_probs=with_probs,
        long_input=long_input,
        domain=domain,
        policy=policy,
    )


def neural_backend_info() -> dict[str, Any]:
    """Which ONNX Runtime execution providers the neural pipeline can and does use.

    Returns provider facts plus the stable available/default/active runtime labels. ``model`` is the
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
    active_variant: str | None = None
    model = active()
    if model is not None:
        active_providers = list(model._sess.get_providers())
        selected = getattr(model, "runtime_variant", None)
        active_variant = selected.label if selected is not None else None
    return {
        "model": _DATASET,
        "default_variant": "default",
        "available_variants": [item.label for item in neural_variants(available_only=True)],
        "active_variant": active_variant,
        "available_providers": available,
        "active_providers": active_providers,
    }
