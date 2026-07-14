"""UD (CoNLL-U) evaluation harness — pyaegean on the field's standard benchmark.

`aegean.greek.heldout` measures generalization *within* the AGDT under pyaegean's own
protocol, and `aegean.greek.proiel` measures it on out-of-AGDT text. This module measures
the pipeline on the **Universal Dependencies** Ancient Greek test folds with the **official
CoNLL 2018 shared-task evaluator** — the protocol behind the published cross-tool numbers
(see ``docs/benchmarks.md``) — and builds the **leakage-exclusion manifest** that every
future trained model must honour.

Data: ``UD_Ancient_Greek-Perseus`` / ``UD_Ancient_Greek-PROIEL``, pinned to commits,
licensed **CC BY-NC-SA** (Perseus 2.5, PROIEL 3.0) — fetched to the cache for **evaluation
only**, never bundled and never trained on (the PROIEL handling). The evaluator (``conll18_ud_eval.py``, Mozilla
Public License 2.0) is fetched to the cache pinned by sha256 and imported from there.

Protocol (spelled out in ``docs/benchmarks.md``):

- **Gold tokenization.** The pipeline runs over each fold's gold FORM column, so scores
  measure tagging/lemma/parsing quality, not tokenizer agreement.
- **No tagset collapsing.** UPOS and lemmas are scored exactly as emitted (unlike
  `evaluate_on_proiel`, which reconciles tagsets) — convention gaps count against us.
- **DEPREL.** The shipped neural pipeline emits UD relations, so **LAS** is scored directly
  against UD gold. (The legacy pure-Python parser emits AGDT/Prague labels, for which only
  **UAS** is comparable; it is reported as a baseline, not as the accuracy claim.)
- **Leakage.** UD Perseus is converted *from* the AGDT, so its sentence ids point straight at
  AGDT files (``tlg0008….tb.xml@197``). The shipped neural model's training split removes every
  UD-Perseus dev+test sentence via the `agdt_ud_overlap` exclusion manifest, so its Perseus
  scores are leakage-clean. The legacy full-AGDT backends have *seen* those sentences, so their
  Perseus-fold scores are an in-training upper bound. The PROIEL fold is clean for every
  pyaegean model (none trains on PROIEL).
"""

from __future__ import annotations

import importlib.util
import json
import re
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ..data import cache_dir, download_file

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Sequence

    from ..analysis.stats import BootstrapCI

__all__ = [
    "UDDependency",
    "UDDocument",
    "UDEmptyNode",
    "UDComment",
    "UDItem",
    "UDMiscEntry",
    "UDMultiwordToken",
    "UDNodeID",
    "UDOpaqueRow",
    "UDProjection",
    "UDRow",
    "UDSentence",
    "UDToken",
    "agdt_ud_overlap",
    "bootstrap_ud",
    "evaluate_on_ud",
    "evaluate_by_genre",
    "dump_conllu",
    "dumps_conllu",
    "load_conllu",
    "load_conllu_document",
    "loads_conllu",
    "write_conllu",
    "UnsupportedUDStructureError",
    "ud_path",
]

_CACHE_SUBDIR = "ud-grc"

# UD Ancient Greek treebanks, pinned for reproducibility (CC BY-NC-SA: Perseus 2.5, PROIEL 3.0
# — per each treebank's README; eval only).
_UD_REPO: dict[str, tuple[str, str]] = {
    "perseus": ("UD_Ancient_Greek-Perseus", "331ddef91411d0e6549744ee889e05549e6da77d"),
    "proiel": ("UD_Ancient_Greek-PROIEL", "a4ab8d436de97d4598d410d91ea20b4127d04a5f"),
}
# The two UD folds carry DIFFERENT Creative-Commons versions (each treebank's own README at the
# pinned commit): UD-Perseus is 2.5, UD-PROIEL is 3.0. Both are NonCommercial + ShareAlike, so
# both are evaluation-only, never bundled, never trained on — but the version differs, so it is
# recorded per treebank rather than blanket-stated.
_UD_LICENSE: dict[str, str] = {
    "perseus": "CC BY-NC-SA 2.5",
    "proiel": "CC BY-NC-SA 3.0",
}
_SPLITS = ("train", "dev", "test")

# AGDT (Perseus) TLG author-group id -> literary genre, for genre-sliced evaluation. The
# UD-Perseus sentence ids begin with the AGDT source filename, which begins with the TLG author
# id (e.g. "tlg0012.tlg001…@197" -> Homer). Genre boundaries are editorial (Hesiod is grouped
# with epic as didactic hexameter). Only ids that actually occur in a fold matter; the rest fall
# to "other". `evaluate_by_genre` reports the unmapped ids so this table can be audited/extended.
_AUTHOR_GENRE: dict[str, str] = {
    "tlg0012": "epic",     # Homer
    "tlg0013": "epic",     # Homeric Hymns (hexameter)
    "tlg0020": "epic",     # Hesiod (didactic hexameter)
    "tlg0085": "tragedy",  # Aeschylus
    "tlg0011": "tragedy",  # Sophocles
    "tlg0006": "tragedy",  # Euripides
    "tlg0019": "comedy",   # Aristophanes
    "tlg0016": "prose",    # Herodotus
    "tlg0003": "prose",    # Thucydides
    "tlg0059": "prose",    # Plato
    "tlg0032": "prose",    # Xenophon
    "tlg0007": "prose",    # Plutarch
    "tlg0008": "prose",    # Athenaeus (Deipnosophistae)
    "tlg0060": "prose",    # Diodorus Siculus
}


def _sent_genre(sent_id: str) -> tuple[str, str]:
    """(author id, genre) for a UD sentence id like ``tlg0012.tlg001.perseus-grc1.tb.xml@197``."""
    head = sent_id.rpartition("@")[0] or sent_id  # drop the "@197" sentence index
    author = head.split(".", 1)[0]
    return author, _AUTHOR_GENRE.get(author, "other")

# The official CoNLL 2018 shared-task evaluator (MPL 2.0), pinned by content hash.
_EVAL_URL = "https://universaldependencies.org/conll18/conll18_ud_eval.py"
_EVAL_SHA256 = "1072e02af00b1a56205b5e8216d51dee9b8944a104d80744afaccc78859fcb16"

_EXCLUSION_NAME = "agdt-ud-exclusion.json"


_WORD_ID_RE = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_RANGE_ID_RE = re.compile(r"([1-9][0-9]*)-([1-9][0-9]*)\Z")
_EMPTY_ID_RE = re.compile(r"(0|[1-9][0-9]*)\.([1-9][0-9]*)\Z")


@dataclass(frozen=True, slots=True)
class UDNodeID:
    """A structurally typed CoNLL-U identifier, retained without float coercion.

    ``kind`` is ``word``, ``root``, ``range``, ``empty``, or ``unknown``.  The
    ``unknown`` form is used only by lenient parsing so malformed input can be
    inspected and re-exported; strict parsing rejects it with a line number.
    """

    raw: str
    kind: Literal["word", "root", "range", "empty", "unknown"]
    major: int | None = None
    minor: int | None = None
    end: int | None = None

    @classmethod
    def parse(cls, raw: str, *, strict: bool = True) -> "UDNodeID":
        if not isinstance(raw, str) or not raw:
            if strict:
                raise ValueError("CoNLL-U ID must be a non-empty string")
            return cls(str(raw), "unknown")
        if _WORD_ID_RE.fullmatch(raw):
            number = int(raw)
            return cls(raw, "root" if number == 0 else "word", major=number)
        match = _RANGE_ID_RE.fullmatch(raw)
        if match:
            start, end = (int(value) for value in match.groups())
            if start >= end:
                if strict:
                    raise ValueError("multiword ID range must have start < end")
                return cls(raw, "unknown")
            return cls(raw, "range", major=start, end=end)
        match = _EMPTY_ID_RE.fullmatch(raw)
        if match:
            major, minor = (int(value) for value in match.groups())
            # Official UD permits 0.1; preserving it is important because it is
            # a valid enhanced/empty identifier, not a malformed float.
            return cls(raw, "empty", major=major, minor=minor)
        if strict:
            raise ValueError(f"invalid CoNLL-U ID {raw!r}")
        return cls(raw, "unknown")

    @property
    def is_word(self) -> bool:
        return self.kind == "word"

    @property
    def is_range(self) -> bool:
        return self.kind == "range"

    @property
    def is_empty(self) -> bool:
        return self.kind == "empty"


@dataclass(frozen=True, slots=True)
class UDDependency:
    """One parsed ``DEPS`` arc; raw head text remains available on the row."""

    head: UDNodeID
    relation: str


@dataclass(frozen=True, slots=True)
class UDMiscEntry:
    """One ordered ``MISC`` item; a bare key has ``value=None``."""

    key: str
    value: str | None = None


def _parse_deps(raw: str, *, strict: bool) -> tuple[UDDependency, ...]:
    if raw in ("", "_"):
        return ()
    out: list[UDDependency] = []
    for item in raw.split("|"):
        head, sep, relation = item.partition(":")
        if not sep or not relation:
            if strict:
                raise ValueError(f"invalid DEPS item {item!r}")
            continue
        try:
            node_id = UDNodeID.parse(head, strict=True)
        except ValueError:
            if strict:
                raise
            continue
        if node_id.kind == "range" or node_id.kind == "unknown":
            if strict:
                raise ValueError(f"invalid enhanced DEPS head {head!r}")
            continue
        out.append(UDDependency(node_id, relation))
    return tuple(out)


def _parse_misc(raw: str, *, strict: bool) -> tuple[UDMiscEntry, ...]:
    if raw in ("", "_"):
        return ()
    out: list[UDMiscEntry] = []
    for item in raw.split("|"):
        if not item:
            if strict:
                raise ValueError("empty MISC item")
            continue
        key, sep, value = item.partition("=")
        if not key:
            if strict:
                raise ValueError("MISC key must be non-empty")
            continue
        out.append(UDMiscEntry(key, value if sep else None))
    return tuple(out)


@dataclass(frozen=True, slots=True)
class UDToken:
    """One syntactic word, retaining additive enhanced/raw annotations.

    The first eight fields and their positional/equality behavior are the legacy
    projection.  Additive raw/typed fields are excluded from equality so old
    callers comparing parsed words remain compatible.
    """

    id: int
    form: str
    lemma: str
    upos: str
    xpos: str
    feats: str
    head: int
    deprel: str
    deps: tuple[UDDependency, ...] = field(default=(), compare=False)
    deps_raw: str = field(default="_", compare=False)
    misc: tuple[UDMiscEntry, ...] = field(default=(), compare=False)
    misc_raw: str = field(default="_", compare=False)
    raw_columns: tuple[str, ...] = field(default=(), compare=False)
    line_number: int | None = field(default=None, compare=False)


@dataclass(frozen=True, slots=True)
class UDMultiwordToken:
    """One CoNLL-U range row such as ``4-5``."""

    start: int
    end: int
    form: str
    raw_columns: tuple[str, ...] = ()
    deps: tuple[UDDependency, ...] = field(default=(), compare=False)
    deps_raw: str = field(default="_", compare=False)
    misc: tuple[UDMiscEntry, ...] = field(default=(), compare=False)
    misc_raw: str = field(default="_", compare=False)
    line_number: int | None = field(default=None, compare=False)

    @property
    def id(self) -> str:
        return f"{self.start}-{self.end}"


@dataclass(frozen=True, slots=True)
class UDEmptyNode:
    """One CoNLL-U empty node such as ``5.1`` (including valid ``0.1``)."""

    major: int
    minor: int
    raw_columns: tuple[str, ...] = ()
    deps: tuple[UDDependency, ...] = field(default=(), compare=False)
    deps_raw: str = field(default="_", compare=False)
    misc: tuple[UDMiscEntry, ...] = field(default=(), compare=False)
    misc_raw: str = field(default="_", compare=False)
    line_number: int | None = field(default=None, compare=False)

    @property
    def id(self) -> str:
        return f"{self.major}.{self.minor}"


@dataclass(frozen=True, slots=True)
class UDOpaqueRow:
    """A malformed row retained by lenient parsing for forensic re-export."""

    raw_columns: tuple[str, ...]
    line_number: int | None = field(default=None, compare=False)

    @property
    def id(self) -> str:
        return self.raw_columns[0] if self.raw_columns else ""


UDRow = UDToken | UDMultiwordToken | UDEmptyNode | UDOpaqueRow


@dataclass(frozen=True, slots=True)
class UDComment:
    """A preserved comment item in the original sentence order."""

    text: str


UDItem = UDRow | UDComment


@dataclass(frozen=True, slots=True)
class UDProjection:
    """Explicit mapping from model ordinals to original word IDs."""

    ordinal_to_id: tuple[tuple[int, int], ...]
    omitted_ranges: tuple[str, ...] = ()
    omitted_empty_nodes: tuple[str, ...] = ()
    enhanced_dependencies_present: bool = False

    @property
    def word_ids(self) -> tuple[int, ...]:
        return tuple(original for _ordinal, original in self.ordinal_to_id)

    @property
    def omitted_ids(self) -> tuple[str, ...]:
        return self.omitted_ranges + self.omitted_empty_nodes


@dataclass(frozen=True, slots=True)
class UDSentence:
    """One sentence with a legacy word projection and optional full row stream."""

    sent_id: str
    text: str
    tokens: tuple[UDToken, ...]
    rows: tuple[UDRow, ...] = field(default=(), compare=False)
    comments: tuple[str, ...] = field(default=(), compare=False)
    items: tuple[UDItem, ...] = field(default=(), compare=False)
    _raw_block: str | None = field(default=None, init=False, compare=False, repr=False)
    _raw_signature: tuple[Any, ...] = field(default=(), init=False, compare=False, repr=False)
    _document_raw_text: str | None = field(
        default=None, init=False, compare=False, repr=False
    )
    _document_raw_signature: tuple[Any, ...] = field(
        default=(), init=False, compare=False, repr=False
    )
    _document_leading_comments: tuple[str, ...] = field(
        default=(), init=False, compare=False, repr=False
    )
    _document_trailing_comments: tuple[str, ...] = field(
        default=(), init=False, compare=False, repr=False
    )

    @property
    def multiword_tokens(self) -> tuple[UDMultiwordToken, ...]:
        return tuple(row for row in self.rows if isinstance(row, UDMultiwordToken))

    @property
    def empty_nodes(self) -> tuple[UDEmptyNode, ...]:
        return tuple(row for row in self.rows if isinstance(row, UDEmptyNode))

    @property
    def projection(self) -> UDProjection:
        rows = _effective_rows(self)
        word_ordinal = 0
        ordinal_to_id_list: list[tuple[int, int]] = []
        for row in rows:
            if isinstance(row, UDToken):
                word_ordinal += 1
                ordinal_to_id_list.append((word_ordinal, row.id))
        ordinal_to_id = tuple(ordinal_to_id_list)
        return UDProjection(
            ordinal_to_id=ordinal_to_id,
            omitted_ranges=tuple(row.id for row in rows if isinstance(row, UDMultiwordToken)),
            omitted_empty_nodes=tuple(row.id for row in rows if isinstance(row, UDEmptyNode)),
            enhanced_dependencies_present=any(
                isinstance(row, (UDToken, UDMultiwordToken, UDEmptyNode))
                and row.deps_raw not in ("", "_")
                for row in rows
            ),
        )

    @property
    def surface_projection(self) -> UDProjection:
        """Alias naming the model-facing word projection explicitly."""
        return self.projection


@dataclass(frozen=True, slots=True)
class UDDocument:
    """A complete CoNLL-U document, including sentence order and document comments."""

    sentences: tuple[UDSentence, ...]
    leading_comments: tuple[str, ...] = ()
    trailing_comments: tuple[str, ...] = ()
    _raw_text: str | None = field(default=None, init=False, compare=False, repr=False)
    _raw_signature: tuple[Any, ...] = field(default=(), init=False, compare=False, repr=False)

    def dumps(self, *, canonical: bool = False) -> str:
        if not canonical and self._raw_text is not None and _document_signature(self) == self._raw_signature:
            return self._raw_text
        body = dump_conllu(self.sentences, canonical=True)
        if self.leading_comments:
            body = "\n".join(self.leading_comments) + "\n" + body
        if self.trailing_comments:
            body += "\n".join(self.trailing_comments) + "\n"
        return body


def ud_path(treebank: str = "perseus", split: str = "test", *, download: bool = True) -> Path:
    """The cached path of a UD Ancient Greek fold, fetching it on first use.

    ``treebank`` is ``"perseus"`` or ``"proiel"``; ``split`` is ``"train"``/``"dev"``/
    ``"test"``. The data is CC BY-NC-SA (Perseus 2.5, PROIEL 3.0) — cached for evaluation
    only, never bundled."""
    repo, commit = _UD_REPO[treebank]
    if split not in _SPLITS:
        raise ValueError(f"split must be one of {_SPLITS}; got {split!r}")
    name = f"grc_{treebank}-ud-{split}.conllu"
    dest = cache_dir() / _CACHE_SUBDIR / name
    if download and not dest.exists():
        download_file(f"https://raw.githubusercontent.com/UniversalDependencies/{repo}/{commit}/{name}", dest)
    return dest


def _read_conllu_source(source: Path | str) -> str:
    """Read a path or raw CoNLL-U string without making string callers write temp files."""
    if isinstance(source, Path):
        with source.open("r", encoding="utf-8", newline="") as handle:
            return handle.read()
    if not isinstance(source, str):
        raise TypeError("CoNLL-U source must be a path or string")
    if "\n" in source or "\r" in source:
        return source
    path = Path(source)
    if path.exists() or path.suffix.lower() in {".conllu", ".conll", ".conll-u"}:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return handle.read()
    return source


def _effective_rows(sent: UDSentence) -> tuple[UDRow, ...]:
    """Return structural rows, reflecting a legacy ``tokens=`` replacement if present."""
    if not sent.rows:
        return sent.tokens
    row_tokens = tuple(row for row in sent.rows if isinstance(row, UDToken))
    if len(row_tokens) == len(sent.tokens) and all(
        _row_signature(original) == _row_signature(replacement)
        for original, replacement in zip(row_tokens, sent.tokens, strict=True)
    ):
        return sent.rows
    replacements = iter(sent.tokens)
    result: list[UDRow] = []
    for row in sent.rows:
        if isinstance(row, UDToken):
            try:
                result.append(next(replacements))
            except StopIteration:
                continue
        else:
            result.append(row)
    result.extend(replacements)
    return tuple(result)


def _row_signature(row: UDRow) -> tuple[Any, ...]:
    if isinstance(row, UDToken):
        return (
            "word", row.id, row.form, row.lemma, row.upos, row.xpos, row.feats,
            row.head, row.deprel, row.deps, row.deps_raw, row.misc, row.misc_raw,
            row.raw_columns,
        )
    if isinstance(row, UDMultiwordToken):
        return (
            "range", row.start, row.end, row.form, row.deps, row.deps_raw,
            row.misc, row.misc_raw, row.raw_columns,
        )
    if isinstance(row, UDEmptyNode):
        return (
            "empty", row.major, row.minor, row.deps, row.deps_raw,
            row.misc, row.misc_raw, row.raw_columns,
        )
    return ("opaque", row.raw_columns)


def _sentence_signature(
    sent_id: str, text: str, tokens: tuple[UDToken, ...], rows: tuple[UDRow, ...],
    comments: tuple[str, ...], items: tuple[UDItem, ...] = (),
) -> tuple[Any, ...]:
    item_signature = tuple(
        ("comment", item.text) if isinstance(item, UDComment) else ("row", _row_signature(item))
        for item in items
    )
    return (
        sent_id, text, comments,
        tuple(_row_signature(row) for row in rows),
        tuple(_row_signature(token) for token in tokens),
        item_signature,
    )


def _document_signature(document: UDDocument) -> tuple[Any, ...]:
    return (
        document.leading_comments,
        document.trailing_comments,
        tuple(
            _sentence_signature(
                sent.sent_id,
                sent.text,
                sent.tokens,
                _effective_rows(sent),
                sent.comments,
                sent.items,
            )
            for sent in document.sentences
        ),
    )


