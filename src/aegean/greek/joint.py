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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..data import fetch
from .mst import decode_mst
from .udfeats import feats_from_xpos

__all__ = [
    "NeuralPipelineNotLoadedError",
    "SentenceAnalysis",
    "active",
    "analyze_sentence",
    "disable_neural_pipeline",
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


def _compose_lemma(form: str, upos: str, script_id: int, model: "_JointModel") -> str:
    """The dev-preferred ``lookup-first`` composition: (form|UPOS) lookup → form lookup
    → predicted edit script → lowercase lookup → the form itself."""
    looked = model.lookup_form_upos.get(f"{form}|{upos}") or model.lookup_form.get(form)
    if looked:
        return looked
    if 0 <= script_id < len(model.trees):
        from .lemmatizer import apply_tree

        applied = apply_tree(model.trees[script_id], form)
        if applied:
            return applied
    return model.lookup_lower.get(form.lower()) or form


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
        self._sess = ort.InferenceSession(
            str(model_dir / "model.onnx"), opts, providers=["CPUExecutionProvider"]
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

    def _run(self, words: list[str]) -> dict[str, Any]:
        """One encoder pass over a pre-tokenized sentence → raw arrays + word bookkeeping."""
        np = self._np
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

    def analyze(self, words: list[str]) -> SentenceAnalysis:
        forms = [unicodedata.normalize("NFC", w) for w in words]
        n = len(forms)
        if n == 0:
            return SentenceAnalysis((), (), (), (), (), (), ())
        out = self._run(forms)
        word_pos: list[int] = out["_word_pos"]
        kept: list[int] = out["_kept"]
        nw = len(kept)

        upos = ["X"] * n
        xpos = ["---------"] * n
        head = [0 if i == 0 else 1 for i in range(n)]
        rel = ["root" if i == 0 else "dep" for i in range(n)]
        lemma = list(forms)

        if nw:
            heads_w = decode_mst(out["arc"][0, :nw, : nw + 1])
            rel_scores = out["rel"][0]                      # [R, W, W+1]
            lem_ids = out["lemma"][0].argmax(-1)            # [W]
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
                lemma[w] = _compose_lemma(forms[w], upos[w], int(lem_ids[wi]), self)
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
        )


_ACTIVE: _JointModel | None = None


def use_neural_pipeline(*, force: bool = False) -> None:
    """Activate the neural pipeline (tags + morphology + trees + lemmas, one model).

    Fetches the model bundle to the cache on first use — never bundled in the wheel —
    then loads it via onnxruntime. Requires the ``[neural]`` extra
    (``pip install 'pyaegean[neural]'``). Once active, `aegean.greek.pos_tags` /
    `pos_tag`, `aegean.greek.parse` (UD relations), and `aegean.greek.lemmatize`
    all use it; `analyze_sentence` returns the full joint analysis in one call.

    Raises `aegean.data.DataNotAvailableError` if the download fails (set
    ``PYAEGEAN_GRC_JOINT_URL`` to fetch from your own mirror), and
    `NeuralPipelineNotLoadedError` if the optional dependencies are missing."""
    global _ACTIVE
    model_dir = fetch(_DATASET, force=force)
    _ACTIVE = _JointModel(model_dir)


def disable_neural_pipeline() -> None:
    """Deactivate the neural pipeline; every function falls back to its prior cascade."""
    global _ACTIVE
    _ACTIVE = None


def active() -> _JointModel | None:
    """The active joint model, or ``None`` (the default)."""
    return _ACTIVE


def analyze_sentence(words: list[str]) -> SentenceAnalysis:
    """The full joint analysis of one pre-tokenized sentence (raises if not active)."""
    if _ACTIVE is None:
        raise NeuralPipelineNotLoadedError(
            "neural pipeline not loaded — call aegean.greek.use_neural_pipeline() first"
        )
    return _ACTIVE.analyze(words)
