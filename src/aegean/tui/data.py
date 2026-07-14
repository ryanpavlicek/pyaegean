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
    "AnalysisOption",
    "AnalysisResult",
    "line_analyses",
    "run_line_analysis",
    "greek_neural_available",
    "translation_available",
    "translate_line",
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
    "confidence_available",
    "greek_pipeline",
    "greek_scan",
    "greek_syllables",
    "greek_ipa",
    "doctor_report",
    "fetch_dataset",
    "read_corpus_spec",
    "WorkRow",
    "catalog_rows",
    "fetched_work_ids",
    "fetched_work_entries",
    "fetch_work",
    "fetch_author_works",
    "remove_work",
    "config_path",
    "load_tui_config",
    "save_tui_config",
]


class TuiError(Exception):
    """A clean, user-facing error a screen can display in place of a traceback."""


# The browsable corpora (every registered corpus except ddbdp, whose materialisation
# is too heavy for the TUI browser), in a stable presentation order (bundled first,
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
    "isicily",
    "iip",
    "iospe",
    "igcyr",
    "edh",
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
    "isicily": "I.Sicily Greek inscriptions (Sicily)",
    "iip": "IIP Greek inscriptions (Israel/Palestine)",
    "iospe": "IOSPE Greek inscriptions (Black Sea)",
    "igcyr": "IGCyr/GVCyr Greek inscriptions (Cyrenaica)",
    "edh": "EDH Greek inscriptions (Heidelberg)",
}