def _validate_rows(rows: tuple[UDRow, ...], *, strict: bool, line_number: int | None = None) -> None:
    if not strict:
        return
    word_ids: set[int] = set()
    row_ids: set[str] = set()
    ranges: list[UDMultiwordToken] = []
    empty_ids: set[tuple[int, int]] = set()
    positions: dict[str, int] = {}

    def where(row: UDRow) -> str:
        number = getattr(row, "line_number", None) or line_number
        return f" on line {number}" if number is not None else ""

    for row in rows:
        if isinstance(row, UDOpaqueRow):
            raise ValueError(f"invalid CoNLL-U row{where(row)}")
        if isinstance(row, UDToken):
            if row.id <= 0 or row.id in word_ids:
                raise ValueError(f"duplicate or non-positive word ID {row.id}{where(row)}")
            word_ids.add(row.id)
            row_ids.add(str(row.id))
            positions[str(row.id)] = len(positions)
            if row.head < 0 or (row.head != 0 and row.head not in word_ids):
                # Forward basic heads are legal in UD, so defer reference checks below.
                if row.head < 0:
                    raise ValueError(
                        f"invalid basic HEAD {row.head!r} for word {row.id}{where(row)}"
                    )
            if row.deprel in ("", "_"):
                raise ValueError(f"empty basic DEPREL for word {row.id}{where(row)}")
            continue
        if isinstance(row, UDMultiwordToken):
            if row.start <= 0 or row.start >= row.end:
                raise ValueError(f"invalid multiword range {row.id!r}{where(row)}")
            if row.id in row_ids:
                raise ValueError(f"duplicate row ID {row.id!r}{where(row)}")
            row_ids.add(row.id)
            ranges.append(row)
            positions[row.id] = len(positions)
            if row.deps_raw not in ("", "_") and not row.deps:
                raise ValueError(f"invalid DEPS for multiword row {row.id!r}{where(row)}")
            if row.raw_columns and (
                any(row.raw_columns[index] != "_" for index in (2, 3, 4, 6, 7, 8))
                or row.raw_columns[5] not in ("_", "Typo=Yes")
            ):
                raise ValueError(
                    f"multiword row {row.id!r} has invalid non-FORM fields{where(row)}"
                )
            continue
        if row.major < 0 or row.minor <= 0:
            raise ValueError(f"invalid empty-node ID {row.id!r}{where(row)}")
        if row.id in row_ids or (row.major, row.minor) in empty_ids:
            raise ValueError(f"duplicate empty-node ID {row.id!r}{where(row)}")
        row_ids.add(row.id)
        empty_ids.add((row.major, row.minor))
        positions[row.id] = len(positions)
        if row.raw_columns and any(row.raw_columns[index] != "_" for index in (6, 7)):
            raise ValueError(f"empty node {row.id!r} must use '_' for HEAD/DEPREL{where(row)}")
        if not row.deps:
            raise ValueError(f"empty node {row.id!r} must have non-empty DEPS{where(row)}")
    ordered_ranges = sorted(ranges, key=lambda item: (item.start, item.end))
    for current, following in zip(ordered_ranges, ordered_ranges[1:]):
        if following.start <= current.end:
            raise ValueError(f"overlapping multiword-token ranges{where(following)}")
    expected = 1
    for row in rows:
        if isinstance(row, UDToken):
            if row.id != expected:
                raise ValueError(
                    f"word IDs must be sequential: expected {expected}, got {row.id}{where(row)}"
                )
            expected += 1
    for range_row in ranges:
        if any(index not in word_ids for index in range(range_row.start, range_row.end + 1)):
            raise ValueError(
                f"multiword range {range_row.id} does not cover all word IDs{where(range_row)}"
            )
        range_position = positions[range_row.id]
        first_position = next(
            position
            for position, row in enumerate(rows)
            if isinstance(row, UDToken) and row.id == range_row.start
        )
        if range_position + 1 != first_position:
            raise ValueError(
                f"multiword range {range_row.id} must immediately precede its words"
                f"{where(range_row)}"
            )
    for row in rows:
        if isinstance(row, UDEmptyNode) and row.major > 0:
            major_position = next(
                (position for position, candidate in enumerate(rows)
                 if isinstance(candidate, UDToken) and candidate.id == row.major),
                None,
            )
            row_position = positions[row.id]
            if major_position is None or row_position <= major_position:
                raise ValueError(
                    f"empty node {row.id!r} must follow word {row.major}{where(row)}"
                )
            next_word_position = next(
                (
                    position
                    for position, candidate in enumerate(rows)
                    if isinstance(candidate, UDToken) and candidate.id == row.major + 1
                ),
                None,
            )
            if next_word_position is not None and row_position >= next_word_position:
                raise ValueError(
                    f"empty node {row.id!r} must precede word {row.major + 1}{where(row)}"
                )
        if isinstance(row, UDEmptyNode) and row.major == 0:
            first_word_position = next(
                (
                    position
                    for position, candidate in enumerate(rows)
                    if isinstance(candidate, UDToken)
                ),
                None,
            )
            if first_word_position is not None and positions[row.id] >= first_word_position:
                raise ValueError(f"empty node {row.id!r} must precede word 1{where(row)}")
    for major in sorted({row.major for row in rows if isinstance(row, UDEmptyNode)}):
        major_rows = [
            row for row in rows if isinstance(row, UDEmptyNode) and row.major == major
        ]
        suffixes = [row.minor for row in major_rows]
        if suffixes != list(range(1, len(suffixes) + 1)):
            raise ValueError(
                f"empty-node suffixes for major {major} must be ordered and sequential"
                f"{where(major_rows[0])}"
            )
    for row in rows:
        if isinstance(row, UDToken) and (row.head != 0 and row.head not in word_ids):
            raise ValueError(
                f"invalid basic HEAD {row.head!r} for word {row.id}{where(row)}"
            )
        if not isinstance(row, (UDToken, UDMultiwordToken, UDEmptyNode)):
            continue
        for dep in row.deps:
            if dep.head.kind == "range" or dep.head.kind == "unknown":
                raise ValueError(f"invalid enhanced DEPS head {dep.head.raw!r}{where(row)}")
            if dep.head.kind != "root" and dep.head.raw not in row_ids:
                raise ValueError(f"unknown enhanced DEPS head {dep.head.raw!r}{where(row)}")
    root_rows = [row for row in rows if isinstance(row, UDToken) and row.head == 0]
    if rows and word_ids and len(root_rows) != 1:
        first_word = next(row for row in rows if isinstance(row, UDToken))
        raise ValueError(
            f"basic tree must contain exactly one root, found {len(root_rows)}"
            f"{where(root_rows[0] if root_rows else first_word)}"
        )
    for row in rows:
        if not isinstance(row, UDToken) or row.head == 0:
            continue
        seen: set[int] = set()
        head = row.head
        while head:
            if head in seen:
                raise ValueError(f"cycle in basic tree at word {row.id}{where(row)}")
            seen.add(head)
            parent = next((candidate for candidate in rows if isinstance(candidate, UDToken) and candidate.id == head), None)
            if parent is None or parent.head == 0:
                break
            head = parent.head


def _parse_conllu_text(text: str, *, strict: bool = False) -> UDDocument:
    if strict and text and re.search(r"(?:\r\n|\n){2}\Z", text) is None:
        raise ValueError(f"line {len(text.splitlines())}: final blank line is required")
    sentences: list[UDSentence] = []
    sent_id = text_value = ""
    comments: list[str] = []
    rows: list[UDRow] = []
    items: list[UDItem] = []
    raw_lines: list[str] = []
    leading_comments: list[str] = []
    trailing_comments: list[str] = []

    def finish() -> None:
        nonlocal sent_id, text_value, comments, rows, items, raw_lines
        if not rows:
            if comments:
                (leading_comments if not sentences else trailing_comments).extend(comments)
                comments = []
                items = []
                raw_lines = []
            return
        row_tuple = tuple(rows)
        tokens = tuple(row for row in row_tuple if isinstance(row, UDToken))
        comment_tuple = tuple(comments)
        _validate_rows(row_tuple, strict=strict)
        item_tuple = tuple(items)
        signature = _sentence_signature(
            sent_id, text_value, tokens, row_tuple, comment_tuple, item_tuple
        )
        sentence = UDSentence(
            sent_id=sent_id,
            text=text_value,
            tokens=tokens,
            rows=row_tuple,
            comments=comment_tuple,
            items=item_tuple,
        )
        object.__setattr__(sentence, "_raw_block", "".join(raw_lines))
        object.__setattr__(sentence, "_raw_signature", signature)
        sentences.append(sentence)
        sent_id = text_value = ""
        comments = []
        rows = []
        items = []
        raw_lines = []

    for line_number, raw in enumerate(text.splitlines(keepends=True), start=1):
        line = raw.rstrip("\r\n")
        if not line.strip():
            raw_lines.append(raw)
            finish()
            continue
        raw_lines.append(raw)
        if line.startswith("#"):
            if strict and rows:
                raise ValueError(
                    f"line {line_number}: comments must precede sentence data rows"
                )
            comments.append(line)
            items.append(UDComment(line))
            if line.startswith("# sent_id") and "=" in line:
                sent_id = line.split("=", 1)[1].strip()
            elif line.startswith("# text") and "=" in line:
                text_value = line.split("=", 1)[1].strip()
            continue
        cols = line.split("\t")
        if len(cols) != 10:
            if strict:
                raise ValueError(
                    f"line {line_number}: expected 10 tab-separated CoNLL-U columns, "
                    f"got {len(cols)}"
                )
            rows.append(UDOpaqueRow(tuple(cols), line_number))
            items.append(rows[-1])
            continue
        if strict and any(column == "" for column in cols):
            raise ValueError(f"line {line_number}: empty CoNLL-U column")
        raw_id = cols[0]
        try:
            node_id = UDNodeID.parse(raw_id, strict=strict)
        except ValueError as exc:
            raise ValueError(f"line {line_number}: {exc}") from exc
        if node_id.kind == "unknown":
            rows.append(UDOpaqueRow(tuple(cols), line_number))
            items.append(rows[-1])
            continue
        if node_id.kind == "root":
            if strict:
                raise ValueError(f"line {line_number}: ID 0 is only valid as an enhanced HEAD")
            rows.append(UDOpaqueRow(tuple(cols), line_number))
            items.append(rows[-1])
            continue
        if node_id.kind == "word":
            head_raw = cols[6]
            if _WORD_ID_RE.fullmatch(head_raw) or (not strict and head_raw.isdigit()):
                head = int(head_raw)
            elif strict:
                raise ValueError(f"line {line_number}: invalid basic HEAD {head_raw!r}")
            else:
                head = 0
            try:
                deps = _parse_deps(cols[8], strict=strict)
                misc = _parse_misc(cols[9], strict=strict)
            except ValueError as exc:
                raise ValueError(f"line {line_number}: {exc}") from exc
            word_row = UDToken(
                    id=node_id.major or 0, form=cols[1], lemma=cols[2], upos=cols[3],
                    xpos=cols[4], feats=cols[5], head=head, deprel=cols[7],
                    deps=deps, deps_raw=cols[8], misc=misc, misc_raw=cols[9],
                    raw_columns=tuple(cols),
                    line_number=line_number,
                )
            rows.append(word_row)
            items.append(word_row)
        elif node_id.kind == "range":
            try:
                deps = _parse_deps(cols[8], strict=strict)
                misc = _parse_misc(cols[9], strict=strict)
            except ValueError as exc:
                raise ValueError(f"line {line_number}: {exc}") from exc
            range_row = UDMultiwordToken(
                node_id.major or 0, node_id.end or 0, cols[1], tuple(cols),
                deps=deps, deps_raw=cols[8], misc=misc, misc_raw=cols[9],
                line_number=line_number,
            )
            rows.append(range_row)
            items.append(range_row)
        elif node_id.kind == "empty":
            try:
                deps = _parse_deps(cols[8], strict=strict)
                misc = _parse_misc(cols[9], strict=strict)
            except ValueError as exc:
                raise ValueError(f"line {line_number}: {exc}") from exc
            empty_row = UDEmptyNode(
                node_id.major or 0, node_id.minor or 0, tuple(cols),
                deps=deps, deps_raw=cols[8], misc=misc, misc_raw=cols[9],
                line_number=line_number,
            )
            rows.append(empty_row)
            items.append(empty_row)
    finish()
    document = UDDocument(
        tuple(sentences),
        leading_comments=tuple(leading_comments),
        trailing_comments=tuple(trailing_comments),
    )
    object.__setattr__(document, "_raw_text", text)
    signature = _document_signature(document)
    for sentence in document.sentences:
        object.__setattr__(sentence, "_document_raw_text", text)
        object.__setattr__(sentence, "_document_raw_signature", signature)
        object.__setattr__(
            sentence, "_document_leading_comments", document.leading_comments
        )
        object.__setattr__(
            sentence, "_document_trailing_comments", document.trailing_comments
        )
    object.__setattr__(document, "_raw_signature", signature)
    return document


