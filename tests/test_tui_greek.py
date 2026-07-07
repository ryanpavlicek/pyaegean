"""Content-asserting Pilot tests for the Greek workbench screen.

Textual 8.2.8 constraints these tests work within:

- no pytest-asyncio in the dev env, so each async body is wrapped in
  ``asyncio.new_event_loop().run_until_complete(_run())``;
- a rich/plain renderable inside a ``Static`` is read back via ``widget.content``
  (``.renderable`` / ``._renderable`` are absent on 8.x);
- Pilot tests run under ``PYTHONUTF8=1`` (set below) so Greek renders in widgets.

The assertions check real CONTENT: the known Iliad 1.1 hexameter foot pattern in
the scansion tab, the hyphenated syllable split of a typed word, a token's lemma
in the pipeline tab, the IPA transcription, and that a non-scanning line shows
the friendly adapter error rather than crashing. Each pinned string is the live
``aegean.tui.data`` output, re-checked against it by ``_pinned_strings_sanity``.
"""

from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("PYTHONUTF8", "1")

pytest.importorskip("textual")

from aegean.tui.app import AegeanApp  # noqa: E402
from aegean.tui import data as adapter  # noqa: E402

# The opening line of the Iliad, the canonical hexameter probe.
ILIAD_1_1 = "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"

# The foot-glyph pattern greek_scan returns for that line (the "DDSDDS" shape:
# dactyl dactyl spondee dactyl dactyl, closing foot). Pinned from a live call.
ILIAD_SCAN_PATTERN = "—⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×"


def _run(coro) -> None:
    """Drive an async Pilot body without pytest-asyncio (a fresh event loop)."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


def _pinned_strings_sanity() -> None:
    """The pinned constants must still match a live adapter call (guards against
    the tests silently drifting from the backend)."""
    scan = adapter.greek_scan(ILIAD_1_1, "hexameter")
    assert scan.ok
    assert scan.summary.startswith(ILIAD_SCAN_PATTERN)
    syl = adapter.greek_syllables("θάλασσα")
    assert syl.summary == "θά-λασ-σα"
    ipa = adapter.greek_ipa("λόγος", "attic")
    assert ipa.summary == "loɡos"
    pipe = adapter.greek_pipeline(ILIAD_1_1)
    assert pipe.rows[0]["lemma"] == "μῆνις"
    assert pipe.rows[0]["upos"] == "NOUN"


def test_pinned_strings_match_live_adapter() -> None:
    """The pins the Pilot tests assert on are the adapter's live output."""
    _pinned_strings_sanity()


async def _type(pilot, widget_id: str, text: str) -> None:
    """Focus an input and set its value, then let the change handlers run.

    The greek workbench debounces input by 0.12 s (so a fast typist doesn't re-run
    every backend per keystroke), so wait past the debounce for the render to land."""
    inp = pilot.app.screen.query_one(widget_id)
    inp.value = text
    await pilot.pause(0.2)


def test_scansion_tab_shows_known_iliad_pattern() -> None:
    """Typing Iliad 1.1 renders the known hexameter foot pattern in the scansion
    tab (not a crash, not an empty tab)."""

    async def body() -> None:
        from textual.widgets import Static

        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("g")  # switch to the Greek workbench
            await pilot.pause()
            await _type(pilot, "#greek-input", ILIAD_1_1)
            content = app.screen.query_one("#greek-scansion", Static).content
            assert ILIAD_SCAN_PATTERN in content
            # the six feet are named too (the first is a dactyl)
            assert "dactyl" in content

    _run(body())


def test_scansion_meter_selector_defaults_to_hexameter() -> None:
    """The scansion tab's meter selector starts on hexameter, so the default
    scan of a hexameter line succeeds."""

    async def body() -> None:
        from textual.widgets import Select, Static

        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("g")
            await pilot.pause()
            assert app.screen.query_one("#greek-meter", Select).value == "hexameter"
            await _type(pilot, "#greek-input", ILIAD_1_1)
            content = app.screen.query_one("#greek-scansion", Static).content
            assert ILIAD_SCAN_PATTERN in content

    _run(body())


def test_syllables_tab_shows_hyphenated_split() -> None:
    """Typing a word shows its hyphenated syllabification in the syllables tab."""

    async def body() -> None:
        from textual.widgets import Static

        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("g")
            await pilot.pause()
            await _type(pilot, "#greek-input", "θάλασσα")
            content = app.screen.query_one("#greek-syllables", Static).content
            assert content == "θά-λασ-σα"

    _run(body())


def test_syllables_tab_uses_first_word() -> None:
    """With a multi-word line the syllables tab splits the first word only."""

    async def body() -> None:
        from textual.widgets import Static

        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("g")
            await pilot.pause()
            await _type(pilot, "#greek-input", "θάλασσα καὶ γῆ")
            content = app.screen.query_one("#greek-syllables", Static).content
            assert content == "θά-λασ-σα"

    _run(body())


