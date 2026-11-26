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
the SigLA dataset) and Cypro-Minoan are undeciphered. :func:`is_undeciphered`
flags the corpora a screen must caption that way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # type-only imports keep the module import-light
    from pathlib import Path

    from ..core.corpus import Corpus
    from ..core.model import Document, Token

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
    "greek_betacode",
    "greek_gloss",
    "greek_scan",
    "greek_syllables",
    "greek_ipa",
    "format_token_inspector",
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
    "remove_dataset",
    "library_summary",
    "library_packs",
    "library_items",
    "library_install",
    "library_remove",
    "missing_corpus_item",
    "missing_bible_items",
    "config_path",
    "load_tui_config",
    "save_tui_config",
]


class TuiError(Exception):
    """A clean, user-facing error a screen can display in place of a traceback."""


from ..core.catalog import (  # noqa: E402
    UNDECIPHERED_IDS as _CATALOG_UNDECIPHERED,
    tui_asset_map as _tui_asset_map,
    tui_blurbs as _tui_blurbs,
    tui_browsable_ids as _tui_browsable_ids,
)

# The browsable corpora (derived from aegean.core.catalog; excludes heavy archives
# ddbdp and patrologia from full-corpus TUI materialization).
CORPUS_IDS: tuple[str, ...] = _tui_browsable_ids()

# Undeciphered corpora: Linear A (lineara and sigla) and Cypro-Minoan.
UNDECIPHERED: frozenset[str] = _CATALOG_UNDECIPHERED

# One-line descriptions for the corpus overview (offline, no load needed).
_CORPUS_BLURB: dict[str, str] = _tui_blurbs()

# corpus id -> the release-asset name that must be in the store before the
# corpus loads. Corpora not listed here are bundled in the wheel.
_CORPUS_ASSET: dict[str, str] = {
    cid: asset for cid, asset in _tui_asset_map().items() if cid in CORPUS_IDS
}


def is_undeciphered(corpus_id: str) -> bool:
    """Whether ``corpus_id`` is an undeciphered corpus (Linear A, as both
    ``lineara`` and the SigLA dataset, or Cypro-Minoan), so a screen must caption
    uses conventional sign-value labels rather than Greek readings."""
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
    exact_balances: bool = False
    exact_difference: str = ""
    within_tolerance: bool = False
    account_eligible: bool = False
    account_eligible_exact: bool = False
    eligibility_mode: str = "tolerance"
    tolerance: float = 0.10


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
            exact_balances=r["exact_balances"],
            exact_difference=r["exact_difference"],
            within_tolerance=r["within_tolerance"],
            account_eligible=r["account_eligible"],
            account_eligible_exact=r["account_eligible_exact"],
            eligibility_mode=r["eligibility_mode"],
            tolerance=r["tolerance"],
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


def greek_betacode(text: str) -> str:
    """Convert ASCII Beta Code to Unicode Greek (never raises; passes through on error)."""
    from ..greek import betacode_to_unicode

    if not text:
        return ""
    try:
        return betacode_to_unicode(text)
    except Exception:  # pragma: no cover - betacode_to_unicode is total
        return text


_TUI_DODSON: Any = None


def _tui_dodson() -> Any:
    """Lazy offline Dodson lexicon instance private to the TUI adapter."""
    global _TUI_DODSON
    if _TUI_DODSON is None:
        from ..greek.koine import DodsonLexicon

        _TUI_DODSON = DodsonLexicon.load()
    return _TUI_DODSON


