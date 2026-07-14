"""Loss-aware interoperability with the current supported spaCy ``Doc`` API."""

from __future__ import annotations

import json
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

__all__ = ["to_spacy", "from_spacy"]

_SIDECAR_KEY = "aegean.interop/v1"
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
        "spaCy is required for this adapter; install it with "
        "pip install 'pyaegean[spacy]'"
    )


def _require_spacy() -> tuple[Any, Any]:
    try:
        from spacy.tokens import Doc
        from spacy.vocab import Vocab
    except Exception as exc:  # broken optional installs need the same clean hint
        raise _dependency_error() from exc
    return Doc, Vocab


def _version() -> str:
    try:
        return importlib_metadata.version("spacy")
    except importlib_metadata.PackageNotFoundError as exc:
        raise _dependency_error() from exc


def _spacy_native_state(doc: Any) -> dict[str, Any]:
    """Return the exact JSON projection bound by the canonical sidecar."""
    tokens: list[dict[str, Any]] = []
    for token in doc:
        tokens.append(
            {
                "i": int(token.i),
                "idx": int(token.idx),
                "text": str(token.text),
                "lemma": str(token.lemma_),
                "pos": str(token.pos_),
                "tag": str(token.tag_),
                "morph": str(token.morph),
                "dep": str(token.dep_),
                "head": int(token.head.i),
                "sent_start": (
                    None if token.is_sent_start is None else bool(token.is_sent_start)
                ),
                "whitespace": str(token.whitespace_),
            }
        )
    return {"text": str(doc.text), "tokens": tokens}


def _native_signature(state: Mapping[str, Any]) -> str:
    return json.dumps(
        state,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _native_fields(doc: Any) -> tuple[str, ...]:
    tokens = tuple(doc)
    fields: list[str] = ["text"]
    if tokens:
        fields.extend(("form", "spacing"))
    if any(token.lemma_ for token in tokens):
        fields.append("lemma")
    if any(token.pos_ for token in tokens):
        fields.append("upos")
    if any(token.tag_ for token in tokens):
        fields.append("xpos")
    if any(str(token.morph) for token in tokens):
        fields.append("feats")
    if any(token.dep_ for token in tokens):
        fields.extend(("head", "deprel"))
    if any(token.is_sent_start is not None for token in tokens):
        fields.append("sentence_starts")
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
        target="spacy",
        version=_version(),
        direction=direction,
    )


def _projection_spaces(document: InteropDocument) -> tuple[list[bool], bool]:
    """Build spaCy's one-ASCII-space projection without searching source text."""
    ordered = [
        (sentence.sent_id, token.id)
        for sentence in document.ud_document.sentences
        for token in sentence.tokens
    ]
    if not ordered:
        return [], document.source_text in {None, ""}
    alignments = []
    for key in ordered:
        metadata = document.token_metadata.get(key)
        alignments.append(None if metadata is None else metadata.alignment)
    complete = document.source_text is not None and all(
        alignment is not None for alignment in alignments
    )
    if not complete:
        return [True] * (len(ordered) - 1) + [False], False
    assert document.source_text is not None
    concrete = [alignment for alignment in alignments if alignment is not None]
    spaces: list[bool] = []
    exact = concrete[0].start_char == 0
    for index, alignment in enumerate(concrete):
        next_start = (
            concrete[index + 1].start_char
            if index + 1 < len(concrete)
            else len(document.source_text)
        )
        gap = document.source_text[alignment.end_char:next_start]
        spaces.append(bool(gap) and gap[0].isspace())
        if gap not in {"", " "}:
            exact = False
    return spaces, exact


