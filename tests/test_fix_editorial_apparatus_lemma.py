"""Leiden editorial apparatus must not corrupt neural lemma composition.

A form carrying the combining underdot (U+0323) is a *damaged but legible* reading:
the mark is the editor's annotation about the papyrus or stone, not part of the word.
Every other lookup in the package already drops it before probing a table; Greek
neural lemma composition did not, and because the shipped lookup tables contain no
underdotted keys at all, every such form missed the lookup and fell through to an
edit tree applied to a character sequence the tree was never learned on. That
fabricated non-word lemmas on exactly the corpora where the mark occurs (documentary
papyri and inscriptions).
"""

from __future__ import annotations

import unicodedata

import pytest


from aegean.greek import neural_preprocessing as prep


@pytest.fixture(autouse=True, scope="module")
def _restore_backends():
    """Leave the process as this module found it.

    Backend activation is global session state, so a module that turns one on and walks
    away changes what unrelated tests see -- which under ``pytest -n`` means a different
    worker, and a failure with no visible cause. Everything this file activates is turned
    off again here."""
    yield
    from aegean import greek

    for name in (
        "disable_neural_pipeline",
        "disable_treebank",
        "disable_lsj",
        "disable_lexicon",
        "disable_paradigms",
        "disable_tagger",
        "disable_parser",
        "disable_lemmatizer",
        "disable_neural_lemmatizer",
        "disable_calibration",
    ):
        try:
            getattr(greek, name)()
        except Exception:  # pragma: no cover - a backend that was never active
            pass


UNDERDOT = "̣"


def test_strip_editorial_apparatus_removes_only_the_underdot() -> None:
    assert prep._strip_editorial_apparatus("μητ̣ρ̣ὸς") == "μητρὸς"
    assert prep._strip_editorial_apparatus("κ̣αρπῶν") == "καρπῶν"
    assert prep._strip_editorial_apparatus("Ἰ̣ω̣άνν̣ῃ") == "Ἰωάννῃ"


def test_strip_editorial_apparatus_preserves_real_diacritics() -> None:
    # Accents, breathings, iota subscript and diaeresis are part of the word and must
    # survive; only the apparatus mark is editorial.
    for word in ("ἀβαρὲς", "μήτηρ", "τῷ", "προϊών", "ᾅδης", "Ἑρμουπολίτης"):
        assert prep._strip_editorial_apparatus(word) == word


def test_strip_editorial_apparatus_is_idempotent_and_nfc() -> None:
    once = prep._strip_editorial_apparatus("μητ̣ρ̣ὸς")
    assert prep._strip_editorial_apparatus(once) == once
    assert unicodedata.normalize("NFC", once) == once


def test_underdotted_form_now_reaches_the_lookup_table() -> None:
    # The defect: the lookup is keyed on apparatus-free training forms, so an
    # underdotted form could never match and always fell through to an edit tree.
    lookup_form = {"μητρός": "μήτηρ"}
    value, resolved, path = prep.compose_lemma_detail(
        "μητ̣ρ̣ός", "NOUN", -1,
        lookup_form_upos={}, lookup_form=lookup_form, lookup_lower={},
    )
    assert (value, resolved, path) == ("μήτηρ", True, "lookup_form")


def test_exact_key_still_wins_over_the_apparatus_free_probe() -> None:
    # If a table ever does carry an underdotted key, it must take precedence.
    value, _resolved, path = prep.compose_lemma_detail(
        "μητ̣ρ̣ός", "NOUN", -1,
        lookup_form_upos={},
        lookup_form={"μητ̣ρ̣ός": "EXACT", "μητρός": "STRIPPED"},
        lookup_lower={},
    )
    assert (value, path) == ("EXACT", "lookup_form")


