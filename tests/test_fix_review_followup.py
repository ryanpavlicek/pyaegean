"""Regression tests for the post-0.44 defect-review follow-up.

These are the cross-cutting cases not already pinned by the focused progress,
translation, and CLI suites: checksum-confirmed reset completion, long-held lock
exclusivity, extraction crash-window provenance, and multi-instance response-cache
merging. Every test is local/offline and exercises the production implementation.
"""

from __future__ import annotations

import hashlib
import tarfile
import threading
import time
from pathlib import Path

import pytest


def test_pinned_complete_part_survives_reset_without_duplicate_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean import data

    payload = b"complete close-delimited response"
    expected = hashlib.sha256(payload).hexdigest()
    part = tmp_path / "asset.part"
    calls = {"n": 0}

    def reset_after_complete(
        _url: str,
        dest: Path,
        _abort: object = None,
        *,
        progress: object = None,
    ) -> None:
        calls["n"] += 1
        dest.write_bytes(payload)
        raise ConnectionResetError("RST after complete body")

    monkeypatch.setattr(data, "_download_once", reset_after_complete)
    data._download("https://example.invalid/asset", part, "asset", expected_sha256=expected)
    assert calls["n"] == 1  # checksum proves completion; no duplicate Range request
    assert part.read_bytes() == payload


def test_unpinned_reset_is_never_accepted_as_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean import data

    part = tmp_path / "asset.part"
    calls = {"n": 0}

    def reset_unverifiable(
        _url: str,
        dest: Path,
        _abort: object = None,
        *,
        progress: object = None,
    ) -> None:
        calls["n"] += 1
        dest.write_bytes(b"possibly truncated")
        raise ConnectionResetError("RST")

    monkeypatch.setattr(data, "_download_once", reset_unverifiable)
    with pytest.raises(data.DataNotAvailableError, match="partial download kept"):
        data._download("https://example.invalid/asset", part, "asset")
    assert calls["n"] == data._DOWNLOAD_ATTEMPTS


def test_kernel_lock_remains_exclusive_past_lease_timing(tmp_path: Path) -> None:
    from aegean._locking import FileLock

    path = tmp_path / "asset.lock"
    acquired = threading.Event()
    first = FileLock(
        path,
        stale_after=0.08,
        poll_every=0.005,
        heartbeat_every=0.01,
    )

    def wait_for_lock() -> None:
        with FileLock(
            path,
            stale_after=0.08,
            poll_every=0.005,
            heartbeat_every=0.01,
        ):
            acquired.set()

    with first:
        time.sleep(0.12)  # older than the legacy lease threshold; kernel lock remains live
        waiter = threading.Thread(target=wait_for_lock, daemon=True)
        waiter.start()
        time.sleep(0.05)
        assert not acquired.is_set()  # still exclusive after the former lease boundary
    waiter.join(timeout=2)
    assert acquired.is_set()
    assert path.exists()  # persistent sentinel; kernel ownership, not existence, is the lock
    assert FileLock.is_locked(path) is False


def test_old_holder_never_unlinks_a_successor_lock(tmp_path: Path) -> None:
    from aegean._locking import FileLock

    path = tmp_path / "asset.lock"
    old = FileLock(path, stale_after=1, poll_every=0.01, heartbeat_every=0.1)
    old.__enter__()
    old.__exit__(None, None, None)
    # The sentinel is never unlinked. A successor takes kernel ownership of the
    # same inode, eliminating the former ownership-check/unlink ABA window.
    assert path.exists()
    with FileLock(path, poll_every=0.01):
        assert FileLock.is_locked(path)


def _archive(tmp_path: Path, label: str, content: bytes) -> tuple[Path, str]:
    source = tmp_path / f"{label}-source"
    source.mkdir()
    (source / "corpus.txt").write_bytes(content)
    archive = tmp_path / f"{label}.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(source, arcname="images")
    return archive, hashlib.sha256(archive.read_bytes()).hexdigest()


def test_embedded_extraction_stamp_closes_post_swap_crash_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean import data

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    v1, sha1 = _archive(tmp_path, "v1", b"v1")
    v2, sha2 = _archive(tmp_path, "v2", b"v2")
    monkeypatch.setitem(
        data._REMOTE,
        "bundle",
        data.DataSpec(name="bundle", url=v1.as_uri(), license="test", sha256=sha1, extract=True),
    )
    target = data.fetch("bundle")
    assert (target / data._EMBEDDED_EXTRACT_STAMP).read_text(encoding="ascii") == sha1
    data._extract_stamp("bundle").unlink()  # crash after target swap, before sibling stamp

    monkeypatch.setitem(
        data._REMOTE,
        "bundle",
        data.DataSpec(name="bundle", url=v2.as_uri(), license="test", sha256=sha2, extract=True),
    )
    refreshed = data.fetch("bundle")
    assert (refreshed / "images" / "corpus.txt").read_bytes() == b"v2"
    assert (refreshed / data._EMBEDDED_EXTRACT_STAMP).read_text(encoding="ascii") == sha2


def test_response_cache_merges_independent_instance_updates(tmp_path: Path) -> None:
    from aegean.ai.cache import ResponseCache

    path = tmp_path / "responses.json"
    first = ResponseCache(path)
    second = ResponseCache(path)  # both begin from the same empty snapshot
    first.set("p", "m", None, "first", "A")
    second.set("p", "m", None, "second", "B")

    reread = ResponseCache(path)
    assert reread.get("p", "m", None, "first") == "A"
    assert reread.get("p", "m", None, "second") == "B"


def test_response_cache_does_not_roll_back_unrelated_newer_keys(tmp_path: Path) -> None:
    from aegean.ai.cache import ResponseCache

    path = tmp_path / "responses.json"
    ResponseCache(path).set("p", "m", None, "shared", "original")
    first = ResponseCache(path)
    stale = ResponseCache(path)
    first.set("p", "m", None, "shared", "newer")
    stale.set("p", "m", None, "other", "answer")

    reread = ResponseCache(path)
    assert reread.get("p", "m", None, "shared") == "newer"
    assert reread.get("p", "m", None, "other") == "answer"
