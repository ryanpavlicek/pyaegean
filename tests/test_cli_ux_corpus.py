"""CLI-friendliness fixes in the corpus + analyze command groups.

Pins the audited behaviors: query --where value/field validation with did-you-mean,
limit-consistent JSON payloads, the empty-result hints (search/query/load/balance),
load -o extension dispatch (.db is real SQLite), combine/import/cite --json, the
shared metadata filters on stats/dispersion/balance/geo/structure/hands, export/geo
--level validated up front, geo's GeoJSON extension check + one-line missing-extra
failure, sign close-matches, and the analyze group help map naming every command."""

from __future__ import annotations

import json
import sqlite3

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean.core.corpus import Corpus  # noqa: E402
from aegean.core.model import Document, DocumentMeta, Token, TokenKind  # noqa: E402

runner = CliRunner()


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    from aegean.cli import _build_app

    return _build_app()


def ok(app, *args: str):  # type: ignore[no-untyped-def]
    res = runner.invoke(app, list(args))
    assert res.exit_code == 0, res.output
    return res


def err(app, *args: str):  # type: ignore[no-untyped-def]
    res = runner.invoke(app, list(args))
    assert res.exit_code == 1, res.output
    return res


def _doc(did: str, words: list[str], scribe: str = "", site: str = "") -> Document:
    return Document(
        id=did,
        script_id="greek",
        tokens=[Token(text=w, kind=TokenKind.WORD) for w in words],
        lines=[list(range(len(words)))],
        meta=DocumentMeta(scribe=scribe, site=site),
    )


@pytest.fixture()
def tiny_json(tmp_path):  # type: ignore[no-untyped-def]
    """A two-document Greek corpus on disk (no accounting markers, no find-sites)."""
    c = Corpus(documents=[_doc("D1", ["λόγος"]), _doc("D2", ["βασιλεύς"])], script_id="greek")
    p = tmp_path / "tiny.json"
    c.to_json(p)
    return p


# ── query --where validation ─────────────────────────────────────────────────
def test_query_where_number_value_validated(app) -> None:  # type: ignore[no-untyped-def]
    res = err(app, "query", "lineara", "--where", "word-min-syllables=abc")
    assert "aegean: --where word-min-syllables expects a number, got 'abc'" in res.output
    assert "Traceback" not in res.output


def test_query_where_unknown_field_suggests(app) -> None:  # type: ignore[no-untyped-def]
    res = err(app, "query", "lineara", "--where", "site=HT")
    assert "unknown field 'site' — did you mean 'site-is'?" in res.output
    assert "--fields" in res.output


def test_query_where_unknown_field_without_close_match(app) -> None:  # type: ignore[no-untyped-def]
    res = err(app, "query", "lineara", "--where", "zzzqqq=1")
    assert "unknown field 'zzzqqq'" in res.output
    assert "did you mean" not in res.output
    assert "--fields" in res.output


def test_query_json_respects_limit_and_reports_totals(app) -> None:  # type: ignore[no-untyped-def]
    capped = json.loads(
        ok(app, "query", "lineara", "--where", "word-prefix=KU", "--limit", "2", "--json").stdout
    )
    assert len(capped["inscriptions"]) == 2
    assert capped["matched"]["inscriptions"] > 2  # the untruncated total rides along
    full = json.loads(
        ok(app, "query", "lineara", "--where", "word-prefix=KU", "--limit", "0", "--json").stdout
    )
    assert len(full["inscriptions"]) == full["matched"]["inscriptions"]
    assert len(full["words"]) == full["matched"]["words"]
    assert capped["inscriptions"] == full["inscriptions"][:2]  # a prefix, not a resample


# ── empty-result hints ───────────────────────────────────────────────────────
def test_query_empty_result_hint(app) -> None:  # type: ignore[no-untyped-def]
    res = ok(app, "query", "lineara", "--where", "site-is=Nowhere")
    assert "0 matches — values are exact" in res.output
    assert "--fields" in res.output
    # --json keeps the machine contract: an empty payload, no hint on stdout
    data = json.loads(ok(app, "query", "lineara", "--where", "site-is=Nowhere", "--json").stdout)
    assert data["inscriptions"] == [] and data["matched"]["inscriptions"] == 0


def test_search_empty_result_hint(app) -> None:  # type: ignore[no-untyped-def]
    res = ok(app, "search", "lineara", "ZZ-ZZ-ZZ")
    assert "no matches" in res.output and "aegean stats lineara" in res.output
    data = json.loads(ok(app, "search", "lineara", "ZZ-ZZ-ZZ", "--json").stdout)
    assert data["matches"] == []


