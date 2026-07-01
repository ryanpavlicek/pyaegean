"""Seed-lookup grave folding + closed-class coverage in the offline lemmatizer.

Regression tests for the seed-tier lookup key (a running-text grave must find its
acute-keyed entry: δὲ → δέ) and for the closed-class contract: high-frequency function
words get their genuine suppletive lemma from the table (τοῦ → ὁ, μου → ἐγώ), never a
fabricated ending-swap non-word (τός, μος), and unknown words come back NFC-unchanged
with ``known=False``.
"""

from __future__ import annotations

import unicodedata

from aegean.greek import lemmatize, lemmatize_verbose
from aegean.greek.lemmatize import rule_lemma_verbose, seed_lemma_verbose


def test_grave_accent_folds_to_acute_in_seed_lookup() -> None:
    # The highest-frequency particles appear graved before a following word; the
    # citation form carries the acute. Both spellings must hit the same entry.
    assert lemmatize_verbose("δὲ") == ("δέ", True)
    assert lemmatize_verbose("δέ") == ("δέ", True)
    assert lemmatize_verbose("γὰρ") == ("γάρ", True)
    assert lemmatize_verbose("μὴ") == ("μή", True)
    assert lemmatize_verbose("καὶ") == ("καί", True)
    assert lemmatize_verbose("καί") == ("καί", True)  # the acute variant hits too
    assert lemmatize_verbose("ἐπὶ") == ("ἐπί", True)
    assert lemmatize_verbose("ἀλλὰ") == ("ἀλλά", True)


def test_grave_folding_composes_with_case_folding() -> None:
    # Sentence-initial capital plus grave, both normalized away by the lookup key.
    assert seed_lemma_verbose("Θεὸς") == ("θεός", True)
    assert seed_lemma_verbose("Καὶ") == ("καί", True)


def test_article_paradigm_lemmatizes_to_ho() -> None:
    forms = [
        "ὁ", "ἡ", "τό", "τοῦ", "τῆς", "τῷ", "τῇ", "τόν", "τήν",
        "οἱ", "αἱ", "τά", "τῶν", "τοῖς", "ταῖς", "τούς", "τάς",
        # running-text grave variants
        "τὸ", "τὴν", "τὸν", "τοὺς", "τὰ", "τὰς",
    ]
    for form in forms:
        assert lemmatize_verbose(form) == ("ὁ", True), form


def test_personal_pronouns_lemmatize_to_ego_and_su() -> None:
    for form in ["μου", "μοι", "με", "ἐμοῦ", "ἡμεῖς", "ἡμῶν", "ἡμῖν", "ἡμᾶς"]:
        assert lemmatize_verbose(form) == ("ἐγώ", True), form
    for form in ["σου", "σοι", "σε", "σοῦ", "ὑμεῖς", "ὑμῶν", "ὑμῖν", "ὑμᾶς"]:
        assert lemmatize_verbose(form) == ("σύ", True), form


def test_demonstratives_and_relative() -> None:
    assert lemmatize("τούτου") == "οὗτος"
    assert lemmatize("ταῦτα") == "οὗτος"
    assert lemmatize("ἐκείνων") == "ἐκεῖνος"
    assert lemmatize("ὅν") == "ὅς"
    assert lemmatize("ὧν") == "ὅς"
    assert lemmatize("οὐδὲν") == "οὐδείς"
    assert lemmatize("ἑαυτόν") == "ἑαυτοῦ"
    assert lemmatize("ἀλλήλους") == "ἀλλήλων"


def test_copula_and_irregular_adjectives() -> None:
    for form in ["ἐστίν", "ἔστιν", "ἦσαν", "εἰσίν", "εἶναι", "ἔσται"]:
        assert lemmatize_verbose(form) == ("εἰμί", True), form
    assert lemmatize("πολλοί") == "πολύς"
    assert lemmatize("πολλὰ") == "πολύς"
    assert lemmatize("μεγάλου") == "μέγας"


def test_no_fabricated_lemma_for_closed_class_forms() -> None:
    # The ending rules must never synthesise a non-word for a suppletive closed-class
    # form: before the guard, τοῦ → τός, μου → μος, τούτου → τούτος, ἦσαν → ἦσα.
    fabrications = {
        "τός", "μος", "σος", "τούτος", "ἑαυτός", "ἀλλήλος",
        "οὐδώ", "ἦσα", "πολλός", "μεγάλος", "ἰδός", "ἐνώπιος", "πά",
    }
    forms = [
        "τοῦ", "τούς", "τοῖς", "μου", "σου", "μοι", "σοι", "τούτου", "τοῦτον",
        "ἑαυτόν", "ἀλλήλους", "οὐδείς", "ἦσαν", "πολλοί", "μεγάλου",
        "ἰδού", "ἐνώπιον", "πᾶν",
    ]
    for form in forms:
        assert lemmatize(form) not in fabrications, form


def test_rule_layer_skips_closed_class_and_vowelless_stems() -> None:
    # The standalone rule layer (no seed table) declines these outright instead of
    # ending-swapping them; the form comes back unchanged with recovered=False.
    for form in ["τοῦ", "τούς", "μου", "σοι", "τούτου", "ἑαυτόν", "πᾶν", "ἰδού"]:
        assert rule_lemma_verbose(form) == (unicodedata.normalize("NFC", form), False), form


def test_rule_layer_still_generalizes_regular_paradigms() -> None:
    # The conservative rule layer keeps doing its job on regular open-class forms.
    assert rule_lemma_verbose("νόμου") == ("νόμος", True)
    assert rule_lemma_verbose("καρπούς") == ("καρπός", True)
    assert rule_lemma_verbose("λύεις") == ("λύω", True)
    assert rule_lemma_verbose("παύομεν") == ("παύω", True)
    assert lemmatize("νόμου") == "νόμος"


def test_unknown_words_return_nfc_unchanged_with_known_false() -> None:
    # The documented contract: no table hit, no rule, no fabrication.
    for word in ["γλαύξ", "πατήρ", "ἀλώπηξ"]:
        lemma, known = lemmatize_verbose(word)
        assert lemma == unicodedata.normalize("NFC", word)
        assert known is False


def test_closed_class_lemmas_are_fixpoints() -> None:
    # A citation form must lemmatize to itself (and lemmatize must be idempotent).
    for lemma in ["ὁ", "ἐγώ", "σύ", "αὐτός", "οὗτος", "ἐκεῖνος", "ὅς", "εἰμί",
                  "οὐδείς", "πολύς", "μέγας", "δέ", "γάρ", "μή", "οὐ", "ἐπί"]:
        assert lemmatize(lemma) == lemma


def test_negation_allomorphs() -> None:
    assert lemmatize("οὐκ") == "οὐ"
    assert lemmatize("οὐχ") == "οὐ"
    assert lemmatize("ἐξ") == "ἐκ"


def test_neuter_guard_covers_grave_and_capitalized_variants() -> None:
    # The guard lists now match under the folded key: the graved neuter ἱερὸν used to
    # slip past the ἱερόν guard and get stripped to ἱερός.
    assert lemmatize("ἱερὸν") == "ἱερὸν"
    assert rule_lemma_verbose("ἱερὸν") == ("ἱερὸν", False)
    assert lemmatize_verbose("ἂν")[0] == "ἄν"  # graved ἄν folds onto its entry
