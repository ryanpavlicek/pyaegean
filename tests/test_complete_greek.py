"""Coverage-completion tests for `aegean.greek` (test-coverage-completion task).

Audit of the assigned `aegean.greek` public group (normalize/betacode/strip/tokenize/
sentences, syllabify, accentuation/place_accent/recessive_accent/persistent_accent,
scan_*/scan_line/syllable_options/syllable_quantities, pos_tag(s)/best_pos/analyze/
analyze_sentence, lemmatize/lemmatize_verbose/seed_lemma_verbose/rule_lemma_verbose,
resolve_sandhi/resolve_sentence, to_ipa, pipeline, catalog/popular_works/nt_books,
load_nt/load_work) found nearly the whole surface already correctness-tested. Where each
already-covered function's correctness test lives:

  - normalize, betacode_to_unicode, unicode_to_betacode, strip_diacritics:
        test_greek_normalize
  - tokenize, tokenize_words, sentences, syllabify, accentuation, lemmatize,
        lemmatize_verbose, rule_lemma_verbose: test_greek_pipeline
  - place_accent, recessive_accent, persistent_accent: test_accent_law
  - scan, syllable_quantities: test_greek_prosody
  - scan_hexameter/pentameter/trimeter/aeolic, scan_line, syllable_options:
        test_greek_meter
  - pos_tag, pos_tags: test_greek_pos
  - analyze, best_pos, lemmas: test_greek_morphology
  - resolve_sandhi, resolve_sentence: test_greek_sandhi
  - to_ipa: test_greek_phonology
  - pipeline: test_pipeline_convenience
  - catalog, popular_works, nt_books: test_greek_catalogue, test_greek_discovery
  - load_nt (incl. the offline bundled-sample fallback): test_nt, test_koine

The one genuinely UNTESTED public function in the group is the seed-tier lemma lookup
`seed_lemma_verbose` (only exercised indirectly through `lemmatize`). It is the
foundation of the lemmatizer cascade and has an explicit "never consults the trained
backends" contract, so it earns a direct correctness test here. Each expected value is
hand-derived from Ancient Greek morphology (not read back from the function) or asserted
as a true invariant over the bundled gold table.

`analyze_sentence` (the neural-joint pipeline) and `load_work` (Perseus/First1KGreek
fetch) are network/model-gated and not deeply tested here; see the note at the bottom.
"""

from __future__ import annotations

import unicodedata

from aegean.greek.lemmatize import _lemma_table, seed_lemma_verbose


# ── seed_lemma_verbose: known forms ──────────────────────────────────────────
def test_seed_lemma_verbose_known_irregular() -> None:
    """ἦν is the 3rd-sg imperfect of the suppletive copula; its citation form is εἰμί.
    This lemma is NOT derivable from the ending (it is irregular/suppletive), which is
    exactly why it lives in the seed table rather than the rule layer."""
    assert seed_lemma_verbose("ἦν") == ("εἰμί", True)


def test_seed_lemma_verbose_known_regular() -> None:
    """θεόν is the accusative singular of the 2nd-declension noun θεός; the seed table
    returns the correctly-accented nominative citation form with known=True."""
    assert seed_lemma_verbose("θεόν") == ("θεός", True)


def test_seed_lemma_verbose_unknown_returns_nfc_form_unchanged() -> None:
    """πατρός (3rd-decl. genitive of πατήρ) is held out of the seed table and its lemma
    is not ending-recoverable, so the seed tier returns the NFC-normalized input verbatim
    with known=False (it does not guess, and crucially does not fall through to the rule
    layer — that composition happens one level up in lemmatize_verbose)."""
    assert "πατρός" not in _lemma_table()  # genuinely not a seed entry
    assert seed_lemma_verbose("πατρός") == ("πατρός", False)


