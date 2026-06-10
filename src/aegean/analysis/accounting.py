"""Accounting reconciliation over a Document (the KU-RO / PO-TO-KU-RO check).

Exploratory: section boundaries are heuristic and the metrology is contested —
a "balance" is evidence to weigh, not ground truth.
"""

from __future__ import annotations

from ..core.model import Document
from ..core.numerals import BalanceCheck, check_balances, markers_for, parse_account_lines


def account_lines(document: Document) -> list[list[str]]:
    """The document's physical lines as token-text lists."""
    return [[document.tokens[i].text for i in line] for line in document.lines]


def balance_check(document: Document) -> list[BalanceCheck]:
    """Verify every total line on a document against its summed item lines.

    Uses the script's total markers (Linear A's KU-RO, Linear B's TO-SO/TO-SA)."""
    markers = markers_for(document.script_id)
    return check_balances(parse_account_lines(account_lines(document), markers), markers)
