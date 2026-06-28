"""Accent *placement* (the laws engine, `aegean.greek.accent_law`).

A curated gold set of forms whose accent is fully determinable from spelling (no decisive
dichronon) gives a measured placement-accuracy number; separate tests pin the honest
`certain=False` behaviour on dichrona and the morphology-override that resolves them.
"""

from __future__ import annotations

from aegean.greek import accentuation
from aegean.greek.accent_law import LONG, persistent_accent, place_accent, recessive_accent

# Finite verbs (recessive): (bare-but-breathed input, expected accented form).
GOLD_RECESSIVE = [
    ("λυω", "λύω"),
    ("ἐλυον", "ἔλυον"),
    ("παιδευω", "παιδεύω"),
    ("ἐπαιδευον", "ἐπαίδευον"),
    ("λεγω", "λέγω"),
    ("γραφω", "γράφω"),
    ("ἐγραφον", "ἔγραφον"),
    ("βουλομαι", "βούλομαι"),   # final -μαι counts short -> proparoxytone
    ("φερε", "φέρε"),
]

# Nominals (persistent): (bare form, lemma, expected accented form).
GOLD_PERSISTENT = [
    ("ἀνθρωπος", "ἄνθρωπος", "ἄνθρωπος"),
    ("ἀνθρωπου", "ἄνθρωπος", "ἀνθρώπου"),   # long ultima pulls accent off the antepenult
    ("λογος", "λόγος", "λόγος"),
    ("λογου", "λόγος", "λόγου"),
    ("δωρον", "δῶρον", "δῶρον"),             # long penult + short ultima -> circumflex
    ("δωρου", "δῶρον", "δώρου"),             # circumflex -> acute when the ultima lengthens
    ("θαλασσης", "θάλασσα", "θαλάσσης"),
]


def test_recessive_gold():
    for bare, expected in GOLD_RECESSIVE:
        ap = recessive_accent(bare)
        assert ap.form == expected, f"{bare} -> {ap.form!r} != {expected!r}"
        assert ap.certain, f"{bare} should be determinable"


def test_persistent_gold():
    for bare, lemma, expected in GOLD_PERSISTENT:
        ap = persistent_accent(bare, lemma)
        assert ap.form == expected, f"{bare}/{lemma} -> {ap.form!r} != {expected!r}"
        assert ap.certain, f"{bare} should be determinable"


def test_placement_accuracy_on_determinable_set():
    """The measured number: placement is exact on the determinable gold set."""
    total = len(GOLD_RECESSIVE) + len(GOLD_PERSISTENT)
    correct = sum(recessive_accent(b).form == e for b, e in GOLD_RECESSIVE)
    correct += sum(persistent_accent(b, lem).form == e for b, lem, e in GOLD_PERSISTENT)
    assert correct / total == 1.0, f"{correct}/{total}"


def test_round_trip_against_reader():
    """Re-placing a known accent reproduces it, and the reader agrees on type/position."""
    for bare, expected in GOLD_RECESSIVE:
        ap = recessive_accent(bare)
        info = accentuation(ap.form)
        assert info.accent_type == ap.accent_type
        assert info.position_from_end == ap.position_from_end
        assert info.classification == ap.classification


def test_classification_fields():
    assert recessive_accent("βουλομαι").classification == "proparoxytone"
    assert persistent_accent("δωρον", "δῶρον").classification == "properispomenon"
    assert recessive_accent("λυω").classification == "paroxytone"


def test_accent_lands_on_second_vowel_of_diphthong():
    # παιδεύω: the ευ diphthong carries the accent on its second vowel (υ).
    assert recessive_accent("παιδευω").form == "παιδεύω"
    # final -αι is short, so βούλομαι is proparoxytone (not paroxytone).
    assert recessive_accent("βουλομαι").position_from_end == 3


def test_dichronon_is_flagged_uncertain():
    # final α (dichronon) of θάλασσα leaves antepenult-vs-penult undecided
    ap = persistent_accent("θαλασσα", "θάλασσα")
    assert ap.certain is False and "dichronon" in ap.note
    # penult υ of λῦε leaves acute-vs-circumflex undecided
    assert recessive_accent("λυε").certain is False


def test_morphology_override_resolves_dichronon():
    # told the penult is long, the engine commits to the circumflex λῦε, certainly.
    ap = recessive_accent("λυε", penult_length=LONG)
    assert ap.form == "λῦε" and ap.certain and ap.accent_type == "circumflex"


def test_strips_an_existing_wrong_accent():
    # placement works regardless of any accent already present (it is stripped first).
    assert recessive_accent("λυώ").form == "λύω"
    assert recessive_accent("ἔλύον").form == "ἔλυον"


def test_place_accent_dispatch():
    assert place_accent("λυω", recessive=True).form == "λύω"
    assert place_accent("ἀνθρωπου", recessive=False, lemma="ἄνθρωπος").form == "ἀνθρώπου"
