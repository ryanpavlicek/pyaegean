"""Corpus health report — a descriptive diagnostic over one corpus.

`diagnose(corpus)` composes existing public machinery (reading statuses, the
accounting reconciliation, the numeral parser, provenance/citation, the review
evidence classes, the sign inventory) into one `DiagnoseReport`: what the corpus
is made of and where a scholar might want to look, stated as OBSERVABLE facts,
never as a verdict.

Framing rule (accounting): Aegean metrology and the section boundaries of an
account are imperfectly understood, so a stated total that does not reconcile is
a *lead, not a verdict on the scribe*. The report says exactly that wherever it
reports a discrepancy. Every check degrades gracefully on a corpus it does not
apply to (a Greek prose corpus has no accounting section — it is marked
not-applicable, never an error).

Zero-dependency: the report builds from the stdlib and the core value objects;
rich (for `.print`) and pandas (for `.to_dataframe`) are imported lazily.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .model import ReadingStatus, TokenKind
from .numerals import BalanceCheck

if TYPE_CHECKING:  # type-only: keep the core import-clean
    from .corpus import Corpus

__all__ = [
    "ACCOUNTING_CAVEAT",
    "AccountingProfile",
    "DiagnoseReport",
    "NumeralProfile",
    "ProvenanceProfile",
    "ReviewProfile",
    "SignProfile",
    "StatusProfile",
    "diagnose",
]

# The four undeciphered/deciphered Aegean syllabic scripts (registered_scripts()
# minus alphabetic Greek): the ones whose word tokens decompose into syllabograms,
# so the sign-frequency checks apply to them.
_AEGEAN_SCRIPTS = frozenset({"lineara", "linearb", "cypriot", "cyprominoan"})

# The standard Aegean-accounting caveat, mirroring the accounting module's own
# docstring language and wiki/Limitations. It travels with any reported discrepancy.
ACCOUNTING_CAVEAT = (
    "Aegean metrology and accounting section boundaries are imperfectly understood; "
    "a reported discrepancy is a lead, not a verdict on the scribe."
)

_DISCREPANCY_TOLERANCE = 0.10  # mirrors accounting.is_checkable_account's lenient cutoff
_EXAMPLE_CAP = 10              # how many example ids/tokens a section keeps


# ── structured sections ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class StatusProfile:
    """Token counts by editorial `ReadingStatus`, plus how many documents carry a
    non-CERTAIN (damaged / restored / lost) token."""

    total_tokens: int
    certain: int
    unclear: int
    restored: int
    lost: int
    documents_total: int
    documents_with_apparatus: int


@dataclass(frozen=True)
class ProvenanceProfile:
    """Whether the corpus can state where it came from and be cited."""

    has_provenance: bool
    has_source: bool
    has_license: bool
    has_citation: bool
    can_cite: bool
    citation: str
    edition_fidelity: str


@dataclass(frozen=True)
class AccountingProfile:
    """Stated-total reconciliation over an Aegean accounting corpus.

    ``balanced`` / ``discrepant`` split the documents that carry a stated total
    (KU-RO / KU-RA / TO-SO) by whether every total reconciles within the lenient
    metrological tolerance; ``intact_and_balancing`` is the clean drill set
    (`accounting.checkable_accounts`). A discrepancy is a lead, not a verdict."""

    applicable: bool
    note: str
    documents_with_total: int
    balanced: int
    discrepant: int
    balanced_ids: tuple[str, ...]
    discrepant_ids: tuple[str, ...]
    intact_and_balancing: int
    checkable_ids: tuple[str, ...]


@dataclass(frozen=True)
class NumeralProfile:
    """Tokens the loader classified as numerals that the numeral parser cannot
    parse — an observable inconsistency worth a look, not an error."""

    applicable: bool
    note: str
    anomaly_count: int
    examples: tuple[tuple[str, str], ...]  # (doc_id, token_text)


@dataclass(frozen=True)
class ReviewProfile:
    """Annotation review state: how densely a sourced-lemmatization corpus carries
    tokens a human should verify (the same predicate `aegean.io.review` uses)."""

    applicable: bool
    note: str
    word_tokens: int
    needs_review: int
    density: float


@dataclass(frozen=True)
class SignProfile:
    """Sign-frequency observations for an Aegean corpus (level='full' only): signs
    used exactly once in word tokens (hapax), and word-token signs whose label is
    absent from the script's sign inventory. Observable facts, no interpretation."""

    applicable: bool
    computed: bool
    note: str
    distinct_signs: int
    hapax_count: int
    hapax_examples: tuple[str, ...]
    out_of_inventory_occurrences: int
    out_of_inventory_distinct: int
    out_of_inventory_examples: tuple[tuple[str, str, str], ...]  # (doc_id, token, sign)


