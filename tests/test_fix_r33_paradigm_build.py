"""Build-logic tests for the UniMorph paradigm-table gender cross-check.

Covers ``scripts/build_paradigm_table.py`` (repo-only build recipe): the attested-gender
cross-check that corrects UniMorph's wrong masculine articles on feminine second-declension
``-ος`` nouns (``ἡ δοκός``, ``ἡ κιβωτός``, ``ἡ ψῆφος``; Smyth §230 N.), the single-token
override guard, the curated feminine ``-ος`` backstop, and the structural ``-μα`` neuter fill.
All offline, on a tiny in-memory fixture, no clone or network.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_paradigm_table as B  # noqa: E402


def _lemma(s: str) -> str:
    return B.clean_lemma(s)


# --- strip_accents: the stem is accent-invariant across a shifting paradigm ---------------


def test_strip_accents_drops_accents_and_length_keeps_letters() -> None:
    assert B.strip_accents("πνεύματος") == "πνευματος"
    # accent shifts from lemma to genitive, the accent-blind stem does not
    assert B.strip_accents("ἀπόφθεγμα")[:-1] + "ατος" == B.strip_accents("ἀποφθέγματος")


# --- is_ma_neuter: the dental (-ματ-) genitive is the class diagnostic --------------------


def test_is_ma_neuter_true_on_dental_genitive() -> None:
    forms = {("nom", "sg"): {"πνεῦμα"}, ("gen", "sg"): {"πνεύματος"}}
    assert B.is_ma_neuter("πνεῦμα", forms) is True
    # gen plural in -ματων also counts
    assert B.is_ma_neuter("πρᾶγμα", {("gen", "pl"): {"πραγμάτων"}}) is True


def test_is_ma_neuter_false_without_dental_stem_or_ending() -> None:
    # a -μα lemma with no dental genitive in its paradigm (data gap / mis-shape)
    assert B.is_ma_neuter("ὄνομα", {("nom", "sg"): {"ὄνομα"}}) is False
    # not a -μα lemma at all
    assert B.is_ma_neuter("λόγος", {("gen", "sg"): {"λόγου"}}) is False
    # a genitive that is not the dental -ματος stem
    assert B.is_ma_neuter("δῶμα", {("gen", "sg"): {"δώμης"}}) is False


# --- agdt_gender_map: strict-plurality attested gender per NOUN lemma ---------------------


def test_agdt_gender_map_plurality_ties_and_filters() -> None:
    lexicon = {
        "δοκόν": [{"pos": "NOUN", "lemma": "δοκός", "gender": "fem", "case": "acc"}],
        "δοκός": [{"pos": "NOUN", "lemma": "δοκός", "gender": "fem", "case": "nom"}],
        "λόγος": [{"pos": "NOUN", "lemma": "λόγος", "gender": "masc"}],
        # a lemma attested 3 fem / 1 masc -> strict plurality fem
        "ὁδόν": [{"pos": "NOUN", "lemma": "ὁδός", "gender": "fem"}],
        "ὁδοῦ": [{"pos": "NOUN", "lemma": "ὁδός", "gender": "fem"}],
        "ὁδῷ": [{"pos": "NOUN", "lemma": "ὁδός", "gender": "fem"}],
        "ὁδός": [{"pos": "NOUN", "lemma": "ὁδός", "gender": "masc"}],
        # a lemma tied 1 fem / 1 masc -> omitted (no attested majority)
        "τιεα": [{"pos": "NOUN", "lemma": "τιε", "gender": "fem"}],
        "τιεβ": [{"pos": "NOUN", "lemma": "τιε", "gender": "masc"}],
        # a genderless NOUN and an adjective contribute nothing
        "καλός": [{"pos": "ADJ", "lemma": "καλός", "gender": "masc"}],
        "ανευ": [{"pos": "NOUN", "lemma": "ανευγ"}],
    }
    m = B.agdt_gender_map(lexicon)
    assert m["δοκός"] == ("fem", 2)
    assert m["λόγος"] == ("masc", 1)
    assert m["ὁδός"] == ("fem", 3)  # 3 fem beat 1 masc
    assert "τιε" not in m  # tie omitted
    assert "καλός" not in m  # adjective gender not harvested
    assert "ανευγ" not in m  # genderless


# --- resolve_noun_gender: the precedence chain -------------------------------------------


def test_resolve_ma_neuter_wins() -> None:
    # the structural neuter fill overrides everything, even a set article and attestation
    assert B.resolve_noun_gender("πνεῦμα", "masc", {"πνεῦμα": ("fem", 9)}, True) == "neut"


def test_resolve_attested_overrides_article_with_two_votes() -> None:
    assert B.resolve_noun_gender("δοκός", "masc", {"δοκός": ("fem", 5)}, False) == "fem"
    # attested masculine beats a wrong feminine article (>=2 votes)
    assert B.resolve_noun_gender("αὐχήν", "fem", {"αὐχήν": ("masc", 9)}, False) == "masc"


def test_resolve_single_vote_does_not_override_set_article() -> None:
    # one isolated token is too weak to overturn the article (the -εύς masc Παλληνεύς case)
    assert B.resolve_noun_gender("Παλληνεύς", "masc", {"Παλληνεύς": ("fem", 1)}, False) == "masc"


def test_resolve_single_vote_fills_absent_article() -> None:
    # but a single attestation is enough to FILL an absent article gender
    assert B.resolve_noun_gender("βοτάνη", None, {"βοτάνη": ("fem", 1)}, False) == "fem"


def test_resolve_curated_backstop_when_attested_silent() -> None:
    # κιβωτός: masc article, only a single (non-overriding) attestation -> curated fem
    assert B.resolve_noun_gender("κιβωτός", "masc", {"κιβωτός": ("fem", 1)}, False) == "fem"
    # curated fem with no attestation at all still wins over a wrong masc article
    assert B.resolve_noun_gender("ψῆφος", "masc", {}, False) == "fem"


def test_resolve_falls_back_to_article() -> None:
    assert B.resolve_noun_gender("λόγος", "masc", {}, False) == "masc"
    assert B.resolve_noun_gender("φύλαξ", "masc", {"φύλαξ": ("fem", 1)}, False) == "masc"
    assert B.resolve_noun_gender("ξένον", None, {}, False) is None


# --- build_index end-to-end on a tiny TSV fixture ----------------------------------------

_ROWS = [
    ("δοκός", "ὁ δοκός", "N;NOM;SG"),       # masc article, curated + AGDT fem -> fem
    ("δοκός", "τὸν δοκόν", "N;ACC;SG"),
    ("ἄρκτος", "ὁ ἄρκτος", "N;NOM;SG"),     # masc article, AGDT fem>=2, NOT curated -> fem
    ("λόγος", "ὁ λόγος", "N;NOM;SG"),       # masc article, AGDT masc -> masc
    ("πρᾶγμα", "πρᾶγμα", "N;NOM;SG"),       # no article, dental -μα -> neut (structural fill)
    ("πρᾶγμα", "πράγματος", "N;GEN;SG"),
    ("κιβωτός", "ὁ κιβωτός", "N;NOM;SG"),   # masc article, AGDT fem single vote -> curated fem
    ("φύλαξ", "ὁ φύλαξ", "N;NOM;SG"),       # masc article, AGDT fem single vote, not curated
    ("καλός", "καλός", "ADJ;NOM;SG;MASC"),  # adjective gender from the tag, not the noun logic
]

_ATTESTED = {
    _lemma("δοκός"): ("fem", 5),
    _lemma("ἄρκτος"): ("fem", 5),
    _lemma("λόγος"): ("masc", 3),
    _lemma("κιβωτός"): ("fem", 1),
    _lemma("φύλαξ"): ("fem", 1),
}


def _gender(index: dict, form: str) -> str | None:
    return index[form][0].get("gender")


def test_build_index_applies_crosscheck() -> None:
    index = B.build_index(_ROWS, attested=_ATTESTED)
    # feminine -ος corrected from the wrong masc article via the >=2-vote attestation
    assert _gender(index, "δοκόν") == "fem"
    assert _gender(index, "δοκός") == "fem"
    assert _gender(index, "ἄρκτος") == "fem"  # AGDT-only fix (not on the curated list)
    # genuine masculine kept
    assert _gender(index, "λόγος") == "masc"
    # structural -μα neuter filled where the article said nothing
    assert _gender(index, "πρᾶγμα") == "neut"
    assert _gender(index, "πράγματος") == "neut"
    # single-vote attestation cannot override; the curated backstop still corrects it
    assert _gender(index, "κιβωτός") == "fem"
    # single-vote attestation, not curated -> the article masc stands (no spurious flip)
    assert _gender(index, "φύλαξ") == "masc"
    # adjective gender comes straight from the UniMorph tag
    assert _gender(index, "καλός") == "masc"


def test_build_index_default_uses_guards_but_not_attestation() -> None:
    # with no attested map, AGDT-only corrections do not fire, but the curated and structural
    # guards still do -- so ἄρκτος stays at its (wrong) article masc while δοκός/κιβωτός/πρᾶγμα fix
    index = B.build_index(_ROWS)
    assert _gender(index, "ἄρκτος") == "masc"  # needs AGDT to fix; unchanged from article
    assert _gender(index, "δοκός") == "fem"    # curated backstop, no AGDT needed
    assert _gender(index, "κιβωτός") == "fem"  # curated backstop, no AGDT needed
    assert _gender(index, "πρᾶγμα") == "neut"  # structural, no AGDT needed
    assert _gender(index, "λόγος") == "masc"


def test_build_index_form_keys_stable_and_shape() -> None:
    index = B.build_index(_ROWS, attested=_ATTESTED)
    # every analysis record keeps the AGDT shape
    for entries in index.values():
        for a in entries:
            assert set(a) <= {"lemma", "pos", "case", "number", "gender"}
            assert {"lemma", "pos", "case", "number"} <= set(a)
    # deterministic: a second build is identical
    assert B.build_index(_ROWS, attested=_ATTESTED) == index
