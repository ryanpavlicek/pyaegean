"""The browser demo (docs/demo/): its Python logic, and the HTML wiring that calls it.

Pyodide-in-a-browser can't run in CI, so this exercises docs/demo/demo.py directly against
the installed package (the demo runs the same functions under Pyodide) and structurally
checks that index.html references the demo module, the pinned Pyodide build, and the package.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

_DEMO_DIR = Path(__file__).resolve().parents[1] / "docs" / "demo"


def _load_demo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_pyaegean_web_demo", _DEMO_DIR / "demo.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_demo_betacode() -> None:
    demo = _load_demo()
    assert json.loads(demo.betacode("mh=nin"))["unicode"] == "μῆνιν"


def test_demo_greek_pipeline() -> None:
    demo = _load_demo()
    recs = json.loads(demo.greek_pipeline("ἐν ἀρχῇ ἦν ὁ λόγος."))
    assert recs and {"text", "upos", "lemma"} <= set(recs[0])
    assert recs[0]["text"] == "ἐν"


def test_demo_greek_scan() -> None:
    demo = _load_demo()
    ok = json.loads(demo.greek_scan("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"))
    assert ok["scans"] is True and "—" in ok["pattern"]
    bad = json.loads(demo.greek_scan("ἐν ἀρχῇ ἦν"))
    assert bad["scans"] is False


def test_demo_lineara_search() -> None:
    demo = _load_demo()
    out = json.loads(demo.lineara_search("KU-*-RO"))
    assert any(m["word"] == "KU-MA-RO" for m in out["matches"])


def test_demo_greek_word() -> None:
    demo = _load_demo()
    r = json.loads(demo.greek_word("ἀνθρώπους"))
    assert r["syllables"] == ["ἀν", "θρώ", "πους"]
    assert "acute" in r["accent"] and r["ipa_attic"] and r["ipa_koine"]
    assert any(m["lemma"] == "ἄνθρωπος" for m in r["morphology"])


def test_demo_gloss_nt() -> None:
    demo = _load_demo()
    r = json.loads(demo.gloss_nt("ἀγάπη"))
    assert r["word"] == "ἀγάπη" and "love" in r["gloss"]


def test_demo_catalog() -> None:
    demo = _load_demo()
    r = json.loads(demo.catalog("homer"))
    assert r["total"] >= 2 and any(m["id"] == "tlg0012.tlg001" for m in r["matches"])


def test_demo_bridge() -> None:
    demo = _load_demo()
    assert json.loads(demo.bridge("linearb", "po-me"))["greek"] == "ποιμήν"
    assert json.loads(demo.bridge("cypriot", "pa-si-le-u-se"))["greek"] == "βασιλεύς"
    assert "error" in json.loads(demo.bridge("linearb", "zz-zz"))


def test_demo_cypriot_inscription() -> None:
    demo = _load_demo()
    r = json.loads(demo.cypriot_inscription("IG XV 1, 95"))
    assert r["id"] == "IG XV 1, 95" and r["site"] == "Kurion"
    assert r["lines"] and "ta-ma-ti-ri" in r["lines"][0]
    assert "Δήμητρι" in r["greek"]
    assert r["source_url"].startswith("https://")
    assert "error" in json.loads(demo.cypriot_inscription("IG XV 1, 99999"))


def test_demo_lineara_balance() -> None:
    demo = _load_demo()
    r = json.loads(demo.lineara_balance("HT9b"))
    assert r["checks"] and r["checks"][0]["marker"] == "KU-RO" and r["checks"][0]["balances"]
    assert "error" in json.loads(demo.lineara_balance("NOPE"))


def test_demo_import_text() -> None:
    demo = _load_demo()
    r = json.loads(demo.import_text("ἐν ἀρχῇ ἦν ὁ λόγος καὶ ὁ λόγος"))
    assert r["documents"] == 1 and r["tokens"] == 8
    assert any(t["word"] == "λόγος" and t["count"] == 2 for t in r["top"])


def test_demo_phonetic_compare() -> None:
    demo = _load_demo()
    r = json.loads(demo.phonetic_compare("qa-si-re-u", "βασιλεύς"))
    assert 0 < r["similarity"] <= 1


def test_demo_epidoc_import() -> None:
    demo = _load_demo()
    from aegean.core.model import Document, DocumentMeta, FormSegment, Token, TokenFormState, TokenKind
    from aegean.io import to_epidoc

    doc = Document(
        id="IG1", script_id="greek",
        tokens=[Token(
            "λόγος", TokenKind.WORD, line_no=0, position=0,
            form_state=TokenFormState(
                diplomatic="λογος", regularized="λόγος", segments=(FormSegment("λόγος"),)
            ),
        )],
        lines=[[0]], meta=DocumentMeta(site="Athens", name="t"),
    )
    r = json.loads(demo.epidoc_import(to_epidoc(doc)))
    assert r["id"] == "IG1" and r["site"] == "Athens" and r["tokens"] == 1 and r["preview"] == ["λόγος"]
    assert r["form_states"] == [{
        "text": "λόγος", "diplomatic": "λογος", "regularized": "λόγος",
        "normalized": None, "editorial_status": "certain",
    }]
    assert "error" in json.loads(demo.epidoc_import("not xml"))


def test_demo_accent_word() -> None:
    demo = _load_demo()
    r = json.loads(demo.accent_word("ανθρωπος"))
    assert r["accented"] == "άνθρωπος" and r["classification"] == "proparoxytone"
    assert r["certain"] is True
    p = json.loads(demo.accent_word("θεου", "θεός"))
    assert p["accented"] == "θεοῦ" and p["accent"] == "circumflex"
    assert p["classification"] == "perispomenon"


def test_demo_sandhi() -> None:
    demo = _load_demo()
    r = json.loads(demo.sandhi("κἀγώ"))
    assert r["words"] == ["καί", "ἐγώ"] and r["kind"] == "crasis" and r["uncertain"] is False
    e = json.loads(demo.sandhi("ἀπ'"))
    assert e["words"] == ["ἀπό"] and e["kind"] == "elision"
    n = json.loads(demo.sandhi("γνῶσιν"))          # ambiguous i-stem: never claimed
    assert n["kind"] == "none" and n["words"] == ["γνῶσιν"]


def test_demo_prosody_word() -> None:
    demo = _load_demo()
    r = json.loads(demo.prosody_word("ἄνθρωπος"))
    assert [s["syllable"] for s in r["syllables"]] == ["ἄν", "θρω", "πος"]
    assert [s["quantity"] for s in r["syllables"]] == ["heavy", "heavy", "heavy"]


def test_demo_lemmatize_word() -> None:
    demo = _load_demo()
    hit = json.loads(demo.lemmatize_word("ἀνθρώπων"))
    assert hit["lemma"] == "ἄνθρωπος" and hit["known"] is True and hit["pos"] == "NOUN"
    # the honest miss: an ambiguous -ου genitive comes back unchanged, not fabricated
    miss = json.loads(demo.lemmatize_word("προφήτου"))
    assert miss["lemma"] == "προφήτου" and miss["known"] is False


def test_demo_text_profile() -> None:
    demo = _load_demo()
    greek = json.loads(demo.text_profile("μῆνιν ἄειδε θεά"))
    assert greek["script"] == "greek" and greek["is_polytonic"] is True
    beta = json.loads(demo.text_profile("mh=nin a)/eide qea/"))
    assert beta["looks_like_betacode"] is True and beta["is_polytonic"] is False


def test_demo_nt_verse() -> None:
    import unicodedata

    nfc = lambda s: unicodedata.normalize("NFC", s)  # noqa: E731
    demo = _load_demo()
    r = json.loads(demo.nt_verse("John 1.1"))
    assert r["ref"] == "John 1.1" and r["text"].startswith(nfc("Ἐν ἀρχῇ ἦν ὁ Λόγος"))
    first = r["tokens"][0]
    assert first == {"text": "Ἐν", "lemma": "ἐν", "morph": "PREP",
                     "strongs": "1722", "upos": "ADP"}
    p = json.loads(demo.nt_verse("Philemon 1.4"))
    assert p["ref"] == "Phlm 1.4" and p["tokens"][0]["lemma"] == nfc("εὐχαριστέω")
    assert "error" in json.loads(demo.nt_verse("Rev 1.1"))       # not in the offline sample
    assert "error" in json.loads(demo.nt_verse("John"))          # malformed ref


def test_demo_idioms() -> None:
    demo = _load_demo()
    r = json.loads(demo.idioms("τὸ δ' ἐφ' ἡμῖν ἐστι"))
    assert any("in our power" in i["gloss"] for i in r["idioms"])
    assert json.loads(demo.idioms("λόγος"))["idioms"] == []


def test_demo_lineara_stats() -> None:
    demo = _load_demo()
    r = json.loads(demo.lineara_stats("Haghia Triada"))
    top = r["dispersion"][0]
    assert top["word"] == "KU-RO" and top["count"] == 37 and top["dp_norm"] == 0.851
    assert r["keyness"][0]["word"] == "KU-RO" and r["keyness"][0]["site_count"] == 35
    assert all(k["log_ratio"] > 0 for k in r["keyness"])
    bad = json.loads(demo.lineara_stats("Atlantis"))
    assert "error" in bad and "Khania" in bad["sites"]


def test_demo_lineara_query() -> None:
    demo = _load_demo()
    r = json.loads(demo.lineara_query("Khania", "KU"))
    assert r["total"] == 5 and any(w["word"] == "I-KU-PI" for w in r["words"])
    site_only = json.loads(demo.lineara_query("Zakros", ""))
    assert site_only["total"] > 0
    assert "error" in json.loads(demo.lineara_query("", ""))


def test_demo_numerals() -> None:
    demo = _load_demo()
    r = json.loads(demo.numerals("12 ½ ≈ ⅙ KU-RO"))
    by_tok = {x["token"]: x for x in r["readings"]}
    assert by_tok["12"]["value"] == 12 and by_tok["½"]["value"] == 0.5
    assert by_tok["⅙"]["display"] == "⅙" and by_tok["KU-RO"]["value"] is None
    assert r["sum"] == 12.6667


def test_demo_sign_info() -> None:
    demo = _load_demo()
    r = json.loads(demo.sign_info("lineara", "PA"))
    assert r["glyph"] == "𐘂" and r["codepoint"] == "U+10602" and r["sound_value"] == "pa"
    assert "exploratory" in r["note"]                      # Linear A honesty caveat
    b = json.loads(demo.sign_info("linearb", "da"))        # case-folded label
    assert b["label"] == "DA" and b["sound_value"]
    cm = json.loads(demo.sign_info("cyprominoan", "CM008"))
    assert cm["codepoint"] == "U+12F96" and cm["sound_value"] == ""
    assert "undeciphered" in cm["note"]
    assert "error" in json.loads(demo.sign_info("lineara", "NOPE"))
    assert "error" in json.loads(demo.sign_info("klingon", "PA"))


def test_demo_linearb_tablet() -> None:
    demo = _load_demo()
    r = json.loads(demo.linearb_tablet("PY Ta 641"))
    assert r["site"] == "Pylos" and "tripod" in r["name"]
    assert r["lines"] and r["lines"][0].startswith("TI-RI-PO-DE")
    assert any(g["word"] == "TI-RI-PO-DE" and g["greek"] == "τρίπους" for g in r["readings"])
    bad = json.loads(demo.linearb_tablet("XX 0"))
    assert "error" in bad and "PY Ta 641" in bad["ids"]


def test_demo_cyprominoan_doc() -> None:
    demo = _load_demo()
    r = json.loads(demo.cyprominoan_doc("cm-enkomi-ball"))
    assert r["site"] == "Enkomi" and "CM005-CM023-CM002" in r["sign_groups"]
    assert "undeciphered" in r["note"]
    bad = json.loads(demo.cyprominoan_doc("nope"))
    assert "error" in bad and "cm-ugarit-tablet" in bad["ids"]


def test_demo_geo_word() -> None:
    demo = _load_demo()
    site = json.loads(demo.geo_word("Phaistos"))
    assert site["lat"] == 35.05 and site["lon"] == 24.81 and site["region"] == "crete"
    assert site["pleiades"].endswith("/589987")
    word = json.loads(demo.geo_word("KU-RO"))
    ht = word["sites"][0]
    assert ht["site"] == "Haghia Triada" and ht["documents"] == 32
    assert ht["lat"] == 35.06 and ht["lon"] == 24.79
    assert "error" in json.loads(demo.geo_word("zzz-zzz"))


def test_demo_cite_bundled() -> None:
    demo = _load_demo()
    r = json.loads(demo.cite_bundled("lineara", "Zakros"))
    assert r["documents"] == 53
    assert "Recueil des inscriptions" in r["citation"]
    assert "subset: filter(site='Zakros') → 53 of 1721 documents" in r["citation"]
    assert r["bibtex"].startswith("@misc{lineara-corpus")
    assert len(r["fingerprint"]) == 64 and int(r["fingerprint"], 16) >= 0
    # the whole-corpus and subset fingerprints differ (the hash covers content)
    whole = json.loads(demo.cite_bundled("lineara"))
    assert whole["documents"] == 1721 and whole["fingerprint"] != r["fingerprint"]
    assert "error" in json.loads(demo.cite_bundled("nt"))        # fetched corpora refused
    assert "error" in json.loads(demo.cite_bundled("lineara", "Atlantis"))


def test_demo_export_epidoc() -> None:
    demo = _load_demo()
    r = json.loads(demo.export_epidoc("lineara", "HT9b"))
    assert r["id"] == "HT9b"
    assert '<div type="edition"' in r["xml"] and "<idno>HT9b</idno>" in r["xml"]
    # the exported XML reads back through the import path (round-trip)
    back = json.loads(demo.epidoc_import(r["xml"]))
    assert back["id"] == "HT9b" and back["site"] == "Haghia Triada"
    assert "error" in json.loads(demo.export_epidoc("ddbdp", "x"))   # bundled corpora only
    assert "error" in json.loads(demo.export_epidoc("lineara", "NOPE"))


def test_demo_explain() -> None:
    demo = _load_demo()
    r = json.loads(demo.explain("ἐν ἀρχῇ ἦν ὁ λόγος"))
    assert r["text"] == "ἐν ἀρχῇ ἦν ὁ λόγος"
    first = r["tokens"][0]
    assert first["token"] == "ἐν" and first["upos"] == "ADP" and first["lemma"] == "ἐν"
    # every token carries its evidence class and a plain-language note, no confidence number
    assert {"token", "upos", "lemma", "source", "review", "morphology", "note"} <= set(first)
    assert first["source"] == "seed" and first["review"] is False
    assert "seed table" in first["note"]
    assert all(isinstance(t["review"], bool) for t in r["tokens"])


def test_demo_diagnose_corpus() -> None:
    demo = _load_demo()
    r = json.loads(demo.diagnose_corpus("lineara"))
    assert r["documents"] == 1721 and r["tokens"] == 6406
    assert r["reading_status"] == {
        "certain": 5734, "unclear": 120, "restored": 0, "lost": 552,
        "documents_with_apparatus": 366,
    }
    assert r["provenance"]["can_cite"] is True
    assert r["accounting"]["applicable"] is True
    assert r["accounting"]["documents_with_total"] == 37
    assert r["accounting"]["balanced"] == 14 and r["accounting"]["discrepant"] == 23
    assert r["accounting"]["intact_and_balancing"] == 7
    assert "lead, not a verdict" in r["accounting"]["caveat"]
    assert r["numerals"] == {"applicable": True, "anomalies": 0}
    assert r["review"]["applicable"] is False  # no sourced-lemmatization evidence classes
    assert "signs" not in r  # quick level omits the sign scan
    # deep adds the sign-frequency scan
    deep = json.loads(demo.diagnose_corpus("lineara", True))
    assert deep["signs"] == {
        "distinct": 162, "hapax": 56,
        "out_of_inventory_occurrences": 157, "out_of_inventory_distinct": 66,
    }
    # a Greek prose corpus marks accounting / numerals not-applicable, never an error
    greek = json.loads(demo.diagnose_corpus("greek"))
    assert greek["accounting"]["applicable"] is False
    assert "error" in json.loads(demo.diagnose_corpus("nt"))  # fetched corpora refused


def test_demo_apparatus() -> None:
    demo = _load_demo()
    r = json.loads(demo.apparatus("cypriot"))
    assert r["status_counts"] == {"certain": 370, "unclear": 188, "restored": 51, "lost": 19}
    assert r["non_certain"] == 258
    assert r["documents_with_apparatus"] == 130
    assert r["alt_reading_tokens"] == 0  # bundled cypriot carries no <app>/<rdg> variants
    # only the apparatus that actually occurs is legended
    assert any("unclear" in n for n in r["marker_notes"])
    assert any("restored" in n for n in r["marker_notes"])
    assert "error" in json.loads(demo.apparatus("ddbdp"))


def test_demo_linearb_dossiers() -> None:
    demo = _load_demo()
    r = json.loads(demo.linearb_dossiers("2"))
    assert r["min_docs"] == 2
    by_key = {(d["site"], d["series"]): d for d in r["dossiers"]}
    np_dossier = by_key[("Knossos", "Np")]
    assert np_dossier["documents"] == 3
    assert set(np_dossier["doc_ids"]) == {"KN Np 267", "KN Np 272", "KN Np 85"}
    assert np_dossier["hands"] == {}  # the bundled sample records no hands for these
    # a higher threshold returns fewer, and min_docs=1 returns at least as many
    assert json.loads(demo.linearb_dossiers("1"))["total"] >= r["total"]
    assert json.loads(demo.linearb_dossiers("junk"))["min_docs"] == 1  # bad input floors to 1


def test_demo_seriate_site() -> None:
    demo = _load_demo()
    r = json.loads(demo.seriate_site("Zakros"))
    assert r["site"] == "Zakros" and r["documents"] == 53
    assert r["seriated"] == 47  # only the sign-bearing documents seriate
    assert len(r["order"]) == 47 and len(set(r["order"])) == 47
    assert r["order"][0] == "ZAWa38"  # deterministic, input-order-invariant ordering
    assert "ZA10a" in r["order"]
    assert "EXPLORATORY" in r["note"]
    bad = json.loads(demo.seriate_site("Atlantis"))
    assert "error" in bad and "Khania" in bad["sites"]


def test_demo_allographs() -> None:
    demo = _load_demo()
    r = json.loads(demo.allographs("linearb"))
    assert r["script"] == "linearb" and r["signs"] == 211
    ra = next(g for g in r["groups"] if g["base"] == "RA")
    assert ra["members"] == ["RA", "RA2", "RA3"] and ra["kind"] == "homophone-number"
    assert r["composites"] == []
    assert "not claimed" in r["note"]  # the palaeographic-allography caveat
    la = json.loads(demo.allographs("lineara"))
    assert len(la["groups"]) == 4 and la["composites"]  # Linear A has ligature signs
    cm = json.loads(demo.allographs("cyprominoan"))
    assert any(g["kind"] == "catalog-suffix" for g in cm["groups"])
    assert "error" in json.loads(demo.allographs("klingon"))


def test_demo_works_without_sqlite3() -> None:
    """Pyodide unvendors sqlite3 from its stdlib, so `import aegean` and the demo's calls
    must not require it (regression: a top-level `import sqlite3` in the opt-in cache made
    the whole in-browser demo crash). Run in a subprocess with sqlite3 blocked."""
    import subprocess
    import sys

    code = (
        "import sys\n"
        "sys.modules['sqlite3'] = None  # simulate Pyodide: importing sqlite3 raises\n"
        "import aegean\n"
        "from aegean import greek\n"
        "from aegean.analysis import word_matches_sign_pattern\n"
        "assert greek.betacode_to_unicode('mh=nin') == 'μῆνιν'\n"
        "assert greek.scan_line('ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ').pattern\n"
        "assert list(greek.pipeline('ἐν ἀρχῇ ἦν ὁ λόγος'))\n"
        "c = aegean.load('lineara')\n"
        "assert any(word_matches_sign_pattern(w, '*-RO') for w, _ in c.word_frequencies())\n"
        "assert greek.catalog('homer')\n"
        "greek.use_dodson(); assert greek.gloss_nt('ἀγάπη')\n"
        "from aegean.scripts.linearb.lexicon import greek_reading\n"
        "assert greek_reading('po-me')[0] == 'ποιμήν'\n"
        "from aegean import io\n"
        "assert io.from_text('ἦν ὁ λόγος').word_frequencies()\n"
        "from aegean.analysis import balance_check\n"
        "assert balance_check(c.get('HT9b'))\n"
        "assert greek.place_accent('ανθρωπος', recessive=True).form == 'άνθρωπος'\n"
        "assert greek.resolve_sandhi('κἀγώ').words == ('καί', 'ἐγώ')\n"
        "assert greek.scan('μῆνιν')\n"
        "assert greek.lemmatize_verbose('ἀνθρώπων') == ('ἄνθρωπος', True)\n"
        "from aegean.ai import idiom_glosses\n"
        "assert idiom_glosses(\"ἐφ' ἡμῖν\")\n"
        "from aegean.geo import site_coordinates\n"
        "assert 'Haghia Triada' in site_coordinates()\n"
        "from aegean.analysis import FilterRow, dispersions\n"
        "assert dispersions(c, top=1)[0].item == 'KU-RO'\n"
        "assert c.query([FilterRow('site-is', 'Khania')], output='words').words\n"
        "from aegean.core.script import get_script\n"
        "assert get_script('lineara').sign_inventory.by_label('PA')\n"
        "from aegean.core.numerals import parse_value\n"
        "assert parse_value('½') == 0.5\n"
        "from aegean.io import to_epidoc\n"
        "assert '<TEI' in to_epidoc(c.get('HT9b'))\n"
        "assert c.cite() and len(c.fingerprint()) == 64\n"
        "from aegean.data import load_bundled_json\n"
        "assert load_bundled_json('greek', 'nt_sample.json')['documents']\n"
        "assert aegean.load('linearb').get('PY Ta 641')\n"
        "assert aegean.load('cyprominoan').documents\n"
        "assert greek.explain_pipeline('ἐν ἀρχῇ ἦν ὁ λόγος')\n"
        "assert c.diagnose('full').signs.computed\n"
        "from aegean.core.apparatus import apparatus_summary\n"
        "assert apparatus_summary(aegean.load('cypriot')).non_certain > 0\n"
        "from aegean.analysis.hands import dossiers\n"
        "assert dossiers(aegean.load('linearb'))\n"
        "from aegean.analysis.seriation import seriate\n"
        "assert seriate(c.filter(site='Zakros')).order\n"
        "from aegean.analysis.allographs import variant_groups\n"
        "assert variant_groups('lineara').groups\n"
        "print('OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, f"demo path needs sqlite3:\n{r.stdout}\n{r.stderr}"
    assert "OK" in r.stdout


def test_demo_html_wiring() -> None:
    html = (_DEMO_DIR / "index.html").read_text(encoding="utf-8")
    assert 'fetch("demo.py")' in html                 # loads the tested Python module
    assert "cdn.jsdelivr.net/pyodide/v0.28.0" in html  # pinned Pyodide build (verified to exist)
    assert 'micropip.install("pyaegean")' in html      # installs the package in-browser
    # every JS-referenced tool exists in the demo module
    demo = _load_demo()
    for name in ("betacode", "greek_pipeline", "greek_word", "greek_scan", "gloss_nt", "catalog",
                 "bridge", "cypriot_inscription", "lineara_search", "lineara_balance", "import_text",
                 "phonetic_compare", "lexicon_link", "epidoc_import", "accent_word", "sandhi",
                 "prosody_word", "nt_verse", "idioms", "lemmatize_word", "text_profile",
                 "lineara_stats", "lineara_query", "numerals", "sign_info", "linearb_tablet",
                 "cyprominoan_doc", "geo_word", "cite_bundled", "export_epidoc", "explain",
                 "diagnose_corpus", "apparatus", "linearb_dossiers", "seriate_site", "allographs"):
        assert hasattr(demo, name) and f'"{name}"' in html