# corpus id -> the release-asset name that must be in the store before the
# corpus loads (the same signal `aegean data list` reports). Corpora not listed
# here are bundled in the wheel and always available. The Greek-epigraphy corpora
# (I.Sicily, IIP, IOSPE, IGCyr, EDH) are fetch-on-demand release assets, not bundled. ddbdp is
# deliberately absent from this map: it is not listed in the TUI corpus browser (see CORPUS_IDS),
# so the browser never needs its download status.
_CORPUS_ASSET: dict[str, str] = {
    "nt": "nt-corpus",
    "damos": "damos-corpus",
    "sigla": "sigla-corpus",
    "isicily": "isicily-corpus",
    "iip": "iip-corpus",
    "iospe": "iospe-corpus",
    "igcyr": "igcyr-corpus",
    "edh": "edh-corpus",
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
    alignment: dict[str, Any] | None = None
    form_state: dict[str, Any] | None = None


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
    source_text: str | None = None


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
    """The corpora for the overview, each with its download state.

    Bundled corpora (Linear A/B, Cypriot, Cypro-Minoan, Greek) are always
    downloaded. The fetch-on-demand corpora (NT, DAMOS, SigLA, and the Greek-
    epigraphy corpora I.Sicily/IIP/IOSPE/IGCyr/EDH) are reported downloaded only
    when their release asset is in the local store, so a screen can mark which
    need a fetch. Offline: nothing is loaded or downloaded."""
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
                    alignment=(
                        {
                            "document_id": t.alignment.document_id,
                            "sentence_id": t.alignment.sentence_id,
                            "source_token_id": t.alignment.source_token_id,
                            "original_text": t.alignment.original_text,
                            "start_char": t.alignment.start_char,
                            "end_char": t.alignment.end_char,
                            "whitespace_before": t.alignment.whitespace_before,
                            "normalized_text": t.alignment.normalized_text,
                            "normalization_ops": t.alignment.normalization_ops,
                        }
                        if t.alignment is not None
                        else None
                    ),
                    form_state=(
                        t.form_state.to_dict() if t.form_state is not None else None
                    ),
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
        source_text=doc.source_text,
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
def confidence_available() -> bool:
    """Whether the pipeline can surface calibrated confidence right now.

    True only when the neural pipeline is active AND a calibration is loaded: confidence
    is model-only, and the project never surfaces a raw (uncalibrated) softmax. A TUI
    surface requests confidence only when this holds, so a pipeline call never raises for
    a missing calibration — the confidence column appears when the numbers are free."""
    from ..greek import joint
    from ..greek.calibrate import active as _calibration_active

    return joint.active() is not None and _calibration_active() is not None


def greek_pipeline(text: str, *, with_confidence: bool = False) -> GreekResult:
    """Analyze Greek ``text`` and return per-token rows (never raises to the UI).

    Rows come from the shared :func:`aegean._view.pipeline_rows`, the same
    mapping the ``aegean greek pipeline`` command uses, so a token row is
    identical across the two surfaces. Empty input yields ``ok`` with no rows.

    ``with_confidence=True`` threads through; when the active backends produce
    calibrated numbers (see `confidence_available`) each row also carries
    ``upos_confidence`` / ``lemma_confidence``, otherwise those keys are absent."""
    from .._view import pipeline_rows

    text = text.strip()
    if not text:
        return GreekResult(ok=True, rows=[])
    try:
        rows = pipeline_rows(text, with_confidence=with_confidence)
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


# ── in-reader line analysis ─────────────────────────────────────────────────────
# One line of a document, analysed on demand: Greek lines get the offline parser/
# tagger, the neural pipeline, IPA, and (BYOAI, optional) translation; syllabic
# lines get sign values, the Greek bridge + gloss (Linear B / Cypriot), or an
# honest exploratory transliteration (undeciphered Linear A / Cypro-Minoan).


@dataclass(frozen=True)
class AnalysisOption:
    """One analysis a reader line can be run through, with whether it is available.

    ``available`` is False when a prerequisite is missing (the ``[neural]`` extra,
    or a configured BYOAI provider for translation); ``detail`` says why, or gives a
    one-line hint (an honesty caveat for the undeciphered scripts)."""

    key: str
    label: str
    available: bool
    detail: str = ""


@dataclass(frozen=True)
class AnalysisResult:
    """The rendered output of one analysis. Either a table (``columns`` + ``rows``)
    or a prose ``text`` block (a translation), with an optional ``note`` (provenance
    or an exploratory caveat). Never raised: a failure sets ``ok=False`` + ``error``."""

    ok: bool
    title: str = ""
    columns: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()
    text: str = ""
    note: str = ""
    error: str = ""


# The scripts that read as Greek (alphabetic Greek, NT, and fetched Greek works all
# load with script_id "greek"). Syllabic scripts are handled by their own branches.
_GREEK_SCRIPTS: frozenset[str] = frozenset({"greek"})


def line_analyses(script_id: str) -> list[AnalysisOption]:
    """The analyses offered for a line of ``script_id``, each flagged available or not.

    Greek: offline parser/tagger, neural pipeline (needs ``[neural]`` + the model),
    IPA, and translation (only when a BYOAI provider is configured). Linear B / Cypriot:
    the Greek reading + gloss, and sign values. Linear A / Cypro-Minoan (undeciphered):
    signs and, for Linear A, an exploratory transliteration, both plainly caveated."""
    if script_id in _GREEK_SCRIPTS:
        neural_ok, neural_why = greek_neural_available()
        tr_ok, tr_why = translation_available()
        return [
            AnalysisOption("offline", "offline parser / tagger", True),
            AnalysisOption("neural", "neural pipeline", neural_ok, neural_why),
            AnalysisOption("ipa", "IPA (reconstructed)", True),
            AnalysisOption("translate", "translate (BYOAI, optional)", tr_ok, tr_why),
        ]
    if script_id in {"linearb", "cypriot"}:
        return [
            AnalysisOption("bridge", "Greek reading + gloss", True),
            AnalysisOption("signs", "signs (glyph + value)", True),
        ]
    if script_id in {"lineara", "sigla"}:
        caveat = "Linear A is undeciphered — exploratory, not a reading"
        return [
            AnalysisOption("exploratory", "transliteration (exploratory)", True, caveat),
            AnalysisOption("signs", "signs (glyph + value)", True, caveat),
        ]
    if script_id == "cyprominoan":
        return [
            AnalysisOption("signs", "signs (glyph only)", True, "Cypro-Minoan is undeciphered"),
        ]
    return [AnalysisOption("signs", "signs", True)]


def run_line_analysis(
    key: str, *, script_id: str, text: str, token_texts: tuple[str, ...]
) -> AnalysisResult:
    """Run analysis ``key`` on one line and return a renderable result. Never raises.

    ``text`` is the line as one string (Greek analyses use it); ``token_texts`` are the
    line's token surface forms (the syllabic analyses split each on ``-`` into signs)."""
    try:
        if key == "offline":
            return _greek_offline(text)
        if key == "neural":
            return _greek_neural(text)
        if key == "ipa":
            return _greek_ipa_result(text)
        if key == "translate":
            return translate_line(text)
        if key == "bridge":
            return _aegean_bridge(script_id, token_texts)
        if key == "exploratory":
            return _lineara_exploratory(token_texts)
        if key == "signs":
            return _aegean_signs(script_id, token_texts)
    except Exception as exc:  # pragma: no cover - each helper is already total
        return AnalysisResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    return AnalysisResult(ok=False, error=f"unknown analysis {key!r}")


# ── Greek line analyses ─────────────────────────────────────────────────────────
def _greek_offline(text: str) -> AnalysisResult:
    r = greek_pipeline(text, with_confidence=confidence_available())
    if not r.ok:
        return AnalysisResult(ok=False, error=r.error)
    from .._view import format_confidence

    # The evidence column shows the lemma's source class only when it is NOT a grounded
    # analysis (the CLI's src-column convention): blank = trustworthy, a name = verify it.
    def _base(row: dict[str, Any]) -> tuple[str, ...]:
        return (
            str(row["index"]), row["text"], row["upos"], row["lemma"],
            str(row.get("lemma_source", "")) if row.get("review_recommended", False) else "",
        )

    # A calibrated 'conf' column appears only when the rows carry a confidence (the same
    # condition as the workbench + the CLI), so the offline table is unchanged otherwise.
    has_conf = bool(r.rows) and "upos_confidence" in r.rows[0]
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    if has_conf:
        columns = ("#", "token", "POS", "lemma", "check", "conf")
        rows = tuple(
            _base(row) + (format_confidence(row["upos_confidence"], row["lemma_confidence"]),)
            for row in r.rows
        )
    else:
        columns = ("#", "token", "POS", "lemma", "check")
        rows = tuple(_base(row) for row in r.rows)
    return AnalysisResult(
        ok=True, title="offline parser / tagger", columns=columns, rows=rows,
    )


def greek_neural_available() -> tuple[bool, str]:
    """Whether the neural pipeline can run: the ``[neural]`` extra must be installed.
    The model is fetched on first run, so a missing model is not a blocker here (the
    detail says so); a missing extra is."""
    import importlib.util

    missing = [m for m in ("onnxruntime", "tokenizers", "numpy") if importlib.util.find_spec(m) is None]
    if missing:
        return False, "needs the [neural] extra (pip install 'pyaegean[neural]')"
    from ..data import _REMOTE, is_downloaded

    root = _store_root()
    fetched = (
        root is not None and "grc-joint" in _REMOTE and is_downloaded(_REMOTE["grc-joint"], root)
    )
    return True, "" if fetched else "downloads the model (~170 MB) on first run"


def _greek_neural(text: str) -> AnalysisResult:
    text = text.strip()
    if not text:
        return AnalysisResult(ok=True, title="neural pipeline")
    from ..greek import pipeline, use_neural_pipeline

    try:
        use_neural_pipeline()
    except Exception as exc:
        return AnalysisResult(ok=False, error=f"neural pipeline unavailable: {exc}")
    try:
        recs = pipeline(text, parse=True)
    except Exception as exc:
        return AnalysisResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    rows = tuple(
        (
            str(r.index), r.text, r.upos,
            # an unresolved/identity lemma is flagged with its evidence class so a model
            # guess never displays like a grounded analysis
            r.lemma if not r.review_recommended else f"{r.lemma} [{r.lemma_source.value}]",
            r.feats or "",
            f"{r.relation}→{r.head}" if r.relation and r.head is not None else "",
        )
        for r in recs
    )
    return AnalysisResult(
        ok=True, title="neural pipeline",
        columns=("#", "token", "POS", "lemma", "features", "dep"), rows=rows,
        note="grc-joint neural model",
    )


def _greek_ipa_result(text: str) -> AnalysisResult:
    r = greek_ipa(text)
    if not r.ok:
        return AnalysisResult(ok=False, error=r.error)
    rows = tuple((row["word"], row["ipa"]) for row in r.rows)
    return AnalysisResult(
        ok=True, title="IPA (reconstructed, Attic)",
        columns=("word", "IPA"), rows=rows, note=r.summary,
    )


def translation_available() -> tuple[bool, str]:
    """Whether translation can run: a BYOAI provider must have its API key set. Returns
    (available, hint). Translation is always optional — it requires an external LLM."""
    providers = _usable_providers()
    if providers:
        return True, "via " + ", ".join(providers)
    return False, (
        "set a provider API key (BYOAI, e.g. OPENAI_API_KEY) or configure the keyless "
        "local provider (PYAEGEAN_LOCAL_MODEL + a running Ollama) to enable"
    )


def _usable_providers() -> list[str]:
    """Provider names configured for use: an API key in the environment (the BYOAI
    signal), or, for the keyless ``local`` provider, its model named
    (``PYAEGEAN_LOCAL_MODEL`` — the endpoint URL has an Ollama default and the key is
    optional, so the model is the one signal that a local server is intended)."""
    import os

    from ..ai.client import _PROVIDERS

    out = []
    for name, cls in _PROVIDERS.items():
        if name == "local":
            if os.environ.get(cls.env_model):
                out.append(name)
        elif getattr(cls, "env_key", "") and os.environ.get(cls.env_key):
            out.append(name)
    return sorted(out)


def translate_line(text: str, *, script: str = "greek") -> AnalysisResult:
    """Translate one line via the configured BYOAI provider (exploratory, provenanced).

    Returns a text result with the provider/model in ``note``; a missing key or any
    provider error becomes a clean ``error`` (translation never crashes the reader)."""
    text = text.strip()
    if not text:
        return AnalysisResult(ok=True, title="translation")
    providers = _usable_providers()
    if not providers:
        return AnalysisResult(
            ok=False,
            error="no BYOAI provider configured — set an API key (e.g. OPENAI_API_KEY) "
                  "or PYAEGEAN_LOCAL_MODEL (the keyless local provider) to translate",
        )
    from ..ai import AIError, get_client
    from ..translate import translate as _translate

    try:
        # Route to the first CONFIGURED provider (sorted, so anthropic keeps priority when
        # keyed) rather than translate()'s anthropic default, which would fail for a user
        # whose only configured provider is another hosted one or the keyless local server.
        client = get_client(providers[0])
        result = _translate(text, script=script, client=client)  # type: ignore[arg-type]
    except AIError as exc:
        return AnalysisResult(ok=False, error=str(exc))
    except Exception as exc:  # pragma: no cover - AIError covers the known cases
        return AnalysisResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    note = f"exploratory · {result.provider}/{result.model}"
    return AnalysisResult(ok=True, title="translation", text=result.text, note=note)


# ── Aegean line analyses ────────────────────────────────────────────────────────
def _aegean_signs(script_id: str, token_texts: tuple[str, ...]) -> AnalysisResult:
    """Per-sign glyph and sound value from the script's inventory. For an undeciphered
    script the value column is honestly blank / conventional (noted)."""
    from ..core.script import get_script

    inv = get_script(script_id).sign_inventory
    rows: list[tuple[str, ...]] = []
    for word in token_texts:
        for label in _sign_labels(word):
            # Sign labels are upper-case (PO, KU) but tokens may be written either case
            # (Linear B po-me vs Linear A KU-RO), so try the label as written then folded.
            sign = inv.by_label(label) or inv.by_label(label.upper()) or inv.by_label(label.lower())
            glyph = (sign.glyph if sign else "") or ""
            value = (sign.phonetic if sign and sign.phonetic else "—")
            rows.append((sign.label if sign else label, glyph, value))
    note = (
        "undeciphered — sign values are conventional, not a reading"
        if script_id in UNDECIPHERED
        else ""
    )
    return AnalysisResult(
        ok=True, title="signs", columns=("sign", "glyph", "value"),
        rows=tuple(rows), note=note,
    )


def _aegean_bridge(script_id: str, token_texts: tuple[str, ...]) -> AnalysisResult:
    """The Greek reading + gloss for each word (Linear B / Cypriot, deciphered)."""
    import importlib

    mod = importlib.import_module(f"..scripts.{script_id}", __package__)
    rows: list[tuple[str, ...]] = []
    for word in token_texts:
        phon = mod.word_to_phonetic(word)
        reading = mod.greek_reading(word)
        if reading:
            greek, gloss = reading
        else:
            greek, gloss = "", (mod.gloss(word) or "")
        rows.append((word, phon, greek, gloss))
    return AnalysisResult(
        ok=True, title="Greek reading", columns=("word", "sound", "Greek", "gloss"),
        rows=tuple(rows),
    )


def _lineara_exploratory(token_texts: tuple[str, ...]) -> AnalysisResult:
    """A hypothetical (Linear-B-shared) transliteration for each Linear A word, plainly
    labelled exploratory: Linear A is undeciphered, so this is not a reading."""
    from ..scripts.lineara import word_to_phonetic

    rows = tuple((word, word_to_phonetic(word)) for word in token_texts)
    return AnalysisResult(
        ok=True, title="transliteration (exploratory)",
        columns=("word", "conventional value"), rows=rows,
        note="Linear A is undeciphered — these are hypothetical, shared-with-Linear-B "
        "values, not an established reading",
    )


def _sign_labels(word: str) -> list[str]:
    """Split a syllabic word's surface form into its sign labels (``KU-RO`` → KU, RO)."""
    return [s for s in word.split("-") if s]


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


# ── Greek work library (fetch + read individual works, distinct from datasets) ──


def read_corpus_spec(spec: str) -> "Corpus":
    """Load any corpus spec — a registered id, a Greek work id (``tlg0012.tlg001``), or a
    ``.json``/``.db`` file — re-raising failures as a clean :class:`TuiError`.

    A superset of :func:`load_corpus` (registered ids only): this is how the corpus browser
    opens a fetched Greek work or a saved file. The registered corpora resolve identically."""
    from ..core.resolve import CorpusNotFound, read_corpus

    try:
        return read_corpus(spec)
    except (CorpusNotFound, KeyError):
        raise TuiError(f"no corpus {spec!r}") from None
    except Exception as exc:  # network / parse failure on a fetch-on-demand work
        raise TuiError(f"could not load {spec!r}: {exc}") from None


@dataclass(frozen=True)
class WorkRow:
    """One Greek work in the library table: catalogue metadata plus whether it is already
    fetched to the cache (and its on-disk size when so)."""

    id: str
    author: str
    title: str
    greek_title: str
    source: str
    fetched: bool
    bytes: int | None


def _fetched_works() -> list[dict[str, Any]]:
    from ..greek import list_fetched_works

    return list_fetched_works()


def fetched_work_ids() -> list[str]:
    """The CTS ids of every Greek work already downloaded to the cache (a local scan)."""
    return [w["id"] for w in _fetched_works()]


def remove_work(work_id: str) -> bool:
    """Delete one downloaded Greek work from the cache. Returns True if it was removed
    (False when it was not downloaded). Wraps ``greek.remove_fetched_works``."""
    from ..greek import remove_fetched_works

    return work_id in remove_fetched_works([work_id])


def fetched_work_entries() -> list[CorpusEntry]:
    """Every downloaded Greek work as a :class:`CorpusEntry`, so the corpus browser can list
    them alongside the registered corpora — a fetched work is a permanent, selectable corpus,
    not a transient one. Blurb is ``author — title (Greek work)``; always on disk, never
    undeciphered."""
    entries: list[CorpusEntry] = []
    for w in _fetched_works():
        label = f"{w['author']} — {w['title']}".strip(" —") or w["id"]
        entries.append(
            CorpusEntry(
                id=w["id"], blurb=f"{label} (Greek work)",
                downloaded=True, bundled=False, undeciphered=False,
            )
        )
    return entries


def catalog_rows(
    query: str | None = None,
    *,
    author: str | None = None,
    title: str | None = None,
    source: str | None = None,
) -> list[WorkRow]:
    """The Greek-work catalogue as :class:`WorkRow`s, each flagged with its fetched state.

    Case-insensitive substring filtering (the library ``catalog`` already ANDs the filters).
    The screen renders a capped slice; the full match list is returned so it can show the count."""
    from ..greek import catalog

    fetched = {w["id"]: w for w in _fetched_works()}
    out: list[WorkRow] = []
    for w in catalog(query, author=author, title=title, source=source):
        hit = fetched.get(w["id"])
        out.append(
            WorkRow(
                id=w["id"], author=w.get("author", ""), title=w.get("title", ""),
                greek_title=w.get("greek_title", ""), source=w.get("source", ""),
                fetched=hit is not None, bytes=(hit["bytes"] if hit else None),
            )
        )
    return out


def fetch_work(
    work_id: str,
    on_progress: Callable[[str], None] | None = None,
    abort: Callable[[], bool] | None = None,
) -> "Path":
    """Fetch one Greek work into the cache (via ``load_work``); returns its cache path.

    A screen runs this on a worker. ``abort`` is polled before the transfer (a single work is a
    small TEI file, so cancellation is best-effort, not mid-chunk). Errors become :class:`TuiError`."""
    from pathlib import Path

    from ..data import DataNotAvailableError, FetchAborted
    from ..greek import list_fetched_works, load_work

    if abort is not None and abort():
        raise FetchCanceled(f"fetch of {work_id} canceled")
    if on_progress is not None:
        on_progress(f"fetching {work_id}…")
    try:
        load_work(work_id)
    except FetchAborted:
        raise FetchCanceled(f"fetch of {work_id} canceled (partial download kept)") from None
    except DataNotAvailableError as exc:
        raise TuiError(str(exc)) from None
    except Exception as exc:  # network / parse failure
        raise TuiError(f"could not fetch {work_id!r}: {exc}") from None
    path = next((Path(w["path"]) for w in list_fetched_works() if w["id"] == work_id), None)
    if path is None:
        raise TuiError(f"fetched {work_id} but could not locate it in the cache")
    if on_progress is not None:
        on_progress(f"stored {work_id}")
    return path


def fetch_author_works(
    author: str,
    *,
    source: str = "auto",
    on_progress: Callable[[str], None] | None = None,
    abort: Callable[[], bool] | None = None,
) -> list[str]:
    """Fetch every catalogue work by ``author`` into the cache; returns the ids present after.

    Drives the shared ``fetch_works`` generator (idempotent — cached works are skipped), streaming
    a per-work line through ``on_progress``. A rate limit or abort surfaces as :class:`TuiError` /
    :class:`FetchCanceled` after the works already fetched are kept."""
    from ..data import FetchAborted
    from ..greek import GitHubRateLimitError, fetch_works

    src = None if source == "auto" else source
    done: list[str] = []

    def progress(i: int, total: int, w: dict[str, str]) -> None:
        if on_progress is not None:
            on_progress(f"[{i}/{total}] {w['id']} ({w.get('title', '')})…")

    try:
        for res in fetch_works(author=author, source=src, on_progress=progress, abort=abort):
            if res.status in ("fetched", "cached"):
                done.append(res.id)
    except FetchAborted:
        raise FetchCanceled(f"fetch of {author!r} works canceled (fetched works kept)") from None
    except GitHubRateLimitError as exc:
        raise TuiError(str(exc)) from None
    except Exception as exc:  # network / disk failure
        raise TuiError(f"could not fetch works by {author!r}: {exc}") from None
    return done


# ── persisted TUI config (theme, …); a sibling of the REPL history file ──


def config_path() -> "Path":
    """The TUI config file: ``$XDG_CONFIG_HOME/pyaegean/tui.json`` (or ``~/.config/...``)."""
    import os
    from pathlib import Path

    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "pyaegean" / "tui.json"


def load_tui_config() -> dict[str, Any]:
    """The persisted TUI config, or ``{}`` when missing/unreadable/invalid (never raises)."""
    import json

    try:
        return dict(json.loads(config_path().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}


def save_tui_config(data: dict[str, Any]) -> None:
    """Persist the TUI config (best-effort — a write failure is swallowed, like the REPL history)."""
    import json

    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass
