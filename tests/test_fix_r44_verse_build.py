"""R44 verse-fold build regression tests.

Three fixes to the verse dependency fold build:

  * FIX 1 (``training/agdt_ud_deps.convert_tree``): a *leaf* ``APOS`` node (an appositive
    attached straight to its antecedent) converts to ``appos`` — never ``cc`` (which UD
    reserves for coordinating-conjunction words). A *leaf* ``COORD`` conjunction stays
    ``cc``. The ``_AP`` / ``_CO`` restructure branches are byte-identical to before.
  * FIX 2 (``scripts/build_verse_fold.TRACKS``): the fold is tragedy-only. The annotated
    Maximus material is the prose paraphrase (the lines do not scan), so it is not built;
    Maximus is retained only as a forbidden training work.
  * FIX 3 (``scripts/build_verse_fold`` lemma repair): malformed UNESP gold lemmas — Latin
    homoglyph vowels, and LSJ citation-form tails — are repaired to clean Greek-script
    headwords, and the build validates every emitted lemma.

Each test verifies the actual converted/cleaned OUTPUT, not merely that the call runs.
"""

from __future__ import annotations

import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "training"))
import build_verse_fold as bvf  # noqa: E402
from agdt_ud_deps import convert_tree  # noqa: E402


def _w(wid: int, head: int, rel: str, *, xpos: str = "n-s---mn-",
       form: str = "x", lemma: str = "x") -> dict:
    return {"id": str(wid), "head": str(head), "relation": rel, "xpos": xpos,
            "form": form, "lemma": lemma}


# --- FIX 1: leaf APOS -> appos, leaf COORD -> cc ----------------------------------


def test_leaf_apos_noun_maps_to_appos() -> None:
    # a bare appositive noun attached to its antecedent (the dominant UNESP style)
    words = [_w(1, 0, "PRED", xpos="v1spia---"), _w(2, 1, "APOS")]
    assert convert_tree(words)[1] == (1, "appos")


def test_leaf_coord_conjunction_stays_cc() -> None:
    words = [_w(1, 0, "PRED", xpos="v1spia---"),
             _w(2, 1, "COORD", xpos="c--------", form="καί", lemma="καί")]
    assert convert_tree(words)[1] == (1, "cc")


def test_ap_restructure_branch_byte_identical() -> None:
    # an APOS coordinator with two _AP members + a shared punct operator: the restructure
    # branch (untouched by FIX 1) must produce exactly the pre-fix labels.
    ap = [
        _w(1, 0, "PRED", xpos="v1saia---", form="εἶδον", lemma="ὁράω"),
        _w(2, 4, "OBJ_AP", xpos="n-s---ma-", form="ἄνδρα", lemma="ἀνήρ"),
        _w(3, 4, "AuxX", xpos="u--------", form=",", lemma="punc1"),
        _w(4, 1, "APOS", xpos="n-s---ma-", form="βασιλέα", lemma="βασιλεύς"),
        _w(5, 4, "OBJ_AP", xpos="n-s---ma-", form="Πρίαμον", lemma="Πρίαμος"),
    ]
    assert convert_tree(ap) == [
        (0, "root"), (1, "obj"), (4, "punct"), (2, "punct"), (2, "appos"),
    ]


def test_co_restructure_branch_byte_identical() -> None:
    co = [
        _w(1, 0, "PRED", xpos="v1saia---", form="εἶδον", lemma="ὁράω"),
        _w(2, 4, "OBJ_CO", xpos="n-s---ma-", form="ἄνδρα", lemma="ἀνήρ"),
        _w(3, 4, "AuxY", xpos="c--------", form="καί", lemma="καί"),
        _w(4, 1, "COORD", xpos="c--------", form="καί", lemma="καί"),
        _w(5, 4, "OBJ_CO", xpos="n-s---fa-", form="γυναῖκα", lemma="γυνή"),
    ]
    assert convert_tree(co) == [
        (0, "root"), (1, "obj"), (2, "advmod"), (2, "cc"), (2, "conj"),
    ]


# --- FIX 2: tragedy-only; Maximus retained only as a forbidden work ----------------


def test_fold_is_tragedy_only() -> None:
    assert set(bvf.TRACKS) == {"tragedy"}


def test_maximus_still_fails_disjointness() -> None:
    # dropped from the fold, but a training set containing it must still fail the build
    with pytest.raises(SystemExit):
        bvf.check_disjointness({"maximus-astrol-1-4.xml"})
    with pytest.raises(SystemExit):
        bvf.check_disjointness({"tlg1385.tlg001.perseus-grc1.tb.xml"})
    # ...and Bacchae (the tragedy source) still fails too
    with pytest.raises(SystemExit):
        bvf.check_disjointness({"tlg0006.tlg017.perseus-grc2.tb.xml"})


def test_disjointness_records_both_works_and_medea() -> None:
    rec = bvf.check_disjointness(
        {"pedalion:euripides_medea.xml", "tlg0003.tlg001.perseus-grc1.tb.xml"}
    )
    assert rec["tragedy"]["forbidden_matches"] == []
    assert rec["tragedy"]["same_author_in_training"] == ["pedalion:euripides_medea.xml"]
    assert rec["hexameter"]["forbidden_matches"] == []


