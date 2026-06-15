"""The MCP server tools (aegean.mcp_server).

The tool functions are plain callables, tested directly here (no MCP runtime needed); the
FastMCP build is gated behind the [mcp] dependency."""

from __future__ import annotations

import pytest

from aegean import mcp_server as m


def test_list_corpora() -> None:
    names = m.list_corpora()
    assert "lineara" in names and "nt" in names


def test_corpus_info() -> None:
    info = m.corpus_info("lineara")
    assert info["documents"] == 1721
    assert info["script_id"] == "lineara"
    assert "Godart" in info["citation"]


def test_show_document() -> None:
    doc = m.show_document("lineara", "HT13")
    assert doc["id"] == "HT13"
    assert doc["lines"] and isinstance(doc["lines"][0], list)
    assert "error" in m.show_document("lineara", "NOPE")


def test_search_signs() -> None:
    hits = {h["word"] for h in m.search_signs("lineara", "KU-*-RO")}
    assert "KU-MA-RO" in hits


def test_balance_accounts() -> None:
    rows = m.balance_accounts("lineara", "HT13")
    assert rows and rows[0]["doc_id"] == "HT13"
    assert {"stated_total", "computed_sum", "balances"} <= set(rows[0])


def test_greek_pipeline() -> None:
    recs = m.greek_pipeline("ἐν ἀρχῇ ἦν ὁ λόγος.")
    assert recs and {"text", "upos", "lemma"} <= set(recs[0])
    assert recs[0]["text"] == "ἐν"


def test_greek_scan() -> None:
    ok = m.greek_scan("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ", "hexameter")
    assert ok["scans"] is True and "—" in ok["pattern"]
    sapphic = m.greek_scan("φαίνεταί μοι κῆνος ἴσος θέοισιν", "sapphic_hendecasyllable")
    assert sapphic["scans"] is True
    bad = m.greek_scan("ἐν ἀρχῇ ἦν", "hexameter")
    assert bad["scans"] is False and "error" in bad


def test_koine_gloss() -> None:
    g = m.koine_gloss("λόγος")
    assert g is not None and g["strongs"] == "3056" and "word" in g["gloss"]
    assert m.koine_gloss("zzznotgreek") is None


def test_build_server_registers_tools() -> None:
    pytest.importorskip("mcp")
    server = m.build_server()
    assert server is not None
    assert len(m.TOOLS) == 8  # the registered tool surface
