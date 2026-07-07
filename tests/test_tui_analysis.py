"""Pilot + unit tests for the in-reader line-analysis modal (`aegean.tui.screens.analysis`).

The modal is a thin view over the ``tui.data`` analysis surface (tested in
test_tui_data). Here: the shared ``format_result`` renders a table and a text block; the
modal auto-runs the first analysis on mount; Esc closes it; and an unavailable analysis
(translation without a key) shows why instead of crashing.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from aegean.tui import data as adapter  # noqa: E402
from aegean.tui.app import AegeanApp  # noqa: E402
from aegean.tui.screens.analysis import LineAnalysisScreen, format_result  # noqa: E402


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    asyncio.new_event_loop().run_until_complete(coro)


def test_format_result_renders_a_table_and_a_text_block() -> None:
    tbl = adapter.AnalysisResult(
        ok=True, title="parse", columns=("#", "token"), rows=(("1", "μῆνιν"),), note="n=1"
    )
    out = format_result(tbl)
    assert "parse" in out and "token" in out and "μῆνιν" in out and "n=1" in out
    txt = adapter.AnalysisResult(ok=True, title="translation", text="the wrath", note="via x")
    out2 = format_result(txt)
    assert "the wrath" in out2 and "via x" in out2
    err = adapter.AnalysisResult(ok=False, error="boom")
    assert format_result(err) == "boom"


def test_modal_auto_runs_offline_analysis_for_a_greek_line() -> None:
    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("corpus")
            await pilot.pause()
            app.push_screen(
                LineAnalysisScreen(
                    script_id="greek", line_number=1,
                    line_text="μῆνιν ἄειδε θεὰ", token_texts=("μῆνιν", "ἄειδε", "θεὰ"),
                )
            )
            await pilot.pause()
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, LineAnalysisScreen)
            out = str(modal.output_text())
            assert "μῆνις" in out  # the offline lemma of μῆνιν, run on mount
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, LineAnalysisScreen)  # Esc closes

    _run(body())


def test_modal_shows_why_translation_is_unavailable_without_a_key(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from aegean.ai.client import _PROVIDERS

    for cls in _PROVIDERS.values():
        if getattr(cls, "env_key", ""):
            monkeypatch.delenv(cls.env_key, raising=False)

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.goto("corpus")
            await pilot.pause()
            modal = LineAnalysisScreen(
                script_id="greek", line_number=1, line_text="μῆνιν", token_texts=("μῆνιν",)
            )
            app.push_screen(modal)
            await pilot.pause()
            await pilot.pause()
            # selecting the (unavailable) translate option shows the reason, no crash
            modal._run("translate")
            await app.workers.wait_for_complete()  # drain any analysis worker before asserting
            await pilot.pause()
            out = str(modal.output_text())
            assert "unavailable" in out.lower() or "byoai" in out.lower()

    _run(body())
