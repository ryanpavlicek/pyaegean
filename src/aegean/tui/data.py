"""The library adapter: the one seam between the TUI and the pyaegean library.

Every screen calls these functions and nothing else from the library. That keeps
the screens pure UI (unit-testable with a mocked adapter) and keeps all library
knowledge, error translation, and result shaping in one plain-Python module that
plain pytest can drive without Textual.

Design rules this file obeys:

- **No Textual import.** Nothing here knows about widgets or screens; that is
  what makes it a plain unit-test target.
- **The UI never sees a raw exception.** Corpus loading re-raises the library's
  ``CorpusNotFound`` as :class:`TuiError` (a clean message a screen can show).
  The Greek helpers catch `ScansionError` / `ValueError` into an ``.ok`` /
  ``.error`` / ``.rows`` :class:`GreekResult` so a bad line renders as a message,
  not a traceback.
- **Numbers come from the shared mappings.** ``balance_rows`` delegates to
  :func:`aegean._view.balance_rows` and ``greek_pipeline`` to
  :func:`aegean._view.pipeline_rows`, the same functions the CLI uses, so the two
  surfaces cannot drift.

Undeciphered-script honesty: Linear A (both the bundled ``lineara`` corpus and
the SigLA dataset) and Cypro-Minoan are undeciphered, so any structural analysis
the adapter returns for them is exploratory, not a reading. :func:`is_undeciphered`
flags the corpora a screen must caption that way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # type-only imports keep the module import-light
    from pathlib import Path

    from ..core.corpus import Corpus
    from ..core.model import Document

__all__ = [
    "TuiError",
    "CorpusEntry",
    "DocRow",
    "TokenCell",
    "DocLine",
    "DocDetail",
    "BalanceRow",
    "GreekResult",
    "DatasetRow",
    "CORPUS_IDS",
    "UNDECIPHERED",
    "is_undeciphered",
    "list_corpora",
    "load_corpus",
    "document_rows",
    "document_detail",
    "search_corpus",
    "balance_rows",
    "greek_pipeline",
    "greek_scan",
    "greek_syllables",
    "greek_ipa",
    "doctor_report",
    "fetch_dataset",
]


class TuiError(Exception):
    """A clean, user-facing error a screen can display in place of a traceback."""


# The eight registered corpora, in a stable presentation order (bundled first,
# then the fetch-on-demand ones). Kept as a constant so a screen can render the
# overview without loading anything; validated against the live loader registry
# by the adapter tests.
CORPUS_IDS: tuple[str, ...] = (
    "lineara",
    "linearb",
    "cypriot",
    "cyprominoan",
    "greek",
    "nt",
    "damos",
    "sigla",
)

# The undeciphered corpora: any structural analysis of these is exploratory,
# never a reading. The same honesty rule the CLI and docstrings carry, enforced
# here at the adapter so every screen inherits it. Both ``lineara`` and ``sigla``
# are Linear A (SigLA is the Salgarella & Castellan Linear A dataset), which is
# undeciphered; ``cyprominoan`` is the undeciphered Cypro-Minoan sign corpus.
UNDECIPHERED: frozenset[str] = frozenset({"lineara", "sigla", "cyprominoan"})

# One-line descriptions for the corpus overview (offline, no load needed).
_CORPUS_BLURB: dict[str, str] = {
    "lineara": "Linear A inscriptions (undeciphered)",
    "linearb": "Linear B sample tablets (Mycenaean Greek)",
    "cypriot": "Cypriot syllabary texts (Greek)",
    "cyprominoan": "Cypro-Minoan signs (undeciphered)",
    "greek": "alphabetic Greek sample texts",
    "nt": "Greek New Testament (Nestle 1904)",
    "damos": "DAMOS full Linear B corpus",
    "sigla": "SigLA Linear A corpus",
}

# corpus id -> the release-asset name that must be in the store before the
# corpus loads (the same signal `aegean data list` reports). Corpora not listed
# here are bundled in the wheel and always available.
_CORPUS_ASSET: dict[str, str] = {
    "nt": "nt-corpus",
    "damos": "damos-corpus",
    "sigla": "sigla-corpus",
}


def is_undeciphered(corpus_id: str) -> bool:
    """Whether ``corpus_id`` is an undeciphered corpus (Linear A, as both
    ``lineara`` and the SigLA dataset, or Cypro-Minoan), so a screen must caption
    its analysis as exploratory, not a reading."""
    return corpus_id in UNDECIPHERED


@dataclass(frozen=True, slots=True)
class CorpusEntry:
    """One corpus in the overview: its id, a one-line blurb, whether its data is
    on disk (bundled corpora are always ``True``; fetch-on-demand corpora reflect
    the store), and whether it is an undeciphered script."""

    id: str
    blurb: str
    downloaded: bool
    bundled: bool
    undeciphered: bool


@dataclass(frozen=True, slots=True)
class DocRow:
    """One document in the corpus's document table."""

    id: str
    site: str
    period: str
    n_words: int
    n_tokens: int
    structure: str


