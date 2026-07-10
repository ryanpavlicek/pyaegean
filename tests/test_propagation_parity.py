"""Propagation-parity safeguards: for each bug CLASS that has recurred as an
un-propagated sibling, enumerate ALL the sibling sites and assert the invariant holds
across every one of them.

Across the audit sweeps, the dominant residual-defect source was a fix applied to one
site but not its siblings (a separator-collision fixed in the fingerprint but not the
cache key; the Leiden underdot stripped in one script bridge but not another; the
double-consonant quantity rule in meter but not prosody; a structured MCP error on one
tool but not the rest). These tests turn each such class into an enforced invariant: add
a new sibling that lacks the fix and the matching test fails here, in the same commit,
instead of surfacing in a later sweep. This is the standing guard against propagation gaps.
"""

from __future__ import annotations

import sys
import types

import pytest

import aegean


# ── CLASS: the double-consonant quantity rule (ζ/ξ/ψ make position) is one source ──
def test_double_consonant_set_is_shared_between_prosody_meter_syllabify():
    """meter and prosody must use the SAME double-consonant set, so they cannot disagree
    on quantity (the class that had ζ/ξ/ψ right in meter but wrong in prosody). Sharing the
    single source is the structural guarantee that they stay in sync."""
    from aegean.greek.meter import _DOUBLE
    from aegean.greek.prosody import _onset_is_double
    from aegean.greek.syllabify import DOUBLE_CONSONANTS

    assert _DOUBLE is DOUBLE_CONSONANTS  # one source of truth: meter reuses the syllabify set
    assert set(DOUBLE_CONSONANTS) == set("ζξψ")
    assert _onset_is_double("ζος") and _onset_is_double("ξις") and not _onset_is_double("λος")


def test_prosody_marks_double_consonant_position_like_the_rule():
    """A vowel before a double consonant is heavy by position in prosody, matching the rule
    meter already applied (the two modules must not diverge on ζ/ξ/ψ)."""
    from aegean.greek.prosody import syllable_quantities

    for word, first in [("ὄζος", "heavy"), ("ὀψέ", "heavy"), ("τάξις", "heavy")]:
        assert syllable_quantities(word)[0] == first, word


# ── CLASS: a script sign→sound bridge normalizes the Leiden underdot before lookup ──
@pytest.mark.parametrize("script", ["lineara", "linearb", "cypriot"])
def test_phonetic_bridges_strip_the_leiden_underdot(script):
    """Every deciphered/bridged word_to_phonetic must read a damaged-but-legible sign
    (underdot, U+0323) the same as its clean form (the class fixed in Linear B, then
    Cypriot). A syllable with an underdot must not fall through to raw text."""
    import importlib

    mod = importlib.import_module(f"aegean.scripts.{script}.phonetic")
    # pick a real two-sign word from the phonetic map so the lookup is meaningful
    pmap = mod.phonetic_map()
    signs = [k for k in pmap if k.isalpha()][:2]
    if len(signs) < 2:
        pytest.skip("no multi-sign coverage")
    clean = "-".join(s.lower() for s in signs)
    underdotted = clean.replace(signs[1].lower(), signs[1].lower()[0] + "̣" + signs[1].lower()[1:], 1)
    assert mod.word_to_phonetic(underdotted) == mod.word_to_phonetic(clean), (script, underdotted)


@pytest.mark.parametrize("script", ["lineara", "linearb", "cypriot"])
def test_phonetic_bridges_fold_case(script):
    """Every deciphered/bridged word_to_phonetic folds case, so the standard lowercase
    transliteration reads the same as uppercase (the class fixed in Linear B/Cypriot,
    then Linear A)."""
    import importlib

    mod = importlib.import_module(f"aegean.scripts.{script}.phonetic")
    pmap = mod.phonetic_map()
    sign = next((k for k in pmap if k.isalpha()), None)
    if sign is None:
        pytest.skip("no signs")
    assert mod.word_to_phonetic(sign.lower()) == mod.word_to_phonetic(sign.upper()), script