@dataclass(frozen=True)
class DiagnoseReport:
    """A descriptive health report for one corpus. Sections are always present; a
    section that does not apply carries ``applicable=False`` and an explanatory note.

    Render with `print` (rich table when installed, plain text otherwise),
    `to_markdown` (a shareable summary), or `to_dataframe` (needs the ``[data]`` extra)."""

    script_id: str
    source: str
    level: str
    n_documents: int
    n_tokens: int
    reading_status: StatusProfile
    provenance: ProvenanceProfile
    accounting: AccountingProfile
    numerals: NumeralProfile
    review: ReviewProfile
    signs: SignProfile

    # ── rendering ────────────────────────────────────────────────────────────
    def _sections(self) -> list[tuple[str, list[tuple[str, str]], str]]:
        """(title, [(check, value)...], note) for each section, shared by every renderer."""
        s = self.reading_status
        p = self.provenance
        a = self.accounting
        nm = self.numerals
        rv = self.review
        sg = self.signs

        out: list[tuple[str, list[tuple[str, str]], str]] = []
        out.append((
            "overview",
            [
                ("script", self.script_id or "(unnamed)"),
                ("documents", str(self.n_documents)),
                ("tokens", str(self.n_tokens)),
                ("depth", self.level),
            ],
            self.source and f"source: {self.source}" or "",
        ))
        out.append((
            "reading status",
            [
                ("total tokens", str(s.total_tokens)),
                ("certain", str(s.certain)),
                ("unclear", str(s.unclear)),
                ("restored", str(s.restored)),
                ("lost", str(s.lost)),
                (
                    "documents with apparatus",
                    f"{s.documents_with_apparatus} of {s.documents_total}",
                ),
            ],
            "",
        ))
        out.append((
            "provenance & citation",
            [
                ("provenance recorded", _yn(p.has_provenance)),
                ("license recorded", _yn(p.has_license)),
                ("citation recorded", _yn(p.has_citation)),
                ("can produce a citation", _yn(p.can_cite)),
                ("edition fidelity", p.edition_fidelity or "(none)"),
            ],
            p.can_cite and f"cite: {p.citation}" or "",
        ))
        if a.applicable:
            out.append((
                "accounting",
                [
                    ("documents with a stated total", str(a.documents_with_total)),
                    ("balanced (within tolerance)", str(a.balanced)),
                    ("discrepant (leads)", str(a.discrepant)),
                    ("intact and balancing", str(a.intact_and_balancing)),
                    ("discrepant ids", _ids(a.discrepant_ids)),
                ],
                ACCOUNTING_CAVEAT,
            ))
        else:
            out.append(("accounting", [("applicable", "no")], a.note))
        if nm.applicable:
            out.append((
                "numeral anomalies",
                [
                    ("numeral-like tokens that fail to parse", str(nm.anomaly_count)),
                    ("examples", _examples2(nm.examples)),
                ],
                "",
            ))
        else:
            out.append(("numeral anomalies", [("applicable", "no")], nm.note))
        if rv.applicable:
            out.append((
                "annotation review",
                [
                    ("word tokens", str(rv.word_tokens)),
                    ("needs review", str(rv.needs_review)),
                    ("review density", f"{rv.density * 100:.1f}%"),
                ],
                "",
            ))
        else:
            out.append(("annotation review", [("applicable", "no")], rv.note))
        if not sg.applicable:
            out.append(("sign-frequency outliers", [("applicable", "no")], sg.note))
        elif not sg.computed:
            out.append(("sign-frequency outliers", [("computed", "no")], sg.note))
        else:
            out.append((
                "sign-frequency outliers",
                [
                    ("distinct signs (word tokens)", str(sg.distinct_signs)),
                    ("hapax signs (used once)", str(sg.hapax_count)),
                    ("hapax examples", _ids(sg.hapax_examples)),
                    ("signs absent from inventory (occurrences)",
                     str(sg.out_of_inventory_occurrences)),
                    ("… distinct labels", str(sg.out_of_inventory_distinct)),
                    ("examples", _examples3(sg.out_of_inventory_examples)),
                ],
                "",
            ))
        return out

    def to_markdown(self) -> str:
        """A shareable corpus-health summary in Markdown. Wherever a discrepancy is
        reported, the standard Aegean-metrology caveat travels with it."""
        lines = [f"# Corpus health report: {self.script_id or '(unnamed)'}", ""]
        for title, rows, note in self._sections():
            lines.append(f"## {_title(title)}")
            lines.append("")
            lines.append("| check | value |")
            lines.append("| --- | --- |")
            for check, value in rows:
                lines.append(f"| {check} | {_md_cell(value)} |")
            if note:
                lines.append("")
                lines.append(f"> {note}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def to_text(self) -> str:
        """A plain-text rendering (the fallback used by `print` when rich is absent)."""
        lines: list[str] = [f"Corpus health report: {self.script_id or '(unnamed)'}", ""]
        for title, rows, note in self._sections():
            lines.append(_title(title))
            width = max((len(c) for c, _ in rows), default=0)
            for check, value in rows:
                lines.append(f"  {check.ljust(width)}  {value}")
            if note:
                lines.append(f"  ({note})")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def print(self, *, console: Any = None) -> None:
        """Render to the terminal: a rich table per section when rich is importable,
        a plain-text fallback otherwise (the core never requires rich)."""
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.text import Text
        except ModuleNotFoundError:
            import sys

            sys.stdout.write(self.to_text())
            return
        con = console or Console()
        con.print(f"[bold]Corpus health report: {self.script_id or '(unnamed)'}[/bold]")
        for title, rows, note in self._sections():
            t = Table(title=_title(title), title_justify="left")
            t.add_column("check")
            t.add_column("value")
            for check, value in rows:
                t.add_row(Text(check), Text(value))
            con.print(t)
            if note:
                con.print(Text(note, style="dim"))

    def to_dataframe(self):  # type: ignore[no-untyped-def]
        """A pandas DataFrame with one row per (section, check).

        pandas is an optional dependency — install with ``pip install 'pyaegean[data]'``."""
        try:
            import pandas as pd  # lazy, optional [data] extra
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "to_dataframe() needs pandas; install it with: pip install 'pyaegean[data]'"
            ) from exc

        rows = [
            {"section": title, "check": check, "value": value}
            for title, section_rows, _note in self._sections()
            for check, value in section_rows
        ]
        return pd.DataFrame(rows, columns=["section", "check", "value"])


