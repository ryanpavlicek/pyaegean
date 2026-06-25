"""The `aegean` CLI: every command exercised offline through CliRunner.

Backends that would fetch/train (LSJ, treebank, neural, parser training) are
exercised only through their error paths or a stubbed joint model — the CLI's
own logic is what's under test, on the bundled corpora and the zero-dep stack."""

from __future__ import annotations

import json

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean.cli import _build_app  # noqa: E402

runner = CliRunner()


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


def ok(app, *args: str) -> str:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, list(args))
    assert res.exit_code == 0, res.output
    return res.output


def err(app, *args: str) -> str:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, list(args))
    assert res.exit_code != 0, res.output
    return res.output


# ── root ─────────────────────────────────────────────────────────────────────
def test_version(app):
    import aegean

    assert aegean.__version__ in ok(app, "--version")


def test_no_args_shows_help(app):
    res = runner.invoke(app, [])
    assert "greek" in res.output and "analyze" in res.output


# ── corpus commands ──────────────────────────────────────────────────────────
def test_info_json(app):
    data = json.loads(ok(app, "info", "lineara", "--json"))
    assert data["documents"] == 1721
    assert "GORILA" in data["source"]


def test_info_unknown_corpus(app):
    msg = err(app, "info", "nope")
    assert "unknown corpus" in msg and "lineara" in msg  # lists the registered ids


def test_load_filter_and_export(app, tmp_path):
    out = tmp_path / "ht.json"
    msg = ok(app, "load", "lineara", "--site", "Haghia Triada", "--output", str(out))
    assert "1110 documents" in msg
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["_meta"]["scriptId"] == "lineara" and len(data["documents"]) == 1110


def test_show_document(app):
    out = ok(app, "show", "lineara", "HT13")
    assert "KU-RO" in out and "Haghia Triada" in out
    assert "no document" in err(app, "show", "lineara", "NOPE99")


def test_search_json(app):
    data = json.loads(ok(app, "search", "lineara", "KU-*-RO", "--json"))
    assert [m["word"] for m in data["matches"]] == ["KU-MA-RO"]


def test_query_where_and_fields(app):
    data = json.loads(
        ok(app, "query", "lineara", "--where", "site-is=Haghia Triada",
           "--output-kind", "words", "--json")
    )
    assert {"word": "KU-RO", "count": 32} in data["words"]  # 32 of 33 KU-RO are at HT
    assert "query: " in data["citation"]
    fields = json.loads(ok(app, "query", "lineara", "--fields", "--json"))
    assert "site-is" in fields
    assert "unknown field" in err(app, "query", "lineara", "--where", "bogus=1")
    assert "expected field=value" in err(app, "query", "lineara", "--where", "oops")


def test_stats(app):
    words = json.loads(ok(app, "stats", "lineara", "--top", "3", "--json"))
    assert len(words) == 3 and words[0]["item"] == "KU-RO"
    signs = json.loads(ok(app, "stats", "lineara", "--signs", "--top", "3", "--json"))
    assert all(s["count"] > 0 for s in signs)


def test_balance_and_strict(app):
    data = json.loads(ok(app, "balance", "lineara", "HT13", "--json"))
    assert data[0]["marker"] == "KU-RO" and data[0]["balances"] is False
    assert data[0]["difference"] == pytest.approx(0.5)
    res = runner.invoke(app, ["balance", "lineara", "HT13", "--strict"])
    assert res.exit_code == 1  # the famous half-unit discrepancy


def test_cite_styles_and_subset(app):
    plain = ok(app, "cite", "lineara")
    assert "GORILA" in plain or "Godart" in plain
    sub = ok(app, "cite", "lineara", "--site", "Haghia Triada")
    assert "subset: filter(site='Haghia Triada')" in sub
    assert ok(app, "cite", "lineara", "--style", "bibtex").startswith("@misc{")
    assert "style" in err(app, "cite", "lineara", "--style", "chicago")


def test_export_json_and_csv(app, tmp_path):
    out = tmp_path / "x.json"
    ok(app, "export", "lineara", "--site", "Zakros", "-f", "json", "-o", str(out))
    assert out.exists()
    pytest.importorskip("pandas")
    csv = tmp_path / "x.csv"
    ok(app, "export", "lineara", "--site", "Zakros", "-f", "csv", "-o", str(csv))
    assert csv.read_text(encoding="utf-8").splitlines()[0].startswith("id,")
    assert "unknown format" in err(app, "export", "lineara", "-f", "xml", "-o", str(out))


