"""Guards on the opt-in UniMorph paradigm tier (r33).

With ``use_paradigms()`` active, the paradigm table could return arbitrary first-entry
picks as grounded lemmas that need no review, so a wrong reading displaced the correct one:

* a 3rd-declension nominal dative homograph shadowed the dominant verb the ending rule
  resolves (``ἔχει`` -> ``ἔχις`` instead of the verb ``ἔχει`` -> ``ἔχω``);
* an intra-table multi-lemma form returned ``entries[0]`` (``βασιλεία`` -> ``βασίλεια``,
  ``φωτός`` -> ``φώς`` vs ``φῶς`` which share the genitive);
* a capitalized proper name was served the downcased common-noun lemma (``Πέτρος`` ->
  ``πέτρος`` 'stone').

The fix: consult the paradigm table only after the guarded ending rules fail to recover
(ordering guard), skip a capitalized surface (the table is lowercase common vocabulary),
skip any form the table maps to more than one distinct lemma, and report a genuine hit under
its own ``PARADIGM`` evidence class (no longer ``SEED``). A grounded 3rd-declension form the
rules cannot touch (``γυναικός`` -> ``γυνή``) still resolves.

Offline and no optional deps: the paradigm index is a small in-test gzip fixture whose
entries reproduce the traps, loaded via ``use_paradigms(path=...)`` with no network.
"""

from __future__ import annotations

import gzip
import json
import unicodedata
from pathlib import Path

import pytest

from aegean import greek
from aegean.greek import paradigms, treebank
from aegean.greek.explain import _NOTES, explain_pipeline
from aegean.greek.lemmatize import (
    LemmaSource,
    _is_capitalized,
    lemmatize_sourced,
    needs_review,
)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# A form -> [analysis, ...] index whose entries reproduce every trap the guards must catch.
# Keys are the lowercase NFC surface the loader normalizes a query to (paradigms._norm).
_ENTRY = {"pos": "NOUN", "case": "gen", "number": "sg", "gender": "fem"}
_FIXTURE: dict[str, list[dict[str, str]]] = {
    # verb-homograph traps: a nominal dative cell over the dominant verb the rule resolves
    "ἔχει": [{**_ENTRY, "lemma": "ἔχις", "case": "dat", "gender": "masc"}],
    "βάλλει": [{**_ENTRY, "lemma": "βάλλις", "case": "dat"}],
    # intra-table ambiguity: one surface, two distinct lemmas (entries[0] is the WRONG pick)
    "βασιλεία": [
        {**_ENTRY, "lemma": "βασίλεια", "case": "nom", "number": "pl", "gender": "neut"},
        {**_ENTRY, "lemma": "βασιλεία", "case": "nom"},
    ],
    "φωτός": [
        {**_ENTRY, "lemma": "φώς", "gender": "masc"},
        {**_ENTRY, "lemma": "φῶς", "gender": "neut"},
    ],
    # capitalization trap: the table keys the downcased common noun
    "πέτρος": [{**_ENTRY, "lemma": "πέτρος", "case": "nom", "gender": "masc"}],
    # the genuine 3rd-declension win the rules cannot recover (single lemma)
    "γυναικός": [{**_ENTRY, "lemma": "γυνή"}],
    # two cells of ONE lemma: still an unambiguous, grounded hit
    "γυναιξί": [
        {**_ENTRY, "lemma": "γυνή", "case": "dat", "number": "pl"},
        {**_ENTRY, "lemma": "γυνή", "case": "dat", "number": "pl"},
    ],
    # a regular -ον noun the rule recovers; a table entry must NOT pre-empt the rule
    "καρπόν": [{**_ENTRY, "lemma": "ΞΞ_SENTINEL", "case": "acc"}],
}


@pytest.fixture
def index_path(tmp_path: Path) -> Path:
    index = {_nfc(k): v for k, v in _FIXTURE.items()}
    p = tmp_path / "grc-paradigms.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    return p


@pytest.fixture(autouse=True)
def _no_backend_leak():
    """All lemmatizer backends off before and after each test (module-global state)."""
    paradigms.disable_paradigms()
    treebank.disable_treebank()
    yield
    paradigms.disable_paradigms()
    treebank.disable_treebank()


