"""Idiom / multiword-expression grounding (zero-dep, offline).

The idiom layer grounds the real, non-compositional meaning of fixed Greek phrases
(``ἐφ' ἡμῖν`` = "in our power", not "upon us") — the one error class per-token
morphology grounding cannot reach. Detection is surface- + lemma-based, not a parser;
these tests pin both paths, the no-false-positive behaviour, and the wiring into the
morphology grounding default.
"""

from __future__ import annotations

import warnings

from aegean import translate
from aegean.ai import idiom_glosses
from aegean.data import load_bundled_json


def _contents(items):
    return [i.content for i in items]


def test_surface_match_finds_eph_hemin_with_elision():
    # The apostrophe/elision in ἐφ' ἡμῖν must not block the accent-insensitive surface match.
    g = idiom_glosses("τὰ μὲν ἐστιν ἐφ' ἡμῖν")
    items = [i for i in g if i.ref == "ἐφ' ἡμῖν"]
    assert items, _contents(g)
    item = items[0]
    assert item.source == "lexicon:idiom"
    assert item.content == "ἐφ' ἡμῖν: in our power, up to us"
    assert "in our power" in item.content


def test_inflected_idiom_caught_by_lemma_path():
    # οἷός τε ἐστί is the inflected form of the lexicon's citation οἷός τε εἰμί: ἐστί
    # lemmatizes to εἰμί, so the idiom's content lemmas (οιος τε ειμι) appear as an
    # adjacent run even though the surface form never does. This is the contiguous
    # lemma path.
    g = idiom_glosses("οἷός τε ἐστί λέγειν")
    contents = _contents(g)
    assert any(c.startswith("οἷός τε εἰμί:") and "be able to" in c for c in contents), contents


def test_lemma_path_longest_match_suppresses_nested_sub_idiom():
    # Longest-match suppression must apply on the *lemma* path, not only the surface path.
    # In "οἷός τε ἐστί φεύγειν", ἐστί lemmatizes to εἰμί, so the long idiom οἷός τε εἰμί
    # (lemmas οιος τε ειμι) matches contiguously; its nested sub-idiom οἷόν τε (lemmas
    # οιος τε) occupies a lemma span contained in the longer one and must be dropped.
    g = idiom_glosses("οἷός τε ἐστί φεύγειν")
    refs = [i.ref for i in g]
    assert "οἷός τε εἰμί" in refs, refs
    assert "οἷόν τε" not in refs, refs  # the contained sub-idiom is suppressed


def test_two_distinct_lemma_path_idioms_both_emit():
    # Suppression is containment-based, not blanket: two genuinely distinct idioms whose
    # lemma spans are disjoint must both survive. Here οἷός τε εἰμί (lemma path) and
    # πρὸς τούτοις (inflected τούτοις, lemma path) sit in different parts of the sentence.
    g = idiom_glosses("οἷός τε ἐστί λέγειν, πρὸς τούτοις ἔρχεται")
    refs = {i.ref for i in g}
    assert "οἷός τε εἰμί" in refs, refs
    assert "πρὸς τούτοις" in refs, refs


def test_no_false_positive_on_unrelated_text():
    # Opening of the Iliad: no idiom from the lexicon is present.
    g = idiom_glosses("μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος")
    assert g == []


def test_empty_and_whitespace_text_returns_empty():
    assert idiom_glosses("") == []
    assert idiom_glosses("   ") == []


def test_gapped_correlative_matches_across_a_gap():
    # The "..." in the lexicon surface (οὐ μόνον ... ἀλλὰ καί) matches when the two
    # segments appear in order with arbitrary tokens between them.
    g = idiom_glosses("οὐ μόνον τοῦτο ἀλλὰ καὶ ἐκεῖνο")
    contents = _contents(g)
    assert any("not only" in c and "but also" in c for c in contents), contents


def test_accent_insensitive_surface_match():
    # The same idiom is found whether or not the input carries accents.
    accented = idiom_glosses("διὰ τοῦτο ἔρχεται")
    bare = idiom_glosses("δια τουτο ερχεται")
    assert any(i.ref == "διὰ τοῦτο" for i in accented)
    assert any(i.ref == "διὰ τοῦτο" for i in bare)


def test_glosses_are_deduplicated_by_meaning():
    # No two returned items share an identical gloss.
    g = idiom_glosses("διὰ τοῦτο καὶ ἐφ' ἡμῖν ἐστιν, οὐδὲν ἧττον.")
    glosses = [i.content.split(": ", 1)[1] for i in g]
    assert len(glosses) == len(set(glosses))


def test_never_raises_on_odd_input():
    # Numerals, Latin, punctuation-only: degrade to a result (possibly empty), never raise.
    for text in ["123 456", "hello world", "!!! ??? ...", "ΑΒΓ"]:
        assert isinstance(idiom_glosses(text), list)


