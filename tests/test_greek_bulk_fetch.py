"""The bulk Greek-work fetch layer: list_fetched_works / fetch_works / rate-limit (offline).

No network: ``load_work`` and the GitHub listing are monkeypatched, and the cache is a tmp dir.
"""

from __future__ import annotations

import urllib.error

import pytest

from aegean.data import DataNotAvailableError, FetchAborted
from aegean.scripts.greek import perseus
from aegean.scripts.greek.perseus import (
    GitHubRateLimitError,
    fetch_works,
    list_fetched_works,
)


def _seed(tmp_path, monkeypatch):
    """Point the cache at a tmp dir with a couple of cached edition files."""
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    from aegean.data import cache_dir

    commit = cache_dir() / "greek-works" / "perseus" / "d4fab69a2c26"
    commit.mkdir(parents=True)
    (commit / "tlg0012.tlg001.perseus-grc2.xml").write_text("<TEI/>", encoding="utf-8")  # Iliad, in catalog
    (commit / "tlg9999.tlg999.perseus-grc1.xml").write_text("<TEI/>", encoding="utf-8")  # not in catalog
    (commit / "tlg0012.tlg002.perseus-grc1.xml.part").write_text("x", encoding="utf-8")  # ignored
    (cache_dir() / "greek-works" / "listings").mkdir(parents=True, exist_ok=True)  # ignored


def test_list_fetched_works_scans_cache_and_cross_references_catalog(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    by_id = {w["id"]: w for w in list_fetched_works()}
    assert by_id["tlg0012.tlg001"]["author"] == "Homer"
    assert by_id["tlg0012.tlg001"]["title"] == "Iliad"
    assert by_id["tlg0012.tlg001"]["source"] == "perseus"
    assert by_id["tlg0012.tlg001"]["bytes"] > 0
    assert "tlg9999.tlg999" in by_id  # a work absent from the catalogue still appears
    assert "tlg0012.tlg002" not in by_id  # a .part file is not a fetched work
    assert "listings" not in by_id


def test_list_fetched_works_empty_when_nothing_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    assert list_fetched_works() == []


def test_fetch_works_reports_cached_and_fetched(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)  # Iliad is cached
    calls: list[str] = []
    monkeypatch.setattr(perseus, "load_work", lambda work, **k: calls.append(work))
    works = [
        {"id": "tlg0012.tlg001", "author": "Homer", "title": "Iliad"},
        {"id": "tlg0012.tlg002", "author": "Homer", "title": "Odyssey"},
    ]
    status = {r.id: r.status for r in fetch_works(works=works)}
    assert status["tlg0012.tlg001"] == "cached"
    assert status["tlg0012.tlg002"] == "fetched"
    assert calls == ["tlg0012.tlg002"]  # only the uncached work triggered a download


def test_fetch_works_empty_author_yields_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    assert list(fetch_works(author="zzzznotanauthor")) == []


def test_fetch_works_limit_caps_new_downloads(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    monkeypatch.setattr(perseus, "load_work", lambda work, **k: None)
    works = [{"id": f"tlg0001.tlg00{i}", "author": "x", "title": "y"} for i in range(1, 6)]
    results = list(fetch_works(works=works, limit=2))
    assert sum(r.status == "fetched" for r in results) == 2


def test_fetch_works_stops_on_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))

    def boom(work, **k):
        raise GitHubRateLimitError("limited")

    monkeypatch.setattr(perseus, "load_work", boom)
    with pytest.raises(GitHubRateLimitError):
        list(fetch_works(works=[{"id": "tlg0012.tlg002", "author": "H", "title": "O"}]))


def test_fetch_works_stops_after_consecutive_failures(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))

    def boom(work, **k):
        raise DataNotAvailableError("nope")

    monkeypatch.setattr(perseus, "load_work", boom)
    works = [{"id": f"tlg0001.tlg00{i}", "author": "x", "title": "y"} for i in range(1, 6)]
    with pytest.raises(DataNotAvailableError, match="consecutive failures"):
        list(fetch_works(works=works))


def test_fetch_works_abort_between_works(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    monkeypatch.setattr(perseus, "load_work", lambda work, **k: None)
    with pytest.raises(FetchAborted):
        list(fetch_works(works=[{"id": "tlg0012.tlg002", "author": "H", "title": "O"}],
                         abort=lambda: True))


def test_github_listing_raises_rate_limit_on_403(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            "url", 403, "rate limit exceeded",
            {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "0"},  # type: ignore[arg-type]
            None,
        )

    monkeypatch.setattr(perseus.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(GitHubRateLimitError):
        perseus._github_listing("some/repo", "data/tlg0012/tlg001", "abc123def456")
