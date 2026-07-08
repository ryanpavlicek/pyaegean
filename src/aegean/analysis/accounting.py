"""Accounting reconciliation over a Document (the KU-RO / PO-TO-KU-RO check).

Exploratory: section boundaries are heuristic and the metrology is contested —
a "balance" is evidence to weigh, not ground truth.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..core.model import Document, ReadingStatus
from ..core.numerals import BalanceCheck, check_balances, markers_for, parse_account_lines


def account_lines(document: Document) -> list[list[str]]:
    """The document's physical lines as token-text lists."""
    return [[document.tokens[i].text for i in line] for line in document.lines]


def balance_check(document: Document) -> list[BalanceCheck]:
    """Verify every total line on a document against its summed item lines.

    Uses the script's total markers (Linear A's KU-RO/KU-RA and PO-TO-KU-RO, Linear B's
    TO-SO/TO-SA/TO-SO-DE)."""
    markers = markers_for(document.script_id)
    return check_balances(parse_account_lines(account_lines(document), markers), markers)


def is_checkable_account(document: Document, *, tolerance: float = 0.10) -> bool:
    """Whether a document is an *intact, balancing* account — a clean drill /
    teaching candidate, and a useful "trust the arithmetic" corpus filter.

    Intact = every token is securely read (``ReadingStatus.CERTAIN``, no bracketed
    restoration in the text), so no lacuna or damage muddies the sum. Balancing =
    at least one stated total (e.g. KU-RO) sits within ``max(1, tolerance ×
    stated)`` of its summed items — the workbench's Scribe-School cutoff, lenient
    by default (10%) because Aegean metrology is imperfectly understood."""
    for t in document.tokens:
        if t.status is not ReadingStatus.CERTAIN or "[" in t.text or "]" in t.text:
            return False
    return any(
        abs(ch.difference) <= max(1.0, tolerance * abs(ch.stated_total))
        for ch in balance_check(document)
    )


def checkable_accounts(corpus: Any, *, tolerance: float = 0.10) -> list[Document]:
    """The intact, balancing accounts of a corpus (see :func:`is_checkable_account`)."""
    docs: Iterable[Document] = getattr(corpus, "documents", corpus)
    return [d for d in docs if is_checkable_account(d, tolerance=tolerance)]
