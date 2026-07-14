"""Loss-aware interoperability with the current supported Stanza document API."""

from __future__ import annotations

import json
from dataclasses import replace
from importlib import metadata as importlib_metadata
from typing import Any, Mapping

from .interop import (
    InteropDependencyError,
    InteropDocument,
    InteropLossError,
    InteropReport,
    InteropResult,
    InteropSchemaError,
    _adapter_omitted_ids,
    _adapter_sidecar_fields,
    decode_sidecar,
    encode_sidecar,
)

__all__ = ["to_stanza", "from_stanza"]

_SIDECAR_ATTRIBUTE = "_aegean_interop_sidecar"
_LOSSY_IMPORT_FIELDS = (
    "document_identity",
    "token_metadata",
    "source_alignment",
    "form_state",
    "lemma_provenance",
    "confidence",
    "receipts",
    "analysis_state",
    "sentence_metadata",
    "profile",
    "provenance",
    "empty_nodes",
    "opaque_rows",
    "comments",
    "row_order",
    "raw_conllu",
)


def _dependency_error() -> InteropDependencyError:
    return InteropDependencyError(
        "Stanza is required for this adapter; install it with "
        "pip install 'pyaegean[stanza]'"
    )


def _require_stanza() -> tuple[Any, Any]:
    try:
        import stanza
        from stanza.models.common.doc import Document
    except Exception as exc:  # broken optional installs need the same clean hint
        raise _dependency_error() from exc
    return stanza, Document


def _version() -> str:
    try:
        return importlib_metadata.version("stanza")
    except importlib_metadata.PackageNotFoundError as exc:
        raise _dependency_error() from exc


def _json_value(value: Any, *, field: str) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _json_value(item, field=field)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item, field=field) for item in value]
    raise InteropSchemaError(
        f"Stanza native field {field} is not JSON-safe: {type(value).__name__}"
    )


def _stanza_native_state(doc: Any) -> dict[str, Any]:
    """Return every native field whose mutation invalidates the sidecar."""
    sentences: list[dict[str, Any]] = []
    for sentence in doc.sentences:
        sentences.append(
            {
                "index": int(sentence.index),
                "sent_id": _json_value(sentence.sent_id, field="sent_id"),
                "text": _json_value(sentence.text, field="sentence.text"),
                "tokens": [
                    {
                        "id": _json_value(token.id, field="token.id"),
                        "text": str(token.text),
                        "start_char": _json_value(
                            token.start_char, field="token.start_char"
                        ),
                        "end_char": _json_value(
                            token.end_char, field="token.end_char"
                        ),
                        "spaces_before": _json_value(
                            token.spaces_before, field="token.spaces_before"
                        ),
                        "spaces_after": _json_value(
                            token.spaces_after, field="token.spaces_after"
                        ),
                    }
                    for token in sentence.tokens
                ],
                "words": [
                    {
                        "id": _json_value(word.id, field="word.id"),
                        "text": str(word.text),
                        "lemma": _json_value(word.lemma, field="word.lemma"),
                        "upos": _json_value(word.upos, field="word.upos"),
                        "xpos": _json_value(word.xpos, field="word.xpos"),
                        "feats": _json_value(word.feats, field="word.feats"),
                        "head": _json_value(word.head, field="word.head"),
                        "deprel": _json_value(word.deprel, field="word.deprel"),
                        "deps": _json_value(word.deps, field="word.deps"),
                        "misc": _json_value(word.misc, field="word.misc"),
                        "start_char": _json_value(
                            word.start_char, field="word.start_char"
                        ),
                        "end_char": _json_value(
                            word.end_char, field="word.end_char"
                        ),
                    }
                    for word in sentence.words
                ],
            }
        )
    return {
        "text": _json_value(doc.text, field="document.text"),
        "sentences": sentences,
    }


def _native_signature(state: Mapping[str, Any]) -> str:
    return json.dumps(
        state,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _native_fields(doc: Any) -> tuple[str, ...]:
    sentences = tuple(doc.sentences)
    tokens = tuple(token for sentence in sentences for token in sentence.tokens)
    words = tuple(word for sentence in sentences for word in sentence.words)
    fields: list[str] = []
    if isinstance(doc.text, str):
        fields.append("text")
    if sentences:
        fields.append("sentences")
    if sentences and all(
        sentence.sent_id not in {None, "", "_"} for sentence in sentences
    ):
        fields.append("sent_id")
    if words:
        fields.append("form")
    if any(len(token.id) > 1 for token in tokens):
        fields.append("mwt")
    if tokens and all(
        token.start_char is not None and token.end_char is not None
        for token in tokens
    ):
        fields.extend(("offsets", "whitespace"))
    for field, attribute in (
        ("lemma", "lemma"),
        ("upos", "upos"),
        ("xpos", "xpos"),
        ("feats", "feats"),
    ):
        if any(getattr(word, attribute) not in {None, "", "_"} for word in words):
            fields.append(field)
    if any(word.deprel not in {None, "", "_"} for word in words):
        fields.extend(("head", "deprel"))
    if any(word.deps not in {None, "", "_"} for word in words):
        fields.append("deps")
    if any(word.misc not in {None, "", "_"} for word in words):
        fields.append("misc")
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
        target="stanza",
        version=_version(),
        direction=direction,
    )


