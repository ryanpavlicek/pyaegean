"""Lossless JSON (de)serialization helpers for :mod:`aegean.core.corpus`."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from .model import (
    Document,
    DocumentMeta,
    ReadingStatus,
    Sign,
    SignInventory,
    SourceAlignment,
    Token,
    TokenFormState,
    TokenKind,
)
from .provenance import SCHEMA_VERSION, Provenance

# ── (de)serialization helpers for the lossless round-trip ──────────────────
_BOM = "\ufeff"  # a decoded UTF-8 BOM: not whitespace, so str.strip() leaves it in place

_JSON_TYPE_NAMES: dict[type, str] = {
    type(None): "null", bool: "a boolean", int: "a number", float: "a number",
    str: "a string", list: "an array", tuple: "an array", dict: "an object",
}


def _json_type(value: Any) -> str:
    """Name a decoded JSON value's type the way the file's author wrote it."""
    return _JSON_TYPE_NAMES.get(type(value), type(value).__name__)


# The most caller-supplied names quoted back in one message; the rest are counted.
_MAX_NAMED = 5


def _shown(value: Any, *, limit: int = 60) -> str:
    """A repr of a value taken from the file being read, capped to ``limit`` characters.

    Every value quoted back in these messages is untrusted input, and the message reaches
    a terminal or a log: a half-megabyte ``kind`` string would otherwise be echoed whole."""
    if isinstance(value, str) and len(value) > limit:
        return repr(value[: limit - 3] + "...")
    text = repr(value)
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text


def _is_readable_file(path: Path) -> bool:
    """Whether ``path`` names an existing file, for a string that may not be a path at all.

    A JSON payload reaching this check can hold anything: NUL bytes, embedded newlines, a
    length past the filesystem limit. ``Path.is_file`` answers False for most such names on
    its own, and the guard covers the platforms where the refusal surfaces as an error
    instead, so an unusable name never masks the caller's own decode error."""
    try:
        return path.is_file()
    except (OSError, ValueError):
        return False


def _expect_object(value: Any, what: str) -> dict[str, Any]:
    """``value`` as a JSON object, or a ValueError naming ``what`` is malformed."""
    if not isinstance(value, dict):
        raise ValueError(f"{what} must be a JSON object, got {_json_type(value)}")
    return value


def _expect_array(value: Any, what: str) -> list[Any]:
    """``value`` as a JSON array. A string is rejected rather than iterated: taking one
    would silently spread its characters across the field (``"abc"`` → three entries)."""
    if not isinstance(value, list):
        raise ValueError(f"{what} must be a JSON array, got {_json_type(value)}")
    return value


