"""The MCP server tools (aegean.mcp_server).

The tool functions are plain callables, tested directly here (no MCP runtime needed); the
FastMCP build and wire-level contract are gated behind the [mcp] dependency. The shared
error convention across every tool: a domain miss (unknown corpus / document / work /
dictionary / style / query field) returns a ``{"error": ...}`` payload with a did-you-mean
hint (for a work, the greek_catalog pointer) and never raises."""

from __future__ import annotations

import pytest

from aegean import mcp_server as m

# ── the corpus tools ─────────────────────────────────────────────────────────


def test_list_corpora() -> None:
    names = m.list_corpora()
    assert "lineara" in names and "nt" in names
    assert names == sorted(names)


def test_corpus_info() -> None:
    info = m.corpus_info("lineara")
    assert info["documents"] == 1721
    assert info["script_id"] == "lineara"
    assert "Godart" in info["citation"]


def test_corpus_info_forgives_case() -> None:
    assert m.corpus_info("LINEARA")["documents"] == 1721


def test_unknown_corpus_error_convention() -> None:
    """Every corpus-taking tool returns {"error": ...} with a suggestion, never raises."""
    for result in (
        m.corpus_info("linera"),
        m.show_document("linera", "HT13"),
        m.search_signs("linera", "KU-*"),
        m.balance_accounts("linera"),
        m.query_corpus("linera", []),
        m.cite_corpus("linera"),
        m.geo_sites("linera"),
    ):
        assert isinstance(result, dict)
        assert "unknown corpus 'linera'" in result["error"]
        assert "'lineara'" in result["error"]  # the did-you-mean hint
        assert "cypriot" in result["error"]  # the available-names list


def test_show_document() -> None:
    doc = m.show_document("lineara", "HT13")
    assert doc["id"] == "HT13"
    assert doc["lines"] and isinstance(doc["lines"][0], list)


def test_show_document_forgives_case() -> None:
    assert m.show_document("lineara", "ht13")["id"] == "HT13"


def test_show_document_miss_offers_close_ids() -> None:
    miss = m.show_document("lineara", "13")
    assert "no document '13' in 'lineara'" in miss["error"]
    assert "HT13" in miss["error"]  # close: ... hint
    no_close = m.show_document("lineara", "NOPE")
    assert "no document 'NOPE'" in no_close["error"]
    assert "close:" not in no_close["error"]


def test_search_signs() -> None:
    hits = m.search_signs("lineara", "KU-*-RO")
    assert isinstance(hits, list)
    assert {h["word"] for h in hits} == {"KU-MA-RO"}


def test_search_signs_limit_zero_is_unlimited() -> None:
    # 'KU-*' matches 12 words in the bundled Linear A corpus.
    all_hits = m.search_signs("lineara", "KU-*", limit=0)
    assert isinstance(all_hits, list) and len(all_hits) == 12
    assert m.search_signs("lineara", "KU-*", limit=-1) == all_hits
    capped = m.search_signs("lineara", "KU-*", limit=3)
    assert isinstance(capped, list) and len(capped) == 3
    assert capped == all_hits[:3]


def test_balance_accounts() -> None:
    rows = m.balance_accounts("lineara", "HT13")
    assert isinstance(rows, list)
    # The MCP tool shares aegean._view's row shape with the CLI and TUI, so the
    # three surfaces cannot drift (parity guardrail).
    assert rows and rows[0]["doc"] == "HT13"
    assert {"doc", "marker", "stated", "computed", "difference", "items", "balances"} == set(rows[0])
    import aegean
    from aegean._view import balance_rows

    assert rows == balance_rows(aegean.load("lineara").get("HT13"))
    # Forgiving doc resolution reaches this tool too.
    assert m.balance_accounts("lineara", "ht13") == rows


def test_balance_accounts_unknown_doc_is_an_error_not_empty() -> None:
    miss = m.balance_accounts("lineara", "NOPE")
    assert isinstance(miss, dict)
    assert "no document 'NOPE' in 'lineara'" in miss["error"]


# ── query_corpus ─────────────────────────────────────────────────────────────