def load_conllu(source: Path | str, *, strict: bool = False) -> list[UDSentence]:
    """Load CoNLL-U from a path or raw string.

    The default is compatibility-lenient: valid words, ranges, empty nodes, comments,
    and all ten raw columns are retained, while malformed rows become opaque rows.
    ``strict=True`` turns malformed columns, IDs, structural ranges, DEPS, MISC, and
    references into line-aware ``ValueError`` exceptions.
    """
    return [
        sentence
        for sentence in _parse_conllu_text(_read_conllu_source(source), strict=strict).sentences
        if sentence.tokens
    ]


def loads_conllu(text: str, *, strict: bool = False) -> list[UDSentence]:
    """Load CoNLL-U directly from a string."""
    return load_conllu(text, strict=strict)


def load_conllu_document(source: Path | str, *, strict: bool = False) -> UDDocument:
    """Load a complete CoNLL-U document wrapper, retaining raw source text."""
    return _parse_conllu_text(_read_conllu_source(source), strict=strict)


def _word_columns(token: UDToken) -> tuple[str, ...]:
    expected = (
        str(token.id), token.form, token.lemma, token.upos, token.xpos, token.feats,
        str(token.head), token.deprel, token.deps_raw, token.misc_raw,
    )
    if (
        len(token.raw_columns) == 10
        and tuple(token.raw_columns) == expected
        and token.deps == _parse_deps(token.deps_raw, strict=False)
        and token.misc == _parse_misc(token.misc_raw, strict=False)
    ):
        return token.raw_columns
    columns = (
        str(token.id), token.form, token.lemma, token.upos, token.xpos, token.feats,
        str(token.head), token.deprel, token.deps_raw, token.misc_raw,
    )
    return _annotation_columns(
        columns, token.deps_raw, token.deps, token.misc_raw, token.misc
    )


def _annotation_columns(
    raw_columns: tuple[str, ...],
    deps_raw: str,
    deps: tuple[UDDependency, ...],
    misc_raw: str,
    misc: tuple[UDMiscEntry, ...],
) -> tuple[str, ...]:
    """Apply typed annotation edits while retaining every unrelated raw column."""
    columns = list(raw_columns) if len(raw_columns) == 10 else ["_"] * 10
    parsed_deps = _parse_deps(deps_raw, strict=False)
    deps_value = deps_raw or "_"
    if deps != parsed_deps:
        deps_value = "_"
    if deps:
        deps_value = "|".join(f"{dep.head.raw}:{dep.relation}" for dep in deps)
    parsed_misc = _parse_misc(misc_raw, strict=False)
    misc_value = misc_raw or "_"
    if misc != parsed_misc:
        misc_value = "_"
    if misc:
        misc_value = "|".join(
            entry.key if entry.value is None else f"{entry.key}={entry.value}"
            for entry in misc
        )
    columns[8] = deps_value
    columns[9] = misc_value
    return tuple(columns)


def _row_columns(row: UDRow) -> tuple[str, ...]:
    if isinstance(row, UDToken):
        return _word_columns(row)
    if isinstance(row, UDMultiwordToken):
        if len(row.raw_columns) == 10 and row.raw_columns[0] == row.id and row.raw_columns[1] == row.form:
            return _annotation_columns(
                row.raw_columns, row.deps_raw, row.deps, row.misc_raw, row.misc
            )
        columns = (row.id, row.form, "_", "_", "_", "_", "_", "_", "_", "_")
        return _annotation_columns(columns, row.deps_raw, row.deps, row.misc_raw, row.misc)
    if isinstance(row, UDEmptyNode):
        if len(row.raw_columns) == 10 and row.raw_columns[0] == row.id:
            return _annotation_columns(
                row.raw_columns, row.deps_raw, row.deps, row.misc_raw, row.misc
            )
        columns = (row.id, "_", "_", "_", "_", "_", "_", "_", "_", "_")
        return _annotation_columns(columns, row.deps_raw, row.deps, row.misc_raw, row.misc)
    return row.raw_columns


def _canonical_comments(sent: UDSentence) -> list[str]:
    """Update standard metadata comments while retaining every unknown comment."""
    comments: list[str] = []
    saw_sent_id = False
    saw_text = False
    for comment in sent.comments:
        if comment.startswith("# sent_id") and "=" in comment:
            saw_sent_id = True
            if sent.sent_id:
                comments.append(f"# sent_id = {sent.sent_id}")
        elif comment.startswith("# text") and "=" in comment:
            saw_text = True
            if sent.text:
                comments.append(f"# text = {sent.text}")
        else:
            comments.append(comment)
    additions: list[str] = []
    if sent.sent_id and not saw_sent_id:
        additions.append(f"# sent_id = {sent.sent_id}")
    if sent.text and not saw_text:
        additions.append(f"# text = {sent.text}")
    return additions + comments


def _canonical_sentence(sent: UDSentence) -> str:
    comments = _canonical_comments(sent)
    rows = _effective_rows(sent)
    item_rows = tuple(
        item for item in sent.items
        if isinstance(item, (UDToken, UDMultiwordToken, UDEmptyNode, UDOpaqueRow))
    )
    item_comments = tuple(item.text for item in sent.items if isinstance(item, UDComment))
    if sent.items and item_comments == tuple(comments) and len(item_rows) == len(rows) and all(
        _row_signature(left) == _row_signature(right)
        for left, right in zip(item_rows, rows, strict=True)
    ):
        lines = [
            item.text if isinstance(item, UDComment) else "\t".join(_row_columns(item))
            for item in sent.items
        ]
    else:
        lines = comments + ["\t".join(_row_columns(row)) for row in rows]
    return "\n".join(lines) + "\n\n"