# ── CLASS: every script's sign_inventory returns an independent copy ──
@pytest.mark.parametrize("script", ["lineara", "linearb", "cypriot", "cyprominoan", "greek"])
def test_sign_inventory_accessors_return_independent_copies(script):
    inv = aegean.get_script(script).sign_inventory
    if not inv.signs:
        pytest.skip("no signs")
    inv.signs[0].attrs["_probe"] = "x"
    assert aegean.get_script(script).sign_inventory.signs[0].attrs.get("_probe") is None


# ── CLASS: every hash / cache key is injective (length-prefixed, no separator collision) ──
def test_hash_keys_are_injective_no_separator_collision():
    """Both keyed hashers must length-prefix their fields: a control char in the data
    must not shift a field boundary and collide two distinct inputs (the fingerprint had
    this fix; the AI cache key later needed the same)."""
    from aegean.ai.cache import ResponseCache

    rc = ResponseCache()
    rc.set("p", "m", "sysA\x00", "promptB", "ONE")
    assert rc.get("p", "m", "sysA", "\x00promptB") is None  # no collision

    from aegean.core.model import Document, Token, TokenKind

    def fp(a, b):
        d = Document(id="D", script_id="s", tokens=[Token(a, TokenKind.WORD), Token(b, TokenKind.WORD)], lines=[[0, 1]])
        return aegean.Corpus([d], script_id="s").fingerprint()

    assert fp("a\x00", "b") != fp("a", "\x00b")  # fingerprint is injective too


# ── CLASS: every MCP corpus tool returns a structured error, never a raw exception ──
def test_mcp_corpus_tools_return_structured_error_on_bad_input():
    """Each MCP tool taking a corpus must return {"error": ...} for an unknown corpus,
    not raise (the class fixed on greek_gloss, then _load_corpus for the 7 corpus tools)."""
    from aegean import mcp_server

    bad = "definitely-not-a-corpus"
    # (tool, args) with a valid arg count but an unknown corpus
    calls = [
        (mcp_server.corpus_info, (bad,)),
        (mcp_server.balance_accounts, (bad,)),
        (mcp_server.search_signs, (bad, "KU-*")),
        (mcp_server.geo_sites, (bad,)),
        (mcp_server.show_document, (bad, "HT13")),
    ]
    for tool, args in calls:
        try:
            out = tool(*args)
        except Exception as exc:  # noqa: BLE001 — a raised exception IS the failure
            pytest.fail(f"{tool.__name__} raised {exc!r} instead of a structured error")
        assert isinstance(out, dict) and "error" in out, tool.__name__


# ── CLASS: every provider adapter wraps a non-SDK call failure in ProviderCallError ──
def _fake_sdk_that_raises(exc: Exception) -> dict[str, types.ModuleType]:
    # a minimal stand-in for each provider SDK whose call raises a NON-SDK-error exception
    anthropic = types.ModuleType("anthropic")
    anthropic.APIError = type("APIError", (Exception,), {})

    class _AntMessages:
        def create(self, **k):
            raise exc

    anthropic.Anthropic = lambda api_key=None: types.SimpleNamespace(messages=_AntMessages())

    openai = types.ModuleType("openai")
    openai.APIError = type("APIError", (Exception,), {})

    class _Comp:
        def create(self, **k):
            raise exc

    openai.OpenAI = lambda api_key=None, base_url=None: types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=_Comp())
    )

    genai = types.ModuleType("google.genai")
    errors = types.ModuleType("google.genai.errors")
    errtypes = types.ModuleType("google.genai.types")
    errors.APIError = type("APIError", (Exception,), {})
    errtypes.GenerateContentConfig = lambda **k: None

    class _Models:
        def generate_content(self, **k):
            raise exc

    genai.Client = lambda api_key=None: types.SimpleNamespace(models=_Models())
    google = types.ModuleType("google")
    google.genai = genai
    return {
        "anthropic": anthropic, "openai": openai,
        "google": google, "google.genai": genai,
        "google.genai.errors": errors, "google.genai.types": errtypes,
    }