def to_spacy(
    document: InteropDocument, *, vocab: Any = None, allow_lossy: bool = False
) -> InteropResult[Any]:
    """Project one immutable canonical document into a real spaCy ``Doc``."""
    Doc, Vocab = _require_spacy()
    if not isinstance(document, InteropDocument):
        raise InteropSchemaError("document must be an InteropDocument")
    if vocab is None:
        vocab = Vocab()

    sentences = document.ud_document.sentences
    tokens = [token for sentence in sentences for token in sentence.tokens]
    spaces, exact_spacing = _projection_spaces(document)
    words = [token.form for token in tokens]
    lemmas = ["" if token.lemma == "_" else token.lemma for token in tokens]
    pos = ["" if token.upos == "_" else token.upos for token in tokens]
    tags = ["" if token.xpos == "_" else token.xpos for token in tokens]
    morphs = ["" if token.feats == "_" else token.feats for token in tokens]
    sent_starts = [
        index == 0 for sentence in sentences for index, _token in enumerate(sentence.tokens)
    ]

    parsed = any(token.deprel not in {"", "_"} for token in tokens)
    heads: list[int] | None = [] if parsed else None
    deps: list[str] | None = [] if parsed else None
    if parsed:
        offset = 0
        assert heads is not None and deps is not None
        for sentence in sentences:
            for index, token in enumerate(sentence.tokens):
                heads.append(
                    offset + index if token.head == 0 else offset + token.head - 1
                )
                deps.append("" if token.deprel == "_" else token.deprel)
            offset += len(sentence.tokens)

    try:
        doc = Doc(
            vocab,
            words=words,
            spaces=spaces,
            tags=tags,
            pos=pos,
            morphs=morphs,
            lemmas=lemmas,
            heads=heads,
            deps=deps,
            sent_starts=sent_starts,
        )
    except (TypeError, ValueError) as exc:
        raise InteropSchemaError(f"invalid spaCy projection: {exc}") from exc

    native_state = _spacy_native_state(doc)
    sidecar_fields = _adapter_sidecar_fields(document, target="spacy")
    try:
        sidecar = encode_sidecar(
            document,
            target="spacy",
            native_signature=_native_signature(native_state),
        )
    except (TypeError, ValueError, InteropSchemaError) as exc:
        if not allow_lossy:
            raise InteropSchemaError(f"could not encode spaCy sidecar: {exc}") from exc
        sidecar = None
    if sidecar is not None:
        doc.user_data[_SIDECAR_KEY] = sidecar

    warnings: tuple[str, ...] = ()
    if not exact_spacing:
        warnings = (
            "spaCy stores only a boolean trailing-space projection; exact source "
            "spacing remains in the sidecar",
        )
    return InteropResult(
        doc,
        sidecar,
        _report(
            direction="export",
            native_fields=_native_fields(doc),
            sidecar_fields=sidecar_fields if sidecar is not None else (),
            lost_fields=() if sidecar is not None else sidecar_fields,
            warnings=warnings,
            omitted_ids=_adapter_omitted_ids(document, target="spacy"),
        ),
    )


def _lossy_document(doc: Any) -> InteropDocument:
    from aegean.greek.ud import UDDocument, UDSentence, UDToken

    values = tuple(doc)
    if not values:
        return InteropDocument(UDDocument(()), source_text=str(doc.text))
    starts = [0]
    starts.extend(
        index
        for index, token in enumerate(values[1:], start=1)
        if token.is_sent_start is True
    )
    bounds = [*starts, len(values)]
    sentences: list[UDSentence] = []
    for sentence_index, (start, end) in enumerate(zip(bounds, bounds[1:])):
        rows: list[UDToken] = []
        for local_index, token in enumerate(values[start:end], start=1):
            head_index = int(token.head.i)
            if head_index == int(token.i):
                head = 0
            elif start <= head_index < end:
                head = head_index - start + 1
            else:
                raise InteropSchemaError(
                    "spaCy dependency head crosses a sentence boundary"
                )
            rows.append(
                UDToken(
                    local_index,
                    str(token.text),
                    str(token.lemma_) or "_",
                    str(token.pos_) or "_",
                    str(token.tag_) or "_",
                    str(token.morph) or "_",
                    head,
                    str(token.dep_) or "_",
                )
            )
        sentence_text = str(doc[start:end].text)
        sentences.append(
            UDSentence(f"sent-{sentence_index}", sentence_text, tuple(rows))
        )
    return InteropDocument(UDDocument(tuple(sentences)), source_text=str(doc.text))


def from_spacy(
    doc: Any, *, sidecar: str | None = None, allow_lossy: bool = False
) -> InteropResult[InteropDocument]:
    """Import a real spaCy ``Doc`` and validate its complete native state."""
    Doc, _Vocab = _require_spacy()
    if not isinstance(doc, Doc):
        raise InteropSchemaError("doc must be a spacy.tokens.Doc")
    attached = doc.user_data.get(_SIDECAR_KEY)
    if sidecar is not None and attached is not None and attached != sidecar:
        raise InteropSchemaError(
            "user_data key aegean.interop/v1 conflicts with supplied sidecar"
        )
    if sidecar is None:
        sidecar = attached if isinstance(attached, str) else None
    signature = _native_signature(_spacy_native_state(doc))
    native_fields = _native_fields(doc)
    if sidecar is not None:
        decoded = decode_sidecar(
            sidecar, target="spacy", native_signature=signature
        )
        document = InteropDocument.from_dict(decoded["payload"])
        return InteropResult(
            document,
            sidecar,
            _report(
                direction="import",
                native_fields=native_fields,
                sidecar_fields=_adapter_sidecar_fields(document, target="spacy"),
                omitted_ids=_adapter_omitted_ids(document, target="spacy"),
            ),
        )
    if not allow_lossy:
        raise InteropLossError(
            "spaCy Doc has no aegean.interop/v1 sidecar; unavailable fields: "
            + ", ".join(_LOSSY_IMPORT_FIELDS)
        )
    document = _lossy_document(doc)
    return InteropResult(
        document,
        None,
        _report(
            direction="import",
            native_fields=native_fields,
            lost_fields=_LOSSY_IMPORT_FIELDS,
            warnings=(
                "sentence IDs are generated because spaCy does not store the source IDs",
            ),
        ),
    )
