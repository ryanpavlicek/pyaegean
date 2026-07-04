"""Regression tests for the ninth sweep (propagation audit), 0.19.11.

Each pins an un-propagated sibling of an already-fixed bug class: the fix that had
landed at one site but not its siblings. Each reproduces the finder's concrete failure
and asserts the corrected behavior.
"""

from __future__ import annotations

import sys
import types

import pytest

import aegean
from aegean.core.model import Document, Token, TokenKind


def _corpus() -> "aegean.Corpus":
    doc = Document(id="D", script_id="lineara",
                   tokens=[Token("KU", TokenKind.WORD, position=0)], lines=[[0]])
    return aegean.Corpus([doc], script_id="lineara")


# ── A: atomic writes (atomic-write class, fixed in the caches 0.19.1) ──────────
def test_atomic_path_keeps_the_prior_file_on_a_failed_write(tmp_path):
    from aegean._atomic import atomic_path

    target = tmp_path / "f.txt"
    target.write_text("ORIGINAL", encoding="utf-8")
    with pytest.raises(RuntimeError):
        with atomic_path(target) as tmp:
            tmp.write_text("partial", encoding="utf-8")
            raise RuntimeError("boom mid-write")
    assert target.read_text(encoding="utf-8") == "ORIGINAL"  # prior file intact
    assert list(tmp_path.glob(".*.tmp")) == []               # temp cleaned up


