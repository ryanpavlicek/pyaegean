"""Tests for the 8 categorized Ancient/Patristic/Byzantine Greek collections and first-class LXX parity."""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import pytest

import aegean
from aegean import greek
from aegean.greek import bible as bib


# ── 1. Offline discovery & integrity of all 8 Greek collections (3,844 works) ──


def test_collections_offline_index_and_license_purity() -> None:
    cols = greek.collections()
    assert len(cols) == 8
    by_id = {c["id"]: c for c in cols}
    assert set(by_id) == {
        "chrysostom",
        "church-fathers-early",
        "church-fathers-late",
        "classical-greek",
        "hellenistic-greek",
        "imperial-greek",
        "late-antique-greek",
        "byzantine-lit",
    }
    assert by_id["chrysostom"]["works"] == 155
    assert by_id["chrysostom"]["category"] == "patristics"
    assert sum(c["works"] for c in cols) == 3844

    # Verify zero NonCommercial or proprietary contamination across all 3,844 indexed works
    all_works = greek.collection_works()
    assert len(all_works) == 3844
    for w in all_works:
        lic = w["license"].upper()
        assert not re.search(r"\bNC\b|BY-NC|NONCOMMERCIAL|ALL RIGHTS RESERVED", lic), w

    # Chrysostom search & resolution offline
    matthew = greek.resolve_collection_work("ogc002060")
    assert matthew["collection"] == "chrysostom"
    assert "Matthaeum" in matthew["title"]
    assert greek.resolve_collection_work("chrysostom:In Matthaeum")["work_id"] == "ogc002060"

    # Author search across collections (Patristics, Classical, Byzantine)
    basil = greek.collection_works("church-fathers-early", author="Basilius")
    assert len(basil) >= 20
    anna = greek.collection_works("byzantine-lit", query="Alexias")
    assert len(anna) == 1
    plato = greek.collection_works("classical-greek", author="Plato")
    assert len(plato) >= 30


# ── 2. Synthetic collection bundle load, aegean.open(), and FTS5 search ────────


