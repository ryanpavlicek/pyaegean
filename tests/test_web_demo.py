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


def test_demo_html_wiring() -> None:
    html = (_DEMO_DIR / "index.html").read_text(encoding="utf-8")
    assert 'fetch("demo.py")' in html                 # loads the tested Python module
    assert "cdn.jsdelivr.net/pyodide/v0.28.0" in html  # pinned Pyodide build (verified to exist)
    assert 'micropip.install("pyaegean")' in html      # installs the package in-browser
    # every JS-referenced tool exists in the demo module
    demo = _load_demo()
    for name in ("greek_pipeline", "greek_scan", "betacode", "lineara_search"):
        assert hasattr(demo, name) and f'"{name}"' in html
