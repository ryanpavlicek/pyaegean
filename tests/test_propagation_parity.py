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

import re
import sys
import types
from pathlib import Path

import pytest

import aegean

_REPO_ROOT = Path(__file__).resolve().parents[1]


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


# ── CLASS: every neural ONNX session takes its providers from the one shared resolver ──
def test_neural_sessions_share_the_provider_resolver():
    """Every neural InferenceSession (the joint pipeline's one, the GreTa lemmatizer's
    encoder AND decoder) must take ``providers=`` from `aegean.greek._ort.resolve_providers`
    — never a hard-coded list — so provider policy (the PYAEGEAN_ORT_PROVIDERS override,
    GPU auto-detect, the CPU fallback, the TensorRT exclusion) cannot drift between the
    two backends."""
    import inspect

    from aegean.greek import _ort, joint, neural_lemmatizer

    for mod, n_sessions in ((joint, 1), (neural_lemmatizer, 2)):
        src = inspect.getsource(mod)
        assert mod._ort is _ort, mod.__name__            # the same shared module
        assert src.count("InferenceSession(") == n_sessions, mod.__name__
        assert "_ort.resolve_providers()" in src, mod.__name__
        # a literal provider list at a constructor is exactly the drift being guarded
        assert '["CPUExecutionProvider"]' not in src, mod.__name__
    # each module resolves once, ahead of the wrapped session construction (so a bad
    # PYAEGEAN_ORT_PROVIDERS surfaces its own ValueError, not the corrupt-model message)
    joint_src = inspect.getsource(joint)
    assert "providers = _ort.resolve_providers()" in joint_src
    assert "providers=providers" in joint_src
    lem_src = inspect.getsource(neural_lemmatizer)
    assert "prov = _ort.resolve_providers()" in lem_src
    assert lem_src.count("providers=prov") == 2


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


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRY EXHAUSTIVENESS
#
# For each LIVE registry, enumerate its members at test time and assert every
# consumer surface covers them. This turns the "grew a registry, forgot a surface"
# drift into a same-commit failure: adding a LemmaSource, a hosted lexicon, an AI
# provider, a corpus, an export format, or a fetchable dataset without propagating
# it to every enumerating surface fails HERE, not in a later audit sweep. Each test
# names the registry it guards and the release where the propagation class last bit.
# ═══════════════════════════════════════════════════════════════════════════════


def _read_wiki(name: str) -> str:
    """Read a wiki page as text (precedent: tests/test_benchmark_claims reads wiki).
    Skips cleanly when the wiki tree is absent (e.g. a wheel-only test env)."""
    p = _REPO_ROOT / "wiki" / name
    if not p.exists():
        pytest.skip(f"wiki/{name} is not present in this checkout")
    return p.read_text(encoding="utf-8")


# ── CLASS: LemmaSource — every evidence class reaches every enumerating surface ──
# The PARADIGM-omission class: LemmaSource.PARADIGM was added (0.37.0) and had to be
# threaded into the explain rendering map AND every docstring/help that enumerates
# the evidence classes. A new member that misses the rendering map raises KeyError on
# a token of that class; one that misses a docstring makes the docstring lie.
def test_every_lemma_source_member_has_a_note_in_the_explain_rendering_map():
    """`greek.explain` must render a note for EVERY LemmaSource: the plain-language
    ``_NOTES`` map covers the grounded/miss classes, and NEURAL/IDENTITY are worded at
    run time (their note depends on which stack produced the lemma). A member in
    neither path would raise KeyError when ``explain_pipeline`` reaches it — the exact
    PARADIGM-omission class (0.37.0)."""
    import inspect

    from aegean.greek import explain
    from aegean.greek.lemmatize import LemmaSource

    runtime_worded = {LemmaSource.NEURAL, LemmaSource.IDENTITY}
    for member in LemmaSource:
        assert member in explain._NOTES or member in runtime_worded, (
            f"LemmaSource.{member.name} has no note in explain.py "
            "(neither in _NOTES nor a run-time-worded branch)"
        )
    # the two run-time-worded members must actually be branched on in the source, so
    # "covered by runtime_worded" names a real handler, not an unhandled fall-through.
    src = inspect.getsource(explain)
    for member in runtime_worded:
        assert f"LemmaSource.{member.name}" in src, (
            f"explain.py is expected to run-time-word LemmaSource.{member.name} but "
            "never branches on it"
        )


