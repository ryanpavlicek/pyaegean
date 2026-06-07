"""The download-to-cache layer: sha256 verification, atomicity, idempotency,
env-override URLs, and clear errors. Uses file:// URLs — no network."""

from __future__ import annotations

import pytest

from aegean import data
from aegean.data import DataNotAvailableError, DataSpec, fetch, sha256_file


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))


def _source(tmp_path, content=b"facsimile-bytes"):
    src = tmp_path / "src.bin"
    src.write_bytes(content)
    return src, sha256_file(src)


def test_unknown_dataset_raises():
    with pytest.raises(DataNotAvailableError, match="unknown dataset"):
        fetch("nope")


def test_unpinned_url_reports_env_hint():
    with pytest.raises(DataNotAvailableError, match="PYAEGEAN_LINEARA_IMAGES_URL"):
        fetch("lineara-images")


def test_env_override_downloads_and_is_idempotent(tmp_path, monkeypatch):
    src, _ = _source(tmp_path)
    monkeypatch.setenv("PYAEGEAN_LINEARA_IMAGES_URL", src.as_uri())
    p = fetch("lineara-images")
    assert p.exists() and p.read_bytes() == src.read_bytes()
    mtime = p.stat().st_mtime_ns
    assert fetch("lineara-images") == p  # second call is a no-op (not re-downloaded)
    assert p.stat().st_mtime_ns == mtime


def test_sha256_verification_passes_and_rejects(tmp_path, monkeypatch):
    src, good = _source(tmp_path)
    monkeypatch.setitem(
        data._REMOTE,
        "test-ds",
        DataSpec(name="test-ds", url=src.as_uri(), license="test", sha256=good),
    )
    assert fetch("test-ds").read_bytes() == src.read_bytes()

    monkeypatch.setitem(
        data._REMOTE,
        "bad-ds",
        DataSpec(name="bad-ds", url=src.as_uri(), license="test", sha256="0" * 64),
    )
    with pytest.raises(DataNotAvailableError, match="checksum mismatch"):
        fetch("bad-ds")
    assert not (data.cache_dir() / "bad-ds").exists()  # corrupt download removed
    assert not (data.cache_dir() / "bad-ds.part").exists()


def test_force_redownloads(tmp_path, monkeypatch):
    src, _ = _source(tmp_path, b"v1")
    monkeypatch.setenv("PYAEGEAN_LINEARA_IMAGES_URL", src.as_uri())
    p = fetch("lineara-images")
    assert p.read_bytes() == b"v1"
    src.write_bytes(b"v2")  # upstream changes
    assert fetch("lineara-images").read_bytes() == b"v1"  # cached, unchanged
    assert fetch("lineara-images", force=True).read_bytes() == b"v2"  # forced refresh