def test_query_corpus_inscriptions() -> None:
    res = m.query_corpus(
        "lineara",
        [
            {"field": "site-is", "value": "Haghia Triada"},
            {"field": "ins-contains-word", "value": "KU-RO"},
        ],
    )
    assert res["total_inscriptions"] == 32
    assert len(res["inscriptions"]) == 32
    assert "HT13" in res["inscriptions"]
    assert res["description"] == "Site is: Haghia Triada · Contains exact word: KU-RO"
    assert "Godart" in res["citation"]  # the exact-subset citation travels with the result


def test_query_corpus_limit_caps_lists_not_totals() -> None:
    res = m.query_corpus(
        "lineara", [{"field": "site-is", "value": "Haghia Triada"}], limit=5
    )
    assert res["total_inscriptions"] == 1110
    assert len(res["inscriptions"]) == 5


def test_query_corpus_words_document_frequency() -> None:
    res = m.query_corpus(
        "lineara", [{"field": "word-prefix", "value": "KU"}], output_kind="words", limit=0
    )
    assert res["total_words"] == 33
    assert {"word": "KU-RO", "count": 34} in res["words"]  # 34 = document frequency


def test_query_corpus_negate() -> None:
    everything = m.query_corpus("lineara", [])
    assert everything["total_inscriptions"] == 1721
    negated = m.query_corpus(
        "lineara", [{"field": "site-is", "value": "Haghia Triada", "negate": True}]
    )
    assert negated["total_inscriptions"] == 1721 - 1110


def test_query_corpus_bad_input_errors() -> None:
    bad_field = m.query_corpus("lineara", [{"field": "site", "value": "x"}])
    assert "unknown field 'site'" in bad_field["error"]
    assert "'site-is'" in bad_field["error"]  # did-you-mean
    assert "word-sign-pattern" in bad_field["error"]  # the full field list

    bad_kind = m.query_corpus("lineara", [], output_kind="documents")
    assert "unknown output_kind 'documents'" in bad_kind["error"]

    bad_row = m.query_corpus("lineara", [{"field": "site-is"}])
    assert "'field' and 'value'" in bad_row["error"]

    bad_number = m.query_corpus("lineara", [{"field": "word-min-syllables", "value": "abc"}])
    assert "takes a number" in bad_number["error"]

    bad_connector = m.query_corpus(
        "lineara", [{"field": "site-is", "value": "x", "connector": "xor"}]
    )
    assert "unknown connector 'xor'" in bad_connector["error"]


def test_query_corpus_coerces_string_numbers() -> None:
    res = m.query_corpus(
        "lineara", [{"field": "word-min-syllables", "value": "5"}], output_kind="words"
    )
    assert "error" not in res
    assert res["total_words"] > 0


# ── cite_corpus ──────────────────────────────────────────────────────────────


def test_cite_corpus_plain() -> None:
    res = m.cite_corpus("lineara")
    assert res["documents"] == 1721
    assert "Godart" in res["citation"]


def test_cite_corpus_styles() -> None:
    bib = m.cite_corpus("lineara", style="bibtex")
    assert bib["citation"].startswith("@misc") and "Godart" in bib["citation"]
    apa = m.cite_corpus("lineara", style="apa")
    assert "Godart" in apa["citation"]


def test_cite_corpus_subset() -> None:
    res = m.cite_corpus("lineara", site="Haghia Triada")
    assert res["documents"] == 1110
    assert res["filters"] == {"site": "Haghia Triada"}
    assert "Haghia Triada" in res["citation"]  # the subset note names the filter
    assert "1110 of 1721" in res["citation"]


def test_cite_corpus_bad_style() -> None:
    res = m.cite_corpus("lineara", style="mla")
    assert "'plain', 'bibtex', or 'apa'" in res["error"]


# ── geo_sites ────────────────────────────────────────────────────────────────


def test_geo_sites_coordinates() -> None:
    res = m.geo_sites("lineara")
    assert res["located"] == 52 and res["total_sites"] == 52
    ht = next(r for r in res["sites"] if r["site"] == "Haghia Triada")
    assert ht["lat"] == 35.06 and ht["lon"] == 24.79
    assert ht["pleiades"] == 589672
    assert ht["pleiades_uri"] == "https://pleiades.stoa.org/places/589672"
    assert ht["contested"] is None


