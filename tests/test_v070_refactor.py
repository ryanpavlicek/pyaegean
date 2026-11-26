"""Tests for the v0.70.0 architectural refactor (R1–R3):

- Declarative corpus catalog (``aegean.core.catalog``) as single source of truth
  for loaders, TUI metadata, CLI fetch hints, and Library Manager.
- Lazy SQLite FTS5 sidecar full-text search (``aegean.search``) with Greek
  diacritic folding, volume/book scoping, and automatic cache invalidation.
- Universal ``aegean.open()`` front door and fluent ``Corpus.search()`` /
  ``Corpus.export()`` methods.
- Unified CLI ``aegean find`` command and predictive target completion.
- Modular MCP server (29 tools) including path-rejection security invariant.
- Upgraded TUI ``BiblicalScreen`` (9 NT editions + ``LXX & Patristics`` / PG).
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

import pytest

import aegean
from aegean import mcp_server as m
from aegean.core import catalog
from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind


def test_declarative_catalog_drives_all_surfaces() -> None:
    from aegean.cli._data import _FETCH_HINTS
    from aegean.library import _BUNDLED_CORPORA, _DATASET_META
    from aegean.tui import data as tui_data

    assert len(catalog.CORPORA) == 30
    assert tui_data.CORPUS_IDS == catalog.tui_browsable_ids()
    assert tui_data._CORPUS_BLURB == catalog.tui_blurbs()
    assert tui_data.UNDECIPHERED == catalog.UNDECIPHERED_IDS

    bundled_ids = {row["id"] for row in _BUNDLED_CORPORA}
    assert bundled_ids == {c.id for c in catalog.CORPORA if c.bundled}

    for spec in catalog.CORPORA:
        if spec.asset_name:
            assert spec.asset_name in _DATASET_META
            if spec.fetch_hint:
                assert _FETCH_HINTS[spec.asset_name] == spec.fetch_hint


def test_fts5_search_on_json_gz_and_cache_invalidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    from aegean import search as srch

    # Build a synthetic gzipped Patrologia Graeca archive
    pg_payload = {
        "volumes": [
            {
                "id": "PG073",
                "author": "Cyril of Alexandria",
                "title": "Commentarii in Joannem",
                "pages": [
                    {"page": 10, "text": "Ἐν ἀρχῇ ἦν ὁ Λόγος καὶ ὁ Θεός."},
                    {"page": 11, "text": "Περὶ τῆς ἀγάπης καὶ τῆς ἀληθείας."},
                ],
            },
            {
                "id": "PG123",
                "author": "Theophylact",
                "title": "Enarratio in Evangelium Matthaei",
                "pages": [
                    {"page": 5, "text": "Ὁ Λόγος σὰρξ ἐγένετο ἐν τῷ κόσμῳ."},
                ],
            },
        ]
    }
    gz_path = tmp_path / "patrologia-graeca-corpus.json.gz"
    gz_path.write_bytes(gzip.compress(json.dumps(pg_payload, ensure_ascii=False).encode("utf-8")))

    # Diacritic-insensitive search ("λογος" matches "Λόγος")
    hits = srch.search_text("λογος", str(gz_path))
    assert len(hits) == 2
    assert {h.doc_id for h in hits} == {"PG073", "PG123"}

    # Scoped search to PG073 only
    pg73_hits = srch.search_text("λογος", str(gz_path), book="PG073")
    assert len(pg73_hits) == 1
    assert pg73_hits[0].ref == "PG073 p.10"

    # Sidecar index exists on disk and reuses cleanly
    idx = srch.fts_index_path(gz_path)
    assert idx.exists()

    # Modifying source file invalidates sidecar automatically
    pg_payload["volumes"][0]["pages"].append({"page": 12, "text": "Νέος λόγος σοφίας."})
    gz_path.write_bytes(gzip.compress(json.dumps(pg_payload, ensure_ascii=False).encode("utf-8")))
    st = gz_path.stat()
    os.utime(gz_path, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000))

    hits_after = srch.search_text("σοφιας", str(gz_path))
    assert len(hits_after) == 1
    assert hits_after[0].ref == "PG073 p.12"

    reclaimed = srch.clear_fts_cache()
    assert reclaimed > 0


def test_open_corpus_and_fluent_methods(tmp_path: Path) -> None:
    # 1. Registered corpus
    c = aegean.open("greek")
    assert len(c) == 5

    # 2. NT and LXX offline samples through universal aegean.open()
    john = aegean.open("John", ref="1.1-3", offline=True)
    assert len(john) == 1
    gen = aegean.open("Gen", ref="1.1-2", offline=True)
    assert len(gen) == 1

    # 3. Fluent Corpus.search() (diacritic-insensitive)
    hits = john.search("λογος")
    assert hits
    assert any("John.1.1" in h.ref for h in hits)

    # 4. Fluent Corpus.export() across JSON, DB, XML, Turtle, JSON-LD
    doc = Document(
        id="TEST1",
        script_id="greek",
        tokens=[Token(text="λόγος", kind=TokenKind.WORD)],
        lines=[[0]],
    )
    mini = Corpus([doc], script_id="greek")
    for name in ("out.json", "out.db", "out.xml", "out.ttl", "out.jsonld"):
        out = mini.export(tmp_path / name)
        assert out.exists() and out.stat().st_size > 0

    # Round-trip open() on .json and .xml
    assert len(aegean.open(tmp_path / "out.json")) == 1
    assert len(aegean.open(tmp_path / "out.xml")) == 1

    with pytest.raises(ValueError, match="unsupported export format"):
        mini.export(tmp_path / "out.bogus")


def test_cli_find_and_predictive_completion(tmp_path: Path) -> None:
    pytest.importorskip("typer")
    from typer.testing import CliRunner

    from aegean.cli import _build_app
    from aegean.cli._complete import complete_line

    app = _build_app()
    runner = CliRunner()

    # Search bundled offline Greek sample via CLI `aegean find`
    res = runner.invoke(app, ["find", "μηνιν", "greek", "--json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.stdout)
    assert data["count"] >= 1

    # Search NT offline sample
    res_nt = runner.invoke(app, ["find", "λογος", "nt", "--offline", "--json"])
    assert res_nt.exit_code == 0, res_nt.output
    assert json.loads(res_nt.stdout)["count"] >= 1

    # Predictive completion suggests targets for second positional arg of `find`
    import typer

    group = typer.main.get_command(app)
    cands = complete_line(group, "find λογος pat")
    values = [c.insert for c in cands]
    assert "patrologia" in values


def test_new_mcp_parity_tools_and_path_security() -> None:
    assert len(m.TOOLS) == 29
    assert "biblical_lxx" in m.__all__

    # Library status & search (read-only)
    st = m.library_status()
    assert "summary" in st and "packs" in st
    assert len(st["packs"]) == 10

    sr = m.library_search("patrologia")
    assert sr["count"] >= 1
    assert any(it["id"] == "patrologia-graeca-corpus" for it in sr["items"])

    # search_text works on bundled corpus
    hits = m.search_text("λογος", target="nt")
    assert hits["count"] >= 1

    # search_text strictly rejects filesystem paths (security invariant)
    bad = m.search_text("λογος", target="/etc/passwd")
    assert "error" in bad
    bad2 = m.search_text("λογος", target="corpus.json")
    assert "error" in bad2

    # Biblical catalog reflects 9 editions & 112 commentaries
    eds = m.biblical_catalog("editions")
    assert eds["count"] == 9
    comms = m.biblical_catalog("commentaries")
    assert comms["count"] == 112


def test_tui_biblical_screen_9_editions_and_pg_patristics() -> None:
    pytest.importorskip("textual")
    from aegean.tui.screens.bible import _EDITIONS

    ed_ids = [eid for _, eid in _EDITIONS]
    assert len(ed_ids) == 9
    for expected in ("nestle1904", "sblgnt", "srgnt", "bhp", "tisch", "wh", "byz", "antoniades", "tr"):
        assert expected in ed_ids

    from aegean.tui._bible_data import bible_lxx_and_catenae_text

    txt = bible_lxx_and_catenae_text("PG073")
    assert "PG073" in txt
    assert "11 Fathers / traditions" in txt