@dataclass(frozen=True, slots=True)
class TokenCell:
    """One token in the document detail, with the apparatus a screen styles on:
    its text, kind, editorial ``status`` (certain / unclear / restored / lost),
    any alternate readings, and per-token annotations (the NT's lemma / morph /
    Strong's / gloss)."""

    text: str
    kind: str
    status: str
    alt: tuple[str, ...]
    annotations: dict[str, str]


@dataclass(frozen=True, slots=True)
class DocLine:
    """One physical line of a document: its 1-based number and its tokens."""

    number: int
    tokens: tuple[TokenCell, ...]


@dataclass(frozen=True, slots=True)
class DocDetail:
    """The full detail of one document: identity, metadata, lines of tokens, and
    the undeciphered flag so the detail pane can caption exploratory analysis."""

    id: str
    site: str
    period: str
    support: str
    scribe: str
    n_tokens: int
    n_words: int
    structure: str
    lines: tuple[DocLine, ...]
    undeciphered: bool


@dataclass(frozen=True, slots=True)
class BalanceRow:
    """One reconciled total line (the shared ``_view.balance_rows`` shape as a
    dataclass): the total marker, the stated total, the computed sum, their
    signed difference, the item count, and whether they balance."""

    doc: str
    marker: str
    stated: float
    computed: float
    difference: float
    items: int
    balances: bool


@dataclass(frozen=True, slots=True)
class DatasetRow:
    """One fetchable dataset in the data-store view."""

    name: str
    downloaded: bool
    bytes: int | None
    note: str
    license: str


@dataclass(frozen=True, slots=True)
class GreekResult:
    """The result of a Greek helper: ``ok`` with ``rows`` (and optional
    ``summary``), or not-ok with an ``error`` message. The UI checks ``ok`` and
    never sees an exception."""

    ok: bool
    rows: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    summary: str = ""


# ── corpora ──────────────────────────────────────────────────────────────────
def _store_root() -> "Path | None":
    """The data-store directory, or ``None`` if it cannot be reached."""
    from ..data import cache_dir

    try:
        return cache_dir()
    except OSError:
        return None


def list_corpora() -> list[CorpusEntry]:
    """The eight corpora for the overview, each with its download state.

    Bundled corpora (Linear A/B, Cypriot, Cypro-Minoan, Greek) are always
    downloaded. The fetch-on-demand corpora (NT, DAMOS, SigLA) are reported
    downloaded only when their release asset is in the local store, so a screen
    can mark which need a fetch. Offline: nothing is loaded or downloaded."""
    root = _store_root()
    entries: list[CorpusEntry] = []
    for cid in CORPUS_IDS:
        asset = _CORPUS_ASSET.get(cid)
        bundled = asset is None
        if asset is None:
            downloaded = True
        elif root is None:
            downloaded = False
        else:
            downloaded = (root / asset).exists()
        entries.append(
            CorpusEntry(
                id=cid,
                blurb=_CORPUS_BLURB.get(cid, cid),
                downloaded=downloaded,
                bundled=bundled,
                undeciphered=cid in UNDECIPHERED,
            )
        )
    return entries


def load_corpus(corpus_id: str) -> "Corpus":
    """Load a corpus by id, re-raising the library's ``CorpusNotFound`` as a
    clean :class:`TuiError`.

    Delegates to :func:`aegean.load` so bundled corpora load instantly and the
    fetch-on-demand ones download on first use (a network call the caller runs on
    a worker). A bad id, or a fetch failure, becomes one readable message rather
    than a traceback the UI would have to render."""
    import aegean
    from ..core.resolve import CorpusNotFound

    try:
        return aegean.load(corpus_id)
    except (CorpusNotFound, KeyError):
        raise TuiError(f"no corpus {corpus_id!r}") from None
    except Exception as exc:  # network / parse failure on a fetch-on-demand corpus
        raise TuiError(f"could not load {corpus_id!r}: {exc}") from None


def document_rows(corpus: "Corpus") -> list[DocRow]:
    """One :class:`DocRow` per document, in corpus order, with the heuristic
    structure category (accounting / libation / list / text / other)."""
    from ..analysis import classify_structure

    return [
        DocRow(
            id=d.id,
            site=d.meta.site,
            period=d.meta.period,
            n_words=len(d.words),
            n_tokens=len(d.tokens),
            structure=classify_structure(d),
        )
        for d in corpus
    ]


