"""Shared ONNX Runtime execution-provider selection for the neural backends.

Both neural sessions (the joint pipeline in `aegean.greek.joint` and the GreTa
lemmatizer in `aegean.greek.neural_lemmatizer`) build their ``InferenceSession``
through `resolve_providers`, so provider policy — the ``PYAEGEAN_ORT_PROVIDERS``
override, GPU auto-detection, the CPU fallback — cannot drift between them.

The published benchmark numbers (``docs/benchmarks.md``) are measured on CPU
(``CPUExecutionProvider``); GPU execution is a throughput convenience only. The
shipped models are int8-quantized, and quantized ops may partition only partially
onto a GPU provider (onnxruntime assigns the unsupported nodes back to CPU).
"""

from __future__ import annotations

import os

__all__ = ["resolve_providers"]

_ENV = "PYAEGEAN_ORT_PROVIDERS"

# Auto-detect preference order. TensorrtExecutionProvider is deliberately absent:
# CUDA wheels list it even when no usable TensorRT install exists, so it is only
# ever selected through an explicit PYAEGEAN_ORT_PROVIDERS override.
_PREFERRED = ("CUDAExecutionProvider", "DmlExecutionProvider")
_CPU = "CPUExecutionProvider"


def resolve_providers() -> list[str]:
    """The ONNX Runtime execution providers a neural session should use.

    ``PYAEGEAN_ORT_PROVIDERS`` (comma-separated provider names, e.g.
    ``CUDAExecutionProvider,CPUExecutionProvider``) is exact user intent: each name
    is validated against the installed onnxruntime's available providers and the
    list is passed through as given — nothing is appended, so naming a GPU provider
    without ``CPUExecutionProvider`` runs GPU-only. An unknown or unavailable name,
    or a value that names no providers at all, raises ``ValueError`` listing what
    this install offers (instead of a cryptic onnxruntime failure later).

    Without the override, auto-detect: prefer ``CUDAExecutionProvider``, then
    ``DmlExecutionProvider`` (DirectML) when available, always ending with
    ``CPUExecutionProvider`` as the fallback. ``TensorrtExecutionProvider`` is never
    auto-selected. On a plain CPU wheel this resolves to exactly
    ``["CPUExecutionProvider"]`` — the configuration every published benchmark
    number is measured on; GPU execution is a throughput convenience, and the
    int8-quantized models may partition only partially onto a GPU provider."""
    import onnxruntime as ort  # the [neural] extra; lazy so `import aegean` stays clean

    available = list(ort.get_available_providers())
    override = os.environ.get(_ENV)
    if override is not None:
        wanted = [p.strip() for p in override.split(",") if p.strip()]
        if not wanted:
            raise ValueError(
                f"{_ENV} is set but names no providers; "
                f"available providers: {', '.join(available)}"
            )
        unknown = [p for p in wanted if p not in available]
        if unknown:
            raise ValueError(
                f"{_ENV} requests execution provider(s) not available in this "
                f"onnxruntime install: {', '.join(unknown)}; "
                f"available providers: {', '.join(available)}"
            )
        return wanted
    out = [p for p in _PREFERRED if p in available]
    if _CPU not in out:
        out.append(_CPU)
    return out
