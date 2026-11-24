"""Tests for TUI scholarly upgrades: interlinear reader inspector, lexicon/scansion
line analyses, Beta Code live workbench mode, and full 10-meter scansion support."""

from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("PYTHONUTF8", "1")

pytest.importorskip("textual")

from aegean.tui import data as adapter  # noqa: E402
from aegean.tui.app import AegeanApp  # noqa: E402
from aegean.tui.screens.greek import _METERS  # noqa: E402
from aegean.tui.widgets import DetailPane  # noqa: E402


def _run(coro) -> None:  # type: ignore[no-untyped-def]
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


def test_greek_gloss_and_auto_scan_line_analyses() -> None:
    keys = [o.key for o in adapter.line_analyses("greek")]
    assert {"offline", "neural", "neural_oov", "gloss", "scan", "ipa", "translate"} <= set(keys)

    gloss_res = adapter.run_line_analysis(
        "gloss",
        script_id="greek",
        text="ἐν ἀρχῇ ἦν ὁ λόγος",
        token_texts=("ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος"),
    )
    assert gloss_res.ok
    assert gloss_res.columns == ("word", "lemma", "Strong's", "gloss", "source")
    logos_rows = [r for r in gloss_res.rows if r[0] == "λόγος"]
    assert logos_rows and logos_rows[0][2] == "G3056" and "word" in logos_rows[0][3].lower()

    scan_hex = adapter.run_line_analysis(
        "scan",
        script_id="greek",
        text="μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος",
        token_texts=("μῆνιν", "ἄειδε", "θεὰ", "Πηληϊάδεω", "Ἀχιλῆος"),
    )
    assert scan_hex.ok and "hexameter" in scan_hex.title

    scan_tri = adapter.run_line_analysis(
        "scan",
        script_id="greek",
        text="τί δ᾽ ἔστι; λέξον· εἰ φρενῶν ἐτήτυμον",
        token_texts=("τί", "δ᾽", "ἔστι;", "λέξον·", "εἰ", "φρενῶν", "ἐτήτυμον"),
    )
    assert scan_tri.ok and "trimeter" in scan_tri.title


def test_token_inspector_formats_nt_annotations() -> None:
    tok = adapter.TokenCell(
        text="Λόγος",
        kind="word",
        status="certain",
        alt=(),
        annotations={"lemma": "λόγος", "morph": "N-NSM", "upos": "NOUN", "strongs": "3056"},
    )
    summary = adapter.format_token_inspector(tok, script_id="greek")
    assert "Λόγος" in summary
    assert "lemma: λόγος" in summary
    assert "NOUN (N-NSM)" in summary
    assert "Strong's G3056" in summary
    assert "word" in summary.lower()


def test_workbench_has_all_ten_meters_betacode_and_lexicon_tab() -> None:
    assert len(_METERS) == 10
    meter_values = {v for _, v in _METERS}
    assert {"hexameter", "pentameter", "trimeter", "glyconic", "sapphic_hendecasyllable"} <= meter_values

    async def body() -> None:
        from textual.widgets import Input, Static

        app = AegeanApp()
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.press("g")
            await pilot.pause()
            screen = app.screen
            screen.action_toggle_betacode()  # type: ignore[attr-defined]
            inp = screen.query_one("#greek-input", Input)
            inp.value = "lo/gos"
            await pilot.pause()
            await pilot.pause(0.2)
            bar = str(screen.query_one("#greek-betacode-bar", Static).content)
            assert "λόγος" in bar
            lex = str(screen.query_one("#greek-lexicon", Static).content)
            assert "G3056" in lex and "dodson" in lex

    _run(body())


def test_corpus_reader_word_cursor_inspector_and_interlinear_toggle() -> None:
    async def body() -> None:
        from textual.widgets import Static

        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            app.goto("corpus")
            await pilot.pause()
            screen = app.screen
            screen._open_corpus("nt")  # type: ignore[attr-defined]
            await app.workers.wait_for_complete()
            await pilot.pause()
            # Open the first bundled NT document (John 1)
            first_doc = screen._all_rows[0].id  # type: ignore[attr-defined]
            screen._show_document(first_doc)  # type: ignore[attr-defined]
            await pilot.pause()
            reader = screen.query_one("#corpus-detail", DetailPane)
            inspector_0 = str(screen.query_one("#corpus-inspector", Static).content)
            assert inspector_0.startswith("L1:") and "Strong's" in inspector_0
            reader.action_token_next()
            await pilot.pause()
            assert reader.cursor_token == 1
            inspector_1 = str(screen.query_one("#corpus-inspector", Static).content)
            assert inspector_1 != inspector_0
            assert not reader.show_interlinear
            reader.action_toggle_interlinear()
            await pilot.pause()
            assert reader.show_interlinear
            assert "[dim]" in str(reader.content)

    _run(body())
