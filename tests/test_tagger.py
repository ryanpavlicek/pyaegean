"""The generalizing averaged-perceptron POS tagger (opt-in).

Offline: trains a tiny model from the agdt-dep fixture and checks the API + integration.
The fixture is too small for accuracy; real numbers need the full AGDT (opt-in). State is
restored after each test.
"""

from __future__ import annotations

import pathlib

import pytest

from aegean import greek
from aegean.greek import tagger
from aegean.greek.tagger import TaggerNotLoadedError, train_tagger

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "agdt-dep"


@pytest.fixture(autouse=True)
def _restore_default() -> None:
    yield
    tagger.disable_tagger()
    greek.disable_treebank()


def _activate(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    train_tagger(source_dir=str(FIXTURE_DIR), epochs=8, force=True)
    greek.use_tagger(train=False)


def test_tag_pos_returns_valid_tags(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    model = tagger.active()
    assert model is not None
    tags = tagger.tag_pos(["ὁ", "ἄνθρωπος", "γράφει"])
    assert len(tags) == 3
    assert all(t in model["labels"] for t in tags)


def test_pos_tag_routes_through_tagger(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert greek.pos_tag("γράφει") == "NOUN"  # baseline: open-class verb falls back to NOUN
    _activate(tmp_path, monkeypatch)
    model = tagger.active()
    assert model is not None
    assert greek.pos_tag("γράφει") in model["labels"]  # now the tagger decides


def test_pos_tags_in_context(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    tags = dict(greek.pos_tags("ὁ ἄνθρωπος γράφει"))
    assert set(tags) == {"ὁ", "ἄνθρωπος", "γράφει"}


def test_evaluate_tagger_returns_heldout_metrics(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    res = greek.evaluate_tagger(source_dir=str(FIXTURE_DIR), holdout=0.5, epochs=3)
    assert set(res) >= {"pos_all", "pos_unseen", "n_all", "n_seen", "n_unseen"}
    assert 0.0 <= res["pos_all"] <= 1.0
    assert 0.0 <= res["pos_unseen"] <= 1.0


def test_tag_pos_requires_use_tagger() -> None:
    tagger.disable_tagger()
    with pytest.raises(TaggerNotLoadedError):
        tagger.tag_pos(["ὁ"])
