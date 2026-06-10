"""Greek dependency parsing (opt-in arc-eager + averaged-perceptron parser).

Offline: a synthetic projective AGDT-format fixture exercises the data model, the
transition system/oracle, and a tiny trained model. Real-AGDT training/eval is
local-only (not in CI), like the treebank/LSJ. State is restored after each test.
"""

from __future__ import annotations

import pathlib

import pytest

from aegean import greek
from aegean.greek import syntax
from aegean.greek.syntax import DepTree, ParserNotLoadedError, load_gold_trees, train_parser

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "agdt-dep"


@pytest.fixture(autouse=True)
def _restore_default() -> None:
    yield
    syntax.disable_parser()


def _gold_trees() -> list[DepTree]:
    return load_gold_trees(source_dir=FIXTURE_DIR)


def test_load_gold_trees_and_model() -> None:
    trees = _gold_trees()
    assert len(trees) == 2
    t = trees[0]
    assert [tok.form for tok in t.tokens] == ["ὁ", "ἄνθρωπος", "λόγον", "γράφει"]
    root = t.root()
    assert root is not None and root.form == "γράφει" and root.relation == "PRED"
    assert t.tokens[1].upos == "NOUN"          # postag decoded via the treebank
    assert {c.form for c in t.children(4)} == {"ἄνθρωπος", "λόγον"}
    assert t.head_of(2) is root                 # ἄνθρωπος → γράφει
    assert t.is_projective()


def test_oracle_round_trip_reconstructs_gold() -> None:
    # Applying the static oracle's actions through the transition system must rebuild
    # the exact gold tree — the core correctness check for the parser's machinery.
    for tree in _gold_trees():
        actions = syntax._oracle(tree)
        assert actions is not None  # fixture is projective
        stack, beta = [0], 1
        head: dict[int, int] = {}
        rel: dict[int, str] = {}
        for act_type, r in actions:
            s0 = stack[-1]
            if act_type == syntax.RIGHT:
                rel[beta] = r
            elif act_type == syntax.LEFT:
                rel[s0] = r
            syntax._apply(act_type, r, stack, head, {}, {}, beta)
            beta = syntax._advance_beta(act_type, beta)
        for tok in tree.tokens:
            assert head.get(tok.id) == tok.head
            assert rel.get(tok.id) == tok.relation


def test_train_then_parse_yields_a_valid_tree(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    train_parser(source_dir=FIXTURE_DIR, epochs=10, force=True)
    greek.use_parser(train=False)

    tree = greek.parse(["ὁ", "ἄνθρωπος", "λόγον", "γράφει"])
    assert isinstance(tree, DepTree)
    n = len(tree.tokens)
    assert n == 4
    # Structural validity: every head is in range, no self-loops, ≥1 root, acyclic.
    assert all(0 <= tok.head <= n and tok.head != tok.id for tok in tree.tokens)
    assert any(tok.head == 0 for tok in tree.tokens)
    for tok in tree.tokens:  # walk to root, must terminate
        seen, cur = set(), tok.id
        while cur != 0:
            assert cur not in seen
            seen.add(cur)
            cur = next(t.head for t in tree.tokens if t.id == cur)


def test_parse_requires_use_parser() -> None:
    syntax.disable_parser()
    with pytest.raises(ParserNotLoadedError):
        greek.parse("ὁ λόγος")


def test_evaluate_returns_metrics(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    res = greek.evaluate_parser(source_dir=FIXTURE_DIR, holdout=0.5, epochs=5)
    assert set(res) >= {"uas", "las", "tokens", "sentences"}
    assert 0.0 <= res["las"] <= res["uas"] <= 1.0
