"""Dependency-free, source-preserving Greek sentence segmentation.

The segmenter intentionally has a small contract.  Rules are conservative and
deterministic; callers that have edition-specific or learned evidence can pass a
``SentenceSegmenter`` implementation.  Plugin results are normalized and checked
before a caller can use them, so a malformed plugin cannot create a gap, overlap,
or out-of-range source mapping.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Literal, Protocol, runtime_checkable

SegmentationPolicy = Literal["default", "prose", "verse", "inscription", "papyrus"]
BoundaryProvenance = Literal["rule", "explicit", "plugin"]
SCHEMA_VERSION = 1

_POLICIES = ("default", "prose", "verse", "inscription", "papyrus")
_TERMINAL = frozenset(".!?;;··")
_TRAILING_CLOSERS = frozenset('"”»)]}〕〉》】］⟧>』')
_ABBREVIATIONS = frozenset({"cf", "sc", "fr", "ed", "p", "pp", "l", "ll", "col", "ca", "κτλ", "δηλ", "κ", "δ"})
_POLICY_IDS = {
    "default": "pyaegean-sentence-default-v1",
    "prose": "pyaegean-sentence-prose-v1",
    "verse": "pyaegean-sentence-verse-v1",
    "inscription": "pyaegean-sentence-inscription-v1",
    "papyrus": "pyaegean-sentence-papyrus-v1",
    "explicit": "pyaegean-sentence-explicit-v1",
}
POLICY_IDS = MappingProxyType(_POLICY_IDS)
PLUGIN_POLICY_ID = "caller-plugin-unversioned"
POLICY_RULES = MappingProxyType({
    "default": "conservative punctuation: period, Greek question mark, ano teleia, !, and ?; dotted abbreviations/numbers are protected",
    "prose": "the default conservative punctuation policy, named for literary prose; modern !/? are strong terminals",
    "verse": "prose punctuation plus every non-empty physical line is a boundary",
    "inscription": "only strong period/!/?: weak semicolon and ano-teleia marks remain uncommitted",
    "papyrus": "only strong period/!?; terminal marks inside balanced [], ⟦⟧, or <> editorial brackets are ignored",
})
_DOTTED_ABBREVIATION = re.compile(r"(?<![^\W\d_])(?:[^\W\d_]\.){2,}", re.UNICODE)
_DOTTED_NUMBER = re.compile(r"\d+(?:\.\d+)+")
_WORD_BEFORE_PERIOD = re.compile(r"([^\W\d_]+)\.", re.UNICODE)


@dataclass(frozen=True, slots=True)
class SentenceBoundary:
    """One half-open source span and the evidence that ended it.

    ``start`` and ``end`` are Python code-point offsets into the exact source
    string.  Whitespace between spans is intentionally retained in the source,
    but is not assigned to either sentence.  Rule output has no confidence:
    callers must not mistake a deterministic rule marker for a calibrated score.
    """

    start: int
    end: int
    policy: str = "default"
    provenance: BoundaryProvenance = "rule"
    confidence: float | None = None
    policy_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("start", "end"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.end <= self.start:
            raise ValueError("sentence boundary end must be greater than start")
        if not isinstance(self.policy, str) or not self.policy:
            raise TypeError("boundary policy must be a non-empty string")
        if self.provenance not in ("rule", "explicit", "plugin"):
            raise ValueError("boundary provenance must be rule, explicit, or plugin")
        expected_policy_id = POLICY_IDS.get(self.policy)
        if self.policy_id is None:
            default_policy_id = (
                PLUGIN_POLICY_ID if self.provenance == "plugin" else expected_policy_id
            )
            if default_policy_id is not None:
                object.__setattr__(self, "policy_id", default_policy_id)
        elif self.policy_id is not None and (
            not isinstance(self.policy_id, str) or not self.policy_id
        ):
            raise TypeError("policy_id must be a non-empty string or None")
        if (
            expected_policy_id is not None
            and self.provenance in ("rule", "explicit")
            and self.policy_id != expected_policy_id
        ):
            raise ValueError("policy_id does not match boundary policy")
        if self.provenance == "plugin" and self.policy_id in POLICY_IDS.values():
            raise ValueError("plugin boundaries cannot claim a built-in policy_id")
        if self.confidence is not None:
            if (
                isinstance(self.confidence, bool)
                or not isinstance(self.confidence, (int, float))
                or not math.isfinite(float(self.confidence))
                or not 0.0 <= float(self.confidence) <= 1.0
            ):
                raise ValueError("boundary confidence must be a finite number in [0, 1]")
            if self.provenance == "rule":
                raise ValueError("rule boundaries must not claim a confidence")

    @property
    def start_char(self) -> int:
        """Alias used by source-alignment consumers."""
        return self.start

    @property
    def end_char(self) -> int:
        """Alias used by source-alignment consumers."""
        return self.end

    def text(self, source: str) -> str:
        """Return this exact source slice after validating the source type/range."""
        if not isinstance(source, str):
            raise TypeError("source must be a string")
        if self.end > len(source):
            raise ValueError("sentence boundary falls outside the source")
        return source[self.start : self.end]

    def to_dict(self, source: str | None = None) -> dict[str, Any]:
        """Return JSON-safe boundary metadata, optionally including its text."""
        value: dict[str, Any] = {
            "start": self.start,
            "end": self.end,
            "start_char": self.start,
            "end_char": self.end,
            "policy": self.policy,
            "provenance": self.provenance,
            "confidence": self.confidence,
            "policy_id": self.policy_id,
            "schema_version": SCHEMA_VERSION,
        }
        if source is not None:
            value["text"] = self.text(source)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SentenceBoundary":
        """Decode one JSON boundary and apply the same constructor validation."""
        if not isinstance(value, Mapping):
            raise TypeError("sentence boundary must be an object")
        expected = {
            "start", "end", "start_char", "end_char", "policy", "provenance",
            "confidence", "policy_id", "schema_version", "text",
        }
        if set(value) - expected:
            raise ValueError("sentence boundary contains unknown fields")
        schema_version = value.get("schema_version", SCHEMA_VERSION)
        if (
            not isinstance(schema_version, int)
            or isinstance(schema_version, bool)
            or schema_version != SCHEMA_VERSION
        ):
            raise ValueError("unsupported sentence boundary schema")
        if "start" in value and "start_char" in value and value["start"] != value["start_char"]:
            raise ValueError("start and start_char disagree")
        if "end" in value and "end_char" in value and value["end"] != value["end_char"]:
            raise ValueError("end and end_char disagree")
        start = value.get("start", value.get("start_char"))
        end = value.get("end", value.get("end_char"))
        if start is None or end is None:
            raise ValueError("sentence boundary requires start and end")
        return cls(
            start,
            end,
            policy=value.get("policy", "default"),
            provenance=value.get("provenance", "rule"),
            confidence=value.get("confidence"),
            policy_id=value.get("policy_id"),
        )


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    """Immutable, validated result returned by every sentence segmenter."""

    source: str
    boundaries: tuple[SentenceBoundary, ...]
    policy: str = "default"
    provenance: BoundaryProvenance = "rule"
    policy_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, str):
            raise TypeError("segmentation source must be a string")
        if not isinstance(self.boundaries, tuple):
            raise TypeError("boundaries must be a tuple of SentenceBoundary values")
        if any(not isinstance(item, SentenceBoundary) for item in self.boundaries):
            raise TypeError("boundaries must contain SentenceBoundary values")
        if not isinstance(self.policy, str) or not self.policy:
            raise TypeError("segmentation policy must be a non-empty string")
        if self.provenance not in ("rule", "explicit", "plugin"):
            raise ValueError("segmentation provenance must be rule, explicit, or plugin")
        expected_policy_id = POLICY_IDS.get(self.policy)
        if self.policy_id is None:
            default_policy_id = (
                PLUGIN_POLICY_ID if self.provenance == "plugin" else expected_policy_id
            )
            if default_policy_id is not None:
                object.__setattr__(self, "policy_id", default_policy_id)
        elif self.policy_id is not None and (
            not isinstance(self.policy_id, str) or not self.policy_id
        ):
            raise TypeError("policy_id must be a non-empty string or None")
        if (
            expected_policy_id is not None
            and self.provenance in ("rule", "explicit")
            and self.policy_id != expected_policy_id
        ):
            raise ValueError("policy_id does not match segmentation policy")
        if self.provenance == "plugin" and self.policy_id in POLICY_IDS.values():
            raise ValueError("plugin results cannot claim a built-in policy_id")
        previous_end = -1
        for boundary in self.boundaries:
            if boundary.policy != self.policy:
                raise ValueError("boundary policy does not match segmentation policy")
            if boundary.provenance != self.provenance:
                raise ValueError("boundary provenance does not match segmentation provenance")
            if boundary.policy_id != self.policy_id:
                raise ValueError("boundary policy_id does not match segmentation policy_id")
            if boundary.end > len(self.source):
                raise ValueError("sentence boundary falls outside the source")
            if boundary.start < previous_end:
                raise ValueError("sentence boundaries must be ordered and non-overlapping")
            if self.source[boundary.start].isspace() or self.source[boundary.end - 1].isspace():
                raise ValueError("sentence boundaries must start and end on non-whitespace source")
            if not self.source[boundary.start : boundary.end].strip():
                raise ValueError("sentence boundaries must contain non-whitespace source")
            previous_end = boundary.end
        if not self.boundaries:
            if self.source.strip():
                raise ValueError("non-empty source requires sentence boundaries")
            return
        previous_end = 0
        for boundary in self.boundaries:
            if self.source[previous_end : boundary.start].strip():
                raise ValueError("sentence boundaries do not cover all non-whitespace source")
            previous_end = boundary.end
        if self.source[previous_end:].strip():
            raise ValueError("sentence boundaries do not cover all non-whitespace source")

    @property
    def segments(self) -> tuple[SentenceBoundary, ...]:
        """Alias for callers that use segment terminology."""
        return self.boundaries

    @property
    def spans(self) -> tuple[SentenceBoundary, ...]:
        return self.boundaries

    @property
    def sentence_spans(self) -> tuple[SentenceBoundary, ...]:
        return self.boundaries

    @property
    def sentences(self) -> tuple[str, ...]:
        # Keep the historical ``sentences()`` projection: terminal punctuation
        # was a delimiter and was not included in returned strings.  Rich
        # boundaries and token alignments retain the punctuation in their exact
        # source spans.
        projected: list[str] = []
        for boundary in self.boundaries:
            sentence = boundary.text(self.source).strip()
            protected_periods = _protected_periods(sentence, _ABBREVIATIONS)
            terminal_index = max(
                (
                    index
                    for index, char in enumerate(sentence)
                    if char in _TERMINAL
                    and not (char == "." and index in protected_periods)
                ),
                default=-1,
            )
            suffix = sentence[terminal_index + 1 :]
            if terminal_index >= 0 and not any(
                char.isspace() or _is_greek_word_character(char) for char in suffix
            ):
                sentence = (
                    sentence[: terminal_index + 1].rstrip(".!?;;··").rstrip()
                    + suffix
                )
            if sentence:
                projected.append(sentence)
        return tuple(projected)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "source": self.source,
            "policy": self.policy,
            "policy_id": self.policy_id,
            "provenance": self.provenance,
            "boundaries": [boundary.to_dict(self.source) for boundary in self.boundaries],
            "sentences": list(self.sentences),
        }

    def to_json(self) -> str:
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, value: str) -> "SegmentationResult":
        """Strictly decode a schema-1 JSON result, rejecting duplicate keys."""
        import json

        def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, item in items:
                if key in result:
                    raise ValueError(f"duplicate JSON key {key!r}")
                result[key] = item
            return result

        try:
            raw = json.loads(value, object_pairs_hook=pairs)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid segmentation JSON: {exc}") from exc
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SegmentationResult":
        """Decode and validate a JSON-ready result."""
        if not isinstance(value, Mapping):
            raise TypeError("segmentation result must be an object")
        expected = {"schema_version", "source", "policy", "policy_id", "provenance", "boundaries", "sentences"}
        if set(value) != expected:
            raise ValueError("segmentation result keys do not match schema 1")
        schema_version = value.get("schema_version")
        if (
            not isinstance(schema_version, int)
            or isinstance(schema_version, bool)
            or schema_version != SCHEMA_VERSION
        ):
            raise ValueError("unsupported segmentation result schema")
        source = value.get("source")
        raw = value.get("boundaries")
        sentences_value = value.get("sentences")
        if not isinstance(source, str) or not isinstance(raw, Sequence) or not isinstance(sentences_value, list):
            raise ValueError("segmentation result requires source and boundaries")
        boundaries_list: list[SentenceBoundary] = []
        for item in raw:
            if not isinstance(item, Mapping) or set(item) != {
                "start",
                "end",
                "start_char",
                "end_char",
                "policy",
                "provenance",
                "confidence",
                "policy_id",
                "schema_version",
                "text",
            }:
                raise ValueError("sentence boundary keys do not match schema 1")
            boundary = SentenceBoundary.from_dict(item)
            if item["text"] != source[boundary.start : boundary.end]:
                raise ValueError("sentence boundary text does not match source span")
            boundaries_list.append(boundary)
        boundaries = tuple(boundaries_list)
        result = cls(
            source,
            boundaries,
            policy=value.get("policy", "default"),
            provenance=value.get("provenance", "rule"),
            policy_id=value.get("policy_id"),
        )
        if sentences_value != list(result.sentences):
            raise ValueError("segmentation sentences do not match source spans")
        return result


@runtime_checkable
class SentenceSegmenter(Protocol):
    """Protocol for caller-supplied deterministic or learned segmenters."""

    def segment(self, text: str) -> SegmentationResult | Sequence[Any]:
        """Return a rich result or boundary-like sequence for *text*."""


SegmenterLike = SentenceSegmenter | Callable[[str], Any]


def _policy_name(policy: str) -> SegmentationPolicy:
    if not isinstance(policy, str):
        raise TypeError("segmentation policy must be a string")
    if policy not in _POLICIES:
        raise ValueError(f"unknown segmentation policy {policy!r}; expected one of {_POLICIES}")
    return policy  # type: ignore[return-value]


def _nonspace_start(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _protected_periods(text: str, abbreviations: frozenset[str]) -> set[int]:
    """Return non-terminal period offsets in linear passes over *text*."""
    protected: set[int] = set()

    index = 0
    while index < len(text):
        if text[index] != ".":
            index += 1
            continue
        end = index + 1
        while end < len(text) and text[end] == ".":
            end += 1
        if end - index >= 2:
            protected.update(range(index, end))
        index = end

    for match in _DOTTED_ABBREVIATION.finditer(text):
        protected.update(
            offset
            for offset in range(match.start(), match.end())
            if text[offset] == "."
        )
    for match in _DOTTED_NUMBER.finditer(text):
        protected.update(
            offset
            for offset in range(match.start(), match.end())
            if text[offset] == "."
        )
    for match in _WORD_BEFORE_PERIOD.finditer(text):
        word = match.group(1)
        period = match.end() - 1
        if word.casefold() in abbreviations:
            protected.add(period)
            continue
        # Ordinary Latin initials such as ``J. smith`` are protected.  Greek
        # lower-case single-letter words remain sentence-compatible (``α. β``).
        next_index = _nonspace_start(text, period + 1)
        if (
            len(word) == 1
            and word.isascii()
            and word.isupper()
            and next_index < len(text)
            and text[next_index].islower()
        ):
            protected.add(period)
    return protected


def _balanced_editorial_positions(text: str) -> list[bool]:
    """Mark characters inside balanced papyrological editorial brackets."""
    bracket_pairs = {"[": "]", "⟦": "⟧", "<": ">"}
    stack: list[tuple[str, int]] = []
    changes = [0] * (len(text) + 1)
    for index, char in enumerate(text):
        closer = bracket_pairs.get(char)
        if closer is not None:
            stack.append((closer, index))
        elif stack and char == stack[-1][0]:
            _expected, start = stack.pop()
            changes[start + 1] += 1
            changes[index] -= 1
    inside = [False] * len(text)
    depth = 0
    for index in range(len(text)):
        depth += changes[index]
        inside[index] = depth > 0
    return inside


def _is_greek_word_character(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x0370 <= codepoint <= 0x037D
        or 0x037F <= codepoint <= 0x0386
        or 0x0388 <= codepoint <= 0x03FF
        or 0x1F00 <= codepoint <= 0x1FFF
        or 0x0300 <= codepoint <= 0x036F
    )


def _atomic_punctuation_end(text: str, end: int) -> int:
    """Extend a rule boundary through the tokenizer's current punctuation atom."""
    apostrophes = frozenset("'’᾽ʼ")
    while end < len(text) and not text[end].isspace():
        char = text[end]
        if _is_greek_word_character(char):
            break
        if (
            char in apostrophes
            and end + 1 < len(text)
            and _is_greek_word_character(text[end + 1])
        ):
            break
        end += 1
    return end


