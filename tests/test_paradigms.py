"""UniMorph paradigm backend: cleaning, cascade priority, features, and failure modes.

Three dimensions (the CONTRIBUTING rule for a feature that reads external input and is a step
in a user journey):

* **correctness** — the build-script cleaner strips the definite article and the metrical
  breve/macron length marks, splits variant cells, expands parenthesised optionals, and maps
  every UniMorph feature to the project's convention (matching ``treebank.decode_postag``);
  the resulting lexicon resolves the irregular / third-declension / heteroclite cells
  (γυναικός, πατράσι, ὕδατος, κόλακος) to the right lemma AND features, ranked ABOVE the
  ending rules and BELOW the treebank/seed tiers;
* **adversarial** — a malformed index file (corrupt gzip, non-object JSON, wrong record
  shape, missing) raises a clean `DataNotAvailableError`, never a raw traceback;
* **graceful** — with the backend off (the default) the cascade is byte-unchanged;
  use/disable round-trips and never touches the network.

No network and no optional deps: ``use_paradigms(path=...)`` loads a local gzip fixture built
in-test with the real build-script cleaner, so every test runs under a bare ``pytest`` offline.
"""

from __future__ import annotations

import gzip
import json
import sys
import unicodedata
from pathlib import Path

import pytest

from aegean import greek
from aegean.data import DataNotAvailableError
from aegean.greek import paradigms, treebank
from aegean.greek.lemmatize import LemmaSource, lemmatize_sourced, needs_review

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_paradigm_table as bpt  # noqa: E402

# Real UniMorph grc rows (verbatim shape: lemma, form-with-article-and-length-marks, features).
_ROWS: list[tuple[str, str, str]] = [
    ("γυνή", "ἡ γῠνή", "N;NOM;SG"),
    ("γυνή", "τῆς γῠναικός", "N;GEN;SG"),
    ("γυνή", "ταῖς γῠναιξί(ν) / γῠναίκεσσι(ν)", "N;DAT;PL"),
    ("γυνή", "τὴν γῠναῖκᾰ / γῠνήν", "N;ACC;SG"),
    ("γυνή", "γύναι / γῠνή", "N;VOC;SG"),
    ("πατήρ", "ὁ πᾰτήρ", "N;NOM;SG"),
    ("πατήρ", "τοῖς πᾰτράσῐ", "N;DAT;PL"),
    ("ὕδωρ", "τὸ ῠ̔́δωρ", "N;NOM;SG"),
    ("ὕδωρ", "τοῦ ῠ̔́δᾰτος", "N;GEN;SG"),
    ("κόλαξ", "ὁ κόλᾰξ", "N;NOM;SG"),
    ("κόλαξ", "τοῦ κόλᾰκος", "N;GEN;SG"),
    ("λόγος", "τοῦ λόγου", "N;GEN;SG"),  # a regular form the seed/rule already handle
    ("ἐνώπιος", "τὸ ἐνώπιον", "ADJ;ACC;SG;NEUT"),  # collides with the preposition ἐνώπιον
    ("δίκαιος", "τῶν δῐκαίων", "ADJ;GEN;PL;MASC"),  # an adjective carries its tag gender
]


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


@pytest.fixture
def index_path(tmp_path: Path) -> Path:
    """A small paradigm index, built through the real cleaner and written as ``.json.gz``.

    A sentinel entry for ``πόλει`` (a form the bundled seed already maps to πόλις) is injected
    so a test can prove the seed tier out-ranks the paradigm tier."""
    index = bpt.build_index(_ROWS)
    index["πόλει"] = [{"lemma": "ΞΞ_PARADIGM", "pos": "NOUN", "case": "dat", "number": "sg"}]
    p = tmp_path / "grc-paradigms.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    return p


@pytest.fixture(autouse=True)
def _no_backend_leak():
    """Every test starts and ends with all lemmatizer backends off (global state)."""
    paradigms.disable_paradigms()
    treebank.disable_treebank()
    yield
    paradigms.disable_paradigms()
    treebank.disable_treebank()


# ── build-script cleaning: articles, length marks, variants, parens, features ──────────────
def test_strip_length_drops_only_the_metrical_marks() -> None:
    # breve (U+0306) and macron (U+0304) go; the acute (U+0301) and breathing stay.
    out = bpt.strip_length("εἰσᾰγωγᾱ́")
    decomp = unicodedata.normalize("NFD", out)
    assert "̆" not in decomp and "̄" not in decomp  # no breve/macron
    assert "́" in decomp                              # the acute survived
    assert out == _nfc("εἰσαγωγά")


def test_parse_form_field_strips_article_and_harvests_gender() -> None:
    keys, genders = bpt.parse_form_field("ὁ βοηθός")
    assert keys == ["βοηθός"]                 # the masculine article ὁ is stripped
    assert genders == {"masc"}                # …and its gender harvested


