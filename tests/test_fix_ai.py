"""Regression tests for the AI-layer fixes: generator grounding recorded in
provenance (not silently dropped after the prompt pass), the response-cache key
covering max_tokens, unknown grounding modes rejected loudly, and the verify-mode
safety claim stated conditionally. No SDKs or keys — a fake client stands in."""

from __future__ import annotations

import inspect
import pathlib
import warnings

import pytest

from aegean import ai, translate
from aegean.ai.cache import ResponseCache, _key
from aegean.ai.client import LLMClient, LLMResponse

_WIKI_AI_LAYER = pathlib.Path(__file__).resolve().parent.parent / "wiki" / "AI-Layer.md"


class CapturingClient(LLMClient):
    """Records prompts/systems and counts provider calls."""

    provider = "capture"

    def __init__(self, model="cap-1", **kw):
        super().__init__(model, **kw)
        self.calls: list[tuple[str | None, str]] = []

    def _complete(self, *, prompt, system, max_tokens):
        self.calls.append((system, prompt))
        return LLMResponse(f"ANSWER({len(self.calls)})", self.provider, self.model)


# ── generator grounding: provenance must match what the model saw ────────────
_EVIDENCE = "μῆνιν → lemma μῆνις"


@pytest.mark.parametrize(
    "call",
    [
        lambda c, g: ai.translate("μῆνιν", grounding=g, client=c),
        lambda c, g: ai.gloss("μῆνιν", grounding=g, client=c),
        lambda c, g: ai.decipher_hypotheses("A-TA", grounding=g, client=c),
        lambda c, g: ai.nlp_assist("μῆνιν", grounding=g, client=c),
        lambda c, g: ai.summarize("μῆνιν ἄειδε", grounding=g, client=c),
        lambda c, g: ai.ask("What form is μῆνιν?", grounding=g, client=c),
        lambda c, g: ai.verify_translation("μῆνιν", "wrath", grounding=g, client=c),
        lambda c, g: ai.extract("μῆνιν", grounding=g, client=c),
    ],
    ids=[
        "translate", "gloss", "decipher", "nlp_assist",
        "summarize", "ask", "verify_translation", "extract",
    ],
)
def test_generator_grounding_reaches_prompt_and_provenance(call):
    # Grounding passed as a GENERATOR is read twice (prompt evidence block, then
    # result provenance). It used to be exhausted by the first read, so the model
    # WAS grounded but the ExploratoryResult recorded zero grounding — a silently
    # false audit trail. Both reads must now see the evidence.
    c = CapturingClient()
    r = call(c, (e for e in [_EVIDENCE]))
    _, prompt = c.calls[-1]
    assert _EVIDENCE in prompt  # the model actually saw the evidence
    assert [g.content for g in r.grounding] == [_EVIDENCE]  # ...and the trace says so
    assert r.grounding[0].source == "custom"


def test_generator_grounding_trace_not_falsely_ungrounded():
    # The user-facing symptom: trace() claimed "grounding: none" for a grounded call.
    c = CapturingClient()
    r = ai.translate("μῆνιν", grounding=(e for e in [_EVIDENCE]), client=c)
    assert "grounding: none" not in r.trace()
    assert _EVIDENCE in r.trace()


# ── cache key: max_tokens is response-shaping and must be in the key ─────────
def test_cache_key_separates_max_tokens():
    # A truncated short-limit response must never be served for a longer request.
    cache = ResponseCache()
    cache.set("p", "m", "s", "prompt", "SHORT…", max_tokens=64)
    assert cache.get("p", "m", "s", "prompt", max_tokens=1024) is None  # no collision
    assert cache.get("p", "m", "s", "prompt", max_tokens=64) == "SHORT…"  # exact hit
    cache.set("p", "m", "s", "prompt", "LONG ANSWER", max_tokens=1024)
    assert len(cache) == 2  # two distinct entries, not an overwrite
    assert cache.get("p", "m", "s", "prompt", max_tokens=64) == "SHORT…"


