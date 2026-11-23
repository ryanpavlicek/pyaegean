"""Regression tests for scale and surface polish:
- Zero-copy Corpus.load() for fresh-allocating loaders (preserving cached-loader isolation)
- Bounded offset/limit pagination on MCP list/query tools
- Non-blocking TUI corpus loading with stale-result suppression
"""

from __future__ import annotations

import asyncio
import threading

import pytest

import aegean
from aegean import mcp_server as m
from aegean.core.corpus import _FRESH_LOADERS, _LOADERS, Corpus, register_loader
from aegean.core.model import Document, Token, TokenKind


def _mini_corpus(doc_id: str = "D1") -> Corpus:
    return Corpus(
        [Document(id=doc_id, script_id="greek", tokens=[Token("λόγος", TokenKind.WORD)], lines=[[0]])],
        script_id="greek",
    )


# ── Corpus.load() zero-copy vs cached isolation ──────────────────────────────


def test_fresh_loader_skips_copy_and_cached_loader_stays_isolated() -> None:
    created: list[Corpus] = []

    def fresh_loader() -> Corpus:
        c = _mini_corpus("F1")
        created.append(c)
        return c

    singleton = _mini_corpus("C1")

    def cached_loader() -> Corpus:
        return singleton

    try:
        register_loader("_test_fresh_c2", fresh_loader, fresh=True)
        register_loader("_test_cached_c2", cached_loader)

        loaded_fresh = Corpus.load("_test_fresh_c2")
        assert loaded_fresh is created[-1]

        loaded_cached = Corpus.load("_test_cached_c2")
        assert loaded_cached is not singleton
        assert loaded_cached.documents[0].id == "C1"

        # Re-registering with fresh=False restores defensive copying.
        register_loader("_test_fresh_c2", fresh_loader, fresh=False)
        loaded_copied = Corpus.load("_test_fresh_c2")
        assert loaded_copied is not created[-1]
    finally:
        _LOADERS.pop("_test_fresh_c2", None)
        _LOADERS.pop("_test_cached_c2", None)
        _FRESH_LOADERS.discard("_test_fresh_c2")
        _FRESH_LOADERS.discard("_test_cached_c2")


def test_fetched_loaders_marked_fresh_and_bundled_loaders_stay_isolated() -> None:
    bundled = {"lineara", "linearb", "cypriot", "cyprominoan", "greek"}
    fetched = {"ddbdp", "damos", "sigla", "nt", "isicily", "iip", "iospe", "igcyr", "edh"}
    assert bundled.isdisjoint(_FRESH_LOADERS)
    assert fetched <= _FRESH_LOADERS

    a = aegean.load("greek")
    b = aegean.load("greek")
    assert a is not b


# ── MCP bounded pagination ───────────────────────────────────────────────────


def test_mcp_query_corpus_pagination_inscriptions_and_words() -> None:
    full_ins = m.query_corpus(
        "lineara", [{"field": "site-is", "value": "Haghia Triada"}], limit=10
    )
    assert full_ins["offset"] == 0
    assert full_ins["truncated"] is True
    assert full_ins["next_offset"] == 10
    assert len(full_ins["inscriptions"]) == 10

    p1 = m.query_corpus(
        "lineara", [{"field": "site-is", "value": "Haghia Triada"}], limit=4, offset=0
    )
    p2 = m.query_corpus(
        "lineara", [{"field": "site-is", "value": "Haghia Triada"}], limit=6, offset=4
    )
    assert p1["inscriptions"] + p2["inscriptions"] == full_ins["inscriptions"]
    assert p1["next_offset"] == 4
    assert p2["next_offset"] == 10

    # Words mode pagination reconstructs the full result cleanly.
    all_words = m.query_corpus(
        "lineara", [{"field": "word-prefix", "value": "KU"}], output_kind="words", limit=0
    )
    assert all_words["truncated"] is False
    assert all_words["next_offset"] is None
    stitched: list[dict[str, object]] = []
    offset = 0
    while True:
        page = m.query_corpus(
            "lineara",
            [{"field": "word-prefix", "value": "KU"}],
            output_kind="words",
            limit=10,
            offset=offset,
        )
        stitched.extend(page["words"])
        if not page["truncated"]:
            assert page["next_offset"] is None
            break
        offset = page["next_offset"]
    assert stitched == all_words["words"]


