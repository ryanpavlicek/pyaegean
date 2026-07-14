"""Execution-provider selection for the neural ONNX sessions (`aegean.greek._ort`).

Correctness: auto-detect prefers CUDA, then DirectML, never TensorRT, and always ends on
CPU; a plain CPU wheel resolves to exactly ``["CPUExecutionProvider"]`` — the published
benchmark configuration. The ``PYAEGEAN_ORT_PROVIDERS`` override is exact user intent:
validated, order-preserving, passed through as given (nothing appended). Adversarial: an
unknown provider name, or a value naming no providers, fails with one clean ``ValueError``
naming what this install offers, never a cryptic onnxruntime failure later.

All offline: onnxruntime is faked through ``sys.modules``, so these run (and mean the
same thing) with or without the ``[neural]`` extra installed."""

from __future__ import annotations

import sys
import types

import pytest

from aegean.greek import _ort, joint

_ENV = "PYAEGEAN_ORT_PROVIDERS"


def _fake_ort(monkeypatch: pytest.MonkeyPatch, available: list[str]) -> None:
    mod = types.ModuleType("onnxruntime")
    mod.get_available_providers = lambda: list(available)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "onnxruntime", mod)


# --- auto-detection ---------------------------------------------------------------


def test_plain_cpu_wheel_resolves_to_exactly_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_ENV, raising=False)
    _fake_ort(monkeypatch, ["CPUExecutionProvider"])
    assert _ort.resolve_providers() == ["CPUExecutionProvider"]


def test_cpu_wheel_extras_like_azure_are_not_auto_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # the real CPU wheel lists AzureExecutionProvider; only CPU may be auto-picked
    monkeypatch.delenv(_ENV, raising=False)
    _fake_ort(monkeypatch, ["AzureExecutionProvider", "CPUExecutionProvider"])
    assert _ort.resolve_providers() == ["CPUExecutionProvider"]


def test_auto_prefers_cuda_and_never_tensorrt(monkeypatch: pytest.MonkeyPatch) -> None:
    # a CUDA wheel lists TensorRT even when no usable TensorRT install exists
    monkeypatch.delenv(_ENV, raising=False)
    _fake_ort(
        monkeypatch,
        ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    assert _ort.resolve_providers() == ["CUDAExecutionProvider", "CPUExecutionProvider"]


def test_auto_prefers_dml_when_no_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_ENV, raising=False)
    _fake_ort(monkeypatch, ["DmlExecutionProvider", "CPUExecutionProvider"])
    assert _ort.resolve_providers() == ["DmlExecutionProvider", "CPUExecutionProvider"]


def test_auto_orders_cuda_before_dml_before_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_ENV, raising=False)
    _fake_ort(
        monkeypatch,
        ["DmlExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    assert _ort.resolve_providers() == [
        "CUDAExecutionProvider",
        "DmlExecutionProvider",
        "CPUExecutionProvider",
    ]


# --- the env override -------------------------------------------------------------


def test_override_is_validated_ordered_and_whitespace_tolerant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_ort(monkeypatch, ["CUDAExecutionProvider", "CPUExecutionProvider"])
    monkeypatch.setenv(_ENV, " CPUExecutionProvider , CUDAExecutionProvider ")
    # order preserved exactly as the user wrote it (CPU deliberately first here)
    assert _ort.resolve_providers() == ["CPUExecutionProvider", "CUDAExecutionProvider"]


def test_override_without_cpu_is_passed_through_not_padded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # an explicit override is exact user intent: CPU is NOT appended behind it
    _fake_ort(monkeypatch, ["CUDAExecutionProvider", "CPUExecutionProvider"])
    monkeypatch.setenv(_ENV, "CUDAExecutionProvider")
    assert _ort.resolve_providers() == ["CUDAExecutionProvider"]


def test_override_can_select_tensorrt_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    # never auto-selected, but an explicit request for an AVAILABLE provider is honored
    _fake_ort(monkeypatch, ["TensorrtExecutionProvider", "CPUExecutionProvider"])
    monkeypatch.setenv(_ENV, "TensorrtExecutionProvider,CPUExecutionProvider")
    assert _ort.resolve_providers() == ["TensorrtExecutionProvider", "CPUExecutionProvider"]


def test_override_unknown_provider_fails_naming_requested_and_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_ort(monkeypatch, ["CPUExecutionProvider"])
    monkeypatch.setenv(_ENV, "WarpDriveExecutionProvider")
    with pytest.raises(ValueError) as exc:
        _ort.resolve_providers()
    msg = str(exc.value)
    assert "WarpDriveExecutionProvider" in msg      # what was asked for
    assert "CPUExecutionProvider" in msg            # what this install offers
    assert _ENV in msg                              # which knob to fix


@pytest.mark.parametrize("value", ["", "   ", " , ", ",,,"])
def test_override_empty_or_whitespace_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    _fake_ort(monkeypatch, ["CPUExecutionProvider"])
    monkeypatch.setenv(_ENV, value)
    with pytest.raises(ValueError, match="names no providers"):
        _ort.resolve_providers()


# --- neural_backend_info ----------------------------------------------------------


def test_backend_info_reports_availability_without_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_ort(monkeypatch, ["CPUExecutionProvider"])
    monkeypatch.setattr(joint, "_ACTIVE", None)
    info = joint.neural_backend_info()
    assert info["model"] == "grc-joint"
    assert info["available_providers"] == ["CPUExecutionProvider"]
    assert info["active_providers"] is None  # pipeline not loaded, no crash


def test_backend_info_reads_the_live_session(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_ort(monkeypatch, ["CUDAExecutionProvider", "CPUExecutionProvider"])
    sess = types.SimpleNamespace(
        get_providers=lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"]
    )
    monkeypatch.setattr(joint, "_ACTIVE", types.SimpleNamespace(_sess=sess))
    info = joint.neural_backend_info()
    assert info["active_providers"] == ["CUDAExecutionProvider", "CPUExecutionProvider"]
    assert info["available_providers"] == ["CUDAExecutionProvider", "CPUExecutionProvider"]


def test_backend_info_survives_a_missing_neural_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # None in sys.modules makes `import onnxruntime` raise ImportError — the
    # missing-extra shape; availability must degrade to None, never crash
    monkeypatch.setitem(sys.modules, "onnxruntime", None)  # type: ignore[arg-type]
    monkeypatch.setattr(joint, "_ACTIVE", None)
    info = joint.neural_backend_info()
    assert info == {
        "model": "grc-joint",
        "available_providers": None,
        "active_providers": None,
    }


def test_backend_info_is_exported_from_the_greek_package() -> None:
    from aegean import greek

    assert "neural_backend_info" in greek.__all__
    assert greek.neural_backend_info is joint.neural_backend_info
    assert "analyze_sentences" in greek.__all__
    assert greek.analyze_sentences is joint.analyze_sentences
    assert "iter_analyze_sentences" in greek.__all__
    assert greek.iter_analyze_sentences is joint.iter_analyze_sentences