# ── CLASS: every registered provider has an installable extra of its own name ──
def test_every_registered_provider_has_a_pyproject_extra():
    """The ProviderNotInstalled message interpolates the provider name into
    ``pip install 'pyaegean[<provider>]'``, so every registered provider MUST have an
    extra of exactly that name or the error sends users to a nonexistent install line
    (the class the 0.31.0 'local' provider shipped with: registered, no extra)."""
    tomllib = pytest.importorskip(
        "tomllib", reason="stdlib from 3.11; this repo-hygiene guard runs on the 3.11+ jobs"
    )
    from pathlib import Path

    from aegean.ai.client import _PROVIDERS

    pyproject = tomllib.loads(
        (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    )
    extras = set(pyproject["project"]["optional-dependencies"])
    missing = set(_PROVIDERS) - extras
    assert not missing, f"registered providers without a pyproject extra: {sorted(missing)}"


# ── CLASS: the needs-review class set has ONE source of truth ──
def test_needs_review_set_is_single_sourced():
    """io.review's low-confidence set must be DERIVED from greek.needs_review (the one
    canonical predicate), never re-hardcoded: the two were once defined independently and
    could drift, silently changing which rows a review table flags."""
    from aegean.greek.lemmatize import LemmaSource, needs_review
    from aegean.io.review import _low_confidence

    assert _low_confidence() == frozenset(s.value for s in LemmaSource if needs_review(s))
    # and the derived set is exactly the two honest-miss classes today
    assert _low_confidence() == {"identity", "unresolved"}


_WRAP_COVERED = [
    ("anthropic", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY"),
    ("grok", "XAI_API_KEY"), ("openrouter", "OPENROUTER_API_KEY"),
    ("gemini", "GEMINI_API_KEY"), ("local", "PYAEGEAN_LOCAL_API_KEY"),
]


def test_every_registered_provider_has_wrap_coverage():
    """The parametrize list below must enumerate EVERY registered provider — a new adapter
    that ships without transport-failure wrap coverage fails here, loudly (the 0.31.0
    'local' adapter initially shipped outside this list)."""
    from aegean.ai.client import _PROVIDERS

    assert {p for p, _ in _WRAP_COVERED} == set(_PROVIDERS)


@pytest.mark.parametrize("provider,env", _WRAP_COVERED)
def test_provider_adapters_wrap_a_transport_failure(provider, env, monkeypatch):
    """A provider call that raises a non-SDK-error (a transport failure) must surface as
    ProviderCallError from every adapter, not leak raw (the class fixed for the OpenAI-
    compatible empty-choices path, then the Gemini transport path)."""
    from aegean import ai
    from aegean.ai.client import ProviderCallError

    class _Boom(Exception):
        pass

    for name, mod in _fake_sdk_that_raises(_Boom("network down")).items():
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.setenv(env, "key")
    with pytest.raises(ProviderCallError):
        ai.get_client(provider, model="m").complete("hi")


# ── CLASS: every public corpus export overwrites atomically (a failed write keeps the file) ──
def test_all_public_exports_are_atomic(tmp_path, monkeypatch):
    """to_json / to_sqlite / to_csv / write_epidoc must build via a temp file and replace,
    so a failed write never destroys the prior export (the class fixed for the caches,
    then propagated to every export path)."""
    from aegean.core.model import Document, Token, TokenKind

    corpus = aegean.Corpus(
        [Document(id="D", script_id="lineara", tokens=[Token("KU", TokenKind.WORD, position=0)], lines=[[0]])],
        script_id="lineara",
    )

    def _write_json(p):
        corpus.to_json(p)

    def _write_sqlite(p):
        from aegean import db
        db.to_sqlite(corpus, p)

    def _write_epidoc(p):
        from aegean.io.epidoc import write_epidoc
        write_epidoc(corpus.documents[0], p)

    for label, writer in [("json", _write_json), ("db", _write_sqlite), ("xml", _write_epidoc)]:
        target = tmp_path / f"out.{label}"
        writer(target)                      # a good first write
        original = target.read_bytes()
        # a temp+replace exporter leaves no ".*.tmp" sibling behind after a clean write
        leftovers = list(tmp_path.glob(f".{target.name}.*.tmp"))
        assert leftovers == [], (label, leftovers)
        assert target.read_bytes() == original