# ── the five probe forms land honest: a correct/rule lemma or an honest miss, never wrong-grounded
@pytest.mark.parametrize("form,rule_lemma", [("ἔχει", "ἔχω"), ("βάλλει", "βάλλω")])
def test_verb_homograph_resolves_by_rule_not_by_paradigm(
    index_path: Path, form: str, rule_lemma: str
) -> None:
    greek.use_paradigms(path=index_path)
    # the table really holds the trap (a nominal dative that ends in -ει)...
    trap = paradigms.active().lemmatize(form)
    assert trap is not None and _nfc(trap) != rule_lemma
    # ...but the guarded ending rule is consulted first and wins.
    lemma, source = lemmatize_sourced(form)
    assert (_nfc(lemma), source) == (rule_lemma, LemmaSource.RULE)
    assert _nfc(lemma) != _nfc(trap)  # the shadowing nominal never surfaces


@pytest.mark.parametrize("form,wrong_pick", [("βασιλεία", "βασίλεια"), ("φωτός", "φώς")])
def test_intra_table_ambiguity_is_an_honest_miss_not_an_arbitrary_pick(
    index_path: Path, form: str, wrong_pick: str
) -> None:
    plex = greek.use_paradigms(path=index_path)
    assert len(plex.lemma_options(form)) == 2  # the table is internally ambiguous here
    lemma, source = lemmatize_sourced(form)
    # no grounded pick: falls through to an honest miss (needs review), never the entries[0] guess
    assert needs_review(source) is True
    assert not (needs_review(source) is False and _nfc(lemma) == wrong_pick)
    assert _nfc(lemma) == _nfc(form)  # the normalized surface is returned unchanged


def test_capitalized_proper_name_is_not_served_the_downcased_common_noun(
    index_path: Path,
) -> None:
    plex = greek.use_paradigms(path=index_path)
    assert plex.lemmatize("Πέτρος") == "πέτρος"  # the table WOULD downcase it...
    lemma, source = lemmatize_sourced("Πέτρος")
    # ...but the capitalization guard blocks it; the surface capitalization is preserved.
    assert needs_review(source) is True
    assert _nfc(lemma) == "Πέτρος"
    assert _nfc(lemma) != "πέτρος"


# ── the genuine third-declension win stays grounded, under its own PARADIGM class ──────────
def test_third_declension_form_is_paradigm_grounded(index_path: Path) -> None:
    # without the backend it is an honest miss the rules cannot recover
    assert lemmatize_sourced("γυναικός") == ("γυναικός", LemmaSource.UNRESOLVED)
    greek.use_paradigms(path=index_path)
    lemma, source = lemmatize_sourced("γυναικός")
    assert (_nfc(lemma), source) == ("γυνή", LemmaSource.PARADIGM)
    assert needs_review(source) is False


def test_multiple_cells_of_one_lemma_stay_grounded(index_path: Path) -> None:
    plex = greek.use_paradigms(path=index_path)
    assert plex.lemma_options("γυναιξί") == frozenset({"γυνή"})  # two cells, one lemma
    lemma, source = lemmatize_sourced("γυναιξί")
    assert (_nfc(lemma), source) == ("γυνή", LemmaSource.PARADIGM)
    assert needs_review(source) is False


def test_rule_recovered_form_is_never_pre_empted_by_a_paradigm_entry(index_path: Path) -> None:
    """The ordering guard: a regular form the rule recovers is RULE even when the table holds
    an entry for it (the sentinel lemma must never surface)."""
    plex = greek.use_paradigms(path=index_path)
    assert plex.lemmatize("καρπόν") == "ΞΞ_SENTINEL"  # the table has a (bogus) entry...
    lemma, source = lemmatize_sourced("καρπόν")
    assert (_nfc(lemma), source) == ("καρπός", LemmaSource.RULE)  # ...the rule still wins


