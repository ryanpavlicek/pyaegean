from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from aegean.greek import neural_preprocessing as prep
from aegean.greek.joint import _JointModel


_ROOT = Path(__file__).resolve().parents[1]


class _Encoding:
    def __init__(self, ids, word_ids, overflowing=()):
        self.ids = ids
        self.word_ids = word_ids
        self.overflowing = list(overflowing)


class _Tokenizer:
    def __init__(self, encoding):
        self.encoding = encoding
        self.seen = None
        self.truncation = None

    def enable_truncation(self, **kwargs):
        self.truncation = kwargs

    def encode(self, words, *, is_pretokenized):
        self.seen = (list(words), is_pretokenized)
        return self.encoding


def test_contract_normalizes_nfd_and_preserves_roberta_special_rows() -> None:
    tokenizer = _Tokenizer(_Encoding([0, 10, 11, 2], [None, 0, 0, None]))
    prep.configure_tokenizer(tokenizer, 4)
    alignment = prep.align_pretokenized(tokenizer, ["α\u0301"], 4)
    assert tokenizer.seen == (["ά"], True)
    assert alignment.input_ids == (0, 10, 11, 2)
    assert alignment.first_subword_positions == (1,)
    assert alignment.kept_indices == (0,)
    assert tokenizer.truncation == {
        "max_length": 4,
        "stride": 0,
        "strategy": "longest_first",
        "direction": "right",
    }


def test_transformers_adapter_uses_backend_encoding_with_overflow() -> None:
    encoding = _Encoding(
        [0, 10, 11, 20, 2],
        [None, 0, 0, 1, None],
        [SimpleNamespace(word_ids=[None, 1, 2, None])],
    )
    backend = _Tokenizer(encoding)

    class Wrapper:
        backend_tokenizer = backend

        def __call__(self, *args, **kwargs):
            raise AssertionError("the lossy BatchEncoding path must not be used")

    wrapper = Wrapper()
    prep.configure_tokenizer(wrapper, 5)
    alignment = prep.align_pretokenized(wrapper, ["one", "partial", "tail"], 5)
    assert alignment.input_ids == (0, 10, 11, 2)
    assert alignment.kept_indices == (0,)
    assert backend.truncation["max_length"] == 5


def test_align_encoding_accepts_existing_word_ids_without_input_words() -> None:
    alignment = prep.align_encoding(
        SimpleNamespace(ids=[0, 10, 2], word_ids=[None, 0, None], overflowing=[]),
        3,
    )
    assert alignment.input_ids == (0, 10, 2)
    assert alignment.word_pos == (1,)
    assert alignment.kept_indices == (0,)


def test_partial_final_word_is_removed_from_ids_and_supervision() -> None:
    encoding = _Encoding(
        [0, 10, 11, 20, 21, 2],
        [None, 0, 0, 1, 1, None],
        [SimpleNamespace(word_ids=[None, 1, 1, 2, None])],
    )
    tokenizer = _Tokenizer(encoding)
    alignment = prep.align_pretokenized(tokenizer, ["alpha", "cut", "tail"], 6)
    assert alignment.input_ids == (0, 10, 11, 2)
    assert alignment.word_pos == (1,)
    assert alignment.kept_indices == (0,)


def test_shared_supervision_maps_tags_heads_relations_and_scripts() -> None:
    tokenizer = _Tokenizer(_Encoding([0, 10, 20, 30, 2], [None, 0, 1, 2, None]))
    example = {
        "tokens": ["a", "b", "c"],
        "upos": ["NOUN", "VERB", "NOUN"],
        "xpos": ["abcdefghi", "abcdefghi", "abcdefghi"],
        "head": [0, 1, 2],
        "deprel": ["root", "dep", "dep"],
        "script": [4, 5, 6],
    }
    maps = {
        head: {value: index for index, value in enumerate(("-", *"abcdefghi"))}
        for head in prep.TAG_HEADS
    }
    maps["upos"] = {"NOUN": 0, "VERB": 1}
    maps["deprel"] = {"root": 0, "dep": 1}
    result = prep.build_supervision(
        example,
        tokenizer,
        maps,
        5,
        include_parser=True,
        include_scripts=True,
        script_count=7,
    )
    assert result["word_pos"] == [1, 2, 3]
    assert result["kept"] == [0, 1, 2]
    assert result["arc_heads"] == [0, 1, 2]
    assert result["arc_rels"] == [0, 1, 1]
    assert result["scripts"] == [4, 5, 6]
    assert result["labels_upos"] == [-100, 0, 1, 0, -100]