def test_geo_sites_word_attestations() -> None:
    res = m.geo_sites("lineara", word="ku-ro")  # case-insensitive
    counts = {r["site"]: r["count"] for r in res["sites"]}
    assert counts == {"Haghia Triada": 32, "Phaistos": 1, "Zakros": 1}
    missing = m.geo_sites("lineara", word="ZZZ-ZZZ")
    assert missing["sites"] == [] and "not attested" in missing["note"]


def test_geo_sites_no_findspot_corpus_gets_hint() -> None:
    res = m.geo_sites("greek")
    assert res["sites"] == [] and res["located"] == 0
    assert "find-spot" in res["note"]


# ── data_status ──────────────────────────────────────────────────────────────


def test_data_status_matches_the_registry() -> None:
    from aegean.data import _REMOTE, cache_dir

    res = m.data_status()
    assert res["store"] == str(cache_dir())
    assert [d["name"] for d in res["datasets"]] == sorted(_REMOTE)
    for d in res["datasets"]:
        assert isinstance(d["downloaded"], bool)
        assert d["license"]
        if d["downloaded"]:
            assert isinstance(d["bytes"], int) and d["bytes"] > 0 and d["size"]
        else:
            assert d["bytes"] is None and d["size"] == ""


# ── the Greek tools ──────────────────────────────────────────────────────────


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


def test_greek_catalog_exact_work() -> None:
    res = m.greek_catalog("tlg0012.tlg001")
    assert res["total"] == 1
    (work,) = res["works"]
    assert work["author"] == "Homer" and work["title"] == "Iliad"
    assert work["source"] == "perseus"


def test_greek_catalog_filters_and_limit() -> None:
    plato = m.greek_catalog(author="plato", limit=0)
    assert plato["total"] == 39 and len(plato["works"]) == 39
    assert all("plato" in w["author"].lower() for w in plato["works"])
    capped = m.greek_catalog(limit=5)
    assert len(capped["works"]) == 5 and capped["total"] > 1000


def test_greek_catalog_bad_source() -> None:
    res = m.greek_catalog(source="scaife")
    assert "unknown source 'scaife'" in res["error"]
    assert "'perseus' or 'first1k'" in res["error"]


# ── greek_work ───────────────────────────────────────────────────────────────


def _iliad_cached() -> bool:
    """True when the Iliad's directory listing and TEI edition are both in the local
    data store at the pinned commit, so ``greek_work`` loads it with zero network."""
    import json

    from aegean.data import cache_dir
    from aegean.scripts.greek import perseus

    repo = perseus._SOURCES["perseus"][0]
    commit = perseus._ref("perseus")
    listing = (
        cache_dir() / "greek-works" / "listings"
        / f"{repo.replace('/', '--')}@{commit[:12]}--data--tlg0012--tlg001.json"
    )
    if not listing.exists():
        return False
    chosen = perseus.pick_edition(json.loads(listing.read_text(encoding="utf-8")))
    if chosen is None:
        return False
    return (cache_dir() / "greek-works" / "perseus" / commit[:12] / chosen).exists()


iliad_cached = pytest.mark.skipif(
    not _iliad_cached(),
    reason="tlg0012.tlg001 (Iliad) is not in the local data store; "
    "`aegean greek work tlg0012.tlg001` caches it",
)


@iliad_cached
def test_greek_work_loads_a_cached_work() -> None:
    """The summary mirrors the CLI's `greek work` fields, plus the line preview."""
    res = m.greek_work("tlg0012.tlg001", ref="1.1-1.10")
    assert res["work"] == "tlg0012.tlg001"
    assert res["documents"] == 1
    assert res["tokens"] == 78  # Iliad 1.1-1.10, Perseus grc2 edition
    assert res["first"] == "tlg0012.tlg001:1.1-1.10"
    assert "Ἰλιάς" in res["name"]
    assert "canonical-greekLit" in res["source"]
    assert res["data_version"].startswith("PerseusDL/canonical-greekLit@")
    assert len(res["preview"]) == 10
    assert res["preview"][0].startswith("μῆνιν ἄειδε θεὰ")