def _rule_boundaries(
    text: str,
    policy: SegmentationPolicy,
    abbreviations: frozenset[str] = _ABBREVIATIONS,
) -> tuple[SentenceBoundary, ...]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    first = _nonspace_start(text, 0)
    if first == len(text):
        return ()
    ends: set[int] = set()
    protected_periods = _protected_periods(text, abbreviations)
    editorial_positions = (
        _balanced_editorial_positions(text) if policy == "papyrus" else []
    )
    terminal = _TERMINAL
    if policy in ("inscription", "papyrus"):
        terminal = frozenset(".!?")
    index = first
    while index < len(text):
        char = text[index]
        if char == "." and index in protected_periods:
            index += 1
            continue
        if policy == "papyrus" and char in _TERMINAL and editorial_positions[index]:
            index += 1
            continue
        if char in terminal:
            end = index + 1
            while end < len(text) and text[end] in terminal:
                end += 1
            while end < len(text) and text[end] in _TRAILING_CLOSERS:
                end += 1
            end = _atomic_punctuation_end(text, end)
            ends.add(end)
            index = end
            continue
        index += 1
    if policy == "verse":
        line_start = 0
        for line in text.splitlines(keepends=True):
            content_start = _nonspace_start(text, line_start)
            line_end = line_start + len(line.rstrip("\r\n").rstrip())
            if line_end > content_start:
                ends.add(line_end)
            line_start += len(line)
    ordered_ends = sorted(end for end in ends if end > first)
    boundaries: list[SentenceBoundary] = []
    start = first
    for end in ordered_ends:
        if end <= start:
            continue
        boundaries.append(SentenceBoundary(start, end, policy=policy, provenance="rule"))
        start = _nonspace_start(text, end)
        if start >= len(text):
            break
    if start < len(text):
        boundaries.append(SentenceBoundary(start, len(text.rstrip()), policy=policy, provenance="rule"))
    return tuple(boundaries)