def test_load_empty_filter_hint(app) -> None:  # type: ignore[no-untyped-def]
    res = ok(app, "load", "lineara", "--site", "Nowhere")
    assert "0 matches — filters are exact" in res.output
    assert "without filters" in res.output


def test_balance_empty_hint(app, tiny_json) -> None:  # type: ignore[no-untyped-def]
    res = ok(app, "balance", str(tiny_json))
    assert "no stated totals" in res.output
    assert "KU-RO / TO-SO" in res.output


# ── load -o extension dispatch ───────────────────────────────────────────────
def test_load_output_db_is_real_sqlite(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "zakros.db"
    res = ok(app, "load", "lineara", "--site", "Zakros", "-o", str(out))
    assert "wrote 53 documents" in res.output
    assert out.read_bytes()[:16] == b"SQLite format 3\x00"  # not JSON bytes in a .db
    con = sqlite3.connect(out)
    try:
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    assert names  # a real schema
    # and the file round-trips through every corpus-taking command
    info = json.loads(ok(app, "info", str(out), "--json").stdout)
    assert info["documents"] == 53


def test_load_output_unknown_extension_fails(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    res = err(app, "load", "lineara", "--site", "Zakros", "-o", str(tmp_path / "out.xyz"))
    assert ".json or .db/.sqlite extension" in res.output


# ── combine / import / cite --json ───────────────────────────────────────────
def test_combine_json_payload(app, tmp_path, tiny_json) -> None:  # type: ignore[no-untyped-def]
    other = tmp_path / "other.json"
    Corpus(documents=[_doc("D3", ["μῆνις"])], script_id="greek").to_json(other)
    out = tmp_path / "merged.json"
    data = json.loads(
        ok(app, "combine", str(tiny_json), str(other), "-o", str(out), "--json").stdout
    )
    assert data == {"written": 3, "path": str(out), "sources": 2}
    assert len(json.loads(out.read_text(encoding="utf-8"))["documents"]) == 3


def test_combine_conflict_error_names_cli_flag(app, tmp_path, tiny_json) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "dup.json"
    res = err(app, "combine", str(tiny_json), str(tiny_json), "-o", str(out))
    assert "--on-conflict" in res.output  # the CLI flag, not the Python dedupe= keyword
    assert "dedupe=" not in res.output
    res = err(app, "combine", str(tiny_json), str(tiny_json), "-o", str(out),
              "--on-conflict", "bogus")
    assert "--on-conflict must be 'error', 'first', 'last', or 'suffix'" in res.output


def test_import_json_payload_and_split(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    src = tmp_path / "two.txt"
    src.write_text("μῆνιν ἄειδε\n\nθεὰ Πηληϊάδεω\n", encoding="utf-8")
    out = tmp_path / "two.json"
    data = json.loads(
        ok(app, "import", str(src), "-o", str(out), "--split", "paragraph", "--json").stdout
    )
    assert data == {"written": 2, "path": str(out), "source": str(src)}
    assert len(json.loads(out.read_text(encoding="utf-8"))["documents"]) == 2


def test_import_unknown_script_suggests(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    src = tmp_path / "t.txt"
    src.write_text("x\n", encoding="utf-8")
    res = err(app, "import", str(src), "-o", str(tmp_path / "o.json"), "--script", "grek")
    assert "unknown script 'grek' — did you mean 'greek'?" in res.output


def test_import_id_col_validated(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    src = tmp_path / "rows.csv"
    src.write_text("text,name\nfoo,a\n", encoding="utf-8")
    res = err(app, "import", str(src), "-o", str(tmp_path / "o.json"), "--id-col", "nosuch")
    assert "--id-col 'nosuch' is not a column" in res.output
    assert "text, name" in res.output  # names the real columns


def test_import_encoding_error_hints_encoding(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    src = tmp_path / "latin.txt"
    src.write_bytes(b"caf\xe9\n")  # not valid UTF-8
    res = err(app, "import", str(src), "-o", str(tmp_path / "o.json"))
    assert "--encoding" in res.output and "Traceback" not in res.output
    ok(app, "import", str(src), "-o", str(tmp_path / "o.json"), "--encoding", "latin-1")


def test_cite_json(app) -> None:  # type: ignore[no-untyped-def]
    data = json.loads(ok(app, "cite", "lineara", "--style", "bibtex", "--json").stdout)
    assert data["corpus"] == "lineara" and data["style"] == "bibtex"
    assert data["citation"].startswith("@misc{")


# ── shared metadata filters ──────────────────────────────────────────────────
def test_stats_metadata_filter_known_answer(app) -> None:  # type: ignore[no-untyped-def]
    rows = json.loads(
        ok(app, "stats", "lineara", "--site", "Haghia Triada", "--top", "1", "--json").stdout
    )
    assert rows == [{"item": "KU-RO", "count": 35}]  # 35 of the 37 KU-RO tokens are at HT
    all_rows = json.loads(ok(app, "stats", "lineara", "--top", "1", "--json").stdout)
    assert all_rows[0]["count"] > rows[0]["count"]  # the filter really narrowed the corpus


def test_dispersion_metadata_filter_known_answer(app) -> None:  # type: ignore[no-untyped-def]
    filtered = json.loads(
        ok(app, "dispersion", "lineara", "KU-RO", "--site", "Haghia Triada", "--json").stdout
    )[0]
    assert filtered["frequency"] == 35 and filtered["range"] == 32
    unfiltered = json.loads(ok(app, "dispersion", "lineara", "KU-RO", "--json").stdout)[0]
    assert unfiltered["frequency"] == 37 and unfiltered["range"] == 34


def test_balance_output_and_filter(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "ht13.json"
    ok(app, "balance", "lineara", "HT13", "-o", str(out))
    rows = json.loads(out.read_text(encoding="utf-8"))
    assert rows[0]["marker"] == "KU-RO" and rows[0]["balances"] is False
    assert rows[0]["difference"] == pytest.approx(0.5)  # the famous half-unit discrepancy
    zakros = json.loads(ok(app, "balance", "lineara", "--site", "Zakros", "--json").stdout)
    assert zakros and all(r["doc"].startswith("ZA") for r in zakros)


def test_balance_output_creates_parent_dirs(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "a" / "b" / "ht13.json"
    res = ok(app, "balance", "lineara", "HT13", "-o", str(out))
    assert out.exists()
    assert f"wrote {out}" in res.output  # the shared write_result confirmation


# ── export / geo --level and extras ──────────────────────────────────────────
def test_export_level_validated_up_front(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "x.csv"
    res = err(app, "export", "lineara", "-f", "csv", "--level", "bogus", "-o", str(out))
    assert "--level must be 'document', 'token', or 'word'; got 'bogus'" in res.output
    assert not out.exists()


def test_geo_level_validated_on_table_path(app) -> None:  # type: ignore[no-untyped-def]
    # was silently ignored (exit 0) when no --output was given
    res = err(app, "geo", "lineara", "--level", "bogus")
    assert "--level must be 'site' or 'inscription'; got 'bogus'" in res.output


def test_geo_output_extension_validated(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    res = err(app, "geo", "lineara", "-o", str(tmp_path / "geo.csv"))
    assert ".json or .geojson extension" in res.output
    assert not (tmp_path / "geo.csv").exists()


def test_geo_metadata_filter_table(app) -> None:  # type: ignore[no-untyped-def]
    rows = json.loads(ok(app, "geo", "lineara", "--site", "Zakros", "--json").stdout)
    assert [r["site"] for r in rows] == ["Zakros"]
    assert rows[0]["lat"] == pytest.approx(35.1, abs=0.05)
    assert rows[0]["lon"] == pytest.approx(26.26, abs=0.05)


def test_geo_geojson_write_filtered(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("geopandas")
    out = tmp_path / "sub" / "dir" / "zakros.geojson"  # parents are created by the guard
    res = ok(app, "geo", "lineara", "--site", "Zakros", "-o", str(out))
    assert "wrote 1 features" in res.output
    gj = json.loads(out.read_text(encoding="utf-8"))
    assert gj["type"] == "FeatureCollection" and len(gj["features"]) == 1
    assert gj["features"][0]["properties"]["site"] == "Zakros"


def test_geo_missing_extra_is_one_line(app, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import aegean.geo

    def boom(*a, **k):  # type: ignore[no-untyped-def]
        raise ImportError(
            "geographic analysis needs the optional dependencies: pip install 'pyaegean[geo]'"
        )

    monkeypatch.setattr(aegean.geo, "word_distribution", boom)
    res = err(app, "geo", "lineara", "--word", "KU-RO", "-o", "geo_out.json")
    assert "pip install 'pyaegean[geo]'" in res.output
    assert "Traceback" not in res.output


def test_geo_help_renders_extra_brackets_literally(app) -> None:  # type: ignore[no-untyped-def]
    out = ok(app, "geo", "--help").output
    assert "[geo]" in out  # rich markup must not eat the extra's name


# ── sign close-matches ───────────────────────────────────────────────────────
def test_sign_unknown_label_close_matches(app) -> None:  # type: ignore[no-untyped-def]
    res = err(app, "sign", "lineara", "KUU")
    assert "no sign 'KUU'" in res.output
    assert "close:" in res.output and "KU" in res.output


def test_sign_hopeless_label_has_no_close_line(app) -> None:  # type: ignore[no-untyped-def]
    res = err(app, "sign", "lineara", "QQQQQQQQ")
    assert "no sign" in res.output and "close:" not in res.output


# ── cache help cross-reference ───────────────────────────────────────────────
def test_cache_help_cross_references_data_cache(app) -> None:  # type: ignore[no-untyped-def]
    from aegean.cli._corpus import cache_cmd

    assert "aegean data store" in (cache_cmd.__doc__ or "")


# ── analyze group ────────────────────────────────────────────────────────────
def test_analyze_group_help_names_every_command() -> None:
    from aegean.cli._analyze import analyze_app

    registered = {c.callback.__name__ for c in analyze_app.registered_commands}
    keyword = {
        "distance": "distance", "align": "alignment", "compare": "compare",
        "nearest": "nearest", "assoc": "association", "cooccur": "co-occurrence",
        "clusters": "clusters", "structure": "structure", "hands": "scribal hands",
    }
    assert registered == set(keyword)  # a new command must be added to this map + the help
    help_text = analyze_app.info.help or ""
    for name in registered:
        assert keyword[name] in help_text, f"analyze --help does not mention {name!r}"


def test_analyze_structure_filter_and_output(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "census.json"
    res = ok(app, "analyze", "structure", "lineara", "--site", "Haghia Triada", "-o", str(out))
    assert f"wrote {out}" in res.output
    census = json.loads(out.read_text(encoding="utf-8"))
    assert sum(census.values()) == 1110  # exactly the HT documents
    assert census.get("accounting", 0) > 0


def test_analyze_structure_single_doc_output(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "one.json"
    ok(app, "analyze", "structure", "lineara", "HT13", "-o", str(out))
    assert json.loads(out.read_text(encoding="utf-8")) == {"doc": "HT13", "category": "accounting"}


def test_analyze_hands_filters_and_top_zero(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = Corpus(
        documents=[
            _doc("T1", ["α"], scribe="A", site="Knossos"),
            _doc("T2", ["β"], scribe="A", site="Knossos"),
            _doc("T3", ["γ"], scribe="B", site="Pylos"),
        ],
        script_id="greek",
    )
    p = tmp_path / "hands.json"
    c.to_json(p)
    profiles = json.loads(ok(app, "analyze", "hands", str(p), "--json").stdout)
    assert {(pr["hand"], pr["doc_count"]) for pr in profiles} == {("A", 2), ("B", 1)}
    knossos = json.loads(
        ok(app, "analyze", "hands", str(p), "--site", "Knossos", "--json").stdout
    )
    assert [(pr["hand"], pr["doc_count"]) for pr in knossos] == [("A", 2)]
    all_rows = json.loads(ok(app, "analyze", "hands", str(p), "--top", "0", "--json").stdout)
    assert len(all_rows) == 2  # 0 = all, not an empty slice


def test_analyze_nearest_output_and_ranking(app, tmp_path, tiny_json) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "near.json"
    ok(app, "analyze", "nearest", "qa-si-re-u", str(tiny_json), "-o", str(out))
    ranked = json.loads(out.read_text(encoding="utf-8"))
    assert ranked[0]["candidate"] == "βασιλεύς"  # qa-si-re-u really is closest to basileus
    assert ranked[0]["distance"] < ranked[1]["distance"]


def test_analyze_assoc_output_combines_with_json(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "assoc.json"
    res = ok(app, "analyze", "assoc", "lineara", "KU-RO", "KI-RO", "-o", str(out), "--json")
    data = json.loads(res.stdout)  # --json still prints even when -o was given
    assert data == json.loads(out.read_text(encoding="utf-8"))
    assert data["counts"]["joint"] > 0 and 0 <= data["fisher_p"] <= 1


def test_analyze_cooccur_output_writes_csv(app, tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "co.csv"
    ok(app, "analyze", "cooccur", "lineara", "KU-RO", "--top", "3", "-o", str(out))
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "word,shared_documents"
    assert len(lines) == 4  # header + the 3 requested rows
