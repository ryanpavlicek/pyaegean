"""Regression tests: the offline rule lemmatizer no longer fabricates a non-word for the
contracted second-declension nouns in -οῦς and for the accent-receding κύριος paradigm.

Two related fabrication classes, both surfaced by live testing and both instances of the
established "a genitive strip-rewritten to a *-ος that does not exist" defect:

  * Ἰησοῦ → *Ἰησός  (a contracted -οῦς noun: gold Ἰησοῦς).  The genitive -οῦ carries the
    same circumflex as a genuine oxytone -ός genitive (Χριστός → Χριστοῦ, which strips
    CORRECTLY), so the accent alone cannot flag it: the citation form is purely lexical.
    A curated contract-noun stem now blocks the -ου → -ος strip (an honest miss at the rule
    layer, never *Ἰησός) and the frequent forms are seeded to the -οῦς nominative.
  * Κυρίου → *Κυρίος  (κύριος, a proparoxytone whose accent recedes: gold κύριος, lowercase).
    Not a capitalization artefact — lowercase κυρίου failed identically. The rule preserves
    the surface stem accent and cannot restore the antepenult, so the whole κύριος paradigm
    (the most frequent NT noun) is seeded to the correct citation form.

Measured on the full Nestle1904 NT (offline protocol: no backends active): offline lemma
accuracy 66.16 → 66.98, +1,135 correct tokens, 736 confident-wrong fabrications removed,
0 previously-correct lemmas lost.
"""

from __future__ import annotations

import unicodedata

import pytest


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# ── the contracted -οῦς nouns resolve to the -οῦς nominative, via the seed (right class) ──
@pytest.mark.parametrize(
    "form,want",
    [("Ἰησοῦ", "Ἰησοῦς"), ("Ἰησοῦν", "Ἰησοῦς"), ("νοῦν", "νοῦς"), ("χοῦν", "χοῦς")],
)
def test_contract_2nd_noun_resolves_to_ous_nominative(form: str, want: str) -> None:
    from aegean.greek.lemmatize import LemmaSource, lemmatize_sourced

    lemma, source = lemmatize_sourced(form)
    assert _nfc(lemma) == want, (form, lemma)
    # the evidence class is SEED (a curated lexical entry), a grounded analysis — not review-bait
    assert source is LemmaSource.SEED, (form, source)
    # and never the fabricated *-ός non-word
    assert not lemma.endswith("ός"), (form, lemma)


def test_iesous_genitive_is_the_headline_fix() -> None:
    """Ἰησοῦ was the single largest confident fabrication (Ἰησοῦ → *Ἰησός, 326 NT tokens)."""
    from aegean.greek.lemmatize import LemmaSource, lemmatize_sourced, needs_review

    lemma, source = lemmatize_sourced("Ἰησοῦ")
    assert _nfc(lemma) == "Ἰησοῦς" and source is LemmaSource.SEED
    assert not needs_review(source)


# ── the rule layer alone (bypasses the seed): a circumflex -οῦ contract noun is an honest
#    miss, NEVER *-ός — the guard, tested where the seed cannot mask it ─────────────────────
@pytest.mark.parametrize("form", ["Ἰησοῦ", "νοῦ", "χοῦ", "πλοῦ"])
def test_contract_genitive_rule_layer_is_honest_miss_never_os(form: str) -> None:
    from aegean.greek.lemmatize import rule_lemma_verbose

    lemma, recovered = rule_lemma_verbose(form)
    # rule_lemma_verbose consults ONLY the deterministic rules + guards, so this exercises the
    # contract-noun guard (and the vowel-less-stem guard) directly, not the seed table.
    assert not recovered, (form, lemma)              # not a confident fabrication
    assert _nfc(lemma) == _nfc(form)                 # the normalized form, unchanged
    assert not lemma.endswith("ός"), (form, lemma)   # never *Ἰησός / *νός


def test_contract_stem_guard_is_load_bearing_for_vowelful_stem() -> None:
    """Ἰησοῦς has a vowelful stem (ιησ), so the -ου strip WOULD fire without the guard — this
    is the case the vowel-less-stem guard cannot catch. Pin that the curated guard covers it."""
    from aegean.greek.lemmatize import _CONTRACT_2ND_STEMS, _bare

    assert _bare("Ἰησοῦ")[:-2] in _CONTRACT_2ND_STEMS