def _expect_str(value: Any, what: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{what} must be a string, got {_json_type(value)}")
    return value


_EnumT = TypeVar("_EnumT", bound=Enum)


def _enum_value(enum_cls: type[_EnumT], value: Any, what: str) -> _EnumT:
    """One of an enum's values, or a ValueError listing what the field accepts."""
    try:
        return enum_cls(value)
    except (ValueError, KeyError, TypeError):
        allowed = ", ".join(repr(member.value) for member in enum_cls)
        raise ValueError(f"{what} is {_shown(value)}, which is not one of: {allowed}") from None


def _read_json_text(path: Path) -> str:
    """Read a JSON file (plain or gzip-compressed) as ``utf-8-sig``.

    A leading UTF-8 BOM is stripped so BOM-less UTF-8 reads identically. Gzip-compressed
    corpus files (magic bytes ``\\x1f\\x8b``) are decompressed transparently, so
    ``Corpus.from_json`` accepts both ``.json`` and ``.json.gz`` assets. A path the OS
    cannot even name — a JSON string that reached this branch, or one longer than the
    filesystem allows — is reported as such."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise ValueError(
            f"cannot read a corpus from {_shown(str(path))}: {exc.strerror or exc}. Pass a path to a "
            "JSON corpus file, a JSON string starting with '{', or a dict to Corpus.from_dict"
        ) from None
    if raw[:2] == b"\x1f\x8b":
        import gzip

        raw = gzip.decompress(raw)
    return raw.decode("utf-8-sig")


def _schema_version(meta: dict[str, Any]) -> int | None:
    """The file's declared schema version, validated.

    The value is not decoration: it selects how this reader treats the file (form state
    is only read from schema 3 and up), so a version this release cannot interpret is
    refused rather than quietly downgrading the file's content. A missing or null
    version is legal and reads as the pre-form-state schema."""
    stored = meta.get("schemaVersion")
    if stored is None:
        return None
    if isinstance(stored, bool) or not isinstance(stored, int):
        raise ValueError(
            f"corpus '_meta'.schemaVersion must be an integer, got {_json_type(stored)} "
            f"({_shown(stored)}); pyaegean writes schema {SCHEMA_VERSION}"
        )
    if stored < 1:
        raise ValueError(
            f"corpus '_meta'.schemaVersion must be 1 or greater, got {stored}"
        )
    if stored > SCHEMA_VERSION:
        raise ValueError(
            f"this corpus file uses schema version {stored}, but this pyaegean "
            f"understands up to {SCHEMA_VERSION} — upgrade pyaegean to read it"
        )
    return stored


def _provenance_to_dict(p: Provenance | None) -> dict[str, Any] | None:
    if p is None:
        return None
    return {
        "source": p.source, "license": p.license, "citation": p.citation,
        "url": p.url, "schema_version": p.schema_version, "notes": list(p.notes),
        "data_version": p.data_version, "edition_fidelity": p.edition_fidelity,
    }


def _provenance_from_dict(d: dict[str, Any] | None) -> Provenance | None:
    if not d:
        return None
    d = _expect_object(d, "corpus 'provenance'")
    return Provenance(
        source=d.get("source", ""), license=d.get("license", ""),
        citation=d.get("citation", ""), url=d.get("url", ""),
        schema_version=d.get("schema_version", SCHEMA_VERSION),
        notes=tuple(_expect_array(d.get("notes") or [], "'provenance'.notes")),
        data_version=d.get("data_version", ""),
        edition_fidelity=d.get("edition_fidelity", ""),
    )


def _inventory_to_dict(inv: SignInventory | None) -> dict[str, Any] | None:
    if inv is None:
        return None
    return {
        "script_id": inv.script_id,
        "signs": [
            {
                "label": s.label, "glyph": s.glyph, "codepoint": s.codepoint,
                "phonetic": s.phonetic, "script_id": s.script_id, "attrs": s.attrs,
            }
            for s in inv.signs
        ],
    }


def _inventory_from_dict(d: dict[str, Any] | None) -> SignInventory | None:
    if not d:
        return None
    obj = _expect_object(d, "corpus 'signInventory'")
    raw_signs = obj.get("signs")
    entries = [] if raw_signs is None else _expect_array(raw_signs, "'signInventory'.signs")
    signs = []
    for i, s in enumerate(entries):
        where = f"'signInventory'.signs[{i}]"
        entry = _expect_object(s, where)
        if "label" not in entry:
            raise ValueError(f"{where} is missing 'label'")
        signs.append(
            Sign(
                label=_expect_str(entry["label"], f"{where}.label"),
                glyph=entry.get("glyph"), codepoint=entry.get("codepoint"),
                phonetic=entry.get("phonetic"), script_id=entry.get("script_id", ""),
                attrs=dict(_expect_object(entry.get("attrs") or {}, f"{where}.attrs")),
            )
        )
    return SignInventory(signs, obj.get("script_id", ""))


def _token_to_dict(t: Token) -> dict[str, Any]:
    d: dict[str, Any] = {
        "text": t.text, "kind": t.kind.value, "signs": list(t.signs),
        "glyphs": t.glyphs, "line_no": t.line_no, "position": t.position,
    }
    if t.status is not ReadingStatus.CERTAIN:  # omit the default to keep JSON compact + back-compatible
        d["status"] = t.status.value
    if t.alt:
        d["alt"] = list(t.alt)
    if t.annotations:
        d["annotations"] = dict(t.annotations)
    if t.alignment is not None:
        d["alignment"] = _alignment_to_dict(t.alignment)
    if t.form_state is not None:
        if not isinstance(t.form_state, TokenFormState):
            raise TypeError("token form_state must be a TokenFormState or None")
        d["form_state"] = t.form_state.to_dict()
    return d


def _token_from_dict(
    d: dict[str, Any], *, allow_form_state: bool = True, context: str = "token"
) -> Token:
    d = _expect_object(d, context)
    for field in ("text", "kind"):
        if field not in d:
            raise ValueError(f"{context} is missing {field!r}")
    raw_alignment = d.get("alignment")
    if raw_alignment is None:
        alignment = None
    elif isinstance(raw_alignment, SourceAlignment):
        # SQLite reconstruction already has a validated typed value.  Reusing it
        # keeps this central decoder the single validation seam.
        alignment = raw_alignment
    elif isinstance(raw_alignment, dict):
        alignment = _alignment_from_dict(raw_alignment, context=context)
    else:
        raise ValueError(
            f"malformed token alignment in {context}: expected an object, "
            f"got {_json_type(raw_alignment)}"
        )
    raw_form_state = d.get("form_state") if allow_form_state else None
    if raw_form_state is None:
        form_state = None
    elif isinstance(raw_form_state, TokenFormState):
        form_state = raw_form_state
    elif isinstance(raw_form_state, dict):
        try:
            form_state = TokenFormState.from_dict(raw_form_state)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"malformed token form_state in {context}: {exc}") from exc
    else:
        raise ValueError(
            f"malformed token form_state in {context}: expected an object, "
            f"got {_json_type(raw_form_state)}"
        )
    return Token(
        text=_expect_str(d["text"], f"{context}: 'text'"),
        kind=_enum_value(TokenKind, d["kind"], f"{context}: 'kind'"),
        signs=tuple(_expect_array(d.get("signs") or [], f"{context}: 'signs'")),
        glyphs=d.get("glyphs"), line_no=d.get("line_no"), position=d.get("position"),
        status=(
            _enum_value(ReadingStatus, d["status"], f"{context}: 'status'")
            if d.get("status")
            else ReadingStatus.CERTAIN
        ),
        alt=tuple(_expect_array(d.get("alt") or [], f"{context}: 'alt'")),
        annotations=dict(_expect_object(d.get("annotations") or {}, f"{context}: 'annotations'")),
        alignment=alignment,
        form_state=form_state,
    )


def _alignment_to_dict(a: SourceAlignment) -> dict[str, Any]:
    """Serialize a typed alignment value without exposing dataclass internals."""
    return {
        "document_id": a.document_id,
        "sentence_id": a.sentence_id,
        "source_token_id": a.source_token_id,
        "original_text": a.original_text,
        "start_char": a.start_char,
        "end_char": a.end_char,
        "whitespace_before": a.whitespace_before,
        "normalized_text": a.normalized_text,
        "normalization_ops": list(a.normalization_ops),
    }


def _span_offset(value: Any, field: str, context: str) -> int:
    """One character offset of an alignment's source span, as an ``int``.

    ``True`` is an ``int`` in Python but never a character offset in a corpus file, so
    booleans are refused alongside every other non-integer."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(
            f"malformed token alignment in {context}: {field} must be an integer, "
            f"got {_json_type(value)} ({_shown(value)})"
        )
    return value