# ── rendering helpers ───────────────────────────────────────────────────────────
def _yn(flag: bool) -> str:
    return "yes" if flag else "no"


def _title(t: str) -> str:
    return t[:1].upper() + t[1:]


def _ids(ids: tuple[str, ...]) -> str:
    if not ids:
        return "(none)"
    shown = ", ".join(ids[:_EXAMPLE_CAP])
    return shown + (f" (+{len(ids) - _EXAMPLE_CAP} more)" if len(ids) > _EXAMPLE_CAP else "")


def _examples2(pairs: tuple[tuple[str, str], ...]) -> str:
    if not pairs:
        return "(none)"
    return "; ".join(f"{d}: {t}" for d, t in pairs[:_EXAMPLE_CAP])


def _examples3(triples: tuple[tuple[str, str, str], ...]) -> str:
    if not triples:
        return "(none)"
    return "; ".join(f"{d}: {tok} [{s}]" for d, tok, s in triples[:_EXAMPLE_CAP])


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|")


# ── the diagnostic itself ────────────────────────────────────────────────────────
def _tolerance_ok(check: BalanceCheck, tolerance: float = _DISCREPANCY_TOLERANCE) -> bool:
    """Whether one total reconciles within the lenient metrological tolerance
    (mirrors accounting.is_checkable_account's cutoff)."""
    return abs(check.difference) <= max(1.0, tolerance * abs(check.stated_total))