def test_form_upos_probe_also_falls_back(monkeypatch) -> None:
    value, _resolved, path = prep.compose_lemma_detail(
        "μητ̣ρ̣ός", "NOUN", -1,
        lookup_form_upos={"μητρός|NOUN": "μήτηρ"}, lookup_form={}, lookup_lower={},
    )
    assert (value, path) == ("μήτηρ", "lookup_form_upos")


def test_lower_fallback_also_uses_the_apparatus_free_probe() -> None:
    value, _resolved, path = prep.compose_lemma_detail(
        "Μητ̣ρ̣ός", "NOUN", -1,
        lookup_form_upos={}, lookup_form={}, lookup_lower={"μητρός": "μήτηρ"},
    )
    assert (value, path) == ("μήτηρ", "lookup_lower_fallback")


def test_edit_tree_runs_on_the_apparatus_free_form() -> None:
    # The tree encodes prefix/suffix LENGTHS; an underdot in the middle shifts those
    # offsets and grafts stray characters into the result.
    seen: list[str] = []

    def apply_edit_script(_tree, word):
        seen.append(word)
        return word[:-2] + "ος"

    value, resolved, path = prep.compose_lemma_detail(
        "κ̣αρπῶν", "NOUN", 0,
        lookup_form_upos={}, lookup_form={}, lookup_lower={},
        trees=[["keep"]], apply_edit_script=apply_edit_script,
    )
    assert seen == ["καρπῶν"], "the edit tree must not see the apparatus mark"
    assert UNDERDOT not in unicodedata.normalize("NFD", value)
    assert (resolved, path) == (True, "edit_script")


def test_identity_fallthrough_never_returns_an_apparatus_bearing_lemma() -> None:
    value, resolved, path = prep.compose_lemma_detail(
        "κ̣αρπῶν", "NOUN", -1,
        lookup_form_upos={}, lookup_form={}, lookup_lower={},
    )
    assert value == "καρπῶν"
    assert UNDERDOT not in unicodedata.normalize("NFD", value)
    assert (resolved, path) == (False, "identity_fallback")


def test_clean_forms_are_completely_unaffected() -> None:
    # The whole change must be inert for text without an apparatus mark, which is
    # every literary corpus and every published literary benchmark row.
    lookup_form = {"λόγου": "λόγος"}
    for mode in ("canonical", "lookup-first", "neural-only", "neural-first", "unseen-neural"):
        got = prep.compose_lemma_detail(
            "λόγου", "NOUN", -1,
            lookup_form_upos={}, lookup_form=lookup_form, lookup_lower={}, mode=mode,
        )
        expected_value = "λόγος" if mode != "neural-only" else "λόγου"
        assert got[0] == expected_value, mode


@pytest.mark.parametrize("mode", ["canonical", "lookup-first", "neural-first", "unseen-neural"])
def test_apparatus_fallback_applies_in_every_lookup_bearing_mode(mode: str) -> None:
    value, _resolved, _path = prep.compose_lemma_detail(
        "μητ̣ρ̣ός", "NOUN", -1,
        lookup_form_upos={}, lookup_form={"μητρός": "μήτηρ"}, lookup_lower={}, mode=mode,
    )
    assert value == "μήτηρ", mode


def test_shipped_v3_lookup_tables_contain_no_apparatus_keys() -> None:
    """The premise of the fix, asserted against the REAL shipped artifact.

    If a future model were trained on apparatus-bearing forms this test fails and the
    fallback ordering above must be revisited.
    """
    pytest.importorskip("onnxruntime")
    from aegean import greek
    from aegean.greek import joint

    greek.use_neural_pipeline()
    model = joint.active()
    if model is None:  # pragma: no cover - neural extra present but model unavailable
        pytest.skip("joint model unavailable")
    for table in ("lookup_form", "lookup_form_upos", "lookup_lower"):
        keys = getattr(model, table)
        offenders = [k for k in keys if UNDERDOT in unicodedata.normalize("NFD", k)]
        assert not offenders, f"{table} unexpectedly carries apparatus keys: {offenders[:5]}"