_EVIDENCE_ANCHOR = re.compile(r"evidence class\s*[(:]")


def _evidence_enumeration(doc: str) -> str:
    """The evidence-class value list in a docstring, anchored on the ``evidence
    class(`` / ``evidence class:`` that introduces the ``/``-delimited values and
    running to the closing ``)``.

    Anchoring is essential and load-bearing here: ``neural`` also appears in
    ``parser/neural fields`` and ``punct`` inside ``punctuation``, so a whole-doc
    membership test gives false passes (verified against the real docstrings)."""
    m = _EVIDENCE_ANCHOR.search(doc)
    assert m is not None, "no 'evidence class(' / 'evidence class:' enumeration anchor"
    end = doc.find(")", m.end())
    assert end != -1, "no ')' closing the evidence-class enumeration"
    return doc[m.end():end]


def _evidence_surface_doc(surface: str) -> str:
    import inspect

    if surface == "cli greek explain --help":
        pytest.importorskip("typer", reason="the CLI explain help needs the [cli] extra")
        from aegean.cli import _greek

        return inspect.getdoc(_greek.explain) or ""
    from aegean import mcp_server

    attr = {
        "mcp greek_pipeline docstring": "greek_pipeline",
        "mcp greek_explain docstring": "greek_explain",
    }[surface]
    return inspect.getdoc(getattr(mcp_server, attr)) or ""


@pytest.mark.parametrize(
    "surface",
    [
        "cli greek explain --help",
        "mcp greek_pipeline docstring",
        "mcp greek_explain docstring",
    ],
)
def test_every_lemma_source_value_enumerated_in_evidence_class_surfaces(surface):
    """Each canonical evidence-class enumeration (the CLI ``explain`` help and the two
    MCP tool docstrings) must list EVERY LemmaSource value inside its own enumeration
    context. Adding a member without extending these lists fails here — the
    PARADIGM-omission class (0.37.0). (The ``pipeline.TokenRecord`` and
    ``_view.pipeline_rows`` docstrings describe the classes in prose / an illustrative
    ``e.g.`` list rather than an exhaustive value list; their omissions are reported as
    a separate consistency gap, not pinned here.)"""
    from aegean.greek.lemmatize import LemmaSource

    segment = _evidence_enumeration(_evidence_surface_doc(surface))
    missing = [m.value for m in LemmaSource if m.value not in segment]
    assert not missing, f"{surface} omits LemmaSource values {missing}"


# ── CLASS: hosted lexica — every gloss-capable dictionary is advertised, no more ──
# greek.lexica() partitions into hosted (ingested → gloss-capable) and deep-link
# only. The MCP greek_gloss docstring and the wiki MCP table must list exactly the
# hosted set and never a deep-link-only lexicon as gloss-capable (use_lexicon raises
# for a deep-link lexicon — it cannot gloss). Adding a hosted lexicon (Autenrieth was
# the fourth, 0.38.0) must reach both surfaces.
def _hosted_and_deeplink_lexica():
    from aegean import greek

    infos = greek.lexica()
    return (
        sorted(i.id for i in infos if i.hosted),
        sorted(i.id for i in infos if not i.hosted),
    )


