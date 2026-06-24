"""Tests for the pluggable lexicon registry (``greek.lexica``)."""

from __future__ import annotations

import pytest

from aegean import greek
from aegean.greek import koine
from aegean.greek import lexicons as lexmod


@pytest.fixture(autouse=True)
def _reset_lexica():
    """Each test starts and ends with no lexicon active."""
    lexmod._ACTIVE.clear()
    greek.disable_lsj()
    koine.disable_dodson()
    yield
    lexmod._ACTIVE.clear()
    greek.disable_lsj()
    koine.disable_dodson()


def test_lexica_lists_hosted_and_deeplink():
    ids = {i.id: i.hosted for i in greek.lexica()}
    assert ids["lsj"] is True
    assert ids["dodson"] is True
    assert ids["autenrieth"] is False  # deep-link only
    assert ids["slater"] is False
    assert ids["montanari"] is False


def test_lexicon_link_logeion_and_perseus():
    assert (
        greek.lexicon_link("λόγος", lemmatize=False)
        == "https://logeion.uchicago.edu/%CE%BB%CF%8C%CE%B3%CE%BF%CF%82"
    )
    assert greek.lexicon_link("λόγος", service="perseus", lemmatize=False).startswith(
        "https://www.perseus.tufts.edu/hopper/morph?l="
    )
    with pytest.raises(KeyError):
        greek.lexicon_link("λόγος", service="nope")


def test_deeplink_only_lexicon_guard():
    with pytest.raises(ValueError, match="deep-link only"):
        greek.use_lexicon("autenrieth")


def test_unknown_lexicon_raises():
    with pytest.raises(KeyError):
        greek.use_lexicon("does-not-exist")
    with pytest.raises(KeyError):
        greek.gloss("λόγος", dictionary="does-not-exist")


def test_gloss_requires_active_lexicon():
    with pytest.raises(greek.LexiconNotLoadedError):
        greek.gloss("λόγος")
    with pytest.raises(greek.LexiconNotLoadedError):
        greek.gloss("λόγος", dictionary="dodson")  # registered but not loaded


def test_dodson_through_registry():
    greek.use_dodson()
    g = greek.gloss("λόγος", dictionary="dodson")
    assert g and "word" in g
    assert greek.gloss("λόγος") == g  # an unspecified dictionary uses the active one
    e = greek.entry("λόγος", dictionary="dodson")
    assert e is not None
    assert e.lexicon == "dodson"
    assert e.headword
    assert "dodson" in greek.active_lexica()


def test_lexentry_str():
    greek.use_dodson()
    e = greek.entry("λόγος", dictionary="dodson")
    assert e is not None
    assert str(e).startswith(e.headword)
    assert "dodson" in str(e)