def test_cross_path_golden_alignment_matches_runtime_and_training_supervision() -> None:
    encoding = _Encoding(
        [0, 10, 11, 20, 30, 2],
        [None, 0, 0, 1, 2, None],
    )
    tokenizer = _Tokenizer(encoding)
    words = ["α\u0301ν", "δ᾽", "·"]
    alignment = prep.align_pretokenized(tokenizer, words, 6)

    runtime = _JointModel.__new__(_JointModel)
    runtime._tok = _Tokenizer(encoding)
    runtime.manifest = SimpleNamespace(max_subwords=6)
    assert runtime._encode(words) == ([0, 10, 11, 20, 30, 2], [1, 3, 4], [0, 1, 2])

    maps = {head: {"-": 0} for head in prep.TAG_HEADS}
    maps["upos"] = {"X": 0}
    example = {
        "tokens": words,
        "upos": ["X", "X", "X"],
        "xpos": ["---------", "---------", "---------"],
    }
    supervision = prep.build_supervision(example, _Tokenizer(encoding), maps, 6)
    assert supervision["input_ids"] == list(alignment.input_ids)
    assert supervision["word_pos"] == list(alignment.first_subword_positions)
    assert supervision["labels_upos"] == [-100, 0, -100, 0, 0, -100]

    for relative, delegate in (
        ("training/train_tagger.py", "build_supervision"),
        ("training/train_parser.py", "build_supervision"),
        ("training/train_full.py", "build_supervision"),
        ("training/bakeoff_upos.py", "align_pretokenized"),
    ):
        tree = ast.parse((_ROOT / relative).read_text(encoding="utf-8"))
        encode = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "encode"
        )
        assert any(
            isinstance(node, ast.Attribute) and node.attr == delegate for node in ast.walk(encode)
        ), relative


