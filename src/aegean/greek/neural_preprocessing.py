"""Versioned, dependency-free preprocessing shared by neural training and runtime.

The module deliberately knows nothing about torch, transformers, or tokenizers.  It
accepts the small duck-typed surface exposed by both HuggingFace and the Rust
``tokenizers`` package.  Keeping this contract here makes a tokenizer/alignment change
an explicit preprocessing-version change instead of a silent training/runtime fork.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

PREPROCESSING_VERSION = "pyaegean-neural-preprocessing-v1"
ANNOTATION_PROFILE = "pyaegean-canonical-v1"
NORMALIZATION = "NFC"
SEGMENTATION = "pretokenized"
SPECIAL_TOKEN_POLICY = "roberta:<s>:0:</s>:2"
TAG_HEADS = ("upos", *(f"x{i}" for i in range(9)))
SUPPORTED_PREPROCESSING_VERSIONS = ("grc-joint-v3", PREPROCESSING_VERSION)
PARSER_FEATURE_ENCODER_ONLY = "encoder-only"
PARSER_FEATURE_SOFT_UPOS_MORPH = "soft-upos-morph"
DEFAULT_PARSER_FEATURE_DIM = 128
_PARSER_FEATURE_ACTIVATION = "tanh"
_PARSER_FEATURE_ROOT_POLICY = "zero"


@dataclass(frozen=True, slots=True)
class Alignment:
    """Token IDs and whole-word bookkeeping for one pretokenized input."""

    input_ids: tuple[int, ...]
    attention_mask: tuple[int, ...]
    word_ids: tuple[int | None, ...]
    first_subword_positions: tuple[int, ...]
    kept_indices: tuple[int, ...]

    @property
    def word_pos(self) -> tuple[int, ...]:
        """Compatibility spelling used by the parser model."""
        return self.first_subword_positions


@dataclass(frozen=True, slots=True)
class ParserFeatureSpec:
    """Architecture contract for the representations consumed by parser scorers."""

    mode: str
    projection_dim: int
    source_heads: tuple[str, ...]
    projection_activation: str | None
    root_policy: str | None


@dataclass(frozen=True, slots=True)
class JointCheckpointSpec:
    """Validated fields required to reconstruct a full joint checkpoint."""

    model_name: str
    maps: dict[str, dict[str, int]]
    n_scripts: int
    parser_features: ParserFeatureSpec


def make_parser_feature_spec(
    mode: str = PARSER_FEATURE_ENCODER_ONLY,
    projection_dim: int = DEFAULT_PARSER_FEATURE_DIM,
) -> ParserFeatureSpec:
    """Construct one of the predeclared parser-input architectures."""
    if mode == PARSER_FEATURE_ENCODER_ONLY:
        return ParserFeatureSpec(mode, 0, (), None, None)
    if mode != PARSER_FEATURE_SOFT_UPOS_MORPH:
        raise ValueError(f"unsupported parser feature mode {mode!r}")
    if (
        isinstance(projection_dim, bool)
        or not isinstance(projection_dim, int)
        or not 1 <= projection_dim <= 512
    ):
        raise ValueError("soft parser feature projection_dim must be an integer from 1 to 512")
    return ParserFeatureSpec(
        mode,
        projection_dim,
        TAG_HEADS,
        _PARSER_FEATURE_ACTIVATION,
        _PARSER_FEATURE_ROOT_POLICY,
    )


def parser_feature_metadata(parser_features: ParserFeatureSpec) -> dict[str, Any]:
    """Serialize the parser-input architecture into checkpoint labels metadata."""
    if parser_features.mode == PARSER_FEATURE_ENCODER_ONLY:
        expected = make_parser_feature_spec()
        if parser_features != expected:
            raise ValueError("invalid encoder-only parser feature specification")
        return {"parser_features": {"mode": PARSER_FEATURE_ENCODER_ONLY}}
    expected = make_parser_feature_spec(
        parser_features.mode,
        parser_features.projection_dim,
    )
    if parser_features != expected:
        raise ValueError("invalid soft parser feature specification")
    return {
        "parser_features": {
            "mode": parser_features.mode,
            "projection_dim": parser_features.projection_dim,
            "source_heads": list(parser_features.source_heads),
            "projection_activation": parser_features.projection_activation,
            "root_policy": parser_features.root_policy,
        }
    }


def validate_parser_feature_spec(spec: Mapping[str, Any]) -> ParserFeatureSpec:
    """Validate parser-input metadata, defaulting immutable v3 labels to encoder-only."""
    if "parser_features" not in spec:
        return make_parser_feature_spec()
    raw = spec.get("parser_features")
    if not isinstance(raw, Mapping):
        raise ValueError("checkpoint labels.json parser_features must be an object")
    mode = raw.get("mode")
    if mode == PARSER_FEATURE_ENCODER_ONLY:
        if set(raw) != {"mode"}:
            raise ValueError("encoder-only parser_features may contain only mode")
        return make_parser_feature_spec()
    if mode != PARSER_FEATURE_SOFT_UPOS_MORPH:
        raise ValueError(f"unsupported checkpoint parser feature mode {mode!r}")
    required = {
        "mode",
        "projection_dim",
        "source_heads",
        "projection_activation",
        "root_policy",
    }
    if set(raw) != required:
        raise ValueError(
            "soft parser_features must contain exactly mode, projection_dim, source_heads, "
            "projection_activation, and root_policy"
        )
    projection_dim = raw.get("projection_dim")
    if isinstance(projection_dim, bool) or not isinstance(projection_dim, int):
        raise ValueError("soft parser feature projection_dim must be an integer from 1 to 512")
    parsed = make_parser_feature_spec(mode, projection_dim)
    if raw.get("source_heads") != list(parsed.source_heads):
        raise ValueError(f"soft parser feature source_heads must be {list(TAG_HEADS)!r}")
    if raw.get("projection_activation") != parsed.projection_activation:
        raise ValueError(
            f"soft parser feature projection_activation must be {parsed.projection_activation!r}"
        )
    if raw.get("root_policy") != parsed.root_policy:
        raise ValueError(f"soft parser feature root_policy must be {parsed.root_policy!r}")
    return parsed


def normalize_tokens(words: Sequence[str]) -> list[str]:
    """Normalize pretokenized forms exactly once using canonical NFC."""
    if any(not isinstance(word, str) for word in words):
        raise TypeError("neural pretokenized words must be strings")
    return [unicodedata.normalize("NFC", word) for word in words]


def contract_metadata(max_subwords: int) -> dict[str, Any]:
    """Return the serializable metadata written beside training checkpoints."""
    if isinstance(max_subwords, bool) or not isinstance(max_subwords, int) or max_subwords < 1:
        raise ValueError("max_subwords must be a positive integer")
    return {
        "annotation_profile": ANNOTATION_PROFILE,
        "preprocessing_version": PREPROCESSING_VERSION,
        "normalization": NORMALIZATION,
        "segmentation": SEGMENTATION,
        "special_token_policy": SPECIAL_TOKEN_POLICY,
        "max_subwords": max_subwords,
    }


def validate_joint_checkpoint_spec(spec: Mapping[str, Any]) -> JointCheckpointSpec:
    """Validate the architecture fields consumed by the joint ONNX exporter."""
    model_name = spec.get("model_name")
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("checkpoint labels.json model_name must be a non-empty string")
    heads = spec.get("tag_heads")
    if not isinstance(heads, list) or tuple(heads) != TAG_HEADS:
        raise ValueError(f"checkpoint labels.json tag_heads must be {list(TAG_HEADS)!r}")
    raw_maps = spec.get("maps")
    if not isinstance(raw_maps, Mapping):
        raise ValueError("checkpoint labels.json maps must be an object")
    maps: dict[str, dict[str, int]] = {}
    for head in (*TAG_HEADS, "deprel"):
        raw_mapping = raw_maps.get(head)
        if not isinstance(raw_mapping, Mapping) or not raw_mapping:
            raise ValueError(f"checkpoint labels.json map {head!r} must be a non-empty object")
        mapping: dict[str, int] = {}
        for label, index in raw_mapping.items():
            if not isinstance(label, str):
                raise ValueError(f"checkpoint labels.json map {head!r} contains a non-string label")
            if isinstance(index, bool) or not isinstance(index, int):
                raise ValueError(f"checkpoint labels.json map {head!r} contains a non-integer id")
            mapping[label] = index
        if sorted(mapping.values()) != list(range(len(mapping))):
            raise ValueError(
                f"checkpoint labels.json map {head!r} ids must be contiguous from zero"
            )
        maps[head] = mapping
    n_scripts = spec.get("n_scripts")
    if isinstance(n_scripts, bool) or not isinstance(n_scripts, int) or n_scripts < 1:
        raise ValueError("checkpoint labels.json n_scripts must be a positive integer")
    parser_features = validate_parser_feature_spec(spec)
    return JointCheckpointSpec(model_name.strip(), maps, n_scripts, parser_features)


def configure_tokenizer(tokenizer: Any, max_subwords: int) -> None:
    """Enable the persisted right/longest-first, stride-zero tokenizer policy.

    Fast transformers tokenizers expose this through ``backend_tokenizer``. Call this
    once before training/evaluation encoding; package inference reads the same policy
    from the validated serialized tokenizer and does not mutate it per request.
    """
    backend = getattr(tokenizer, "backend_tokenizer", tokenizer)
    enable = getattr(backend, "enable_truncation", None)
    if callable(enable):
        try:
            enable(
                max_length=max_subwords,
                stride=0,
                strategy="longest_first",
                direction="right",
            )
        except TypeError:
            enable(max_length=max_subwords, stride=0, strategy="longest_first")


def validate_special_token_policy(policy: str) -> None:
    """Reject a tokenizer special-token policy outside the Roberta contract."""
    if policy != SPECIAL_TOKEN_POLICY:
        raise ValueError(
            f"unsupported neural special-token policy {policy!r}; expected {SPECIAL_TOKEN_POLICY!r}"
        )


def tokenizer_json_contract(tokenizer: Mapping[str, Any]) -> tuple[int, str]:
    """Validate serialized truncation/special-token settings and return their contract."""
    truncation = tokenizer.get("truncation")
    if not isinstance(truncation, Mapping):
        raise ValueError("tokenizer must declare a truncation policy")
    max_subwords = truncation.get("max_length")
    if isinstance(max_subwords, bool) or not isinstance(max_subwords, int) or max_subwords < 1:
        raise ValueError("tokenizer max_length must be a positive integer")
    if (
        truncation.get("direction") != "Right"
        or truncation.get("strategy") != "LongestFirst"
        or truncation.get("stride") != 0
    ):
        raise ValueError("tokenizer must use right/longest-first/stride-0 truncation")
    post = tokenizer.get("post_processor")
    if not isinstance(post, Mapping) or post.get("type") != "RobertaProcessing":
        raise ValueError("tokenizer must use the Roberta special-token policy")
    if post.get("cls") != ["<s>", 0] or post.get("sep") != ["</s>", 2]:
        raise ValueError("tokenizer must use <s>:0 and </s>:2 special tokens")
    return max_subwords, SPECIAL_TOKEN_POLICY


def validate_tokenizer_contract(tokenizer: Any, max_subwords: int) -> None:
    """Validate the configured fast tokenizer before joint-model training starts."""
    backend = getattr(tokenizer, "backend_tokenizer", tokenizer)
    serialize = getattr(backend, "to_str", None)
    if not callable(serialize):
        raise ValueError("joint training requires a serializable fast tokenizer")
    try:
        raw = json.loads(serialize())
    except (TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("joint training tokenizer did not serialize as JSON") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("joint training tokenizer JSON must be an object")
    actual_max, _policy = tokenizer_json_contract(raw)
    if actual_max != max_subwords:
        raise ValueError(
            f"tokenizer max_length {actual_max} disagrees with requested {max_subwords}"
        )


def load_checkpoint_metadata(checkpoint: str | Path, spec: Mapping[str, Any]) -> dict[str, Any]:
    """Load and validate the preprocessing contract written by a training checkpoint."""
    root = Path(checkpoint)
    metadata: dict[str, Any] = {}
    contract_keys = {
        "annotation_profile",
        "normalization",
        "segmentation",
        "preprocessing_version",
        "shared_preprocessing_version",
        "special_token_policy",
        "max_subwords",
    }

    def merge_contract(source: Mapping[str, Any], source_name: str) -> None:
        nested = source.get("metadata")
        if nested is not None and not isinstance(nested, Mapping):
            raise ValueError(
                f"checkpoint metadata {source_name} field 'metadata' must be an object"
            )
        candidates = [nested, source] if isinstance(nested, Mapping) else [source]
        for candidate in candidates:
            for key in contract_keys:
                if key not in candidate:
                    continue
                canonical = (
                    "preprocessing_version" if key == "shared_preprocessing_version" else key
                )
                value = candidate[key]
                if canonical in metadata and metadata[canonical] != value:
                    raise ValueError(
                        f"checkpoint metadata {canonical!r} conflicts in {source_name}: "
                        f"{metadata[canonical]!r} != {value!r}"
                    )
                metadata[canonical] = value

    for filename in ("checkpoint-metadata.json", "metadata.json", "checkpoint.json"):
        path = root / filename
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid checkpoint metadata {filename}: {exc}") from exc
        if not isinstance(value, Mapping):
            raise ValueError(f"checkpoint metadata {filename} must be a JSON object")
        merge_contract(value, filename)
    merge_contract(spec, "labels.json")
    max_subwords = metadata.get("max_subwords")
    if isinstance(max_subwords, bool) or not isinstance(max_subwords, int) or max_subwords < 1:
        raise ValueError("checkpoint metadata is missing a positive max_subwords")
    expected = contract_metadata(max_subwords)
    for key, expected_value in expected.items():
        actual = metadata.get(key)
        if actual != expected_value:
            raise ValueError(
                f"checkpoint metadata {key!r} is {actual!r}; expected {expected_value!r}"
            )
    return expected


def validate_manifest_contract(manifest: Any) -> None:
    """Validate the fields that select this executable preprocessing contract."""
    version = getattr(manifest, "preprocessing_version", None)
    if version not in SUPPORTED_PREPROCESSING_VERSIONS:
        raise ValueError(
            f"unsupported neural preprocessing version {version!r}; "
            f"expected one of {SUPPORTED_PREPROCESSING_VERSIONS!r}"
        )
    if getattr(manifest, "annotation_profile", ANNOTATION_PROFILE) != ANNOTATION_PROFILE:
        raise ValueError(f"neural preprocessing requires annotation profile {ANNOTATION_PROFILE!r}")
    if getattr(manifest, "normalization", NORMALIZATION) != NORMALIZATION:
        raise ValueError("neural preprocessing requires NFC normalization")
    if getattr(manifest, "segmentation", SEGMENTATION) != SEGMENTATION:
        raise ValueError("neural preprocessing requires pretokenized segmentation")
    validate_special_token_policy(getattr(manifest, "special_token_policy", SPECIAL_TOKEN_POLICY))


def _field(value: Any, name: str, default: Any = None) -> Any:
    value = getattr(value, name, default)
    return value() if callable(value) else value


def _as_encoding(tokenizer: Any, words: list[str], max_subwords: int) -> Any:
    """Call either a Rust tokenizer or a transformers-style tokenizer."""
    # Fast transformers wrappers expose the same Rust tokenizer used by the runtime.
    # Prefer it so overflow word IDs remain available for whole-word truncation.
    backend = getattr(tokenizer, "backend_tokenizer", None)
    backend_encode = getattr(backend, "encode", None)
    if callable(backend_encode):
        return backend_encode(words[:max_subwords], is_pretokenized=True)
    # ``tokenizers.Tokenizer.encode`` returns an Encoding with ids/word_ids.  A
    # transformers tokenizer's ``encode`` returns only a list, so fall through to its
    # callable interface in that case.
    encode = getattr(tokenizer, "encode", None)
    if callable(encode):
        try:
            candidate = encode(words[:max_subwords], is_pretokenized=True)
        except TypeError:
            candidate = None
        if candidate is not None and _field(candidate, "ids") is not None:
            return candidate
    call = getattr(tokenizer, "__call__", None)
    if not callable(call):
        raise TypeError("tokenizer must expose encode(...) or a transformers-style __call__(...)")
    return call(
        words[:max_subwords],
        is_split_into_words=True,
        truncation=True,
        max_length=max_subwords,
    )


def _word_ids(encoding: Any) -> list[int | None]:
    ids = _field(encoding, "word_ids")
    if ids is None:
        encodings = _field(encoding, "encodings")
        if encodings:
            ids = _field(encodings[0], "word_ids")
    if ids is None:
        raise TypeError("tokenizer encoding does not expose word IDs")
    result = list(ids)
    previous: int | None = None
    for value in result:
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise ValueError("tokenizer returned an invalid word ID")
        if value is not None and previous is not None and value < previous:
            raise ValueError("tokenizer word IDs are not monotonic")
        if value is not None and previous is not None and value > previous + 1:
            raise ValueError("tokenizer word IDs are not contiguous")
        if value is not None:
            previous = value
    return result


def _overflowing(encoding: Any) -> list[Any]:
    overflow = _field(encoding, "overflowing", ())
    if overflow is None:
        overflow = ()
    # BatchEncoding stores overflow on its first underlying Encoding.
    if not overflow:
        encodings = _field(encoding, "encodings")
        if encodings:
            overflow = _field(encodings[0], "overflowing", ())
    return list(overflow or ())


def _alignment_from_encoding(
    encoding: Any,
    max_subwords: int,
    *,
    input_word_count: int | None,
) -> Alignment:
    raw_ids = _field(encoding, "ids")
    if raw_ids is None:
        raw_ids = encoding["input_ids"]
    ids = list(raw_ids)[:max_subwords]
    if any(
        isinstance(token_id, bool) or not isinstance(token_id, int) or token_id < 0
        for token_id in ids
    ):
        raise ValueError("tokenizer returned an invalid token ID")
    word_ids = _word_ids(encoding)[: len(ids)]
    if len(word_ids) != len(ids):
        raise ValueError("tokenizer returned mismatched IDs and word IDs")
    if input_word_count is not None and any(
        word_id is not None and word_id >= input_word_count for word_id in word_ids
    ):
        raise ValueError("tokenizer returned a word ID outside the input")
    overflow = _overflowing(encoding)
    if overflow:
        overflow_ids = _word_ids(overflow[0])
        first_overflow = next((wid for wid in overflow_ids if wid is not None), None)
        last_main = next((wid for wid in reversed(word_ids) if wid is not None), None)
        if first_overflow is not None and first_overflow == last_main:
            keep = [wid != last_main for wid in word_ids]
            ids = [token_id for token_id, present in zip(ids, keep) if present]
            word_ids = [wid for wid, present in zip(word_ids, keep) if present]
    first: list[int] = []
    kept: list[int] = []
    previous: int | None = None
    for position, word_id in enumerate(word_ids):
        if word_id is not None and word_id != previous:
            first.append(position)
            kept.append(word_id)
        previous = word_id
    attention = tuple(1 for _ in ids)
    return Alignment(tuple(ids), attention, tuple(word_ids), tuple(first), tuple(kept))


def align_pretokenized(tokenizer: Any, words: Sequence[str], max_subwords: int) -> Alignment:
    """Encode words and return complete-word first-subword alignment.

    Right truncation can leave a final word split between the main encoding and its
    overflow.  Such a partial word is removed, including all of its labels, while
    special-token rows remain.  This is intentionally based on overflow word IDs, not
    on an assumption about subword lengths.
    """
    if isinstance(max_subwords, bool) or not isinstance(max_subwords, int) or max_subwords < 1:
        raise ValueError("max_subwords must be a positive integer")
    normalized = normalize_tokens(words)
    encoding = _as_encoding(tokenizer, normalized, max_subwords)
    return _alignment_from_encoding(encoding, max_subwords, input_word_count=len(normalized))


def align_encoding(encoding: Any, max_subwords: int) -> Alignment:
    """Align a pre-existing duck-typed Encoding/BatchEncoding."""
    if isinstance(max_subwords, bool) or not isinstance(max_subwords, int) or max_subwords < 1:
        raise ValueError("max_subwords must be a positive integer")
    return _alignment_from_encoding(encoding, max_subwords, input_word_count=None)


def _label(mapping: Mapping[str, int], value: str) -> int:
    try:
        return int(mapping[value])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"unknown neural label {value!r}") from exc


def build_supervision(
    example: Mapping[str, Any],
    tokenizer: Any,
    maps: Mapping[str, Mapping[str, int]],
    max_subwords: int,
    *,
    include_parser: bool = False,
    include_scripts: bool = False,
    script_count: int | None = None,
) -> dict[str, Any]:
    """Build tagger/parser/full training fields from the shared alignment.

    ``kept_indices`` always refers to original word indices.  Dependency heads are
    remapped to the kept-word numbering (ROOT remains zero); a head outside the kept
    prefix receives ``-100`` and its relation is ignored by the parser loss.
    """
    words = list(example["tokens"])
    for field in ("upos", "xpos"):
        if len(example[field]) != len(words):
            raise ValueError(f"example field {field!r} does not match token count")
    if include_parser or include_scripts:
        for field in ("head", "deprel"):
            if len(example[field]) != len(words):
                raise ValueError(f"example field {field!r} does not match token count")
    if include_scripts and len(example["script"]) != len(words):
        raise ValueError("example field 'script' does not match token count")
    for index, (upos, xpos) in enumerate(zip(example["upos"], example["xpos"])):
        if not isinstance(upos, str):
            raise ValueError(f"example UPOS at token {index} must be a string")
        if not isinstance(xpos, str) or len(xpos) != 9:
            raise ValueError(f"example XPOS at token {index} must contain exactly 9 characters")
    if include_parser or include_scripts:
        for index, (head, relation) in enumerate(zip(example["head"], example["deprel"])):
            if isinstance(head, bool) or not isinstance(head, int) or not 0 <= head <= len(words):
                raise ValueError(f"example dependency head at token {index} is invalid")
            if not isinstance(relation, str):
                raise ValueError(f"example dependency relation at token {index} must be a string")
    if include_scripts:
        if isinstance(script_count, bool) or not isinstance(script_count, int) or script_count < 1:
            raise ValueError("script_count must be a positive integer when scripts are included")
        for index, script in enumerate(example["script"]):
            if (
                isinstance(script, bool)
                or not isinstance(script, int)
                or (script != -100 and not 0 <= script < script_count)
            ):
                raise ValueError(f"example lemma script at token {index} is invalid")
    required_maps = set(TAG_HEADS)
    if include_parser or include_scripts:
        required_maps.add("deprel")
    for name in required_maps:
        mapping = maps.get(name)
        if not isinstance(mapping, Mapping) or not mapping:
            raise ValueError(f"missing or empty neural label map {name!r}")
        values = list(mapping.values())
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError(f"neural label map {name!r} contains a non-integer ID")
        if sorted(values) != list(range(len(values))):
            raise ValueError(f"neural label map {name!r} IDs must be contiguous from zero")
    alignment = align_pretokenized(tokenizer, words, max_subwords)
    word_ids = alignment.word_ids
    labels: dict[str, list[int]] = {head: [] for head in TAG_HEADS}
    previous: int | None = None
    for word_id in word_ids:
        first = word_id is not None and word_id != previous
        if first:
            assert word_id is not None
            labels["upos"].append(_label(maps["upos"], example["upos"][word_id]))
            xpos = example["xpos"][word_id]
            for index in range(9):
                labels[f"x{index}"].append(_label(maps[f"x{index}"], xpos[index]))
        else:
            for head in TAG_HEADS:
                labels[head].append(-100)
        previous = word_id
    first_positions = set(alignment.first_subword_positions)
    out: dict[str, Any] = {
        "input_ids": list(alignment.input_ids),
        "attention_mask": list(alignment.attention_mask),
        "word_index": [
            word_id if position in first_positions else -100
            for position, word_id in enumerate(word_ids)
        ],
        "word_pos": list(alignment.first_subword_positions),
        "kept": list(alignment.kept_indices),
    }
    out.update({f"labels_{head}": labels[head] for head in TAG_HEADS})
    if include_parser or include_scripts:
        old_to_new = {word: index for index, word in enumerate(alignment.kept_indices)}
        heads: list[int] = []
        relations: list[int] = []
        for word in alignment.kept_indices:
            gold_head = int(example["head"][word])
            if gold_head == 0:
                mapped_head = 0
            else:
                mapped = old_to_new.get(gold_head - 1)
                mapped_head = mapped + 1 if mapped is not None else -100
            heads.append(mapped_head)
            relations.append(
                _label(maps["deprel"], example["deprel"][word]) if mapped_head != -100 else -100
            )
        out["arc_heads"] = heads
        out["arc_rels"] = relations
    if include_scripts:
        out["scripts"] = [example["script"][word] for word in alignment.kept_indices]
    return out


def compose_lemma_detail(
    form: str,
    upos: str,
    script_id: int,
    *,
    lookup_form_upos: Mapping[str, str],
    lookup_form: Mapping[str, str],
    lookup_lower: Mapping[str, str],
    trees: Sequence[Any] = (),
    apply_edit_script: Callable[[Any, str], str | None] | None = None,
    mode: str = "canonical",
) -> tuple[str, bool, str]:
    """Compose a lemma and return ``(value, resolved, provenance_path)``.

    ``canonical`` is the shipped runtime policy.  The other modes mirror historical
    development experiments and are intentionally opt-in, so a caller cannot silently
    change the product composition.
    """
    form = unicodedata.normalize("NFC", form)
    if mode not in {"canonical", "lookup-first", "neural-only", "neural-first", "unseen-neural"}:
        raise ValueError(f"unknown lemma composition mode: {mode!r}")
    looked_upos = lookup_form_upos.get(f"{form}|{upos}")
    looked_form = lookup_form.get(form)
    lower = lookup_lower.get(form.lower())
    if mode in {"canonical", "lookup-first", "unseen-neural"}:
        if looked_upos:
            return looked_upos, True, "lookup_form_upos"
        if looked_form:
            return looked_form, True, "lookup_form"
    if mode == "unseen-neural" and lower:
        return lower, True, "lookup_lower_fallback"
    applied: str | None = None
    if apply_edit_script is not None and 0 <= script_id < len(trees):
        applied = apply_edit_script(trees[script_id], form)
        if not applied or applied == "_" or applied == form:
            applied = None
    if mode == "neural-only":
        return (applied or form), bool(applied), "edit_script" if applied else "identity_fallback"
    if mode == "neural-first" and applied:
        return applied, True, "edit_script"
    if mode == "neural-first":
        if looked_upos:
            return looked_upos, True, "lookup_form_upos"
        if looked_form:
            return looked_form, True, "lookup_form"
    if mode in {"canonical", "lookup-first"} and applied:
        return applied, True, "edit_script"
    if lower:
        return lower, True, "lookup_lower_fallback"
    if mode == "unseen-neural" and applied:
        return applied, True, "edit_script"
    return form, False, "identity_fallback"


def compose_lemma(*args: Any, **kwargs: Any) -> str:
    """String-only convenience wrapper around :func:`compose_lemma_detail`."""
    return compose_lemma_detail(*args, **kwargs)[0]


canonical_lemma = compose_lemma


__all__ = [
    "ANNOTATION_PROFILE",
    "Alignment",
    "DEFAULT_PARSER_FEATURE_DIM",
    "JointCheckpointSpec",
    "NORMALIZATION",
    "PARSER_FEATURE_ENCODER_ONLY",
    "PARSER_FEATURE_SOFT_UPOS_MORPH",
    "PREPROCESSING_VERSION",
    "ParserFeatureSpec",
    "SEGMENTATION",
    "SPECIAL_TOKEN_POLICY",
    "TAG_HEADS",
    "SUPPORTED_PREPROCESSING_VERSIONS",
    "align_encoding",
    "align_pretokenized",
    "build_supervision",
    "canonical_lemma",
    "compose_lemma",
    "compose_lemma_detail",
    "contract_metadata",
    "configure_tokenizer",
    "load_checkpoint_metadata",
    "make_parser_feature_spec",
    "normalize_tokens",
    "parser_feature_metadata",
    "tokenizer_json_contract",
    "validate_manifest_contract",
    "validate_joint_checkpoint_spec",
    "validate_parser_feature_spec",
    "validate_special_token_policy",
    "validate_tokenizer_contract",
]