# --- false-positive regressions (scattered function words must not match) ---------------


def test_no_false_positive_on_in_the_beginning_was_the_word():
    # Regression: the all-function-word idioms whose lemmas are "ἐν ὁ" must not fire on a
    # sentence that merely contains ἐν ... ὁ scattered apart. In "ἐν ἀρχῇ ἦν ὁ λόγος"
    # (lemmas ἐν ἀρχή εἰμί ὁ λόγος) ἐν is followed by ἀρχή, not ὁ, so a contiguous lemma
    # match cannot fire — and those bare-surface idioms were dropped from the lexicon too.
    assert idiom_glosses("ἐν ἀρχῇ ἦν ὁ λόγος.") == []


def test_no_especially_gloss_on_bare_en_tois():
    # "ἐν τοῖς ἀνθρώποις" is the plain prepositional phrase "among men", not the
    # superlative idiom; it must never inject the "especially" gloss.
    g = idiom_glosses("ἐν τοῖς ἀνθρώποις ἦν")
    assert not any("especially" in i.content for i in g)


def test_dropped_generic_surfaces_are_not_in_the_lexicon():
    # The bare-surface idioms whose literal reading dominates were pruned: their surface
    # forms occur constantly as ordinary prepositional/article phrases, so an exact match
    # is unreliable without syntactic context.
    surfaces = {e["surface"] for e in load_bundled_json("greek", "idioms.json")}
    for dropped in ("ἐν τοῖς", "ἐν τῷ", "ἐν ᾧ", "τὸ πρῶτον", "τὸ νῦν",
                    "μᾶλλον ἤ", "ἐν μέρει", "πρὸ τοῦ"):
        assert dropped not in surfaces, dropped


def test_distinctive_idioms_are_kept():
    # The pruning kept the genuinely non-compositional, distinctive idioms.
    surfaces = {e["surface"] for e in load_bundled_json("greek", "idioms.json")}
    for kept in ("ἐφ' ἡμῖν", "οὐδὲν ἧττον", "οὐκ ἔστιν ὅπως", "οἷός τε εἰμί",
                 "δῆλον ὅτι", "διὰ τοῦτο"):
        assert kept in surfaces, kept


# --- the bundled lexicon ---------------------------------------------------------------


def test_bundled_lexicon_is_well_formed_and_multiword():
    raw = load_bundled_json("greek", "idioms.json")
    assert isinstance(raw, list) and raw
    for entry in raw:
        assert set(entry) >= {"surface", "lemmas", "gloss", "note"}
        # Every kept entry is a genuine multiword expression (>= 2 content lemmas),
        # not a single word or bare particle.
        assert len(entry["lemmas"].split()) >= 2, entry["surface"]
        assert entry["gloss"].strip()


# --- wiring into the grounding builder -------------------------------------------------

_IDIOM_SENT = "τὰ μὲν ἐστιν ἐφ' ἡμῖν"
_PLAIN_SENT = "μῆνιν ἄειδε θεά"


def test_morphology_mode_includes_idiom_item_on_idiom_text():
    g = translate.grounding_for(_IDIOM_SENT, "greek", mode="morphology")
    idiom_items = [i for i in g if i.source == "lexicon:idiom"]
    assert idiom_items, _contents(g)
    assert any("in our power" in i.content for i in idiom_items)


def test_morphology_mode_has_no_idiom_item_on_plain_text():
    g = translate.grounding_for(_PLAIN_SENT, "greek", mode="morphology")
    assert not any(i.source == "lexicon:idiom" for i in g)


def test_full_mode_also_carries_idiom_item():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        g = translate.grounding_for(_IDIOM_SENT, "greek", mode="full")
    assert any(i.source == "lexicon:idiom" for i in g)


def test_lemma_and_none_modes_carry_no_idiom_item():
    # Idioms ride only with morphology/full; the legacy lemma mode and none are unchanged.
    for mode in ("lemma", "none"):
        g = translate.grounding_for(_IDIOM_SENT, "greek", mode=mode)
        assert not any(i.source == "lexicon:idiom" for i in g)


def test_idiom_item_reaches_the_translation_prompt():
    # The idiom gloss must actually be sent to the model in the default mode.
    from aegean.ai.client import LLMClient, LLMResponse

    class CapturingClient(LLMClient):
        provider = "capture"

        def __init__(self, model="cap-1", **kw):
            super().__init__(model, **kw)
            self.last_prompt = ""

        def _complete(self, *, prompt, system, max_tokens):
            self.last_prompt = prompt
            return LLMResponse("t", self.provider, self.model)

    c = CapturingClient()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        translate.translate(_IDIOM_SENT, script="greek", mode="morphology", client=c)
    assert "in our power" in c.last_prompt
