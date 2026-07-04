"""Regression tests for the seventh adversarial sweep (0.19.9).

Each test pins one confirmed finding from the sweep of the surfaces the six prior
passes covered least: it reproduces the finder's concrete failure scenario and asserts
the fixed output, not merely that the call runs.
"""

from __future__ import annotations

import json
import sys
import types

import pytest

import aegean
from aegean.core.model import Document, Token, TokenKind


# ── Fix 1: db.search preserves a None position instead of int()-crashing ──────
def test_db_search_preserves_none_position(tmp_path):
    """A token stored without a position (0.19.4 made this a supported, round-tripped
    state) must be *findable*: db.search int()-coerced the position and crashed
    ``TypeError`` on the None case, in both token and substring modes."""
    from aegean import db

    doc = Document(
        id="D",
        script_id="lineara",
        tokens=[Token("FIRST", TokenKind.WORD, position=0), Token("APPENDED", TokenKind.WORD)],
        lines=[[0, 1]],
    )
    path = tmp_path / "c.db"
    db.to_sqlite(aegean.Corpus([doc], script_id="lineara"), path)

    # the matching token has position=None; both modes must return it, not raise
    assert db.search(path, "APPENDED") == [("D", None, "APPENDED")]
    assert db.search(path, "APPEND", mode="substring") == [("D", None, "APPENDED")]
    # a positioned token still returns its int position
    assert db.search(path, "FIRST") == [("D", 0, "FIRST")]


# ── Fix 2: OpenAI-compatible adapter wraps an empty choices list ──────────────
def _fake_openai_empty_choices() -> types.ModuleType:
    mod = types.ModuleType("openai")

    class _Resp:
        choices: list = []          # HTTP 200 with no choices (OpenRouter error/moderation)
        error = {"message": "upstream vendor error", "code": 502}

    class _Completions:
        def create(self, **kwargs):
            return _Resp()

    class _Chat:
        def __init__(self) -> None:
            self.completions = _Completions()

    class OpenAI:
        def __init__(self, api_key=None, base_url=None):
            self.chat = _Chat()

    mod.OpenAI = OpenAI  # type: ignore[attr-defined]
    mod.APIError = type("APIError", (Exception,), {})  # type: ignore[attr-defined]
    return mod


def test_openai_adapter_raises_clean_error_on_empty_choices(monkeypatch):
    """A 200 response with ``choices=[]`` (OpenRouter's shape when an upstream vendor
    errors or moderation fires) must raise a clean ProviderCallError, not the raw
    IndexError that ``resp.choices[0]`` produced outside the SDK-error wrapping."""
    from aegean import ai
    from aegean.ai.client import ProviderCallError

    monkeypatch.setitem(sys.modules, "openai", _fake_openai_empty_choices())
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")

    with pytest.raises(ProviderCallError) as exc:
        ai.get_client("openrouter", model="vendor/model").complete("q")
    msg = str(exc.value)
    assert "no choices" in msg and "vendor/model" in msg
    assert not isinstance(exc.value, IndexError)


# ── Fix 3: response-cache key is injective (no NUL separator collision) ────────
def test_cache_key_no_nul_collision():
    """The cache key length-prefixes its fields, so a NUL in the text cannot shift a
    field boundary and collide two logically-distinct requests (which would serve one
    the other's cached completion). Mirrors the Corpus.fingerprint fix."""
    from aegean.ai.cache import ResponseCache

    rc = ResponseCache()
    rc.set("anthropic", "m", "sysA\x00", "promptB", "ANSWER-1")
    # a genuinely different (system, prompt) split must MISS, not collide
    assert rc.get("anthropic", "m", "sysA", "\x00promptB") is None
    # the original request still hits
    assert rc.get("anthropic", "m", "sysA\x00", "promptB") == "ANSWER-1"


def test_cache_reads_pre_0_19_9_format_file(tmp_path):
    """The key scheme changed in 0.19.9, but a cache file written by an earlier release
    (an opaque-hash-keyed JSON object) must still LOAD without error — its entries simply
    miss under the new key and recompute. A cache format change must not break reads."""
    from aegean.ai.cache import ResponseCache

    legacy = tmp_path / "cache.json"
    legacy.write_text(json.dumps({"deadbeefcafe" * 4: "an old completion"}), encoding="utf-8")
    rc = ResponseCache(legacy)  # must not raise
    assert len(rc) == 1


