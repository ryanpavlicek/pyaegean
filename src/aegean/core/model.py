"""Script-agnostic core data model.

These value objects describe *any* writing system the package supports — a
Linear A syllabogram and a Greek letter are both `Sign`, a ``KU-RO``
word and a Greek word are both `Token`. Nothing here depends on a
particular script; per-script behaviour lives in ``aegean.scripts``.

Numpy/pandas are imported lazily (only inside DataFrame helpers) so importing
the model stays instant and dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Literal


class TokenKind(str, Enum):
    """The role a token plays in a document's text stream."""

    WORD = "word"            # a (multi-sign) lexical word
    LOGOGRAM = "logogram"    # ideogram / commodity sign
    NUMERAL = "numeral"      # a number or metrological fraction
    SEPARATOR = "separator"  # word/entry divider (e.g. 𐄁)
    PUNCT = "punct"          # punctuation (alphabetic scripts)
    UNKNOWN = "unknown"


class ReadingStatus(str, Enum):
    """Editorial certainty of a token's reading (Leiden / EpiDoc conventions).

    ``CERTAIN`` is the default. The others mark the apparatus an epigraphic edition must
    preserve — damaged, restored, or lost text. The bundled loaders decode each edition's
    apparatus into these statuses (the Leiden underdots, brackets, and erasure marks of
    the Cypriot and Linear A corpora); a bring-your-own EpiDoc corpus populates them from
    ``<unclear>`` / ``<supplied>`` / ``<gap>`` markup, and the EpiDoc writer emits them
    back.
    """

    CERTAIN = "certain"      # securely read
    UNCLEAR = "unclear"      # damaged but read (EpiDoc <unclear>; Leiden underdot)
    RESTORED = "restored"    # editorially supplied (EpiDoc <supplied>; Leiden [ ])
    LOST = "lost"            # not preserved / lacuna (read from EpiDoc <gap> or
    #                          <supplied reason="undefined">; Leiden [---])