def test_cache_key_digest_covers_max_tokens_and_nothing_lost():
    # Same inputs → same key; any single differing field (max_tokens included) → new key.
    base = _key("p", "m", "s", "prompt", 1024)
    assert base == _key("p", "m", "s", "prompt", 1024)
    assert base != _key("p", "m", "s", "prompt", 64)
    assert base != _key("p", "m", "s", "other prompt", 1024)
    assert base != _key("p", "m", None, "prompt", 1024)
    assert base != _key("p", "other-model", "s", "prompt", 1024)


def test_cache_max_tokens_default_mirrors_client_complete():
    # get/set default must track LLMClient.complete's max_tokens default, so a call
    # site that doesn't thread the limit through keys consistently with default calls.
    complete_default = inspect.signature(LLMClient.complete).parameters["max_tokens"].default
    for method in (ResponseCache.get, ResponseCache.set):
        assert inspect.signature(method).parameters["max_tokens"].default == complete_default


def test_cache_persistence_round_trips_max_tokens_key(tmp_path):
    path = tmp_path / "ai.json"
    cache = ResponseCache(path)
    cache.set("p", "m", "s", "prompt", "AT-256", max_tokens=256)
    reloaded = ResponseCache(path)
    assert reloaded.get("p", "m", "s", "prompt", max_tokens=256) == "AT-256"
    assert reloaded.get("p", "m", "s", "prompt", max_tokens=512) is None


# ── unknown grounding mode: loud ValueError, never a silent lemma fallback ───
def test_unknown_grounding_mode_raises_and_names_valid_modes():
    with pytest.raises(ValueError, match="morfology") as exc:
        translate.grounding_for("ἦν ὁ λόγος", "greek", mode="morfology")
    msg = str(exc.value)
    for valid in ("morphology", "lemma", "full", "none"):
        assert valid in msg  # the error tells a CLI user exactly what is accepted


def test_unknown_mode_in_translate_raises_before_any_model_call():
    # A typo'd --mode must fail fast, not silently ground in legacy lemma mode
    # (and must not spend an API call on the way).
    c = CapturingClient()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(ValueError, match="unknown grounding mode"):
            translate.translate("ἦν ὁ λόγος", script="greek", mode="morfology", client=c)
    assert c.calls == []


def test_valid_modes_still_accepted():
    # The validation must not reject any documented mode.
    assert translate.grounding_for("ἦν ὁ λόγος", "greek", mode="none") == []
    morph = translate.grounding_for("ἦν ὁ λόγος", "greek", mode="morphology")
    assert morph and all(hasattr(g, "source") for g in morph)
    lemma = translate.grounding_for("ἦν ὁ λόγος", "greek", mode="lemma")
    assert all(g.source in {"lemmatizer", "lexicon:LSJ"} for g in lemma)


# ── verify-mode safety claim: conditional, not structural ────────────────────
def test_verify_docstrings_state_conditional_safety():
    # The old wording claimed the check "can catch errors but never cause them" —
    # false when the gold analysis itself is wrong. The docstrings must state the
    # true, conditional guarantee: no bias on the draft, but a wrong analysis can
    # still mislead the repair.
    doc = translate.translate.__doc__ or ""
    assert "never cause them" not in doc
    assert "cannot bias the initial draft" in doc
    assert "mislead the repair" in doc

    vdoc = ai.verify_translation.__doc__ or ""
    assert "not introduce them" not in vdoc
    assert "mislead the repair" in vdoc


@pytest.mark.skipif(not _WIKI_AI_LAYER.exists(), reason="wiki not present in this checkout")
def test_wiki_verify_row_states_conditional_safety():
    text = _WIKI_AI_LAYER.read_text(encoding="utf-8")
    assert "it catches errors without biasing the translation" not in text
    assert "can still mislead the repair" in text