def test_parse_form_field_variants_parens_and_length() -> None:
    # article (fem) + two variants split on '/' + parenthesised optional-nu, length-stripped.
    keys, genders = bpt.parse_form_field("ταῖς γῠναιξί(ν) / γῠναίκεσσι(ν)")
    assert genders == {"fem"}
    assert set(keys) == {"γυναιξί", "γυναιξίν", "γυναίκεσσι", "γυναίκεσσιν"}
    assert all("̆" not in unicodedata.normalize("NFD", k) for k in keys)


def test_parse_form_field_comma_variants_without_article() -> None:
    # an article-less epic cell with comma-separated variants (σπέος, σπεῖος).
    keys, genders = bpt.parse_form_field("σπέος, σπεῖος")
    assert set(keys) == {"σπέος", "σπεῖος"}
    assert genders == set()


def test_parse_form_field_common_gender_article_votes_both() -> None:
    # "ὁ, ἡ ἔλαφος" (a common-gender noun): both article genders are seen for the cell.
    keys, genders = bpt.parse_form_field("ὁ, ἡ ἔλᾰφος")
    assert keys == ["ἔλαφος"]
    assert genders == {"masc", "fem"}


def test_parse_features_maps_to_project_convention() -> None:
    assert bpt.parse_features("N;GEN;SG") == ("NOUN", "gen", "sg", None)
    assert bpt.parse_features("N;VOC;DU") == ("NOUN", "voc", "du", None)
    assert bpt.parse_features("ADJ;DAT;PL;FEM") == ("ADJ", "dat", "pl", "fem")


def test_parse_features_rejects_unmapped_tags() -> None:
    with pytest.raises(ValueError):
        bpt.parse_features("V;IND;PRS;ACT;3;SG")  # verbs are not in this nominal corpus
    with pytest.raises(ValueError):
        bpt.parse_features("N;ABL;SG")            # ablative is not a Greek case here


def test_build_index_derives_noun_gender_from_the_article() -> None:
    index = bpt.build_index(_ROWS)
    # κόλαξ is articled ὁ/τοῦ (masc); its constant gender is propagated to every cell.
    assert index["κόλαξ"][0]["gender"] == "masc"
    assert index["κόλακος"][0]["gender"] == "masc"
    # ὕδωρ is τό/τοῦ → neuter; γυνή is ἡ/τῆς/τήν → feminine.
    assert index["ὕδατος"][0]["gender"] == "neut"
    assert index["γυναικός"][0]["gender"] == "fem"


def test_build_index_records_have_the_agdt_shape() -> None:
    index = bpt.build_index(_ROWS)
    allowed = {"lemma", "pos", "case", "number", "gender"}
    for entries in index.values():
        for e in entries:
            assert set(e) <= allowed and {"lemma", "pos", "case", "number"} <= set(e)


# ── the lexicon resolves irregular / third-declension cells with the right features ────────
@pytest.mark.parametrize(
    "form,lemma,case,number,gender",
    [
        ("γυναικός", "γυνή", "gen", "sg", "fem"),      # Smyth §275: γυναικός
        ("γυναιξί", "γυνή", "dat", "pl", "fem"),       # γυναιξί(ν)
        ("γυναιξίν", "γυνή", "dat", "pl", "fem"),      # the (ν) expansion
        ("πατράσι", "πατήρ", "dat", "pl", "masc"),     # syncopated πατρ- + ασι
        ("ὕδατος", "ὕδωρ", "gen", "sg", "neut"),       # Smyth §285: heteroclite ὕδωρ
        ("κόλακος", "κόλαξ", "gen", "sg", "masc"),     # guttural stem
    ],
)
def test_paradigm_analyze_gives_correct_lemma_and_features(
    index_path: Path, form: str, lemma: str, case: str, number: str, gender: str
) -> None:
    greek.use_paradigms(path=index_path)
    analyses = greek.analyze(form)
    assert analyses, form
    a = analyses[0]
    assert (_nfc(a.lemma), a.case, a.number, a.gender) == (lemma, case, number, gender)
    assert a.lemma_certain is True


def test_length_marked_source_resolves_from_clean_query(index_path: Path) -> None:
    """The source form ``ῠ̔́δᾰτος`` (breve marks) is indexed under the clean ``ὕδατος``, so a
    real-text query with no length marks resolves it."""
    greek.use_paradigms(path=index_path)
    assert _nfc(greek.lemmatize("ὕδατος")) == "ὕδωρ"


def test_running_text_grave_folds_to_the_citation_acute(index_path: Path) -> None:
    greek.use_paradigms(path=index_path)
    # γυναικός is oxytone; a running-text grave (γυναικὸς) must still find the acute key.
    assert _nfc(greek.lemmatize("γυναικὸς")) == "γυνή"


