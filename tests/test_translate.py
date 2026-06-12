"""Hybrid lexicon+LLM translation: local grounding is deterministic, the
translation call is delegated to the AI layer (faked here)."""

from __future__ import annotations

from aegean import translate
from aegean.ai.client import LLMClient, LLMResponse


class CapturingClient(LLMClient):
    provider = "capture"

    def __init__(self, model="cap-1", **kw):
        super().__init__(model, **kw)
        self.last_prompt = ""

    def _complete(self, *, prompt, system, max_tokens):
        self.last_prompt = prompt
        return LLMResponse("translation", self.provider, self.model)


def test_greek_grounding_uses_lemma_table():
    g = translate.grounding_for("ἦν ὁ λόγος", "greek")
    contents = [item.content for item in g]
    assert "ἦν → lemma εἰμί" in contents
    assert "λόγος → lemma λόγος" in contents
    assert all(item.source == "lemmatizer" for item in g)  # tagged for the trace


def test_lineara_grounding_uses_transliteration():
    g = translate.grounding_for("KU-RO DA-RO 5", "lineara")
    assert [item.content for item in g] == ["KU-RO → /kuro/", "DA-RO → /daro/"]  # numeral dropped
    assert all(item.source == "transliteration" for item in g)


def test_translate_greek_is_grounded_and_exploratory():
    c = CapturingClient()
    r = translate.translate("ἦν ὁ λόγος", script="greek", client=c)
    assert r.kind == "translate" and r.exploratory is True
    assert "εἰμί" in c.last_prompt          # grounding reached the prompt
    assert "Ancient Greek" in c.last_prompt  # source language named
    assert "εἰμί" in " ".join(item.content for item in r.grounding)
    assert "lemmatizer" in r.trace()         # the source is auditable


def test_translate_lineara_routes_source_name():
    c = CapturingClient()
    r = translate.translate("KU-RO DA-RO", script="lineara", client=c)
    assert "Linear A" in c.last_prompt
    assert [item.content for item in r.grounding] == ["KU-RO → /kuro/", "DA-RO → /daro/"]
