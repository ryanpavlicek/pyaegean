"""The shared fetch-then-materialize helper ``aegean.data.fetch_text``: gunzip with a
size cap, atomic write, and a source-sha ``.sha256`` stamp with no legacy-trust
carve-out (a re-pin or a missing stamp re-materializes). Uses file:// URLs — no network."""

from __future__ import annotations

import gzip

import pytest

from aegean import data
from aegean.data import DataNotAvailableError, DataSpec, sha256_file


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))


def _make_gz(tmp_path, content: bytes, name: str = "asset.json.gz"):
    """A gzipped fixture at ``tmp_path/name`` plus the sha256 of the .gz (what fetch pins)."""
    p = tmp_path / name
    with gzip.open(p, "wb") as f:
        f.write(content)
    return p, sha256_file(p)


def _register(monkeypatch, name: str, url: str, sha: str) -> None:
    monkeypatch.setitem(
        data._REMOTE, name, DataSpec(name=name, url=url, license="test", sha256=sha)
    )


def _stamp(dest):
    return dest.with_name(dest.name + ".sha256")


def test_fresh_fetch_materializes_and_stamps(tmp_path, monkeypatch):
    gz, sha = _make_gz(tmp_path, b"line one\nline two\n")
    _register(monkeypatch, "txt", gz.as_uri(), sha)
    dest = data.cache_dir() / "out" / "materialized.txt"

    out = data.fetch_text("txt", dest)

    assert out == dest
    assert dest.read_bytes() == b"line one\nline two\n"
    assert _stamp(dest).read_text(encoding="ascii").strip() == sha  # source sha recorded


def test_unchanged_recall_serves_cached_without_rematerialize(tmp_path, monkeypatch):
    gz, sha = _make_gz(tmp_path, b"content\n")
    _register(monkeypatch, "txt", gz.as_uri(), sha)
    dest = data.cache_dir() / "out.txt"

    out = data.fetch_text("txt", dest)
    mtime = out.stat().st_mtime_ns

    assert data.fetch_text("txt", dest) == out
    assert out.stat().st_mtime_ns == mtime  # not re-written on the unchanged re-call


def test_repinned_source_rematerializes(tmp_path, monkeypatch):
    gz1, sha1 = _make_gz(tmp_path, b"v1-content\n", name="v1.gz")
    _register(monkeypatch, "txt", gz1.as_uri(), sha1)
    dest = data.cache_dir() / "out.txt"

    assert data.fetch_text("txt", dest).read_bytes() == b"v1-content\n"
    assert _stamp(dest).read_text().strip() == sha1

    # Re-pin the same dataset name to a new archive with different content + sha.
    gz2, sha2 = _make_gz(tmp_path, b"v2-content\n", name="v2.gz")
    _register(monkeypatch, "txt", gz2.as_uri(), sha2)

    assert data.fetch_text("txt", dest).read_bytes() == b"v2-content\n"  # picked up v2
    assert _stamp(dest).read_text().strip() == sha2


def test_missing_stamp_rematerializes(tmp_path, monkeypatch):
    """No legacy-trust carve-out (the contrast with fetch()'s heavy-extract path): a
    missing stamp forces a fresh materialize instead of serving whatever is at dest."""
    gz, sha = _make_gz(tmp_path, b"content\n")
    _register(monkeypatch, "txt", gz.as_uri(), sha)
    dest = data.cache_dir() / "out.txt"

    data.fetch_text("txt", dest)
    _stamp(dest).unlink()  # simulate a materialization that lost its stamp
    dest.write_bytes(b"stale copy that must not be served\n")

    assert data.fetch_text("txt", dest).read_bytes() == b"content\n"  # re-materialized
    assert _stamp(dest).read_text().strip() == sha


def test_unreadable_stamp_rematerializes(tmp_path, monkeypatch):
    gz, sha = _make_gz(tmp_path, b"content\n")
    _register(monkeypatch, "txt", gz.as_uri(), sha)
    dest = data.cache_dir() / "out.txt"

    data.fetch_text("txt", dest)
    _stamp(dest).write_bytes(b"\xff\xfe not-ascii garbage")  # unreadable as ascii
    dest.write_bytes(b"stale\n")

    assert data.fetch_text("txt", dest).read_bytes() == b"content\n"
    assert _stamp(dest).read_text(encoding="ascii").strip() == sha


def test_interrupted_write_leaves_no_partial_then_recovers(tmp_path, monkeypatch):
    gz, sha = _make_gz(tmp_path, b"full content\n")
    # Return the gz straight from fetch so the flaky os.replace bites only fetch_text's
    # atomic writes, not fetch()'s own download rename.
    monkeypatch.setattr(data, "fetch", lambda name, **kw: gz)
    dest = data.cache_dir() / "sub" / "out.txt"

    import aegean._atomic as atomic

    real_replace = atomic.os.replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("simulated crash mid-swap")
        real_replace(src, dst)

    monkeypatch.setattr(atomic.os, "replace", flaky)

    with pytest.raises(OSError):
        data.fetch_text("txt", dest)

    assert not dest.exists()  # no partial served
    assert not _stamp(dest).exists()
    if dest.parent.exists():
        assert list(dest.parent.iterdir()) == []  # no temp leaked

    # A subsequent call lands the full file atomically and stamps it.
    out = data.fetch_text("txt", dest)
    assert out == dest and out.read_bytes() == b"full content\n"
    assert _stamp(dest).read_text().strip() == sha


def test_oversized_gzip_stream_raises_clean_error(tmp_path, monkeypatch):
    gz, sha = _make_gz(tmp_path, b"x" * 5000)
    _register(monkeypatch, "txt", gz.as_uri(), sha)
    dest = data.cache_dir() / "out.txt"

    with pytest.raises(DataNotAvailableError):
        data.fetch_text("txt", dest, max_bytes=100)
    assert not dest.exists()  # nothing materialized on refusal


def test_non_gzip_passthrough(tmp_path, monkeypatch):
    src = tmp_path / "plain.txt"
    src.write_bytes(b"plain text, not compressed\n")
    sha = sha256_file(src)
    _register(monkeypatch, "plain", src.as_uri(), sha)
    dest = data.cache_dir() / "out.txt"

    out = data.fetch_text("plain", dest)

    assert out.read_bytes() == b"plain text, not compressed\n"
    assert _stamp(dest).read_text().strip() == sha


def test_non_gzip_oversized_raises_clean_error(tmp_path, monkeypatch):
    src = tmp_path / "big.txt"
    src.write_bytes(b"y" * 5000)
    sha = sha256_file(src)
    _register(monkeypatch, "big", src.as_uri(), sha)
    dest = data.cache_dir() / "out.txt"

    with pytest.raises(DataNotAvailableError):
        data.fetch_text("big", dest, max_bytes=100)
    assert not dest.exists()


def test_download_false_returns_dest_without_fetching(tmp_path):
    # An unknown dataset would raise if fetch_text tried to fetch; download=False must not.
    dest = tmp_path / "cached.txt"
    assert data.fetch_text("nonexistent-dataset", dest, download=False) == dest
    assert not dest.exists()
