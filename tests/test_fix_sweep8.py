"""Regression tests for the eighth (regression-focused) sweep, 0.19.10.

Five of these pin defects the 0.19.1-0.19.9 fix churn introduced (marked REGRESSION),
and each reproduces the finder's concrete failure scenario and asserts the corrected
output. The `data remove` on_disk regression is pinned in tests/test_cli_data_store.py
(where the CliRunner harness lives).
"""

from __future__ import annotations

import asyncio
import tempfile
import threading

import pytest


# ── R3 (regression, 0.19.2): clean_gloss over-dropped real "X of" glosses ─────
def test_clean_gloss_keeps_real_glosses_starting_with_a_derivation_prefix():
    """The _DERIVATION_ONLY guard must drop bare derivation pointers ("adverb of",
    "comp. of") but NOT a real meaning whose first word merely starts with one of
    those abbreviation letters ("composed of", "control of")."""
    from aegean.ai.grounding import clean_gloss

    for keep in ["composed of", "a company of", "a compound of", "control of",
                 "advantage of", "comprised of"]:
        assert clean_gloss(keep) == keep, keep
    for drop in ["adverb of", "comp. of", "a strengthd. form of",
                 "as if contr. from", "collateral form of"]:
        assert clean_gloss(drop) == "", drop
    # a real gloss with an inline Greek object still survives (cut at the Greek run)
    assert clean_gloss("σύνθετος: composed of ξύλων") == "composed of"


# ── R5 (regression, 0.19.7): analysis cache use-after-close across threads ────
def test_analysis_cache_survives_enable_disable_under_worker_threads():
    """Enabling cross-thread cache use (0.19.7) must not let enable()/disable()
    from one thread crash a memoized call in flight on another: a concurrent close
    degrades to a miss (recompute), never a ProgrammingError."""
    from aegean import cache

    @cache.memoize(version="1")
    def _sum(payload):
        return sum(payload["nums"])

    path_a = tempfile.mktemp(suffix=".sqlite")
    path_b = tempfile.mktemp(suffix=".sqlite")
    cache.enable(path_a)
    try:
        _sum({"nums": [1, 2, 3]})  # warm
        errors: list[str] = []

        def worker() -> None:
            try:
                for _ in range(150):
                    assert _sum({"nums": [1, 2, 3]}) == 6
            except Exception as exc:  # noqa: BLE001 — the whole point is to catch a crash
                errors.append(repr(exc))

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for _ in range(25):  # churn the connection closed under the workers
            cache.enable(path_b)
            cache.enable(path_a)
            cache.disable()
            cache.enable(path_a)
        for t in threads:
            t.join()
        assert errors == []
        assert _sum({"nums": [1, 2, 3]}) == 6  # still correct after the churn
    finally:
        cache.disable()


# ── TUI (regression, 0.19.1): open a corpus while already on the browser ──────
def test_tui_open_corpus_reconciles_when_already_on_the_corpus_screen():
    """Opening a different corpus from the palette while the corpus browser is
    already current must load it: switch_screen to the current screen posts no
    ScreenResume, so goto() drives the reconcile directly. 0.19.1's removal of the
    CorpusChanged message left this path silently showing the previous corpus."""
    pytest.importorskip("textual")
    from aegean.tui.app import AegeanApp
    from aegean.tui.screens.corpus import CorpusBrowserScreen
    from aegean.tui.widgets import DocTable

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.open_corpus("lineara")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CorpusBrowserScreen)
            assert screen._loaded_id == "lineara"
            assert screen.query_one("#corpus-docs", DocTable).row_count == 1721
            # open a DIFFERENT corpus while already on the corpus screen
            app.open_corpus("cypriot")
            await pilot.pause()
            assert app.state.selected_corpus == "cypriot"
            assert screen._loaded_id == "cypriot"  # reconciled, not stuck on lineara
            assert screen.query_one("#corpus-docs", DocTable).row_count == 180

    asyncio.new_event_loop().run_until_complete(body())


# ── F1 (fresh defect): persistent accent on imparisyllabic 3rd-decl nouns ─────
def test_persistent_accent_recedes_for_imparisyllabic_nouns():
    """A noun that gains a syllable in the oblique cases must keep its accent on the
    STEM syllable (counted from the start): σῶμα -> σώματος (antepenult), not the
    penult σωμάτος a from-the-end anchor produced."""
    from aegean.greek.accent_law import place_accent

    imparisyllabic = [
        ("σωματος", "σῶμα", "σώματος"),
        ("πραγματος", "πρᾶγμα", "πράγματος"),
        ("ῥητορος", "ῥήτωρ", "ῥήτορος"),
    ]
    for form, lemma, want in imparisyllabic:
        assert place_accent(form, recessive=False, lemma=lemma).form == want, form
    # parisyllabic nouns (constant syllable count) are unchanged, incl. the long-
    # ultima σωτῆρα recession that was already correct
    parisyllabic = [
        ("λογου", "λόγος", "λόγου"),
        ("ἀνθρωπου", "ἄνθρωπος", "ἀνθρώπου"),   # long ultima -> penult
        ("ἀνθρωπον", "ἄνθρωπος", "ἄνθρωπον"),   # short ultima -> antepenult
        ("θαλασσης", "θάλασσα", "θαλάσσης"),
    ]
    for form, lemma, want in parisyllabic:
        assert place_accent(form, recessive=False, lemma=lemma).form == want, form


# ── F2 (fresh defect): workbench import with a duplicate document id ──────────
def test_workbench_import_keys_extras_by_id_not_position():
    """from_workbench_export must attach each document's glyphs/transcription/images
    by id: from_records collapses duplicate ids (last wins), so a positional zip
    shifted every later document's extras onto the wrong id and dropped the tail."""
    import json
    import os

    from aegean.io import from_workbench_export

    data = [
        {"id": "HT13", "words": ["a-b"], "glyphs": "G_A", "transcription": "side a"},
        {"id": "HT13", "words": ["c-d"], "glyphs": "G_B", "transcription": "side b"},
        {"id": "HT14", "words": ["e-f"], "glyphs": "G_14", "transcription": "HT14 text"},
    ]
    fd, path = tempfile.mkstemp(suffix=".json")
    os.write(fd, json.dumps(data).encode("utf-8"))
    os.close(fd)
    try:
        corpus = from_workbench_export(path)
    finally:
        os.unlink(path)

    assert [d.id for d in corpus] == ["HT13", "HT14"]
    ht13, ht14 = corpus.get("HT13"), corpus.get("HT14")
    # HT13 keeps the LAST duplicate's extras (matching from_records dedup)
    assert ht13.glyphs == "G_B" and ht13.transcription == "side b"
    # HT14 keeps its OWN extras -- previously it got HT13 side-b's, shifted by one
    assert ht14.glyphs == "G_14" and ht14.transcription == "HT14 text"