def _alignments(document: InteropDocument) -> tuple[list[Any], bool]:
    keys = [
        (sentence.sent_id, token.id)
        for sentence in document.ud_document.sentences
        for token in sentence.tokens
    ]
    values = []
    for key in keys:
        metadata = document.token_metadata.get(key)
        values.append(None if metadata is None else metadata.alignment)
    return values, bool(keys) and all(value is not None for value in values)


def _word_dict(word: Any, alignment: Any) -> dict[str, Any]:
    return {
        "id": word.id,
        "text": word.form,
        "lemma": None if word.lemma == "_" else word.lemma,
        "upos": None if word.upos == "_" else word.upos,
        "xpos": None if word.xpos == "_" else word.xpos,
        "feats": None if word.feats == "_" else word.feats,
        "head": word.head,
        "deprel": None if word.deprel == "_" else word.deprel,
        "deps": None if word.deps_raw in {"", "_"} else word.deps_raw,
        "misc": None if word.misc_raw in {"", "_"} else word.misc_raw,
        "start_char": None if alignment is None else alignment.start_char,
        "end_char": None if alignment is None else alignment.end_char,
    }


def _native_sentences(
    document: InteropDocument, alignments: list[Any]
) -> tuple[list[list[dict[str, Any]]], list[list[str]]]:
    native: list[list[dict[str, Any]]] = []
    comments: list[list[str]] = []
    flat_index = 0
    for sentence in document.ud_document.sentences:
        if sentence.sent_id != sentence.sent_id.strip() or any(
            delimiter in sentence.sent_id for delimiter in ("\t", "\r", "\n")
        ):
            raise InteropSchemaError(
                "Stanza sentence IDs must not contain surrounding whitespace, tabs, or line breaks"
            )
        ranges = {item.start: item for item in sentence.multiword_tokens}
        rows: list[dict[str, Any]] = []
        for word in sentence.tokens:
            if word.id in ranges:
                item = ranges[word.id]
                first_alignment = alignments[flat_index]
                final_offset = flat_index + item.end - item.start
                last_alignment = (
                    alignments[final_offset]
                    if final_offset < len(alignments)
                    else None
                )
                rows.append(
                    {
                        "id": (item.start, item.end),
                        "text": item.form,
                        "start_char": (
                            None
                            if first_alignment is None
                            else first_alignment.start_char
                        ),
                        "end_char": (
                            None if last_alignment is None else last_alignment.end_char
                        ),
                        "misc": (
                            None if item.misc_raw in {"", "_"} else item.misc_raw
                        ),
                    }
                )
            rows.append(_word_dict(word, alignments[flat_index]))
            flat_index += 1
        native.append(rows)
        comments.append([f"# sent_id = {sentence.sent_id}"])
    return native, comments


def to_stanza(
    document: InteropDocument, *, allow_lossy: bool = False
) -> InteropResult[Any]:
    """Project one immutable canonical document into a real Stanza ``Document``."""
    _stanza, Document = _require_stanza()
    if not isinstance(document, InteropDocument):
        raise InteropSchemaError("document must be an InteropDocument")
    alignments, complete_alignments = _alignments(document)
    native_sentences, comments = _native_sentences(document, alignments)
    native_text = document.source_text
    try:
        native = Document(native_sentences, text=native_text, comments=comments)
    except (IndexError, TypeError, ValueError) as exc:
        raise InteropSchemaError(f"invalid Stanza projection: {exc}") from exc

    native_state = _stanza_native_state(native)
    sidecar_fields = _adapter_sidecar_fields(document, target="stanza")
    try:
        sidecar = encode_sidecar(
            document,
            target="stanza",
            native_signature=_native_signature(native_state),
        )
    except (TypeError, ValueError, InteropSchemaError) as exc:
        if not allow_lossy:
            raise InteropSchemaError(f"could not encode Stanza sidecar: {exc}") from exc
        sidecar = None
    if sidecar is not None:
        setattr(native, _SIDECAR_ATTRIBUTE, sidecar)
    warnings: tuple[str, ...] = ()
    if document.source_text is not None and not complete_alignments:
        warnings = (
            "source text is native, but exact token offsets and whitespace remain "
            "sidecar-only because complete alignment is unavailable",
        )
    return InteropResult(
        native,
        sidecar,
        _report(
            direction="export",
            native_fields=_native_fields(native),
            sidecar_fields=sidecar_fields if sidecar is not None else (),
            lost_fields=() if sidecar is not None else sidecar_fields,
            warnings=warnings,
            omitted_ids=_adapter_omitted_ids(document, target="stanza"),
        ),
    )


