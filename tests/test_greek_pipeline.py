"""Greek NLP stages: tokenize, syllabify, accent analysis, baseline lemmatize."""

from __future__ import annotations

import pytest

from aegean.core.model import TokenKind
from aegean.greek import (
    accentuation,
    lemmatize,
    lemmatize_verbose,
    sentences,
    syllabify,
    tokenize,
    tokenize_words,
)


# ── tokenization ─────────────────────────────────────────────────────────────
def test_tokenize_words_drops_punctuation():
    assert tokenize_words("ἐν ἀρχῇ ἦν ὁ λόγος, καὶ θεός.") == [
        "ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος", "καὶ", "θεός"
    ]


def test_tokenize_keeps_elision_apostrophe():
    # Sappho's elided forms keep their internal/trailing apostrophe in one token
    words = tokenize_words("ποικιλόθρον’ ἀθανάτ’ Ἀφρόδιτα")
    assert words == ["ποικιλόθρον’", "ἀθανάτ’", "Ἀφρόδιτα"]


def test_tokenize_types_words_and_punct():
    toks = tokenize("λόγος, καί")
    assert [(t.text, t.kind) for t in toks] == [
        ("λόγος", TokenKind.WORD),
        (",", TokenKind.PUNCT),
        ("καί", TokenKind.WORD),
    ]


def test_sentences_split_on_greek_punctuation():
    assert sentences("ἐν ἀρχῇ ἦν ὁ λόγος. καὶ θεός ἦν;") == [
        "ἐν ἀρχῇ ἦν ὁ λόγος",
        "καὶ θεός ἦν",
    ]


# ── syllabification ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "word,expected",
    [
        ("λόγος", ["λό", "γος"]),
        ("ἄνθρωπος", ["ἄν", "θρω", "πος"]),   # muta cum liquida: θρ stays together
        ("θάλασσα", ["θά", "λασ", "σα"]),       # doubled σσ splits
        ("Μῆνιν", ["Μῆ", "νιν"]),
        ("ποικιλόθρον", ["ποι", "κι", "λό", "θρον"]),  # οι diphthong
        ("ἀρχῇ", ["ἀρ", "χῇ"]),
        ("Ἀχιλῆος", ["Ἀ", "χι", "λῆ", "ος"]),  # vowel hiatus η|ο
    ],
)
def test_syllabify(word, expected):
    assert syllabify(word) == expected


# ── lexicalised exceptions (compounds divide at the point of union, Smyth §140) ──
def test_syllabify_exceptions_override_the_rules():
    assert syllabify("εἰσφέρω") == ["εἰσ", "φέ", "ρω"]    # rules would give εἰ-σφέ-ρω
    assert syllabify("ἐκλείπω") == ["ἐκ", "λεί", "πω"]    # rules would give ἐ-κλεί-πω
    assert syllabify("δύσκολος") == ["δύσ", "κο", "λος"]  # rules would give δύ-σκο-λος


def test_syllabify_exceptions_preserve_casing():
    assert syllabify("Εἰσφέρω") == ["Εἰσ", "φέ", "ρω"]


def test_every_exception_entry_earns_its_place():
    """Each lexicon entry must join back to its form AND differ from the rules
    (otherwise it is dead weight and should be removed)."""
    from aegean.greek.syllabify import _EXCEPTIONS, _rule_syllabify

    for form, syls in _EXCEPTIONS.items():
        assert "".join(syls) == form, f"{form}: syllables don't join back"
        assert list(syls) != _rule_syllabify(form), f"{form}: rules already agree"
        assert syllabify(form) == list(syls)


# ── accent analysis ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "word,acc,pos,cls",
    [
        ("λόγος", "acute", 2, "paroxytone"),
        ("θεά", "acute", 1, "oxytone"),
        ("ἄνθρωπος", "acute", 3, "proparoxytone"),
        ("Μῆνιν", "circumflex", 2, "properispomenon"),
        ("πρὸς", "grave", 1, "barytone"),
    ],
)
def test_accentuation(word, acc, pos, cls):
    info = accentuation(word)
    assert info.accent_type == acc
    assert info.position_from_end == pos
    assert info.classification == cls


def test_accentuation_unaccented():
    info = accentuation("ανθρωπος")  # no accent marks
    assert info.accent_type is None
    assert info.classification is None


# ── baseline lemmatization ───────────────────────────────────────────────────
def test_lemmatize_seed_table():
    assert lemmatize("λόγου") == "λόγος"
    assert lemmatize("ἦν") == "εἰμί"
    assert lemmatize("θεόν") == "θεός"


