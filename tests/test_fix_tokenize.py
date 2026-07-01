"""Greek punctuation in the tokenizer letter class, γάρ/οὖν tagging, movable-ν guards.

Regression tests for three fixes:

1. The tokenizer's letter class spanned U+0370–03FF wholesale, so U+0387 GREEK
   ANO TELEIA and U+037E GREEK QUESTION MARK (canonical punctuation; NFC folds
   them to ``·`` and ``;``) were glued into WORD tokens (3,330 glued tokens over
   the bundled NT text with its punctuation in canonical form). Both must
   tokenize as PUNCT, exactly like their lookalikes, and ``pos_tag`` must agree.
2. γάρ and οὖν were tagged SCONJ; both are postpositive connectives that never
   subordinate. The bundled NT gold (reconciled UD upos) tags every occurrence
   CCONJ, like δέ.
3. The movable-ν rule fired on any -σι(ν)/-στι(ν) shape, so third-declension
   i-stem accusative singulars (γνῶσιν, πίστιν: the ν is the case morpheme) got
   a false ``movable-nu`` with a fabricated bare alternative. The rule now only
   claims validated hosts (-ουσι(ν), or the curated ``_MOVABLE_NU_HOSTS``).
"""

from __future__ import annotations

import pytest

from aegean.core.model import TokenKind
from aegean.greek.pos import pos_tag
from aegean.greek.sandhi import resolve_sandhi
from aegean.greek.tokenize import sentences, tokenize, tokenize_words

ANO_TELEIA = "·"  # GREEK ANO TELEIA (NFC folds it to U+00B7)
GREEK_QMARK = ";"  # GREEK QUESTION MARK (NFC folds it to U+003B)


# --- 1. U+0387 / U+037E are punctuation, not letters -------------------------


def test_ano_teleia_splits_off_the_word() -> None:
    toks = tokenize(f"λόγος{ANO_TELEIA} θεός")
    assert [(t.text, t.kind) for t in toks] == [
        ("λόγος", TokenKind.WORD),
        (ANO_TELEIA, TokenKind.PUNCT),
        ("θεός", TokenKind.WORD),
    ]


def test_greek_question_mark_splits_off_the_word() -> None:
    toks = tokenize(f"τίς{GREEK_QMARK}")
    assert [(t.text, t.kind) for t in toks] == [
        ("τίς", TokenKind.WORD),
        (GREEK_QMARK, TokenKind.PUNCT),
    ]


def test_tokenize_words_drops_canonical_greek_punctuation() -> None:
    text = f"λόγος{ANO_TELEIA} τίς{GREEK_QMARK}"
    assert tokenize_words(text) == ["λόγος", "τίς"]


def test_canonical_punctuation_matches_nfc_lookalike_tokenization() -> None:
    # U+0387 must tokenize exactly like its NFC fold U+00B7 (and U+037E like
    # ';'): same token boundaries, same kinds.
    canonical = tokenize(f"λόγος{ANO_TELEIA} τίς{GREEK_QMARK}")
    folded = tokenize("λόγος· τίς;")
    assert [t.kind for t in canonical] == [t.kind for t in folded]
    assert [t.text for t in canonical if t.kind is TokenKind.WORD] == [
        t.text for t in folded if t.kind is TokenKind.WORD
    ]


def test_sentence_split_on_canonical_punctuation_still_works() -> None:
    text = f"ἐν ἀρχῇ{ANO_TELEIA} ὁ λόγος{GREEK_QMARK} τέλος."
    assert sentences(text) == ["ἐν ἀρχῇ", "ὁ λόγος", "τέλος"]


@pytest.mark.parametrize(
    "letter",
    [
        "Ͱ",  # U+0370, range start
        "ͽ",  # U+037D, just below the question mark
        "Ϳ",  # U+037F, just above it
        "Ά",  # U+0386, just below the ano teleia
        "Έ",  # U+0388, just above it
        "Ͽ",  # U+03FF, range end
        "ϝ",  # digamma, mid-range
        "ᾷ",  # Extended Greek
    ],
)
def test_boundary_letters_are_still_word_tokens(letter: str) -> None:
    toks = tokenize(letter)
    assert len(toks) == 1 and toks[0].kind is TokenKind.WORD