def _field(value: Any, *, name: str) -> str:
    if value is None or value == "":
        return "_"
    text = str(value)
    if "\t" in text or "\n" in text or "\r" in text:
        raise InteropSchemaError(f"Stanza {name} contains a CoNLL-U delimiter")
    return text


def _lossy_document(doc: Any) -> InteropDocument:
    from aegean.greek.ud import UDDocument, UDSentence, load_conllu_document

    parsed_sentences: list[UDSentence] = []
    for sentence_index, sentence in enumerate(doc.sentences):
        sent_id = (
            f"sent-{sentence_index}"
            if sentence.sent_id in {None, "", "_"}
            else _field(sentence.sent_id, name="sent_id")
        )
        lines = [f"# sent_id = {sent_id}"]
        for token in sentence.tokens:
            if len(token.id) > 1:
                start, end = token.id
                lines.append(
                    "\t".join(
                        (
                            f"{start}-{end}",
                            _field(token.text, name="token text"),
                            "_", "_", "_", "_", "_", "_", "_", "_",
                        )
                    )
                )
            for word in token.words:
                lines.append(
                    "\t".join(
                        (
                            str(word.id),
                            _field(word.text, name="word text"),
                            _field(word.lemma, name="lemma"),
                            _field(word.upos, name="upos"),
                            _field(word.xpos, name="xpos"),
                            _field(word.feats, name="feats"),
                            str(word.head if word.head is not None else 0),
                            _field(word.deprel, name="deprel"),
                            _field(word.deps, name="deps"),
                            _field(word.misc, name="misc"),
                        )
                    )
                )
        if not sentence.tokens:
            parsed_sentences.append(
                UDSentence(sent_id, str(sentence.text or ""), ())
            )
            continue
        parsed = load_conllu_document("\n".join(lines) + "\n\n", strict=False)
        parsed_sentences.append(replace(parsed.sentences[0], text=str(sentence.text or "")))
    source_text = doc.text if isinstance(doc.text, str) else None
    return InteropDocument(UDDocument(tuple(parsed_sentences)), source_text=source_text)


def from_stanza(
    doc: Any, *, sidecar: str | None = None, allow_lossy: bool = False
) -> InteropResult[InteropDocument]:
    """Import a real Stanza document and validate its complete native state."""
    _stanza, Document = _require_stanza()
    if not isinstance(doc, Document):
        raise InteropSchemaError("doc must be a stanza.models.common.doc.Document")
    attached = getattr(doc, _SIDECAR_ATTRIBUTE, None)
    if sidecar is not None and attached is not None and attached != sidecar:
        raise InteropSchemaError(
            "Stanza aegean.interop/v1 property conflicts with supplied sidecar"
        )
    if sidecar is None:
        sidecar = attached if isinstance(attached, str) else None
    native_fields = _native_fields(doc)
    signature = _native_signature(_stanza_native_state(doc))
    if sidecar is not None:
        decoded = decode_sidecar(
            sidecar, target="stanza", native_signature=signature
        )
        document = InteropDocument.from_dict(decoded["payload"])
        return InteropResult(
            document,
            sidecar,
            _report(
                direction="import",
                native_fields=native_fields,
                sidecar_fields=_adapter_sidecar_fields(document, target="stanza"),
                omitted_ids=_adapter_omitted_ids(document, target="stanza"),
            ),
        )
    if not allow_lossy:
        raise InteropLossError(
            "Stanza Document has no aegean.interop/v1 sidecar; unavailable fields: "
            + ", ".join(_LOSSY_IMPORT_FIELDS)
        )
    document = _lossy_document(doc)
    lost = list(_LOSSY_IMPORT_FIELDS)
    generated_sentence_ids = any(
        sentence.sent_id in {None, "", "_"} for sentence in doc.sentences
    )
    if generated_sentence_ids:
        lost.append("sentence_ids")
    if any(len(token.id) > 1 for sentence in doc.sentences for token in sentence.tokens):
        lost.append("MWT_row_state")
    warnings = [
        "native offsets cannot become stable SourceAlignment values without a document ID"
    ]
    if generated_sentence_ids:
        warnings.append("sentence IDs are generated because Stanza does not store them")
    return InteropResult(
        document,
        None,
        _report(
            direction="import",
            native_fields=native_fields,
            lost_fields=tuple(lost),
            warnings=tuple(warnings),
        ),
    )