# ── the κύριος paradigm (accent recession): every case resolves to the lowercase κύριος ──
@pytest.mark.parametrize(
    "form",
    ["Κυρίου", "κυρίου", "Κυρίῳ", "κυρίῳ", "Κύριον", "κύριον", "Κύριος", "κύριος",
     "Κύριε", "κύριε", "Κύριοι", "κύριοι", "κυρίων", "κυρίοις", "κυρίους"],
)
def test_kurios_paradigm_resolves_to_lowercase_kurios(form: str) -> None:
    from aegean.greek.lemmatize import LemmaSource, lemmatize_sourced

    lemma, source = lemmatize_sourced(form)
    # gold (Nestle1904) is the lowercase κύριος for every case, capitalized or not
    assert lemma == "κύριος", (form, lemma)
    assert source is LemmaSource.SEED, (form, source)
    # the mis-accented *κυρίος (accent on the penult) the rule used to fabricate is gone
    assert lemma != _nfc("κυρίος")


def test_kuriou_defect_is_not_a_capitalization_artifact() -> None:
    """The reported defect held for BOTH cases: the lowercase κυρίου failed the same way the
    capitalized Κυρίου did (both fabricated the mis-accented *κυρίος). Both are now correct."""
    from aegean.greek.lemmatize import lemmatize

    assert lemmatize("Κυρίου") == "κύριος"
    assert lemmatize("κυρίου") == "κύριος"


# ── anti-regression: the genuine oxytone -ός genitive shares the circumflex and MUST still
#    strip; the fix must not disturb any correct path (measured: 0 correct lemmas lost) ──────
@pytest.mark.parametrize(
    "form,want",
    [("Χριστοῦ", "Χριστός"), ("οὐρανοῦ", "οὐρανός"), ("λαοῦ", "λαός"), ("ἀδελφοῦ", "ἀδελφός"),
     ("ναοῦ", "ναός"), ("ὁδοῦ", "ὁδός"), ("θυμοῦ", "θυμός")],
)
def test_oxytone_os_genitive_still_strips_correctly(form: str, want: str) -> None:
    from aegean.greek.lemmatize import lemmatize, rule_lemma_verbose

    # an oxytone -ός noun takes the circumflex in the genitive (Smyth §163a); its -οῦ IS the
    # regular thematic genitive and DOES strip to -ός — the guard must not block it.
    assert _nfc(lemmatize(form)) == want, form
    lemma, recovered = rule_lemma_verbose(form)
    assert recovered and _nfc(lemma) == want, (form, lemma)


def test_regular_second_decl_genitive_unaffected() -> None:
    """The plain -ου → -ος strip (Smyth §211) and the seed hits are untouched by the fix."""
    from aegean.greek.lemmatize import lemmatize

    for form, want in [("λόγου", "λόγος"), ("νόμου", "νόμος"), ("λόγον", "λόγος"),
                       ("ἀνθρώπου", "ἄνθρωπος")]:
        assert _nfc(lemmatize(form)) == want, form


def test_kuria_and_kurios_derivatives_are_untouched() -> None:
    """The feminine κυρία ("lady") and the derivatives κυριότης / κυριακός / κυριεύω have
    distinct stems; seeding the masculine κύριος paradigm must not capture them."""
    from aegean.greek.lemmatize import lemmatize

    assert lemmatize("κυρία") != "κύριος"                 # feminine nominative
    assert lemmatize("κυρίᾳ") != "κύριος"                 # feminine dative (-ᾳ, not the masc -ῳ)
    assert lemmatize("κυριότητος") != "κύριος"            # κυριότης
    assert _nfc(lemmatize("κυριεύει")) == "κυριεύω"       # the verb still strips normally


# ── the grave/enclitic normalization the neighboring guards rely on still holds through the
#    new seed lookup (the seed key folds a grave to the acute, like every other seed) ─────────
def test_seed_lookup_still_folds_grave_and_normalizes() -> None:
    from aegean.greek.lemmatize import lemmatize

    # a decomposed (NFD) input resolves identically to the composed form (the seed key is NFC)
    assert lemmatize(unicodedata.normalize("NFD", "Ἰησοῦ")) == "Ἰησοῦς"
    # and a neighboring guard's enclitic-throwback case is unregressed
    assert _nfc(lemmatize("δῶρόν")) == "δῶρον"


def test_no_contract_or_kurios_form_is_a_confident_fabrication() -> None:
    """The umbrella property: none of the fixed forms is a confident (known=True) *-ος
    non-word. Either a correct seed hit, or an honest miss — never a fabrication."""
    from aegean.greek.lemmatize import lemmatize_verbose

    for form in ["Ἰησοῦ", "Ἰησοῦν", "νοῦν", "χοῦν",
                 "Κυρίου", "κυρίου", "Κυρίῳ", "Κύριον", "Κύριε"]:
        lemma, known = lemmatize_verbose(form)
        if known:
            # a confident answer must be the actual attested lemma, not a mis-accented -ος
            assert lemma in {"Ἰησοῦς", "νοῦς", "χοῦς", "κύριος"}, (form, lemma)