def diagnose(corpus: "Corpus", level: str = "quick") -> DiagnoseReport:
    """A descriptive health report for ``corpus``.

    ``level`` is ``"quick"`` (the default: reading status, provenance, accounting,
    numeral anomalies, review state) or ``"full"`` (adds the sign-frequency scan for
    Aegean corpora). Composes only existing public machinery; every check that does
    not apply to this corpus (a Greek prose corpus has no accounting) is marked
    not-applicable rather than raising."""
    if level not in ("quick", "full"):
        raise ValueError(f"level must be 'quick' or 'full'; got {level!r}")

    from ..io.review import needs_review_flag
    from .numerals import _MARKERS_BY_SCRIPT, parse_value

    docs = corpus.documents
    script_id = corpus.script_id
    prov = corpus.provenance

    # ── single pass: statuses, numeral anomalies, review evidence classes ──────
    total_tokens = 0
    by_status: Counter[ReadingStatus] = Counter()
    docs_with_apparatus = 0
    numeral_anomalies: list[tuple[str, str]] = []
    word_tokens = 0
    needs_review = 0
    has_evidence_class = False
    for d in docs:
        apparatus = False
        for t in d.tokens:
            total_tokens += 1
            by_status[t.status] += 1
            if t.status is not ReadingStatus.CERTAIN:
                apparatus = True
            if t.kind is TokenKind.NUMERAL and parse_value(t.text) is None:
                numeral_anomalies.append((d.id, t.text))
            if t.kind is TokenKind.WORD:
                word_tokens += 1
                if "lemma_source" in t.annotations or "lemma_known" in t.annotations:
                    has_evidence_class = True
                    if needs_review_flag(t.annotations):
                        needs_review += 1
        if apparatus:
            docs_with_apparatus += 1

    reading_status = StatusProfile(
        total_tokens=total_tokens,
        certain=by_status[ReadingStatus.CERTAIN],
        unclear=by_status[ReadingStatus.UNCLEAR],
        restored=by_status[ReadingStatus.RESTORED],
        lost=by_status[ReadingStatus.LOST],
        documents_total=len(docs),
        documents_with_apparatus=docs_with_apparatus,
    )

    # ── provenance / citation ──────────────────────────────────────────────────
    can_cite = False
    citation = ""
    if prov is not None:
        try:
            citation = corpus.cite()
            can_cite = bool(citation)
        except Exception:
            can_cite = False
    provenance = ProvenanceProfile(
        has_provenance=prov is not None,
        has_source=bool(prov and prov.source),
        has_license=bool(prov and prov.license),
        has_citation=bool(prov and prov.citation),
        can_cite=can_cite,
        citation=citation,
        edition_fidelity=(prov.edition_fidelity if prov is not None else ""),
    )

    # ── accounting (Linear A / B; the scripts numerals.py defines markers for) ──
    accounting_scripts = frozenset(_MARKERS_BY_SCRIPT)
    if script_id in accounting_scripts:
        from ..analysis.accounting import balance_check, checkable_accounts

        with_total: list[str] = []
        balanced_ids: list[str] = []
        discrepant_ids: list[str] = []
        for d in docs:
            checks = balance_check(d)
            if not checks:
                continue
            with_total.append(d.id)
            if all(_tolerance_ok(c) for c in checks):
                balanced_ids.append(d.id)
            else:
                discrepant_ids.append(d.id)
        checkable_ids = [d.id for d in checkable_accounts(corpus)]
        accounting = AccountingProfile(
            applicable=True,
            note="",
            documents_with_total=len(with_total),
            balanced=len(balanced_ids),
            discrepant=len(discrepant_ids),
            balanced_ids=tuple(balanced_ids),
            discrepant_ids=tuple(discrepant_ids),
            intact_and_balancing=len(checkable_ids),
            checkable_ids=tuple(checkable_ids),
        )
        numerals = NumeralProfile(
            applicable=True,
            note="",
            anomaly_count=len(numeral_anomalies),
            examples=tuple(numeral_anomalies[:_EXAMPLE_CAP]),
        )
    else:
        na = f"{script_id or 'this corpus'} carries no accounting numerals"
        accounting = AccountingProfile(
            applicable=False, note=na, documents_with_total=0, balanced=0, discrepant=0,
            balanced_ids=(), discrepant_ids=(), intact_and_balancing=0, checkable_ids=(),
        )
        numerals = NumeralProfile(
            applicable=False, note=na, anomaly_count=0, examples=()
        )

    # ── annotation review state ────────────────────────────────────────────────
    if has_evidence_class:
        review = ReviewProfile(
            applicable=True,
            note="",
            word_tokens=word_tokens,
            needs_review=needs_review,
            density=(needs_review / word_tokens if word_tokens else 0.0),
        )
    else:
        review = ReviewProfile(
            applicable=False,
            note="no sourced-lemmatization evidence classes; run aegean.greek.annotate first",
            word_tokens=word_tokens,
            needs_review=0,
            density=0.0,
        )

    # ── sign-frequency outliers (Aegean, full only) ────────────────────────────
    signs = _sign_profile(corpus, script_id, level == "full")

    return DiagnoseReport(
        script_id=script_id,
        source=(prov.source if prov is not None else ""),
        level=level,
        n_documents=len(docs),
        n_tokens=total_tokens,
        reading_status=reading_status,
        provenance=provenance,
        accounting=accounting,
        numerals=numerals,
        review=review,
        signs=signs,
    )


