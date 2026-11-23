"""Tests for length-bucketed batching, non-pickle typed DiskCache, and SQLite ResponseCache."""

from __future__ import annotations

import math
import os
import pickle
import sqlite3
import stat
from pathlib import Path
from typing import Any

import pytest

from aegean import cache
from aegean.ai.cache import ResponseCache
from aegean.analysis.morphology import ClusterMember, MorphCluster
from aegean.analysis.stats import Dispersion, KeynessRow
from aegean.greek import joint


_PICKLE_TRIPWIRE_CALLED: list[str] = []


def _tripwire(msg: str) -> str:
    _PICKLE_TRIPWIRE_CALLED.append(msg)
    return msg


class _Exploit:
    def __reduce__(self) -> tuple[Any, tuple[str]]:
        return (_tripwire, ("executed",))


def test_disk_cache_rejects_legacy_pickle_without_deserializing(tmp_path: Path) -> None:
    """A planted pickle payload in the SQLite cache must be a cold miss and never execute."""
    _PICKLE_TRIPWIRE_CALLED.clear()
    payload = pickle.dumps(_Exploit())
    assert not _PICKLE_TRIPWIRE_CALLED

    db_path = tmp_path / "analysis.sqlite"
    dc = cache.DiskCache(db_path)
    try:
        if os.name == "posix":
            assert stat.S_IMODE(db_path.stat().st_mode) == 0o600
        # Plant a raw pickle blob directly into SQLite as a legacy/tampered row.
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
            ("legacy-key", payload),
        )
        conn.commit()
        conn.close()

        assert dc.get("legacy-key") is cache._MISS
        assert not _PICKLE_TRIPWIRE_CALLED
    finally:
        dc.close()


def test_disk_cache_typed_json_roundtrips_dataclasses_and_containers(tmp_path: Path) -> None:
    db_path = tmp_path / "typed.sqlite"
    dc = cache.DiskCache(db_path)
    try:
        sample = {
            "tuple": (1, "α", None, True),
            "set": frozenset({"β", "γ"}),
            "special_floats": [float("inf"), float("-inf")],
            "int_key_dict": {1: "one", "1": "str-one"},
            "clusters": [
                MorphCluster(
                    stem="KU-RO",
                    members=(ClusterMember(word="KU-RO", count=5, suffix=""),),
                    total_count=5,
                    suffixes=("",),
                )
            ],
            "disp": Dispersion(item="λόγος", frequency=10, range=3, parts=5, dp=0.2, dp_norm=0.25),
            "keyness": KeynessRow(
                item="θεός",
                target_count=4,
                target_total=100,
                reference_count=1,
                reference_total=200,
                log_likelihood=5.1,
                log_ratio=3.0,
                p_value=0.02,
            ),
        }
        dc.set("k1", sample)
        got = dc.get("k1")
        assert got == sample
        assert isinstance(got["tuple"], tuple)
        assert isinstance(got["set"], frozenset)
        assert isinstance(got["clusters"][0], MorphCluster)
        assert isinstance(got["disp"], Dispersion)
        assert isinstance(got["keyness"], KeynessRow)

        dc.set("nan_key", float("nan"))
        assert math.isnan(dc.get("nan_key"))

        # Unsupported arbitrary custom objects are silently not cached (no exception).
        class _Custom:
            pass

        dc.set("unsupported", _Custom())
        assert dc.get("unsupported") is cache._MISS
    finally:
        dc.close()


def test_response_cache_sqlite_backend_roundtrip_sharing_and_corruption_fallback(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ai_responses.sqlite"
    c1 = ResponseCache(db_path)
    c2 = ResponseCache(db_path)
    try:
        assert c1.backend == "sqlite"
        if os.name == "posix":
            assert stat.S_IMODE(db_path.stat().st_mode) == 0o600
        c1.set("anthropic", "claude-test", "sys", "prompt-1", "ANSWER-1", max_tokens=128)
        # Second live instance sees persisted entry immediately via keyed SELECT.
        assert c2.get("anthropic", "claude-test", "sys", "prompt-1", max_tokens=128) == "ANSWER-1"
        assert c2.get("anthropic", "claude-test", "sys", "prompt-1", max_tokens=256) is None
        assert len(c2) == 1

        c2.set("openai", "gpt-test", None, "prompt-2", "ANSWER-2", max_tokens=64)
        assert c1.get("openai", "gpt-test", None, "prompt-2", max_tokens=64) == "ANSWER-2"
        assert len(c1) == 2
    finally:
        c1.close()
        c2.close()

    # Corrupt SQLite file degrades cleanly to memory-only without raising.
    bad_path = tmp_path / "corrupt.sqlite"
    bad_path.write_bytes(b"not a valid sqlite database header")
    bad_cache = ResponseCache(bad_path)
    try:
        assert bad_cache.get("p", "m", "s", "prompt") is None
        bad_cache.set("p", "m", "s", "prompt", "MEM-ONLY")
        assert bad_cache.get("p", "m", "s", "prompt") == "MEM-ONLY"
    finally:
        bad_cache.close()


def test_analyze_sentences_length_bucket_groups_by_length_and_restores_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_batches: list[list[list[str]]] = []

    class _FakeModel:
        def analyze_batch(self, chunk: list[list[str]]) -> list[joint.SentenceAnalysis]:
            seen_batches.append([list(s) for s in chunk])
            return [
                joint.SentenceAnalysis(
                    tokens=tuple(s),
                    upos=("NOUN",) * len(s),
                    xpos=("n-s---mn-",) * len(s),
                    feats=("_",) * len(s),
                    head=tuple(range(len(s))),
                    deprel=("root",) + ("dep",) * (len(s) - 1),
                    lemma=tuple(s),
                    lemma_resolved=(True,) * len(s),
                )
                for s in chunk
            ]

    monkeypatch.setattr(joint, "active", lambda: _FakeModel())

    inputs = [
        ["α", "β", "γ", "δ"],  # len 4
        ["ε"],                  # len 1
        ["ζ", "η", "θ"],        # len 3
        ["ι", "κ"],             # len 2
    ]
    out = joint.analyze_sentences(inputs, batch_size=2, length_bucket=True)
    # Batches must be length-grouped: (len 1, len 2) then (len 3, len 4)
    assert seen_batches == [
        [["ε"], ["ι", "κ"]],
        [["ζ", "η", "θ"], ["α", "β", "γ", "δ"]],
    ]
    # Returned order must match original input order exactly!
    assert [list(a.tokens) for a in out] == inputs

    with pytest.raises(TypeError, match="length_bucket"):
        joint.analyze_sentences(inputs, batch_size=2, length_bucket="yes")  # type: ignore[arg-type]