def greek_gloss(text: str) -> GreekResult:
    """Gloss every Greek word in ``text`` using active registry lexica plus bundled Dodson.

    Never fetches over the network and never raises. Returns one row per word token
    with ``word``, ``lemma``, ``strongs``, ``gloss``, and ``source``."""
    from ..greek import lemmatize, tokenize
    from ..greek.lexicons import active_lexica, entry as registry_lookup

    text = text.strip()
    if not text:
        return GreekResult(ok=True, rows=[])
    try:
        words = [t.text for t in tokenize(text) if any(ch.isalpha() for ch in t.text)]
        dodson = _tui_dodson()
        active_names = active_lexica()
        rows: list[dict[str, Any]] = []
        for word in words:
            lemma = lemmatize(word) or word
            entry = dodson.lookup(word) or (dodson.lookup(lemma) if lemma != word else None)
            strongs = f"G{entry.strongs}" if entry is not None else ""
            gloss_text = entry.gloss if entry is not None else ""
            source = "dodson" if entry is not None else ""
            if active_names:
                reg_entry = registry_lookup(lemma) or registry_lookup(word)
                if reg_entry is not None and reg_entry.gloss:
                    gloss_text = reg_entry.gloss
                    source = reg_entry.lexicon
            rows.append({
                "word": word,
                "lemma": entry.lemma if entry is not None else lemma,
                "strongs": strongs,
                "gloss": gloss_text,
                "source": source,
            })
    except Exception as exc:  # pragma: no cover - offline helpers are total
        return GreekResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    glossed = sum(1 for r in rows if r["gloss"])
    return GreekResult(ok=True, rows=rows, summary=f"{glossed}/{len(rows)} glossed")


def format_token_inspector(token: TokenCell, *, script_id: str = "greek") -> str:
    """One-line scholarly inspection summary for the highlighted reader token."""
    parts: list[str] = [token.text]
    if token.status and token.status != "certain":
        parts.append(f"[{token.status}]")
    ann = token.annotations
    lemma = ann.get("lemma", "")
    morph = ann.get("morph") or ann.get("feats") or ann.get("xpos") or ""
    upos = ann.get("upos", "")
    strongs = ann.get("strongs", "")
    gloss = ann.get("gloss", "")
    if not gloss and script_id == "greek" and any(ch.isalpha() for ch in token.text):
        try:
            dodson = _tui_dodson()
            hit = (
                dodson.by_strongs(strongs)
                if strongs
                else (dodson.lookup(lemma) if lemma else dodson.lookup(token.text))
            )
            if hit is not None:
                gloss = hit.gloss
                if not lemma:
                    lemma = hit.lemma
                if not strongs:
                    strongs = hit.strongs
        except Exception:
            pass
    if lemma:
        parts.append(f"lemma: {lemma}")
    if upos and morph:
        parts.append(f"{upos} ({morph})")
    elif morph:
        parts.append(morph)
    elif upos:
        parts.append(upos)
    if strongs:
        s_code = strongs if strongs.upper().startswith("G") else f"G{strongs}"
        parts.append(f"Strong's {s_code}")
    if gloss:
        parts.append(f"'{gloss}'")
    if token.alt:
        parts.append(f"alt: {', '.join(token.alt)}")
    if token.form_state is not None:
        dipl = token.form_state.get("diplomatic")
        reg = token.form_state.get("regularized")
        if dipl and reg and dipl != reg:
            parts.append(f"dipl. {dipl} -> reg. {reg}")
    return "  ·  ".join(parts)


