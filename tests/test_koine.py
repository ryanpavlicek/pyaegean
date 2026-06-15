"""Koine glossing via the bundled Dodson lexicon (aegean.greek.koine)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from aegean import greek
from aegean.data import DataNotAvailableError
from aegean.greek import koine


@pytest.fixture()
def dodson() -> Iterator[None]:
    greek.use_dodson(force=True)
    try:
        yield
    finally:
        koine.disable_dodson()


def test_requires_activation() -> None:
    koine.disable_dodson()
    with pytest.raises(koine.DodsonNotLoadedError):
        greek.gloss_nt("λόγος")


def test_lexicon_loads(dodson: None) -> None:
    lex = koine.active()
    assert lex is not None and len(lex) > 5000


def test_gloss_by_strongs(dodson: None) -> None:
    assert greek.gloss_strongs("3056") == "a word, speech, divine utterance, analogy"
    assert greek.gloss_strongs(2316) == "God, a god"           # int key too
    assert greek.gloss_strongs("G746").startswith("ruler")      # 'G' prefix tolerated
    assert greek.gloss_strongs("999999") is None                # unknown number


def test_gloss_by_word(dodson: None) -> None:
    assert greek.gloss_nt("λόγος") == "a word, speech, divine utterance, analogy"
    assert greek.gloss_nt("Λόγος") == greek.gloss_nt("λόγος")   # case-folded
    assert greek.gloss_nt("λογος") == greek.gloss_nt("λόγος")   # accent-folded
    assert greek.gloss_nt("zzznotgreek") is None                # graceful miss


def test_lookup_returns_entry(dodson: None) -> None:
    e = greek.lookup_nt("ἀγάπη")
    assert e is not None
    assert e.strongs == "26" and e.lemma == "ἀγάπη"
    assert "love" in e.gloss


def test_nt_tokens_are_self_glossed(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_nt attaches a Dodson gloss to each token (offline, from the bundle)."""
    def _offline(name: str, **k: object) -> object:
        raise DataNotAvailableError("simulated offline")

    monkeypatch.setattr("aegean.data.fetch", _offline)
    doc = greek.load_nt("Philemon").documents[0]
    paulos = doc.tokens[0]
    assert paulos.annotations["strongs"] == "3972"
    assert paulos.annotations.get("gloss") == "Paul"
