"""Tests for the unified Corpus & Text Library Manager across Python, CLI, REPL, and TUI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

import aegean
from aegean import library


# ── Python API: catalog, packs, resolution, missing-asset detection ──────────


def test_library_lazy_export_and_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    assert aegean.library is library

    snap = library.summary()
    assert snap["bundled_count"] == 5
    assert snap["downloaded_count"] == 0
    assert snap["installed_bytes"] == 0
    assert snap["categories"]["corpus"]["bundled"] == 5
    assert snap["categories"]["bible"]["total"] >= 7
    assert snap["categories"]["commentary"]["total"] >= 77
    assert snap["categories"]["work"]["total"] > 1500
    assert len(snap["packs"]) == 7


def test_list_items_categories_and_statuses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))

    bundled = library.list_items(status="bundled")
    assert {it.id for it in bundled} == {"lineara", "linearb", "cypriot", "cyprominoan", "greek"}
    assert all(it.installed and not it.removable for it in bundled)

    bible_items = library.list_items(category="bible")
    bible_ids = {it.id for it in bible_items}
    assert {
        "nt-corpus",
        "nt-editions",
        "nt-witnesses",
        "strongs-greek",
        "lxx-corpus",
        "apostolic-fathers-corpus",
        "pseudepigrapha-corpus",
    } <= bible_ids

    corpora = library.list_items(category="corpus")
    corpus_ids = {it.id for it in corpora}
    assert {
        "lineara",
        "damos-corpus",
        "sigla-corpus",
        "nt-corpus",
        "isicily-corpus",
        "aphrodisias-corpus",
        "crete-corpus",
        "byzantine-corpus",
        "homer-scholia-corpus",
        "patrologia-graeca-corpus",
    } <= corpus_ids

    comms = library.list_items(category="commentary")
    assert len(comms) >= 77

    lexica = library.list_items(category="lexicon")
    assert {"lsj-index", "middle-liddell-index", "abbott-smith-index"} <= {it.id for it in lexica}

    with pytest.raises(ValueError, match="unknown category"):
        library.list_items(category="nope")
    with pytest.raises(ValueError, match="unknown status"):
        library.list_items(status="nope")


def test_search_and_resolve_targets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))

    # Packs & aliases
    bib_pack = library.resolve_targets("biblical")
    assert [it.id for it in bib_pack] == [
        "nt-corpus",
        "nt-editions",
        "nt-witnesses",
        "strongs-greek",
        "lxx-corpus",
    ]
    assert [it.id for it in library.resolve_targets("bible")] == [it.id for it in bib_pack]

    # Friendly dataset & corpus aliases
    assert [it.id for it in library.resolve_targets("byz")] == ["nt-editions"]
    assert [it.id for it in library.resolve_targets("editions")] == ["nt-editions"]
    assert [it.id for it in library.resolve_targets("lxx")] == ["lxx-corpus"]
    assert [it.id for it in library.resolve_targets("strongs")] == ["strongs-greek"]
    assert [it.id for it in library.resolve_targets("witnesses")] == ["nt-witnesses"]
    assert [it.id for it in library.resolve_targets("damos")] == ["damos-corpus"]
    assert [it.id for it in library.resolve_targets("lsj")] == ["lsj-index"]

    # Literary works by title, ID, and author:<name>
    assert [it.id for it in library.resolve_targets("Iliad")] == ["tlg0012.tlg001"]
    assert [it.id for it in library.resolve_targets("tlg0012.tlg002")] == ["tlg0012.tlg002"]
    homer = library.resolve_targets("author:Homer")
    assert any(it.id == "tlg0012.tlg001" for it in homer)

    # Commentaries by book shorthand
    john_comms = library.resolve_targets("commentary:John")
    assert len(john_comms) >= 1
    assert all(it.category == "commentary" for it in john_comms)

    # Search across all categories
    hits = library.search("Iliad", limit=10)
    assert hits and hits[0].id == "tlg0012.tlg001"

    # Unknown target suggests close matches
    with pytest.raises(LookupError, match="did you mean"):
        library.resolve_targets("damso")


def test_missing_for_bible_and_corpus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))

    # Bundled John 1.1-5 in Nestle 1904 needs nothing
    assert library.missing_for_bible(tab="interlinear", edition="nestle1904", book="John", ref="1.1-5") == []
    # Byzantine Majority needs nt-editions
    miss_byz = library.missing_for_bible(tab="interlinear", edition="byz", book="John", ref="1.1-5")
    assert [m.id for m in miss_byz] == ["nt-editions"]
    # Non-bundled NT book needs nt-corpus
    miss_rom = library.missing_for_bible(tab="interlinear", edition="nestle1904", book="Rom", ref="8.28")
    assert [m.id for m in miss_rom] == ["nt-corpus"]
    # Bundled LXX Gen 1.1 needs nothing; Gen 2.1 needs lxx-corpus
    assert library.missing_for_bible(tab="interlinear", edition="nestle1904", book="Gen", ref="1.1-5") == []
    miss_lxx = library.missing_for_bible(tab="interlinear", edition="nestle1904", book="Gen", ref="2.1-3")
    assert [m.id for m in miss_lxx] == ["lxx-corpus"]
    # Witnesses tab needs nt-witnesses
    assert [m.id for m in library.missing_for_bible(tab="witnesses")] == ["nt-witnesses"]

    # Corpus check (all 5 bundled corpora including linearb report None)
    assert library.missing_for_corpus("lineara") is None
    assert library.missing_for_corpus("linearb") is None
    miss_damos = library.missing_for_corpus("damos")
    assert miss_damos is not None and miss_damos.id == "damos-corpus"


def test_install_and_remove_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    store = tmp_path / "pyaegean"
    store.mkdir(parents=True, exist_ok=True)

    def fake_fetch(name: str, **_kwargs: Any) -> Path:
        spec = aegean.data._REMOTE[name]
        target = aegean.data.on_disk_paths(spec, store)[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fake-data-payload" * 100)
        return target

    monkeypatch.setattr(aegean.data, "fetch", fake_fetch)

    # Install nt-editions via friendly alias 'byz'
    res = library.install("byz")
    assert len(res) == 1
    assert res[0].id == "nt-editions"
    assert res[0].status == "installed"
    assert res[0].bytes and res[0].bytes > 0

    # Idempotent repeat install
    again = library.install("nt-editions")
    assert again[0].status == "already_installed"

    # Bundled item cannot be removed
    b_rem = library.remove("lineara")
    assert b_rem[0].status == "bundled"

    # Remove nt-editions cleanly
    rem = library.remove("editions")
    assert rem[0].status == "removed"
    assert rem[0].bytes_reclaimed > 0
    assert library.get_item("nt-editions") is not None
    assert not library.get_item("nt-editions").installed  # type: ignore[union-attr]


# ── CLI & predictive completion ──────────────────────────────────────────────


def test_cli_library_and_bible_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pytest.importorskip("typer")
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    runner = CliRunner()
    app = _build_app()

    r_status = runner.invoke(app, ["library", "status", "--json"])
    assert r_status.exit_code == 0, r_status.output
    data = json.loads(r_status.output)
    assert data["bundled_count"] == 5
    assert len(data["packs"]) == 7

    r_packs = runner.invoke(app, ["library", "packs", "--json"])
    assert r_packs.exit_code == 0, r_packs.output
    packs = json.loads(r_packs.output)
    assert {p["id"] for p in packs} == {
        "biblical",
        "patristic",
        "aegean",
        "epigraphy",
        "literary",
        "lexica",
        "neural",
    }

    r_search = runner.invoke(app, ["library", "search", "Iliad", "--json"])
    assert r_search.exit_code == 0, r_search.output
    hits = json.loads(r_search.output)
    assert hits and hits[0]["id"] == "tlg0012.tlg001"

    r_bible_status = runner.invoke(app, ["bible", "status", "--json"])
    assert r_bible_status.exit_code == 0, r_bible_status.output
    bdata = json.loads(r_bible_status.output)
    assert bdata["pack"]["id"] == "biblical"
    assert len(bdata["bundles"]) == 5


def test_predictive_completion_for_library_and_bible_install() -> None:
    pytest.importorskip("typer")
    from typer.main import get_command

    from aegean.cli import _build_app
    from aegean.cli._complete import complete_line

    group = get_command(_build_app())

    c1 = complete_line(group, "library install bib")
    assert any(item.insert == "biblical" for item in c1)

    c2 = complete_line(group, "library list c")
    inserts = {item.insert for item in c2}
    assert {"corpus", "commentary"} <= inserts

    c3 = complete_line(group, "bible install ed")
    assert any(item.insert == "editions" for item in c3)


# ── TUI integration: Biblical inline download, Corpus inline download, LibraryScreen ──


def _run(coro: Any) -> None:
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


def test_tui_bible_inline_download_for_byzantine_edition(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("textual")
    from textual.containers import Horizontal
    from textual.widgets import Button, Select

    from aegean.tui.app import AegeanApp
    from aegean.tui.screens.bible import BiblicalScreen

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    store = tmp_path / "pyaegean"
    store.mkdir(parents=True, exist_ok=True)
    installed_targets: list[str] = []

    def fake_fetch(name: str, **_kwargs: Any) -> Path:
        installed_targets.append(name)
        spec = aegean.data._REMOTE[name]
        target = aegean.data.on_disk_paths(spec, store)[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"{}")
        return target

    monkeypatch.setattr(aegean.data, "fetch", fake_fetch)

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            app.goto("bible")
            await pilot.pause()
            assert isinstance(app.screen, BiblicalScreen)

            # Default John 1.1-5 in Nestle 1904 is bundled -> fetch bar stays hidden
            bar = app.screen.query_one("#bible-fetch-bar", Horizontal)
            assert bar.has_class("hidden")

            # Switching to Byzantine Majority reveals inline download bar for nt-editions
            sel = app.screen.query_one("#bible-edition", Select)
            sel.value = "byz"
            await pilot.pause()
            assert not bar.has_class("hidden")
            btn = app.screen.query_one("#bible-fetch-one", Button)
            assert "nt-editions" in str(btn.label)

            # Clicking the inline Download button installs nt-editions and hides the bar
            await pilot.click("#bible-fetch-one")
            await pilot.pause(0.3)
            assert "nt-editions" in installed_targets
            assert bar.has_class("hidden")

    _run(body())


def test_tui_corpus_inline_download_for_uninstalled_corpus(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("textual")
    from textual.containers import Horizontal

    from aegean.tui.app import AegeanApp
    from aegean.tui.screens.corpus import CorpusBrowserScreen

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            app.open_corpus("damos")
            await pilot.pause()
            assert isinstance(app.screen, CorpusBrowserScreen)
            bar = app.screen.query_one("#corpus-download-bar", Horizontal)
            assert not bar.has_class("hidden")

    _run(body())


def test_tui_library_screen_mounts_and_filters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("textual")
    from textual.widgets import DataTable, Input

    from aegean.tui.app import AegeanApp
    from aegean.tui.screens.library import LibraryScreen

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            assert isinstance(app.screen, LibraryScreen)

            packs_tbl = app.screen.query_one("#lib-packs-table", DataTable)
            assert packs_tbl.row_count == 7

            installed_tbl = app.screen.query_one("#lib-installed-table", DataTable)
            assert installed_tbl.row_count == 5  # the 5 bundled corpora

            # Filter narrows packs table to matching packs
            search_box = app.screen.query_one("#lib-search", Input)
            search_box.value = "biblical"
            await pilot.pause()
            assert packs_tbl.row_count == 2  # biblical + patristic (mentions biblical commentaries)

            search_box.value = "aegean"
            await pilot.pause()
            assert packs_tbl.row_count == 1

    _run(body())