def test_export_import_workbench_roundtrip(app, tmp_path):
    wb = tmp_path / "wb.json"
    ok(app, "export", "lineara", "--site", "Zakros", "-f", "workbench", "-o", str(wb))
    assert wb.exists()
    back = tmp_path / "back.json"
    msg = ok(app, "import", str(wb), "--workbench", "-o", str(back))
    assert "document" in msg and back.exists()


def test_import_epidoc_roundtrip(app, tmp_path):
    epi = tmp_path / "epi"
    ok(app, "export", "lineara", "--site", "Zakros", "-f", "epidoc", "-o", str(epi))
    back = tmp_path / "back.json"
    msg = ok(app, "import", str(epi), "--epidoc", "--script", "lineara", "-o", str(back))
    assert "document" in msg and back.exists()


def test_geo_table(app):
    rows = json.loads(ok(app, "geo", "lineara", "--json"))
    assert any(r["site"] == "Haghia Triada" for r in rows)
    assert all("lat" in r and "lon" in r for r in rows)


def test_geo_word_distribution(app):
    rows = json.loads(ok(app, "geo", "lineara", "--word", "KU-RO", "--json"))
    assert rows and all({"site", "lat", "lon", "count"} <= set(r) for r in rows)
    assert any(r["site"] == "Haghia Triada" and r["count"] > 0 for r in rows)


def test_sign_lookup(app):
    data = json.loads(ok(app, "sign", "lineara", "KU", "--json"))
    assert data["phonetic"] == "ku" and data["codepoint"] == "U+10642"
    assert "no sign" in err(app, "sign", "lineara", "ZZ-NOT-A-SIGN")


def test_bridge(app):
    data = json.loads(ok(app, "bridge", "linearb", "po-me", "--json"))
    assert data["greek"] == "ποιμήν"
    assert "βασιλεύς" in ok(app, "bridge", "cypriot", "pa-si-le-u-se")
    assert "deciphered" in err(app, "bridge", "lineara", "KU-RO")
    assert "no attested" in err(app, "bridge", "linearb", "zz-zz")


# ── data group ───────────────────────────────────────────────────────────────
def test_data_list_and_cache(app):
    names = [d["name"] for d in json.loads(ok(app, "data", "list", "--json"))]
    assert "grc-joint" in names and "lineara-images" in names
    cache = json.loads(ok(app, "data", "cache", "--json"))
    assert "cache_dir" in cache
    assert "unknown dataset" in err(app, "data", "fetch", "not-a-dataset")


# ── greek group ──────────────────────────────────────────────────────────────
def test_greek_normalize_lenient(app):
    res = runner.invoke(app, ["greek", "normalize", "λόγoς", "--lenient"])
    assert res.exit_code == 0
    assert "λόγος" in res.output and "Latin letter" in res.output  # repair + note
    assert "must be NFC" in err(app, "greek", "normalize", "x", "--form", "NFX")


def test_greek_betacode_both_ways(app):
    assert ok(app, "greek", "betacode", "mh=nin").strip() == "μῆνιν"
    assert ok(app, "greek", "betacode", "μῆνιν", "--reverse").strip() == "mh=nin"


def test_greek_strip(app):
    assert ok(app, "greek", "strip", "ἄνθρωπος").strip() == "ανθρωπος"


def test_greek_tokenize(app):
    out = json.loads(ok(app, "greek", "tokenize", "ἐν ἀρχῇ ἦν.", "--json"))
    assert out == ["ἐν", "ἀρχῇ", "ἦν", "."]
    sents = ok(app, "greek", "tokenize", "ἦν ὁ λόγος. καὶ θεός ἦν;", "--sentences")
    assert sents.splitlines() == ["ἦν ὁ λόγος", "καὶ θεός ἦν"]


def test_greek_syllabify_with_exception(app):
    out = ok(app, "greek", "syllabify", "εἰσφέρω", "ἄνθρωπος")
    assert "εἰσ-φέ-ρω" in out and "ἄν-θρω-πος" in out


def test_greek_inflect(app, tmp_path, monkeypatch):
    # Offline: pre-build the AGDT lexicon from the fixture into the cache, so the
    # command's use_inflector() loads it without a network fetch.
    import pathlib

    from aegean.greek.inflect import disable_inflector
    from aegean.greek.treebank import build_lexicon

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    build_lexicon(source_dir=pathlib.Path(__file__).parent / "fixtures" / "agdt", force=True)
    try:
        assert "λόγον" in ok(app, "greek", "inflect", "λόγος", "--case", "acc", "--number", "sg")
        assert "εἶπον" in ok(app, "greek", "inflect", "λέγω", "--paradigm")
    finally:
        disable_inflector()


