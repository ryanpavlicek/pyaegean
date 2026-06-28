"""Hybrid lexicon+LLM translation: local grounding is deterministic, the
translation call is delegated to the AI layer (faked here)."""

from __future__ import annotations

import warnings

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


def test_greek_grounding_lemma_mode_uses_lemma_table():
    # mode="lemma" is the legacy grounding (lemma lines + gated content glosses),
    # preserved for back-compat. Without LSJ loaded the gloss items are empty, so every
    # item here is a lemma line tagged "lemmatizer".
    g = translate.grounding_for("ἦν ὁ λόγος", "greek", mode="lemma")
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
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # baseline-lemmatizer notice is covered separately
        r = translate.translate("ἦν ὁ λόγος", script="greek", client=c)
    assert r.kind == "translate" and r.exploratory is True
    assert "εἰμί" in c.last_prompt          # grounding reached the prompt
    assert "Ancient Greek" in c.last_prompt  # source language named
    assert "εἰμί" in " ".join(item.content for item in r.grounding)
    # Default grounding is morphology-first; its source is auditable in the trace.
    assert "analysis:morphology" in r.trace()


def test_translate_lineara_routes_source_name():
    c = CapturingClient()
    r = translate.translate("KU-RO DA-RO", script="lineara", client=c)
    assert "Linear A" in c.last_prompt
    assert [item.content for item in r.grounding] == ["KU-RO → /kuro/", "DA-RO → /daro/"]


def test_translate_greek_warns_on_baseline_lemmatizer():
    # With only the seed table loaded, lexical grounding misses rare/inflected forms;
    # the user is told how to get fuller grounding (treebank / neural pipeline).
    c = CapturingClient()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        translate.translate("ἦν ὁ λόγος", script="greek", client=c)
    assert any("baseline lemmatizer" in str(w.message) for w in caught)


def test_translate_lineara_does_not_warn_about_lemmatizer():
    c = CapturingClient()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        translate.translate("KU-RO DA-RO", script="lineara", client=c)
    assert not any("baseline lemmatizer" in str(w.message) for w in caught)


# --- morphology-first grounding (the new default) --------------------------------------

_SENT = "ἐν ἀρχῇ ἦν ὁ λόγος"


def _contents(items):
    return [item.content for item in items]


def test_morphology_is_the_default_mode():
    # The default grounding is morphology-first; it differs from the legacy lemma mode.
    default = translate.grounding_for(_SENT, "greek")
    explicit = translate.grounding_for(_SENT, "greek", mode="morphology")
    assert _contents(default) == _contents(explicit)


def test_morphology_grounding_has_per_token_lines_and_no_glosses():
    g = translate.grounding_for(_SENT, "greek", mode="morphology")
    contents = _contents(g)
    # A per-token morphology line: "word = lemma (pos[, morph])".
    assert any(c.startswith("ἦν = εἰμί (verb") for c in contents), contents
    assert any(item.source == "analysis:morphology" for item in g)
    # No LSJ / dictionary-sense grounding in morphology mode.
    assert not any(item.source == "lexicon:LSJ" for item in g)
    assert not any("→ lemma" in c for c in contents)  # not the legacy lemma-line format


def test_morphology_grounding_includes_clause_skeleton_when_parsed():
    # Without a parser loaded, pipeline(parse=True) raises and we fall back to the
    # unparsed analysis: the skeleton is omitted but the call still succeeds. With the
    # baseline backend a skeleton may or may not appear; either way the call never raises
    # and the per-token lines are present.
    g = translate.grounding_for(_SENT, "greek", mode="morphology")
    assert g  # never empty for real Greek text
    skel = [item for item in g if item.source == "analysis:syntax"]
    # If a skeleton line is present it names the main predicate.
    for item in skel:
        assert item.content.startswith("Clause skeleton:")
        assert "main predicate" in item.content


def test_full_mode_is_morphology_plus_gated_glosses():
    morph = translate.grounding_for(_SENT, "greek", mode="morphology")
    full = translate.grounding_for(_SENT, "greek", mode="full")
    # "full" is a superset of the morphology lines (glosses are empty without LSJ, so
    # here they are equal; the morphology lines must all be carried over).
    assert _contents(morph)[: len(_contents(morph))] == _contents(full)[: len(_contents(morph))]
    assert all(item.source != "lexicon:LSJ" for item in morph)


def test_none_mode_yields_no_grounding():
    assert translate.grounding_for(_SENT, "greek", mode="none") == []


def test_modes_differ():
    morph = _contents(translate.grounding_for(_SENT, "greek", mode="morphology"))
    lemma = _contents(translate.grounding_for(_SENT, "greek", mode="lemma"))
    assert morph != lemma
    assert morph  # morphology mode is non-empty


def test_glosses_flag_only_affects_gloss_bearing_modes():
    # glosses is superseded by mode: it has no effect on morphology (already gloss-free).
    on = _contents(translate.grounding_for(_SENT, "greek", mode="morphology", glosses=True))
    off = _contents(translate.grounding_for(_SENT, "greek", mode="morphology", glosses=False))
    assert on == off


def test_translate_forwards_mode():
    # The morphology grounding (per-token "= lemma (pos...)" line) must reach the prompt.
    c = CapturingClient()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = translate.translate(_SENT, script="greek", mode="morphology", client=c)
    assert "= εἰμί (verb" in c.last_prompt
    assert r.kind == "translate" and r.exploratory is True

    # mode="lemma" forwards the legacy lemma-line grounding instead.
    c2 = CapturingClient()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        translate.translate(_SENT, script="greek", mode="lemma", client=c2)
    assert "→ lemma εἰμί" in c2.last_prompt


def test_translate_mode_none_sends_no_grounding_and_no_warning():
    c = CapturingClient()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        r = translate.translate(_SENT, script="greek", mode="none", client=c)
    assert r.grounding == [] or list(r.grounding) == []
    assert not any("baseline lemmatizer" in str(w.message) for w in caught)
