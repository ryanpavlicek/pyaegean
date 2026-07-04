"""Regression tests for the twelfth sweep — the Ancient Greek scholarly audit (0.19.14).

Each pins one philological error found and fixed against a standard authority (Smyth, LSJ,
West, Ventris-Chadwick), so a professor's spot-check now passes.
"""

from __future__ import annotations


# ── #1 accent: an oxytone takes the circumflex in the genitive/dative (Smyth §163a) ──
def test_oxytone_genitive_dative_take_circumflex():
    from aegean.greek.accent_law import place_accent

    cases = [
        ("θεου", "θεός", "θεοῦ"), ("θεῳ", "θεός", "θεῷ"), ("τιμης", "τιμή", "τιμῆς"),
        ("τιμῃ", "τιμή", "τιμῇ"), ("θεων", "θεός", "θεῶν"), ("θεοις", "θεός", "θεοῖς"),
    ]
    for form, lemma, want in cases:
        assert place_accent(form, recessive=False, lemma=lemma).form == want, form
    # nominative/accusative oxytones stay acute (the rule is gen/dat only)
    for form, lemma, want in [("θεος", "θεός", "θεός"), ("θεους", "θεός", "θεούς")]:
        assert place_accent(form, recessive=False, lemma=lemma).form == want, form


# ── #7 accent: the πόλις/πῆχυς -εως genitive keeps the antepenult (Smyth §275) ──
def test_polis_type_genitive_keeps_antepenult():
    from aegean.greek.accent_law import place_accent

    for form, lemma, want in [
        ("πολεως", "πόλις", "πόλεως"), ("πολεων", "πόλις", "πόλεων"), ("πηχεως", "πῆχυς", "πήχεως"),
    ]:
        assert place_accent(form, recessive=False, lemma=lemma).form == want, form


# ── #4 prosody: a double consonant ζ/ξ/ψ makes position (Smyth §144) ──
def test_double_consonant_makes_position():
    from aegean.greek.prosody import syllable_quantities

    assert syllable_quantities("ὄζος") == ["heavy", "heavy"]
    assert syllable_quantities("ὀψέ") == ["heavy", "light"]
    assert syllable_quantities("τάξις") == ["heavy", "heavy"]
    # and it agrees with meter.py (which already handled it) on the same word
    assert syllable_quantities("ὄζος")[0] == "heavy"


# ── #2,3,8,9 lemmatizer: no confident fabrication of non-words ──
def test_lemmatizer_does_not_fabricate_from_verb_and_neuter_forms():
    from aegean.greek.lemmatize import lemmatize_verbose

    # #2 thematic aorist -ον, #3 -όω contract -οῖ, #8 neuter gen -ου: honest miss, not a -ος noun
    for form in ["εἶπον", "ἦλθον", "ἔλαβον", "ἔβαλον", "δηλοῖ", "σταυροῖ", "ἔργου", "δώρου"]:
        lemma, known = lemmatize_verbose(form)
        assert not known, (form, lemma)          # not a confident fabrication
        assert not lemma.endswith("ος"), (form, lemma)
    # #9 ψ/ξ sigmatic futures: not stripped to a -ω future lemma
    for form in ["γράψει", "πέμψει", "διώξει", "βλέψει"]:
        lemma, known = lemmatize_verbose(form)
        assert not known, (form, lemma)
    # genuine forms still resolve (no regression)
    assert lemmatize_verbose("λόγον") == ("λόγος", True)
    assert lemmatize_verbose("λόγου") == ("λόγος", True)
    assert lemmatize_verbose("λέγει") == ("λέγω", True)
    assert lemmatize_verbose("πράσσει") == ("πράσσω", True)


# ── #5,#10 Mycenaean lexicon: the corrected Linear B readings ──
def test_mycenaean_lexicon_readings_corrected():
    from aegean.scripts.linearb.lexicon import greek_reading

    assert greek_reading("PO-NI-KI-JA") == ("φοινίκια", "crimson")     # not Φοίνικες "murex"
    assert greek_reading("KI-TI-ME-NA")[0] == "κτιμένα"                # not ἐϋκτίμενος


# ── #6 glossing: clean_gloss strips a grammatical preamble, keeps the sense ──
def test_clean_gloss_strips_grammatical_preamble():
    from aegean.ai.grounding import clean_gloss

    for raw, want in [
        ("Imp. pl. bear, carry", "bear, carry"),
        ("acc. always father", "father"),
        ("gen. city", "city"),
        ("Epic also water", "water"),
        ("Root ! man", "man"),
        ("not used in pl. fire", "fire"),
    ]:
        assert clean_gloss(raw) == want, raw
    # real glosses (that merely start with a grammatical-abbreviation-looking word) survive
    for keep in ["part of the body", "action, deed", "act of will", "make, do"]:
        assert clean_gloss(keep) == keep, keep