def test_collection_bundle_load_open_commentary_and_fts5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.scripts.greek import _collections as col_mod

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    col_mod._BUNDLE_CACHE.clear()

    # Build a synthetic chrysostom-corpus.json.gz on disk inside the temp cache
    payload = {
        "_meta": {
            "schema": "aegean-greek-collection/1",
            "collection": "chrysostom",
            "title": "John Chrysostom Complete Open Greek Corpus",
            "license": "CC BY-SA 4.0 / CC BY 4.0 / Public Domain",
            "source_repo": "https://github.com/open-greek/open-greek-corpus",
            "source_release": "corpus-2026-11-26",
        },
        "works": {
            "ogc002060": {
                "_info": {
                    "work_id": "ogc002060",
                    "author": "Joannes Chrysostomus",
                    "title": "In Matthaeum (Homiliae 1-90)",
                    "tlg": "tlg2062.tlg152",
                    "tokens": 12,
                    "source": "cgpg",
                    "license": "CC-BY-4.0",
                    "correction": "auto-corrected",
                    "period": "4th–5th c. CE",
                },
                "passages": [
                    ["pg57_0027.1", "Ἡ ἀγάπη οὐδέποτε πίπτει ἐν τῇ ἐκκλησίᾳ."],
                    ["pg57_0028.2", "Μακάριοι οἱ πτωχοὶ τῷ πνεύματι."],
                ],
            }
        },
    }
    spec = aegean.data._REMOTE["chrysostom-corpus"]
    gz_path = aegean.data.on_disk_paths(spec, aegean.data.cache_dir())[0]
    gz_path.parent.mkdir(parents=True, exist_ok=True)
    gz_path.write_bytes(gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8")))

    # Load via load_collection_work, aegean.open("ogc..."), and aegean.open("chrysostom:...")
    c1 = greek.load_collection_work("ogc002060", offline=True)
    assert len(c1) == 1
    assert c1.documents[0].id == "ogc002060"
    assert "Joannes Chrysostomus" in (c1.documents[0].meta.name or "")
    assert any("license=CC-BY-4.0" in n for n in c1.documents[0].meta.notes)

    c2 = aegean.open("ogc002060", offline=True)
    assert len(c2) == 1 and len(c2.documents[0].tokens) == len(c1.documents[0].tokens)

    c3 = aegean.open("chrysostom:In Matthaeum", offline=True)
    assert c3.documents[0].id == "ogc002060"

    # Patristic commentary integration for Chrysostom (kind="chrysostom" / work_id="ogc002060")
    excerpts = bib.commentary_excerpt("Matt", work_id="ogc002060", query="αγαπη")
    assert len(excerpts) == 1
    assert excerpts[0].kind == "chrysostom"
    assert excerpts[0].section_id == "pg57_0027.1"
    assert "ἀγάπη" in excerpts[0].text

    comm_corp = bib.load_commentary("Matt", kind="chrysostom")
    assert comm_corp.documents[0].id == "ogc002060"

    # FTS5 search over collection & scoped to ogc002060
    hits = aegean.search.search_text("πτωχοι", "chrysostom", offline=True)
    assert len(hits) == 1
    assert hits[0].doc_id == "ogc002060"
    assert hits[0].ref == "ogc002060 pg57_0028.2"

    scoped = aegean.search.search_text("αγαπη", "ogc002060", offline=True)
    assert len(scoped) == 1 and scoped[0].ref == "ogc002060 pg57_0027.1"

    # Library search finds individual Chrysostom works offline and reflects installed status
    lib_hits = aegean.library.search("ogc002060")
    assert lib_hits and lib_hits[0].id == "ogc002060"
    assert lib_hits[0].installed is True
    assert lib_hits[0].asset_name == "chrysostom-corpus"

    col_mod._BUNDLE_CACHE.clear()


# ── 3. First-Class Septuagint (LXX) Parity ─────────────────────────────────────


def test_lxx_registered_loader_inline_refs_mt_psalms_and_interlinear(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.greek.bible import _lxx as lxx_mod

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    monkeypatch.setattr(lxx_mod, "_LXX_CACHE", None)

    # 1. aegean.load("lxx") works offline just like aegean.load("nt") (bundled sample fallback)
    monkeypatch.setattr(lxx_mod, "_load_lxx_bundle", lambda *, allow_fetch=True, force=False: None)
    lxx_corp = aegean.load("lxx")
    assert len(lxx_corp) == 2  # Gen 1 + Ps 22
    assert {d.id for d in lxx_corp} == {"Gen 1", "Ps 22"}

    # 2. Inline passage strings & Masoretic Psalm numbering ("MT Ps 23" -> LXX Ps 22!)
    gen = bib.load_lxx("Gen 1:1-2", offline=True)
    assert len(gen) == 1
    assert {t.annotations["ref"] for t in gen.documents[0].tokens} == {"Gen.1.1", "Gen.1.2"}

    ps23 = bib.load_lxx("Ps", ref="23.1-2", numbering="mt", offline=True)
    assert ps23.documents[0].id == "Ps 22"
    assert "MT Ps 23" in (ps23.documents[0].meta.name or "")
    assert ps23.documents[0].tokens[0].annotations["ref"] == "Ps.22.1"
    assert ps23.documents[0].tokens[0].annotations["mt_ref"] == "MT Ps.23.1"

    ps23_inline = bib.load_lxx("MT Ps 23:1-3", offline=True)
    assert ps23_inline.documents[0].id == "Ps 22"
    assert ps23_inline.documents[0].tokens[0].annotations["mt_ref"] == "MT Ps.23.1"

    # 3. aegean.open("Gen 1:1-2", offline=True) works identically to aegean.open("John 1:1-2")
    open_gen = aegean.open("Gen 1:1-2", offline=True)
    assert open_gen.documents[0].id == "Gen 1"

    # 4. Automatic offline interlinear enrichment (tagged annotation_source="auto-lexicon")
    il = bib.load_lxx("Gen 1:1-2", interlinear=True, offline=True)
    toks = il.documents[0].tokens
    assert all(t.annotations.get("annotation_source") == "auto-lexicon" for t in toks)
    theos = next(t for t in toks if "θε" in t.text.lower())
    assert theos.annotations["lemma"] == "θεός"
    assert theos.annotations["strongs"] == "G2316"
    assert "God" in theos.annotations["gloss"]
    # Unaccented ALL-CAPS opening "ΕΝ" must resolve to ADP (not fallback NOUN)
    en_tok = next(t for t in toks if t.text == "ΕΝ")
    assert en_tok.annotations["lemma"] == "ἐν"
    assert en_tok.annotations["morph"] == "ADP"

    # 5. search_bible() auto-detects LXX books and supports corpus="both"
    lxx_hits = bib.search_bible("φῶς", book="Gen", offline=True)
    assert len(lxx_hits) >= 2 and all(h.book == "Gen" for h in lxx_hits)

    both_hits = bib.search_bible("φῶς", corpus="both", offline=True)
    books_seen = {h.book for h in both_hits}
    assert "John" in books_seen and "Gen" in books_seen

    # 6. word_study() includes LXX occurrences alongside NT occurrences
    ws = bib.word_study("φῶς", offline=True)
    assert ws.total_occurrences >= 1
    assert ws.lxx_total >= 2
    assert "Gen" in ws.lxx_by_book
    assert "lxx_total" in ws.to_dict()

    # 7. Ecclesiastes (56th book) resolves cleanly and works with synthetic v2 bundle
    assert bib.resolve_lxx_book("Eccl").work_id == "tlg0527.tlg030"
    assert bib.resolve_lxx_book("Qoheleth").name == "Eccl"
    fake_v2 = {
        "_meta": {"books": 56, "verses": 2},
        "books": {
            "Eccl": {
                "_info": {"name": "Eccl", "title": "Ecclesiastes", "work_id": "tlg0527.tlg030"},
                "verses": {
                    "1.2": "Ματαιότης ματαιοτήτων, εἶπεν ὁ ἐκκλησιαστής, ματαιότης ματαιοτήτων, τὰ πάντα ματαιότης.",
                },
            }
        },
    }
    monkeypatch.setattr(lxx_mod, "_load_lxx_bundle", lambda *, allow_fetch=True, force=False: fake_v2)
    eccl = bib.load_lxx("Eccl 1:2", offline=True)
    assert eccl.documents[0].id == "Eccl 1"
    assert "Ματαιότης" in " ".join(t.text for t in eccl.documents[0].tokens)


def test_cli_greek_collections_and_bible_lxx_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("typer")
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    runner = CliRunner()
    app = _build_app()

    # 1. `aegean greek collections --json` lists all 8 collections offline
    r_cols = runner.invoke(app, ["greek", "collections", "--json"])
    assert r_cols.exit_code == 0, r_cols.output
    data = json.loads(r_cols.stdout)
    assert len(data["collections"]) == 8

    # 2. `aegean greek collections chrysostom --query Matthaeum --json`
    r_ch = runner.invoke(app, ["greek", "collections", "chrysostom", "--query", "Matthaeum", "--json"])
    assert r_ch.exit_code == 0, r_ch.output
    ch_data = json.loads(r_ch.stdout)
    assert any(w["work_id"] == "ogc002060" for w in ch_data["works"])

    # 3. `aegean bible read Ps 23 --mt --interlinear --offline --json`
    r_ps = runner.invoke(app, ["bible", "read", "Ps", "23:1", "--mt", "--interlinear", "--offline", "--json"])
    assert r_ps.exit_code == 0, r_ps.output
    ps_data = json.loads(r_ps.stdout)
    assert ps_data["source"] == "lxx"
    assert ps_data["numbering"] == "mt"
    assert ps_data["verses"][0]["ref"] == "Ps.22.1"
    assert ps_data["verses"][0]["tokens"][0]["mt_ref"] == "MT Ps.23.1"
    assert ps_data["verses"][0]["tokens"][0]["annotation_source"] == "auto-lexicon"

    # 4. `aegean bible search φῶς --corpus both --offline --json`
    r_both = runner.invoke(app, ["bible", "search", "φῶς", "--corpus", "both", "--offline", "--json"])
    assert r_both.exit_code == 0, r_both.output
    both_hits = json.loads(r_both.stdout)
    assert {"John", "Gen"} <= {h["book"] for h in both_hits}

    # 5. `aegean bible commentary --kind chrysostom --json` returns all 26 Chrysostom series
    r_comm = runner.invoke(app, ["bible", "commentary", "--kind", "chrysostom", "--json"])
    assert r_comm.exit_code == 0, r_comm.output
    assert len(json.loads(r_comm.stdout)) == 26


def test_tui_biblical_screen_has_dedicated_lxx_and_patristics_tabs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pytest.importorskip("textual")
    import asyncio

    from textual.widgets import Input, Static, TabbedContent

    from aegean.tui.app import AegeanApp
    from aegean.tui.screens.bible import BiblicalScreen

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))

    async def body() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            await pilot.press("b")
            await pilot.pause()
            assert isinstance(app.screen, BiblicalScreen)

            tabs = app.screen.query_one("#bible-tabs", TabbedContent)
            # Both dedicated Septuagint (LXX) and Patristics tabs exist
            tabs.active = "tab-bible-lxx"
            await pilot.pause()
            lxx_in = app.screen.query_one("#bible-lxx-filter", Input)
            lxx_in.value = "MT Ps 23:1-2"
            await pilot.pause()
            lxx_txt = str(app.screen.query_one("#bible-lxx", Static).render())
            assert "Κύριος ποιμαίνει" in lxx_txt

            tabs.active = "tab-bible-patristics"
            await pilot.pause()
            pat_in = app.screen.query_one("#bible-patristics-filter", Input)
            pat_in.value = "Chrysostom"
            await pilot.pause()
            pat_txt = str(app.screen.query_one("#bible-patristics", Static).render())
            assert "ogc002060" in pat_txt
            assert "John Chrysostom" in pat_txt

    asyncio.run(body())