# ── Fix 4: MCP greek_gloss returns a structured error on a fetch/build failure ─
def test_mcp_greek_gloss_structured_error_on_fetch_failure(monkeypatch):
    """A cold-cache/offline first use of a hosted dictionary raises DataNotAvailableError
    out of use_lexicon; greek_gloss must return the surface's ``{"error": ...}`` payload,
    not leak a raw exception."""
    from aegean import greek, mcp_server
    from aegean.data import DataNotAvailableError

    def _boom(_dictionary):
        raise DataNotAvailableError("could not fetch 'lsj-index' from ...: offline")

    monkeypatch.setattr(greek, "use_lexicon", _boom)
    out = mcp_server.greek_gloss("λόγος", dictionary="lsj")
    assert isinstance(out, dict) and "error" in out
    assert "lsj" in out["error"] and "offline" in out["error"]


# ── Fix 5: Linear B word_to_phonetic strips the Leiden underdot ───────────────
def test_linearb_underdot_normalized():
    """A damaged-but-legible sign (Leiden underdot U+0323) must resolve to its settled
    phonetic value, matching the sibling lexicon bridge, not fall through to its raw
    transliteration."""
    from aegean.analysis.compare import to_phonemes
    from aegean.scripts.linearb import phonetic

    assert phonetic.word_to_phonetic("pọ-me") == "pome"      # was 'pọme'
    assert phonetic.word_to_phonetic("po-me") == "pome"      # clean form unchanged
    assert to_phonemes("ạ-ko-ra-ja", "linearb") == "akoraja"  # public API path


# ── Fix 6: Cypriot classify handles the ⟦⟧ / <> / () Leiden markers ────────────
def test_cypriot_leiden_brackets_stripped_and_status_set():
    """Erasure ⟦⟧, editorial-insertion <>, and abbreviation-expansion () brackets must
    not leak into sign labels, and each must set the right editorial status."""
    c = aegean.load("cypriot")

    def by_leiden(raw):
        return next(t for d in c for t in d.tokens if t.annotations.get("leiden") == raw)

    from aegean.core.model import ReadingStatus

    erased = by_leiden("⟦sa-to⟧")           # scribal erasure, still legible
    assert erased.signs == ("sa", "to") and erased.status is ReadingStatus.UNCLEAR
    inserted = by_leiden("ku-pa-<ra>-ko-ra-se")  # editor-inserted omitted sign
    assert inserted.signs == ("ku", "pa", "ra", "ko", "ra", "se")
    assert inserted.status is ReadingStatus.RESTORED
    expanded = by_leiden("e-(mi)")          # abbreviation expansion: a secure reading
    assert expanded.signs == ("e", "mi") and expanded.status is ReadingStatus.CERTAIN

    # corpus-wide: no apparatus bracket ever survives in a sign label
    leaks = [
        s for d in c for t in d.tokens for s in t.signs
        if any(ch in s for ch in "⟦⟧<>()[]")
    ]
    assert leaks == []


# ── Fix 7: Linear B EpiDoc <app> with variant readings but no <lem> keeps the word ─
def test_linearb_epidoc_app_without_lem_keeps_word(tmp_path):
    """An <app> carrying <rdg> variants but no editor-preferred <lem> must still emit a
    token (reading the first variant, flagged UNCLEAR, the rest as alts), not silently
    drop the word."""
    from aegean.core.model import ReadingStatus
    from aegean.scripts.linearb.epidoc import parse_epidoc

    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><ab>'
        "<w>before</w>"
        "<app><rdg><w>read-a</w></rdg><rdg><w>read-b</w></rdg></app>"
        "<w>after</w>"
        "</ab></body></text></TEI>"
    )
    p = tmp_path / "d.xml"
    p.write_text(xml, encoding="utf-8")
    res = parse_epidoc(p)
    doc = res[0] if isinstance(res, list) else res

    assert [t.text for t in doc.tokens] == ["BEFORE", "READ-A", "AFTER"]
    disputed = doc.tokens[1]
    assert disputed.status is ReadingStatus.UNCLEAR
    assert disputed.alt == ("READ-B",)


# ── Fix 8: throughput claim is framed as illustrative, not a pinned benchmark ─
def test_throughput_framed_as_hardware_dependent():
    """The CPU-throughput figure reads as a verified benchmark unless it says otherwise;
    the doc must frame it as hardware-dependent/illustrative and the registry note must
    name the dependency-drift re-measure trigger."""
    from pathlib import Path

    bench = Path("docs/benchmarks.md").read_text(encoding="utf-8")
    assert "hardware-dependent" in bench and "illustrative" in bench

    claims = json.loads(Path("training/results/published-claims.json").read_text(encoding="utf-8"))
    note = claims["throughput_cpu"]["note"]
    assert "Dependency-drift trigger" in note and "onnxruntime floor" in note