@iliad_cached
def test_greek_work_preview_is_capped() -> None:
    three = m.greek_work("tlg0012.tlg001", ref="1.1-1.10", preview_lines=3)
    assert len(three["preview"]) == 3
    assert three["preview"][0].startswith("μῆνιν")
    none = m.greek_work("tlg0012.tlg001", ref="1.1-1.10", preview_lines=0)
    assert none["preview"] == []
    assert none["tokens"] == 78  # the summary itself is unaffected by the cap


@iliad_cached
def test_greek_work_bad_ref_is_a_structured_error() -> None:
    res = m.greek_work("tlg0012.tlg001", ref="99.99")
    assert "selected no text" in res["error"]
    assert "greek_catalog" in res["error"]


def test_greek_work_unknown_id_error_shape() -> None:
    """A non-work id fails offline with the id-shape example and the catalog pointer."""
    res = m.greek_work("not-a-work")
    assert isinstance(res, dict) and set(res) == {"error"}
    assert "not-a-work" in res["error"]
    assert "tlg0012.tlg001" in res["error"]  # what a work id looks like
    assert "greek_catalog" in res["error"]  # the catalog pointer


def test_greek_work_rejects_filesystem_paths() -> None:
    """Work ids only, never paths: the registry-name invariant extends to works."""
    for bad in ("docs/demo/demo.py", "..\\evil.xml", "corpus.json", "C:/data/x.db"):
        res = m.greek_work(bad)
        assert set(res) == {"error"}, bad
        assert "work id" in res["error"] and "greek_catalog" in res["error"]


def test_greek_gloss_dodson() -> None:
    res = m.greek_gloss("λόγος", dictionary="dodson")
    assert res["headword"] == "λόγος"
    assert "word" in res["gloss"]
    assert "definition" not in res  # concise by default
    full = m.greek_gloss("λόγος", dictionary="dodson", full=True)
    assert "word" in full["definition"]


def test_greek_gloss_miss_and_bad_dictionary() -> None:
    miss = m.greek_gloss("zzznotgreek", dictionary="dodson")
    assert "no dodson entry for 'zzznotgreek'" in miss["error"]

    typo = m.greek_gloss("λόγος", dictionary="cunlife")
    assert "unknown dictionary 'cunlife'" in typo["error"]
    assert "'cunliffe'" in typo["error"]  # did-you-mean

    linked = m.greek_gloss("μῆνις", dictionary="slater")
    assert "deep-link only" in linked["error"]
    assert "lsj" in linked["error"]  # names the hosted dictionaries


def test_koine_gloss() -> None:
    g = m.koine_gloss("λόγος")
    assert g["strongs"] == "3056" and "word" in g["gloss"]
    miss = m.koine_gloss("zzznotgreek")
    assert "no Dodson" in miss["error"]
    assert "greek_gloss" in miss["error"]  # the next-tool hint


# ── the FastMCP layer ([mcp] extra) ──────────────────────────────────────────


def test_build_server_registers_tools() -> None:
    pytest.importorskip("mcp")
    import asyncio

    server = m.build_server()
    assert server is not None
    assert len(m.TOOLS) == 15  # the registered tool surface
    registered = {t.name for t in asyncio.run(server.list_tools())}
    assert registered == {fn.__name__ for fn in m.TOOLS}


def test_wire_level_error_contract() -> None:
    """A domain miss travels as a normal structured result, not a raised ToolError."""
    pytest.importorskip("mcp")
    import asyncio
    import json

    server = m.build_server()
    content, _structured = asyncio.run(
        server.call_tool("corpus_info", {"corpus": "linera"})
    )
    payload = json.loads(content[0].text)
    assert "unknown corpus 'linera'" in payload["error"]
    assert "'lineara'" in payload["error"]


def test_wire_level_input_schema() -> None:
    pytest.importorskip("mcp")
    import asyncio

    tools = {t.name: t for t in asyncio.run(m.build_server().list_tools())}
    assert tools["show_document"].inputSchema["required"] == ["corpus", "doc_id"]
    assert "where" in tools["query_corpus"].inputSchema["required"]
    assert tools["greek_work"].inputSchema["required"] == ["work_id"]
