"""Fast optional-dependency contracts retained in the ordinary full suite."""

from __future__ import annotations

import builtins
from collections.abc import Callable
from typing import Any

import pytest

from aegean.greek.ud import UDDocument, UDSentence, UDToken
from aegean.io._interop_cltk import to_cltk
from aegean.io._interop_spacy import to_spacy
from aegean.io._interop_stanza import to_stanza
from aegean.io.interop import InteropDependencyError, InteropDocument


def _document() -> InteropDocument:
    token = UDToken(1, "λόγος", "λόγος", "NOUN", "_", "_", 0, "root")
    return InteropDocument(UDDocument((UDSentence("s1", "λόγος", (token,)),)))


@pytest.mark.parametrize(
    ("module", "extra", "adapter"),
    [
        ("spacy", "spacy", to_spacy),
        ("stanza", "stanza", to_stanza),
        ("cltk", "cltk", to_cltk),
    ],
)
def test_missing_framework_has_exact_install_hint(
    monkeypatch: pytest.MonkeyPatch,
    module: str,
    extra: str,
    adapter: Callable[[InteropDocument], Any],
) -> None:
    original = builtins.__import__

    def blocked(name: str, *args: object, **kwargs: object) -> Any:
        if name == module or name.startswith(f"{module}."):
            raise ModuleNotFoundError(name)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(
        InteropDependencyError,
        match=rf"pip install 'pyaegean\[{extra}\]'",
    ):
        adapter(_document())


def test_real_framework_suites_are_opt_in(pytestconfig: pytest.Config) -> None:
    addopts = " ".join(pytestconfig.getini("addopts"))
    assert "not framework_interop" in addopts
    assert any(
        marker.startswith("framework_interop:")
        for marker in pytestconfig.getini("markers")
    )
