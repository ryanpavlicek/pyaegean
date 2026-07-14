"""Loss-aware interoperability with the current supported CLTK 2.5 API."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from importlib import metadata as importlib_metadata
from typing import Any

from .interop import (
    InteropDependencyError,
    InteropDocument,
    InteropLossError,
    InteropReport,
    InteropResult,
    InteropSchemaError,
    InteropSentenceMetadata,
    InteropTokenMetadata,
    _adapter_omitted_ids,
    _adapter_sidecar_fields,
    decode_sidecar,
    encode_sidecar,
)

__all__ = ["to_cltk", "from_cltk", "make_cltk_process"]

_SIDECAR_KEY = "aegean.interop/v1"
_PROCESS_ID = "aegean.cltk"
_MAPPED_DOC_FIELDS = frozenset(
    {"language", "words", "raw", "sentence_boundaries", "metadata"}
)
_MAPPED_WORD_FIELDS = frozenset(
    {
        "index_token",
        "index_sentence",
        "string",
        "lemma",
        "upos",
        "features",
        "dependency_relation",
        "governor",
        "xpos",
        "annotation_sources",
        "confidence",
    }
)
_LOSSY_IMPORT_FIELDS = (
    "document_identity",
    "source_alignment",
    "form_state",
    "receipts",
    "analysis_state",
    "sentence_metadata",
    "profile",
    "provenance",
    "sentence_ids",
    "MWT",
    "empty_nodes",
    "enhanced_dependencies",
    "misc",
    "opaque_rows",
    "comments",
    "row_order",
    "raw_conllu",
)


def _dependency_error() -> InteropDependencyError:
    return InteropDependencyError(
        "CLTK is required for this adapter; install it with "
        "pip install 'pyaegean[cltk]'"
    )


def _require_cltk() -> tuple[Any, Any, Any]:
    try:
        from cltk.core.data_types import Doc, Language, Word
    except Exception as exc:  # broken optional installs need the same clean hint
        raise _dependency_error() from exc
    return Doc, Language, Word


def _require_ancient_greek(doc: Any) -> None:
    language = getattr(doc, "language", None)
    if getattr(language, "glottolog_id", None) != "grc":
        raise InteropSchemaError("CLTK document language must be Ancient Greek (grc)")


def _version() -> str:
    try:
        return importlib_metadata.version("cltk")
    except importlib_metadata.PackageNotFoundError as exc:
        raise _dependency_error() from exc


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, (Mapping, list, tuple, set, frozenset)):
        return bool(len(value))
    return True


def _validated_sentence_lengths(words: Any) -> dict[int, int]:
    positions: list[tuple[int, int]] = []
    grouped: dict[int, list[int]] = {}
    for word in words:
        if not isinstance(word.string, str) or not word.string:
            raise InteropSchemaError("CLTK word string must be non-empty")
        sentence_index = word.index_sentence
        token_index = word.index_token
        if (
            not isinstance(sentence_index, int)
            or isinstance(sentence_index, bool)
            or sentence_index < 0
        ):
            raise InteropSchemaError(
                "CLTK word index_sentence must be a non-negative integer"
            )
        if (
            not isinstance(token_index, int)
            or isinstance(token_index, bool)
            or token_index < 0
        ):
            raise InteropSchemaError(
                "CLTK word index_token must be a non-negative integer"
            )
        positions.append((sentence_index, token_index))
        grouped.setdefault(sentence_index, []).append(token_index)
    if positions != sorted(positions):
        raise InteropSchemaError("CLTK words are not in sentence and token order")
    if tuple(grouped) != tuple(range(len(grouped))):
        raise InteropSchemaError(
            "CLTK sentence indices must be contiguous starting at zero"
        )
    for indices in grouped.values():
        if indices != list(range(len(indices))):
            raise InteropSchemaError(
                "CLTK token indices must be contiguous within a sentence"
            )
    return {sentence: len(indices) for sentence, indices in grouped.items()}


def _jsonable(value: Any, *, path: str = "cltk") -> Any:
    """Convert public CLTK state to deterministic JSON without ``repr`` fallback."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return _jsonable(value.value, path=path)
    if isinstance(value, (date, datetime)):
        return {
            "__type__": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": value.isoformat(),
        }
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            if not isinstance(key, (str, int)) or isinstance(key, bool):
                raise InteropSchemaError(f"{path} contains a non-scalar mapping key")
            text_key = str(key)
            if text_key in result:
                raise InteropSchemaError(f"{path} contains colliding mapping keys")
            result[text_key] = _jsonable(item, path=f"{path}.{text_key}")
        return result
    if isinstance(value, (list, tuple)):
        return [
            _jsonable(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, (set, frozenset)):
        encoded = [_jsonable(item, path=f"{path}[]") for item in value]
        return sorted(
            encoded,
            key=lambda item: json.dumps(
                item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        )
    fields = getattr(type(value), "model_fields", None)
    if isinstance(fields, Mapping):
        return {
            "__type__": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": {
                name: _jsonable(getattr(value, name), path=f"{path}.{name}")
                for name in fields
            },
        }
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _jsonable(tolist(), path=path)
    item = getattr(value, "item", None)
    if callable(item):
        return _jsonable(item(), path=path)
    raise InteropSchemaError(
        f"{path} contains unsupported native value {type(value).__name__}"
    )


def _cltk_native_state(doc: Any) -> dict[str, Any]:
    """Return all public CLTK document fields, excluding only our sidecar value."""
    fields = getattr(type(doc), "model_fields", None)
    if not isinstance(fields, Mapping):
        raise InteropSchemaError("doc must be a current CLTK Doc")
    state: dict[str, Any] = {}
    for name in fields:
        value = getattr(doc, name)
        if name == "metadata":
            if not isinstance(value, Mapping):
                raise InteropSchemaError("CLTK Doc.metadata must be a mapping")
            value = {key: item for key, item in value.items() if key != _SIDECAR_KEY}
        state[name] = _jsonable(value, path=f"cltk.{name}")
    return state


def _canonical_native_state(doc: Any) -> str:
    try:
        return json.dumps(
            _cltk_native_state(doc),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise InteropSchemaError(f"CLTK native state is not JSON-safe: {exc}") from exc


def _native_fields(doc: Any) -> tuple[str, ...]:
    words = tuple(doc.words or ())
    fields: list[str] = ["language"]
    if doc.raw is not None:
        fields.append("raw_text")
    if doc.normalized_text is not None:
        fields.append("normalized_text")
    if doc.sentence_boundaries:
        fields.append("sentence_boundaries")
    if words:
        fields.append("form")
    if words and all(
        word.index_token is not None and word.index_sentence is not None
        for word in words
    ):
        fields.append("word_indices")
    if words and all(
        word.index_char_start is not None and word.index_char_stop is not None
        for word in words
    ):
        fields.append("word_offsets")
    if any(word.lemma is not None for word in words):
        fields.append("lemma")
    if any(word.upos is not None for word in words):
        fields.append("upos")
    if any(word.xpos is not None for word in words):
        fields.append("xpos")
    if any(word.features is not None for word in words):
        fields.append("features")
    if any(word.dependency_relation is not None for word in words):
        fields.extend(("governor", "dependency_relation"))
    if any(word.annotation_sources for word in words):
        fields.append("annotation_sources")
    if any(word.confidence for word in words):
        fields.append("confidence")
    for name in (
        "pipeline", "backend", "model", "metadata", "provenance",
        "default_provenance_id", "sentence_annotation_sources",
    ):
        value = getattr(doc, name)
        if name == "metadata":
            value = {
                key: item for key, item in value.items() if key != _SIDECAR_KEY
            }
        if _present(value):
            fields.append(name)
    public_doc_fields = getattr(type(doc), "model_fields", {})
    for name in public_doc_fields:
        if name in _MAPPED_DOC_FIELDS or name in fields:
            continue
        value = getattr(doc, name)
        if _present(value):
            fields.append(name)
    for word in words:
        public_word_fields = getattr(type(word), "model_fields", {})
        for name in public_word_fields:
            if name in _MAPPED_WORD_FIELDS or name in {
                "index_char_start",
                "index_char_stop",
            }:
                continue
            field_name = f"word.{name}"
            if field_name in fields:
                continue
            value = getattr(word, name)
            if _present(value):
                fields.append(field_name)
    return tuple(fields)


def _report(
    *,
    direction: str,
    native_fields: tuple[str, ...],
    sidecar_fields: tuple[str, ...] = (),
    lost_fields: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    omitted_ids: tuple[str, ...] = (),
) -> InteropReport:
    return InteropReport(
        native_fields=native_fields,
        sidecar_fields=sidecar_fields,
        lost_fields=lost_fields,
        warnings=warnings,
        omitted_ids=omitted_ids,
        target="cltk",
        version=_version(),
        direction=direction,
    )


def _typed_pos(value: str) -> Any:
    if value in {"", "_"}:
        return None
    from cltk.morphosyntax.ud_pos import UDPartOfSpeechTag

    try:
        return UDPartOfSpeechTag(tag=value)
    except (TypeError, ValueError) as exc:
        raise InteropSchemaError(f"invalid CLTK UD part of speech {value!r}") from exc


def _typed_deprel(value: str) -> Any:
    if value in {"", "_"}:
        return None
    from cltk.morphosyntax.ud_deprels import get_ud_deprel_tag

    try:
        return get_ud_deprel_tag(value)
    except (TypeError, ValueError):
        return None


def _feature_set(value: str) -> Any:
    if value in {"", "_"}:
        return None
    from cltk.core.data_types import UDFeatureTag, UDFeatureTagSet

    pairs: list[tuple[str, str]] = []
    for item in value.split("|"):
        if "=" not in item:
            raise InteropSchemaError(f"invalid UD feature item {item!r}")
        key, feature_value = item.split("=", 1)
        if not key or not feature_value:
            raise InteropSchemaError(f"invalid UD feature item {item!r}")
        pairs.append((key, feature_value))
    try:
        tags = [UDFeatureTag(key=key, value=item) for key, item in pairs]
        return UDFeatureTagSet(features=tags)
    except (TypeError, ValueError):
        # CLTK's registry may lag a valid UD feature. The complete raw FEATS
        # value remains in the sidecar instead of being partially fabricated.
        return None


def _feature_string(value: Any) -> str:
    if value is None:
        return "_"
    return "|".join(f"{item.key}={item.value}" for item in value.features) or "_"


def _pos_string(value: Any) -> str:
    return "_" if value is None else str(value.tag)


def _deprel_string(value: Any) -> str:
    return "_" if value is None else str(value.code)


def _normalized_text(document: InteropDocument) -> str | None:
    if document.source_text is None:
        return None
    ordered = [
        document.token_metadata.get((sentence.sent_id, token.id))
        for sentence in document.ud_document.sentences
        for token in sentence.tokens
    ]
    alignments = [None if item is None else item.alignment for item in ordered]
    if not alignments or any(item is None for item in alignments):
        return None
    concrete = [item for item in alignments if item is not None]
    cursor = 0
    parts: list[str] = []
    for alignment in concrete:
        parts.append(document.source_text[cursor:alignment.start_char])
        parts.append(alignment.normalized_text)
        cursor = alignment.end_char
    parts.append(document.source_text[cursor:])
    return "".join(parts)


def _sentence_boundaries(document: InteropDocument) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for sentence in document.ud_document.sentences:
        metadata = document.sentence_metadata.get(sentence.sent_id)
        if (
            metadata is not None
            and metadata.boundary_start_char is not None
            and metadata.boundary_end_char is not None
        ):
            result.append(
                (metadata.boundary_start_char, metadata.boundary_end_char)
            )
            continue
        alignments = [
            document.token_metadata.get((sentence.sent_id, token.id))
            for token in sentence.tokens
        ]
        if not alignments or any(
            item is None or item.alignment is None for item in alignments
        ):
            return []
        first = alignments[0]
        last = alignments[-1]
        assert first is not None and first.alignment is not None
        assert last is not None and last.alignment is not None
        result.append((first.alignment.start_char, last.alignment.end_char))
    return result


def to_cltk(
    document: InteropDocument, *, allow_lossy: bool = False
) -> InteropResult[Any]:
    """Project one immutable canonical document into a real CLTK ``Doc``."""
    Doc, Language, Word = _require_cltk()
    if not isinstance(document, InteropDocument):
        raise InteropSchemaError("document must be an InteropDocument")
    words: list[Any] = []
    warnings: list[str] = []
    for sentence_index, sentence in enumerate(document.ud_document.sentences):
        for token_index, token in enumerate(sentence.tokens):
            metadata = document.token_metadata.get((sentence.sent_id, token.id))
            alignment = None if metadata is None else metadata.alignment
            feats = token.feats if metadata is None or metadata.feats is None else metadata.feats
            relation = (
                token.deprel
                if metadata is None or metadata.relation is None
                else metadata.relation
            )
            features = _feature_set(feats)
            dependency_relation = _typed_deprel(relation)
            if feats not in {"", "_"} and features is None:
                warnings.append(f"unsupported CLTK feature registry value at {sentence.sent_id}:{token.id}")
            if relation not in {"", "_"} and dependency_relation is None:
                warnings.append(f"unsupported CLTK dependency relation at {sentence.sent_id}:{token.id}")
            sources: dict[str, str] = {}
            confidence: dict[str, float] = {}
            if metadata is not None:
                if metadata.lemma_source is not None:
                    source = metadata.lemma_source
                    sources["lemma"] = str(
                        source.value if isinstance(source, Enum) else source
                    )
                if metadata.lemma_source_path is not None:
                    sources["lemma_path"] = metadata.lemma_source_path
                if metadata.upos_confidence is not None:
                    confidence["upos"] = float(metadata.upos_confidence)
                if metadata.lemma_confidence is not None:
                    confidence["lemma"] = float(metadata.lemma_confidence)
            try:
                words.append(
                    Word(
                        index_char_start=(
                            None if alignment is None else alignment.start_char
                        ),
                        index_char_stop=(
                            None if alignment is None else alignment.end_char
                        ),
                        index_token=token_index,
                        index_sentence=sentence_index,
                        string=token.form,
                        lemma=None if token.lemma == "_" else token.lemma,
                        upos=_typed_pos(token.upos),
                        features=features,
                        dependency_relation=dependency_relation,
                        governor=token.head,
                        xpos=None if token.xpos == "_" else token.xpos,
                        annotation_sources=sources,
                        confidence=confidence,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise InteropSchemaError(f"invalid CLTK word projection: {exc}") from exc
    try:
        native = Doc(
            language=Language(name="Ancient Greek", glottolog_id="grc"),
            words=words,
            raw=document.source_text,
            normalized_text=_normalized_text(document),
            sentence_boundaries=_sentence_boundaries(document),
            metadata={},
        )
    except (TypeError, ValueError) as exc:
        raise InteropSchemaError(f"invalid CLTK document projection: {exc}") from exc

    sidecar_fields = _adapter_sidecar_fields(document, target="cltk")
    try:
        sidecar = encode_sidecar(
            document,
            target="cltk",
            native_signature=_canonical_native_state(native),
        )
    except (TypeError, ValueError, InteropSchemaError) as exc:
        if not allow_lossy:
            raise InteropSchemaError(f"could not encode CLTK sidecar: {exc}") from exc
        sidecar = None
    if sidecar is not None:
        native.metadata[_SIDECAR_KEY] = sidecar
    return InteropResult(
        native,
        sidecar,
        _report(
            direction="export",
            native_fields=_native_fields(native),
            sidecar_fields=sidecar_fields if sidecar is not None else (),
            lost_fields=() if sidecar is not None else sidecar_fields,
            warnings=tuple(warnings),
            omitted_ids=_adapter_omitted_ids(document, target="cltk"),
        ),
    )


def _lossy_document(
    doc: Any,
) -> tuple[InteropDocument, tuple[str, ...], tuple[str, ...]]:
    from aegean.greek.ud import UDDocument, UDSentence, UDToken

    words = tuple(doc.words or ())
    grouped: dict[int, list[Any]] = {}
    _validated_sentence_lengths(words)
    for word in words:
        sentence_index = word.index_sentence
        grouped.setdefault(sentence_index, []).append(word)

    boundaries = tuple(doc.sentence_boundaries or ())
    if boundaries and len(boundaries) != len(grouped):
        raise InteropSchemaError(
            "CLTK sentence boundary count disagrees with sentence indices"
        )
    source_text = doc.raw if isinstance(doc.raw, str) else None
    sentence_metadata: dict[str, InteropSentenceMetadata] = {}
    token_metadata: dict[tuple[str, int], InteropTokenMetadata] = {}
    sentences: list[UDSentence] = []
    missing_governor = False
    for sentence_index, sentence_words in grouped.items():
        if [word.index_token for word in sentence_words] != list(
            range(len(sentence_words))
        ):
            raise InteropSchemaError(
                "CLTK token indices must be contiguous within a sentence"
            )
        sent_id = f"sent-{sentence_index}"
        tokens: list[UDToken] = []
        for token_index, word in enumerate(sentence_words, start=1):
            if not isinstance(word.string, str) or not word.string:
                raise InteropSchemaError("CLTK word string must be non-empty")
            governor = word.governor
            if governor is not None and (
                not isinstance(governor, int)
                or isinstance(governor, bool)
                or governor < 0
                or governor > len(sentence_words)
                or governor == token_index
            ):
                raise InteropSchemaError(
                    "CLTK governor must be a valid non-self sentence word ID"
                )
            if governor is None:
                missing_governor = True
            relation = _deprel_string(word.dependency_relation)
            features = _feature_string(word.features)
            xpos = "_" if word.xpos is None else str(word.xpos)
            tokens.append(
                UDToken(
                    token_index,
                    word.string,
                    "_" if word.lemma is None else str(word.lemma),
                    _pos_string(word.upos),
                    xpos,
                    features,
                    0 if governor is None else governor,
                    relation,
                )
            )
            sources = word.annotation_sources or {}
            confidence = word.confidence or {}
            token_metadata[(sent_id, token_index)] = InteropTokenMetadata(
                head=governor,
                relation=None if relation == "_" else relation,
                xpos=None if xpos == "_" else xpos,
                feats=None if features == "_" else features,
                lemma_source=sources.get("lemma"),
                lemma_source_path=sources.get("lemma_path"),
                upos_confidence=confidence.get("upos"),
                lemma_confidence=confidence.get("lemma"),
            )
        sentence_text = " ".join(token.form for token in tokens)
        if boundaries:
            boundary = boundaries[sentence_index]
            if (
                not isinstance(boundary, (tuple, list))
                or len(boundary) != 2
                or any(
                    not isinstance(item, int) or isinstance(item, bool) or item < 0
                    for item in boundary
                )
                or boundary[1] < boundary[0]
            ):
                raise InteropSchemaError("CLTK sentence boundary is invalid")
            start, end = int(boundary[0]), int(boundary[1])
            if source_text is not None:
                if end > len(source_text):
                    raise InteropSchemaError(
                        "CLTK sentence boundary lies outside raw text"
                    )
                sentence_text = source_text[start:end]
            sentence_metadata[sent_id] = InteropSentenceMetadata(
                boundary_start_char=start, boundary_end_char=end
            )
        sentences.append(UDSentence(sent_id, sentence_text, tuple(tokens)))

    document_id_value = doc.metadata.get("document_id")
    document_id = (
        document_id_value
        if isinstance(document_id_value, str) and document_id_value
        else None
    )
    document = InteropDocument(
        UDDocument(tuple(sentences)),
        source_text=source_text,
        document_id=document_id,
        token_metadata=token_metadata,
        sentence_metadata=sentence_metadata,
    )
    lost = list(_LOSSY_IMPORT_FIELDS)
    if any(
        word.index_char_start is not None or word.index_char_stop is not None
        for word in words
    ):
        lost.append("word_offsets")
    if document_id is not None:
        lost.remove("document_identity")
    if doc.normalized_text is not None:
        lost.append("normalized_text")
    public_doc_fields = getattr(type(doc), "model_fields", {})
    for name in public_doc_fields:
        if name in _MAPPED_DOC_FIELDS or name == "normalized_text":
            continue
        value = getattr(doc, name)
        if _present(value) and name not in lost:
            lost.append(name)
    for word in words:
        public_word_fields = getattr(type(word), "model_fields", {})
        for name in public_word_fields:
            if name in _MAPPED_WORD_FIELDS or name in {
                "index_char_start",
                "index_char_stop",
            }:
                continue
            field_name = f"word.{name}"
            value = getattr(word, name)
            if _present(value) and field_name not in lost:
                lost.append(field_name)
    extra_metadata = {key for key in doc.metadata if key not in {_SIDECAR_KEY, "document_id"}}
    if extra_metadata:
        lost.append("metadata")
    warnings: tuple[str, ...] = (
        ("governor=None retained in token metadata; UD structural head uses 0",)
        if missing_governor
        else ()
    )
    return document, tuple(lost), warnings


def from_cltk(
    doc: Any, *, sidecar: str | None = None, allow_lossy: bool = False
) -> InteropResult[InteropDocument]:
    """Import a real CLTK ``Doc`` and validate its complete native state."""
    Doc, _Language, _Word = _require_cltk()
    if not isinstance(doc, Doc):
        raise InteropSchemaError("doc must be a cltk.core.data_types.Doc")
    _require_ancient_greek(doc)
    embedded = doc.metadata.get(_SIDECAR_KEY)
    if sidecar is not None and embedded is not None and embedded != sidecar:
        raise InteropSchemaError(
            "metadata key aegean.interop/v1 conflicts with supplied sidecar"
        )
    if sidecar is None:
        sidecar = embedded if isinstance(embedded, str) else None
    native_fields = _native_fields(doc)
    signature = _canonical_native_state(doc)
    if sidecar is not None:
        try:
            decoded = decode_sidecar(
                sidecar, target="cltk", native_signature=signature
            )
        except (TypeError, ValueError, InteropSchemaError) as exc:
            raise InteropSchemaError(f"invalid CLTK sidecar: {exc}") from exc
        document = InteropDocument.from_dict(decoded["payload"])
        return InteropResult(
            document,
            sidecar,
            _report(
                direction="import",
                native_fields=native_fields,
                sidecar_fields=_adapter_sidecar_fields(document, target="cltk"),
                omitted_ids=_adapter_omitted_ids(document, target="cltk"),
            ),
        )
    if not allow_lossy:
        raise InteropLossError(
            "CLTK Doc has no aegean.interop/v1 sidecar; unavailable fields: "
            + ", ".join(_LOSSY_IMPORT_FIELDS)
        )
    document, lost, warnings = _lossy_document(doc)
    retained_native_fields = tuple(
        field for field in native_fields if field not in set(lost)
    )
    return InteropResult(
        document,
        None,
        _report(
            direction="import",
            native_fields=retained_native_fields,
            lost_fields=lost,
            warnings=warnings,
        ),
    )


def _record_value(record: Any, name: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _record_annotation(
    record: Any, names: tuple[str, ...], default: Any = None
) -> Any:
    """Return the first computed annotation, treating ``None`` as absent."""
    missing = object()
    for name in names:
        value = _record_value(record, name, missing)
        if value is not missing and value is not None:
            return value
    return default


def make_cltk_process(
    pipeline: Any, *, parse: bool = True, with_confidence: bool = False
) -> Any:
    """Create a network-free CLTK process around one explicitly owned pipeline."""
    if pipeline is None or not (
        callable(getattr(pipeline, "analyze", None))
        or callable(getattr(pipeline, "analyze_tokens", None))
    ):
        raise TypeError("pipeline must provide analyze or analyze_tokens")
    Doc, _Language, Word = _require_cltk()
    try:
        from cltk.core.data_types import Process
    except Exception as exc:
        raise _dependency_error() from exc

    class AegeanCLTKProcess(Process):
        process_id = _PROCESS_ID
        _aegean_pipeline: Any

        def __init__(self) -> None:
            super().__init__(glottolog_id="grc")
            object.__setattr__(self, "_aegean_pipeline", pipeline)

        def run(self, input_doc: Any) -> Any:
            if not isinstance(input_doc, Doc):
                raise InteropSchemaError("input_doc must be a CLTK Doc")
            _require_ancient_greek(input_doc)
            if not isinstance(input_doc.raw, str):
                raise InteropSchemaError("CLTK Doc.raw must be a string")
            sentence_lengths = _validated_sentence_lengths(input_doc.words)
            kwargs = {"parse": parse, "with_confidence": with_confidence}
            analyze = getattr(self._aegean_pipeline, "analyze", None)
            analyze_tokens = getattr(self._aegean_pipeline, "analyze_tokens", None)
            try:
                if callable(analyze):
                    records = list(analyze(input_doc.raw, **kwargs) or ())
                else:
                    forms = [str(word.string or "") for word in input_doc.words]
                    assert callable(analyze_tokens)
                    records = list(analyze_tokens(forms, **kwargs) or ())
            except Exception as exc:
                raise InteropSchemaError(f"pyaegean pipeline failed: {exc}") from exc
            if len(records) != len(input_doc.words):
                raise InteropSchemaError(
                    f"pipeline returned {len(records)} records for "
                    f"{len(input_doc.words)} CLTK words"
                )
            clone = input_doc.model_copy(deep=True)
            clone.pipeline = input_doc.pipeline
            new_words: list[Any] = []
            for position, (old, record) in enumerate(zip(clone.words, records)):
                if old.index_token is None or old.index_sentence is None:
                    raise InteropSchemaError(
                        "CLTK words require token and sentence indices before processing"
                    )
                form = _record_value(
                    record, "text", _record_value(record, "form", old.string)
                )
                if form != old.string:
                    raise InteropSchemaError(
                        f"pipeline changed token order/form at index {position}"
                    )
                record_index = _record_value(record, "index")
                if record_index is not None:
                    if not isinstance(record_index, int) or isinstance(
                        record_index, bool
                    ):
                        raise InteropSchemaError(
                            f"pipeline returned a non-integer token index at position {position}"
                        )
                    if record_index != old.index_token + 1:
                        raise InteropSchemaError(
                            f"pipeline changed token index at position {position}"
                        )
                record_sentence = _record_value(record, "sentence")
                if record_sentence is not None:
                    if not isinstance(record_sentence, int) or isinstance(
                        record_sentence, bool
                    ):
                        raise InteropSchemaError(
                            f"pipeline returned a non-integer sentence index at position {position}"
                        )
                    if record_sentence != old.index_sentence:
                        raise InteropSchemaError(
                            f"pipeline changed sentence membership at position {position}"
                        )
                sources = dict(old.annotation_sources)
                confidence = dict(old.confidence)
                source = _record_value(record, "lemma_source")
                if source is not None:
                    sources["lemma"] = str(
                        source.value if isinstance(source, Enum) else source
                    )
                source_path = _record_value(record, "lemma_source_path")
                if source_path is not None:
                    sources["lemma_path"] = str(source_path)
                for record_name, key in (
                    ("upos_confidence", "upos"),
                    ("lemma_confidence", "lemma"),
                ):
                    score = _record_value(record, record_name)
                    if score is not None:
                        if (
                            not isinstance(score, (int, float))
                            or isinstance(score, bool)
                            or not math.isfinite(float(score))
                            or not 0.0 <= float(score) <= 1.0
                        ):
                            raise InteropSchemaError(
                                f"pipeline returned invalid {record_name} at index {position}"
                            )
                        confidence[key] = float(score)
                feature_value = _record_annotation(
                    record,
                    ("feats", "features"),
                    _feature_string(old.features),
                )
                if not isinstance(feature_value, str):
                    raise InteropSchemaError(
                        f"pipeline returned non-string UD features at index {position}"
                    )
                typed_features = _feature_set(feature_value)
                if feature_value not in {"", "_"} and typed_features is None:
                    raise InteropSchemaError(
                        f"CLTK cannot represent pipeline UD features {feature_value!r} "
                        f"at index {position}"
                    )
                relation_value = _record_annotation(
                    record,
                    ("relation", "deprel"),
                    _deprel_string(old.dependency_relation),
                )
                if not isinstance(relation_value, str):
                    raise InteropSchemaError(
                        f"pipeline returned non-string dependency relation at index {position}"
                    )
                typed_relation = _typed_deprel(relation_value)
                if relation_value not in {"", "_"} and typed_relation is None:
                    raise InteropSchemaError(
                        f"CLTK cannot represent pipeline dependency relation "
                        f"{relation_value!r} at index {position}"
                    )
                governor_value = _record_annotation(
                    record, ("head", "governor"), old.governor
                )
                if governor_value is not None:
                    if not isinstance(governor_value, int) or isinstance(
                        governor_value, bool
                    ):
                        raise InteropSchemaError(
                            f"pipeline returned a non-integer head at index {position}"
                        )
                    sentence_length = sentence_lengths[old.index_sentence]
                    if (
                        governor_value < 0
                        or governor_value > sentence_length
                        or governor_value == old.index_token + 1
                    ):
                        raise InteropSchemaError(
                            f"pipeline returned an invalid head at index {position}"
                        )
                update = {
                    **old.model_dump(mode="python"),
                    "string": form,
                    "lemma": _record_value(record, "lemma", old.lemma),
                    "upos": _typed_pos(
                        _record_value(record, "upos", _pos_string(old.upos))
                    ),
                    "features": typed_features,
                    "dependency_relation": typed_relation,
                    "governor": governor_value,
                    "xpos": _record_annotation(record, ("xpos",), old.xpos),
                    "annotation_sources": sources,
                    "confidence": confidence,
                }
                try:
                    new_words.append(Word(**update))
                except (TypeError, ValueError) as exc:
                    raise InteropSchemaError(
                        f"invalid CLTK word projection: {exc}"
                    ) from exc
            clone.words = new_words
            clone.metadata.pop(_SIDECAR_KEY, None)
            return clone

    return AegeanCLTKProcess()
