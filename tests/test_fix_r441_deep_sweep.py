"""Adversarial regressions for cross-process and persistence guarantees."""

from __future__ import annotations

import hashlib
import io
import tarfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


def test_analysis_cache_distinguishes_list_tuple_and_mixed_dict_keys(tmp_path: Path) -> None:
    from aegean import cache

    calls = 0

    @cache.memoize()
    def kind(value: object) -> str:
        nonlocal calls
        calls += 1
        return type(value).__name__

    cache.enable(tmp_path / "analysis.sqlite")
    try:
        assert kind([1, 2]) == "list"
        assert kind((1, 2)) == "tuple"
        assert kind({"a": 1, 2: 3}) == "dict"
        assert kind({2: 3, "a": 1}) == "dict"
        assert calls == 3  # reordered heterogeneous dict keys share one safe key
    finally:
        cache.disable()


def test_analysis_cache_independent_writers_never_surface_sqlite_lock(tmp_path: Path) -> None:
    from aegean.cache import DiskCache

    caches = [DiskCache(tmp_path / "analysis.sqlite") for _ in range(4)]
    try:
        def write(group: int) -> None:
            for i in range(100):
                caches[group].set(f"{group}:{i}", (group, i))

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(write, range(4)))
        assert sum(len(c) for c in caches) >= 400
    finally:
        for cache in caches:
            cache.close()


def test_file_lock_keeps_persistent_path_without_aba_release(tmp_path: Path) -> None:
    from aegean._locking import FileLock

    path = tmp_path / "asset.lock"
    acquired = threading.Event()

    with FileLock(path, poll_every=0.005):
        assert FileLock.is_locked(path)

        def waiter() -> None:
            with FileLock(path, poll_every=0.005):
                acquired.set()

        thread = threading.Thread(target=waiter)
        thread.start()
        time.sleep(0.03)
        assert not acquired.is_set()
    thread.join(timeout=2)
    assert acquired.is_set()
    assert path.exists()
    assert not FileLock.is_locked(path)


def test_direct_downloads_to_same_destination_are_serialized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean import data

    payload = b"one complete artifact"
    source = tmp_path / "source.bin"
    source.write_bytes(payload)
    dest = tmp_path / "dest.bin"
    sha = hashlib.sha256(payload).hexdigest()
    original = data._download
    calls = 0

    def slow(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        time.sleep(0.04)
        original(*args, **kwargs)

    monkeypatch.setattr(data, "_download", slow)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: data.download_file(source.as_uri(), dest, sha256=sha), range(2)))
    assert results == [dest, dest]
    assert calls == 1
    assert dest.read_bytes() == payload


def test_negative_content_length_is_rejected() -> None:
    from aegean.data import _expected_length

    with pytest.raises(ValueError, match="negative Content-Length"):
        _expected_length({"Content-Length": "-1"})


def test_tar_caps_and_special_files_are_rejected_before_extraction(tmp_path: Path) -> None:
    from aegean import data

    archive = tmp_path / "payload.tar"
    with tarfile.open(archive, "w") as tf:
        info = tarfile.TarInfo("large.txt")
        body = b"12345"
        info.size = len(body)
        tf.addfile(info, io.BytesIO(body))
    with pytest.raises(data.DataNotAvailableError, match="expands to"):
        data._safe_extract_tar(archive, tmp_path / "out-size", max_bytes=4)
    with pytest.raises(data.DataNotAvailableError, match="members"):
        data._safe_extract_tar(archive, tmp_path / "out-count", max_members=0)

    special = tmp_path / "special.tar"
    with tarfile.open(special, "w") as tf:
        fifo = tarfile.TarInfo("pipe")
        fifo.type = tarfile.FIFOTYPE
        tf.addfile(fifo)
    with pytest.raises(data.DataNotAvailableError, match="special file"):
        data._safe_extract_tar(special, tmp_path / "out-special")


def test_prebuilt_member_failed_copy_preserves_prior_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean import data

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "model").write_bytes(b"new")
    dest = tmp_path / "model"
    dest.write_bytes(b"old-valid")
    monkeypatch.setattr(data, "fetch", lambda _name: bundle)

    def broken_copy(_src: object, target: object) -> None:
        Path(target).write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr("shutil.copyfile", broken_copy)
    with pytest.raises(OSError, match="disk full"):
        data.fetch_prebuilt("bundle", dest, member="model")
    assert dest.read_bytes() == b"old-valid"


def test_failed_model_write_preserves_prior_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.greek import tagger

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    out = tagger.cache_dir() / tagger._MODEL_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"old-valid-model")
    monkeypatch.setattr(tagger, "_sentences", lambda _source: [])
    monkeypatch.setattr(tagger, "_train", lambda _sentences, _epochs: ({}, []))

    def broken_open(path: object, *_args: object, **_kwargs: object) -> object:
        Path(path).write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(tagger.gzip, "open", broken_open)
    with pytest.raises(OSError, match="disk full"):
        tagger.train_tagger(source_dir="fixture", force=True)
    assert out.read_bytes() == b"old-valid-model"


def test_extract_swap_failure_restores_prior_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean import data

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    root = data.cache_dir()
    target = root / "bundle"
    target.mkdir()
    (target / "value").write_text("old", encoding="utf-8")
    source = tmp_path / "new"
    source.mkdir()
    (source / "value").write_text("new", encoding="utf-8")
    archive = tmp_path / "new.tar"
    with tarfile.open(archive, "w") as tf:
        tf.add(source / "value", arcname="value")
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    real_replace = Path.replace

    def fail_staging(self: Path, destination: object) -> Path:
        if self.name == "bundle.extract":
            raise OSError("swap failed")
        return real_replace(self, destination)

    monkeypatch.setattr(Path, "replace", fail_staging)
    with pytest.raises(OSError, match="swap failed"):
        data._fetch_and_extract(archive.as_uri(), "bundle", True, sha)
    assert (target / "value").read_text(encoding="utf-8") == "old"
    assert not (root / "bundle.old").exists()


def test_result_write_failure_preserves_prior_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.cli._common import write_result

    output = tmp_path / "result.json"
    output.write_text("old-valid", encoding="utf-8")
    original = Path.write_text

    def broken(self: Path, text: str, *args: object, **kwargs: object) -> int:
        if self != output:
            original(self, "partial", encoding="utf-8")
            raise OSError("disk full")
        return original(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", broken)
    with pytest.raises(BaseException):
        write_result({"answer": 42}, output)
    assert output.read_text(encoding="utf-8") == "old-valid"


def test_default_nt_evaluations_reject_bundled_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    from aegean import data
    from aegean.greek.erroranalysis import nt_error_analysis
    from aegean.greek.nt_eval import evaluate_on_nt
    from aegean.scripts.greek import nt

    monkeypatch.setattr(
        data,
        "fetch",
        lambda *_a, **_k: (_ for _ in ()).throw(data.DataNotAvailableError("offline")),
    )
    nt._bundled_payload.cache_clear()
    with pytest.raises(data.DataNotAvailableError, match="full pinned 27-book"):
        evaluate_on_nt(lambda forms: [(form, "X") for form in forms])
    with pytest.raises(data.DataNotAvailableError, match="full pinned 27-book"):
        nt_error_analysis(lambda forms: [(form, "X") for form in forms])


def test_translation_rarity_never_uses_or_fetches_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    from aegean.scripts.greek import nt
    from aegean.translate import _rare_word_line

    monkeypatch.setattr(nt, "_load_cached_full_nt", lambda: None)
    assert _rare_word_line("λόγος φαρμακεία") == ""
