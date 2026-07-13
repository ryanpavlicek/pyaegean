"""Neural Greek lemmatizer — the opt-in ``[neural]`` backend.

A fine-tuned **GreTa** (Ancient-Greek T5) seq2seq that *generates* the lemma of an unseen
form — the high-accuracy counterpart to the pure-Python edit-tree lemmatizer
(`aegean.greek.lemmatizer`). On the leakage-free held-out AGDT split it reaches **76.3%
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

import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING

from ..data import fetch, load_gzip_json
from . import _ort

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
    """Raised when the neural lemmatizer is used before `use_neural_lemmatizer`,
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
        # Provider policy lives in one place (_ort.resolve_providers): the published
        # numbers are measured on CPU; a GPU provider is a throughput convenience.
        # (Resolve providers before the sessions so a bad PYAEGEAN_ORT_PROVIDERS value
        # surfaces its own ValueError, not the "model corrupt" message below.)
        prov = _ort.resolve_providers()
        model_path = model_dir / "encoder_model.onnx"
        try:
            self._enc = ort.InferenceSession(str(model_path), opts, providers=prov)
            model_path = model_dir / "decoder_model.onnx"
            self._dec = ort.InferenceSession(str(model_path), opts, providers=prov)
        except Exception as e:
            # A corrupt/truncated encoder or decoder .onnx (an interrupted extract, disk
            # corruption, or a legacy pre-0.29 extract cache that fetch() trusts without
            # re-hashing) makes onnxruntime raise a bare parse error naming nothing
            # actionable; say what it is and how to re-fetch, mirroring the tokenizer wrapper.
            raise NeuralLemmatizerNotLoadedError(
                f"could not load the neural lemmatizer model at {model_path} "
                f"(onnxruntime: {e}) — the cached model looks corrupt or incompletely "
                f"downloaded. Re-fetch it: run `aegean data remove {_DATASET}` and retry, "
                f"or call use_neural_lemmatizer(force=True)."
            ) from e
        self._dec_in = {i.name for i in self._dec.get_inputs()}
        try:
            self._tok = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        except Exception as e:
            # an old tokenizers release fails on the shipped tokenizer.json format with a
            # bare Rust serde error that names nothing actionable; say what fixes it.
            raise NeuralLemmatizerNotLoadedError(
                "could not load the model's tokenizer.json — usually an outdated "
                "tokenizers package: pip install 'tokenizers>=0.20'"
            ) from e
        self._lookup: Mapping[str, str] = load_gzip_json(model_dir / "lookup.json.gz")

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


def _require_neural_extra() -> None:
    """Probe the ``[neural]`` extra BEFORE fetching, so a user who never installed it is
    told to ``pip install 'pyaegean[neural]'`` rather than to retry a download.

    The same import guard lives in `_NeuralModel.__init__`, but that runs only after
    `fetch` succeeds — on a fresh machine with no cached model the missing-extra message
    would otherwise be unreachable (a missing model would surface as a network/fetch error
    first). Extra presence is a cheap, purely-local fact, so this check is free."""
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        from tokenizers import Tokenizer  # noqa: F401
    except ModuleNotFoundError as e:
        raise NeuralLemmatizerNotLoadedError(
            "the neural backend needs the optional dependencies: "
            "pip install 'pyaegean[neural]'"
        ) from e


def use_neural_lemmatizer(*, force: bool = False) -> None:
    """Activate the neural (GreTa seq2seq) lemmatizer.

    Fetches the model bundle (ONNX encoder/decoder + tokenizer + gold lookup) to the cache on
    first use — never bundled in the wheel — then loads it via onnxruntime. Requires the
    ``[neural]`` extra (``pip install 'pyaegean[neural]'``). Best paired with
    `aegean.greek.use_treebank`, whose attested lemmas take precedence for seen forms.

    Raises `NeuralLemmatizerNotLoadedError` if the optional dependencies are missing
    (checked before any download), and `aegean.data.DataNotAvailableError` if the model URL
    is not yet pinned (set ``PYAEGEAN_GRC_LEMMA_NEURAL_URL`` to fetch from your own mirror)
    or the download fails.
    """
    global _ACTIVE
    _require_neural_extra()
    model_dir = fetch(_DATASET, force=force)
    _ACTIVE = _NeuralModel(model_dir)


def disable_neural_lemmatizer() -> None:
    """Deactivate the neural lemmatizer; the cascade falls back to the edit-tree/seed/identity."""
    global _ACTIVE
    _ACTIVE = None


def active() -> _NeuralModel | None:
    """The active neural model, or ``None`` (the default)."""
    from .runtime import _legacy_backends_allowed

    if not _legacy_backends_allowed():
        return None
    return _ACTIVE


def predict(form: str) -> str:
    """Lemmatize a form with the active neural model (raises if none is active)."""
    if _ACTIVE is None:
        raise NeuralLemmatizerNotLoadedError(
            "neural lemmatizer not loaded — call aegean.greek.use_neural_lemmatizer() first"
        )
    return _ACTIVE.predict(form)
