"""Tests for the local PyAegean Greek visual corpus browser (`aegean.browser`, `aegean browse`, TUI)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pytest

import aegean
from aegean.browser import (
    analyze_text_payload,
    analyze_word_payload,
    bible_commentaries_payload,
    bible_psalm_payload,
    catalog_payload,
    collections_payload,
    create_server,
    document_payload,
    export_payload,
    library_payload,
    scan_lines_payload,
    search_payload,
    word_study_payload,
)
from aegean.browser._service import decode_robinson, decode_xpos


def test_morphology_decoders() -> None:
    """AGDT 9-char XPOS and Robinson NT codes decode to human-readable labels."""
    x = decode_xpos("v3saia---")
    assert x["POS"] == "Verb"
    assert x["Person"] == "3rd"
    assert x["Number"] == "Singular"
    assert x["Tense"] == "Aorist"
    assert x["Mood"] == "Indicative"
    assert x["Voice"] == "Active"
    assert decode_xpos("---------") == {}

    r_verb = decode_robinson("V-AAI-3S")
    assert r_verb == {
        "POS": "Verb",
        "Tense": "Aorist",
        "Voice": "Active",
        "Mood": "Indicative",
        "Person": "3rd",
        "Number": "Singular",
    }
    r_noun = decode_robinson("N-NSM")
    assert r_noun == {"POS": "Noun", "Case": "Nominative", "Number": "Singular", "Gender": "Masculine"}


def test_catalog_and_collections_payloads_offline() -> None:
    """Catalog lists Greek corpora, NT/LXX catalogs, 8 collections, lexica, and engine status."""
    cat = catalog_payload()
    assert cat["version"] == aegean.__version__
    assert len(cat["featured"]) >= 5
    assert len(cat["nt_books"]) == 27
    assert len(cat["lxx_books"]) == 56
    assert len(cat["nt_editions"]) >= 8
    assert len(cat["collections"]) == 8
    assert any(c["id"] == "greek" for c in cat["corpora"])
    assert any(lx["id"] == "lsj" and lx["hosted"] for lx in cat["lexica"])

    works = collections_payload(query="Chrysostom", limit=10)
    assert works["total"] >= 100
    assert len(works["works"]) == 10
    assert all("work_id" in w for w in works["works"])


def test_document_payload_nt_lxx_classical_and_scratchpad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Document loader serves NT, LXX (with MT Psalm numbering), classical samples, and Beta Code."""
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))

    # 1. NT John 1:1-3 (offline bundled)
    nt = document_payload("John 1:1-3", offline=True)
    assert nt["context"]["is_biblical"] is True
    assert nt["context"]["testament"] == "nt"
    assert nt["context"]["book"] == "John"
    assert len(nt["context"]["related_commentaries"]) >= 5
    assert nt["translation"]["available"] is True
    assert "In the beginning was the Word" in nt["blocks"][0]["translation"]
    assert nt["stats"]["tokens"] > 20
    assert any(t["strongs"] == "G3056" for b in nt["blocks"] for t in b["tokens"])

    # 2. LXX Genesis 1:1-2 (offline bundled, fresh cache -> ΕΝ & ἐπάνω ADP)
    lxx = document_payload("Gen 1:1-2", offline=True)
    assert lxx["context"]["testament"] == "lxx"
    assert lxx["translation"]["available"] is True
    by_txt = {t["text"]: t for b in lxx["blocks"] for t in b["tokens"]}
    assert by_txt["ΕΝ"]["upos"] == "ADP"
    assert by_txt["ἐπάνω"]["upos"] == "ADP"

    # 3. LXX Psalm with Masoretic numbering (MT Ps 23 -> LXX Ps 22)
    ps = document_payload("MT Ps 23:1-3", offline=True)
    assert ps["context"]["testament"] == "lxx"
    assert ps["context"]["numbering"] == "mt"
    assert ps["blocks"][0]["ref"] == "Ps.22.1"
    assert ps["blocks"][0]["mt_ref"] == "MT Ps.23.1"
    assert "shepherd" in ps["blocks"][0]["translation"].lower()

    # 4. Bundled classical Greek sample (Homer Iliad 1.1)
    hom = document_payload("greek", doc_index=0, offline=True)
    assert hom["context"]["is_biblical"] is False
    assert hom["doc_id"] == "iliad-1.1"
    assert hom["translation"]["available"] is True
    assert "wrath of Achilles" in hom["translation"]["document_text"]
    assert len(hom["context"]["related_works"]) >= 1

    # 5. Custom Beta Code passage with custom translation
    custom = analyze_text_payload(
        "mh=nin a)/eide qea\\",
        betacode=True,
        translation="Sing, goddess, the wrath",
    )
    assert custom["target"] == "scratchpad"
    assert custom["blocks"][0]["tokens"][0]["text"] == "μῆνιν"
    assert custom["translation"]["document_text"] == "Sing, goddess, the wrath"