# ── in-reader line analysis ─────────────────────────────────────────────────────
# One line of a document, analysed on demand: Greek lines get the offline parser/
# tagger, the neural pipeline (plus optional weighted OOV reranking), dictionary
# glossing, verse scansion, IPA, and (BYOAI, optional) translation; syllabic
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

    Greek: offline parser/tagger, neural pipeline, neural + weighted OOV reranker
    (both need ``[neural]`` + the model), dictionary glossing (Dodson + active
    lexica), verse scansion, IPA, and translation (only when a BYOAI provider is
    configured). Linear B / Cypriot: the Greek reading + gloss, and sign values.
    Linear A / Cypro-Minoan (undeciphered): signs and, for Linear A, an exploratory
    transliteration, both plainly caveated."""
    if script_id in _GREEK_SCRIPTS:
        neural_ok, neural_why = greek_neural_available()
        tr_ok, tr_why = translation_available()
        return [
            AnalysisOption("offline", "offline parser / tagger", True),
            AnalysisOption("neural", "neural pipeline", neural_ok, neural_why),
            AnalysisOption("neural_oov", "neural + OOV reranker (weighted)", neural_ok, neural_why),
            AnalysisOption("gloss", "lexicon glosses (Dodson + active lexica)", True),
            AnalysisOption("scan", "metrical scansion (auto-detect meter)", True),
            AnalysisOption("ipa", "IPA (reconstructed)", True),
            AnalysisOption("translate", "translate (BYOAI, optional)", tr_ok, tr_why),
        ]
    if script_id in {"linearb", "cypriot"}:
        return [
            AnalysisOption("bridge", "Greek reading + gloss", True),
            AnalysisOption("signs", "signs (glyph + value)", True),
        ]
    if script_id in {"lineara", "sigla"}:
        return [
            AnalysisOption("exploratory", "conventional values (Linear B-shared)", True),
            AnalysisOption("signs", "signs (glyph + value)", True),
        ]
    if script_id == "cyprominoan":
        return [
            AnalysisOption("signs", "signs (glyph only)", True),
        ]
    return [AnalysisOption("signs", "signs", True)]


def run_line_analysis(
    key: str, *, script_id: str, text: str, token_texts: tuple[str, ...],
    source_context: str | None = None,
) -> AnalysisResult:
    """Run analysis ``key`` on one line and return a renderable result. Never raises.

    ``text`` is the line as one string (Greek analyses use it); ``token_texts`` are the
    line's token surface forms (the syllabic analyses split each on ``-`` into signs).
    ``source_context`` is retained source material for translation only."""
    try:
        if key == "offline":
            return _greek_offline(text)
        if key == "neural":
            return _greek_neural(text, use_oov=False)
        if key == "neural_oov":
            return _greek_neural(text, use_oov=True)
        if key == "gloss":
            return _greek_gloss_result(text)
        if key == "scan":
            return _greek_scan_result(text)
        if key == "ipa":
            return _greek_ipa_result(text)
        if key == "translate":
            return translate_line(text, source_context=source_context)
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
    return True, "" if fetched else "downloads the model (~173 MB) on first run"


def _greek_neural(text: str, *, use_oov: bool = False) -> AnalysisResult:
    title = "neural + OOV reranker (weighted)" if use_oov else "neural pipeline"
    text = text.strip()
    if not text:
        return AnalysisResult(ok=True, title=title)
    from ..greek import (
        disable_oov_lemma_reranker,
        oov_lemma_reranker_active,
        pipeline,
        use_calibration_registry,
        use_neural_pipeline,
        use_oov_lemma_reranker,
    )
    from ..greek import calibrate as _cal

    try:
        use_neural_pipeline()
    except Exception as exc:
        return AnalysisResult(ok=False, error=f"neural pipeline unavailable: {exc}")

    # Load bundled Schema-2 calibration if none is active so scholars see calibrated
    # confidence alongside predictions (raw softmax is never exposed).
    if _cal.active_registry() is None and _cal.active() is None:
        try:
            use_calibration_registry()
        except Exception:
            pass

    was_oov = oov_lemma_reranker_active()
    try:
        if use_oov and not was_oov:
            use_oov_lemma_reranker(config="weighted")
        has_conf = _cal.active_registry() is not None or _cal.active() is not None
        recs = pipeline(text, parse=True, with_confidence=has_conf)
    except Exception as exc:
        return AnalysisResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    finally:
        if use_oov and not was_oov:
            try:
                disable_oov_lemma_reranker()
            except Exception:
                pass

    from .._view import format_confidence

    any_conf = any(
        r.upos_confidence is not None or r.lemma_confidence is not None for r in recs
    )
    rows: list[tuple[str, ...]] = []
    for r in recs:
        base = (
            str(r.index), r.text, r.upos,
            # an unresolved/identity lemma is flagged with its evidence class so a model
            # guess never displays like a grounded analysis
            r.lemma if not r.review_recommended else f"{r.lemma} [{r.lemma_source.value}]",
            r.feats or "",
            f"{r.relation}→{r.head}" if r.relation and r.head is not None else "",
        )
        if any_conf:
            rows.append(base + (format_confidence(r.upos_confidence, r.lemma_confidence),))
        else:
            rows.append(base)
    columns: tuple[str, ...] = (
        ("#", "token", "POS", "lemma", "features", "dep", "conf")
        if any_conf
        else ("#", "token", "POS", "lemma", "features", "dep")
    )
    note = "grc-joint neural model + bundled weighted top-10 OOV lemma reranker" if use_oov else "grc-joint neural model"
    if any_conf:
        note += " · calibrated confidence"
    return AnalysisResult(
        ok=True, title=title, columns=columns, rows=tuple(rows), note=note,
    )


def _greek_gloss_result(text: str) -> AnalysisResult:
    r = greek_gloss(text)
    if not r.ok:
        return AnalysisResult(ok=False, error=r.error)
    rows = tuple(
        (row["word"], row["lemma"], row["strongs"] or "-", row["gloss"] or "-", row["source"] or "-")
        for row in r.rows
    )
    return AnalysisResult(
        ok=True,
        title="lexicon glosses",
        columns=("word", "lemma", "Strong's", "gloss", "source"),
        rows=rows,
        note=r.summary,
    )


def _greek_scan_result(text: str) -> AnalysisResult:
    from ..greek.meter import AEOLIC_LINES

    text = text.strip()
    if not text:
        return AnalysisResult(ok=True, title="metrical scansion")
    meters = ("hexameter", "pentameter", "trimeter", *sorted(AEOLIC_LINES))
    for meter in meters:
        res = greek_scan(text, meter)
        if res.ok and res.rows:
            rows = tuple((r["pattern"], r["foot"]) for r in res.rows)
            return AnalysisResult(
                ok=True,
                title=f"metrical scansion ({meter})",
                columns=("pattern", "foot"),
                rows=rows,
                note=res.summary,
            )
    return AnalysisResult(
        ok=False,
        error="line does not fit hexameter, pentameter, trimeter, or Aeolic lyric templates",
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


def _aligned_line_text(document: "Document", tokens: list["Token"]) -> str | None:
    """An exact retained source slice, only when every local mapping is reliable."""
    source = document.source_text
    if source is None or not tokens:
        return None
    start: int | None = None
    end = 0
    for token in tokens:
        alignment = token.alignment
        if alignment is None:
            return None
        try:
            alignment.validate_source(source, document_id=document.id)
        except (TypeError, ValueError):
            return None
        if start is None:
            start = alignment.start_char
        elif alignment.start_char < end:
            return None
        end = alignment.end_char
    return source[start:end]


def _line_source_context(
    corpus: "Corpus", doc_id: str | None, line_number: int, *,
    token_texts: tuple[str, ...] | None = None,
) -> str | None:
    """Serialize the selected reader line and at most one actual neighbor each side.

    Reader line numbers select within one document, never by matching repeated
    text or token positions. Source-aligned slices preserve their exact characters;
    legacy token joins are explicitly labeled reconstructions. Editorial state and
    known source/speaker annotations accompany the text, without model annotations.
    Nothing is fetched or inferred, and an unavailable selection supplies no context.
    """
    import json

    if doc_id is None:
        return None
    try:
        document = _resolve_document(corpus, doc_id)
    except TuiError:
        return None
    selected = line_number - 1
    if not 0 <= selected < len(document.lines):
        return None
    selected_tokens = [document.tokens[i] for i in document.lines[selected]]
    if token_texts is not None and tuple(t.text for t in selected_tokens) != token_texts:
        return None
    source_keys = frozenset({
        "who", "speaker", "speaker_label", "speech_id", "role", "ref",
    })
    lines: list[dict[str, Any]] = []
    for index in range(max(0, selected - 1), min(len(document.lines), selected + 2)):
        indices = document.lines[index]
        tokens = [document.tokens[i] for i in indices]
        # A noncontiguous grouping must not claim intervening, unselected tokens
        # belong to this reader line merely because its endpoints are aligned.
        contiguous = bool(indices) and indices == list(range(indices[0], indices[-1] + 1))
        raw = _aligned_line_text(document, tokens) if contiguous else None
        cells: list[dict[str, Any]] = []
        for token in tokens:
            cell: dict[str, Any] = {
                "text": token.text, "kind": token.kind.value,
                "status": token.status.value, "alternates": list(token.alt),
            }
            metadata = {k: v for k, v in token.annotations.items() if k in source_keys}
            if metadata:
                cell["source_metadata"] = metadata
            state = token.form_state
            if state is not None:
                editorial: dict[str, Any] = {
                    "diplomatic": state.diplomatic,
                    "segments": [segment.to_dict() for segment in state.segments],
                }
                if state.regularized is not None:
                    editorial["regularized"] = state.regularized
                cell["editorial_state"] = editorial
            cells.append(cell)
        lines.append({
            "reader_line": index + 1,
            "selected": index == selected,
            "text": raw if raw is not None else " ".join(t.text for t in tokens),
            "text_origin": "aligned_source_slice" if raw is not None else "reconstructed_token_text",
            "tokens": cells,
        })
    context: dict[str, Any] = {
        "document_id": document.id, "selected_reader_line": line_number, "lines": lines,
    }
    if document.meta.name:
        context["document_name"] = document.meta.name
    provenance = corpus.provenance
    if provenance is not None:
        context["source"] = {
            key: value for key in ("source", "citation", "url", "edition_fidelity")
            if (value := getattr(provenance, key))
        }
    return json.dumps(context, ensure_ascii=False, sort_keys=True)


def translate_line(
    text: str, *, script: str = "greek", source_context: str | None = None,
) -> AnalysisResult:
    """Translate one line via the configured BYOAI provider (exploratory, provenanced).

    Returns exact translation text with provider/model and the shared translation
    audit labels in ``note``; a missing key or any provider error becomes a clean
    ``error`` (translation never crashes the reader).
    The selected text is passed exactly, with source context supplied separately."""
    if not text.strip():
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
        result = _translate(
            text, script=script, client=client, source_context=source_context,
        )  # type: ignore[arg-type]
    except AIError as exc:
        return AnalysisResult(ok=False, error=str(exc))
    except Exception as exc:  # pragma: no cover - AIError covers the known cases
        return AnalysisResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    note = f"exploratory · {result.provider}/{result.model}"
    audit_notes = result._translation_notes()
    if audit_notes:
        note += "\n\n" + audit_notes
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
        "Conventional Linear B-derived phonetic values."
        if script_id in UNDECIPHERED
        else ""
    )
    return AnalysisResult(
        ok=True, title="signs", columns=("sign", "glyph", "value"),
        rows=tuple(rows), note=note,
    )


def _aegean_bridge(script_id: str, token_texts: tuple[str, ...]) -> AnalysisResult:
    """Greek reading and gloss for each word (Linear B / Cypriot)."""
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
    """Linear B-shared conventional phonetic values for Linear A words."""
    from ..scripts.lineara import word_to_phonetic

    rows = tuple((word, word_to_phonetic(word)) for word in token_texts)
    return AnalysisResult(
        ok=True, title="conventional values (Linear B-shared)",
        columns=("word", "conventional value"), rows=rows,
        note="Conventional Linear B-shared phonetic values.",
    )


def _sign_labels(word: str) -> list[str]:
    """Split a syllabic word's surface form into its sign labels (``KU-RO`` → KU, RO)."""
    return [s for s in word.split("-") if s]