def _resolve_document(corpus: "Corpus", doc_id: str) -> "Document":
    from ..core.resolve import resolve_document

    doc, _near = resolve_document(corpus, doc_id)
    if doc is None:
        raise TuiError(f"no document {doc_id!r} in this corpus")
    return doc


def document_detail(corpus: "Corpus", doc_id: str) -> DocDetail:
    """The full apparatus-aware detail of one document (forgiving id lookup).

    Every token carries its editorial status, alternate readings, and
    annotations so the detail pane can style unclear / restored / lost text and
    surface the NT's lemma / morph / gloss. The ``undeciphered`` flag is set for
    Linear A / Cypro-Minoan so the pane can caption its structure as
    exploratory."""
    doc = _resolve_document(corpus, doc_id)
    from ..analysis import classify_structure

    lines = tuple(
        DocLine(
            number=i + 1,
            tokens=tuple(
                TokenCell(
                    text=t.text,
                    kind=t.kind.value,
                    status=t.status.value,
                    alt=tuple(t.alt),
                    annotations=dict(t.annotations),
                )
                for t in toks
            ),
        )
        for i, toks in enumerate(doc.line_tokens)
    )
    return DocDetail(
        id=doc.id,
        site=doc.meta.site,
        period=doc.meta.period,
        support=doc.meta.support,
        scribe=doc.meta.scribe,
        n_tokens=len(doc.tokens),
        n_words=len(doc.words),
        structure=classify_structure(doc),
        lines=lines,
        undeciphered=corpus.script_id in UNDECIPHERED or doc.script_id in UNDECIPHERED,
    )


def search_corpus(corpus: "Corpus", pattern: str) -> list[tuple[str, int]]:
    """Words matching a wildcard sign pattern (``KU-*-RO``, ``**-RE``), each with
    its corpus frequency, most frequent first.

    Wraps :func:`aegean.analysis.word_matches_sign_pattern` over the corpus word
    frequencies. An empty or single-sign-only pattern matches nothing (the
    library rule), so the caller gets an empty list, never an error."""
    from ..analysis.patterns import word_matches_sign_pattern

    return [
        (word, count)
        for word, count in corpus.word_frequencies()
        if word_matches_sign_pattern(word, pattern)
    ]


def balance_rows(document: "Document") -> list[BalanceRow]:
    """The document's reconciled total lines as :class:`BalanceRow` s.

    Delegates to the shared :func:`aegean._view.balance_rows` (the exact rows the
    ``aegean balance`` command emits) and wraps each in a dataclass, so the TUI
    and the CLI show identical accounting numbers by construction. Empty when the
    document states no total."""
    from .._view import balance_rows as _rows

    return [
        BalanceRow(
            doc=r["doc"],
            marker=r["marker"],
            stated=r["stated"],
            computed=r["computed"],
            difference=r["difference"],
            items=r["items"],
            balances=r["balances"],
        )
        for r in _rows(document)
    ]


# ── Greek workbench ───────────────────────────────────────────────────────────
def greek_pipeline(text: str) -> GreekResult:
    """Analyze Greek ``text`` and return per-token rows (never raises to the UI).

    Rows come from the shared :func:`aegean._view.pipeline_rows`, the same
    mapping the ``aegean greek pipeline`` command uses, so a token row is
    identical across the two surfaces. Empty input yields ``ok`` with no rows."""
    from .._view import pipeline_rows

    text = text.strip()
    if not text:
        return GreekResult(ok=True, rows=[])
    try:
        rows = pipeline_rows(text)
    except Exception as exc:  # pragma: no cover - the baseline pipeline is total
        return GreekResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    return GreekResult(ok=True, rows=rows, summary=f"{len(rows)} token(s)")


def greek_scan(text: str, meter: str = "hexameter") -> GreekResult:
    """Scan a Greek line against ``meter``, catching a bad meter or an unscannable
    line into ``.error`` instead of raising.

    On success ``rows`` holds one row per foot (``name`` and ``pattern`` glyphs)
    and ``summary`` is the full glyph pattern, the caesura, and whether the
    scansion was ambiguous."""
    from ..greek import scan_line
    from ..greek.meter import ScansionError

    text = text.strip()
    if not text:
        return GreekResult(ok=True, rows=[])
    try:
        result = scan_line(text, meter)
    except ScansionError as exc:
        return GreekResult(ok=False, error=str(exc))
    except ValueError as exc:  # pragma: no cover - ScansionError covers the known cases
        return GreekResult(ok=False, error=str(exc))
    rows = [{"foot": f.name, "pattern": str(f)} for f in result.feet]
    summary = result.pattern
    if result.caesura:
        summary += f"  ·  {result.caesura} caesura"
    if result.ambiguous:
        summary += "  ·  ambiguous"
    return GreekResult(ok=True, rows=rows, summary=summary)