@dataclass(frozen=True, slots=True)
class SourceMarkupRef:
    """A semantic reference to an element in a source edition.

    This is deliberately *not* a raw XML-byte or offset claim.  ``path`` is a
    semantic locator supplied by the importer. The EpiDoc reader uses unique
    document-order labels such as ``"reg[17]"``; the locator is stable for that
    parsed source tree, not across arbitrary edits to the XML. ``attrs`` preserves
    source attribute order for faithful diagnostics.
    """

    source_id: str
    path: str
    tag: str
    attrs: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name in ("source_id", "path", "tag"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if not isinstance(self.attrs, tuple):
            raise TypeError("attrs must be an ordered tuple of (name, value) pairs")
        seen_attrs: set[str] = set()
        for item in self.attrs:
            if not isinstance(item, tuple) or len(item) != 2:
                raise TypeError("attrs must contain (name, value) tuples")
            key, value = item
            if not isinstance(key, str) or not key.strip():
                raise TypeError("source markup attribute names must be non-empty strings")
            if not isinstance(value, str):
                raise TypeError("source markup attribute values must be strings")
            if key in seen_attrs:
                raise ValueError(f"duplicate source markup attribute name {key!r}")
            seen_attrs.add(key)

    @property
    def attributes(self) -> tuple[tuple[str, str], ...]:
        """Alias for ``attrs`` used by callers that prefer the expanded name."""
        return self.attrs

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {
            "source_id": self.source_id,
            "path": self.path,
            "tag": self.tag,
            "attrs": [[key, value] for key, value in self.attrs],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SourceMarkupRef":
        """Decode and validate one canonical source reference mapping."""
        if not isinstance(value, dict):
            raise TypeError("source_ref must be an object")
        expected = {"source_id", "path", "tag", "attrs"}
        if set(value) != expected:
            raise ValueError("source_ref must contain exactly source_id, path, tag, attrs")
        attrs = value["attrs"]
        if not isinstance(attrs, list):
            raise TypeError("source_ref.attrs must be a JSON array")
        pairs: list[tuple[str, str]] = []
        for item in attrs:
            if not isinstance(item, list) or len(item) != 2:
                raise TypeError("source_ref.attrs must contain two-item arrays")
            pairs.append((item[0], item[1]))
        return cls(value["source_id"], value["path"], value["tag"], tuple(pairs))


@dataclass(frozen=True, slots=True)
class FormSegment:
    """One ordered piece of a token form and its editorial reading status.

    An empty segment is permitted only for ``ReadingStatus.LOST``.  That models a
    lacuna without inventing replacement text; non-empty restored text remains
    visibly marked as editor-supplied by its status and optional source reference.
    """

    text: str
    status: ReadingStatus = ReadingStatus.CERTAIN
    source_ref: SourceMarkupRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("form segment text must be a string")
        if not isinstance(self.status, ReadingStatus):
            try:
                object.__setattr__(self, "status", ReadingStatus(self.status))
            except (TypeError, ValueError) as exc:
                raise TypeError("form segment status must be a ReadingStatus") from exc
        if not isinstance(self.source_ref, (SourceMarkupRef, type(None))):
            raise TypeError("form segment source_ref must be a SourceMarkupRef or None")
        if not self.text and self.status is not ReadingStatus.LOST:
            raise ValueError("only LOST form segments may have empty text")

    @property
    def role(self) -> ReadingStatus:
        """Compatibility spelling for code that calls the status a segment role."""
        return self.status

    @property
    def source(self) -> SourceMarkupRef | None:
        """Compatibility alias for ``source_ref``."""
        return self.source_ref

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "status": self.status.value,
            "source_ref": self.source_ref.to_dict() if self.source_ref is not None else None,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FormSegment":
        if not isinstance(value, dict):
            raise TypeError("form segment must be an object")
        expected = {"text", "status", "source_ref"}
        if set(value) != expected:
            raise ValueError("form segment must contain exactly text, status, source_ref")
        raw_ref = value["source_ref"]
        ref = None if raw_ref is None else SourceMarkupRef.from_dict(raw_ref)
        return cls(value["text"], ReadingStatus(value["status"]), ref)


@dataclass(frozen=True, slots=True)
class TokenFormState:
    """Lossless form states for one token, independent of display ``Token.text``.

    ``diplomatic`` is the explicitly supplied/original form.  ``regularized`` and
    ``normalized`` are optional editorial/model forms; ``model_input`` records the
    exact string actually sent to a model.  ``model_input_source`` is a constrained
    provenance label rather than an unverifiable free-form claim.  ``segments``
    retain ordered supplied/unclear/lost pieces and may encode source choices, so
    their concatenation is intentionally not required to equal ``diplomatic``.
    """

    diplomatic: str
    regularized: str | None = None
    normalized: str | None = None
    model_input: str | None = None
    segments: tuple[FormSegment, ...] = ()
    model_input_ops: tuple[str, ...] = ()
    model_input_source: Literal["diplomatic", "regularized", "normalized", "explicit"] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.diplomatic, str):
            raise TypeError("diplomatic must be a string")
        if self.model_input is not None and not isinstance(self.model_input, str):
            raise TypeError("model_input must be a string or None")
        if self.model_input is None and self.model_input_source is not None:
            raise ValueError("model_input_source must be None when model_input is None")
        if self.model_input is None and self.model_input_ops:
            raise ValueError("model_input_ops must be empty when model_input is None")
        if self.model_input is not None and self.model_input_source is None:
            raise ValueError("model_input_source is required when model_input is provided")
        for name in ("regularized", "normalized"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string or None")
        if not isinstance(self.segments, tuple):
            raise TypeError("segments must be an ordered tuple of FormSegment values")
        if any(not isinstance(segment, FormSegment) for segment in self.segments):
            raise TypeError("segments must contain FormSegment values")
        if not isinstance(self.model_input_ops, tuple):
            raise TypeError("model_input_ops must be a tuple of strings")
        if any(not isinstance(op, str) or not op for op in self.model_input_ops):
            raise ValueError("model_input_ops must contain non-empty strings")
        allowed = {"diplomatic", "regularized", "normalized", "explicit"}
        if self.model_input_source is not None and self.model_input_source not in allowed:
            raise ValueError(
                "model_input_source must be one of diplomatic, regularized, normalized, explicit"
            )
        if self.model_input_source == "regularized" and self.regularized is None:
            raise ValueError("regularized model_input_source requires regularized text")
        if self.model_input_source == "normalized" and self.normalized is None:
            raise ValueError("normalized model_input_source requires normalized text")

    @property
    def original(self) -> str:
        """Alias for the explicit diplomatic/original form."""
        return self.diplomatic

    @property
    def model_input_provenance(self) -> str | None:
        """Read-only alias for the constrained ``model_input_source`` label."""
        return self.model_input_source

    @property
    def operations(self) -> tuple[str, ...]:
        """Read-only alias for the ordered model-input operations."""
        return self.model_input_ops

    @property
    def supplied_text(self) -> str:
        return "".join(s.text for s in self.segments if s.status is ReadingStatus.RESTORED)

    @property
    def unclear_text(self) -> str:
        return "".join(s.text for s in self.segments if s.status is ReadingStatus.UNCLEAR)

    @property
    def lost_text(self) -> str:
        return "".join(s.text for s in self.segments if s.status is ReadingStatus.LOST)

    @property
    def supplied(self) -> bool:
        return any(s.status is ReadingStatus.RESTORED for s in self.segments)

    @property
    def restored(self) -> bool:
        return self.supplied

    @property
    def unclear(self) -> bool:
        return any(s.status is ReadingStatus.UNCLEAR for s in self.segments)

    @property
    def lost(self) -> bool:
        return any(s.status is ReadingStatus.LOST for s in self.segments)

    @property
    def has_uncertainty(self) -> bool:
        return self.unclear

    @property
    def has_damage(self) -> bool:
        return self.unclear or self.lost

    @property
    def editorial_status(self) -> ReadingStatus:
        """Most severe segment status, ordered LOST > RESTORED > UNCLEAR > CERTAIN."""
        for status in (
            ReadingStatus.LOST,
            ReadingStatus.RESTORED,
            ReadingStatus.UNCLEAR,
            ReadingStatus.CERTAIN,
        ):
            if any(segment.status is status for segment in self.segments):
                return status
        return ReadingStatus.CERTAIN

    @property
    def status(self) -> ReadingStatus:
        """Compatibility alias for the derived editorial status."""
        return self.editorial_status

    def to_dict(self) -> dict[str, Any]:
        return {
            "diplomatic": self.diplomatic,
            "regularized": self.regularized,
            "normalized": self.normalized,
            "model_input": self.model_input,
            "segments": [segment.to_dict() for segment in self.segments],
            "model_input_ops": list(self.model_input_ops),
            "model_input_source": self.model_input_source,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TokenFormState":
        if not isinstance(value, dict):
            raise TypeError("form_state must be an object")
        expected = {
            "diplomatic", "regularized", "normalized", "model_input", "segments",
            "model_input_ops", "model_input_source",
        }
        if set(value) != expected:
            raise ValueError("form_state contains unknown or missing fields")
        raw_segments = value["segments"]
        raw_ops = value["model_input_ops"]
        if not isinstance(raw_segments, list):
            raise TypeError("form_state.segments must be a JSON array")
        if not isinstance(raw_ops, list):
            raise TypeError("form_state.model_input_ops must be a JSON array")
        return cls(
            diplomatic=value["diplomatic"], regularized=value["regularized"],
            normalized=value["normalized"], model_input=value["model_input"],
            segments=tuple(FormSegment.from_dict(item) for item in raw_segments),
            model_input_ops=tuple(raw_ops), model_input_source=value["model_input_source"],
        )


@dataclass(frozen=True, slots=True)
class SourceAlignment:
    """Lossless provenance for one token in an exact source snapshot.

    Character positions are half-open Python string offsets, not encoded-byte
    positions.  ``original_text`` is the exact source slice and
    ``normalized_text`` is the tokenizer's normalized view of that slice.  For a
    typed editorial token, :class:`TokenFormState` separately records the later
    regularized/normalized selection and the exact value handed to an analyzer.
    The alignment value is intentionally immutable so annotation and export code
    cannot silently alter the source mapping after it has been created.
    """

    document_id: str
    sentence_id: str | None
    source_token_id: str
    original_text: str
    start_char: int
    end_char: int
    whitespace_before: str
    normalized_text: str
    normalization_ops: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject malformed mappings at their boundary rather than later in exports."""
        for name in ("document_id", "source_token_id"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
            if not value:
                raise ValueError(f"{name} must be non-empty")
        if self.sentence_id is not None:
            if not isinstance(self.sentence_id, str):
                raise TypeError("sentence_id must be a string or None")
            if not self.sentence_id:
                raise ValueError("sentence_id must be non-empty when provided")
        for name in ("original_text", "whitespace_before", "normalized_text"):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f"{name} must be a string")
        if any(not character.isspace() for character in self.whitespace_before):
            raise ValueError("whitespace_before must contain only Unicode whitespace")
        for name in ("start_char", "end_char"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.end_char < self.start_char:
            raise ValueError("end_char must be greater than or equal to start_char")
        if len(self.original_text) != self.end_char - self.start_char:
            raise ValueError(
                "original_text length must equal end_char - start_char "
                "(Python code-point offsets)"
            )
        if not isinstance(self.normalization_ops, tuple):
            raise TypeError("normalization_ops must be a tuple of strings")
        if any(not isinstance(op, str) or not op for op in self.normalization_ops):
            raise ValueError("normalization_ops must contain non-empty strings")
        if bool(self.normalization_ops) != (self.normalized_text != self.original_text):
            raise ValueError(
                "normalization_ops must be non-empty exactly when normalized_text "
                "differs from original_text"
            )

    def validate_source(self, source_text: str, document_id: str | None = None) -> None:
        """Validate the owning document and exact source slice.

        ``ValueError`` identifies either a document mismatch or a changed source
        snapshot.  This is deliberately a strict check: a mapping must never be
        projected against a merely similar normalized string.
        """
        if not isinstance(source_text, str):
            raise TypeError("source_text must be a string")
        if document_id is not None and document_id != self.document_id:
            raise ValueError(
                f"alignment belongs to document {self.document_id!r}, "
                f"not {document_id!r}"
            )
        if self.end_char > len(source_text):
            raise ValueError(
                f"source slice [{self.start_char}:{self.end_char}] falls outside "
                f"the {len(source_text)}-character source"
            )
        if source_text[self.start_char:self.end_char] != self.original_text:
            raise ValueError(
                f"source slice [{self.start_char}:{self.end_char}] does not match "
                f"original_text for token {self.source_token_id!r}"
            )


@dataclass(frozen=True, slots=True)
class Sign:
    """One graphic unit of a script (syllabogram, letter, or logogram)."""

    label: str
    glyph: str | None = None
    codepoint: int | None = None
    phonetic: str | None = None
    script_id: str = ""
    # Script-specific facts kept flexible: e.g. shared_with_linearb,
    # confidence, alt_glyphs, category="logogram".
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Token:
    """One unit in a document's transliterated text stream."""

    text: str                       # transliteration, e.g. "KU-RO"
    kind: TokenKind
    signs: tuple[str, ...] = ()     # decomposed sign labels, e.g. ("KU", "RO")
    glyphs: str | None = None       # Unicode form, when known
    line_no: int | None = None
    position: int | None = None     # index within the document's token stream
    status: ReadingStatus = ReadingStatus.CERTAIN  # editorial certainty (Leiden/EpiDoc)
    alt: tuple[str, ...] = ()       # alternate readings (EpiDoc <app>/<rdg>); text is the lemma
    # Script-specific per-token facts kept flexible (mirrors Sign.attrs): e.g. the
    # Greek NT carries lemma, morph, strongs, gloss, normalized, upos, ref here.
    annotations: dict[str, str] = field(default_factory=dict)
    # Optional lossless source mapping.  Excluded from legacy equality so old
    # positional/value semantics remain stable while callers can inspect it.
    alignment: SourceAlignment | None = field(default=None, compare=False)
    # Optional A6 form-state record.  Appended last and excluded from equality so
    # legacy Token value/positional semantics and cache consumers remain unchanged.
    form_state: TokenFormState | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if self.form_state is not None and not isinstance(self.form_state, TokenFormState):
            raise TypeError("form_state must be a TokenFormState or None")


@dataclass(frozen=True, slots=True)
class DocumentMeta:
    """Bibliographic / archaeological metadata for a document."""

    site: str = ""
    support: str = ""
    scribe: str = ""
    findspot: str = ""
    period: str = ""
    name: str = ""
    images: tuple[str, ...] = ()    # references/URLs only — never binaries
    notes: tuple[str, ...] = ()     # editorial notes / bibliography (<note>, <bibl>)


@dataclass(slots=True)
class Document:
    """One inscription / tablet / text."""

    id: str
    script_id: str
    tokens: list[Token]
    lines: list[list[int]]          # each line is a list of indices into tokens
    glyphs: str = ""
    transcription: str = ""
    translations: list[str] = field(default_factory=list)
    meta: DocumentMeta = field(default_factory=DocumentMeta)
    # Exact source snapshot used by any token alignments.  Excluded from legacy
    # equality for compatibility with pre-A4 Document values.
    source_text: str | None = field(default=None, compare=False)

    def validate_source_alignment(self) -> None:
        """Validate all token mappings against this document's exact source.

        Legacy documents (no source snapshot and no alignments) remain valid.  A
        source-bearing document is intentionally all-or-nothing: every token must
        have a mapping, mappings must point to this document, be ordered without
        overlap, use unique IDs, and record the exact whitespace gap preceding
        each source slice.
        """
        has_alignment = any(token.alignment is not None for token in self.tokens)
        if self.source_text is None and not has_alignment:
            return
        if self.source_text is None:
            raise ValueError(
                f"document {self.id!r} has token alignment but no source_text"
            )
        seen_ids: set[str] = set()
        previous_start = -1
        previous_end = 0
        for ordinal, token in enumerate(self.tokens):
            alignment = token.alignment
            if alignment is None:
                raise ValueError(
                    f"document {self.id!r} token {ordinal} is missing source alignment"
                )
            alignment.validate_source(self.source_text, document_id=self.id)
            if alignment.source_token_id in seen_ids:
                raise ValueError(
                    f"document {self.id!r} has duplicate source_token_id "
                    f"{alignment.source_token_id!r}"
                )
            seen_ids.add(alignment.source_token_id)
            if alignment.start_char <= previous_start:
                raise ValueError(
                    f"document {self.id!r} token alignments are not in strict "
                    "monotonic source order"
                )
            if alignment.start_char < previous_end:
                raise ValueError(
                    f"document {self.id!r} token alignments overlap at "
                    f"[{alignment.start_char}:{alignment.end_char}]"
                )
            expected_gap = self.source_text[previous_end:alignment.start_char]
            if alignment.whitespace_before != expected_gap:
                raise ValueError(
                    f"document {self.id!r} token {ordinal} has incorrect "
                    "whitespace_before"
                )
            previous_start = alignment.start_char
            previous_end = alignment.end_char

    def _of_kind(self, kind: TokenKind) -> list[Token]:
        return [t for t in self.tokens if t.kind is kind]

    @property
    def words(self) -> list[Token]:
        return self._of_kind(TokenKind.WORD)

    @property
    def numerals(self) -> list[Token]:
        return self._of_kind(TokenKind.NUMERAL)

    @property
    def logograms(self) -> list[Token]:
        return self._of_kind(TokenKind.LOGOGRAM)

    @property
    def line_tokens(self) -> list[list[Token]]:
        """Tokens regrouped by physical line."""
        return [[self.tokens[i] for i in line] for line in self.lines]

    def __len__(self) -> int:
        return len(self.tokens)

    def _repr_html_(self) -> str:
        """Rich rendering in Jupyter/Colab (plain ``repr`` everywhere else)."""
        from ._html import card, esc, table

        meta = self.meta
        sub = " · ".join(
            esc(b) for b in (meta.site, meta.period, meta.support, meta.scribe) if b
        )
        title = esc(self.id) + (
            f" <span style='color:#888;font-weight:400'>{sub}</span>" if sub else ""
        )
        counts = f"{len(self.words)} words · {len(self.numerals)} numerals · {len(self.tokens)} tokens"
        body = f"<div style='color:#666;font-size:0.85em;margin-bottom:6px'>{esc(counts)}</div>"
        line_rows = [
            (str(i + 1), " ".join(t.text for t in toks))
            for i, toks in enumerate(self.line_tokens)
        ]
        body += table(["line", "tokens"], line_rows) if line_rows else "<em>no tokens</em>"
        return card(title, body)


class SignInventory:
    """The set of signs for a script, indexed by label / glyph / codepoint."""

    _SUBSCRIPT_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")

    def __init__(self, signs: list[Sign], script_id: str = "") -> None:
        self.signs = signs
        self.script_id = script_id
        self._by_label = {s.label: s for s in signs}
        # A second index folding subscript sign-numbers to ASCII digits, so a label
        # the corpus prints with a Unicode subscript (RA₂) resolves against an
        # inventory that stores the ASCII form (RA2), and vice versa. First wins.
        self._by_label_fold: dict[str, Sign] = {}
        for s in signs:
            self._by_label_fold.setdefault(s.label.translate(self._SUBSCRIPT_DIGITS), s)
        # Two entries sharing a glyph or codepoint is a data problem worth
        # surfacing, not silently indexing last-wins (which is how a mislabeled
        # duplicate hides). Warn and keep the first, mirroring Corpus's
        # duplicate-id handling.
        self._by_glyph: dict[str, Sign] = {}
        self._by_codepoint: dict[int, Sign] = {}
        dupes: list[str] = []
        for s in signs:
            if s.glyph:
                if s.glyph in self._by_glyph:
                    dupes.append(f"glyph {s.glyph} ({self._by_glyph[s.glyph].label}/{s.label})")
                else:
                    self._by_glyph[s.glyph] = s
            if s.codepoint is not None:
                if s.codepoint in self._by_codepoint:
                    dupes.append(
                        f"codepoint U+{s.codepoint:04X} "
                        f"({self._by_codepoint[s.codepoint].label}/{s.label})"
                    )
                else:
                    self._by_codepoint[s.codepoint] = s
        if dupes:
            import warnings

            shown = ", ".join(dupes[:5]) + (f" (+{len(dupes) - 5} more)" if len(dupes) > 5 else "")
            warnings.warn(
                f"SignInventory: {len(dupes)} duplicate glyph/codepoint mapping(s), "
                f"keeping the first of each: {shown}",
                stacklevel=2,
            )

    def __len__(self) -> int:
        return len(self.signs)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.signs)

    def by_label(self, label: str) -> Sign | None:
        hit = self._by_label.get(label)
        if hit is not None:
            return hit
        return self._by_label_fold.get(label.translate(self._SUBSCRIPT_DIGITS))

    def by_glyph(self, glyph: str) -> Sign | None:
        return self._by_glyph.get(glyph)

    def by_codepoint(self, codepoint: int) -> Sign | None:
        return self._by_codepoint.get(codepoint)

    def copy(self) -> "SignInventory":
        """An independent copy: each `Sign` is rebuilt with its own ``attrs`` dict.

        `Sign` is a frozen value object but its ``attrs`` is a mutable per-sign dict for
        user analysis; a shared/cached inventory (the ``@lru_cache``-d ``*_inventory()``
        accessors) would otherwise let one caller's ``attrs`` edit leak into every later
        reader and into a subsequent corpus load. Mirrors `Corpus.copy` for the sign layer."""
        return SignInventory([replace(s, attrs=dict(s.attrs)) for s in self.signs], self.script_id)

    def to_dataframe(self):  # type: ignore[no-untyped-def]
        try:
            import pandas as pd  # lazy, optional [data] extra
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "to_dataframe() needs pandas; install it with: pip install 'pyaegean[data]'"
            ) from exc

        return pd.DataFrame(
            {
                "label": s.label,
                "glyph": s.glyph,
                "codepoint": s.codepoint,
                "phonetic": s.phonetic,
                **s.attrs,
            }
            for s in self.signs
        )

    def _repr_html_(self) -> str:
        """Rich rendering in Jupyter/Colab (plain ``repr`` everywhere else)."""
        from ._html import card, esc, table

        cap = 200
        shown = self.signs[:cap]
        rows = [
            (s.label, s.glyph or "", s.codepoint if s.codepoint is not None else "", s.phonetic or "")
            for s in shown
        ]
        title = (
            f"{esc(self.script_id or 'sign')} inventory "
            f"<span style='color:#888;font-weight:400'>· {len(self.signs)} signs</span>"
        )
        body = table(["label", "glyph", "codepoint", "phonetic"], rows)
        if len(self.signs) > cap:
            body += (
                f"<div style='color:#888;font-size:0.8em'>… {len(self.signs) - cap} more</div>"
            )
        return card(title, body)