def test_lemmatize_unknown_returns_normalized_form():
    # A form outside the regular paradigms the rule layer covers (a third-declension stem
    # whose lemma is not recoverable from the ending) is returned unchanged.
    lemma, known = lemmatize_verbose("πατρός")
    assert known is False
    assert lemma == "πατρός"


# The generalizing ending-stripping rule layer must recover the citation form of regular
# inflected words it has never seen (none of these are in the seed table), by stem-preserving
# ending substitution. Each pair is a hand-checked (form, lemma) for the regular first/second-
# declension nominal and thematic-verb paradigms. This is the correctness guard for the claim
# that the default lemmatizer generalizes rather than only looking up a seed table.
@pytest.mark.parametrize(
    ("form", "lemma"),
    [
        ("νόμου", "νόμος"),       # 2nd-decl noun, genitive sg, accent on the stem
        ("ἀγαθόν", "ἀγαθός"),     # 2nd-decl adjective, accusative sg, oxytone
        ("ἀγαθῷ", "ἀγαθός"),      # 2nd-decl dative sg (iota subscript), perispomenon
        ("ἀδελφοί", "ἀδελφός"),   # 2nd-decl nominative pl, oxytone
        ("δόξαν", "δόξα"),        # 1st-decl feminine -α, accusative sg
        ("λύομεν", "λύω"),        # thematic verb, present 1pl
        ("γράφεις", "γράφω"),     # thematic verb, present 2sg
        ("λύει", "λύω"),          # thematic verb, present 3sg
        ("πιστεύειν", "πιστεύω"), # present active infinitive
    ],
)
def test_rule_layer_lemmatizes_unseen_regular_forms(form: str, lemma: str):
    from aegean.greek.lemmatize import _lemma_table, rule_lemma_verbose

    assert form not in _lemma_table()  # genuinely held out from the seed table
    out, recovered = rule_lemma_verbose(form)
    assert (out, recovered) == (lemma, True)
    # and it flows through the public default lemmatizer too
    assert lemmatize(form) == lemma


def test_rule_layer_does_not_overfire_on_irregular_or_indeclinable():
    # Forms outside the regular paradigms must be left unchanged, not force-fit to a rule. The
    # conservative guards (added after measuring on the full NT, where a naive stripper regressed
    # ~1,000 tokens) keep these whole: a contracted nominative (Ἰησοῦς, circumflex -οῦς), a neuter
    # noun whose lemma IS the -ον form (ἔργον), a contracted verb (ζῇ, circumflex -ῇ), a perispomenon
    # adverb (ποῦ), and a third-declension genitive.
    for surface in ("γυναικός", "μᾶλλον", "Ἰησοῦς", "ἔργον", "ζῇ", "ποῦ", "ἐκεῖ"):
        out, recovered = lemmatize_verbose(surface)
        assert (out, recovered) == (surface, False), f"{surface} was wrongly altered to {out}"
    # ἑαυτοῦ is now a genuine closed-class table hit (reflexive pronoun, lemma = itself),
    # returned known=True, not a fabricated recovery.
    assert lemmatize_verbose("ἑαυτοῦ") == ("ἑαυτοῦ", True)


def test_lemmatize_sourced_reports_the_evidence_class():
    from aegean.greek import LemmaSource, lemmatize_sourced

    assert lemmatize_sourced("ἦν") == ("εἰμί", LemmaSource.SEED)       # closed-class / seed
    assert lemmatize_sourced("νόμου") == ("νόμος", LemmaSource.RULE)   # ending-rule recovery
    assert lemmatize_sourced("πατρός") == ("πατρός", LemmaSource.UNRESOLVED)  # baseline miss


def test_needs_review_matches_the_lemma_known_flag():
    """`needs_review` is the exact complement of `lemmatize_verbose`'s `known`, and flags
    only the two ungrounded classes."""
    from aegean.greek import LemmaSource, needs_review

    assert needs_review(LemmaSource.IDENTITY) and needs_review(LemmaSource.UNRESOLVED)
    for grounded in (LemmaSource.ATTESTED, LemmaSource.NEURAL, LemmaSource.RULE,
                     LemmaSource.SEED, LemmaSource.PUNCT):
        assert not needs_review(grounded)
    # derivation consistency: known == not needs_review(source), for real forms
    from aegean.greek import lemmatize_sourced
    for w in ("ἦν", "νόμου", "πατρός", "ὁ", "θεόν", "ἀγαθῷ"):
        _lemma, src = lemmatize_sourced(w)
        assert lemmatize_verbose(w)[1] is (not needs_review(src))
