"""TLS compatibility for verified asset downloads on Python 3.14."""

from __future__ import annotations

import ssl
import urllib.request
from typing import Any

from aegean import data


def test_https_asset_context_keeps_verification_but_clears_strict(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, Any] = {}
    marker = object()

    def fake_urlopen(request: Any, **kwargs: Any) -> object:
        captured.update(kwargs)
        return marker

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert data._urlopen_verified("https://example.invalid/asset", timeout=30) is marker
    context = captured["context"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is True
    strict = getattr(ssl, "VERIFY_X509_STRICT", 0)
    if strict:
        assert not context.verify_flags & strict


def test_non_https_asset_open_does_not_receive_an_ssl_context(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    marker = object()

    def fake_urlopen(request: Any, **kwargs: Any) -> object:
        captured.update(kwargs)
        return marker

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert data._urlopen_verified("file:///tmp/asset", timeout=30) is marker
    assert captured == {"timeout": 30}