# ── seed_lemma_verbose: lookup invariants ────────────────────────────────────
def test_seed_lemma_verbose_lookup_is_case_insensitive() -> None:
    """The docstring promises a lowercase-folded lookup: an all-caps spelling of a
    seed-known form must hit the same lemma (θεός), with the lemma returned in its
    canonical lowercase accented form, not uppercased back."""
    assert seed_lemma_verbose("ΘΕΌΝ") == ("θεός", True)
    # and folding does not invent a hit for an unknown caps form
    assert seed_lemma_verbose("ΞΈΝΟΝ")[1] is False


def test_seed_lemma_verbose_lookup_is_normalization_blind() -> None:
    """Table keys are normalized to NFC, so a decomposed (NFD) spelling of a known form
    still resolves. The NFD and NFC byte sequences differ but denote the same word."""
    nfd_input = unicodedata.normalize("NFD", "θεόν")
    assert nfd_input != "θεόν"  # genuinely a different (decomposed) string
    assert seed_lemma_verbose(nfd_input) == ("θεός", True)


def test_seed_lemma_verbose_returns_nfc_for_unknown_nfd_input() -> None:
    """For an unknown form the contract is to return the *NFC-normalized* input. Feeding
    a decomposed (NFD) unknown form must come back composed (NFC), not as the raw NFD
    string the caller passed in."""
    word = "ξένος"  # not in the seed table
    assert word not in _lemma_table()
    out, known = seed_lemma_verbose(unicodedata.normalize("NFD", word))
    assert known is False
    assert out == unicodedata.normalize("NFC", word)
    # the returned string is itself already NFC (idempotent under re-normalization)
    assert out == unicodedata.normalize("NFC", out)


def test_seed_lemma_verbose_ignores_active_backends(monkeypatch) -> None:
    """Contract from the docstring: the seed tier reads the bundled table ONLY and never
    consults the trained backends (the morphology/rule layers depend on that — their
    features must not shift with backend state, and the backends call back into the seed
    tier). Stub both predictors to explode; seed_lemma_verbose must still return the
    table answer without touching them."""
    from aegean.greek import lemmatizer, neural_lemmatizer

    def boom(*_a: object, **_k: object) -> str:
        raise AssertionError("seed tier consulted a trained backend")

    monkeypatch.setattr(lemmatizer, "active", lambda: object())
    monkeypatch.setattr(lemmatizer, "predict", boom)
    monkeypatch.setattr(neural_lemmatizer, "active", lambda: object())
    monkeypatch.setattr(neural_lemmatizer, "predict", boom)

    assert seed_lemma_verbose("θεόν") == ("θεός", True)
    assert seed_lemma_verbose("ξένος") == ("ξένος", False)


def test_seed_table_values_are_all_known_to_the_seed_tier() -> None:
    """Whole-table invariant: every (form -> lemma) entry must, when looked up, report
    known=True and yield exactly its recorded lemma. This guards against a malformed or
    non-NFC seed entry that would silently be treated as unknown (the kind of dead-entry
    bug the project's audit was created to catch), without asserting any single answer
    that could drift."""
    table = _lemma_table()
    assert table  # the bundle is present and non-empty
    for form, lemma in table.items():
        out, known = seed_lemma_verbose(form)
        assert known is True, f"seed form {form!r} reported unknown"
        assert out == lemma, f"seed form {form!r} -> {out!r} != recorded {lemma!r}"


# ── Functions not deeply testable here (documented) ──────────────────────────
# greek.analyze_sentence IS the neural joint pipeline (greek.analyze_sentence is
#   joint.analyze_sentence); without use_neural_pipeline() it only raises
#   NeuralPipelineNotLoadedError. That activation contract is already covered in
#   test_joint.py (test_analyze_sentence_requires_activation), and exercising the real
#   model needs the fetched grc-joint asset (network), so no offline correctness test is
#   meaningful here. The rule-based sentence analysis is morphology.analyze_sentence and
#   is covered via analyze() in test_greek_morphology.
# greek.load_work fetches Perseus/First1KGreek TEI over the network; its TEI-parsing and
#   edition-selection internals (the deterministic, offline part) are correctness-tested
#   in test_greek_works.py against a bundled fixture. The public fetch path is network-
#   gated, so it is intentionally not retested offline here.
