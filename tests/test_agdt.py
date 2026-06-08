"""AGDT treebank-derived lemmatizer/morphology (opt-in Greek backend).

Offline: a synthetic fixture treebank is parsed into a lexicon and activated; the
network download path is not exercised in CI (same policy as the lineara-images
fetch). Every test restores the default (treebank-off) state afterward.
"""

from __future__ import annotations

import pathlib

import pytest

from aegean import greek
from aegean.greek import treebank
from aegean.greek.morphology import _rule_analyze
from aegean.greek.treebank import TreebankLexicon, build_lexicon, decode_postag

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "agdt"


@pytest.fixture(autouse=True)
def _restore_default() -> None:
    """Ensure the treebank backend is off after each test (no cross-test leakage)."""
    yield
    treebank.disable_treebank()


def _activate(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    build_lexicon(source_dir=FIXTURE_DIR, force=True)
    greek.use_treebank(build=False)


def test_decode_postag() -> None:
    assert decode_postag("n-p---mv-") == {
        "pos": "NOUN", "number": "pl", "gender": "masc", "case": "voc",
    }
    assert decode_postag("v1saia---") == {
        "pos": "VERB", "number": "sg", "tense": "aor", "mood": "ind",
        "voice": "act", "person": "1",
    }
    assert decode_postag("l-s---mn-") == {
        "pos": "DET", "number": "sg", "gender": "masc", "case": "nom",
    }
    assert decode_postag("") == {}


def test_build_lexicon_from_fixture(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    build_lexicon(source_dir=FIXTURE_DIR, force=True)
    lex = TreebankLexicon.load()
    assert len(lex) >= 4

    # εἶπον → λέγω, two attested readings (1sg + 3pl aorist), accented + certain.
    readings = lex.analyze("εἶπον")
    assert readings and all(a.lemma == "λέγω" and a.lemma_certain for a in readings)
    assert {a.person for a in readings} == {"1", "3"}
    assert all(a.pos == "VERB" and a.tense == "aor" for a in readings)

    assert lex.lemmatize("ἄνδρα") == "ἀνήρ"          # irregular 3rd-declension
    assert lex.lemmatize("μένει") == "μένω"          # homonym numbering stripped
    assert lex.lemmatize("οὐκἀττεστεδ") is None      # unknown → None


def test_analyze_prefers_treebank(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    eipon = greek.analyze("εἶπον")
    # The rule engine cannot reach λέγω from εἶπον; the treebank backend does.
    assert any(a.lemma == "λέγω" and a.pos == "VERB" and a.lemma_certain for a in eipon)
    assert greek.lemmatize("εἶπον") == "λέγω"
    assert greek.best_pos("εἶπον") == "VERB"
    # Accented irregular lemma (the rule engine would give the bare "ανδρα").
    assert greek.lemmatize("ἄνδρα") == "ἀνήρ"


def test_falls_back_to_rule_engine_for_unattested(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _activate(tmp_path, monkeypatch)
    # λύομεν is not in the fixture → identical to the pure rule-engine result.
    assert greek.analyze("λύομεν") == _rule_analyze("λύομεν")
    assert greek.analyze("λύομεν")  # and the rule engine does analyse it


def test_disable_restores_default(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    assert greek.lemmatize("εἶπον") == "λέγω"
    treebank.disable_treebank()
    # Back to the baseline: εἶπον is not a known seed lemma, no λέγω reading.
    assert greek.lemmatize("εἶπον") != "λέγω"
    assert not any(a.lemma == "λέγω" for a in greek.analyze("εἶπον"))