def dump_conllu(
    sentences: Iterable[UDSentence] | UDDocument, *, canonical: bool = False
) -> str:
    """Serialize sentences, preserving unchanged parsed blocks or using canonical rows."""
    if isinstance(sentences, UDDocument):
        return sentences.dumps(canonical=canonical)
    sequence = tuple(sentences)
    if not canonical and sequence:
        document_raw = sequence[0]._document_raw_text
        document_signature = sequence[0]._document_raw_signature
        if document_raw is not None and document_signature == _document_signature(
            UDDocument(
                sequence,
                leading_comments=sequence[0]._document_leading_comments,
                trailing_comments=sequence[0]._document_trailing_comments,
            )
        ):
            return document_raw
    blocks: list[str] = []
    for sent in sequence:
        rows = _effective_rows(sent)
        signature = _sentence_signature(sent.sent_id, sent.text, sent.tokens, rows, sent.comments, sent.items)
        if not canonical and sent._raw_block is not None and signature == sent._raw_signature:
            blocks.append(sent._raw_block)
        else:
            blocks.append(_canonical_sentence(sent))
    return "".join(blocks)


def dumps_conllu(
    sentences: Iterable[UDSentence] | UDDocument, *, canonical: bool = False
) -> str:
    """Alias for :func:`dump_conllu` for string-oriented callers."""
    return dump_conllu(sentences, canonical=canonical)


def write_conllu(
    sentences: Iterable[UDSentence] | UDDocument, path: Path | str, *, canonical: bool = False
) -> None:
    """Write CoNLL-U text atomically to ``path``."""
    from .._atomic import atomic_path

    content = (
        sentences.dumps(canonical=canonical)
        if isinstance(sentences, UDDocument)
        else dump_conllu(sentences, canonical=canonical)
    )
    with atomic_path(path) as tmp:
        with tmp.open("w", encoding="utf-8", newline="") as handle:
            handle.write(content)


# --- running the pipeline over gold tokens -------------------------------------


def _tag_forms(forms: list[str]) -> list[str]:
    """UPOS per gold token, mirroring `aegean.greek.pos_tags`'s cascade without
    re-tokenizing: closed-class lexicon → treebank lookup → context tagger → heuristic."""
    from . import tagger, treebank
    from .pos import _LEXICON, _norm, pos_tag

    context: list[str] | None = None
    if tagger.active() is not None:
        context = tagger.tag_pos(forms)
    lex = treebank.active()
    out: list[str] = []
    for i, form in enumerate(forms):
        if not any(ch.isalpha() for ch in form):
            out.append(pos_tag(form))  # PUNCT / NUM
        elif _norm(form) in _LEXICON:
            out.append(_LEXICON[_norm(form)])
        elif lex is not None and lex.pos(form) is not None:
            out.append(lex.pos(form) or "X")
        elif context is not None:
            out.append(context[i])
        else:
            out.append(pos_tag(form))
    return out


class UnsupportedUDStructureError(ValueError):
    """Raised when a complete CoNLL-U prediction is requested for unsupported rows."""


def pipeline_conllu(
    sentences: list[UDSentence],
    *,
    parse: bool = False,
    progress: Callable[[int, int], None] | None = None,
    batch_size: int | None = None,
    on_unsupported: Literal["project", "error"] = "project",
) -> str:
    """Run the active pyaegean pipeline over gold-tokenized sentences, emitting CoNLL-U.

    FORM is the gold token (gold tokenization — see the module docstring); LEMMA and UPOS
    come from the active cascade (whatever backends are switched on); HEAD/DEPREL come
    from `aegean.greek.parse` when ``parse=True`` (requires `use_parser`), else a flat
    placeholder that makes UAS/LAS meaningless (the caller omits them). XPOS/FEATS are
    not emitted by the current stack (``_``). ``progress`` (optional) is called as
    ``progress(done, total)`` after each analyzed sentence — the hook the long fold
    evaluations report through; the output is unaffected. ``batch_size`` (optional) runs
    the **neural** pipeline's encoder over that many sentences at a time (one ONNX call
    per chunk) — a throughput convenience; the recorded benchmark protocol is the
    sequential default (``None``), and without an active joint model the value has no
    effect. Structural rows and enhanced annotations are deliberately projected out of
    predictions; pass ``on_unsupported="error"`` when a caller requires a complete
    predictive output.
    """
    from . import joint
    from .lemmatize import lemmatize

    if on_unsupported not in ("project", "error"):
        raise ValueError("on_unsupported must be 'project' or 'error'")
    if on_unsupported == "error":
        unsupported: list[str] = []
        for sent in sentences:
            projection = sent.projection
            if any(isinstance(row, UDOpaqueRow) for row in sent.rows):
                unsupported.append(sent.sent_id or "<anonymous>")
            elif projection.omitted_ranges or projection.omitted_empty_nodes:
                unsupported.append(sent.sent_id or "<anonymous>")
            elif projection.enhanced_dependencies_present:
                unsupported.append(sent.sent_id or "<anonymous>")
        if unsupported:
            raise UnsupportedUDStructureError(
                "complete predictive CoNLL-U output is unsupported for sentence(s): "
                + ", ".join(unsupported)
            )

    if parse:
        from .syntax import parse as parse_tree

    if batch_size is not None and batch_size < 1:
        raise ValueError(f"batch_size must be a positive integer, got {batch_size!r}")
    total = len(sentences)
    analyses: Iterator[joint.SentenceAnalysis] | None = None
    batch_model = joint.active() if batch_size is not None else None
    if batch_model is not None and batch_size is not None:
        m, bs = batch_model, batch_size

        def _batched() -> Iterator[joint.SentenceAnalysis]:
            for start in range(0, total, bs):
                chunk = sentences[start : start + bs]
                yield from m.analyze_batch([[t.form for t in s.tokens] for s in chunk])

        analyses = _batched()
    lines: list[str] = []
    for done, sent in enumerate(sentences, start=1):
        if progress is not None and done > 1:
            progress(done - 1, total)  # the previous sentence just finished
        forms = [t.form for t in sent.tokens]
        model = joint.active()
        if model is not None:  # the neural pipeline: one encoder pass fills every column
            ana = next(analyses) if analyses is not None else model.analyze(forms)
            if sent.sent_id:
                lines.append(f"# sent_id = {sent.sent_id}")
            if sent.text:
                lines.append(f"# text = {sent.text}")
            for i in range(len(forms)):
                lines.append("	".join((
                    str(i + 1), forms[i], ana.lemma[i], ana.upos[i], ana.xpos[i],
                    ana.feats[i], str(ana.head[i]), ana.deprel[i], "_", "_")))
            lines.append("")
            continue
        lemmas = [lemmatize(f) for f in forms]
        tags = _tag_forms(forms)
        # Placeholder when not parsing: a valid single-root flat tree (the evaluator
        # rejects multi-root sentences); UAS/LAS are meaningless and reported as None.
        heads = [0] + [1] * (len(forms) - 1)
        rels = ["root"] + ["dep"] * (len(forms) - 1)
        if parse:
            tree = parse_tree(forms)
            for tok in tree.tokens:
                heads[tok.id - 1] = tok.head
                rels[tok.id - 1] = tok.relation
            # The evaluator requires exactly one root per sentence; the baseline arc-eager
            # parser can leave several tokens on the root. Standard normalization: keep the
            # first root, re-attach the rest to it (counted as-is by UAS — no gold peeking).
            roots = [i for i, h in enumerate(heads) if h == 0]
            if not roots:
                heads[0] = 0
                rels[0] = "root"
            else:
                for i in roots[1:]:
                    heads[i] = roots[0] + 1
        if sent.sent_id:
            lines.append(f"# sent_id = {sent.sent_id}")
        if sent.text:
            lines.append(f"# text = {sent.text}")
        for i, form in enumerate(forms):
            lines.append(
                "\t".join(
                    (str(i + 1), form, lemmas[i] or form, tags[i], "_", "_",
                     str(heads[i]), rels[i], "_", "_")
                )
            )
        lines.append("")
    if progress is not None and total:
        progress(total, total)  # the last sentence (the in-loop call reports done-1)
    return "\n".join(lines) + "\n"


