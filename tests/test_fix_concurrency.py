"""Regression tests for the concurrency fix pass.

Each pins thread-safe behavior that previously crashed, corrupted, or tore under a
realistic concurrent workload. Deterministic where the old failure was deterministic
(sqlite's thread-identity check); barrier-aligned and repeated where it was a race.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aegean import Corpus
from aegean._locking import FileLock
from aegean.core.model import Document, Token, TokenKind


def _corpus(n_docs: int = 3) -> Corpus:
    return Corpus(
        [Document(id=f"d{i}", script_id="lineara",
                  tokens=[Token("KU-RO", TokenKind.WORD, signs=("KU", "RO"), position=0),
                          Token(str(i), TokenKind.NUMERAL, position=1)],
                  lines=[[0, 1]])
         for i in range(n_docs)],
        script_id="lineara",
    )


# ── the analysis cache works from worker threads (was: 100% ProgrammingError) ──


def test_analysis_cache_is_thread_safe(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from aegean import cache
    from aegean.analysis import stats

    c = _corpus(4)
    cache.enable(tmp_path / "analysis.sqlite")
    try:
        stats.dispersions(c, kind="signs", min_frequency=1)  # warm entry on this thread

        def call(_: int) -> int:
            rows = stats.dispersions(c, kind="signs", min_frequency=1)  # cache hit
            assert cache.stats()["enabled"]  # stats() from a worker also crashed before
            return len(rows)

        with ThreadPoolExecutor(max_workers=4) as ex:
            counts = list(ex.map(call, range(16)))
        assert len(set(counts)) == 1  # every thread got the same (correct) answer
    finally:
        cache.disable()  # disable() from the enabling thread; also exercised above


# ── the AI response cache persists safely under concurrent set() ──


def test_response_cache_concurrent_set_never_raises_or_corrupts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from aegean.ai.cache import ResponseCache

    path = tmp_path / "resp.json"
    rc = ResponseCache(path)
    barrier = threading.Barrier(8)
    errors: list[BaseException] = []

    def writer(i: int) -> None:
        try:
            barrier.wait()
            for j in range(25):
                rc.set("prov", "model", None, f"prompt-{i}-{j}", f"answer-{i}-{j}")
        except BaseException as exc:  # noqa: BLE001 — the assertion is "never raises"
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,), daemon=True) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []  # a persist failure degrades to memory-only, never raises
    # the on-disk file is whole JSON and every serialized in-process write survives
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and len(data) == 8 * 25


def test_response_cache_set_survives_an_unwritable_disk(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The response was already obtained (and paid for); a failing persist must keep
    it in memory rather than raise out of LLMClient.complete."""
    import aegean.ai.cache as m

    rc = m.ResponseCache(tmp_path / "resp.json")
    monkeypatch.setattr(
        m.ResponseCache, "_write_atomic",
        lambda self: (_ for _ in ()).throw(OSError("disk full")),
    )
    rc.set("prov", "model", None, "prompt", "the paid answer")  # must not raise
    assert rc.get("prov", "model", None, "prompt") == "the paid answer"


# ── SQLite reads are not torn by a concurrent append ──


def test_stream_never_yields_a_torn_document(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Each yielded Document's row fields and tokens come from ONE committed state:
    with an appender continuously replacing the document (name and token text updated
    together), a reader must never see a version-N name with version-M tokens."""
    from aegean import db
    from aegean.core.model import DocumentMeta

    p = tmp_path / "c.db"

    def versioned(n: int) -> Corpus:
        doc = Document(
            id="D", script_id="greek",
            tokens=[Token(f"v{n}", TokenKind.WORD, position=0)], lines=[[0]],
            meta=DocumentMeta(name=f"v{n}"),
        )
        return Corpus([doc], script_id="greek")

    db.to_sqlite(versioned(0), p)
    stop = threading.Event()
    torn: list[tuple[str, str]] = []

    def appender() -> None:
        n = 1
        while not stop.is_set():
            try:
                db.to_sqlite(versioned(n), p, append=True)
            except sqlite3.OperationalError:
                continue  # locked by the reader's transaction: clean, retry
            n += 1

    t = threading.Thread(target=appender, daemon=True)
    t.start()
    try:
        for _ in range(200):
            try:
                for doc in db.stream(p):
                    if doc.meta.name != doc.tokens[0].text:
                        torn.append((doc.meta.name, doc.tokens[0].text))
            except sqlite3.OperationalError:
                continue  # writer holds the lock: clean failure, not a tear
    finally:
        stop.set()
        t.join()
    assert torn == []


def test_search_survives_concurrent_fts_updates(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Transactional FTS updates leave the table continuously available to readers."""
    from aegean import db

    p = tmp_path / "c.db"
    db.to_sqlite(_corpus(2), p)
    stop = threading.Event()
    errors: list[BaseException] = []

    def appender() -> None:
        while not stop.is_set():
            try:
                db.to_sqlite(_corpus(2), p, append=True)
            except sqlite3.OperationalError:
                continue

    t = threading.Thread(target=appender, daemon=True)
    t.start()
    try:
        for _ in range(300):
            try:
                hits = db.search(str(p), "KU-RO", mode="token")
            except sqlite3.OperationalError as exc:
                errors.append(exc)
            else:
                assert all(txt == "KU-RO" for _, _, txt in hits)
    finally:
        stop.set()
        t.join()
    assert errors == []


# ── concurrent fetches of one dataset are serialized on the per-dataset lock ──


def test_concurrent_fetch_same_dataset_yields_one_valid_artifact(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import hashlib

    from aegean import data

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "store"))
    payload = b"x" * 4096
    src = tmp_path / "asset.bin"
    src.write_bytes(payload)
    name = "conc-test-asset"
    spec = data.DataSpec(
        name=name, url=src.as_uri(), license="test",
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    monkeypatch.setitem(data._REMOTE, name, spec)

    barrier = threading.Barrier(4)
    results: list[Path] = []
    errors: list[BaseException] = []

    def fetcher() -> None:
        try:
            barrier.wait()
            results.append(data.fetch(name))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=fetcher, daemon=True) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(results) == 4 and len({str(p) for p in results}) == 1
    got = results[0].read_bytes()
    assert hashlib.sha256(got).hexdigest() == spec.sha256  # one whole, valid artifact
    lock = tmp_path / "store" / "pyaegean" / f"{name}.lock"
    assert FileLock.is_locked(lock) is False  # persistent sentinel, ownership released


def test_fetch_abort_hook_stops_the_transfer_and_keeps_the_part(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from aegean import data

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "store"))
    src = tmp_path / "asset.bin"
    src.write_bytes(b"y" * (3 << 20))  # three 1 MiB chunks: aborts after the first
    name = "abort-test-asset"
    monkeypatch.setitem(
        data._REMOTE, name, data.DataSpec(name=name, url=src.as_uri(), license="test")
    )
    calls = {"n": 0}

    def abort() -> bool:
        calls["n"] += 1
        return calls["n"] > 1  # let the first chunk through, then cancel

    try:
        data.fetch(name, abort=abort)
        raise AssertionError("expected FetchAborted")
    except data.FetchAborted:
        pass
    store = tmp_path / "store" / "pyaegean"
    assert (store / f"{name}.part").exists()  # kept for resume
    assert not (store / name).exists()
    assert FileLock.is_locked(store / f"{name}.lock") is False
