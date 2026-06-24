"""Inflection synthesis (inverse lemmatizer) — built offline from the AGDT fixture.

Same policy as the treebank tests: a local ``*.tb.xml`` fixture is parsed into the lexicon
and inverted; no network. Every test restores the default (inflector-off) state afterward.
"""

from __future__ import annotations

import pathlib

import pytest

from aegean import greek
from aegean.greek.inflect import InflectorNotLoadedError, disable_inflector
from aegean.greek.treebank import build_lexicon

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "agdt"


@pytest.fixture(autouse=True)
def _restore_default() -> None:
    yield
    disable_inflector()


def _activate(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    build_lexicon(source_dir=FIXTURE_DIR, force=True)
    greek.use_inflector(build=False)


def test_inflect_noun(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    # λόγον is attested as the masc acc sg of λόγος (postag n-s---ma-)
    assert greek.inflect("λόγος", case="acc", number="sg") == ("λόγον",)


def test_inflect_verb_by_features(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    assert greek.inflect("λέγω", person="1", number="sg", tense="aor") == ("εἶπον",)
    assert greek.inflect("μένω", person="3", number="sg", tense="pres") == ("μένει",)


def test_inflect_partial_spec_dedupes_form(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _activate(tmp_path, monkeypatch)
    # εἶπον is attested as both 1sg and 3pl aorist; an aorist-only query returns it once
    assert greek.inflect("λέγω", tense="aor") == ("εἶπον",)


def test_inflect_homonym_lemma_number_stripped(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _activate(tmp_path, monkeypatch)
    # the fixture lemma is μένω1; the cleaned key μένω resolves it
    assert "μένει" in greek.inflect("μένω", tense="pres")


def test_paradigm_lists_all_cells(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _activate(tmp_path, monkeypatch)
    para = greek.paradigm("λέγω")
    assert "εἶπον" in {form for _feats, form in para}
    persons = {feats.get("person") for feats, form in para if form == "εἶπον"}
    assert {"1", "3"} <= persons  # both the 1sg and 3pl aorist cells survive


def test_unattested_returns_empty(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _activate(tmp_path, monkeypatch)
    assert greek.inflect("λόγος", case="dat", number="du") == ()  # unattested cell
    assert greek.paradigm("ανυπαρκτον") == ()                      # unattested lemma


def test_unknown_feature_raises(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _activate(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="unknown inflection feature"):
        greek.inflect("λόγος", kase="acc")


def test_requires_use_inflector() -> None:
    disable_inflector()
    with pytest.raises(InflectorNotLoadedError):
        greek.inflect("λόγος", case="gen")
