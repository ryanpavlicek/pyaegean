"""Rule-based Greek morphological analysis."""

from __future__ import annotations

from aegean.greek import analyze, best_pos, lemmas
from aegean.greek.morphology import Analysis


def _has(word: str, pos: str, **features: str) -> bool:
    """Whether some analysis of ``word`` has this pos and (at least) these feats."""
    return any(
        a.pos == pos and all(a.features().get(k) == v for k, v in features.items())
        for a in analyze(word)
    )


def test_second_declension_noun_cases() -> None:
    assert _has("λόγον", "NOUN", case="acc", number="sg", gender="masc")
    assert _has("λόγου", "NOUN", case="gen", number="sg")
    assert _has("λόγους", "NOUN", case="acc", number="pl")
    assert _has("ἀνθρώπων", "NOUN", case="gen", number="pl")


def test_dative_singular_needs_iota_subscript() -> None:
    # λόγῳ (with subscript) is a dative; it is *not* the verb λόγω.
    assert _has("λόγῳ", "NOUN", case="dat", number="sg")
    assert not any(a.pos == "VERB" for a in analyze("λόγῳ"))
    # ἀρχῇ → dat sg fem; θεᾷ → dat sg fem.
    assert _has("ἀρχῇ", "NOUN", case="dat", number="sg", gender="fem")
    assert _has("θεᾷ", "NOUN", case="dat", number="sg", gender="fem")


def test_first_declension_feminine() -> None:
    assert _has("θεάν", "NOUN", case="acc", number="sg", gender="fem")
    assert _has("μούσαις", "NOUN", case="dat", number="pl", gender="fem")


def test_thematic_present_active() -> None:
    assert _has("λύω", "VERB", tense="pres", voice="act", mood="ind", person="1", number="sg")
    assert _has("λύεις", "VERB", tense="pres", voice="act", mood="ind", person="2", number="sg")
    assert _has("λύομεν", "VERB", tense="pres", voice="act", mood="ind", person="1", number="pl")
    assert _has("λύουσιν", "VERB", tense="pres", voice="act", mood="ind", person="3", number="pl")


def test_future_and_aorist() -> None:
    assert _has("λύσει", "VERB", tense="fut", voice="act", mood="ind", person="3", number="sg")
    assert _has("ἔλυσα", "VERB", tense="aor", voice="act", mood="ind", person="1", number="sg")


def test_augment_required_for_past_tense() -> None:
    # Without an augment, -ομεν is present only (no spurious imperfect), and a
    # plain noun like λόγον never reads as an (unaugmented) imperfect verb.
    tenses = {a.tense for a in analyze("λύομεν") if a.pos == "VERB"}
    assert tenses == {"pres"}
    assert not any(a.pos == "VERB" for a in analyze("λόγον"))


def test_infinitive_and_participle() -> None:
    assert _has("λύειν", "VERB", tense="pres", voice="act", mood="inf")
    assert _has("λυόμενος", "VERB", tense="pres", voice="mp", mood="part", gender="masc")


def test_mediopassive_present() -> None:
    assert _has("λύομαι", "VERB", tense="pres", voice="mp", mood="ind", person="1", number="sg")
    assert _has("λύεται", "VERB", tense="pres", voice="mp", mood="ind", person="3", number="sg")


def test_closed_class_is_single_and_confident() -> None:
    art = analyze("ὁ")
    assert len(art) == 1 and art[0] == Analysis(lemma="ὁ", pos="DET")
    assert analyze("καί")[0].pos == "CCONJ"
    assert analyze("ἐν")[0].pos == "ADP"


def test_lemma_uses_seed_when_known_else_reconstructs() -> None:
    # Seed-known forms get the correctly-accented lemma and lemma_certain=True.
    known = [a for a in analyze("ἀνθρώπων") if a.pos == "NOUN"][0]
    assert known.lemma == "ἄνθρωπος"
    assert known.lemma_certain is True
    # An out-of-vocabulary regular form is reconstructed (unaccented, uncertain):
    # ἵππον (acc sg) → nominative ἱππος (accent not restored).
    oov = [a for a in analyze("ἵππον") if a.pos == "NOUN"][0]
    assert oov.lemma == "ιππος"
    assert oov.lemma_certain is False


def test_lemmas_and_best_pos() -> None:
    assert "ἄνθρωπος" in lemmas("ἀνθρώπων")
    assert best_pos("λύεις") == "VERB"
    assert best_pos("ἀρχῇ") == "NOUN"
    assert best_pos("ὁ") == "DET"
    assert best_pos("…") is None  # nothing analysable


