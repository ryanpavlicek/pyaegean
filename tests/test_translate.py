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
        self.prompts: list[str] = []

    def _complete(self, *, prompt, system, max_tokens):
        self.last_prompt = prompt
        self.prompts.append(prompt)
        # Distinct per-call text so the second (repair) response is identifiable.
        return LLMResponse(f"translation #{len(self.prompts)}", self.provider, self.model)


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


# --- post-hoc verify: translate raw, then check + repair against grounding -------------


def test_verify_makes_two_calls_and_returns_repaired_result():
    # verify=True runs a draft call then a check-and-repair call: two provider calls,
    # and the result is the repaired (second) translation as an ExploratoryResult.
    c = CapturingClient()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = translate.translate(_SENT, script="greek", verify=True, client=c)
    assert len(c.prompts) == 2                       # draft + repair
    assert r.text == "translation #2"                 # the repaired text is returned
    assert r.kind == "translate" and r.exploratory is True
    # The repair prompt carries the draft and the full grounding; the draft prompt did not.
    draft_prompt, repair_prompt = c.prompts
    assert "= εἰμί (verb" not in draft_prompt          # draft is grounding-free
    assert "translation #1" in repair_prompt           # the raw draft is checked
    assert "= εἰμί (verb" in repair_prompt             # full grounding reaches the checker
    # The grounding travels with the result for the trace, as a normal translate result.
    assert any("εἰμί" in item.content for item in r.grounding)


def test_verify_false_makes_one_call():
    c = CapturingClient()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = translate.translate(_SENT, script="greek", verify=False, client=c)
    assert len(c.prompts) == 1                          # single grounded call (default path)
    assert r.text == "translation #1"
    assert r.kind == "translate"


def test_verify_lineara_falls_back_to_single_call():
    # verify has no effect on non-Greek scripts: the normal single grounded call is used.
    c = CapturingClient()
    r = translate.translate("KU-RO DA-RO", script="lineara", verify=True, client=c)
    assert len(c.prompts) == 1
    assert [item.content for item in r.grounding] == ["KU-RO → /kuro/", "DA-RO → /daro/"]


# --- upgraded concise-cascade gloss layer (mode="full") --------------------------------

import pytest  # noqa: E402

from aegean.ai import clean_gloss, concise_gloss, content_glosses  # noqa: E402
from aegean.greek import koine as _koine  # noqa: E402
from aegean.greek import lexicon as _lexmod  # noqa: E402
from aegean.greek import lexicons as _lexicons  # noqa: E402
from aegean.greek.lexicons import LexiconInfo  # noqa: E402
from aegean.greek.lexindex import IndexLexicon  # noqa: E402


def _concise_lex(dict_id, data):
    """An in-memory concise dictionary served as a registry Lexicon under ``dict_id``.

    ``data`` maps lemma → raw definition body; the registry gloss comes out as
    ``"headword: <concise body>"``, exactly as the hosted Scaife backends emit it."""
    info = LexiconInfo(
        id=dict_id, name="t", scope="x", license="y", source="z", hosted=True
    )
    index = {k: {"hw": k, "def": v} for k, v in data.items()}
    return IndexLexicon(info, index)


@pytest.fixture
def _reset_lexica():
    """Run with no lexicon active (registry + both legacy globals cleared, so a real
    cached dictionary another test left active cannot leak in); restore afterwards."""
    saved = dict(_lexicons._ACTIVE)
    saved_lsj = _lexmod.active()
    saved_dodson = _koine.active()
    _lexicons._ACTIVE.clear()
    _lexmod.disable_lsj()
    _koine.disable_dodson()
    yield
    _lexicons._ACTIVE.clear()
    _lexicons._ACTIVE.update(saved)
    _lexmod._ACTIVE = saved_lsj
    _koine._ACTIVE = saved_dodson


def test_clean_gloss_strips_headword_greek_and_redirects():
    # Leading "headword:" repeat dropped.
    assert clean_gloss("καιρός: due measure, proportion") == "due measure, proportion"
    # Leading Greek etymology run dropped (a concise definition leads with English).
    assert clean_gloss("βιός a bow") == "a bow"
    # "= X" cross-reference redirect dropped, leaving the meaning.
    assert clean_gloss("= life, existence") == "life, existence"
    # Editorial-abbreviation lead dropped.
    assert clean_gloss("Dim. of a small house") == "a small house"
    # A bare redirect / Greek-only line yields nothing (caller falls through).
    assert clean_gloss("τόξον") == ""
    assert clean_gloss("= ") == ""