def test_greek_rarity(app, tmp_path):
    # Offline: a tiny Greek reference corpus written to JSON, passed via --corpus.
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, Token, TokenKind

    words = ["ὁ"] * 20 + ["λόγος"] * 5 + ["σφάκελος"]
    toks = [Token(text=w, kind=TokenKind.WORD) for w in words]
    doc = Document(id="d", script_id="greek", tokens=toks, lines=[list(range(len(toks)))])
    ref = tmp_path / "ref.json"
    Corpus(documents=[doc], script_id="greek").to_json(ref)

    assert "σφάκελος" in ok(app, "greek", "rarity", "ὁ λόγος σφάκελος", "--corpus", str(ref))
    data = json.loads(ok(app, "greek", "rarity", "σφάκελος", "--corpus", str(ref), "--json"))
    assert data["words"][0]["label"] == "hapax"


def test_greek_accent_json(app):
    rows = json.loads(ok(app, "greek", "accent", "λόγος", "--json"))
    assert rows[0]["classification"] == "paroxytone"


def test_greek_quantities_json(app):
    out = json.loads(ok(app, "greek", "quantities", "πατρός", "--json"))
    assert all(q["quantity"] in ("heavy", "light", "common") for q in out["πατρός"])


def test_greek_scan(app):
    out = ok(app, "greek", "scan", "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ")
    assert "—⏑⏑" in out and "hexameter" in out
    # iambic trimeter (tragic dialogue)
    tri = ok(app, "greek", "scan", "ἥκω Διὸς παῖς τήνδε Θηβαίων χθόνα", "--meter", "trimeter")
    assert "×—⏑—" in tri and "trimeter" in tri
    # Πηληϊάδεω is in the synizesis lexicon, so Iliad 1.1 scans
    assert "hexameter" in ok(app, "greek", "scan", "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος")
    # a prose word is not a verse line — clean exit 1, not a guess
    assert "does not scan" in err(app, "greek", "scan", "ἄνθρωπος", "--meter", "trimeter")


def test_greek_ipa(app):
    assert ok(app, "greek", "ipa", "λόγος").strip()
    assert ok(app, "greek", "ipa", "λόγος", "--period", "koine").strip()


def test_greek_tag_and_lemmatize(app):
    tags = json.loads(ok(app, "greek", "tag", "ἐν ἀρχῇ ἦν ὁ λόγος.", "--json"))
    assert tags[0] == {"token": "ἐν", "upos": "ADP"}
    rows = json.loads(ok(app, "greek", "lemmatize", "ἦν ὁ λόγος", "--json"))
    assert {"form": "ἦν", "lemma": "εἰμί", "known": True} in rows


def test_greek_morph_json(app):
    rows = json.loads(ok(app, "greek", "morph", "λόγον", "--json"))
    assert any(a["pos"] == "NOUN" for a in rows)


def test_greek_parse_requires_backend(app):
    assert "no parser active" in err(app, "greek", "parse", "ἦν ὁ λόγος")


def test_greek_pipeline_json_and_parse_error(app):
    recs = json.loads(ok(app, "greek", "pipeline", "ἦν ὁ λόγος.", "--json"))
    assert recs[-1]["upos"] == "PUNCT" and recs[0]["lemma"] == "εἰμί"
    assert "needs a parser" in err(app, "greek", "pipeline", "ἦν ὁ λόγος.", "--parse")


def test_greek_eval_rejects_bad_target(app):
    assert "target must be" in err(app, "greek", "eval", "everything")


def test_greek_eval_has_bootstrap_flag(app):
    # --bootstrap is accepted: with a bad target it reaches the runtime target check
    # (exit 1) rather than an "unknown option" usage error (exit 2). Robust to the
    # terminal width that rich uses to wrap --help output in CI.
    assert "target must be" in err(app, "greek", "eval", "nope", "--bootstrap")


def test_greek_nt_loads(app):
    data = json.loads(ok(app, "greek", "nt", "John", "--ref", "1.1-1.5", "--json"))
    assert data["scope"] == "John" and data["documents"] >= 1 and data["tokens"] > 0