def _alignment_from_dict(d: dict[str, Any], *, context: str = "token") -> SourceAlignment:
    """Deserialize one alignment object, retaining strict constructor checks.

    ``context`` names the document and token the object was read from, so a malformed
    alignment is as locatable in a large file as every other field this reader rejects.
    A value that is not an object is refused by the caller, which knows the token it came
    from; everything below reads the object's own fields."""
    raw_ops = d.get("normalization_ops")
    if raw_ops is not None and not isinstance(raw_ops, (list, tuple)):
        raise ValueError(
            f"malformed token alignment in {context}: normalization_ops must be a JSON "
            f"array, got {_json_type(raw_ops)}"
        )
    start_char = _span_offset(d.get("start_char"), "start_char", context)
    end_char = _span_offset(d.get("end_char"), "end_char", context)
    try:
        return SourceAlignment(
            document_id=d.get("document_id", ""),
            sentence_id=d.get("sentence_id"),
            source_token_id=d.get("source_token_id", ""),
            original_text=d.get("original_text", ""),
            start_char=start_char,
            end_char=end_char,
            whitespace_before=d.get("whitespace_before", ""),
            normalized_text=d.get("normalized_text", ""),
            normalization_ops=tuple(raw_ops or ()),
        )
    except (TypeError, ValueError) as exc:
        # The constructor enforces the span/normalization invariants; without this the
        # only report of a bad span is a bare message naming no document or token.
        raise ValueError(f"malformed token alignment in {context}: {exc}") from exc


