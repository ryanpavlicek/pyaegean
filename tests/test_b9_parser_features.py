"""B9 contracts and differentiable soft POS/morphology parser inputs."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from aegean.greek import neural_preprocessing as prep


def test_soft_parser_feature_metadata_round_trips_and_is_strict() -> None:
    expected = prep.make_parser_feature_spec(
        prep.PARSER_FEATURE_SOFT_UPOS_MORPH,
        prep.DEFAULT_PARSER_FEATURE_DIM,
    )
    labels = prep.parser_feature_metadata(expected)
    assert prep.validate_parser_feature_spec(labels) == expected

    invalid = {
        "parser_features": {
            **labels["parser_features"],
            "source_heads": ["upos"],
        }
    }
    with pytest.raises(ValueError, match="source_heads"):
        prep.validate_parser_feature_spec(invalid)


def test_legacy_labels_default_only_to_encoder_features() -> None:
    assert prep.validate_parser_feature_spec({}) == prep.make_parser_feature_spec()
    with pytest.raises(ValueError, match="may contain only mode"):
        prep.validate_parser_feature_spec(
            {"parser_features": {"mode": prep.PARSER_FEATURE_ENCODER_ONLY, "dimension": 1}}
        )


def _load_training_module(monkeypatch: pytest.MonkeyPatch, torch: types.ModuleType):
    class TinyEncoder(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.config = types.SimpleNamespace(hidden_size=8)
            self.embedding = torch.nn.Embedding(32, 8)

        def forward(self, input_ids, attention_mask):  # noqa: ANN001, ARG002
            return types.SimpleNamespace(last_hidden_state=self.embedding(input_ids))

    class AutoModel:
        @classmethod
        def from_pretrained(cls, model_name):  # noqa: ANN001, ARG003
            return TinyEncoder()

    transformers = types.ModuleType("transformers")
    transformers.AutoModel = AutoModel
    transformers.AutoTokenizer = object
    transformers.get_linear_schedule_with_warmup = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "transformers", transformers)

    path = Path(__file__).parent.parent / "training" / "train_parser.py"
    spec = importlib.util.spec_from_file_location("b9_train_parser_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_soft_features_reach_both_parser_scorers_and_remain_differentiable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch = pytest.importorskip("torch")
    torch.manual_seed(0)
    module = _load_training_module(monkeypatch, torch)
    tag_sizes = {head: 2 for head in prep.TAG_HEADS}
    parser_features = prep.make_parser_feature_spec(
        prep.PARSER_FEATURE_SOFT_UPOS_MORPH,
        projection_dim=5,
    )
    model = module.JointParser(
        "local-test-encoder",
        tag_sizes,
        n_rels=3,
        arc_dim=4,
        rel_dim=4,
        parser_features=parser_features,
    )
    model.eval()

    captured: dict[str, Any] = {}

    def capture(name: str):
        def hook(_module, inputs):  # noqa: ANN001
            captured[name] = inputs[0]

        return hook

    arc_hook = model.arc_dep[0].register_forward_pre_hook(capture("arc"))
    rel_hook = model.rel_head[0].register_forward_pre_hook(capture("rel"))
    try:
        _tags, arc, rel, lemma = model(
            torch.tensor([[1, 2, 3, 0]]),
            torch.tensor([[1, 1, 1, 0]]),
            torch.tensor([[1, 2, 0]]),
        )
    finally:
        arc_hook.remove()
        rel_hook.remove()

    assert arc.shape == (1, 3, 4)
    assert rel.shape == (1, 3, 3, 4)
    assert lemma is None
    arc_inputs = captured["arc"]
    rel_inputs = captured["rel"]
    assert arc_inputs.shape[-1] == 13
    assert rel_inputs.shape[-1] == 13
    assert torch.count_nonzero(arc_inputs[0, 2, -5:]) == 0  # padded dependent
    assert torch.count_nonzero(rel_inputs[0, 0, -5:]) == 0  # ROOT candidate
    assert torch.count_nonzero(rel_inputs[0, 3, -5:]) == 0  # padded candidate
    assert torch.all(arc_inputs[..., -5:].abs() <= 1)

    (arc.sum() + rel.sum()).backward()
    for head in prep.TAG_HEADS:
        gradient = model.tag_heads[head].weight.grad
        assert gradient is not None
        assert torch.count_nonzero(gradient) > 0