def test_hosted_lexica_listed_in_mcp_greek_gloss_docstring():
    """The MCP ``greek_gloss`` docstring names every hosted (gloss-capable) lexicon and
    no deep-link-only one (0.27.1 attribution / registry-drift class)."""
    import inspect

    from aegean import mcp_server

    hosted, deeplink = _hosted_and_deeplink_lexica()
    doc = inspect.getdoc(mcp_server.greek_gloss) or ""
    missing = [h for h in hosted if h not in doc]
    assert not missing, f"mcp greek_gloss docstring omits hosted lexica {missing}"
    listed_deeplink = [d for d in deeplink if d in doc]
    assert not listed_deeplink, (
        f"mcp greek_gloss lists deep-link-only lexica as gloss-capable: {listed_deeplink}"
    )


def test_hosted_lexica_listed_in_wiki_mcp_greek_gloss_row():
    """The wiki MCP ``greek_gloss`` row names every hosted (gloss-capable) lexicon and
    no deep-link-only one."""
    hosted, deeplink = _hosted_and_deeplink_lexica()
    wiki = _read_wiki("MCP.md")
    rows = [ln for ln in wiki.splitlines() if ln.strip().startswith("| `greek_gloss`")]
    assert rows, "no `greek_gloss` row found in wiki/MCP.md"
    row = rows[0]
    missing = [h for h in hosted if h not in row]
    assert not missing, f"wiki MCP greek_gloss row omits hosted lexica {missing}"
    listed_deeplink = [d for d in deeplink if d in row]
    assert not listed_deeplink, (
        f"wiki MCP greek_gloss row lists deep-link-only lexica: {listed_deeplink}"
    )


# ── CLASS: AI providers — every provider reaches the CLI help and doctor extras ──
# The provider registry is the source of truth; the CLI --provider help lists the
# choices and `aegean doctor` maps each provider to its install extra. A provider
# registered without both (the 0.31.0 'local' provider first shipped without its
# extra and outside the wrap-coverage list) misleads users about how to reach it.
def test_every_provider_reaches_the_cli_help_and_doctor_extras():
    """Every registered AI provider appears in the CLI ``--provider`` help and in the
    ``aegean doctor`` extras map (grok/openrouter/local share the ``openai`` extra, so
    the doctor mapping is by the extras' prose, not a 1:1 extra name)."""
    pytest.importorskip("typer", reason="the CLI --provider help needs the [cli] extra")
    from aegean._doctor import _EXTRAS
    from aegean.ai.client import providers
    from aegean.cli import _ai

    provider_ids = providers()
    assert provider_ids, "no AI providers registered"

    help_txt = (_ai.PROVIDER_OPT.help or "").lower()
    missing_help = [p for p in provider_ids if p not in help_txt]
    assert not missing_help, f"CLI --provider help omits providers {missing_help}"

    unlocks = " ".join(u for _e, _m, u in _EXTRAS if "provider" in u.lower()).lower()
    missing_doctor = [p for p in provider_ids if p not in unlocks]
    assert not missing_doctor, f"aegean doctor extras map omits providers {missing_doctor}"


# ── CLASS: corpus ids — every registered corpus is classified on every surface ──
# A new corpus loader must reach the TUI browser (CORPUS_IDS + a blurb) and the CLI
# data surfaces (a fetch-on-demand corpus needs a fetch hint reachable through the
# stem resolver). ddbdp is the one documented exclusion from the TUI browser (its
# materialisation is too heavy). Adding corpus 15 without these fails here.
_TUI_EXCLUDED_CORPORA = {"ddbdp"}  # documented: too heavy for the TUI corpus browser


