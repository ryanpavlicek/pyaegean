"""The opt-in persistent analysis cache (aegean.cache): off by default, hit/miss,
fingerprinting, and the @memoize passthrough."""

from __future__ import annotations

import aegean
from aegean import cache


def setup_function():
    cache.disable()


def teardown_function():
    cache.disable()


# ── opt-in toggle ────────────────────────────────────────────────────────────


def test_disabled_by_default_and_passthrough():
    calls = {"n": 0}

    @cache.memoize()
    def f(x):
        calls["n"] += 1
        return x * 2

    assert not cache.is_enabled()
    assert f(3) == 6 and f(3) == 6
    assert calls["n"] == 2  # no caching while disabled


def test_enable_caches_across_calls(tmp_path):
    cache.enable(tmp_path / "c.sqlite")
    calls = {"n": 0}

    @cache.memoize()
    def f(x):
        calls["n"] += 1
        return [x, x + 1]

    assert f(5) == [5, 6]
    assert f(5) == [5, 6]
    assert calls["n"] == 1                 # second call served from disk
    assert cache.stats()["entries"] == 1


def test_persists_across_a_fresh_cache_object(tmp_path):
    path = tmp_path / "c.sqlite"
    cache.enable(path)
    calls = {"n": 0}

    @cache.memoize(version="1")
    def f(x):
        calls["n"] += 1
        return x * 10

    f(7)
    cache.disable()
    cache.enable(path)                     # reopen the same file
    assert f(7) == 70 and calls["n"] == 1  # still cached


def test_version_bump_invalidates(tmp_path):
    path = tmp_path / "c.sqlite"
    cache.enable(path)
    seen = []

    def make(v):
        @cache.memoize(version=v)
        def f(x):
            seen.append(v)
            return x

        return f

    make("1")(1)
    make("2")(1)                           # different version → recompute
    assert seen == ["1", "2"]


def test_unkeyable_args_compute_directly(tmp_path):
    cache.enable(tmp_path / "c.sqlite")
    calls = {"n": 0}

    @cache.memoize()
    def f(gen):
        calls["n"] += 1
        return sum(gen)

    # a generator can't be fingerprinted → no caching, but still correct
    assert f(iter([1, 2, 3])) == 6
    assert f(iter([1, 2, 3])) == 6
    assert calls["n"] == 2
    assert cache.stats()["entries"] == 0


def test_clear_and_stats(tmp_path):
    cache.enable(tmp_path / "c.sqlite")

    @cache.memoize()
    def f(x):
        return x

    f(1)
    f(2)
    assert cache.stats()["entries"] == 2
    cache.clear()
    assert cache.stats()["entries"] == 0


def test_env_opt_in(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAEGEAN_ANALYSIS_CACHE", str(tmp_path / "env.sqlite"))
    # reset the lazy env check so the new env var is consulted
    monkeypatch.setattr(cache, "_env_checked", False)
    monkeypatch.setattr(cache, "_active", None)
    assert cache.is_enabled()
    assert "env.sqlite" in cache.stats()["path"]


# ── Corpus fingerprint ───────────────────────────────────────────────────────


def test_corpus_fingerprint_stable_and_distinguishing():
    a = aegean.load("lineara")
    b = aegean.load("lineara")
    assert a.fingerprint() == b.fingerprint() == a.cache_key()
    # a different corpus differs
    assert aegean.load("linearb").fingerprint() != a.fingerprint()
    # a filtered subset differs from the whole
    assert a.filter(site="Haghia Triada").fingerprint() != a.fingerprint()


# ── memoize on a real analysis ───────────────────────────────────────────────


def test_dispersions_cached_by_corpus(tmp_path):
    cache.enable(tmp_path / "c.sqlite")
    corpus = aegean.load("lineara")
    r1 = aegean.analysis.dispersions(corpus, min_frequency=3, top=5)
    assert cache.stats()["entries"] == 1
    r2 = aegean.analysis.dispersions(corpus, min_frequency=3, top=5)
    assert r1 == r2                        # identical result, served from cache
    # different parameters → a new entry, not a stale hit
    aegean.analysis.dispersions(corpus, min_frequency=4, top=5)
    assert cache.stats()["entries"] == 2


def test_cli_cache_command(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    monkeypatch.setenv("PYAEGEAN_ANALYSIS_CACHE", str(tmp_path / "cli.sqlite"))
    monkeypatch.setattr(cache, "_env_checked", False)
    monkeypatch.setattr(cache, "_active", None)
    r = CliRunner().invoke(_build_app(), ["cache", "--json"])
    assert r.exit_code == 0, r.output
    assert '"enabled": true' in r.output