def test_third_declension_lemma_is_uncertain() -> None:
    # A third-declension dative plural is recognised, but its nominative (lemma)
    # is not rule-recoverable, so the lemma is flagged uncertain.
    a = [x for x in analyze("σώμασιν") if x.pos == "NOUN" and x.case == "dat"]
    assert a and all(not x.lemma_certain for x in a)


def test_ambiguity_is_surfaced() -> None:
    # -ον is genuinely ambiguous across gender/case; several readings come back.
    cases = {(a.case, a.gender) for a in analyze("δῶρον") if a.pos == "NOUN"}
    assert {("nom", "neut"), ("acc", "neut"), ("acc", "masc")} <= cases


def test_analyze_is_cached_and_returns_tuple() -> None:
    out = analyze("λόγον")
    assert isinstance(out, tuple)
    assert analyze("λόγον") is out  # lru_cache returns the same object


def test_indefinite_and_interrogative_pronoun() -> None:
    # analyze('τις') used to return [] — the enclitic indefinite is now covered.
    indef = analyze("τις")
    assert indef and all(a.pos == "PRON" and a.lemma == "τις" for a in indef)
    assert _has("τις", "PRON", case="nom", number="sg", gender="masc")
    # The interrogative τίς (persistent acute) is a distinct lemma/paradigm.
    interr = analyze("τίς")
    assert interr and all(a.pos == "PRON" and a.lemma == "τίς" for a in interr)
    assert _has("τίς", "PRON", case="nom", number="sg")
    # Oblique forms carry case/number/gender, and the accent keeps the two apart.
    assert _has("τινός", "PRON", case="gen", number="sg")  # enclitic indefinite
    assert _has("τίνα", "PRON", case="acc", number="sg", gender="masc")  # interrogative
    assert all(a.lemma == "τις" for a in analyze("τινός"))
    assert all(a.lemma == "τίς" for a in analyze("τίνα"))


def test_relative_pronoun_paradigm() -> None:
    assert _has("ὅς", "PRON", case="nom", number="sg", gender="masc")
    assert _has("ἥ", "PRON", case="nom", number="sg", gender="fem")
    assert _has("ὅ", "PRON", case="nom", number="sg", gender="neut")
    assert _has("ᾧ", "PRON", case="dat", number="sg", gender="masc")
    assert _has("ὧν", "PRON", case="gen", number="pl")
    assert _has("οἷς", "PRON", case="dat", number="pl")
    assert all(a.lemma == "ὅς" for a in analyze("ᾧ"))
    # The relative ἥ (rough breathing) is not the article ἡ (smooth): the latter
    # stays a single DET reading, carrying its citation lemma ὁ.
    art = analyze("ἡ")
    assert art and art[0] == Analysis(lemma="ὁ", pos="DET")


def test_added_determiners_numerals_ordinals() -> None:
    # Determiners and numerals resolve to a single confident closed-class tag.
    assert analyze("ἄλλος")[0].pos == "DET"
    assert analyze("ἕκαστος")[0].pos == "DET"
    assert analyze("πᾶς")[0].pos == "DET"
    assert analyze("εἷς")[0].pos == "NUM"
    assert analyze("δύο")[0].pos == "NUM"
    assert analyze("τρεῖς")[0].pos == "NUM"
    assert best_pos("εἷς") == "NUM"
    # Ordinals follow UD: ADJ, not NUM.
    assert analyze("πρῶτος")[0].pos == "ADJ"
    assert best_pos("πρῶτος") == "ADJ"


def test_rule_engine_is_backend_independent(monkeypatch) -> None:
    """The rule engine's seed-lemma hint must never consult the trained backends.

    Regression: with use_tagger() + use_lemmatizer() both active, analyze() used to
    recurse to death on an out-of-vocabulary form (analyze → seed hint → edit-tree
    predict → POS features → analyze …), and _rule_analyze's lru_cache made results
    depend on backend state. The morphology engine now reads the seed tier only."""
    from aegean.greek import lemmatizer, neural_lemmatizer
    from aegean.greek.morphology import _rule_analyze

    def boom(*_args, **_kwargs):  # any backend consultation is the bug
        raise AssertionError("rule engine consulted a trained backend")

    monkeypatch.setattr(lemmatizer, "active", lambda: object())
    monkeypatch.setattr(lemmatizer, "predict", boom)
    monkeypatch.setattr(neural_lemmatizer, "active", lambda: object())
    monkeypatch.setattr(neural_lemmatizer, "predict", boom)

    _rule_analyze.cache_clear()
    try:
        out = analyze("ἵππον")  # an OOV-ish nominal: the old path hit the cascade
        assert out  # still analysable, from rules + the seed table alone
        assert analyze("καί")  # closed-class branch too
    finally:
        _rule_analyze.cache_clear()  # don't leak stubbed-state entries to other tests