@dataclass(frozen=True, slots=True, init=False)
class RuleBasedSentenceSegmenter:
    """Conservative built-in segmenter with a named domain policy."""

    policy: SegmentationPolicy
    abbreviations: frozenset[str]

    def __init__(
        self,
        policy: SegmentationPolicy = "default",
        *,
        abbreviations: Sequence[str] | None = None,
    ) -> None:
        object.__setattr__(self, "policy", _policy_name(policy))
        if isinstance(abbreviations, (str, bytes)):
            raise TypeError("abbreviations must be a sequence of strings, not one string")
        raw_extra = () if abbreviations is None else abbreviations
        if any(not isinstance(item, str) or not item for item in raw_extra):
            raise TypeError("abbreviations must contain non-empty strings")
        extra = frozenset(item.casefold().rstrip(".") for item in raw_extra)
        if any(not item or any(char.isspace() for char in item) for item in extra):
            raise ValueError("abbreviations must contain word-like non-empty values")
        object.__setattr__(self, "abbreviations", _ABBREVIATIONS | extra)

    def segment(self, text: str) -> SegmentationResult:
        return SegmentationResult(
            text,
            _rule_boundaries(text, self.policy, self.abbreviations),
            policy=self.policy,
            provenance="rule",
        )


def validate_segmentation_result(
    text: str,
    value: SegmentationResult | Sequence[Any] | Mapping[str, Any],
    *,
    policy: str = "default",
    plugin_policy_id: str = PLUGIN_POLICY_ID,
) -> SegmentationResult:
    """Normalize and adversarially validate a plugin's output before use."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if (
        not isinstance(plugin_policy_id, str)
        or not plugin_policy_id
        or plugin_policy_id in POLICY_IDS.values()
    ):
        plugin_policy_id = PLUGIN_POLICY_ID
    if isinstance(value, SegmentationResult):
        if value.source != text:
            raise ValueError("segmenter returned a result for a different source")
        supplied_policy_id = value.policy_id
        result_policy_id = (
            supplied_policy_id
            if isinstance(supplied_policy_id, str)
            and supplied_policy_id
            and supplied_policy_id not in POLICY_IDS.values()
            and supplied_policy_id != PLUGIN_POLICY_ID
            else plugin_policy_id
        )
        boundaries = tuple(
            SentenceBoundary(
                boundary.start,
                boundary.end,
                policy=value.policy,
                provenance="plugin",
                confidence=boundary.confidence,
                policy_id=result_policy_id,
            )
            for boundary in value.boundaries
        )
        return SegmentationResult(
            text,
            boundaries,
            policy=value.policy,
            provenance="plugin",
            policy_id=result_policy_id,
        )
    raw: Any = value
    result_policy = policy
    if isinstance(value, Mapping):
        if set(value) - {"source", "boundaries", "segments", "policy", "provenance", "policy_id"}:
            raise ValueError("segmenter result contains unknown fields")
        if "boundaries" in value and "segments" in value:
            raise ValueError("segmenter result cannot contain both boundaries and segments")
        if value.get("source", text) != text:
            raise ValueError("segmenter returned a result for a different source")
        raw = value.get("boundaries", value.get("segments"))
        result_policy = value.get("policy", policy)
        raw_provenance = value.get("provenance", "plugin")
        if raw_provenance not in ("rule", "explicit", "plugin"):
            raise ValueError("invalid segmenter provenance")
        supplied_policy_id = value.get("policy_id")
        if supplied_policy_id in POLICY_IDS.values() or supplied_policy_id is None:
            result_policy_id = plugin_policy_id
        elif not isinstance(supplied_policy_id, str) or not supplied_policy_id:
            raise ValueError("invalid plugin policy_id")
        else:
            result_policy_id = supplied_policy_id
    else:
        result_policy_id = plugin_policy_id
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise TypeError("segmenter must return a SegmentationResult or boundary sequence")
    normalized_boundaries: list[SentenceBoundary] = []
    for item in raw:
        if isinstance(item, SentenceBoundary):
            boundary = SentenceBoundary(
                item.start,
                item.end,
                policy=result_policy,
                provenance="plugin",
                confidence=item.confidence,
                policy_id=result_policy_id,
            )
        elif isinstance(item, Mapping):
            allowed = {
                "start", "end", "start_char", "end_char", "policy", "provenance",
                "confidence", "policy_id",
            }
            if set(item) - allowed:
                raise ValueError("segmenter boundary contains unknown fields")
            start = item.get("start", item.get("start_char"))
            end = item.get("end", item.get("end_char"))
            if start is None or end is None:
                raise ValueError("segmenter boundary requires start and end")
            item_policy = item.get("policy", result_policy)
            if item_policy != result_policy:
                raise ValueError("plugin boundary policy must match the result policy")
            supplied_boundary_policy_id = item.get("policy_id")
            if supplied_boundary_policy_id is not None and (
                not isinstance(supplied_boundary_policy_id, str)
                or not supplied_boundary_policy_id
            ):
                raise ValueError("invalid plugin policy_id")
            boundary = SentenceBoundary(
                start,
                end,
                policy=result_policy,
                provenance="plugin",
                confidence=item.get("confidence"),
                policy_id=result_policy_id,
            )
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            if len(item) not in (2, 3, 4):
                raise ValueError("tuple boundaries must contain start, end, and optional metadata")
            tuple_policy = result_policy
            confidence: Any = None
            if len(item) == 3:
                if isinstance(item[2], str):
                    tuple_policy = item[2]
                else:
                    confidence = item[2]
            elif len(item) == 4:
                if not isinstance(item[2], str):
                    raise TypeError("four-item tuple boundaries require a string policy")
                tuple_policy = item[2]
                confidence = item[3]
            if tuple_policy != result_policy:
                raise ValueError("plugin boundary policy must match the result policy")
            boundary = SentenceBoundary(
                item[0], item[1],
                policy=result_policy,
                confidence=confidence,
                provenance="plugin",
                policy_id=result_policy_id,
            )
        else:
            raise TypeError("segmenter boundaries must be typed objects, mappings, or pairs")
        normalized_boundaries.append(boundary)
    return SegmentationResult(
        text,
        tuple(normalized_boundaries),
        policy=result_policy,
        provenance="plugin",
        policy_id=result_policy_id,
    )


def segment_text(
    text: str,
    *,
    policy: str = "default",
    segmenter: SegmenterLike | None = None,
) -> SegmentationResult:
    """Segment text with a built-in policy or caller-supplied plugin."""
    selected = _policy_name(policy)
    if segmenter is None:
        return RuleBasedSentenceSegmenter(selected).segment(text)
    if type(segmenter) is RuleBasedSentenceSegmenter:
        return segmenter.segment(text)
    try:
        callback = getattr(segmenter, "segment", None)
    except Exception as exc:
        raise ValueError(f"sentence segmenter discovery failed: {exc}") from exc
    if callback is None and callable(segmenter):
        callback = segmenter
    if callback is None or not callable(callback):
        raise TypeError("segmenter must implement segment(text) or be callable")
    try:
        raw = callback(text)
    except Exception as exc:
        raise ValueError(f"sentence segmenter failed: {exc}") from exc
    try:
        plugin_policy_id = getattr(segmenter, "policy_id", None)
    except Exception as exc:
        raise ValueError(f"sentence segmenter policy identity failed: {exc}") from exc
    if not isinstance(plugin_policy_id, str) or not plugin_policy_id or plugin_policy_id in POLICY_IDS.values():
        plugin_policy_id = PLUGIN_POLICY_ID
    return validate_segmentation_result(
        text,
        raw,
        policy=selected,
        plugin_policy_id=plugin_policy_id,
    )


def segment_sentences(
    text: str,
    *,
    policy: str = "default",
    segmenter: SegmenterLike | None = None,
) -> SegmentationResult:
    """Compatibility spelling for :func:`segment_text`."""
    return segment_text(text, policy=policy, segmenter=segmenter)


__all__ = [
    "BoundaryProvenance",
    "POLICY_RULES",
    "POLICY_IDS",
    "PLUGIN_POLICY_ID",
    "RuleBasedSentenceSegmenter",
    "SegmentationPolicy",
    "SegmenterLike",
    "SegmentationResult",
    "SentenceBoundary",
    "SentenceSegmenter",
    "segment_sentences",
    "segment_text",
    "validate_segmentation_result",
]