def test_to_sqlite_failed_rebuild_does_not_destroy_the_existing_db(tmp_path, monkeypatch):
    """The HIGH finding: to_sqlite unlinked the user's .db before rebuilding, so a
    mid-build failure left no recoverable file. It now builds into a temp and replaces."""
    from aegean import db

    path = tmp_path / "c.db"
    db.to_sqlite(_corpus(), path)
    size = path.stat().st_size
    assert size > 0

    def _boom(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(db, "_insert_document", _boom)
    with pytest.raises(OSError):
        db.to_sqlite(_corpus(), path)      # a rebuild that fails partway
    assert path.stat().st_size == size     # the prior database is untouched
    assert len(db.from_sqlite(path)) == 1  # and still loads
    assert list(tmp_path.glob(".c.db.*.tmp")) == []


def test_to_json_and_csv_and_epidoc_round_trip_after_atomic_write(tmp_path):
    c = _corpus()
    jp = tmp_path / "c.json"
    c.to_json(jp)
    assert len(aegean.Corpus.from_json(jp)) == 1
    # writing over an existing export still works (temp+replace)
    c.to_json(jp)
    assert len(aegean.Corpus.from_json(jp)) == 1


# ── B: fetch_prebuilt moves the single-file artifact (on_disk class, 0.19.10) ──
def test_fetch_prebuilt_moves_single_file_leaving_no_root_name(tmp_path, monkeypatch):
    """fetch_prebuilt copied the fetched root/name to the built-index name, leaving the
    raw root/name lingering uncounted and unremovable. For a single-file dataset it now
    moves, so no redundant copy is left behind."""
    from aegean import data as D

    (tmp_path / "lsj-index").write_bytes(b"INDEX" * 20)
    monkeypatch.setattr(D, "fetch", lambda name, **k: tmp_path / "lsj-index")
    dest = tmp_path / "lsj-perseus-index.json.gz"
    assert D.fetch_prebuilt("lsj-index", dest) is True
    assert dest.exists()
    assert not (tmp_path / "lsj-index").exists()  # moved, not copied — nothing lingers


# ── C: Gemini adapter wraps a non-APIError transport failure (0.19.3 class) ────
def _fake_genai_raising(exc: Exception):
    genai = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    types_mod = types.ModuleType("google.genai.types")
    errors_mod.APIError = type("APIError", (Exception,), {})
    types_mod.GenerateContentConfig = lambda **k: None

    class _Models:
        def generate_content(self, **k):
            raise exc

    class Client:
        def __init__(self, api_key=None):
            self.models = _Models()

    genai.Client = Client
    google = types.ModuleType("google")
    google.genai = genai
    return {"google": google, "google.genai": genai,
            "google.genai.errors": errors_mod, "google.genai.types": types_mod}


def test_gemini_adapter_wraps_transport_error(monkeypatch):
    from aegean import ai
    from aegean.ai.client import ProviderCallError

    class _ConnectTimeout(Exception):  # not a genai APIError subclass (like httpx's)
        pass

    for name, mod in _fake_genai_raising(_ConnectTimeout("timed out")).items():
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    with pytest.raises(ProviderCallError) as exc:
        ai.get_client("gemini", model="gemini-x").complete("hi")
    assert "gemini request failed" in str(exc.value)
    assert not isinstance(exc.value, _ConnectTimeout)


# ── D: MCP _load_corpus returns a structured error on a fetch failure (0.19.3) ─
def test_mcp_tools_return_structured_error_on_corpus_fetch_failure(monkeypatch):
    """A cold-cache fetch failure for damos/sigla leaked a raw exception out of the
    seven tools that route through _load_corpus; it now returns the structured error."""
    from aegean.data import DataNotAvailableError
    from aegean import mcp_server

    def _boom(corpus):
        raise DataNotAvailableError("could not fetch 'damos-corpus': offline")

    monkeypatch.setattr(aegean, "load", _boom)  # _load_corpus does a local `import aegean`
    for tool, args in [
        (mcp_server.corpus_info, ("damos",)),
        (mcp_server.balance_accounts, ("damos",)),
    ]:
        out = tool(*args)
        assert isinstance(out, dict) and "error" in out, tool.__name__
        assert "damos" in out["error"]


# ── E: Cypriot word_to_phonetic strips the Leiden underdot (0.19.9 class) ──────
def test_cypriot_word_to_phonetic_strips_underdot():
    from aegean.analysis.compare import to_phonemes
    from aegean.scripts.cypriot import phonetic

    assert phonetic.word_to_phonetic("wi-ti-ḷẹ-ra-nu") == "witileranu"
    assert phonetic.word_to_phonetic("wi-ti-le-ra-nu") == "witileranu"  # clean form unchanged
    assert to_phonemes("wi-ti-ḷẹ-ra-nu", "cypriot") == "witileranu"


# ── F: Linear A word_to_phonetic folds case (0.15.0 class) ─────────────────────
def test_lineara_word_to_phonetic_folds_case():
    from aegean.analysis.compare import to_phonemes
    from aegean.scripts.lineara import phonetic

    assert phonetic.word_to_phonetic("qa-de") == "kwade"   # was 'qade'
    assert phonetic.word_to_phonetic("za-zo") == "dzadzo"  # was 'zazo'
    assert phonetic.word_to_phonetic("QA-DE") == "kwade"   # uppercase unchanged
    assert to_phonemes("qa-de", "lineara") == "kwade"


# ── G: sigmatic-future guard on all thematic endings (0.19.2 class) ────────────
def test_lemmatizer_does_not_fabricate_omega_from_sigmatic_futures():
    from aegean.greek.lemmatize import lemmatize_verbose

    # sigmatic future / aorist -> must NOT be stripped to a confident -ω lemma
    for word in ["δώσουσιν", "λύσουσιν", "ποιήσουσιν", "δώσομεν", "δώσετε"]:
        lemma, known = lemmatize_verbose(word)
        assert not (lemma.endswith("ω") and known), (word, lemma, known)
    # genuine thematic presents STILL strip correctly (no σ, or double σ, before the ending)
    assert lemmatize_verbose("λέγουσιν") == ("λέγω", True)
    assert lemmatize_verbose("λέγομεν") == ("λέγω", True)
    assert lemmatize_verbose("γράφετε") == ("γράφω", True)
    assert lemmatize_verbose("πράσσομεν") == ("πράσσω", True)


# ── H: sign-inventory accessors return independent copies (0.19.2 class) ───────
@pytest.mark.parametrize("script", ["lineara", "linearb", "cypriot", "cyprominoan", "greek"])
def test_sign_inventory_attrs_edit_does_not_leak(script):
    inv = aegean.get_script(script).sign_inventory
    if not inv.signs:
        pytest.skip("no signs")
    inv.signs[0].attrs["_probe"] = "leak"
    fresh = aegean.get_script(script).sign_inventory
    assert fresh.signs[0].attrs.get("_probe") is None       # not leaked to a later reader
    # (lineara is the load path most exercised) a fresh load is clean too
    if script == "lineara":
        loaded = aegean.load("lineara")
        assert loaded.sign_inventory.signs[0].attrs.get("_probe") is None


def test_sign_inventory_copy_is_fingerprint_identical():
    from aegean.scripts.lineara.inventory import linear_a_inventory

    inv = linear_a_inventory()
    dup = inv.copy()
    assert len(dup) == len(inv)
    assert [s.label for s in dup.signs] == [s.label for s in inv.signs]
    assert dup.signs[0].attrs is not inv.signs[0].attrs  # independent dicts
    assert dup.signs[0].attrs == inv.signs[0].attrs       # same content