def test_mcp_greek_catalog_search_signs_and_balance_pagination() -> None:
    # greek_catalog pagination
    all_plato = m.greek_catalog(author="plato", limit=0)
    assert all_plato["truncated"] is False
    assert all_plato["next_offset"] is None
    page1 = m.greek_catalog(author="plato", limit=5, offset=0)
    page2 = m.greek_catalog(author="plato", limit=5, offset=5)
    assert page1["offset"] == 0
    assert page1["truncated"] is True
    assert page1["next_offset"] == 5
    assert page1["works"] + page2["works"] == all_plato["works"][:10]

    # search_signs pagination
    all_hits = m.search_signs("lineara", "KU-*", limit=0)
    assert isinstance(all_hits, list) and len(all_hits) == 12
    assert m.search_signs("lineara", "KU-*", limit=5, offset=0) == all_hits[:5]
    assert m.search_signs("lineara", "KU-*", limit=5, offset=5) == all_hits[5:10]
    assert m.search_signs("lineara", "KU-*", limit=5, offset=10) == all_hits[10:]

    # balance_accounts pagination
    all_bal = m.balance_accounts("lineara")
    assert isinstance(all_bal, list) and len(all_bal) > 5
    b1 = m.balance_accounts("lineara", limit=3, offset=0)
    b2 = m.balance_accounts("lineara", limit=3, offset=3)
    assert isinstance(b1, list) and isinstance(b2, list)
    assert b1 + b2 == all_bal[:6]

    # Negative offsets return structured errors across all four tools.
    for res in (
        m.search_signs("lineara", "KU-*", offset=-1),
        m.balance_accounts("lineara", offset=-1),
        m.query_corpus("lineara", [], offset=-1),
        m.greek_catalog(offset=-1),
    ):
        assert isinstance(res, dict) and "offset must be >= 0" in res["error"]


# ── TUI non-blocking corpus loading ──────────────────────────────────────────


def test_tui_corpus_load_runs_off_ui_thread_and_discards_stale_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("textual")
    from textual.widgets import Static

    from aegean.tui import data as adapter
    from aegean.tui.app import AegeanApp
    from aegean.tui.screens.corpus import CorpusBrowserScreen
    from aegean.tui.widgets import DocTable

    assert hasattr(CorpusBrowserScreen._load_corpus_worker, "__wrapped__")

    ui_tid = threading.get_ident()
    worker_tids: list[int] = []
    slow_started = threading.Event()
    release_slow = threading.Event()
    slow_corpus = _mini_corpus("SLOW_DOC")
    fast_corpus = _mini_corpus("FAST_DOC")

    def fake_read(spec: str) -> Corpus:
        worker_tids.append(threading.get_ident())
        if spec == "slow-corpus":
            slow_started.set()
            release_slow.wait(timeout=5.0)
            return slow_corpus
        if spec == "fast-corpus":
            return fast_corpus
        raise adapter.TuiError(f"unknown {spec}")

    monkeypatch.setattr(adapter, "read_corpus_spec", fake_read)

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.open_corpus("slow-corpus")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CorpusBrowserScreen)
            # Immediate loading status before worker finishes.
            assert "loading slow-corpus" in str(screen.query_one("#corpus-status", Static).content)
            assert slow_started.wait(timeout=5.0)
            # Supersede the slow load with a fast load before releasing slow.
            app.open_corpus("fast-corpus")
            await pilot.pause()
            release_slow.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert screen._loaded_id == "fast-corpus"
            docs = screen.query_one("#corpus-docs", DocTable)
            assert docs.row_count == 1
            assert docs.is_valid_row_index(docs.get_row_index("FAST_DOC"))
            assert worker_tids and all(tid != ui_tid for tid in worker_tids)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(body())
    finally:
        release_slow.set()
        loop.close()