def test_greek_pipeline_with_stubbed_joint(app, monkeypatch):
    pytest.importorskip("numpy")
    from test_joint import _stub_model

    from aegean.greek import joint

    monkeypatch.setattr(joint, "_ACTIVE", _stub_model())
    recs = json.loads(ok(app, "greek", "pipeline", "ὁ λόγος ἐστί", "--json"))
    assert [r["upos"] for r in recs] == ["DET", "NOUN", "VERB"]
    assert recs[2]["relation"] == "root" and recs[2]["feats"] is not None
    parsed = json.loads(ok(app, "greek", "parse", "ὁ λόγος ἐστί", "--json"))
    assert [t["relation"] for t in parsed] == ["det", "nsubj", "root"]


def test_greek_lexica_lists(app):
    ids = {d["id"] for d in json.loads(ok(app, "greek", "lexica", "--json"))}
    assert {"lsj", "dodson", "middle-liddell", "cunliffe", "abbott-smith"} <= ids


def test_greek_lexicon_link(app):
    out = ok(app, "greek", "lexicon-link", "λόγος", "--no-lemmatize")
    assert out.strip() == "https://logeion.uchicago.edu/%CE%BB%CF%8C%CE%B3%CE%BF%CF%82"
    pers = ok(app, "greek", "lexicon-link", "λόγος", "--service", "perseus", "--no-lemmatize")
    assert "perseus.tufts.edu" in pers
    assert "link service" in err(app, "greek", "lexicon-link", "λόγος", "--service", "nope")


def test_greek_gloss_dict_dodson(app):
    data = json.loads(ok(app, "greek", "gloss", "λόγος", "--dict", "dodson", "--json"))
    assert data["dictionary"] == "dodson" and "word" in data["gloss"]


def test_greek_gloss_deeplink_only_errors(app):
    msg = err(app, "greek", "gloss", "λόγος", "--dict", "autenrieth")
    assert "deep-link" in msg or "lexicon-link" in msg


# ── analyze group ────────────────────────────────────────────────────────────
def test_analyze_distance_and_align(app):
    d = json.loads(ok(app, "analyze", "distance", "KU-RO", "KI-RO", "--json"))
    assert 0 < d["distance"] < 1
    cells = json.loads(ok(app, "analyze", "align", "KU-RO", "KI-RO", "--json"))
    assert any(c["op"] != "match" for c in cells)


def test_analyze_assoc(app):
    data = json.loads(ok(app, "analyze", "assoc", "lineara", "KU-RO", "KI-RO", "--json"))
    assert data["counts"]["joint"] >= 1 and data["chi_squared"] > 0
    assert 0 <= data["p_value"] <= 1
    assert "does not occur" in err(app, "analyze", "assoc", "lineara", "KU-RO", "ZZ-ZZ")


def test_analyze_cooccur(app):
    rows = json.loads(ok(app, "analyze", "cooccur", "lineara", "KU-RO", "--top", "5", "--json"))
    assert rows and rows[0]["shared_documents"] >= rows[-1]["shared_documents"]


def test_analyze_clusters(app):
    clusters = json.loads(ok(app, "analyze", "clusters", "lineara", "--top", "3", "--json"))
    assert all(c["stem"] for c in clusters)


def test_analyze_structure(app):
    census = json.loads(ok(app, "analyze", "structure", "lineara", "--json"))
    assert census["accounting"] > 100
    one = json.loads(ok(app, "analyze", "structure", "lineara", "HT13", "--json"))
    assert one == {"doc": "HT13", "category": "accounting"}


# ── ai group ─────────────────────────────────────────────────────────────────
def test_ai_providers(app):
    assert set(json.loads(ok(app, "ai", "providers", "--json"))) == {
        "anthropic", "openai", "grok", "gemini", "openrouter",
    }


def test_ai_summarize_registered(app):
    assert "summary" in ok(app, "ai", "summarize", "--help").lower()


def test_ai_unknown_provider_is_clean(app):
    out = err(app, "ai", "translate", "x", "--provider", "nope")
    assert "unknown provider" in out and "Traceback" not in out


def test_ai_translate_with_fake_client(app, monkeypatch):
    from aegean import ai
    from aegean.ai.client import LLMClient, LLMResponse

    class FakeClient(LLMClient):
        provider = "fake"

        def _complete(self, *, prompt, system, max_tokens):  # type: ignore[no-untyped-def]
            return LLMResponse("A TRANSLATION", self.provider, self.model)

    monkeypatch.setattr(ai, "get_client", lambda *a, **k: FakeClient("fake-1"))
    res = runner.invoke(app, ["ai", "translate", "ἐν ἀρχῇ ἦν ὁ λόγος", "--json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data["text"] == "A TRANSLATION" and data["exploratory"] is True
    assert data["kind"] == "translate"