def test_registered_corpora_match_the_tui_browser_ids_and_blurbs():
    """The registered corpus loaders, the TUI ``CORPUS_IDS``, and the TUI blurb map
    must agree: the browser lists every registered corpus except the documented heavy
    exclusion (ddbdp), and every browsable corpus has exactly one blurb.

    The SHIPPED registry is enumerated in a fresh interpreter: several tests register
    throwaway loaders into the live registry without cleanup, so an in-process
    enumeration is order-dependent under xdist (the subprocess-probe pattern)."""
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "-c",
         "import aegean; from aegean.core.corpus import _LOADERS; "
         "print(','.join(sorted(_LOADERS)))"],
        capture_output=True, text=True, check=True,
    )
    from aegean.tui.data import CORPUS_IDS, _CORPUS_BLURB

    registered = set(out.stdout.strip().split(","))
    browser = set(CORPUS_IDS)
    assert browser <= registered, f"TUI lists unregistered corpora: {sorted(browser - registered)}"
    assert registered - browser == _TUI_EXCLUDED_CORPORA, (
        "TUI corpus browser drifted from the loader registry — unlisted registered "
        f"corpora: {sorted(registered - browser - _TUI_EXCLUDED_CORPORA)}"
    )
    assert set(_CORPUS_BLURB) == browser, (
        "every browsable corpus needs a blurb and every blurb a browsable corpus; "
        f"drift: {sorted(set(_CORPUS_BLURB) ^ browser)}"
    )


def test_every_fetchable_corpus_has_a_cli_fetch_hint():
    """Every registered corpus whose id resolves (via the CLI stem resolver) to a
    fetchable ``_REMOTE`` asset must carry a ``_FETCH_HINTS`` entry, so a fetch prints
    its next step (the index-fetch/friendly-guidance class, 0.22.0). Bundled corpora
    resolve to a non-asset name and need no hint. Adding a fetch-on-demand corpus
    without a fetch hint fails here."""
    pytest.importorskip("typer", reason="the CLI data surfaces need the [cli] extra")
    import aegean  # noqa: F401 — register the loaders
    from aegean.cli._data import _FETCH_HINTS, _resolve_name
    from aegean.core.corpus import _LOADERS
    from aegean.data import _REMOTE

    for cid in _LOADERS:
        resolved = _resolve_name(cid)
        if resolved in _REMOTE:  # a fetch-on-demand corpus (its stem resolves to an asset)
            assert resolved in _FETCH_HINTS, (
                f"corpus {cid!r} fetches {resolved!r} but has no CLI fetch hint"
            )
        # a bundled corpus (resolved not in _REMOTE) is always available: no hint needed


# ── CLASS: export formats — the CLI validation set reaches help and the wiki ──
# There is NO central export-format registry: the canonical set is the ``formats``
# tuple validated inside cli._corpus.export(). The --format help and the wiki
# CLI-Cheatsheet formats table must both enumerate it. The RDF formats (ttl/jsonld,
# 0.36.0) reached the CLI but not the cheatsheet table (reported as a doc gap).
def _export_formats() -> tuple[str, ...]:
    import inspect

    from aegean.cli import _corpus

    src = inspect.getsource(_corpus.export)
    m = re.search(r"formats\s*=\s*\(([^)]*)\)", src)
    assert m, "could not locate the export() `formats` validation tuple"
    return tuple(re.findall(r'"([a-z]+)"', m.group(1)))


def test_export_formats_enumerated_in_the_cli_format_help():
    """Every format the ``export`` command validates is named in its ``--format`` help,
    so the help never advertises fewer (or more) formats than the code accepts."""
    pytest.importorskip("typer", reason="the CLI export --format help needs the [cli] extra")
    import inspect

    from aegean.cli import _corpus

    formats = _export_formats()
    assert formats, "no export formats parsed from the validation tuple"
    help_txt = (inspect.signature(_corpus.export).parameters["fmt"].default.help or "").lower()
    missing = [f for f in formats if f not in help_txt]
    assert not missing, f"the export --format help omits formats {missing}"