def test_pos_tag_canonical_greek_punctuation_is_punct() -> None:
    assert pos_tag(ANO_TELEIA) == "PUNCT"
    assert pos_tag(GREEK_QMARK) == "PUNCT"
    # and the NFC lookalikes agree
    assert pos_tag("·") == "PUNCT"
    assert pos_tag(";") == "PUNCT"


# --- 2. γάρ / οὖν are CCONJ, never SCONJ --------------------------------------


@pytest.mark.parametrize("word", ["γάρ", "γὰρ", "οὖν"])
def test_gar_and_oun_are_cconj(word: str) -> None:
    # NT gold (reconciled UD upos): γάρ 1038/1038 CCONJ, οὖν 496/496 CCONJ,
    # matching δέ; neither can subordinate a clause.
    assert pos_tag(word) == "CCONJ"


@pytest.mark.parametrize("word", ["ὅτι", "εἰ", "ἐάν", "ἵνα", "ὡς", "ὅπως", "ἐπεί"])
def test_true_subordinators_remain_sconj(word: str) -> None:
    assert pos_tag(word) == "SCONJ"


def test_other_postpositive_particles_unchanged() -> None:
    for w in ("μέν", "δή", "ἄρα"):
        assert pos_tag(w) == "PART"
    assert pos_tag("δέ") == "CCONJ"


# --- 3. movable-ν only on validated hosts -------------------------------------


@pytest.mark.parametrize("word", ["γνῶσιν", "φύσιν", "κρίσιν", "πίστιν", "βάσιν", "θέσιν"])
def test_istem_accusative_is_not_claimed_movable(word: str) -> None:
    # The final ν is the accusative morpheme; a bare alternant would be a
    # fabricated non-word.
    r = resolve_sandhi(word)
    assert r.kind is None
    assert r.words == (word,)
    assert r.alternatives == ()


@pytest.mark.parametrize(
    "word,bare",
    [
        ("ἐστίν", "ἐστί"),  # copula (curated host)
        ("ἐστὶν", "ἐστὶ"),  # grave running-text variant matches the key
        ("Ἔστιν", "Ἔστι"),  # sentence-initial casing matches too
        ("εἰσίν", "εἰσί"),
        ("φησίν", "φησί"),
        ("δίδωσιν", "δίδωσι"),  # athematic 3sg
        ("πᾶσιν", "πᾶσι"),  # dative plural
        ("χερσίν", "χερσί"),
        ("λέγουσιν", "λέγουσι"),  # -ουσι(ν): validated by ending alone
        ("ποιοῦσιν", "ποιοῦσι"),
    ],
)
def test_validated_movable_nu_hosts_still_fire(word: str, bare: str) -> None:
    r = resolve_sandhi(word)
    assert r.kind == "movable-nu"
    assert r.words == (word,)  # with-ν citation form kept
    assert r.alternatives == (bare,)


def test_accent_distinguishes_host_from_accusative_homograph() -> None:
    # dat. pl. ποσίν (πούς) is a movable-ν host; acc. sg. πόσιν (πόσις) is not.
    assert resolve_sandhi("ποσίν").kind == "movable-nu"
    assert resolve_sandhi("πόσιν").kind is None
    # 3pl φασίν vs acc. sg. φάσιν likewise.
    assert resolve_sandhi("φασίν").kind == "movable-nu"
    assert resolve_sandhi("φάσιν").kind is None


def test_negative_particle_sandhi_unchanged() -> None:
    for surface in ("οὐκ", "οὐχ"):
        r = resolve_sandhi(surface)
        assert r.kind == "movable-nu"
        assert r.words == ("οὐ",)
    assert resolve_sandhi("οὐ").kind is None
