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


def test_unpinned_url_reports_env_hint(monkeypatch):
    monkeypatch.setitem(data._REMOTE, "blob", DataSpec(name="blob", url="", license="x"))
    with pytest.raises(DataNotAvailableError, match="PYAEGEAN_BLOB_URL"):
        fetch("blob")


def test_lineara_images_is_pinned():
    spec = data._REMOTE["lineara-images"]
    assert spec.url.endswith("lineara-images-v1/lineara-images.tar.gz")
    assert len(spec.sha256) == 64 and spec.extract is True


def test_single_file_download_and_idempotent(tmp_path, monkeypatch):
    src, _ = _source(tmp_path)
    monkeypatch.setitem(data._REMOTE, "blob", DataSpec(name="blob", url=src.as_uri(), license="x"))
    p = fetch("blob")
    assert p.exists() and p.read_bytes() == src.read_bytes()
    mtime = p.stat().st_mtime_ns
    assert fetch("blob") == p  # second call is a no-op (not re-downloaded)
    assert p.stat().st_mtime_ns == mtime


def test_env_override_resolves_url(tmp_path, monkeypatch):
    src, _ = _source(tmp_path)
    monkeypatch.setitem(data._REMOTE, "blob", DataSpec(name="blob", url="", license="x"))
    monkeypatch.setenv("PYAEGEAN_BLOB_URL", src.as_uri())
    assert fetch("blob").read_bytes() == src.read_bytes()


def test_lineara_images_env_override_extracts(tmp_path, monkeypatch):
    # The documented user path: point the fetcher at a licensed tar.gz copy.
    archive, _ = _make_targz(tmp_path, {"HT1.jpg": b"facsimile"})
    monkeypatch.setenv("PYAEGEAN_LINEARA_IMAGES_URL", archive.as_uri())
    out = fetch("lineara-images")
    assert out.is_dir()
    assert (out / "images" / "HT1.jpg").read_bytes() == b"facsimile"


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


def _make_targz(tmp_path, files: dict[str, bytes]):
    import tarfile

    src = tmp_path / "payload"
    src.mkdir()
    for rel, content in files.items():
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(src, arcname="images")
    return archive, sha256_file(archive)


def test_extract_dataset_unpacks_and_is_idempotent(tmp_path, monkeypatch):
    archive, sha = _make_targz(tmp_path, {"a.jpg": b"img-a", "sub/b.jpg": b"img-b"})
    monkeypatch.setitem(
        data._REMOTE,
        "imgs",
        DataSpec(name="imgs", url=archive.as_uri(), license="x", sha256=sha, extract=True),
    )
    out = fetch("imgs")
    assert out.is_dir()
    assert (out / "images" / "a.jpg").read_bytes() == b"img-a"
    assert (out / "images" / "sub" / "b.jpg").read_bytes() == b"img-b"
    mtime = out.stat().st_mtime_ns
    assert fetch("imgs") == out and out.stat().st_mtime_ns == mtime  # no re-extract
    assert not (data.cache_dir() / "imgs.part").exists()  # archive cleaned up


def test_extract_repin_redownloads_on_sha_change(tmp_path, monkeypatch):
    """A re-pinned archive (a corpus rebuilt as -v2, new sha256) must be re-fetched, not
    served stale from the existing unpacked directory. The single-file path re-hashes the
    file; the extract path relies on a sha256 stamp beside the unpacked dir."""
    v1, sha1 = _make_targz(tmp_path, {"corpus.txt": b"v1-content"})
    monkeypatch.setitem(
        data._REMOTE, "cx", DataSpec(name="cx", url=v1.as_uri(), license="x", sha256=sha1, extract=True)
    )
    out = fetch("cx")
    assert (out / "images" / "corpus.txt").read_bytes() == b"v1-content"
    assert (data.cache_dir() / "cx.sha256").read_text().strip() == sha1  # stamped

    # re-pin the same dataset to a different archive (v2) — must re-extract
    v2 = tmp_path / "v2.tar.gz"
    import tarfile
    src2 = tmp_path / "p2"
    (src2 / "images").mkdir(parents=True)
    (src2 / "images" / "corpus.txt").write_bytes(b"v2-content")
    with tarfile.open(v2, "w:gz") as tf:
        tf.add(src2 / "images", arcname="images")
    sha2 = sha256_file(v2)
    monkeypatch.setitem(
        data._REMOTE, "cx", DataSpec(name="cx", url=v2.as_uri(), license="x", sha256=sha2, extract=True)
    )
    out2 = fetch("cx")
    assert (out2 / "images" / "corpus.txt").read_bytes() == b"v2-content"  # picked up v2
    assert (data.cache_dir() / "cx.sha256").read_text().strip() == sha2


def test_extract_legacy_unstamped_is_trusted(tmp_path, monkeypatch):
    """A pre-stamp (legacy) extraction has no .sha256 sidecar. To avoid needlessly
    re-downloading every unchanged heavy archive on upgrade, a missing stamp is trusted:
    the existing directory is served as-is (no re-extract)."""
    archive, sha = _make_targz(tmp_path, {"a.txt": b"cached"})
    monkeypatch.setitem(
        data._REMOTE, "cx", DataSpec(name="cx", url=archive.as_uri(), license="x", sha256=sha, extract=True)
    )
    out = fetch("cx")
    (data.cache_dir() / "cx.sha256").unlink()  # simulate a pre-0.29 extraction
    (out / data._EMBEDDED_EXTRACT_STAMP).unlink()  # new caches carry this; legacy did not
    mtime = out.stat().st_mtime_ns
    # a DIFFERENT pinned sha, but no stamp present → trust the legacy extraction, no re-fetch
    monkeypatch.setitem(
        data._REMOTE, "cx", DataSpec(name="cx", url=archive.as_uri(), license="x", sha256="0" * 64, extract=True)
    )
    assert fetch("cx") == out and out.stat().st_mtime_ns == mtime  # untouched


def test_extract_rejects_checksum_mismatch(tmp_path, monkeypatch):
    archive, _ = _make_targz(tmp_path, {"a.jpg": b"x"})
    monkeypatch.setitem(
        data._REMOTE,
        "bad-imgs",
        DataSpec(name="bad-imgs", url=archive.as_uri(), license="x", sha256="0" * 64, extract=True),
    )
    with pytest.raises(DataNotAvailableError, match="checksum mismatch"):
        fetch("bad-imgs")
    assert not (data.cache_dir() / "bad-imgs").exists()


def test_extract_refuses_path_traversal(tmp_path, monkeypatch):
    import tarfile

    archive = tmp_path / "evil.tar.gz"
    payload = tmp_path / "evil.txt"
    payload.write_bytes(b"pwned")
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(payload, arcname="../escape.txt")  # escapes the extraction root
    monkeypatch.setitem(
        data._REMOTE,
        "evil",
        DataSpec(name="evil", url=archive.as_uri(), license="x", sha256=sha256_file(archive), extract=True),
    )
    with pytest.raises(DataNotAvailableError, match="unsafe path"):
        fetch("evil")


def test_force_redownloads(tmp_path, monkeypatch):
    src, _ = _source(tmp_path, b"v1")
    monkeypatch.setitem(data._REMOTE, "blob", DataSpec(name="blob", url=src.as_uri(), license="x"))
    p = fetch("blob")
    assert p.read_bytes() == b"v1"
    src.write_bytes(b"v2")  # upstream changes
    assert fetch("blob").read_bytes() == b"v1"  # cached, unchanged
    assert fetch("blob", force=True).read_bytes() == b"v2"  # forced refresh