# --- the official evaluator -----------------------------------------------------


def _eval_module() -> Any:
    """Import the official ``conll18_ud_eval`` from the cache (fetched once, sha256-pinned)."""
    dest = cache_dir() / _CACHE_SUBDIR / "conll18_ud_eval.py"
    if not dest.exists():
        download_file(_EVAL_URL, dest, sha256=_EVAL_SHA256)
    spec = importlib.util.spec_from_file_location("conll18_ud_eval", dest)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate_on_ud(
    treebank: str = "perseus",
    split: str = "test",
    *,
    source: Path | str | None = None,
    parse: bool | None = None,
    progress: Callable[[int, int], None] | None = None,
    batch_size: int | None = None,
) -> dict[str, Any]:
    """Score the active pipeline on a UD Ancient Greek fold with the official evaluator.

    Runs over the fold's gold tokens (gold-tokenization protocol), emits CoNLL-U, and
    scores it against the gold file with ``conll18_ud_eval``. Activate the backends you
    want measured first (`use_treebank`, `use_tagger`, `use_lemmatizer`,
    `use_neural_lemmatizer`, `use_parser`). ``parse`` defaults to whether the parser
    is active; with ``parse=False`` UAS/LAS are returned as ``None``. ``progress``
    (optional) is called as ``progress(done, total)`` per analyzed sentence.
    ``batch_size`` (optional) batches the neural pipeline's encoder passes (see
    `pipeline_conllu`) — a throughput convenience; the recorded protocol behind every
    published number is the sequential default.

    Returns ``{"upos", "lemma", "uas", "las", "n_words", "n_sentences", "treebank",
    "split", "parsed"}`` — accuracies in [0, 1]. **Read the module docstring's leakage
    caveat before quoting the Perseus fold for an AGDT-trained model.**"""
    gold_path = Path(source) if source is not None else ud_path(treebank, split)
    sentences = load_conllu(gold_path)
    if parse is None:
        from . import joint, syntax

        parse = joint.active() is not None or syntax.active() is not None
    system = pipeline_conllu(sentences, parse=parse, progress=progress, batch_size=batch_size)

    ev = _eval_module()
    with tempfile.TemporaryDirectory() as td:
        sys_path = Path(td) / "system.conllu"
        sys_path.write_text(system, encoding="utf-8")
        with open(gold_path, encoding="utf-8") as gf:
            gold_ud = ev.load_conllu(gf)
        with open(sys_path, encoding="utf-8") as sf:
            system_ud = ev.load_conllu(sf)
    scores = ev.evaluate(gold_ud, system_ud)
    return {
        "treebank": treebank,
        "split": split,
        "parsed": parse,
        "upos": scores["UPOS"].f1,
        "xpos": scores["XPOS"].f1,
        "ufeats": scores["UFeats"].f1,
        "lemma": scores["Lemmas"].f1,
        "uas": scores["UAS"].f1 if parse else None,
        "las": scores["LAS"].f1 if parse else None,
        "clas": scores["CLAS"].f1 if parse else None,
        "n_words": len([t for s in sentences for t in s.tokens]),
        "n_sentences": len(sentences),
    }


# --- bootstrap confidence intervals over the fold's sentences --------------------

_METRIC_KEY = {
    "upos": "UPOS",
    "xpos": "XPOS",
    "ufeats": "UFeats",
    "lemma": "Lemmas",
    "uas": "UAS",
    "las": "LAS",
    "clas": "CLAS",
}


def _split_conllu_sentences(text: str) -> list[str]:
    """Split a CoNLL-U string into sentence blocks, each terminated by a blank line."""
    blocks: list[str] = []
    cur: list[str] = []
    for line in text.splitlines():
        if line.strip():
            cur.append(line)
        elif cur:
            blocks.append("\n".join(cur) + "\n\n")
            cur = []
    if cur:
        blocks.append("\n".join(cur) + "\n\n")
    return blocks


def _score_conllu_text(
    ev: Any, gold_text: str, system_text: str, metrics: Sequence[str]
) -> dict[str, float]:
    """Score one aligned (gold, system) CoNLL-U pair with the official evaluator."""
    import io

    gold_ud = ev.load_conllu(io.StringIO(gold_text))
    system_ud = ev.load_conllu(io.StringIO(system_text))
    scores = ev.evaluate(gold_ud, system_ud)
    return {m: float(scores[_METRIC_KEY[m]].f1) for m in metrics}


def _bootstrap_conllu(
    gold_text: str,
    system_text: str,
    score: Callable[[str, str], dict[str, float]],
    *,
    n_resamples: int = 999,
    level: float = 0.95,
    seed: int = 0,
) -> dict[str, BootstrapCI]:
    """Bootstrap CIs over the sentences of an aligned gold/system CoNLL-U pair.

    ``score(gold, system)`` scores one CoNLL-U pair to ``{metric: value}``. The two texts must
    be sentence-aligned (guaranteed by the gold-tokenization protocol). The resampling unit is
    the **sentence**; ``score`` is injected so the resampling is testable without the evaluator.
    """
    from ..analysis.stats import bootstrap_dict_seq

    gold_blocks = _split_conllu_sentences(gold_text)
    sys_blocks = _split_conllu_sentences(system_text)
    if len(gold_blocks) != len(sys_blocks):
        raise ValueError(
            f"gold/system sentence-count mismatch: {len(gold_blocks)} vs {len(sys_blocks)}"
        )
    pairs = list(zip(gold_blocks, sys_blocks, strict=True))

    def stat(sample: Sequence[tuple[str, str]]) -> dict[str, float]:
        return score("".join(g for g, _ in sample), "".join(s for _, s in sample))

    return bootstrap_dict_seq(pairs, stat, n_resamples=n_resamples, level=level, seed=seed)


def bootstrap_ud(
    treebank: str = "perseus",
    split: str = "test",
    *,
    metrics: Sequence[str] = ("upos", "xpos", "ufeats", "lemma", "uas", "las"),
    n_resamples: int = 999,
    level: float = 0.95,
    seed: int = 0,
    source: Path | str | None = None,
    parse: bool | None = None,
) -> dict[str, BootstrapCI]:
    """Percentile bootstrap CIs for :func:`evaluate_on_ud`'s metrics, over the fold's sentences.

    The active pipeline runs **once** over the fold; each of ``n_resamples`` draws re-scores a
    sentence resample (with replacement) with the official evaluator. Sentences are the
    resampling unit — tokens within a sentence are not independent. Activate the same backends
    you would for :func:`evaluate_on_ud`; with no parser active, ``uas``/``las`` are dropped.
    The band is sampling variability *given this fold* — read the module docstring's leakage
    caveat before quoting the Perseus fold for an AGDT-trained model.
    """
    gold_path = Path(source) if source is not None else ud_path(treebank, split)
    sentences = load_conllu(gold_path)
    if parse is None:
        from . import joint, syntax

        parse = joint.active() is not None or syntax.active() is not None
    system_text = pipeline_conllu(sentences, parse=parse)
    gold_text = gold_path.read_text(encoding="utf-8")
    wanted = [m for m in metrics if parse or m not in ("uas", "las")]
    ev = _eval_module()
    return _bootstrap_conllu(
        gold_text,
        system_text,
        lambda g, s: _score_conllu_text(ev, g, s, wanted),
        n_resamples=n_resamples,
        level=level,
        seed=seed,
    )