# ── PARADIGM is its own evidence class: SEED no longer covers paradigm hits ────────────────
def test_paradigm_hits_report_paradigm_not_seed(index_path: Path) -> None:
    greek.use_paradigms(path=index_path)
    _lemma, source = lemmatize_sourced("γυναικός")
    assert source is LemmaSource.PARADIGM
    assert source is not LemmaSource.SEED
    # PARADIGM is grounded (like SEED) but a distinct, honestly-named class
    assert needs_review(LemmaSource.PARADIGM) is False
    assert LemmaSource.PARADIGM.value == "paradigm"


def test_seed_still_outranks_and_is_distinct_from_the_paradigm(index_path: Path) -> None:
    """A closed-class seed form is SEED (the seed tier is consulted before the rule and the
    paradigm), proving the two grounded classes do not collapse into one another."""
    greek.use_paradigms(path=index_path)
    assert lemmatize_sourced("δέ")[1] is LemmaSource.SEED
    assert lemmatize_sourced("γυναικός")[1] is LemmaSource.PARADIGM


# ── ParadigmLexicon.lemma_options: the distinct-lemma set backing the ambiguity guard ──────
def test_lemma_options_counts_distinct_lemmas(index_path: Path) -> None:
    plex = paradigms.ParadigmLexicon.load(index_path)
    assert plex.lemma_options("γυναικός") == frozenset({"γυνή"})          # single lemma
    assert plex.lemma_options("γυναιξί") == frozenset({"γυνή"})           # two cells, one lemma
    assert plex.lemma_options("φωτός") == frozenset({"φώς", "φῶς"})       # two distinct lemmas
    assert plex.lemma_options("οὐκ_ἐν_τῷ_πίνακι") == frozenset()          # unknown -> empty


def test_lemma_options_compares_lemmas_under_nfc(tmp_path: Path) -> None:
    """Two entries whose lemmas differ only by NFC vs NFD normalization are ONE distinct
    lemma (so a decomposed duplicate does not spuriously trip the ambiguity guard)."""
    composed = _nfc("ἥρως")
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed  # different byte sequences...
    index = {"ηρωσ_key": [{"lemma": composed, "pos": "NOUN", "case": "nom", "number": "sg"},
                          {"lemma": decomposed, "pos": "NOUN", "case": "nom", "number": "sg"}]}
    p = tmp_path / "grc-paradigms.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    plex = paradigms.ParadigmLexicon.load(p)
    assert plex.lemma_options("ηρωσ_key") == frozenset({composed})  # ...one distinct lemma


# ── the capitalization helper ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "word,expected",
    [
        ("Πέτρος", True), ("Ἰησοῦς", True), ("«Πέτρος", True),  # leading non-letter skipped
        ("πέτρος", False), ("ἔχει", False), ("γυναικός", False),
        ("", False), ("123", False),
    ],
)
def test_is_capitalized(word: str, expected: bool) -> None:
    assert _is_capitalized(word) is expected


# ── explain names the UniMorph paradigm table, not the bundled seed table ──────────────────
def test_explain_names_the_paradigm_table(index_path: Path) -> None:
    greek.use_paradigms(path=index_path)
    exps = explain_pipeline("γυναικός")
    assert len(exps) == 1
    e = exps[0]
    assert (_nfc(e.lemma), e.lemma_source, e.needs_review) == ("γυνή", LemmaSource.PARADIGM, False)
    assert "paradigm table" in e.note.lower()
    assert "seed table" not in e.note.lower()


def test_paradigm_note_registered_and_names_unimorph() -> None:
    note = _NOTES[LemmaSource.PARADIGM]
    assert "UniMorph" in note and "paradigm table" in note


# ── the paradigms-off cascade is unchanged by the restructure ─────────────────────────────
def test_offline_cascade_unchanged_when_paradigms_off() -> None:
    assert paradigms.active() is None
    assert lemmatize_sourced("δέ") == ("δέ", LemmaSource.SEED)          # seed / closed-class
    assert lemmatize_sourced("νόμου") == ("νόμος", LemmaSource.RULE)    # ending rule
    lemma, source = lemmatize_sourced("γυναικός")                       # honest 3rd-decl miss
    assert (lemma, source) == ("γυναικός", LemmaSource.UNRESOLVED)
