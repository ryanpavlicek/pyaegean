"""The generalizing edit-tree lemmatizer (opt-in).

The edit-tree unit tests prove the generalization core directly (a rule learned from one
form applies to unseen forms, including accent shifts). The integration tests train a tiny
model from the agdt-dep fixture and check the API + the lemmatize() routing. Real accuracy
needs the full AGDT (opt-in). State is restored after each test.
"""

from __future__ import annotations

import pathlib

import pytest

from aegean import greek
from aegean.greek import lemmatizer
from aegean.greek.lemmatizer import (
    LemmatizerNotLoadedError,
    _norm,
    apply_tree,
    build_tree,
    train_lemmatizer,
)

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "agdt-dep"


@pytest.fixture(autouse=True)
def _restore_default() -> None:
    yield
    lemmatizer.disable_lemmatizer()
    greek.disable_tagger()
    greek.disable_treebank()


# --- edit-tree core (no training) -------------------------------------------


def test_edit_tree_round_trips() -> None:
    tree = build_tree(_norm("λόγου"), _norm("λόγος"))
    assert apply_tree(tree, _norm("λόγου")) == _norm("λόγος")


def test_edit_tree_generalizes_to_unseen_forms() -> None:
    # the -ου → -ος rule learned from one o-stem applies to forms never seen
    tree = build_tree(_norm("λόγου"), _norm("λόγος"))
    assert apply_tree(tree, _norm("νόμου")) == _norm("νόμος")
    assert apply_tree(tree, _norm("δούλου")) == _norm("δούλος")


def test_edit_tree_handles_accent_shift() -> None:
    # grave → acute is a prefix/suffix rewrite the tree captures
    tree = build_tree(_norm("θεὸς"), _norm("θεός"))
    assert apply_tree(tree, _norm("θεὸς")) == _norm("θεός")


def test_apply_returns_none_when_tree_does_not_fit() -> None:
    tree = build_tree(_norm("λόγου"), _norm("λόγος"))  # needs >= 1 trailing char
    assert apply_tree(tree, "") is None


def test_norm_preserves_case() -> None:
    # case must NOT be folded — proper-noun lemmas are capitalized
    assert _norm("Ἀθηναῖος") == "Ἀθηναῖος"


def test_edit_tree_preserves_capitalization() -> None:
    # a capitalized form lemmatizes to a capitalized lemma (no lowercasing)
    tree = build_tree(_norm("Ἀθηναίων"), _norm("Ἀθηναῖος"))
    out = apply_tree(tree, _norm("Ἀθηναίων"))
    assert out == _norm("Ἀθηναῖος")
    assert out is not None and out[0] == "Ἀ"


# --- trained model integration ----------------------------------------------


def _activate(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    train_lemmatizer(source_dir=str(FIXTURE_DIR), epochs=5, force=True)
    greek.use_lemmatizer(train=False)


def test_lemmatize_routes_through_model(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    out = greek.lemmatize("λόγον")
    assert isinstance(out, str) and out
    assert greek.lemmatize("ὁ") == "ὁ"  # identity pattern round-trips


def test_evaluate_lemmatizer_returns_heldout_metrics(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    res = greek.evaluate_lemmatizer(source_dir=str(FIXTURE_DIR), holdout=0.5, epochs=3)
    assert set(res) >= {"lemma_all", "lemma_unseen", "n_all", "n_seen", "n_unseen"}
    assert 0.0 <= res["lemma_all"] <= 1.0
    assert 0.0 <= res["lemma_unseen"] <= 1.0


def test_predict_requires_use_lemmatizer() -> None:
    lemmatizer.disable_lemmatizer()
    with pytest.raises(LemmatizerNotLoadedError):
        lemmatizer.predict("λόγου")