# ── data store, Greek works, config & unified library manager (re-exported) ──
from ._library_data import (  # noqa: E402, F401
    FetchCanceled as FetchCanceled,
    WorkRow as WorkRow,
    _fetched_works as _fetched_works,
    catalog_rows as catalog_rows,
    config_path as config_path,
    dataset_rows as dataset_rows,
    doctor_report as doctor_report,
    fetch_author_works as fetch_author_works,
    fetch_dataset as fetch_dataset,
    fetch_work as fetch_work,
    fetched_work_entries as fetched_work_entries,
    fetched_work_ids as fetched_work_ids,
    library_install as library_install,
    library_items as library_items,
    library_packs as library_packs,
    library_remove as library_remove,
    library_summary as library_summary,
    load_tui_config as load_tui_config,
    missing_bible_items as missing_bible_items,
    missing_corpus_item as missing_corpus_item,
    read_corpus_spec as read_corpus_spec,
    remove_dataset as remove_dataset,
    remove_work as remove_work,
    save_tui_config as save_tui_config,
)

# ── Biblical & Koine Greek study screen adapters (re-exported) ────────────

from ._bible_data import (  # noqa: E402
    _parse_passage_spec as _parse_passage_spec,
)
from ._bible_data import (  # noqa: E402
    bible_compare_text as bible_compare_text,
)
from ._bible_data import (  # noqa: E402
    bible_lxx_and_catenae_text as bible_lxx_and_catenae_text,
)
from ._bible_data import (  # noqa: E402
    bible_lxx_text as bible_lxx_text,
)
from ._bible_data import (  # noqa: E402
    bible_patristics_text as bible_patristics_text,
)
from ._bible_data import (  # noqa: E402
    bible_read_text as bible_read_text,
)
from ._bible_data import (  # noqa: E402
    bible_witnesses_text as bible_witnesses_text,
)
from ._bible_data import (  # noqa: E402
    bible_word_study_text as bible_word_study_text,
)
