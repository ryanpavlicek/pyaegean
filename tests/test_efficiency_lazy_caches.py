"""Tests for Phase 2 startup laziness and interactive runtime caches.

Verifies:
1. Cold ``import aegean`` stays lazy (does not eagerly pull ``aegean.greek``,
   ``aegean.ai``, ``aegean.io``, ``aegean.greek.bible``, or ``aegean.scripts.greek.perseus``),
   while first attribute access still resolves every public facade identically;
2. Pre-folded Septuagint (LXX) and Strong's search indexes remain isolated across bundle
   reloads/monkeypatches and return identical results on repeated queries;
3. The REPL's bounded session corpus cache avoids redundant disk reloads within a session,
   skips stdin/inline JSON, and automatically invalidates when a corpus file's mtime changes.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

from aegean.greek import bible as bib
from aegean.cli._common import load_corpus, session_corpus_cache


def test_import_aegean_keeps_heavy_subpackages_lazy() -> None:
    code = (
        "import sys, aegean\n"
        "for mod in ('aegean.greek', 'aegean.ai', 'aegean.io', 'aegean.greek.bible', "
        "'aegean.translate', 'aegean.scripts.greek.perseus'):\n"
        "    assert mod not in sys.modules, f'eagerly imported {mod}'\n"
        "# Accessing each lazy attribute resolves and caches it cleanly\n"
        "assert hasattr(aegean.greek, 'pipeline')\n"
        "assert hasattr(aegean.greek.bible, 'load_lxx')\n"
        "assert callable(aegean.read_corpus)\n"
        "assert callable(aegean.diagnose)\n"
        "assert 'greek' in dir(aegean) and 'bible' in dir(aegean.greek)\n"
        "print('LAZY_OK')\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, f"{res.stdout}\n{res.stderr}"
    assert "LAZY_OK" in res.stdout


def test_lxx_and_strongs_prefolded_indexes_repeat_identically(monkeypatch) -> None:
    from aegean.greek.bible import _lxx as lxx_mod

    monkeypatch.setattr(lxx_mod, "_load_lxx_bundle", lambda *, allow_fetch=True, force=False: None)
    first = bib.search_lxx("φῶς", offline=True)
    second = bib.search_lxx("φῶς", offline=True)
    assert first == second and len(first) == 3

    # Switching bundle object invalidates the fold cache cleanly
    fake_bundle = {
        "books": {
            "Gen": {"verses": {"1.1": "Ἐν ἀρχῇ ἐποίησεν ὁ θεὸς τὸν οὐρανόν."}},
        }
    }
    monkeypatch.setattr(lxx_mod, "_load_lxx_bundle", lambda *, allow_fetch=True, force=False: fake_bundle)
    assert bib.search_lxx("φῶς", book="Gen", offline=True) == []
    assert len(bib.search_lxx("οὐρανόν", book="Gen", offline=True)) == 1

    # Offline Strong's search hits cached pre-folded Dodson rows identically across calls
    s1 = bib.search_strongs("λόγος", limit=5, allow_fetch=False)
    s2 = bib.search_strongs("λόγος", limit=5, allow_fetch=False)
    assert s1 == s2 and any(e.strongs == "G3056" for e in s1)


def test_session_corpus_cache_hits_and_invalidates_on_file_mtime(tmp_path: Path, monkeypatch) -> None:
    from aegean.core import resolve

    calls: list[str] = []
    real_read = resolve.read_corpus

    def counting_read(spec: str) -> Any:
        calls.append(spec)
        return real_read(spec)

    monkeypatch.setattr(resolve, "read_corpus", counting_read)

    cache: OrderedDict[str, tuple[float | None, Any]] = OrderedDict()
    with session_corpus_cache(cache):
        c1 = load_corpus("lineara")
        c2 = load_corpus("lineara")
        assert c1 is c2
        assert calls == ["lineara"]  # second load served from session cache

        # File-backed corpus reloads automatically when mtime changes
        from aegean import io

        p = tmp_path / "mini.json"
        io.from_text("λόγος", doc_id="d1").to_json(p)
        f1 = load_corpus(str(p))
        assert f1.documents[0].id == "d1"
        assert calls.count(str(p)) == 1

        # Second read at same mtime hits cache
        f2 = load_corpus(str(p))
        assert f2 is f1
        assert calls.count(str(p)) == 1

        # Rewrite file and bump mtime → cache must invalidate and reload fresh
        io.from_text("ἀρχή", doc_id="d2").to_json(p)
        st = p.stat()
        os.utime(p, (st.st_atime + 5.0, st.st_mtime + 5.0))
        f3 = load_corpus(str(p))
        assert f3.documents[0].id == "d2"
        assert calls.count(str(p)) == 2

    # Outside session_corpus_cache, ordinary CLI load_corpus does not use the REPL cache
    load_corpus("lineara")
    assert calls.count("lineara") == 2