def _document_to_dict(d: Document) -> dict[str, Any]:
    # Persistence is a trust boundary: never serialize a source snapshot whose
    # token spans, gaps, or identities are internally inconsistent.
    d.validate_source_alignment()
    return {
        "id": d.id, "script_id": d.script_id, "glyphs": d.glyphs,
        "transcription": d.transcription, "translations": list(d.translations),
        "meta": {
            "site": d.meta.site, "support": d.meta.support, "scribe": d.meta.scribe,
            "findspot": d.meta.findspot, "period": d.meta.period, "name": d.meta.name,
            "images": list(d.meta.images), "notes": list(d.meta.notes),
        },
        "tokens": [_token_to_dict(t) for t in d.tokens],
        "lines": [list(line) for line in d.lines],
        "source_text": d.source_text,
    }


def _document_from_dict(
    d: dict[str, Any], *, allow_form_state: bool = True, index: int | None = None
) -> Document:
    where = "a corpus document" if index is None else f"corpus document {index}"
    d = _expect_object(d, where)
    if "id" not in d:
        raise ValueError(f"{where} is missing 'id'")
    document_id = _expect_str(d["id"], f"{where}: 'id'")
    if not document_id:
        raise ValueError(f"{where} has an empty 'id'")
    # The id names the document in every message below and is itself file content, so the
    # quoted form is capped once here while the document keeps its full id.
    shown_id = _shown(document_id)
    m = _expect_object(d.get("meta") or {}, f"document {shown_id}: 'meta'")
    meta = DocumentMeta(
        site=m.get("site", ""), support=m.get("support", ""), scribe=m.get("scribe", ""),
        findspot=m.get("findspot", ""), period=m.get("period", ""), name=m.get("name", ""),
        images=tuple(_expect_array(m.get("images") or [], f"document {shown_id}: 'meta'.images")),
        notes=tuple(_expect_array(m.get("notes") or [], f"document {shown_id}: 'meta'.notes")),
    )
    tokens = [
        _token_from_dict(
            t,
            allow_form_state=allow_form_state,
            context=f"document {shown_id}, token {i}",
        )
        for i, t in enumerate(
            _expect_array(d.get("tokens") or [], f"document {shown_id}: 'tokens'")
        )
    ]
    source_text = d.get("source_text")
    if source_text is not None and not isinstance(source_text, str):
        raise ValueError(
            f"document {shown_id}: source_text must be a string or null, "
            f"got {_json_type(source_text)}"
        )
    for token in tokens:
        if token.alignment is None:
            continue
        if token.alignment.document_id != document_id:
            raise ValueError(
                f"document {shown_id}: token alignment belongs to "
                f"document {_shown(token.alignment.document_id)}"
            )
        if source_text is not None:
            token.alignment.validate_source(source_text, document_id=document_id)
    raw_lines = _expect_array(d.get("lines") or [], f"document {shown_id}: 'lines'")
    lines = [
        list(_expect_array(line, f"document {shown_id}: line {li}"))
        for li, line in enumerate(raw_lines)
    ]
    # Validate the line index lists against the token count up front: an out-of-range index
    # (a corpus file whose lines got out of sync with tokens) otherwise loads fine and then
    # crashes with a bare IndexError at a much later, unrelated call (line_tokens, _repr_html_,
    # an EpiDoc/workbench export). Fail here with a message that names the malformed source.
    n = len(tokens)
    for li, line in enumerate(lines):
        for i in line:
            if not isinstance(i, int) or isinstance(i, bool) or i < 0 or i >= n:
                raise ValueError(
                    f"document {shown_id}: line {li} references token index {_shown(i)}, "
                    f"but the document has {n} token(s); the source is malformed"
                )
    document = Document(
        id=document_id, script_id=d.get("script_id", ""),
        tokens=tokens, lines=lines,
        glyphs=d.get("glyphs", ""), transcription=d.get("transcription", ""),
        translations=list(
            _expect_array(d.get("translations") or [], f"document {shown_id}: 'translations'")
        ),
        meta=meta,
        source_text=source_text,
    )
    document.validate_source_alignment()
    return document