def test_word_inspector_scansion_search_and_export() -> None:
    """Word inspector, metrical scansion, search, word study, and exports all work offline."""
    w = analyze_word_payload("λόγος", strongs="G3056", book="John")
    assert w["lemma"] == "λόγος"
    assert w["accent"]["classification"] == "paroxytone"
    assert w["syllables"] == ["λό", "γος"]
    assert w["ipa"]["attic"] and w["ipa"]["koine"]
    assert w["strongs"]["strongs"] == "G3056"
    assert w["roots"]["strongs"] == "G3056"
    assert any(lk["service"] == "logeion" for lk in w["external_links"])
    assert len(w["linked_commentaries"]) >= 1

    sc = scan_lines_payload(["μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"], meter="hexameter")
    assert sc["results"][0]["error"] is None
    assert "—" in sc["results"][0]["pattern"]
    assert sc["results"][0]["caesura"] == "penthemimeral"

    hits = search_payload("φῶς", target="bible", offline=True)
    assert hits["count"] >= 2
    assert {"nt", "lxx"} <= {h["source"] for h in hits["hits"]}

    ws = word_study_payload("λόγος", offline=True)
    assert ws["total_occurrences"] >= 1

    comms = bible_commentaries_payload(book="John")
    assert comms["total"] >= 5
    ps_map = bible_psalm_payload(23, "mt_to_lxx")
    assert ps_map["mapped"] == [22]

    lib = library_payload()
    assert len(lib["items"]) >= 30

    nt = document_payload("John 1:1-2", offline=True)
    for fmt, needle in (
        ("conllu", "# sent_id ="),
        ("csv", "ref,token,lemma,upos"),
        ("json", '"blocks"'),
    ):
        content, _ctype, fname = export_payload(
            fmt=fmt,
            title=nt["title"],
            sentences=nt["sentences"],
            blocks=nt["blocks"],
        )
        assert needle in content
        assert fname.endswith(f".{fmt}")


def test_loopback_http_server_routes_and_security_guards() -> None:
    """Live loopback HTTP server serves HTML/CSS/JS + JSON APIs and blocks non-loopback/CSRF."""
    with pytest.raises(ValueError, match="loopback"):
        create_server(host="0.0.0.0", port=0)

    def _get(url: str) -> tuple[int, str, bytes]:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return (resp.status, resp.headers.get("Content-Type", ""), resp.read())

    def _post(url: str, body: dict[str, Any], *, origin: str | None = None) -> tuple[int, bytes]:
        headers = {"Content-Type": "application/json"}
        if origin is not None:
            headers["Origin"] = origin
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return (resp.status, resp.read())

    with create_server("John 1:1-3", port=0, offline=True, open_browser=False) as srv:
        # Static assets
        st_html, ct_html, html = _get(srv.url)
        assert st_html == 200 and "text/html" in ct_html and b"PyAegean Greek Browser" in html
        st_css, ct_css, css = _get(f"{srv.url}styles.css")
        assert st_css == 200 and "text/css" in ct_css and b"--font-greek" in css
        st_js, ct_js, js = _get(f"{srv.url}app.js")
        assert st_js == 200 and "javascript" in ct_js and b"renderSyntaxSvg" in js

        # Core JSON GET routes
        st_h, _, raw_h = _get(f"{srv.url}api/health")
        assert st_h == 200 and json.loads(raw_h)["ok"] is True
        st_c, _, raw_c = _get(f"{srv.url}api/catalog")
        assert st_c == 200 and len(json.loads(raw_c)["nt_books"]) == 27
        st_o, _, raw_o = _get(f"{srv.url}api/open?target={urllib.parse.quote('John 1:1-2')}&offline=1")
        assert st_o == 200 and json.loads(raw_o)["context"]["book"] == "John"
        st_w, _, raw_w = _get(f"{srv.url}api/word?surface={urllib.parse.quote('λόγος')}")
        assert st_w == 200 and json.loads(raw_w)["strongs"]["strongs"] == "G3056"

        # POST routes (valid loopback)
        st_an, raw_an = _post(f"{srv.url}api/analyze-text", {"text": "Ἐν ἀρχῇ ἦν ὁ λόγος."})
        assert st_an == 200 and len(json.loads(raw_an)["blocks"][0]["tokens"]) == 5
        st_sc, raw_sc = _post(f"{srv.url}api/scan", {"lines": ["μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"], "meter": "hexameter"})
        assert st_sc == 200 and json.loads(raw_sc)["results"][0]["caesura"] == "penthemimeral"

        # CSRF cross-origin POST guard -> 403
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _post(f"{srv.url}api/analyze-text", {"text": "λόγος"}, origin="https://evil.example")
        assert exc_info.value.code == 403

        # Unknown route -> 404
        with pytest.raises(urllib.error.HTTPError) as nf_info:
            _get(f"{srv.url}api/nonexistent")
        assert nf_info.value.code == 404


def test_cli_browse_and_tui_browser_integration() -> None:
    """`aegean browse --help`, lazy `aegean.browser`, and TUI web launch hook all resolve cleanly."""
    assert "browser" in dir(aegean)
    assert callable(aegean.browser.serve)

    pytest.importorskip("typer")
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    runner = CliRunner()
    res = runner.invoke(_build_app(), ["browse", "--help"])
    assert res.exit_code == 0, res.output
    assert "--port" in res.output
    assert "--neural" in res.output
    assert "--offline" in res.output

    pytest.importorskip("textual")
    from aegean.tui.app import AegeanApp

    app = AegeanApp(corpus="greek")
    binding_keys = [b.key for b in app.BINDINGS if hasattr(b, "key")]
    assert "v" in binding_keys
    app.action_open_browser(open_browser=False)
    try:
        assert app._browser_server is not None
        assert app._browser_server.url.startswith("http://localhost:")
    finally:
        app.on_unmount()
        assert app._browser_server is None