# --- FIX 3: gold lemma repair -----------------------------------------------------


def test_clean_verse_lemma_maps_latin_homoglyphs() -> None:
    assert bvf.clean_verse_lemma("καí") == "καί"      # Latin í (U+00ED) -> Greek ί (U+03AF)
    assert bvf.clean_verse_lemma("ἀπó") == "ἀπό"      # Latin ó (U+00F3) -> Greek ό (U+03CC)
    out = bvf.clean_verse_lemma("λεíπω")
    assert out == "λείπω"
    # no Latin codepoint survives — every non-combining char is Greek
    assert all(unicodedata.combining(c) or unicodedata.name(c).startswith("GREEK")
               for c in out)


def test_clean_verse_lemma_truncates_citation_tails() -> None:
    assert bvf.clean_verse_lemma("νεβρίς, ὶδος") == "νεβρίς"
    assert bvf.clean_verse_lemma("ἐπιχώριος , α, ον,") == "ἐπιχώριος"  # space-comma
    assert bvf.clean_verse_lemma("χλοήρης , ες") == "χλοήρης"
    assert bvf.clean_verse_lemma("ἐνδυτόν, τό") == "ἐνδυτόν"           # trailing article
    assert bvf.clean_verse_lemma("εὔιος, ‑α, ‑ον") == "εὔιος"         # non-breaking hyphens
    assert bvf.clean_verse_lemma("ἐνθάδε (τὰ ἐνθάδε)") == "ἐνθάδε"     # parenthetical gloss


def test_clean_verse_lemma_leaves_clean_lemmas_unchanged() -> None:
    for good in ("ἥκω", "ὅς", "Ζεύς", "λοχεύω", "δʼ"):  # incl. an elided apostrophe form
        assert bvf.clean_verse_lemma(good) == good


def test_is_clean_headword_accepts_greek_rejects_defects() -> None:
    assert bvf.is_clean_headword("καί")
    assert bvf.is_clean_headword("δʼ")           # apostrophe-final elided form allowed
    assert not bvf.is_clean_headword("καí")       # Latin homoglyph
    assert not bvf.is_clean_headword("εὔιος, ον")  # citation tail
    assert not bvf.is_clean_headword("ἐνθάδε (τὰ ἐνθάδε)")
    assert not bvf.is_clean_headword("")
    assert not bvf.is_clean_headword("ʼ")          # apostrophe only, no Greek letter


def test_assert_clean_lemmas_passes_clean_and_punct() -> None:
    clean = "# sent_id = x\n1\tκαί\tκαί\tCCONJ\tc--------\t_\t0\troot\t_\t_\n"
    bvf.assert_clean_lemmas(clean)  # no raise
    # a punctuation token's lemma is the punct char, which is not a Greek headword: allowed
    punct = "1\t,\t,\tPUNCT\tu--------\t_\t2\tpunct\t_\t_\n"
    bvf.assert_clean_lemmas(punct)


def test_assert_clean_lemmas_fails_on_surviving_defect() -> None:
    bad_latin = "1\tκ\tκαí\tCCONJ\tc--------\t_\t0\troot\t_\t_\n"
    with pytest.raises(SystemExit):
        bvf.assert_clean_lemmas(bad_latin)
    bad_tail = "1\tεὔια\tεὔιος, ον\tNOUN\tn-p---na-\t_\t0\troot\t_\t_\n"
    with pytest.raises(SystemExit):
        bvf.assert_clean_lemmas(bad_tail)


# --- FIX 1 + FIX 3 end-to-end through the real build functions ---------------------


def test_build_pipeline_emits_appos_and_clean_lemma() -> None:
    # a synthetic tragedy sentence: a leaf APOS proper noun whose gold lemma carries an LSJ
    # citation tail. Run the exact per-sentence build path (agdt_reg_words -> lemma repair ->
    # sentence_to_conllu -> validation) and verify the emitted row.
    xml = (
        '<sentence id="1">'
        '<word id="1" form="παῖς" lemma="παῖς" postag="n-s---mn-" relation="PRED" head="0"/>'
        '<word id="2" form="Διόνυσος" lemma="Διόνυσος, ου, ὁ" postag="n-s---mn-" '
        'relation="APOS" head="1"/>'
        "</sentence>"
    )
    words = bvf.agdt_reg_words(ET.fromstring(xml))
    assert bvf.sentence_status(words) == "ok"
    for w in words:  # mirror build()'s in-place repair
        w["lemma_reg"] = bvf.clean_verse_lemma(w["lemma_reg"])
    block, _forms = bvf.sentence_to_conllu("verse:tragedy:t@1", words)
    rows = [ln.split("\t") for ln in block.splitlines() if ln and not ln.startswith("#")]
    got = {int(r[0]): (r[2], r[7]) for r in rows}  # id -> (lemma, deprel)
    assert got[2] == ("Διόνυσος", "appos")  # leaf APOS -> appos; citation tail stripped
    bvf.assert_clean_lemmas(block)  # every emitted lemma is a clean headword