def greek_syllables(word: str) -> GreekResult:
    """Syllabify a Greek word, returning one row per syllable and the hyphenated
    split as ``summary``. Never raises: non-letters pass through."""
    from ..greek import syllabify

    word = word.strip()
    if not word:
        return GreekResult(ok=True, rows=[])
    try:
        syllables = syllabify(word)
    except Exception as exc:  # pragma: no cover - syllabify is total
        return GreekResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    rows = [{"n": i + 1, "syllable": s} for i, s in enumerate(syllables)]
    return GreekResult(ok=True, rows=rows, summary="-".join(syllables))


def greek_ipa(text: str, period: str = "attic") -> GreekResult:
    """Transcribe Greek ``text`` to reconstructed IPA (``attic`` or ``koine``),
    catching a bad period into ``.error``. ``summary`` is the transcription; each
    row pairs an input word with its IPA."""
    from ..greek import to_ipa

    text = text.strip()
    if not text:
        return GreekResult(ok=True, rows=[])
    try:
        ipa = to_ipa(text, period=period)  # type: ignore[arg-type]
    except ValueError as exc:
        return GreekResult(ok=False, error=str(exc))
    words = text.split()
    ipa_words = ipa.split()
    rows = [
        {"word": w, "ipa": ipa_words[i] if i < len(ipa_words) else ""}
        for i, w in enumerate(words)
    ]
    return GreekResult(ok=True, rows=rows, summary=ipa)


# ── data store ─────────────────────────────────────────────────────────────────
def doctor_report() -> dict[str, Any]:
    """The full offline environment report, verbatim from
    :func:`aegean._doctor.build_report` (versions, extras, data store,
    models, analysis cache). No network is touched, and no CLI dependency
    is imported: the report builds in a ``[tui]``-only environment."""
    from .._doctor import build_report

    return build_report()


def dataset_rows() -> list[DatasetRow]:
    """Every fetchable dataset and whether it is downloaded (with its on-disk
    size), for the data-store table. The same per-dataset state ``aegean data
    list`` reports; offline."""
    from ..data import _REMOTE, downloaded_bytes, is_downloaded

    root = _store_root()
    rows: list[DatasetRow] = []
    for name, spec in sorted(_REMOTE.items()):
        # is_downloaded/downloaded_bytes (not a bare root/name probe) so a dataset
        # fetched under a different filename via index/extract is seen, matching the CLI.
        downloaded = is_downloaded(spec, root) if root is not None else False
        size = downloaded_bytes(spec, root) if (downloaded and root is not None) else None
        rows.append(
            DatasetRow(
                name=name,
                downloaded=downloaded,
                bytes=size,
                note=spec.note,
                license=spec.license,
            )
        )
    return rows


class FetchCanceled(TuiError):
    """The fetch's ``abort`` hook fired (the worker was cancelled): the partial
    download is kept on disk, so a later fetch resumes it."""


def fetch_dataset(
    name: str,
    on_progress: Callable[[str], None] | None = None,
    abort: Callable[[], bool] | None = None,
) -> "Path":
    """Download a dataset into the local store, reporting progress lines through
    ``on_progress`` (a screen runs this on a Textual worker so the UI stays live).

    Wraps :func:`aegean.data.fetch`, which is sha256-verified, resumable, and a
    no-op when the dataset is already stored. An unknown name or a network
    failure becomes a :class:`TuiError` the screen can show. ``on_progress`` is
    invoked with a short status before and after the transfer (the underlying
    fetch reports no byte-level progress). ``abort`` is polled during the
    transfer; when it returns true the download stops with :class:`FetchCanceled`
    (how a cancelled worker actually interrupts the transfer, e.g. on quit)."""
    from ..data import _REMOTE, DataNotAvailableError, FetchAborted
    from ..data import fetch as _fetch

    if name not in _REMOTE:
        raise TuiError(f"unknown dataset {name!r}")
    if on_progress is not None:
        on_progress(f"fetching {name}…")
    try:
        path = _fetch(name, abort=abort)
    except FetchAborted:
        raise FetchCanceled(f"fetch of {name} canceled (partial download kept)") from None
    except DataNotAvailableError as exc:
        raise TuiError(str(exc)) from None
    except Exception as exc:  # network / disk failure
        raise TuiError(f"could not fetch {name!r}: {exc}") from None
    if on_progress is not None:
        on_progress(f"stored {name}")
    return path