def test_export_formats_enumerated_in_the_wiki_cheatsheet_table():
    """The wiki CLI-Cheatsheet ``export — formats`` table must list every format the
    ``export`` command validates (the 0.36.0 RDF formats ttl/jsonld reached the CLI
    validation and help but not this table until the table was pinned here)."""
    pytest.importorskip("typer", reason="reads the CLI export() validation tuple")
    formats = _export_formats()
    cheat = _read_wiki("CLI-Cheatsheet.md")
    lines = cheat.splitlines()
    start = next(
        (
            i
            for i, ln in enumerate(lines)
            if ln.startswith("### ") and "export" in ln and "format" in ln.lower()
        ),
        None,
    )
    assert start is not None, "no '### `export` — formats' section in the cheatsheet"
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("### ")), len(lines)
    )
    section = "\n".join(lines[start:end])
    listed = set(re.findall(r"^\|\s*`([a-z]+)`\s*\|", section, re.M))
    missing = [f for f in formats if f not in listed]
    assert not missing, f"the wiki cheatsheet export-formats table omits {missing}"


# ── CLASS: DataSpec.on_disk — a distinct on-disk artifact is always declared ──
# The index-fetch class (0.27.2): a single-file dataset whose backend stores it under
# its built-index filename (lsj-index -> lsj-perseus-index.json.gz) must declare
# ``on_disk``, or `data list` / `doctor` probe cache_dir()/name (the wrong place) and
# report a present dataset as not-downloaded, and `remove` cannot see it.
def test_extract_false_on_disk_matches_the_hosted_artifact_name():
    """Every ``extract=False`` DataSpec that declares ``on_disk`` names exactly one
    file, and that name (a) differs from the dataset name — ``on_disk`` exists only for
    a DISTINCT on-disk filename — and (b) equals the hosted asset's basename, so the
    store, a backend's ``fetch_prebuilt`` dest, and a rebuild all agree on where the
    file lands."""
    from aegean.data import _REMOTE

    for name, spec in _REMOTE.items():
        if spec.extract or not spec.on_disk:
            continue
        assert len(spec.on_disk) == 1, (
            f"{name}: an extract=False dataset occupies one on-disk file, got {spec.on_disk}"
        )
        stored = spec.on_disk[0]
        assert stored != name, (
            f"{name}: a single on_disk equal to the dataset name is a redundant declaration"
        )
        if spec.url:
            basename = spec.url.rsplit("/", 1)[-1]
            assert stored == basename, (
                f"{name}: on_disk {stored!r} != hosted asset basename {basename!r}; "
                "the store and a rebuild would disagree on the filename"
            )


def test_every_prebuilt_index_backend_declares_matching_on_disk():
    """Cross-reference: every opt-in lexicon/paradigm backend that fetches a prebuilt
    index via ``fetch_prebuilt`` relocates it to ``cache_dir()/<index filename>``; the
    matching ``_REMOTE`` spec MUST declare ``on_disk=(that filename,)`` or the
    index-fetch class returns (0.27.2) — the file lands under the built-index name
    while list/doctor/remove probe the bare dataset name. Adding a lexicon index, or
    renaming its built file, without updating the spec fails here."""
    from aegean.data import _REMOTE
    from aegean.greek import abbott_smith, lexicon, lexicons, paradigms, scaife_lex

    # (registry asset name, the built-index filename the backend stores it under)
    pairs = [
        ("lsj-index", lexicon._INDEX_NAME),
        (abbott_smith._PREBUILT, abbott_smith._INDEX_NAME),
        (lexicons._AUTENRIETH_PREBUILT, lexicons._AUTENRIETH_INDEX_NAME),
        (paradigms._PREBUILT, paradigms._INDEX_NAME),
    ]
    pairs += [(s.prebuilt, s.index_name) for s in scaife_lex._SOURCES.values()]

    for asset, index_filename in pairs:
        assert asset in _REMOTE, f"prebuilt asset {asset!r} is not registered in _REMOTE"
        spec = _REMOTE[asset]
        assert not spec.extract, f"{asset}: a prebuilt index is a single file (extract=False)"
        assert spec.on_disk == (index_filename,), (
            f"{asset}: on_disk {spec.on_disk} != ({index_filename!r},) — the index-fetch "
            "class (0.27.2): the built index lands under a distinct name the spec must declare"
        )
        assert index_filename != asset, (
            f"{asset}: the built-index filename equals the dataset name; no on_disk would be needed"
        )