def _sign_profile(corpus: "Corpus", script_id: str, computed: bool) -> SignProfile:
    if script_id not in _AEGEAN_SCRIPTS:
        return SignProfile(
            applicable=False, computed=False,
            note=f"{script_id or 'this corpus'} is not an Aegean syllabic script",
            distinct_signs=0, hapax_count=0, hapax_examples=(),
            out_of_inventory_occurrences=0, out_of_inventory_distinct=0,
            out_of_inventory_examples=(),
        )
    if not computed:
        return SignProfile(
            applicable=True, computed=False,
            note="run with --deep (level='full') to scan sign frequencies",
            distinct_signs=0, hapax_count=0, hapax_examples=(),
            out_of_inventory_occurrences=0, out_of_inventory_distinct=0,
            out_of_inventory_examples=(),
        )
    inv = corpus.sign_inventory
    freq: Counter[str] = Counter()
    out_of_inv_examples: list[tuple[str, str, str]] = []
    out_of_inv_labels: set[str] = set()
    out_of_inv_occurrences = 0
    for d in corpus.documents:
        for t in d.tokens:
            if t.kind is not TokenKind.WORD:
                continue
            for s in t.signs:
                freq[s] += 1
                if inv is not None and inv.by_label(s) is None:
                    out_of_inv_occurrences += 1
                    out_of_inv_labels.add(s)
                    if len(out_of_inv_examples) < _EXAMPLE_CAP:
                        out_of_inv_examples.append((d.id, t.text, s))
    hapax = sorted(s for s, c in freq.items() if c == 1)
    return SignProfile(
        applicable=True,
        computed=True,
        note=("" if inv is not None else "corpus carries no sign inventory"),
        distinct_signs=len(freq),
        hapax_count=len(hapax),
        hapax_examples=tuple(hapax[:_EXAMPLE_CAP]),
        out_of_inventory_occurrences=out_of_inv_occurrences,
        out_of_inventory_distinct=len(out_of_inv_labels),
        out_of_inventory_examples=tuple(out_of_inv_examples),
    )