@given(st.lists(st.integers(min_value=1, max_value=5), min_size=2, max_size=12))
def test_alignment_property_keeps_only_complete_monotonic_words(lengths: list[int]) -> None:
    total = sum(lengths)
    cut = max(1, total // 2)
    full_word_ids = [word for word, length in enumerate(lengths) for _ in range(length)]
    main_words = full_word_ids[:cut]
    overflow_words = full_word_ids[cut:]
    encoding = _Encoding(
        [0, *(100 + index for index in range(len(main_words))), 2],
        [None, *main_words, None],
        [SimpleNamespace(word_ids=[None, *overflow_words, None])],
    )
    alignment = prep.align_pretokenized(
        _Tokenizer(encoding), [f"w{index}" for index in range(len(lengths))], cut + 2
    )
    expected = tuple(index for index in range(len(lengths)) if sum(lengths[: index + 1]) <= cut)
    assert alignment.kept_indices == expected
    assert tuple(sorted(set(alignment.kept_indices))) == alignment.kept_indices
    assert alignment.input_ids[0] == 0 and alignment.input_ids[-1] == 2
    assert all(
        alignment.word_ids[position] == word
        for position, word in zip(alignment.first_subword_positions, expected)
    )


def test_canonical_lemma_rejects_placeholder_and_identity_edits_before_lowercase() -> None:
    kwargs = dict(
        lookup_form_upos={},
        lookup_form={},
        lookup_lower={"form": "lowered"},
        trees=["placeholder", "identity", "real"],
    )

    def apply(tree, form):
        return {"placeholder": "_", "identity": form, "real": "lemma"}[tree]

    assert prep.compose_lemma("FORM", "NOUN", 0, apply_edit_script=apply, **kwargs) == "lowered"
    assert prep.compose_lemma("FORM", "NOUN", 1, apply_edit_script=apply, **kwargs) == "lowered"
    assert prep.compose_lemma("FORM", "NOUN", 2, apply_edit_script=apply, **kwargs) == "lemma"


@pytest.mark.parametrize(
    ("form_upos", "form", "lower", "script_id", "expected"),
    [
        ({"ΛΌΓΟΣ|NOUN": "upos"}, {}, {}, -1, ("upos", True, "lookup_form_upos")),
        ({}, {"ΛΌΓΟΣ": "form"}, {}, -1, ("form", True, "lookup_form")),
        ({}, {}, {}, 0, ("lemma", True, "edit_script")),
        ({}, {}, {"λόγος": "lower"}, -1, ("lower", True, "lookup_lower_fallback")),
        ({}, {}, {}, -1, ("ΛΌΓΟΣ", False, "identity_fallback")),
    ],
)
def test_canonical_lemma_golden_paths(form_upos, form, lower, script_id, expected) -> None:
    assert (
        prep.compose_lemma_detail(
            "ΛΌΓΟΣ",
            "NOUN",
            script_id,
            lookup_form_upos=form_upos,
            lookup_form=form,
            lookup_lower=lower,
            trees=["tree"],
            apply_edit_script=lambda tree, value: "lemma",
        )
        == expected
    )


@pytest.mark.parametrize(
    ("encoding", "message"),
    [
        (_Encoding([0, 1], [None]), "mismatched"),
        (_Encoding([0, 1, 2], [None, 1, 0]), "monotonic"),
        (_Encoding([0, 1, 2, 3], [None, 0, 2, None]), "contiguous"),
        (_Encoding([0, 1, 2], [None, True, None]), "word ID"),
        (_Encoding([0, -1, 2], [None, 0, None]), "token ID"),
        (_Encoding([0, 1, 2], [None, 9, None]), "outside the input"),
    ],
)
def test_alignment_rejects_malformed_tokenizer_output(encoding, message) -> None:
    with pytest.raises(ValueError, match=message):
        prep.align_pretokenized(_Tokenizer(encoding), ["one", "two"], 3)


def test_supervision_rejects_malformed_labels_and_dependencies() -> None:
    tokenizer = _Tokenizer(_Encoding([0, 10, 2], [None, 0, None]))
    base = {
        "tokens": ["one"],
        "upos": ["X"],
        "xpos": ["---------"],
        "head": [0],
        "deprel": ["root"],
        "script": [0],
    }
    maps = {head: {"-": 0} for head in prep.TAG_HEADS}
    maps["upos"] = {"X": 0}
    maps["deprel"] = {"root": 0}

    with pytest.raises(ValueError, match="exactly 9"):
        prep.build_supervision({**base, "xpos": ["short"]}, tokenizer, maps, 3)
    with pytest.raises(ValueError, match="dependency head"):
        prep.build_supervision({**base, "head": [2]}, tokenizer, maps, 3, include_parser=True)
    bad_maps = {**maps, "upos": {"X": 2}}
    with pytest.raises(ValueError, match="contiguous"):
        prep.build_supervision(base, tokenizer, bad_maps, 3)
    with pytest.raises(ValueError, match="lemma script"):
        prep.build_supervision(
            {**base, "script": [2]},
            tokenizer,
            maps,
            3,
            include_scripts=True,
            script_count=2,
        )


def test_checkpoint_metadata_round_trip_and_malformed_sidecar(tmp_path: Path) -> None:
    metadata = prep.contract_metadata(256)
    assert prep.load_checkpoint_metadata(tmp_path, metadata) == metadata

    (tmp_path / "checkpoint-metadata.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid checkpoint metadata"):
        prep.load_checkpoint_metadata(tmp_path, metadata)


def test_checkpoint_metadata_rejects_conflicting_sidecar(tmp_path: Path) -> None:
    metadata = prep.contract_metadata(12)
    (tmp_path / "checkpoint-metadata.json").write_text(
        json.dumps({**metadata, "max_subwords": 99}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="max_subwords.*conflicts"):
        prep.load_checkpoint_metadata(tmp_path, metadata)


def test_joint_checkpoint_spec_rejects_missing_and_malformed_fields() -> None:
    maps = {head: {"-": 0} for head in prep.TAG_HEADS}
    maps["deprel"] = {"root": 0}
    valid = {
        "model_name": "bowphs/GreBerta",
        "tag_heads": list(prep.TAG_HEADS),
        "maps": maps,
        "n_scripts": 1,
    }
    parsed = prep.validate_joint_checkpoint_spec(valid)
    assert parsed.model_name == "bowphs/GreBerta"
    assert parsed.n_scripts == 1
    assert parsed.parser_features == prep.make_parser_feature_spec()

    for changed, message in (
        ({**valid, "model_name": ""}, "model_name"),
        ({**valid, "n_scripts": 0}, "n_scripts"),
        ({**valid, "maps": {**maps, "deprel": {}}}, "deprel"),
        ({**valid, "maps": {**maps, "deprel": {"root": 2}}}, "contiguous"),
    ):
        with pytest.raises(ValueError, match=message):
            prep.validate_joint_checkpoint_spec(changed)


def test_lookup_hit_does_not_apply_an_unused_edit_script() -> None:
    def fail_if_called(tree, form):
        raise AssertionError(f"unused edit script called for {tree!r}, {form!r}")

    result = prep.compose_lemma(
        "FORM",
        "NOUN",
        0,
        lookup_form_upos={},
        lookup_form={"FORM": "known"},
        lookup_lower={},
        trees=["malformed"],
        apply_edit_script=fail_if_called,
    )
    assert result == "known"


def test_tokenizer_contract_rejects_non_roberta_joint_training() -> None:
    valid = {
        "truncation": {
            "direction": "Right",
            "max_length": 12,
            "strategy": "LongestFirst",
            "stride": 0,
        },
        "post_processor": {
            "type": "RobertaProcessing",
            "cls": ["<s>", 0],
            "sep": ["</s>", 2],
        },
    }

    class Serialized:
        def __init__(self, value):
            self.value = value

        def to_str(self):
            import json

            return json.dumps(self.value)

    prep.validate_tokenizer_contract(Serialized(valid), 12)
    with pytest.raises(ValueError, match="Roberta"):
        prep.validate_tokenizer_contract(
            Serialized({**valid, "post_processor": {"type": "TemplateProcessing"}}),
            12,
        )


def test_manifest_contract_rejects_drift_and_accepts_legacy_v3() -> None:
    base = dict(
        annotation_profile=prep.ANNOTATION_PROFILE,
        preprocessing_version=prep.PREPROCESSING_VERSION,
        normalization="NFC",
        segmentation="pretokenized",
        special_token_policy=prep.SPECIAL_TOKEN_POLICY,
    )
    prep.validate_manifest_contract(SimpleNamespace(**base))
    prep.validate_manifest_contract(
        SimpleNamespace(**{**base, "preprocessing_version": "grc-joint-v3"})
    )
    for field, value in (
        ("annotation_profile", "other"),
        ("normalization", "NFD"),
        ("segmentation", "raw"),
        ("special_token_policy", "bert:[CLS]:0:[SEP]:0"),
        ("preprocessing_version", "future-v2"),
    ):
        with pytest.raises(ValueError):
            prep.validate_manifest_contract(SimpleNamespace(**{**base, field: value}))
