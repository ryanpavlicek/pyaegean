"""Offline tests for the neural-lemmatizer cascade integration.

The heavy ONNX inference path is exercised only locally (like the treebank/lemmatizer model
tests) — it needs a fetched model and the ``[neural]`` extra. Here we stub the active model to
verify routing, knownness, the activation error, and that ``import aegean`` stays clean.
"""
from __future__ import annotations

import sys

import pytest

from aegean.greek import neural_lemmatizer as nl
from aegean.greek.lemmatize import lemmatize_verbose


class _Stub:
    """A stand-in for a loaded model: maps a few forms, echoes anything else."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []

    def predict(self, form: str) -> str:
        self.calls.append(form)
        return self.mapping.get(form, form)


@pytest.fixture(autouse=True)
def _reset() -> None:
    nl.disable_neural_lemmatizer()
    yield
    nl.disable_neural_lemmatizer()


def test_predict_before_activation_raises() -> None:
    assert nl.active() is None
    with pytest.raises(nl.NeuralLemmatizerNotLoadedError):
        nl.predict("λόγου")


def test_cascade_routes_to_neural_for_unseen() -> None:
    nl._ACTIVE = _Stub({"νόμου": "νόμος"})  # type: ignore[assignment]
    lemma, known = lemmatize_verbose("νόμου")
    assert lemma == "νόμος"
    assert known is True
    assert nl._ACTIVE.calls == ["νόμου"]  # type: ignore[union-attr]


def test_neural_identity_is_unknown() -> None:
    # A prediction equal to the (normalized) form is an honest "unknown" (identity fall-through),
    # matching the seed-table contract.
    nl._ACTIVE = _Stub({})  # type: ignore[assignment]
    lemma, known = lemmatize_verbose("λόγος")
    assert lemma == "λόγος"
    assert known is False


def test_disable_resets() -> None:
    nl._ACTIVE = _Stub({})  # type: ignore[assignment]
    nl.disable_neural_lemmatizer()
    assert nl.active() is None
    with pytest.raises(nl.NeuralLemmatizerNotLoadedError):
        nl.predict("x")


def test_import_stays_clean() -> None:
    # Activating the backend is what pulls onnxruntime/tokenizers; merely importing must not.
    # Probed in a subprocess so the check is order-independent under parallel test workers
    # (an in-process sys.modules assertion depends on what ran earlier in the same worker).
    import subprocess

    probe = (
        "import sys; import aegean; import aegean.greek; "
        "assert 'onnxruntime' not in sys.modules, 'onnxruntime leaked'; "
        "assert 'tokenizers' not in sys.modules, 'tokenizers leaked'"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
