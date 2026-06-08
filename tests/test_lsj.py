"""LSJ glossing (opt-in Perseus Liddell-Scott-Jones backend).

Offline: a synthetic TEI fixture is parsed into an index and activated; the network
download path is not exercised in CI (same policy as the treebank/lineara-images).
Every test restores the default (LSJ-off) state afterward.
"""

from __future__ import annotations

import pathlib

import pytest

from aegean import greek
from aegean.greek import lexicon
from aegean.greek.lexicon import LSJLexicon, LexiconNotLoadedError, build_index

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "lsj"


@pytest.fixture(autouse=True)
def _restore_default() -> None:
    yield
    lexicon.disable_lsj()


def _activate(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    build_index(source_dir=FIXTURE_DIR, force=True)
    greek.use_lsj(build=False)


def test_build_parses_betacode_keys_and_senses(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    build_index(source_dir=FIXTURE_DIR, force=True)
    lex = LSJLexicon.load()
    assert len(lex) >= 2

    e = lex.lookup("λόγος")  # Beta Code key lo/gos -> λόγος
    assert e is not None
    assert e.headword == "λόγος"
    assert e.senses[0].marker == "A" and e.senses[0].level == 1
    assert any("reckoning" in s.text for s in e.senses)
    # Beta Code inside <foreign> is converted: le/gw -> λέγω
    assert "λέγω" in e.senses[0].text
    # <bibl> citation is compacted into the sense text, not dropped as raw tags
    assert "Hdt." in e.senses[0].text


def test_gloss_and_lookup_via_module(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    assert greek.lookup("λόγος").headword == "λόγος"
    g = greek.gloss("λόγος")
    assert g is not None and g.startswith("λόγος:")


def test_lookup_lemmatizes_on_miss(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    # Inflected forms aren't headwords; the seed lemmatizer resolves them, then the
    # lemma hits the LSJ index (λόγου -> λόγος, ἀνθρώπων -> ἄνθρωπος).
    assert greek.lookup("λόγου").headword == "λόγος"
    assert greek.lookup("ἀνθρώπων").headword == "ἄνθρωπος"


def test_accent_insensitive_fallback(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    assert greek.lookup("λογος") is not None  # unaccented -> stripped fallback


def test_unknown_word_returns_none(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    assert greek.gloss("ζzzz") is None


def test_gloss_requires_use_lsj() -> None:
    lexicon.disable_lsj()
    with pytest.raises(LexiconNotLoadedError):
        greek.gloss("λόγος")
