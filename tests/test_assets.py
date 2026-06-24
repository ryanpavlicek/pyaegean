"""The asset-integrity check (scripts/check_assets.py) probes every pinned remote
asset. These tests are offline: they verify the check's *registry* stays in sync
with the real data layer, without touching the network (the live URL probe runs on
a schedule in .github/workflows/assets.yml)."""

from __future__ import annotations

import importlib.util
import pathlib


def _load_check_assets():  # type: ignore[no-untyped-def]
    path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "check_assets.py"
    spec = importlib.util.spec_from_file_location("check_assets", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_release_assets_cover_every_pinned_remote():
    ca = _load_check_assets()
    from aegean.data import _REMOTE, _resolve_url

    checked = {name for name, _, _ in ca.release_assets()}
    expected = {name for name, spec in _REMOTE.items() if _resolve_url(spec)}
    # every remote dataset that has a pinned URL is probed; bring-your-own (no URL) is skipped
    assert checked == expected and checked


def test_release_asset_urls_and_hashes_well_formed():
    ca = _load_check_assets()
    for name, url, sha in ca.release_assets():
        assert url.startswith("https://github.com/"), name
        assert len(sha) == 64, f"{name} should carry a pinned sha256"


def test_upstream_repos_are_github_urls():
    ca = _load_check_assets()
    assert ca._UPSTREAM_REPOS
    assert all(u.startswith("https://github.com/") for u in ca._UPSTREAM_REPOS.values())


def test_no_network_in_registry_helpers(monkeypatch):
    # release_assets() must be pure registry reads — guard against an accidental fetch.
    import urllib.request

    def _boom(*a, **k):  # pragma: no cover - only fires on regression
        raise AssertionError("release_assets() must not hit the network")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    ca = _load_check_assets()
    assert ca.release_assets()