def test_concise_cascade_prefers_concise_over_lsj_first_sense(_reset_lexica):
    # LSJ leads καιρός with its archaic, etymological-first sense ("row of thrums in a
    # loom"); the concise dictionary leads with the common meaning. The cascade must take
    # the concise one and never the LSJ first sense.
    _lexmod._ACTIVE = _lexmod.LSJLexicon({
        "καιρός": {
            "hw": "καιρός", "key": "kairos", "lead": "καιρός, ὁ",
            "short": "row of thrums in a loom",
            "senses": [{"m": "I", "l": 0, "t": "row of thrums in a loom"}],
        }
    })
    _lexicons._ACTIVE["middle-liddell"] = _concise_lex(
        "middle-liddell", {"καιρός": "due measure, the right moment"}
    )
    g = concise_gloss("καιρός")
    assert g == "due measure, the right moment"
    assert "thrums" not in g  # the LSJ etymological-first sense was not used


def test_concise_cascade_falls_back_to_lsj_only_last(_reset_lexica):
    # With no concise dictionary loaded, the cascade falls back to LSJ (cleaned).
    _lexmod._ACTIVE = _lexmod.LSJLexicon({
        "λόγος": {
            "hw": "λόγος", "key": "logos", "lead": "λόγος, ὁ",
            "short": "word, speech",
            "senses": [{"m": "I", "l": 0, "t": "word, speech"}],
        }
    })
    assert concise_gloss("λόγος") == "word, speech"
    # And with nothing loaded at all, it degrades to empty rather than raising.
    _lexmod.disable_lsj()
    assert concise_gloss("λόγος") == ""


def test_content_glosses_cascade_uses_concise_source(_reset_lexica):
    _lexicons._ACTIVE["middle-liddell"] = _concise_lex(
        "middle-liddell", {"λόγος": "word, speech, account", "θεός": "God, a god"}
    )
    items = content_glosses("ὁ λόγος καὶ ὁ θεός", source="cascade")
    # Concise-sourced glosses are tagged lexicon:concise (auditable in the trace).
    assert items
    assert all(i.source == "lexicon:concise" for i in items)
    joined = " | ".join(i.content for i in items)
    assert "word, speech, account" in joined
    # The function word ὁ is not glossed.
    assert not any(i.ref == "ὁ" for i in items)


def test_content_glosses_cascade_empty_without_any_dictionary(_reset_lexica):
    # No dictionary loaded: the cascade source yields nothing and never raises.
    assert content_glosses("ὁ λόγος", source="cascade") == []


def test_full_mode_includes_concise_glosses_morphology_has_none(_reset_lexica):
    _lexicons._ACTIVE["middle-liddell"] = _concise_lex(
        "middle-liddell", {"λόγος": "word, speech, account"}
    )
    sent = "ἐν ἀρχῇ ἦν ὁ λόγος"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        morph = translate.grounding_for(sent, "greek", mode="morphology")
        full = translate.grounding_for(sent, "greek", mode="full")
    # morphology mode never carries a dictionary gloss.
    assert not any(i.source in ("lexicon:concise", "lexicon:LSJ") for i in morph)
    # full mode adds the upgraded concise-cascade glosses on top of the morphology lines.
    concise_items = [i for i in full if i.source == "lexicon:concise"]
    assert concise_items
    assert any("word, speech, account" in i.content for i in concise_items)
    # full is a superset: every morphology line is carried over unchanged.
    assert _contents(morph) == _contents(full)[: len(_contents(morph))]


def test_full_mode_degrades_gracefully_with_no_concise_dict(_reset_lexica):
    # No concise dictionary and no corpus signal: full mode degrades to morphology-only
    # (no gloss items), never raising.
    sent = "ἐν ἀρχῇ ἦν ὁ λόγος"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        morph = translate.grounding_for(sent, "greek", mode="morphology")
        full = translate.grounding_for(sent, "greek", mode="full")
    assert not any(i.source == "lexicon:concise" for i in full)
    assert _contents(morph) == _contents(full)


def test_lemma_mode_unchanged_uses_legacy_lsj_source(_reset_lexica):
    # The upgrade rides on "full"; "lemma" keeps the legacy lemma lines and, since no LSJ
    # is loaded here, no glosses. Its lemma lines are the legacy "→ lemma" format.
    lemma = translate.grounding_for("ἦν ὁ λόγος", "greek", mode="lemma")
    assert any("→ lemma" in i.content for i in lemma)
    assert not any(i.source == "lexicon:concise" for i in lemma)
