"""Script-agnostic core data model.

These value objects describe *any* writing system the package supports — a
Linear A syllabogram and a Greek letter are both :class:`Sign`, a ``KU-RO``
word and a Greek word are both :class:`Token`. Nothing here depends on a
particular script; per-script behaviour lives in ``aegean.scripts``.

Numpy/pandas are imported lazily (only inside DataFrame helpers) so importing
the model stays instant and dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TokenKind(str, Enum):
    """The role a token plays in a document's text stream."""

    WORD = "word"            # a (multi-sign) lexical word
    LOGOGRAM = "logogram"    # ideogram / commodity sign
    NUMERAL = "numeral"      # a number or metrological fraction
    SEPARATOR = "separator"  # word/entry divider (e.g. 𐄁)
    PUNCT = "punct"          # punctuation (alphabetic scripts)
    UNKNOWN = "unknown"


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


class SignInventory:
    """The set of signs for a script, indexed by label / glyph / codepoint."""

    def __init__(self, signs: list[Sign], script_id: str = "") -> None:
        self.signs = signs
        self.script_id = script_id
        self._by_label = {s.label: s for s in signs}
        self._by_glyph = {s.glyph: s for s in signs if s.glyph}
        self._by_codepoint = {s.codepoint: s for s in signs if s.codepoint is not None}

    def __len__(self) -> int:
        return len(self.signs)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.signs)

    def by_label(self, label: str) -> Sign | None:
        return self._by_label.get(label)

    def by_glyph(self, glyph: str) -> Sign | None:
        return self._by_glyph.get(glyph)

    def by_codepoint(self, codepoint: int) -> Sign | None:
        return self._by_codepoint.get(codepoint)

    def to_dataframe(self):  # type: ignore[no-untyped-def]
        import pandas as pd  # lazy

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
