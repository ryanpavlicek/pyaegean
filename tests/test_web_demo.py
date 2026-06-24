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
    from aegean.core.model import Document, DocumentMeta, Token, TokenKind
    from aegean.io import to_epidoc

    doc = Document(
        id="IG1", script_id="greek",
        tokens=[Token("λόγος", TokenKind.WORD, line_no=0, position=0)],
        lines=[[0]], meta=DocumentMeta(site="Athens", name="t"),
    )
    r = json.loads(demo.epidoc_import(to_epidoc(doc)))
    assert r["id"] == "IG1" and r["site"] == "Athens" and r["tokens"] == 1 and r["preview"] == ["λόγος"]
    assert "error" in json.loads(demo.epidoc_import("not xml"))


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
                 "bridge", "lineara_search", "lineara_balance", "import_text", "phonetic_compare",
                 "lexicon_link", "epidoc_import"):
        assert hasattr(demo, name) and f'"{name}"' in html