def evaluate_by_genre(
    treebank: str = "perseus",
    split: str = "test",
    *,
    metrics: Sequence[str] = ("upos", "lemma", "uas", "las"),
    bootstrap: bool = True,
    n_resamples: int = 999,
    level: float = 0.95,
    seed: int = 0,
    source: Path | str | None = None,
    parse: bool | None = None,
    min_sentences: int = 20,
    progress: Callable[[int, int], None] | None = None,
    batch_size: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Score the active pipeline on a UD fold, sliced by literary genre.

    Each sentence is bucketed by its ``sent_id`` author (a TLG id, mapped through
    ``_AUTHOR_GENRE`` to epic / tragedy / comedy / prose / other). The pipeline runs **once**
    over the whole fold; each genre is then scored with the official evaluator (and, when
    ``bootstrap``, given a percentile CI). Returns ``{genre: {"n_sentences", "n_words",
    "authors", "thin" (True under ``min_sentences``), <metric>: value or BootstrapCI}}`` plus an
    ``"_unmapped"`` list of author ids not in the table (the built-in discovery step: run this
    before pinning any numbers, and extend ``_AUTHOR_GENRE`` from it).

    This is meaningful only for the leakage-clean neural model on Perseus: the offline baseline
    has seen the Perseus test sentences (see the module leakage caveat), so do not publish genre
    slices for it. ``uas``/``las`` are dropped when no parser is active. ``progress`` and
    ``batch_size`` thread through to `pipeline_conllu`; the recorded protocol stays the
    sequential default."""
    gold_path = Path(source) if source is not None else ud_path(treebank, split)
    sentences = load_conllu(gold_path)
    if parse is None:
        from . import joint, syntax

        parse = joint.active() is not None or syntax.active() is not None
    wanted = [m for m in metrics if parse or m not in ("uas", "las")]
    system_text = pipeline_conllu(sentences, parse=parse, progress=progress, batch_size=batch_size)
    gold_blocks = _split_conllu_sentences(gold_path.read_text(encoding="utf-8"))
    sys_blocks = _split_conllu_sentences(system_text)
    if not (len(gold_blocks) == len(sys_blocks) == len(sentences)):
        raise ValueError(
            f"gold/system/sentence count mismatch: {len(gold_blocks)}/{len(sys_blocks)}/"
            f"{len(sentences)}"
        )

    buckets: dict[str, list[tuple[str, str]]] = {}
    authors: dict[str, set[str]] = {}
    unmapped: set[str] = set()
    for sent, g, s in zip(sentences, gold_blocks, sys_blocks):
        author, genre = _sent_genre(sent.sent_id)
        buckets.setdefault(genre, []).append((g, s))
        authors.setdefault(genre, set()).add(author)
        if genre == "other":
            unmapped.add(author)

    ev = _eval_module()
    out: dict[str, dict[str, Any]] = {}
    for genre, pairs in buckets.items():
        gold_text = "".join(g for g, _ in pairs)
        sys_text = "".join(s for _, s in pairs)
        n_words = sum(
            1
            for line in gold_text.splitlines()
            if "\t" in line
            and (row_id := line.split("\t", 1)[0])
            and _WORD_ID_RE.fullmatch(row_id)
            and int(row_id) > 0
        )
        entry: dict[str, Any] = {
            "n_sentences": len(pairs),
            "n_words": n_words,
            "authors": sorted(authors[genre]),
            "thin": len(pairs) < min_sentences,
        }
        if bootstrap and len(pairs) >= 2:
            entry.update(
                _bootstrap_conllu(
                    gold_text, sys_text,
                    lambda gg, ss: _score_conllu_text(ev, gg, ss, wanted),
                    n_resamples=n_resamples, level=level, seed=seed,
                )
            )
        else:
            # A 1-sentence bucket cannot be resampled (bootstrap needs >= 2 items); fall back
            # to the point scores rather than aborting every healthy bucket with it — the
            # bucket is already flagged thin above.
            entry.update(_score_conllu_text(ev, gold_text, sys_text, wanted))
        out[genre] = entry
    out["_unmapped"] = {"authors": sorted(unmapped)}  # type: ignore[dict-item]
    return out


# --- the leakage-exclusion manifest ----------------------------------------------


def _agdt_sentence_forms(path: Path) -> dict[str, tuple[str, ...]]:
    """sentence id → NFC form sequence for one AGDT ``.tb.xml`` file."""
    out: dict[str, tuple[str, ...]] = {}
    cur: list[str] = []
    sid = ""
    for _event, elem in ET.iterparse(str(path), events=("start", "end")):
        tag = elem.tag.rsplit("}", 1)[-1]
        if _event == "start" and tag == "sentence":
            sid = elem.get("id") or ""
            cur = []
        elif _event == "end":
            if tag == "word":
                form = elem.get("form")
                if form:
                    cur.append(unicodedata.normalize("NFC", form))
            elif tag == "sentence":
                if sid:
                    out[sid] = tuple(cur)
                elem.clear()
    return out


def agdt_ud_overlap(
    *,
    splits: tuple[str, ...] = ("dev", "test"),
    source: Path | str | None = None,
    agdt_source: Path | str | None = None,
    verify: bool = True,
    write: bool = True,
) -> dict[str, Any]:
    """Build the AGDT ↔ UD-Perseus leakage-exclusion manifest.

    UD Perseus sentence ids are ``<agdt-file>@<sentence-id>`` — direct references into the
    AGDT source pyaegean trains on. This collects every AGDT sentence appearing in the
    given UD ``splits`` (default: dev + test, the folds that must stay unseen), verifies
    the reference by comparing NFC form sequences against the actual AGDT files, caches
    the manifest as JSON, and returns it. **Every Stage A+ training split must exclude
    these sentences** — see ``docs/benchmarks.md``.

    ``source`` overrides the UD fold path(s) and ``agdt_source`` the AGDT directory (used
    by offline tests); with defaults, both fetch to the cache on first use."""
    _repo, commit = _UD_REPO["perseus"]
    files: dict[str, set[str]] = {}
    ud_forms: dict[tuple[str, str], tuple[str, ...]] = {}
    for split in splits:
        path = Path(source) if source is not None else ud_path("perseus", split)
        for sent in load_conllu(path):
            if "@" not in sent.sent_id:
                continue
            fname, _, sid = sent.sent_id.rpartition("@")
            files.setdefault(fname, set()).add(sid)
            ud_forms[(fname, sid)] = tuple(
                unicodedata.normalize("NFC", t.form) for t in sent.tokens
            )

    checked = identical = 0
    if verify:
        from .treebank import agdt_dir

        base = Path(agdt_source) if agdt_source is not None else agdt_dir(download=True)
        for fname, ids in files.items():
            fp = base / fname
            if not fp.exists():
                continue
            gold = _agdt_sentence_forms(fp)
            for sid in ids:
                if sid in gold:
                    checked += 1
                    identical += int(gold[sid] == ud_forms[(fname, sid)])

    from .. import __version__  # lazy: aegean/__init__ imports this module

    manifest: dict[str, Any] = {
        "purpose": "AGDT sentences that appear in UD-Perseus folds; exclude from training",
        "ud_treebank": "UD_Ancient_Greek-Perseus",
        "ud_commit": commit,
        "splits": list(splits),
        "pyaegean_version": __version__,
        "files": {fname: sorted(ids, key=lambda s: (len(s), s)) for fname, ids in sorted(files.items())},
        "n_sentences": sum(len(ids) for ids in files.values()),
        "verified": {"checked": checked, "form_identical": identical} if verify else None,
    }
    if write:
        dest = cache_dir() / _CACHE_SUBDIR / _EXCLUSION_NAME
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest
