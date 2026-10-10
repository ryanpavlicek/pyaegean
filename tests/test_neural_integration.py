"""Bounded correctness checks against the actual pinned neural model.

Run ``python scripts/check_neural_integration.py --provision`` after installing
``.[dev,neural]``. The ordinary unit suite excludes this group. These tests never
download assets themselves and never load evaluation corpora.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from conftest import _cached_neural_backend


pytestmark = pytest.mark.neural_integration

# The published neural example in wiki/Greek-NLP.md supplies these existing answers.
WORDS = ["ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος"]
UPOS = ("ADP", "NOUN", "VERB", "DET", "NOUN")
LEMMAS = ("ἐν", "ἀρχή", "εἰμί", "ὁ", "λόγος")


@pytest.fixture(scope="module")
def model() -> Iterator[Any]:
    with _cached_neural_backend(required=True) as backend:
        yield backend


def _assert_tree(heads: tuple[int, ...], relations: tuple[str, ...]) -> None:
    n = len(heads)
    assert len(relations) == n
    roots = [i for i, head in enumerate(heads, start=1) if head == 0]
    assert len(roots) == 1
    assert [i for i, relation in enumerate(relations, start=1) if relation == "root"] == roots
    for index, head in enumerate(heads, start=1):
        assert 0 <= head <= n and head != index
        visited: set[int] = set()
        current = index
        while current:
            assert current not in visited, f"dependency cycle from token {index}"
            visited.add(current)
            current = heads[current - 1]
        assert roots[0] in visited, f"token {index} is disconnected from the root"


def test_actual_model_tags_and_lemmatizes_the_existing_example(model: Any) -> None:
    from aegean import greek
    from aegean.greek import joint

    assert isinstance(model, joint._JointModel)
    analysis = greek.analyze_sentence(WORDS)
    assert analysis.tokens == tuple(WORDS)
    assert analysis.upos == UPOS
    assert analysis.lemma == LEMMAS
    assert analysis.feats[1] == "Case=Dat|Gender=Fem|Number=Sing"
    assert all(analysis.lemma_resolved)
    assert analysis.complete and not analysis.truncated
    assert analysis.analyzed == (True,) * len(WORDS)
    _assert_tree(analysis.head, analysis.deprel)

    selected = joint._resolve_neural_variant("default")
    receipt = analysis.receipt
    assert receipt is not None
    assert receipt.model_id == selected.model_id
    assert receipt.asset_sha256 == selected.asset_sha256
    assert receipt.asset_sha256_enforced
    assert receipt.execution_providers == ("CPUExecutionProvider",)
    assert receipt.input_tokens == receipt.analyzed_tokens == len(WORDS)
    assert not receipt.windowed


def test_actual_pipeline_emits_a_single_connected_root(model: Any) -> None:
    from aegean import greek

    records = greek.pipeline("πλῆθός σο̣ι τῶν ἱππαρίων καὶ", parse=True)
    assert len(records) == 5
    assert all(record.upos and record.lemma for record in records)
    _assert_tree(tuple(record.head for record in records), tuple(record.relation for record in records))


def test_strict_long_input_rejects_incomplete_analysis(model: Any) -> None:
    from aegean.greek.joint import NeuralInputTooLongError

    words = ["λόγος"] * (model.max_subwords + 1)
    with pytest.raises(NeuralInputTooLongError) as error:
        model.analyze(words)
    assert error.value.input_tokens == len(words)
    assert 0 < error.value.analyzed_tokens < len(words)
    assert error.value.max_subwords == model.max_subwords


def test_windowed_long_input_preserves_every_token_and_a_valid_tree(model: Any) -> None:
    words = (WORDS * ((model.max_subwords // len(WORDS)) + 1))[:model.max_subwords + 1]
    analysis = model.analyze(words, long_input="windowed")
    assert analysis.tokens == tuple(words)
    assert analysis.complete and not analysis.truncated
    assert analysis.analyzed == (True,) * len(words)
    for field in (analysis.upos, analysis.xpos, analysis.feats, analysis.lemma):
        assert len(field) == len(words)
    assert all(tag and tag != "X" for tag in analysis.upos)
    assert all(lemma and lemma != "_" for lemma in analysis.lemma)
    _assert_tree(analysis.head, analysis.deprel)
    assert analysis.receipt is not None
    assert analysis.receipt.windowed
    assert analysis.receipt.input_tokens == analysis.receipt.analyzed_tokens == len(words)
    assert analysis.receipt.execution_providers == ("CPUExecutionProvider",)


def test_windowed_single_pass_preserves_the_short_analysis(model: Any) -> None:
    assert model.analyze(WORDS, long_input="windowed") == model.analyze(WORDS)
