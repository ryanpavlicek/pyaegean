"""Stdlib-only, lossless interoperability core.

The adapters in this package all use :class:`InteropDocument` as their structural
source.  CoNLL-U parsing and writing deliberately remain delegated to
``aegean.greek.ud``; this module only carries the metadata that CoNLL-U cannot
represent and provides a small, SHA-256-bound JSON sidecar format.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Generic, Iterable, Mapping, TypeVar, cast

from ..core.model import SourceAlignment, TokenFormState
from ..core.provenance import Provenance
from ..greek.confidence import SentenceConfidence, TokenConfidence
from ..greek.lemmatize import LemmaSource
from ..greek.neural_contract import AnalysisReceipt
from ..greek.pipeline import TokenRecord
from ..greek.ud import UDDocument, UDSentence, UDToken, load_conllu_document

__all__ = [
    "InteropError", "InteropDependencyError", "InteropSchemaError", "InteropLossError",
    "InteropReport", "InteropResult", "InteropTokenMetadata", "InteropSentenceMetadata",
    "InteropDocument", "from_ud_document", "from_token_records", "to_conllu",
    "from_conllu", "encode_sidecar", "decode_sidecar", "SIDECAR_COMMENT_PREFIX",
]

SCHEMA = "aegean.interop/v1"
SIDECAR_COMMENT_PREFIX = "# aegean.interop = "
# A decoded sidecar is kept comfortably below typical line/document limits.  The
# same bound is enforced by the writer, so a strict reader never rejects our output.
MAX_SIDECAR_BYTES = 8 * 1024 * 1024

# CoNLL-U line boundaries are the ASCII newlines only.  The Unicode line
# separators U+2028, U+2029 and U+0085 (plus U+000B, U+000C, U+001C-U+001E)
# are ordinary characters here: they can appear literally inside the sidecar
# JSON (encoded with ensure_ascii=False), so ``str.splitlines`` would split the
# single sidecar comment mid-JSON and make the writer emit output its own
# reader rejects.
_CONLLU_NEWLINE_RE = re.compile(r"\r\n|\r|\n")


def _partition_sidecar_comments(raw: str) -> tuple[list[str], str]:
    """Split interop sidecar comment lines from the native CoNLL-U text.

    Returns the decoded sidecar payloads (prefix stripped) and the native text
    with those comment lines removed, reconstructed byte for byte.  Splitting is
    on ASCII newlines only (see ``_CONLLU_NEWLINE_RE``).
    """
    sidecars: list[str] = []
    native_parts: list[str] = []
    position = 0
    for match in _CONLLU_NEWLINE_RE.finditer(raw):
        line = raw[position:match.start()]
        if line.startswith(SIDECAR_COMMENT_PREFIX):
            sidecars.append(line[len(SIDECAR_COMMENT_PREFIX):])
        else:
            native_parts.append(line + match.group(0))
        position = match.end()
    tail = raw[position:]
    if tail.startswith(SIDECAR_COMMENT_PREFIX):
        sidecars.append(tail[len(SIDECAR_COMMENT_PREFIX):])
    elif tail:
        native_parts.append(tail)
    return sidecars, "".join(native_parts)


def _native_signature(raw: str) -> str:
    """Canonical JSON signature for the exact native projection."""
    return json.dumps({"conllu": raw}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class InteropError(Exception):
    """Base class for interoperability failures."""


class InteropDependencyError(InteropError):
    """An optional target dependency is not installed."""


class InteropSchemaError(InteropError):
    """Malformed, unsupported, or tampered interchange data."""


class InteropLossError(InteropError):
    """A strict conversion would lose information."""


@dataclass(frozen=True, slots=True)
class InteropReport:
    native_fields: tuple[str, ...] = ()
    sidecar_fields: tuple[str, ...] = ()
    lost_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    omitted_ids: tuple[str, ...] = ()
    target: str = ""
    version: str | None = None
    schema: str = SCHEMA
    direction: str = ""

    def __post_init__(self) -> None:
        for name in ("native_fields", "sidecar_fields", "lost_fields", "warnings", "omitted_ids"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)):
                raise TypeError(f"{name} must be a sequence of strings")
            try:
                values = tuple(value)
            except TypeError as exc:
                raise TypeError(f"{name} must be a sequence of strings") from exc
            if any(not isinstance(item, str) for item in values):
                raise TypeError(f"{name} must be a sequence of strings")
            if len(set(values)) != len(values):
                raise InteropSchemaError(f"{name} must not contain duplicates")
            object.__setattr__(self, name, values)
        classified = (
            set(self.native_fields),
            set(self.sidecar_fields),
            set(self.lost_fields),
        )
        if any(left & right for index, left in enumerate(classified) for right in classified[index + 1:]):
            raise InteropSchemaError(
                "native_fields, sidecar_fields, and lost_fields must be disjoint"
            )
        if not isinstance(self.target, str) or not self.target:
            raise TypeError("target must be a non-empty string")
        if self.version is not None and (not isinstance(self.version, str) or not self.version):
            raise TypeError("version must be a non-empty string or None")
        if not isinstance(self.direction, str) or not self.direction:
            raise TypeError("direction must be a non-empty string")
        if self.direction not in {"export", "import"}:
            raise InteropSchemaError("direction must be 'export' or 'import'")
        if self.schema != SCHEMA:
            raise InteropSchemaError(f"unsupported interop report schema {self.schema!r}")

    @property
    def target_version(self) -> str | None:
        return self.version

    @property
    def lossless(self) -> bool:
        return not self.lost_fields

    def to_dict(self) -> dict[str, Any]:
        return {
            "native_fields": list(self.native_fields),
            "sidecar_fields": list(self.sidecar_fields),
            "lost_fields": list(self.lost_fields),
            "warnings": list(self.warnings),
            "omitted_ids": list(self.omitted_ids),
            "target": self.target,
            "version": self.version,
            "target_version": self.version,
            "schema": self.schema,
            "direction": self.direction,
            "lossless": self.lossless,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InteropReport":
        _expect_keys(value, {"native_fields", "sidecar_fields", "lost_fields", "warnings", "omitted_ids", "target", "version", "target_version", "schema", "direction", "lossless"}, "interop report")
        if value["version"] != value["target_version"]:
            raise InteropSchemaError("report version and target_version disagree")
        if not isinstance(value["lossless"], bool):
            raise InteropSchemaError("report lossless must be boolean")
        try:
            report = cls(
                value["native_fields"],
                value["sidecar_fields"],
                value["lost_fields"],
                value["warnings"],
                value["omitted_ids"],
                value["target"],
                value["version"],
                value["schema"],
                value["direction"],
            )
        except (TypeError, ValueError) as exc:
            raise InteropSchemaError(f"invalid interop report: {exc}") from exc
        if bool(value["lossless"]) != report.lossless:
            raise InteropSchemaError("report lossless flag disagrees with lost_fields")
        return report


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class InteropResult(Generic[T]):
    value: T
    sidecar: str | None
    report: InteropReport

    @property
    def document(self) -> T:
        """Compatibility alias used by adapter callers."""
        return self.value

    def to_dict(self) -> dict[str, Any]:
        value = self.value.to_dict() if hasattr(self.value, "to_dict") else self.value
        return {"value": value, "sidecar": self.sidecar, "report": self.report.to_dict()}


@dataclass(frozen=True, slots=True)
class InteropTokenMetadata:
    alignment: SourceAlignment | None = None
    form_state: TokenFormState | None = None
    lemma_source: LemmaSource | str | None = None
    lemma_source_path: str | None = None
    confidence: TokenConfidence | None = None
    analysis_receipt: AnalysisReceipt | None = None
    # Optional native projection values from TokenRecord.  CoNLL-U has no
    # representation for ``None`` on these fields; retaining them here prevents
    # an absent value from being fabricated as ``_``/root on a round trip.
    head: int | None = None
    relation: str | None = None
    xpos: str | None = None
    feats: str | None = None
    upos_confidence: float | None = None
    lemma_confidence: float | None = None
    neural_analyzed: bool | None = None
    analysis_complete: bool | None = None
    analysis_warning: str | None = None

    def __post_init__(self) -> None:
        if self.alignment is not None and not isinstance(self.alignment, SourceAlignment):
            raise TypeError("alignment must be SourceAlignment or None")
        if self.form_state is not None and not isinstance(self.form_state, TokenFormState):
            raise TypeError("form_state must be TokenFormState or None")
        if self.lemma_source is not None:
            if isinstance(self.lemma_source, str):
                try:
                    object.__setattr__(self, "lemma_source", LemmaSource(self.lemma_source))
                except ValueError:
                    # Preserve forward-compatible opaque profile labels, while still
                    # retaining ordinary LemmaSource values as their typed enum.
                    pass
            elif not isinstance(self.lemma_source, LemmaSource):
                raise TypeError("lemma_source must be a LemmaSource, string, or None")
        if self.lemma_source_path is not None and not isinstance(self.lemma_source_path, str):
            raise TypeError("lemma_source_path must be a string or None")
        if self.confidence is not None and not isinstance(self.confidence, TokenConfidence):
            raise TypeError("confidence must be TokenConfidence or None")
        if self.analysis_receipt is not None and not isinstance(self.analysis_receipt, AnalysisReceipt):
            raise TypeError("analysis_receipt must be AnalysisReceipt or None")
        if self.head is not None and (not isinstance(self.head, int) or isinstance(self.head, bool) or self.head < 0):
            raise ValueError("head must be a non-negative integer or None")
        for name in ("relation", "xpos", "feats", "analysis_warning"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string or None")
        for name in ("upos_confidence", "lemma_confidence"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0):
                raise ValueError(f"{name} must be a finite confidence in [0, 1]")
        for name in ("neural_analyzed", "analysis_complete"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{name} must be a boolean or None")

    def to_dict(self) -> dict[str, Any]:
        return {
            "alignment": _alignment_dict(self.alignment),
            "form_state": None if self.form_state is None else self.form_state.to_dict(),
            "lemma_source": None if self.lemma_source is None else str(self.lemma_source.value if isinstance(self.lemma_source, Enum) else self.lemma_source),
            "lemma_source_path": self.lemma_source_path,
            "confidence": None if self.confidence is None else self.confidence.to_dict(),
            "analysis_receipt": None if self.analysis_receipt is None else self.analysis_receipt.to_dict(),
            "head": self.head, "relation": self.relation, "xpos": self.xpos, "feats": self.feats,
            "upos_confidence": self.upos_confidence, "lemma_confidence": self.lemma_confidence,
            "neural_analyzed": self.neural_analyzed, "analysis_complete": self.analysis_complete,
            "analysis_warning": self.analysis_warning,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InteropTokenMetadata":
        _expect_keys(value, {"alignment", "form_state", "lemma_source", "lemma_source_path", "confidence", "analysis_receipt", "head", "relation", "xpos", "feats", "upos_confidence", "lemma_confidence", "neural_analyzed", "analysis_complete", "analysis_warning"}, "token metadata")
        return cls(
            alignment=_alignment_from_dict(value["alignment"]),
            form_state=None if value["form_state"] is None else TokenFormState.from_dict(value["form_state"]),
            lemma_source=value["lemma_source"],
            lemma_source_path=value["lemma_source_path"],
            confidence=None if value["confidence"] is None else TokenConfidence.from_dict(value["confidence"]),
            analysis_receipt=None if value["analysis_receipt"] is None else AnalysisReceipt.from_dict(value["analysis_receipt"]),
            head=value["head"], relation=value["relation"], xpos=value["xpos"], feats=value["feats"],
            upos_confidence=value["upos_confidence"], lemma_confidence=value["lemma_confidence"],
            neural_analyzed=value["neural_analyzed"], analysis_complete=value["analysis_complete"],
            analysis_warning=value["analysis_warning"],
        )


@dataclass(frozen=True, slots=True)
class InteropSentenceMetadata:
    confidence: SentenceConfidence | None = None
    boundary_policy: str | None = None
    boundary_policy_id: str | None = None
    boundary_provenance: str | None = None
    boundary_confidence: float | None = None
    boundary_start_char: int | None = None
    boundary_end_char: int | None = None
    analysis_receipt: AnalysisReceipt | None = None

    def __post_init__(self) -> None:
        if self.confidence is not None and not isinstance(self.confidence, SentenceConfidence):
            raise TypeError("confidence must be SentenceConfidence or None")
        if self.analysis_receipt is not None and not isinstance(self.analysis_receipt, AnalysisReceipt):
            raise TypeError("analysis_receipt must be AnalysisReceipt or None")
        for name in ("boundary_policy", "boundary_policy_id", "boundary_provenance"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string or None")
        if self.boundary_confidence is not None and (not isinstance(self.boundary_confidence, (int, float)) or isinstance(self.boundary_confidence, bool) or not math.isfinite(float(self.boundary_confidence))):
            raise ValueError("boundary_confidence must be finite")
        if self.boundary_confidence is not None and not 0.0 <= float(self.boundary_confidence) <= 1.0:
            raise ValueError("boundary_confidence must be in [0, 1]")
        for name in ("boundary_start_char", "boundary_end_char"):
            val = getattr(self, name)
            if val is not None and (not isinstance(val, int) or isinstance(val, bool) or val < 0):
                raise ValueError(f"{name} must be a non-negative integer or None")
        if self.boundary_start_char is not None and self.boundary_end_char is not None and self.boundary_end_char < self.boundary_start_char:
            raise ValueError("boundary_end_char must not precede boundary_start_char")

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": None if self.confidence is None else self.confidence.to_dict(),
            "boundary_policy": self.boundary_policy,
            "boundary_policy_id": self.boundary_policy_id,
            "boundary_provenance": self.boundary_provenance,
            "boundary_confidence": self.boundary_confidence,
            "boundary_start_char": self.boundary_start_char,
            "boundary_end_char": self.boundary_end_char,
            "analysis_receipt": None if self.analysis_receipt is None else self.analysis_receipt.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InteropSentenceMetadata":
        _expect_keys(value, {"confidence", "boundary_policy", "boundary_policy_id", "boundary_provenance", "boundary_confidence", "boundary_start_char", "boundary_end_char", "analysis_receipt"}, "sentence metadata")
        return cls(
            confidence=None if value["confidence"] is None else SentenceConfidence.from_dict(value["confidence"]),
            boundary_policy=value["boundary_policy"], boundary_policy_id=value["boundary_policy_id"],
            boundary_provenance=value["boundary_provenance"], boundary_confidence=value["boundary_confidence"],
            boundary_start_char=value["boundary_start_char"], boundary_end_char=value["boundary_end_char"],
            analysis_receipt=None if value["analysis_receipt"] is None else AnalysisReceipt.from_dict(value["analysis_receipt"]),
        )


@dataclass(frozen=True, slots=True)
class InteropDocument:
    ud_document: UDDocument
    source_text: str | None = None
    document_id: str | None = None
    token_metadata: Mapping[tuple[str, int], InteropTokenMetadata] = field(default_factory=dict)
    sentence_metadata: Mapping[str, InteropSentenceMetadata] = field(default_factory=dict)
    annotation_profile: str | None = None
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ud_document, UDDocument):
            raise TypeError("ud_document must be a UDDocument")
        if self.source_text is not None and not isinstance(self.source_text, str):
            raise TypeError("source_text must be a string or None")
        if self.document_id is not None and (not isinstance(self.document_id, str) or not self.document_id):
            raise TypeError("document_id must be a non-empty string or None")
        if self.annotation_profile is not None and not isinstance(self.annotation_profile, str):
            raise TypeError("annotation_profile must be a string or None")
        tokens: dict[tuple[str, int], InteropTokenMetadata] = {}
        for key, metadata in dict(self.token_metadata).items():
            if not isinstance(key, tuple) or len(key) != 2 or not isinstance(key[0], str) or not isinstance(key[1], int) or isinstance(key[1], bool) or key[1] <= 0:
                raise TypeError("token metadata keys must be (sentence ID, positive integer UD word ID)")
            if not isinstance(metadata, InteropTokenMetadata):
                raise TypeError("token metadata values must be InteropTokenMetadata")
            tokens[(key[0], key[1])] = metadata
        sentences: dict[str, InteropSentenceMetadata] = {}
        for sentence_key, sentence_value in dict(self.sentence_metadata).items():
            if not isinstance(sentence_key, str) or not isinstance(sentence_value, InteropSentenceMetadata):
                raise TypeError("sentence metadata must map string IDs to InteropSentenceMetadata")
            sentences[sentence_key] = sentence_value
        object.__setattr__(self, "token_metadata", MappingProxyType(tokens))
        object.__setattr__(self, "sentence_metadata", MappingProxyType(sentences))
        if self.provenance is not None and not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be Provenance or None")
        sentence_ids = [sentence.sent_id for sentence in self.ud_document.sentences]
        if any(not isinstance(sent_id, str) or not sent_id for sent_id in sentence_ids):
            raise InteropSchemaError("sentence IDs must be non-empty strings")
        if len(set(sentence_ids)) != len(sentence_ids):
            raise InteropSchemaError("duplicate sentence ID")
        for sentence in self.ud_document.sentences:
            word_ids = [token.id for token in sentence.tokens]
            if word_ids != list(range(1, len(word_ids) + 1)):
                raise InteropSchemaError("UD word IDs must be positive and contiguous")
            for token in sentence.tokens:
                if token.head < 0 or token.head > len(word_ids):
                    raise InteropSchemaError("basic HEAD lies outside its sentence")
                if token.head == token.id:
                    raise InteropSchemaError("a token cannot be its own HEAD")
            heads = {token.id: token.head for token in sentence.tokens}
            for token in sentence.tokens:
                seen: set[int] = set()
                current = token.id
                while heads[current] != 0:
                    if current in seen:
                        raise InteropSchemaError("basic dependency tree contains a cycle")
                    seen.add(current)
                    current = heads[current]
        token_by_key = {(sent.sent_id, tok.id): tok for sent in self.ud_document.sentences for tok in sent.tokens}
        known_keys = set(token_by_key)
        if any(key not in known_keys for key in tokens):
            raise InteropSchemaError("token metadata references a non-existent UD word")
        known_sentences = {sent.sent_id for sent in self.ud_document.sentences}
        if any(key not in known_sentences for key in sentences):
            raise InteropSchemaError("sentence metadata references a non-existent sentence")
        receipts_by_sentence: dict[str, set[AnalysisReceipt]] = {
            sent_id: set() for sent_id in known_sentences
        }
        for (sent_id, _token_id), metadata in tokens.items():
            if metadata.analysis_receipt is not None:
                receipts_by_sentence[sent_id].add(metadata.analysis_receipt)
        for sent_id, sentence_metadata in sentences.items():
            if sentence_metadata.analysis_receipt is not None:
                receipts_by_sentence[sent_id].add(sentence_metadata.analysis_receipt)
        if any(len(receipts) > 1 for receipts in receipts_by_sentence.values()):
            raise InteropSchemaError("analysis receipts must agree within a sentence")
        analysis_receipts = tuple(
            next(iter(receipts)) for receipts in receipts_by_sentence.values() if receipts
        )
        inference_profiles = {receipt.annotation_profile for receipt in analysis_receipts}
        if len(inference_profiles) > 1:
            raise InteropSchemaError(
                "analysis receipts contain more than one annotation profile"
            )
        if self.annotation_profile is not None and any(
            receipt.annotation_profile != self.annotation_profile
            for receipt in analysis_receipts
        ):
            raise InteropSchemaError("annotation_profile disagrees with analysis receipt")
        output_profiles = {
            (
                receipt.output_profile_id,
                receipt.output_profile_sha256,
                receipt.postprocessing,
            )
            for receipt in analysis_receipts
        }
        if len(output_profiles) > 1:
            raise InteropSchemaError(
                "analysis receipts contain more than one output analysis profile"
            )
        alignments: list[SourceAlignment] = []
        for key, metadata in tokens.items():
            if metadata.alignment is None:
                continue
            if self.source_text is None:
                raise InteropSchemaError("alignment metadata requires source_text")
            if self.document_id is None:
                raise InteropSchemaError("alignment metadata requires document_id")
            try:
                metadata.alignment.validate_source(self.source_text, self.document_id)
            except (TypeError, ValueError) as exc:
                raise InteropSchemaError(str(exc)) from exc
            alignments.append(metadata.alignment)
        for (sid, _uid), metadata in tokens.items():
            if metadata.alignment is not None and metadata.alignment.sentence_id != sid:
                raise InteropSchemaError("alignment sentence ID disagrees with metadata key")
        for key, metadata in tokens.items():
            if metadata.head is not None:
                token = token_by_key[key]
                sentence_len = len(next(sentence.tokens for sentence in self.ud_document.sentences if sentence.sent_id == key[0]))
                if metadata.head < 0 or metadata.head > sentence_len:
                    raise InteropSchemaError("metadata HEAD is invalid")
                if metadata.head == key[1]:
                    raise InteropSchemaError("metadata HEAD cannot be self-referential")
                if metadata.head != token.head:
                    raise InteropSchemaError("metadata HEAD disagrees with the UD projection")
            token = token_by_key[key]
            for name, native_value in (
                ("relation", token.deprel),
                ("xpos", token.xpos),
                ("feats", token.feats),
            ):
                value = getattr(metadata, name)
                if value is not None and value != native_value:
                    raise InteropSchemaError(
                        f"metadata {name} disagrees with the UD projection"
                    )
        if self.source_text is not None:
            previous_boundary_end: int | None = None
            for sid, sentence_value in sentences.items():
                start = sentence_value.boundary_start_char
                end = sentence_value.boundary_end_char
                if (start is None) != (end is None):
                    raise InteropSchemaError(
                        f"sentence boundary for {sid!r} requires both start and end"
                    )
                if sentence_value.boundary_end_char is not None and sentence_value.boundary_end_char > len(self.source_text):
                    raise InteropSchemaError(f"sentence boundary for {sid!r} lies outside source_text")
            for sentence in self.ud_document.sentences:
                boundary_metadata = sentences.get(sentence.sent_id)
                if (
                    boundary_metadata is None
                    or boundary_metadata.boundary_start_char is None
                ):
                    continue
                start = boundary_metadata.boundary_start_char
                end = boundary_metadata.boundary_end_char
                assert end is not None
                if previous_boundary_end is not None and start < previous_boundary_end:
                    raise InteropSchemaError("sentence boundaries overlap or are out of order")
                sentence_alignments = [
                    cast(
                        SourceAlignment,
                        tokens[(sentence.sent_id, token.id)].alignment,
                    )
                    for token in sentence.tokens
                    if (sentence.sent_id, token.id) in tokens
                    and tokens[(sentence.sent_id, token.id)].alignment is not None
                ]
                if sentence_alignments and (
                    sentence_alignments[0].start_char < start
                    or sentence_alignments[-1].end_char > end
                ):
                    raise InteropSchemaError(
                        f"sentence boundary for {sentence.sent_id!r} excludes an aligned token"
                    )
                previous_boundary_end = end
        seen_source_ids: set[str] = set()
        for alignment in sorted(alignments, key=lambda item: (item.start_char, item.end_char)):
            if alignment.source_token_id in seen_source_ids:
                raise InteropSchemaError("duplicate source token ID")
            seen_source_ids.add(alignment.source_token_id)
            if alignments and alignment.start_char < 0:
                raise InteropSchemaError("negative alignment offset")
        ordered_alignments = sorted(alignments, key=lambda item: item.start_char)
        alignments_in_ud_order = [
            cast(SourceAlignment, tokens[key].alignment)
            for key in token_by_key
            if key in tokens and tokens[key].alignment is not None
        ]
        for previous_alignment, current_alignment in zip(
            alignments_in_ud_order, alignments_in_ud_order[1:]
        ):
            if current_alignment.start_char < previous_alignment.end_char:
                raise InteropSchemaError(
                    "source alignment order disagrees with UD token order"
                )
        if self.source_text is not None:
            for alignment in ordered_alignments:
                whitespace_start = alignment.start_char
                while (
                    whitespace_start > 0
                    and self.source_text[whitespace_start - 1].isspace()
                ):
                    whitespace_start -= 1
                if (
                    self.source_text[whitespace_start:alignment.start_char]
                    != alignment.whitespace_before
                ):
                    raise InteropSchemaError(
                        "alignment whitespace_before does not match source_text"
                    )
            if len(alignments_in_ud_order) == len(token_by_key) and alignments_in_ud_order:
                first_alignment = alignments_in_ud_order[0]
                if (
                    self.source_text[: first_alignment.start_char]
                    != first_alignment.whitespace_before
                ):
                    raise InteropSchemaError(
                        "first alignment whitespace gap does not match source_text"
                    )
                for previous_alignment, current_alignment in zip(
                    alignments_in_ud_order, alignments_in_ud_order[1:]
                ):
                    if (
                        self.source_text[
                            previous_alignment.end_char : current_alignment.start_char
                        ]
                        != current_alignment.whitespace_before
                    ):
                        raise InteropSchemaError(
                            "alignment whitespace gap does not match source_text"
                        )
        for previous_alignment, current_alignment in zip(
            ordered_alignments, ordered_alignments[1:]
        ):
            if current_alignment.start_char < previous_alignment.end_char:
                raise InteropSchemaError("overlapping source alignments")
            if (
                self.source_text is not None
                and self.source_text[
                    previous_alignment.end_char : current_alignment.start_char
                ].isspace()
                and self.source_text[
                    previous_alignment.end_char : current_alignment.start_char
                ]
                != current_alignment.whitespace_before
            ):
                raise InteropSchemaError("alignment whitespace gap does not match source_text")

    @property
    def document(self) -> UDDocument:
        return self.ud_document

    @property
    def ud(self) -> UDDocument:
        return self.ud_document

    @property
    def sentences(self) -> tuple[UDSentence, ...]:
        return self.ud_document.sentences

    @property
    def text(self) -> str | None:
        return self.source_text

    def has_richer_metadata(self) -> bool:
        # Mapping presence is itself data: an explicitly present all-null token
        # metadata record is distinct from no record at all.
        return bool(_sidecar_fields(self))

    def to_dict(self) -> dict[str, Any]:
        return _document_payload(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InteropDocument":
        # The envelope is also the lossless escape hatch for CoNLL-U rows that
        # a target cannot model (including deliberately retained opaque rows).
        # Its hash and schema have already been validated; reparsing must not
        # discard that round-trip capability by imposing strict UD conformance.
        return _document_from_payload(value, strict=False)


def _alignment_dict(value: SourceAlignment | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {"document_id": value.document_id, "sentence_id": value.sentence_id, "source_token_id": value.source_token_id, "original_text": value.original_text, "start_char": value.start_char, "end_char": value.end_char, "whitespace_before": value.whitespace_before, "normalized_text": value.normalized_text, "normalization_ops": list(value.normalization_ops)}


def _alignment_from_dict(value: Any) -> SourceAlignment | None:
    if value is None:
        return None
    _expect_keys(value, {"document_id", "sentence_id", "source_token_id", "original_text", "start_char", "end_char", "whitespace_before", "normalized_text", "normalization_ops"}, "alignment")
    if not isinstance(value["normalization_ops"], list) or any(not isinstance(item, str) for item in value["normalization_ops"]):
        raise InteropSchemaError("alignment normalization_ops must be an array of strings")
    return SourceAlignment(document_id=value["document_id"], sentence_id=value["sentence_id"], source_token_id=value["source_token_id"], original_text=value["original_text"], start_char=value["start_char"], end_char=value["end_char"], whitespace_before=value["whitespace_before"], normalized_text=value["normalized_text"], normalization_ops=tuple(value["normalization_ops"]))


def _provenance_dict(value: Provenance | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {"source": value.source, "license": value.license, "citation": value.citation, "url": value.url, "schema_version": value.schema_version, "notes": list(value.notes), "data_version": value.data_version, "edition_fidelity": value.edition_fidelity}


def _provenance_from_dict(value: Any) -> Provenance | None:
    if value is None:
        return None
    _expect_keys(value, {"source", "license", "citation", "url", "schema_version", "notes", "data_version", "edition_fidelity"}, "provenance")
    if not isinstance(value["notes"], list) or any(not isinstance(item, str) for item in value["notes"]):
        raise InteropSchemaError("provenance notes must be an array of strings")
    for name in (
        "source",
        "license",
        "citation",
        "url",
        "data_version",
        "edition_fidelity",
    ):
        if not isinstance(value[name], str):
            raise InteropSchemaError(f"provenance {name} must be a string")
    if not isinstance(value["schema_version"], int) or isinstance(
        value["schema_version"], bool
    ):
        raise InteropSchemaError("provenance schema_version must be an integer")
    return Provenance(source=value["source"], license=value["license"], citation=value["citation"], url=value["url"], schema_version=value["schema_version"], notes=tuple(value["notes"]), data_version=value["data_version"], edition_fidelity=value["edition_fidelity"])


def _document_payload(document: InteropDocument) -> dict[str, Any]:
    tokens = [{"sentence_id": sid, "ud_id": uid, "metadata": document.token_metadata[(sid, uid)].to_dict()} for sid, uid in sorted(document.token_metadata)]
    sentences = [{"sent_id": sid, "metadata": document.sentence_metadata[sid].to_dict()} for sid in sorted(document.sentence_metadata)]
    ud_word_keys = {(sent.sent_id, tok.id) for sent in document.ud_document.sentences for tok in sent.tokens}
    token_complete = ud_word_keys == set(document.token_metadata)
    sentence_ids = {sent.sent_id for sent in document.ud_document.sentences}
    sentence_complete = sentence_ids == set(document.sentence_metadata)
    return {"conllu": document.ud_document.dumps(), "source_text": document.source_text, "document_id": document.document_id, "annotation_profile": document.annotation_profile, "provenance": _provenance_dict(document.provenance), "tokens": tokens, "sentences": sentences, "tokens_complete": token_complete, "sentences_complete": sentence_complete}


def _document_from_payload(value: Mapping[str, Any], *, strict: bool = True) -> InteropDocument:
    _expect_keys(value, {"conllu", "source_text", "document_id", "annotation_profile", "provenance", "tokens", "sentences", "tokens_complete", "sentences_complete"}, "interop document")
    if not isinstance(value["conllu"], str):
        raise InteropSchemaError("interop document conllu must be a string")
    ud = load_conllu_document(value["conllu"], strict=strict)
    token_map: dict[tuple[str, int], InteropTokenMetadata] = {}
    if not isinstance(value["tokens"], list):
        raise InteropSchemaError("interop document tokens must be an array")
    for entry in value["tokens"]:
        _expect_keys(entry, {"sentence_id", "ud_id", "metadata"}, "token entry")
        key = (entry["sentence_id"], entry["ud_id"])
        if key in token_map:
            raise InteropSchemaError("duplicate token metadata key")
        token_map[key] = InteropTokenMetadata.from_dict(entry["metadata"])
    sentence_map: dict[str, InteropSentenceMetadata] = {}
    if not isinstance(value["sentences"], list):
        raise InteropSchemaError("interop document sentences must be an array")
    for entry in value["sentences"]:
        _expect_keys(entry, {"sent_id", "metadata"}, "sentence entry")
        if entry["sent_id"] in sentence_map:
            raise InteropSchemaError("duplicate sentence metadata key")
        sentence_map[entry["sent_id"]] = InteropSentenceMetadata.from_dict(entry["metadata"])
    known_keys = {(sent.sent_id, tok.id) for sent in ud.sentences for tok in sent.tokens}
    if any(key not in known_keys for key in token_map):
        raise InteropSchemaError("token metadata references an unknown UD word")
    known_sentences = {sent.sent_id for sent in ud.sentences}
    if any(key not in known_sentences for key in sentence_map):
        raise InteropSchemaError("sentence metadata references an unknown sentence")
    if value["tokens_complete"] is True and set(token_map) != known_keys:
        raise InteropSchemaError("token metadata cardinality does not match UD rows")
    if value["sentences_complete"] is True and set(sentence_map) != known_sentences:
        raise InteropSchemaError("sentence metadata cardinality does not match UD sentences")
    if not isinstance(value["tokens_complete"], bool) or not isinstance(value["sentences_complete"], bool):
        raise InteropSchemaError("metadata completeness flags must be booleans")
    return InteropDocument(ud, value["source_text"], value["document_id"], token_map, sentence_map, value["annotation_profile"], _provenance_from_dict(value["provenance"]))


def from_ud_document(document: UDDocument, *, source_text: str | None = None, document_id: str | None = None, annotation_profile: str | None = None, provenance: Provenance | None = None) -> InteropDocument:
    if not isinstance(document, UDDocument):
        raise TypeError("document must be UDDocument")
    token_metadata: dict[tuple[str, int], InteropTokenMetadata] = {}
    for sent in document.sentences:
        for tok in sent.tokens:
            if tok.form_state is not None:
                token_metadata[(sent.sent_id, tok.id)] = InteropTokenMetadata(form_state=tok.form_state)
    return InteropDocument(document, source_text, document_id, token_metadata, {}, annotation_profile, provenance)


def from_token_records(records: Iterable[TokenRecord], *, source_text: str, document_id: str, provenance: Provenance | None = None, annotation_profile: str | None = None) -> InteropDocument:
    if not isinstance(source_text, str) or not isinstance(document_id, str) or not document_id:
        raise TypeError("source_text and non-empty document_id are required")
    values = tuple(records)
    if not values:
        return InteropDocument(UDDocument(()), source_text, document_id, {}, {}, annotation_profile, provenance)
    groups: dict[int, list[TokenRecord]] = {}
    seen_source_ids: set[str] = set()
    record_positions: list[tuple[int, int]] = []
    for rec in values:
        if not isinstance(rec, TokenRecord):
            raise TypeError("records must contain TokenRecord values")
        if not isinstance(rec.sentence, int) or isinstance(rec.sentence, bool) or rec.sentence < 0 or not isinstance(rec.index, int) or isinstance(rec.index, bool) or rec.index <= 0:
            raise InteropSchemaError("record sentence/index must be non-negative/positive integers")
        if rec.alignment is None:
            raise InteropSchemaError("every TokenRecord requires SourceAlignment")
        try:
            rec.alignment.validate_source(source_text, document_id)
        except (TypeError, ValueError) as exc:
            raise InteropSchemaError(str(exc)) from exc
        if rec.alignment.sentence_id is None:
            raise InteropSchemaError("alignment sentence_id is required")
        if rec.alignment.source_token_id in seen_source_ids:
            raise InteropSchemaError("duplicate source token ID")
        seen_source_ids.add(rec.alignment.source_token_id)
        if rec.text != rec.alignment.normalized_text:
            raise InteropSchemaError("record text must equal its aligned normalized_text")
        record_positions.append((rec.sentence, rec.index))
        groups.setdefault(rec.sentence, []).append(rec)
    if record_positions != sorted(record_positions):
        raise InteropSchemaError("records must be in sentence and token order")
    if tuple(sorted(groups)) != tuple(range(len(groups))):
        raise InteropSchemaError("sentence ordinals must be contiguous starting at zero")
    token_meta: dict[tuple[str, int], InteropTokenMetadata] = {}
    sent_meta: dict[str, InteropSentenceMetadata] = {}
    sentences: list[UDSentence] = []
    for ordinal in sorted(groups):
        rows = sorted(groups[ordinal], key=lambda r: r.index)
        expected = tuple(range(1, len(rows) + 1))
        if tuple(r.index for r in rows) != expected:
            raise InteropSchemaError("token ordinals must be contiguous within each sentence")
        row_alignments: list[SourceAlignment] = []
        for row in rows:
            if row.alignment is None:
                raise InteropSchemaError("every TokenRecord requires SourceAlignment")
            row_alignments.append(row.alignment)
        sid = row_alignments[0].sentence_id
        assert sid is not None
        if any(alignment.sentence_id != sid for alignment in row_alignments):
            raise InteropSchemaError("sentence IDs must agree within a sentence")
        if sid in sent_meta:
            raise InteropSchemaError("duplicate sentence ID")
        starts = [alignment.start_char for alignment in row_alignments]
        ends = [alignment.end_char for alignment in row_alignments]
        for previous, current in zip(row_alignments, row_alignments[1:]):
            if current.start_char < previous.end_char:
                raise InteropSchemaError("source alignments overlap")
            if source_text[previous.end_char:current.start_char] != current.whitespace_before:
                raise InteropSchemaError("alignment whitespace gap does not match source_text")
        boundary_values = tuple((r.boundary_policy, r.boundary_policy_id, r.boundary_provenance, r.boundary_confidence, r.boundary_start_char, r.boundary_end_char) for r in rows if any(v is not None for v in (r.boundary_policy, r.boundary_policy_id, r.boundary_provenance, r.boundary_confidence, r.boundary_start_char, r.boundary_end_char)))
        if len(set(boundary_values)) > 1:
            raise InteropSchemaError("sentence boundary metadata must agree within a sentence")
        receipts = {rec.analysis_receipt for rec in rows}
        if len(receipts) > 1:
            raise InteropSchemaError("analysis receipts must agree within a sentence")
        for rec in rows:
            assert rec.alignment is not None
            if rec.analysis_receipt is not None and annotation_profile is not None and rec.analysis_receipt.annotation_profile != annotation_profile:
                raise InteropSchemaError("annotation_profile disagrees with analysis receipt")
        boundary_source = next((rec for rec in rows if any(v is not None for v in (rec.boundary_policy, rec.boundary_policy_id, rec.boundary_provenance, rec.boundary_confidence, rec.boundary_start_char, rec.boundary_end_char))), rows[0])
        sentence_confidences = {
            row.sentence_confidence
            for row in rows
            if row.sentence_confidence is not None
        }
        if len(sentence_confidences) > 1:
            raise InteropSchemaError("sentence confidence must agree within a sentence")
        sentence_confidence = (
            next(iter(sentence_confidences)) if sentence_confidences else None
        )
        boundary = InteropSentenceMetadata(confidence=sentence_confidence, boundary_policy=boundary_source.boundary_policy, boundary_policy_id=boundary_source.boundary_policy_id, boundary_provenance=boundary_source.boundary_provenance, boundary_confidence=boundary_source.boundary_confidence, boundary_start_char=boundary_source.boundary_start_char, boundary_end_char=boundary_source.boundary_end_char, analysis_receipt=rows[0].analysis_receipt)
        start = boundary.boundary_start_char if boundary.boundary_start_char is not None else min(starts)
        end = boundary.boundary_end_char if boundary.boundary_end_char is not None else max(ends)
        if not (0 <= start <= end <= len(source_text)):
            raise InteropSchemaError("sentence boundary lies outside source_text")
        toks: list[UDToken] = []
        for rec in rows:
            assert rec.alignment is not None
            if rec.head is not None and (not isinstance(rec.head, int) or isinstance(rec.head, bool) or rec.head < 0 or rec.head > len(rows)):
                raise InteropSchemaError("record head must be a valid sentence UD word ID or None")
            if rec.head is not None and rec.head == rec.index:
                raise InteropSchemaError("token cannot be its own head")
            relation = rec.relation if rec.relation is not None else "_"
            # UDToken requires concrete scalar columns.  Missing values are
            # projected to UD's conventional placeholders and the originals are
            # retained in InteropTokenMetadata for a lossless envelope round-trip.
            toks.append(UDToken(rec.index, rec.text, rec.lemma, rec.upos, rec.xpos or "_", rec.feats or "_", rec.head if rec.head is not None else 0, relation))
            token_meta[(sid, rec.index)] = InteropTokenMetadata(rec.alignment, rec.form_state, rec.lemma_source, rec.lemma_source_path, rec.token_confidence, rec.analysis_receipt, rec.head, rec.relation, rec.xpos, rec.feats, rec.upos_confidence, rec.lemma_confidence, rec.neural_analyzed, rec.analysis_complete, rec.analysis_warning)
        sentences.append(UDSentence(sid, source_text[start:end], tuple(toks)))
        sent_meta[sid] = boundary
    if annotation_profile is None:
        profiles = {rec.analysis_receipt.annotation_profile for rec in values if rec.analysis_receipt is not None and rec.analysis_receipt.annotation_profile}
        if len(profiles) == 1:
            annotation_profile = next(iter(profiles))
        elif len(profiles) > 1:
            raise InteropSchemaError(
                "analysis receipts contain more than one annotation profile"
            )
    return InteropDocument(UDDocument(tuple(sentences)), source_text, document_id, token_meta, sent_meta, annotation_profile, provenance)


def _canonical_json(value: Any) -> str:
    try:
        out = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise InteropSchemaError(f"value is not JSON-safe: {exc}") from exc
    if len(out.encode("utf-8")) > MAX_SIDECAR_BYTES:
        raise InteropSchemaError("sidecar exceeds maximum size")
    return out


def _expect_keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise InteropSchemaError(f"{label} has unknown or missing fields")


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in pairs:
        if key in out:
            raise InteropSchemaError(f"duplicate JSON key {key!r}")
        out[key] = val
    return out


def _reject_constant(value: str) -> Any:
    raise InteropSchemaError(f"non-finite JSON number {value}")


def encode_sidecar(document: InteropDocument, *, target: str, native_signature: str) -> str:
    if not isinstance(document, InteropDocument) or not isinstance(target, str) or not target or not isinstance(native_signature, str):
        raise TypeError("document, target, and native_signature have invalid types")
    payload = _document_payload(document)
    payload_json = _canonical_json(payload)
    canonical_document = document.ud_document.dumps(canonical=True)
    envelope = {"schema": SCHEMA, "target": target, "document_sha256": hashlib.sha256(canonical_document.encode("utf-8")).hexdigest(), "payload_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(), "native_sha256": hashlib.sha256(native_signature.encode("utf-8")).hexdigest(), "payload": payload}
    return _canonical_json(envelope)


def decode_sidecar(sidecar: str, *, target: str | None = None, native_signature: str | None = None) -> dict[str, Any]:
    if not isinstance(sidecar, str):
        raise TypeError("sidecar must be a string")
    if len(sidecar.encode("utf-8")) > MAX_SIDECAR_BYTES:
        raise InteropSchemaError("sidecar exceeds maximum size")
    try:
        envelope = json.loads(sidecar, object_pairs_hook=_strict_pairs, parse_constant=_reject_constant)
    except InteropSchemaError:
        raise
    except (TypeError, ValueError, UnicodeError) as exc:
        raise InteropSchemaError("invalid sidecar JSON") from exc
    _expect_keys(envelope, {"schema", "target", "document_sha256", "payload_sha256", "native_sha256", "payload"}, "sidecar")
    if envelope["schema"] != SCHEMA:
        raise InteropSchemaError(f"unsupported sidecar schema {envelope['schema']!r}")
    if not envelope["target"]:
        raise InteropSchemaError("sidecar target must be non-empty")
    if target is not None and envelope["target"] != target:
        raise InteropSchemaError("sidecar target does not match requested target")
    payload = envelope["payload"]
    _expect_keys(payload, {"conllu", "source_text", "document_id", "annotation_profile", "provenance", "tokens", "sentences", "tokens_complete", "sentences_complete"}, "sidecar payload")
    for field_name in ("document_sha256", "payload_sha256", "native_sha256", "target"):
        if not isinstance(envelope[field_name], str):
            raise InteropSchemaError(f"sidecar {field_name} must be a string")
    if not isinstance(payload["conllu"], str):
        raise InteropSchemaError("sidecar payload conllu must be a string")
    try:
        canonical_document = load_conllu_document(payload["conllu"], strict=False).dumps(canonical=True)
    except (TypeError, ValueError) as exc:
        raise InteropSchemaError("sidecar payload contains invalid CoNLL-U") from exc
    if hashlib.sha256(canonical_document.encode("utf-8")).hexdigest() != envelope["document_sha256"]:
        raise InteropSchemaError("sidecar document hash mismatch")
    if hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest() != envelope["payload_sha256"]:
        raise InteropSchemaError("sidecar payload hash mismatch")
    if native_signature is not None and hashlib.sha256(native_signature.encode("utf-8")).hexdigest() != envelope["native_sha256"]:
        raise InteropSchemaError("sidecar native projection hash mismatch")
    # Exercise typed decoding now so malformed values fail at the boundary.
    try:
        _document_from_payload(payload, strict=False)
    except (TypeError, ValueError, InteropError) as exc:
        if isinstance(exc, InteropError):
            raise
        raise InteropSchemaError("invalid typed sidecar payload") from exc
    return cast(dict[str, Any], envelope)


def _sidecar_fields(document: InteropDocument) -> tuple[str, ...]:
    fields: list[str] = []
    if document.source_text is not None:
        fields.append("source_text")
    if document.document_id is not None:
        fields.append("document_id")
    if document.token_metadata:
        fields.append("token_metadata")
        token_values = tuple(document.token_metadata.values())
        for name in (
            "alignment", "form_state", "lemma_source", "lemma_source_path",
            "confidence", "analysis_receipt", "head", "relation", "xpos", "feats",
            "upos_confidence", "lemma_confidence", "neural_analyzed",
            "analysis_complete", "analysis_warning",
        ):
            if any(getattr(metadata, name) is not None for metadata in token_values):
                fields.append(name)
    if document.sentence_metadata:
        fields.append("sentence_metadata")
        sentence_values = tuple(document.sentence_metadata.values())
        if any(metadata.confidence is not None for metadata in sentence_values):
            fields.append("sentence_confidence")
        if any(
            any(
                value is not None
                for value in (
                    metadata.boundary_policy,
                    metadata.boundary_policy_id,
                    metadata.boundary_provenance,
                    metadata.boundary_confidence,
                    metadata.boundary_start_char,
                    metadata.boundary_end_char,
                )
            )
            for metadata in sentence_values
        ):
            fields.append("boundary")
        if any(metadata.analysis_receipt is not None for metadata in sentence_values):
            fields.append("sentence_analysis_receipt")
    if document.annotation_profile is not None:
        fields.append("annotation_profile")
    if document.provenance is not None:
        fields.append("provenance")
    return tuple(fields)


def _adapter_sidecar_fields(
    document: InteropDocument, *, target: str
) -> tuple[str, ...]:
    """Classify only values this target needs the sidecar to retain.

    The public report is deliberately instance-specific: an empty confidence
    field, absent MWT range, or nonexistent provenance record is not advertised
    as sidecar data.  Names describe information classes rather than the JSON
    envelope's implementation fields, so native and sidecar classifications
    remain disjoint even when a target carries a useful reduced projection.
    """
    if target not in {"spacy", "stanza", "cltk"}:
        raise ValueError("target must be spacy, stanza, or cltk")
    fields: list[str] = []
    token_values = tuple(document.token_metadata.values())
    sentence_values = tuple(document.sentence_metadata.values())

    if document.document_id is not None or (
        target == "spacy" and document.source_text is not None
    ):
        fields.append("document_identity")
    if document.token_metadata:
        fields.append("token_metadata")
    if any(value.alignment is not None for value in token_values):
        fields.append("source_alignment")
    if any(value.form_state is not None for value in token_values):
        fields.append("form_state")
    if any(
        value.lemma_source is not None or value.lemma_source_path is not None
        for value in token_values
    ):
        fields.append(
            "lemma_provenance" if target != "cltk" else "complete_lemma_provenance"
        )
    if any(
        value.confidence is not None
        or value.upos_confidence is not None
        or value.lemma_confidence is not None
        for value in token_values
    ) or any(value.confidence is not None for value in sentence_values):
        fields.append("typed_confidence" if target == "cltk" else "confidence")
    if any(value.analysis_receipt is not None for value in token_values) or any(
        value.analysis_receipt is not None for value in sentence_values
    ):
        fields.append("receipts")
    if any(
        value.neural_analyzed is not None
        or value.analysis_complete is not None
        or value.analysis_warning is not None
        for value in token_values
    ):
        fields.append("analysis_state")
    if document.sentence_metadata:
        fields.append("sentence_metadata")
    if document.annotation_profile is not None:
        fields.append("profile")
    if document.provenance is not None:
        fields.append("provenance")
    if target in {"spacy", "cltk"} and document.ud_document.sentences:
        fields.append("sentence_ids")

    sentences = document.ud_document.sentences
    has_mwt = any(sentence.multiword_tokens for sentence in sentences)
    has_empty = any(sentence.empty_nodes for sentence in sentences)
    has_opaque = any(
        type(row).__name__ == "UDOpaqueRow"
        for sentence in sentences
        for row in (sentence.rows or sentence.tokens)
    )
    has_comments = bool(
        document.ud_document.leading_comments
        or document.ud_document.trailing_comments
        or any(sentence.comments for sentence in sentences)
    )
    has_enhanced = any(
        getattr(row, "deps_raw", "_") not in {"", "_"}
        for sentence in sentences
        for row in (sentence.rows or sentence.tokens)
    )
    has_misc = any(
        getattr(row, "misc_raw", "_") not in {"", "_"}
        for sentence in sentences
        for row in (sentence.rows or sentence.tokens)
    )
    if has_mwt and target != "stanza":
        fields.append("MWT")
    elif has_mwt:
        fields.append("MWT_row_state")
    if has_empty:
        fields.append("empty_nodes")
    if has_enhanced and target != "stanza":
        fields.append("enhanced_dependencies")
    if has_misc and target != "stanza":
        fields.append("misc")
    if has_opaque:
        fields.append("opaque_rows")
    if has_comments:
        fields.append("comments")
    if has_mwt or has_empty or has_opaque or has_comments:
        fields.append("row_order")
    # Every framework projection omits CoNLL-U's exact raw row spelling and
    # line-ending state even when it represents all of the linguistic values.
    fields.append("raw_conllu")
    return tuple(fields)


def _adapter_omitted_ids(
    document: InteropDocument, *, target: str
) -> tuple[str, ...]:
    if target not in {"spacy", "stanza", "cltk"}:
        raise ValueError("target must be spacy, stanza, or cltk")
    omitted: list[str] = []
    for sentence in document.ud_document.sentences:
        for row in sentence.rows or sentence.tokens:
            kind = type(row).__name__
            if kind == "UDMultiwordToken" and target == "stanza":
                continue
            if kind not in {"UDMultiwordToken", "UDEmptyNode", "UDOpaqueRow"}:
                continue
            omitted.append(f"{sentence.sent_id}:{row.id}")
    return tuple(omitted)


def _conllu_native_fields(document: InteropDocument) -> tuple[str, ...]:
    sentences = document.ud_document.sentences
    rows = tuple(
        row for sentence in sentences for row in (sentence.rows or sentence.tokens)
    )
    fields: list[str] = ["ud_document", "conllu_rows"]
    if (
        document.ud_document.leading_comments
        or document.ud_document.trailing_comments
        or any(sentence.comments for sentence in sentences)
    ):
        fields.append("comments")
    if any(getattr(row, "raw_columns", ()) for row in rows):
        fields.append("raw_columns")
    if any(type(row).__name__ == "UDMultiwordToken" for row in rows):
        fields.append("mwt")
    if any(type(row).__name__ == "UDEmptyNode" for row in rows):
        fields.append("empty_nodes")
    if any(getattr(row, "deps_raw", "_") not in {"", "_"} for row in rows):
        fields.append("enhanced_dependencies")
    if any(getattr(row, "misc_raw", "_") not in {"", "_"} for row in rows):
        fields.append("misc")
    if any(type(row).__name__ == "UDOpaqueRow" for row in rows):
        fields.append("opaque_rows")
    return tuple(fields)


def _report(document: InteropDocument, *, target: str, direction: str, sidecar: bool, lost: Iterable[str] = (), omitted: Iterable[str] = ()) -> InteropReport:
    native = _conllu_native_fields(document)
    side = _sidecar_fields(document) if sidecar else ()
    return InteropReport(native, side, tuple(lost), (), tuple(omitted), target, "2" if target == "conllu" else None, SCHEMA, direction)


def to_conllu(document: InteropDocument, *, include_sidecar: bool = True, allow_lossy: bool = False) -> InteropResult[str]:
    if not isinstance(document, InteropDocument):
        raise TypeError("document must be InteropDocument")
    native = document.ud_document.dumps()
    richer = document.has_richer_metadata()
    sidecar: str | None = None
    output = native
    if richer and not include_sidecar and not allow_lossy:
        raise InteropLossError("CoNLL-U projection omits envelope metadata; request include_sidecar=True or allow_lossy=True")
    if include_sidecar and richer:
        sidecar = encode_sidecar(document, target="conllu", native_signature=_native_signature(native))
        newline = "\r\n" if "\r\n" in native else "\n"
        output = SIDECAR_COMMENT_PREFIX + sidecar + newline + native
    lost = () if sidecar or not richer else _sidecar_fields(document)
    report = _report(document, target="conllu", direction="export", sidecar=bool(sidecar), lost=lost)
    return InteropResult(output, sidecar, report)


def from_conllu(
    source: str | Path, *, strict: bool = True
) -> InteropResult[InteropDocument]:
    try:
        if isinstance(source, Path):
            with source.open("r", encoding="utf-8", newline="") as handle:
                raw = handle.read()
        else:
            raw = source
        # The sidecar comment is transport metadata, not part of the native
        # document.  It is removed before parsing so its hash binds the exact
        # canonical CoNLL-U projection that was exported.
        sidecars, native_raw = _partition_sidecar_comments(raw)
        if len(sidecars) > 1:
            raise InteropSchemaError("duplicate interop sidecar comments")
        ud = load_conllu_document(native_raw, strict=False if sidecars else strict)
    except (OSError, TypeError, ValueError) as exc:
        raise InteropSchemaError(str(exc)) from exc
    if not sidecars:
        value = from_ud_document(ud)
        return InteropResult(value, None, _report(value, target="conllu", direction="import", sidecar=False))
    canonical_native = ud.dumps(canonical=True)
    envelope = decode_sidecar(sidecars[0], target="conllu", native_signature=_native_signature(native_raw))
    payload = envelope["payload"]
    try:
        value = _document_from_payload(payload, strict=False)
    except (TypeError, ValueError, InteropError) as exc:
        if isinstance(exc, InteropError):
            raise
        raise InteropSchemaError("invalid typed sidecar payload") from exc
    # The sidecar payload is bound to this exact parsed document, not a second one.
    if value.ud_document.dumps(canonical=True) != canonical_native:
        raise InteropSchemaError("sidecar payload document differs from native CoNLL-U")
    return InteropResult(value, sidecars[0], _report(value, target="conllu", direction="import", sidecar=True))
