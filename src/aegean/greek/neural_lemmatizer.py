"""Neural Greek lemmatizer — the opt-in ``[neural]`` backend.

A fine-tuned **GreTa** (Ancient-Greek T5) seq2seq that *generates* the lemma of an unseen
form — the high-accuracy counterpart to the pure-Python edit-tree lemmatizer
(:mod:`aegean.greek.lemmatizer`). On the leakage-free held-out AGDT split it reaches **76.3%
on unseen forms**.

It is the unseen-form tier of a **hybrid**: a bundled gold ``form → lemma`` lookup answers
*seen* forms exactly (in AGDT's orthographic convention), and the seq2seq handles the rest —
so the model is consulted only where generation actually wins.

Inference needs ``onnxruntime`` + ``tokenizers`` (the
``[neural]`` extra); these are imported only when the backend is activated, so ``import
aegean`` stays instant and dependency-free. **torch is not required** — decoding is a numpy
greedy loop over the ONNX encoder/decoder sessions. The model (ONNX + tokenizer + lookup) is
fetched-to-cache on first use, never bundled. It is derived from CC BY-SA corpora (AGDT,
Pedalion, Gorman) so the *model* ships under CC BY-SA; the wheel stays Apache-2.0 because the
model is fetched, not bundled.
"""

from __future__ import annotations

import gzip
import json
import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING

from ..data import fetch

if TYPE_CHECKING:  # heavy types, never imported at runtime-base
    from collections.abc import Mapping

__all__ = [
    "NeuralLemmatizerNotLoadedError",
    "active",
    "disable_neural_lemmatizer",
    "predict",
    "use_neural_lemmatizer",
]

# Registered in aegean.data._REMOTE; fetched + extracted to the cache on first use.
_DATASET = "grc-lemma-neural"
_MAX_LEN = 32
_PAD_ID, _EOS_ID = 0, 1  # GreTa/T5: decoder starts at pad, stops at eos


class NeuralLemmatizerNotLoadedError(RuntimeError):
    """Raised when the neural lemmatizer is used before :func:`use_neural_lemmatizer`,
    or when the ``[neural]`` extra (onnxruntime/tokenizers) is not installed."""


def _clean(s: str) -> str:
    """Match the training target convention: NFC, trailing homonym digits dropped."""
    return re.sub(r"\d+$", "", unicodedata.normalize("NFC", s))


class _NeuralModel:
    """A loaded ONNX seq2seq + tokenizer + gold lookup. Torch-free (numpy + onnxruntime)."""

    def __init__(self, model_dir: Path) -> None:
        try:
            import numpy as np
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ModuleNotFoundError as e:  # pragma: no cover - import guard
            raise NeuralLemmatizerNotLoadedError(
                "the neural backend needs the optional dependencies: "
                "pip install 'pyaegean[neural]'"
            ) from e
        self._np = np
        opts = ort.SessionOptions()
        opts.log_severity_level = 3  # quiet
        prov = ["CPUExecutionProvider"]
        self._enc = ort.InferenceSession(str(model_dir / "encoder_model.onnx"), opts, providers=prov)
        self._dec = ort.InferenceSession(str(model_dir / "decoder_model.onnx"), opts, providers=prov)
        self._dec_in = {i.name for i in self._dec.get_inputs()}
        self._tok = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        with gzip.open(model_dir / "lookup.json.gz", "rt", encoding="utf-8") as f:
            self._lookup: Mapping[str, str] = json.load(f)

    def _generate(self, form: str) -> str:
        """Greedy-decode the lemma for one form (torch-free)."""
        np = self._np
        ids = np.array([self._tok.encode(form).ids[:_MAX_LEN]], dtype=np.int64)
        mask = np.ones_like(ids)
        hidden = self._enc.run(None, {"input_ids": ids, "attention_mask": mask})[0]
        dec = np.array([[_PAD_ID]], dtype=np.int64)  # T5 decoder_start_token_id
        for _ in range(_MAX_LEN):
            feed = {"input_ids": dec, "encoder_hidden_states": hidden,
                    "encoder_attention_mask": mask}
            logits = self._dec.run(None, {k: v for k, v in feed.items() if k in self._dec_in})[0]
            nxt = int(logits[0, -1].argmax())
            if nxt == _EOS_ID:
                break
            dec = np.concatenate([dec, [[nxt]]], axis=1)
        return str(self._tok.decode([int(t) for t in dec[0, 1:]], skip_special_tokens=True))

    def predict(self, form: str) -> str:
        """Lemma of ``form``: the gold lookup if the form is attested (seen), else generate."""
        nf = unicodedata.normalize("NFC", form)
        hit = self._lookup.get(nf)
        if hit is not None:
            return hit
        return _clean(self._generate(nf)) or nf


_ACTIVE: _NeuralModel | None = None


def use_neural_lemmatizer(*, force: bool = False) -> None:
    """Activate the neural (GreTa seq2seq) lemmatizer.

    Fetches the model bundle (ONNX encoder/decoder + tokenizer + gold lookup) to the cache on
    first use — never bundled in the wheel — then loads it via onnxruntime. Requires the
    ``[neural]`` extra (``pip install 'pyaegean[neural]'``). Best paired with
    :func:`aegean.greek.use_treebank`, whose attested lemmas take precedence for seen forms.

    Raises :class:`aegean.data.DataNotAvailableError` if the model URL is not yet pinned (set
    ``PYAEGEAN_GRC_LEMMA_NEURAL_URL`` to fetch from your own mirror) or the download fails, and
    :class:`NeuralLemmatizerNotLoadedError` if the optional dependencies are missing.
    """
    global _ACTIVE
    model_dir = fetch(_DATASET, force=force)
    _ACTIVE = _NeuralModel(model_dir)


def disable_neural_lemmatizer() -> None:
    """Deactivate the neural lemmatizer; the cascade falls back to the edit-tree/seed/identity."""
    global _ACTIVE
    _ACTIVE = None


def active() -> _NeuralModel | None:
    """The active neural model, or ``None`` (the default)."""
    return _ACTIVE


def predict(form: str) -> str:
    """Lemmatize a form with the active neural model (raises if none is active)."""
    if _ACTIVE is None:
        raise NeuralLemmatizerNotLoadedError(
            "neural lemmatizer not loaded — call aegean.greek.use_neural_lemmatizer() first"
        )
    return _ACTIVE.predict(form)
