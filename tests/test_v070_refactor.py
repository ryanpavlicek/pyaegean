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


def test_fts_sidecar_hosted_asset_schemas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify FTS5 sidecar indexing against real hosted JSON schemas (PG dict, LXX nested, DAMOS, SigLA)."""
    from aegean import search as srch

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))

    # 1. fts_index_path accepts plain str paths as well as Path objects
    str_idx = srch.fts_index_path(str(tmp_path / "sample.json"))
    assert str_idx == srch.fts_index_path(tmp_path / "sample.json")

    # 2. Hosted Patrologia Graeca schema: volumes is a dict keyed by vol_id with _info + pages
    pg_dict = {
        "_meta": {"version": 1},
        "volumes": {
            "PG073": {
                "_info": {
                    "vol_id": "PG073",
                    "author": "Cyril of Alexandria",
                    "title": "Commentary on the Gospel of John (vol. 6)",
                },
                "pages": [
                    {"page": "10", "text": "Ἐν ἀρχῇ ἦν ὁ Λόγος καὶ Θεὸς ἦν ὁ Λόγος."},
                ],
            }
        },
    }
    pg_gz = tmp_path / "patrologia-dict.json.gz"
    pg_gz.write_bytes(gzip.compress(json.dumps(pg_dict, ensure_ascii=False).encode("utf-8")))
    pg_hits = srch.search_text("λόγος", str(pg_gz), book="PG073")
    assert len(pg_hits) == 1
    assert pg_hits[0].doc_id == "PG073"
    assert pg_hits[0].ref == "PG073 p.10"
    assert pg_hits[0].meta["author"] == "Cyril of Alexandria"

    # 3. Hosted Swete LXX schema: books[code] has {"_info": ..., "verses": {vref: text}}
    lxx_nested = {
        "_meta": {"books": 1},
        "books": {
            "Ps": {
                "_info": {"title": "Psalms", "section": "Poetic"},
                "verses": {
                    "22.1": "Κύριος ποιμαίνει με, καὶ οὐδέν με ὑστερήσει.",
                    "22.2": "εἰς τόπον χλόης, ἐκεῖ με κατεσκήνωσεν.",
                },
            }
        },
    }
    lxx_gz = tmp_path / "lxx-nested.json.gz"
    lxx_gz.write_bytes(gzip.compress(json.dumps(lxx_nested, ensure_ascii=False).encode("utf-8")))
    lxx_hits = srch.search_text("ποιμαίνει", str(lxx_gz))
    assert len(lxx_hits) == 1
    assert lxx_hits[0].ref == "Ps 22.1"
    assert "{" not in lxx_hits[0].text
    assert lxx_hits[0].meta["title"] == "Psalms"

    # 4. Hosted DAMOS Linear B schema: documents carry raw tablet "content" + heading_short
    damos_json = {
        "_meta": {"name": "DAMOS", "version": 2},
        "documents": [
            {
                "id": "42",
                "heading": "PY Ta 711 (2)",
                "heading_short": "PY Ta 711",
                "site": "Pylos",
                "scribe": "2",
                "chronology": "LH IIIB",
                "content": ".1 o-wi-de pu2-ke-qi-ri wa-na-ka te-ke au-ke-wa da-mo-ko-ro",
            }
        ],
    }
    damos_p = tmp_path / "damos.json"
    damos_p.write_text(json.dumps(damos_json, ensure_ascii=False), encoding="utf-8")
    damos_hits = srch.search_text("wa-na-ka", str(damos_p))
    assert len(damos_hits) == 1
    assert damos_hits[0].ref == "PY Ta 711"
    assert damos_hits[0].meta["site"] == "Pylos"

    # 5. Hosted SigLA Linear A schema: documents carry sign-by-sign "attestations"
    sigla_json = {
        "_meta": {"title": "SigLA", "version": 2},
        "documents": [
            {
                "id": "HT 13",
                "site": "Haghia Triada",
                "period": "LM IB",
                "typology": "Tablet",
                "attestations": [
                    {"sign": "KU", "kind": "syllable", "word": 0},
                    {"sign": "RO", "kind": "syllable", "word": 0},
                    {"sign": "VIN", "kind": "logogram", "word": None},
                ],
            }
        ],
    }
    sigla_p = tmp_path / "sigla.json"
    sigla_p.write_text(json.dumps(sigla_json, ensure_ascii=False), encoding="utf-8")
    sigla_hits = srch.search_text("KU-RO", str(sigla_p))
    assert len(sigla_hits) == 1
    assert sigla_hits[0].doc_id == "HT 13"
    assert "KU-RO" in sigla_hits[0].text
    assert "VIN" in sigla_hits[0].text



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