# ── cascade priority: paradigm fills the 3rd-declension gap the rules cannot, below them ────
def test_paradigm_recovers_a_third_declension_form_the_rules_cannot(index_path: Path) -> None:
    # Without the backend, γυναικός is an honest third-declension miss for the rule layer.
    assert lemmatize_sourced("γυναικός") == ("γυναικός", LemmaSource.UNRESOLVED)
    greek.use_paradigms(path=index_path)
    lemma, source = lemmatize_sourced("γυναικός")
    assert _nfc(lemma) == "γυνή"
    assert source is LemmaSource.PARADIGM       # its own grounded, curated evidence class
    assert needs_review(source) is False


def test_regular_forms_are_recovered_by_the_rule_before_the_paradigm(index_path: Path) -> None:
    """The ending rule is consulted BEFORE the paradigm table; a regular form the rule
    recovers is reported RULE, and the paradigm is never reached for it."""
    greek.use_paradigms(path=index_path)
    lemma, source = lemmatize_sourced("καρπόν")   # a regular -ον noun the rule handles
    assert _nfc(lemma) == "καρπός"
    assert source is LemmaSource.RULE


def test_seed_tier_outranks_the_paradigm(index_path: Path) -> None:
    """πόλει is in the bundled seed (→ πόλις); the fixture maps it to a sentinel lemma. The
    seed must win, proving the paradigm is consulted only after the seed misses."""
    greek.use_paradigms(path=index_path)
    lemma, source = lemmatize_sourced("πόλει")
    assert _nfc(lemma) == "πόλις"
    assert source is LemmaSource.SEED
    assert lemma != "ΞΞ_PARADIGM"


def test_treebank_tier_outranks_the_paradigm(index_path: Path, monkeypatch) -> None:
    """An active treebank (ATTESTED) is consulted before the paradigm: its lemma wins."""

    class _StubTreebank:
        def lemmatize(self, w: str) -> str | None:
            return "ΤΒ_ΛΗΜΜΑ" if w == "γυναικός" else None

        def analyze(self, w: str):
            return ()

    greek.use_paradigms(path=index_path)
    monkeypatch.setattr(treebank, "_ACTIVE", _StubTreebank())
    lemma, source = lemmatize_sourced("γυναικός")
    assert lemma == "ΤΒ_ΛΗΜΜΑ"
    assert source is LemmaSource.ATTESTED


def test_paradigm_does_not_shadow_a_closed_class_word(index_path: Path) -> None:
    """The fixture has ἐνώπιον (acc of the adjective ἐνώπιος), but ἐνώπιον is also the
    preposition pyaegean knows as indeclinable — the guard blocks the paradigm from claiming
    it, so it is never fabricated into ἐνώπιος."""
    greek.use_paradigms(path=index_path)
    lemma, _source = lemmatize_sourced("ἐνώπιον")
    assert _nfc(lemma) != "ἐνώπιος"


# ── graceful: default-off, use/disable round-trip ─────────────────────────────────────────
def test_default_is_off_and_offline(index_path: Path) -> None:
    assert paradigms.active() is None
    assert lemmatize_sourced("γυναικός")[1] is LemmaSource.UNRESOLVED
    lex = greek.use_paradigms(path=index_path)
    assert paradigms.active() is lex and len(lex) > 0
    greek.disable_paradigms()
    assert paradigms.active() is None
    assert lemmatize_sourced("γυναικός")[1] is LemmaSource.UNRESOLVED


# ── adversarial: malformed / missing index → clean error, never a raw traceback ───────────
def test_missing_index_is_a_clean_error(tmp_path: Path) -> None:
    with pytest.raises(DataNotAvailableError):
        paradigms.ParadigmLexicon.load(tmp_path / "does-not-exist.json.gz")


def test_corrupt_gzip_is_a_clean_error(tmp_path: Path) -> None:
    bad = tmp_path / "corrupt.json.gz"
    bad.write_bytes(b"this is not gzip")
    with pytest.raises(DataNotAvailableError):
        paradigms.ParadigmLexicon.load(bad)


def test_non_object_json_is_a_clean_error(tmp_path: Path) -> None:
    bad = tmp_path / "list.json.gz"
    with gzip.open(bad, "wt", encoding="utf-8") as f:
        json.dump([1, 2, 3], f)   # a JSON array, not the expected object
    with pytest.raises(DataNotAvailableError):
        paradigms.ParadigmLexicon.load(bad)


def test_wrong_record_shape_is_a_clean_error(tmp_path: Path) -> None:
    bad = tmp_path / "shape.json.gz"
    with gzip.open(bad, "wt", encoding="utf-8") as f:
        json.dump({"γυναικός": "γυνή"}, f)   # value must be a LIST of analysis dicts
    with pytest.raises(DataNotAvailableError):
        paradigms.ParadigmLexicon.load(bad)


def test_use_paradigms_without_url_is_a_clean_error(monkeypatch, tmp_path: Path) -> None:
    """With no cached index and no pinned URL (fetch returns False), the error is clean and
    names the escape hatches — never a raw fetch traceback."""
    monkeypatch.setattr(paradigms, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(paradigms, "fetch_prebuilt", lambda *a, **k: False)
    with pytest.raises(DataNotAvailableError):
        paradigms.use_paradigms()
