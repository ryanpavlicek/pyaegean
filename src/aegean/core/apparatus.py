"""A uniform editorial-apparatus surface across corpora.

Every bundled or fetched corpus decodes its edition's apparatus into the same
`ReadingStatus` vocabulary (the Cypriot IG XV 1 Leiden underdots/brackets, the
Linear A GORILA erased-sign and bracket marks, the SigLA doubtful-reading and
break marks) and into `Token.alt` (alternate readings, e.g. Linear B EpiDoc
``<app>/<rdg>`` variants). This module reads those two channels back out in one
shape, so a caller does not have to know which loader produced a corpus:

* `alt_readings(doc_or_corpus)` — every token that carries alternate readings, as
  a flat list of `AltReading` records.
* `apparatus_summary(corpus)` — the per-corpus apparatus profile (status counts,
  documents carrying non-CERTAIN text, alternate-reading counts, and a legend of
  the apparatus that occurs) as an `ApparatusSummary`. It is deliberately a
  superset of `diagnose`'s ``StatusProfile`` so ``corpus.diagnose()`` can consume
  it directly (see the module note at the bottom for the integration point).

Zero-dependency: only the stdlib and the core value objects. Import stays instant.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .model import ReadingStatus, TokenKind

if TYPE_CHECKING:  # type-only, to keep the core import-clean and cycle-free
    from .corpus import Corpus
    from .model import Document, Token

__all__ = [
    "AltReading",
    "ApparatusSummary",
    "alt_readings",
    "apparatus_summary",
]

# How many alternate-reading examples an ApparatusSummary keeps inline.
_EXAMPLE_CAP = 10

# A plain-language legend for each non-default `ReadingStatus`, in the same terms
# the model docstring and wiki/Limitations use. Only the statuses that actually
# occur in a corpus are surfaced, so the notes describe that corpus, not a guess.
_STATUS_LEGEND: dict[ReadingStatus, str] = {
    ReadingStatus.UNCLEAR: "unclear: damaged but read (Leiden underdot; EpiDoc <unclear>)",
    ReadingStatus.RESTORED: "restored: editorially supplied (Leiden [ ]; EpiDoc <supplied>)",
    ReadingStatus.LOST: "lost: not preserved (Leiden [---]; EpiDoc <gap>)",
}


@dataclass(frozen=True)
class AltReading:
    """One token that carries alternate readings, in a corpus-independent shape.

    ``text`` is the editor-preferred reading (the ``<lem>``); ``alternates`` are
    the variant ``<rdg>`` readings the apparatus records for the same slot."""

    doc_id: str
    position: int | None
    text: str
    kind: str            # `TokenKind` value, e.g. "word" / "logogram"
    status: str          # `ReadingStatus` value, e.g. "certain" / "unclear"
    alternates: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "position": self.position,
            "text": self.text,
            "kind": self.kind,
            "status": self.status,
            "alternates": list(self.alternates),
        }


@dataclass(frozen=True)
class ApparatusSummary:
    """The editorial-apparatus profile of one corpus.

    A superset of `aegean.core.diagnose`'s ``StatusProfile``: the same reading-status
    counts and apparatus-document count, plus the alternate-reading tally and a
    legend of the apparatus that occurs. Built by `apparatus_summary`."""

    script_id: str
    source: str
    n_documents: int
    n_tokens: int
    certain: int
    unclear: int
    restored: int
    lost: int
    documents_with_apparatus: int
    alt_reading_tokens: int
    alt_reading_examples: tuple[AltReading, ...]
    marker_notes: tuple[str, ...]

    @property
    def non_certain(self) -> int:
        """Tokens whose reading is not securely CERTAIN (unclear + restored + lost)."""
        return self.unclear + self.restored + self.lost

    @property
    def status_counts(self) -> dict[str, int]:
        """The four `ReadingStatus` counts keyed by their value."""
        return {
            "certain": self.certain,
            "unclear": self.unclear,
            "restored": self.restored,
            "lost": self.lost,
        }

    def to_dict(self) -> dict[str, Any]:
        """A JSON-serializable summary that round-trips through ``json.dumps``/``loads``."""
        return {
            "script_id": self.script_id,
            "source": self.source,
            "documents": self.n_documents,
            "tokens": self.n_tokens,
            "status_counts": self.status_counts,
            "non_certain": self.non_certain,
            "documents_with_apparatus": self.documents_with_apparatus,
            "alt_reading_tokens": self.alt_reading_tokens,
            "alt_reading_examples": [a.to_dict() for a in self.alt_reading_examples],
            "marker_notes": list(self.marker_notes),
        }


def _iter_documents(obj: "Corpus | Document | Any") -> list["Document"]:
    """The documents of a `Corpus`, a single `Document`, or an iterable of documents.

    A clean `TypeError` on anything else (never a raw AttributeError deep inside)."""
    docs = getattr(obj, "documents", None)
    if docs is not None:                       # a Corpus (or Corpus-like)
        return list(docs)
    if hasattr(obj, "tokens") and hasattr(obj, "id"):  # a single Document
        return [obj]  # type: ignore[list-item]
    try:
        items = list(obj)
    except TypeError:
        raise TypeError(
            "alt_readings/apparatus_summary expect a Corpus, a Document, "
            f"or an iterable of Documents; got {type(obj).__name__}"
        ) from None
    for d in items:
        if not (hasattr(d, "tokens") and hasattr(d, "id")):
            raise TypeError(
                "iterable passed to alt_readings/apparatus_summary must yield "
                f"Documents; got a {type(d).__name__}"
            )
    return items


def alt_readings(doc_or_corpus: "Corpus | Document | Any") -> list[AltReading]:
    """Every token carrying alternate readings (`Token.alt`), in one uniform shape.

    Accepts a `Corpus`, a single `Document`, or an iterable of documents. Tokens
    without alternates are skipped, so the result is exactly the apparatus of
    variant readings across the input, in document then token order. Works
    identically whatever loaded the corpus: Linear B EpiDoc ``<app>/<rdg>``
    variants, a bring-your-own EpiDoc import, or `Corpus.from_records` with an
    ``"alt"`` key all populate `Token.alt` the same way."""
    docs = _iter_documents(doc_or_corpus)
    out: list[AltReading] = []
    for d in docs:
        toks: list[Token] = d.tokens
        for t in toks:
            if t.alt:
                out.append(
                    AltReading(
                        doc_id=d.id,
                        position=t.position,
                        text=t.text,
                        kind=t.kind.value,
                        status=t.status.value,
                        alternates=tuple(t.alt),
                    )
                )
    return out


def apparatus_summary(corpus: "Corpus | Any") -> ApparatusSummary:
    """The editorial-apparatus profile of ``corpus`` as an `ApparatusSummary`.

    One pass over the tokens: reading-status counts, how many documents carry any
    non-CERTAIN token, and the alternate-reading tally with a few inline examples.
    ``marker_notes`` legends only the apparatus that actually occurs (plus the
    provenance ``edition_fidelity`` when the corpus records one), so the summary
    describes this corpus rather than asserting apparatus it does not carry."""
    docs = _iter_documents(corpus)
    script_id = getattr(corpus, "script_id", "") or ""
    prov = getattr(corpus, "provenance", None)

    by_status: Counter[ReadingStatus] = Counter()
    n_tokens = 0
    docs_with_apparatus = 0
    alt_tokens = 0
    alt_examples: list[AltReading] = []
    for d in docs:
        has_apparatus = False
        for t in d.tokens:
            n_tokens += 1
            by_status[t.status] += 1
            if t.status is not ReadingStatus.CERTAIN:
                has_apparatus = True
            if t.alt:
                alt_tokens += 1
                if len(alt_examples) < _EXAMPLE_CAP:
                    alt_examples.append(
                        AltReading(
                            doc_id=d.id,
                            position=t.position,
                            text=t.text,
                            kind=t.kind.value if isinstance(t.kind, TokenKind) else str(t.kind),
                            status=t.status.value,
                            alternates=tuple(t.alt),
                        )
                    )
        if has_apparatus:
            docs_with_apparatus += 1

    notes: list[str] = []
    fidelity = getattr(prov, "edition_fidelity", "") if prov is not None else ""
    if fidelity:
        notes.append(f"edition fidelity: {fidelity}")
    for st in (ReadingStatus.UNCLEAR, ReadingStatus.RESTORED, ReadingStatus.LOST):
        if by_status.get(st):
            notes.append(_STATUS_LEGEND[st])
    if alt_tokens:
        notes.append(
            f"alt: {alt_tokens} token(s) carry alternate readings (EpiDoc <app>/<rdg>)"
        )

    return ApparatusSummary(
        script_id=script_id,
        source=(getattr(prov, "source", "") or "") if prov is not None else "",
        n_documents=len(docs),
        n_tokens=n_tokens,
        certain=by_status[ReadingStatus.CERTAIN],
        unclear=by_status[ReadingStatus.UNCLEAR],
        restored=by_status[ReadingStatus.RESTORED],
        lost=by_status[ReadingStatus.LOST],
        documents_with_apparatus=docs_with_apparatus,
        alt_reading_tokens=alt_tokens,
        alt_reading_examples=tuple(alt_examples),
        marker_notes=tuple(notes),
    )


# ── integration point for corpus.diagnose() (do LATER; not wired here) ───────────
# `aegean.core.diagnose.diagnose` currently computes its `StatusProfile` inline in
# its single token pass (diagnose.py, the ``by_status``/``docs_with_apparatus``
# loop, ~lines 403-436). To adopt this module it can, in that same pass or right
# after it, call ``summary = apparatus_summary(corpus)`` and:
#   * build ``StatusProfile`` from ``summary`` (certain/unclear/restored/lost,
#     documents_with_apparatus, total_tokens) — the fields line up one-to-one; and
#   * add an apparatus/alt-readings section to `DiagnoseReport` from
#     ``summary.alt_reading_tokens`` / ``summary.marker_notes``.
# `ApparatusSummary` is a strict superset of `StatusProfile`, so this is additive
# and no existing diagnose number changes. This module intentionally does NOT edit
# diagnose.py.
