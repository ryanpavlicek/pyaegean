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
from typing import Any

from ..data import fetch
from . import _ort
from .mst import decode_mst
from .udfeats import feats_from_xpos

__all__ = [
    "NeuralPipelineNotLoadedError",
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
_MAX_LEN = 256


class NeuralPipelineNotLoadedError(RuntimeError):
    """Raised when the neural pipeline is used before `use_neural_pipeline`, or when
    the ``[neural]`` extra (onnxruntime/tokenizers/numpy) is not installed."""


@dataclass(frozen=True, slots=True)
class SentenceAnalysis:
    """The joint model's full analysis of one sentence (parallel, per-token lists)."""

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


def _compose_lemma(
    form: str, upos: str, script_id: int, model: "_JointModel"
) -> tuple[str, bool]:
    """The dev-preferred ``lookup-first`` composition, with an honesty flag: returns
    ``(lemma, resolved)``. ``resolved`` is True when a real analysis was found — a
    (form|UPOS) or form lookup, a predicted non-identity edit script, or a lowercase
    lookup — and False for the identity fall-through (the form itself). A lemma that
    equals the surface form is still ``resolved=True`` when it came from a lookup (a
    nominative singular is a genuine analysis), so callers must not infer the source
    from a string compare."""
    looked = model.lookup_form_upos.get(f"{form}|{upos}") or model.lookup_form.get(form)
    if looked:
        return looked, True
    if 0 <= script_id < len(model.trees):
        from .lemmatizer import apply_tree

        applied = apply_tree(model.trees[script_id], form)
        # Two edit-script outputs are never a grounded lemma: the literal "_" (a CoNLL-U
        # empty-LEMMA placeholder that leaked into the training scripts) and the surface
        # form unchanged (the identity script — an out-of-vocabulary form the model just
        # kept; a GENUINE identity lemma, a nominative, comes from the lookups above and
        # stays resolved). Both fall through to the remaining lookups / honest identity.
        if applied and applied != "_" and applied != form:
            return applied, True
    low = model.lookup_lower.get(form.lower())
    if low:
        return low, True
    return form, False


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


class _JointModel:
    """A loaded joint ONNX model + tokenizer + label maps + lemma scripts/lookup."""

    def __init__(self, model_dir: Path) -> None:
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
        per kept word, kept word indices)``. Truncation to ``_MAX_LEN`` happens here, so
        the single and batched passes share the same kept/fallback bookkeeping."""
        enc = self._tok.encode(words, is_pretokenized=True)
        ids = enc.ids[:_MAX_LEN]
        word_ids = enc.word_ids[: len(ids)]
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

    def analyze(self, words: list[str], *, with_probs: bool = False) -> SentenceAnalysis:
        """Analyze one pre-tokenized sentence.

        ``with_probs=False`` (the default) is the historical path, byte-identical to
        before this feature — ``upos_prob`` / ``lemma_script_prob`` stay empty ``()``.
        ``with_probs=True`` fills them with calibrated top-1 confidences, and REQUIRES a
        loaded calibration (`aegean.greek.use_calibration`): with none loaded it raises
        `UncalibratedConfidenceError` rather than exposing a raw softmax."""
        calibration = _probs_calibration(with_probs)
        forms = [unicodedata.normalize("NFC", w) for w in words]
        if not forms:
            return SentenceAnalysis((), (), (), (), (), (), (), ())
        return self._decode(forms, self._run(forms), calibration=calibration)

    def analyze_batch(
        self, sentences: list[list[str]], *, with_probs: bool = False
    ) -> list[SentenceAnalysis]:
        """Analyses of several sentences, one padded encoder pass per call.

        Produces the same fields as ``[self.analyze(s) for s in sentences]`` — empty
        sentences and the truncation fallbacks included; only the number of ONNX calls
        differs. Sequential per-sentence analysis is the recorded benchmark protocol
        (see `_run_batch` on float reduction order); batching is a throughput
        convenience. ``with_probs`` behaves as in `analyze` (calibration required)."""
        calibration = _probs_calibration(with_probs)
        norm = [[unicodedata.normalize("NFC", w) for w in words] for words in sentences]
        out: list[SentenceAnalysis] = [
            SentenceAnalysis((), (), (), (), (), (), (), ()) for _ in norm
        ]
        live = [i for i, forms in enumerate(norm) if forms]
        if live:
            for i, res in zip(live, self._run_batch([norm[i] for i in live])):
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
                sp = word_pos[wi]
                upos[w] = self.inv["upos"][int(out["upos"][0, sp].argmax())]
                xpos[w] = "".join(
                    self.inv[f"x{i}"][int(out[f"x{i}"][0, sp].argmax())] for i in range(9)
                )
                head[w] = heads_w[wi]
                rel[w] = self.inv["deprel"][int(rel_scores[:, wi, heads_w[wi]].argmax())]
                if head[w] == 0:
                    rel[w] = "root"
                lemma[w], resolved[w] = _compose_lemma(forms[w], upos[w], int(lem_ids[wi]), self)
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
        return SentenceAnalysis(
            tokens=tuple(forms), upos=tuple(upos), xpos=tuple(xpos),
            feats=tuple(feats_from_xpos(x) for x in xpos),
            head=tuple(head), deprel=tuple(rel), lemma=tuple(lemma),
            lemma_resolved=tuple(resolved),
            upos_prob=tuple(upos_prob) if calibration is not None else (),
            lemma_script_prob=tuple(lemma_prob) if calibration is not None else (),
        )


_ACTIVE: _JointModel | None = None


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


def use_neural_pipeline(*, force: bool = False) -> None:
    """Activate the neural pipeline (tags + morphology + trees + lemmas, one model).

    Fetches the model bundle to the cache on first use — never bundled in the wheel —
    then loads it via onnxruntime. Requires the ``[neural]`` extra
    (``pip install 'pyaegean[neural]'``). Once active, `aegean.greek.pos_tags` /
    `pos_tag`, `aegean.greek.parse` (UD relations), and `aegean.greek.lemmatize`
    all use it; `analyze_sentence` returns the full joint analysis in one call.

    Raises `NeuralPipelineNotLoadedError` if the optional dependencies are missing
    (checked before any download), and `aegean.data.DataNotAvailableError` if the
    download fails (set ``PYAEGEAN_GRC_JOINT_URL`` to fetch from your own mirror)."""
    global _ACTIVE
    _require_neural_extra()
    model_dir = fetch(_DATASET, force=force)
    _ACTIVE = _JointModel(model_dir)


def disable_neural_pipeline() -> None:
    """Deactivate the neural pipeline; every function falls back to its prior cascade."""
    global _ACTIVE
    _ACTIVE = None


def active() -> _JointModel | None:
    """The active joint model, or ``None`` (the default)."""
    return _ACTIVE


def analyze_sentence(words: list[str], *, with_probs: bool = False) -> SentenceAnalysis:
    """The full joint analysis of one pre-tokenized sentence (raises if not active).

    ``with_probs=True`` additionally fills the calibrated confidence fields and requires
    a loaded calibration (see `_JointModel.analyze`)."""
    if _ACTIVE is None:
        raise NeuralPipelineNotLoadedError(
            "neural pipeline not loaded — call aegean.greek.use_neural_pipeline() first"
        )
    # Keep the default call byte-identical to the historical signature (positional
    # ``words`` only), so existing callers and test stubs are unaffected; only a
    # confidence request threads the keyword through.
    if with_probs:
        return _ACTIVE.analyze(words, with_probs=True)
    return _ACTIVE.analyze(words)


def analyze_sentences(
    sentences: Iterable[list[str]], *, batch_size: int | None = None, with_probs: bool = False
) -> list[SentenceAnalysis]:
    """Full joint analyses of several pre-tokenized sentences (raises if not active).

    ``batch_size=None`` (the default) analyzes each sentence with its own encoder pass —
    identical to calling `analyze_sentence` in a loop, and the code path the published
    benchmark numbers are measured on (plain CPU, ``CPUExecutionProvider``). A positive
    int runs padded chunks of that many sentences through the encoder (one ONNX call per
    chunk), a throughput convenience producing the same analyses; batched matmuls can
    reorder float reductions, so it is never used for the recorded protocol. ``with_probs``
    behaves as in `analyze_sentence` (calibration required)."""
    if _ACTIVE is None:
        raise NeuralPipelineNotLoadedError(
            "neural pipeline not loaded — call aegean.greek.use_neural_pipeline() first"
        )
    sents = [list(s) for s in sentences]
    if batch_size is None:
        if with_probs:
            return [_ACTIVE.analyze(s, with_probs=True) for s in sents]
        return [_ACTIVE.analyze(s) for s in sents]
    if batch_size < 1:
        raise ValueError(f"batch_size must be a positive integer, got {batch_size!r}")
    out: list[SentenceAnalysis] = []
    for start in range(0, len(sents), batch_size):
        chunk = sents[start : start + batch_size]
        # Keep the default call byte-identical to the historical signature (positional
        # ``batch`` only), so existing callers and test spies are unaffected; only a
        # confidence request threads the keyword through.
        out.extend(
            _ACTIVE.analyze_batch(chunk, with_probs=True)
            if with_probs
            else _ACTIVE.analyze_batch(chunk)
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
    if _ACTIVE is not None:
        active_providers = list(_ACTIVE._sess.get_providers())
    return {
        "model": _DATASET,
        "available_providers": available,
        "active_providers": active_providers,
    }
