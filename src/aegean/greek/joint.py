"""The neural Greek pipeline — one model for tags, morphology, trees, and lemmas.

The opt-in ``[neural]`` backend's flagship: a jointly-trained GreBerta encoder with
token-classification heads (UPOS + the 9 AGDT postag positions), biaffine arc/relation
scorers decoded by a single-root MST (`aegean.greek.mst`), and an edit-script lemma head
composed with a train-only lookup. Trained leakage-clean on AGDT + Gorman + Pedalion
(1.41M tokens); measured on the UD Ancient Greek (Perseus) test fold as the **best published
result on every metric** (UD Perseus: UPOS 97.0, UFeats 96.0, lemma 94.3, XPOS 93.5,
UAS 90.2, LAS 85.6 — see ``docs/benchmarks.md`` for protocol, seeds, and bootstrap CIs;
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
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from ..data import fetch, versions
from . import _ort
from .lemmatize import LemmaSource, lemma_verified
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
    "active",
    "analyze_sentence",
    "analyze_sentences",
    "disable_neural_pipeline",
    "neural_backend_info",
    "use_neural_pipeline",
]

# Registered in aegean.data._REMOTE; fetched + extracted to the cache on first use.
_DATASET = "grc-joint"
LongInputMode = Literal["strict", "partial", "windowed"]


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


def _compose_lemma(
    form: str, upos: str, script_id: int, model: "_JointModel"
) -> tuple[str, bool, LemmaSource]:
    """The dev-preferred ``lookup-first`` composition, with an honesty flag: returns
    ``(lemma, resolved, source)``. ``resolved`` is True when a real analysis was found: a
    (form|UPOS) or form lookup, a predicted non-identity edit script, or a lowercase
    lookup — and False for the identity fall-through (the form itself). A lemma that
    equals the surface form is still ``resolved=True`` when it came from a lookup (a
    nominative singular is a genuine analysis), so callers must not infer the source
    from a string compare."""
    looked = model.lookup_form_upos.get(f"{form}|{upos}") or model.lookup_form.get(form)
    if looked:
        return looked, True, LemmaSource.NEURAL_LOOKUP
    if 0 <= script_id < len(model.trees):
        from .lemmatizer import apply_tree

        applied = apply_tree(model.trees[script_id], form)
        # Two edit-script outputs are never a grounded lemma: the literal "_" (a CoNLL-U
        # empty-LEMMA placeholder that leaked into the training scripts) and the surface
        # form unchanged (the identity script — an out-of-vocabulary form the model just
        # kept; a GENUINE identity lemma, a nominative, comes from the lookups above and
        # stays resolved). Both fall through to the remaining lookups / honest identity.
        if applied and applied != "_" and applied != form:
            return applied, True, LemmaSource.NEURAL_EDIT
    low = model.lookup_lower.get(form.lower())
    if low:
        return low, True, LemmaSource.NEURAL_LOOKUP
    return form, False, LemmaSource.IDENTITY


def _probs_calibration(with_probs: bool) -> Any:
    """Resolve the calibration to use when ``with_probs`` is requested, enforcing the
    honesty rule: return ``None`` when probs are not asked for, the active `Calibration`
    when one is loaded, and RAISE otherwise — a raw (uncalibrated) softmax is never
    exposed. Returns a `aegean.greek.calibrate.Calibration` or ``None``."""
    if not with_probs:
        return None
    from . import calibrate

    cal = calibrate.active()
    if cal is None:
        raise calibrate.UncalibratedConfidenceError(
            "uncalibrated confidence is not exposed; load or fit a calibration first "
            "(aegean.greek.use_calibration()). The project never surfaces a raw softmax "
            "probability (measured-claims-only)."
        )
    return cal


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
        enc = self._tok.encode(words[: self.manifest.max_subwords], is_pretokenized=True)
        ids = enc.ids[: self.manifest.max_subwords]
        word_ids = enc.word_ids[: len(ids)]
        # With stride=0, the first overflow retains the rest of a word that straddled the
        # right-truncation boundary. Its first real word ID equals the last ID in the main
        # encoding only when that last word is incomplete; a clean between-word boundary
        # starts the overflow at the next ID. Remove every fragment of the incomplete word
        # while preserving special tokens, so coverage is whole-token honest.
        overflowing = getattr(enc, "overflowing", ())
        if overflowing:
            first_overflow = next(
                (wid for wid in overflowing[0].word_ids if wid is not None), None
            )
            last_main = next((wid for wid in reversed(word_ids) if wid is not None), None)
            if first_overflow is not None and first_overflow == last_main:
                complete = [wid != last_main for wid in word_ids]
                ids = [token_id for token_id, keep in zip(ids, complete) if keep]
                word_ids = [wid for wid, keep in zip(word_ids, complete) if keep]
        word_pos: list[int] = []
        kept: list[int] = []
        prev = None
        for si, wid in enumerate(word_ids):
            if wid is not None and wid != prev:
                word_pos.append(si)
                kept.append(wid)
            prev = wid
        return ids, word_pos, kept

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
        )

    def _window_body_budget(self) -> int:
        """Return the manifest subword budget available to complete input words."""
        manifest = getattr(self, "manifest", None)
        policy = getattr(manifest, "special_token_policy", None)
        if manifest is not None and policy != "roberta:<s>:0:</s>:2":
            raise NeuralWindowingError(
                "windowed neural analysis requires the validated two-token policy "
                "roberta:<s>:0:</s>:2"
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
        verified = [False] * n
        upos_prob: list[float | None] = [None] * n
        lemma_prob: list[float | None] = [None] * n
        arc = np.full((n, n + 1), -np.inf, dtype=np.float32)
        # Relation IDs are bounded by the validated manifest label map.  A compact int16
        # candidate grid avoids an R x N² float tensor; -1 means no finite relation score.
        relation_count = len(self.inv["deprel"])
        if relation_count > int(np.iinfo(np.int16).max):
            raise NeuralWindowingError(
                "windowed neural analysis cannot compact a relation map larger than int16"
            )
        rel_ids = np.full((n, n + 1), -1, dtype=np.int16)

        for wi, (ws, we) in enumerate(windows):
            chunk = forms[ws:we]
            raw = self._run(chunk)
            if raw.get("_kept") != list(range(we - ws)):
                raise NeuralWindowingError(
                    "windowed tokenizer failed to return every complete word in a window"
                )
            local = self._decode(chunk, raw, calibration=calibration)
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
                verified[token] = local.lemma_verified[local_i]
                if local.upos_prob:
                    upos_prob[token] = local.upos_prob[local_i]
                if local.lemma_script_prob:
                    lemma_prob[token] = local.lemma_script_prob[local_i]
                for local_head, score in enumerate(local_arc[local_i]):
                    global_head = 0 if local_head == 0 else ws + local_head
                    if global_head < 0 or global_head > n:
                        continue
                    arc[token, global_head] = score
                    rel_vector = np.asarray(local_rel[:, local_i, local_head])
                    if np.isfinite(rel_vector).any():
                        rel_ids[token, global_head] = np.int16(rel_vector.argmax())
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
            upos_prob=tuple(upos_prob) if calibration is not None else (),
            lemma_script_prob=tuple(lemma_prob) if calibration is not None else (),
            lemma_source=tuple(lemma_source),
            lemma_verified=tuple(verified),
            analyzed=(True,) * n,
            complete=True,
            truncated=False,
            warnings=warning,
            receipt=self._receipt(
                input_tokens=n,
                analyzed_tokens=n,
                truncated=False,
                windowed=True,
            ),
        )

    def analyze(
        self,
        words: list[str],
        *,
        with_probs: bool = False,
        long_input: LongInputMode = "strict",
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
        calibration = _probs_calibration(with_probs)
        forms = [unicodedata.normalize("NFC", w) for w in words]
        if not forms:
            return SentenceAnalysis(
                (), (), (), (), (), (), (), (), analyzed=(),
                receipt=self._receipt(input_tokens=0, analyzed_tokens=0, truncated=False),
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
                return self._decode(forms, self._run(forms), calibration=calibration)
            windows = self._pack_windows(lengths, budget)
            return self._analyze_windowed(forms, lengths, windows, calibration=calibration)
        raw = self._run(forms)
        analyzed_tokens = len(raw["_kept"])
        truncated = analyzed_tokens != len(forms)
        if truncated and mode == "strict":
            raise NeuralInputTooLongError(
                input_tokens=len(forms),
                analyzed_tokens=analyzed_tokens,
                max_subwords=self.max_subwords,
            )
        return self._decode(forms, raw, calibration=calibration)

    def analyze_batch(
        self,
        sentences: list[list[str]],
        *,
        with_probs: bool = False,
        long_input: LongInputMode = "strict",
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
                self.analyze(words, with_probs=with_probs, long_input="windowed")
                for words in sentences
            ]
        calibration = _probs_calibration(with_probs)
        norm = [[unicodedata.normalize("NFC", w) for w in words] for words in sentences]
        out: list[SentenceAnalysis] = [
            SentenceAnalysis(
                (), (), (), (), (), (), (), (), analyzed=(),
                receipt=self._receipt(input_tokens=0, analyzed_tokens=0, truncated=False),
            )
            for _ in norm
        ]
        live = [i for i, forms in enumerate(norm) if forms]
        if live:
            results = self._run_batch([norm[i] for i in live])
            for i, res in zip(live, results):
                analyzed_tokens = len(res["_kept"])
                if analyzed_tokens != len(norm[i]) and mode == "strict":
                    raise NeuralInputTooLongError(
                        input_tokens=len(norm[i]),
                        analyzed_tokens=analyzed_tokens,
                        max_subwords=self.max_subwords,
                    )
                out[i] = self._decode(norm[i], res, calibration=calibration)
        return out

    def _decode(
        self, forms: list[str], out: dict[str, Any], *, calibration: Any = None
    ) -> SentenceAnalysis:
        """Decode one sentence's raw arrays (from `_run`, or one `_run_batch` slice).

        When ``calibration`` is a `Calibration`, per-token calibrated top-1 confidences
        are computed from the SAME logits the argmax reads (no second pass) and returned
        in ``upos_prob`` / ``lemma_script_prob``; with ``calibration=None`` those fields
        stay empty ``()`` and the result is byte-identical to the pre-feature decode."""
        n = len(forms)
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
        verified = [False] * n
        analyzed = [False] * n
        # None = a token with no model logits to read (an undecoded truncation fallback);
        # a float only for decoded words, and only when a calibration is active.
        upos_prob: list[float | None] = [None] * n
        lemma_prob: list[float | None] = [None] * n

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
                lemma[w], resolved[w], lemma_source[w] = _compose_lemma(
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
        # exactly one root, even with truncation fallbacks in play
        roots = [i for i in range(n) if head[i] == 0]
        first = roots[0] if roots else 0
        for i in roots[1:]:
            head[i] = first + 1
            rel[i] = "parataxis"
        if not roots:
            head[0], rel[0] = 0, "root"
        truncated = not all(analyzed)
        warning = (
            (
                f"partial neural analysis: {sum(analyzed)} of {n} tokens fit the "
                f"{self.max_subwords}-subword model limit; tokens marked analyzed=False "
                "carry placeholders, not predictions"
            ),
        ) if truncated else ()
        return SentenceAnalysis(
            tokens=tuple(forms), upos=tuple(upos), xpos=tuple(xpos),
            feats=tuple(feats_from_xpos(x) for x in xpos),
            head=tuple(head), deprel=tuple(rel), lemma=tuple(lemma),
            lemma_resolved=tuple(resolved),
            upos_prob=tuple(upos_prob) if calibration is not None else (),
            lemma_script_prob=tuple(lemma_prob) if calibration is not None else (),
            lemma_source=tuple(lemma_source),
            lemma_verified=tuple(verified),
            analyzed=tuple(analyzed),
            complete=not truncated,
            truncated=truncated,
            warnings=warning,
            receipt=self._receipt(
                input_tokens=n, analyzed_tokens=sum(analyzed), truncated=truncated
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
) -> SentenceAnalysis:
    """The full joint analysis of one pre-tokenized sentence (raises if not active).

    ``with_probs=True`` additionally fills the calibrated confidence fields and requires
    a loaded calibration. ``long_input`` is strict by default; partial mode returns
    explicit coverage status and warnings, while windowed mode reconciles complete-word
    overlap windows with one global observed-arc tree (see `_JointModel.analyze`)."""
    model = active()
    if model is None:
        raise NeuralPipelineNotLoadedError(
            "neural pipeline not loaded — call aegean.greek.use_neural_pipeline() first"
        )
    # Keep the default call byte-identical to the historical signature (positional
    # ``words`` only), so existing callers and test stubs are unaffected; only a
    # confidence request threads the keyword through.
    if with_probs or long_input != "strict":
        return model.analyze(words, with_probs=with_probs, long_input=long_input)
    return model.analyze(words)


def analyze_sentences(
    sentences: Iterable[list[str]],
    *,
    batch_size: int | None = None,
    with_probs: bool = False,
    long_input: LongInputMode = "strict",
) -> list[SentenceAnalysis]:
    """Full joint analyses of several pre-tokenized sentences (raises if not active).

    ``batch_size=None`` (the default) analyzes each sentence with its own encoder pass —
    identical to calling `analyze_sentence` in a loop, and the code path the published
    benchmark numbers are measured on (plain CPU, ``CPUExecutionProvider``). A positive
    int runs padded chunks of that many sentences through the encoder (one ONNX call per
    chunk), a throughput convenience producing the same analyses; batched matmuls can
    reorder float reductions, so it is never used for the recorded protocol. ``with_probs``
    behaves as in `analyze_sentence` (calibration required). Strict and partial modes
    apply independently per sentence; windowed mode is always sequential, so batch
    chunking cannot change owner or global-tree reconciliation."""
    model = active()
    if model is None:
        raise NeuralPipelineNotLoadedError(
            "neural pipeline not loaded — call aegean.greek.use_neural_pipeline() first"
        )
    sents = [list(s) for s in sentences]
    if batch_size is None:
        if with_probs or long_input != "strict":
            return [
                model.analyze(s, with_probs=with_probs, long_input=long_input) for s in sents
            ]
        return [model.analyze(s) for s in sents]
    if batch_size < 1:
        raise ValueError(f"batch_size must be a positive integer, got {batch_size!r}")
    out: list[SentenceAnalysis] = []
    for start in range(0, len(sents), batch_size):
        chunk = sents[start : start + batch_size]
        # Keep the default call byte-identical to the historical signature (positional
        # ``batch`` only), so existing callers and test spies are unaffected; only a
        # confidence request threads the keyword through.
        out.extend(
            model.analyze_batch(
                chunk, with_probs=with_probs, long_input=long_input
            )
            if with_probs or long_input != "strict"
            else model.analyze_batch(chunk)
        )
    return out


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