def test_pipeline_tab_shows_lemma() -> None:
    """The pipeline tab shows a token's lemma (μῆνιν -> μῆνις, a NOUN)."""

    async def body() -> None:
        from textual.widgets import Static

        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("g")
            await pilot.pause()
            await _type(pilot, "#greek-input", ILIAD_1_1)
            content = app.screen.query_one("#greek-pipeline", Static).content
            assert "μῆνις" in content
            assert "NOUN" in content
            assert "μῆνιν" in content

    _run(body())


def test_pipeline_tab_shows_sentence_number_for_multi_sentence_input() -> None:
    """The pipeline tab prefixes each token with its sentence number, so a
    multi-sentence line stays unambiguous: the per-token index restarts at each
    sentence, so two tokens both at index 1 are distinguished by ``0:`` vs ``1:``.
    Without the sentence prefix the two first-tokens would be indistinguishable."""

    async def body() -> None:
        from textual.widgets import Static

        # two sentences: the index restarts, so only the sentence number tells
        # 'θεός' (sentence 0) apart from 'λόγος' (sentence 1), both at index 1.
        line = "θεός. λόγος καὶ ἀρετή."
        rows = adapter.greek_pipeline(line).rows
        assert rows[0]["sentence"] == 0 and rows[0]["index"] == 1
        second_sentence = [r for r in rows if r["sentence"] == 1]
        assert second_sentence and second_sentence[0]["index"] == 1

        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("g")
            await pilot.pause()
            await _type(pilot, "#greek-input", line)
            content = app.screen.query_one("#greek-pipeline", Static).content
            # both sentence prefixes appear, on their respective first tokens
            assert "0:1" in content
            assert "1:1" in content
            # the first token of each sentence is rendered on its prefixed line
            lines = content.splitlines()
            assert any(ln.startswith("0:1") and "θεός" in ln for ln in lines)
            assert any(ln.startswith("1:1") and "λόγος" in ln for ln in lines)

    _run(body())


def test_ipa_tab_shows_transcription() -> None:
    """The IPA tab shows the reconstructed Attic transcription of the line."""

    async def body() -> None:
        from textual.widgets import Static

        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("g")
            await pilot.pause()
            await _type(pilot, "#greek-input", "λόγος")
            content = app.screen.query_one("#greek-ipa", Static).content
            assert content == "loɡos"

    _run(body())


def test_non_scanning_line_shows_friendly_error() -> None:
    """A prose line that does not fit the meter shows the adapter's friendly
    'does not scan' message in the scansion tab, not a traceback or crash."""

    async def body() -> None:
        from textual.widgets import Static

        prose = "λόγος καὶ ἀρετή"
        # confirm the adapter classifies this as a non-scanning line
        result = adapter.greek_scan(prose, "hexameter")
        assert not result.ok
        expected = result.error
        assert "does not scan" in expected

        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("g")
            await pilot.pause()
            await _type(pilot, "#greek-input", prose)
            content = app.screen.query_one("#greek-scansion", Static).content
            assert content == expected
            # the app is still alive: pipeline/syllables of the same line render
            pipe = app.screen.query_one("#greek-pipeline", Static).content
            assert "λόγος" in pipe

    _run(body())


def test_empty_input_shows_hint_not_error() -> None:
    """Before anything is typed, each tab shows the placeholder hint, not an
    error (empty input is ok, not a failure)."""

    async def body() -> None:
        from textual.widgets import Static

        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("g")
            await pilot.pause()
            for tab_id in ("#greek-pipeline", "#greek-scansion", "#greek-syllables", "#greek-ipa"):
                content = app.screen.query_one(tab_id, Static).content
                assert content == "type a line above"

    _run(body())


def test_changing_meter_rescan_shows_error_for_hexameter_line() -> None:
    """Switching the meter selector re-scans the current line: Iliad 1.1 scans as
    hexameter but not as trimeter, so choosing trimeter shows the friendly error."""

    async def body() -> None:
        from textual.widgets import Select, Static

        app = AegeanApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("g")
            await pilot.pause()
            await _type(pilot, "#greek-input", ILIAD_1_1)
            # hexameter: scans
            content = app.screen.query_one("#greek-scansion", Static).content
            assert ILIAD_SCAN_PATTERN in content
            # switch to trimeter and re-scan
            select = app.screen.query_one("#greek-meter", Select)
            select.value = "trimeter"
            await pilot.pause()
            content = app.screen.query_one("#greek-scansion", Static).content
            assert "does not scan" in content
            assert "trimeter" in content

    _run(body())
