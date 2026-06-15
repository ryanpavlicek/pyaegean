"""The intact, balancing-account drill filter (analysis.accounting).

Ports the workbench Scribe-School eligibility rule: an account is a clean drill
candidate iff it is intact (no damaged/restored tokens) and a stated total
balances its items within max(1, 10%)."""

from __future__ import annotations

from aegean.analysis.accounting import checkable_accounts, is_checkable_account
from aegean.core.model import Document, ReadingStatus, Token, TokenKind


def _doc(
    lines: list[list[str]], *, doc_id: str = "t", status: ReadingStatus = ReadingStatus.CERTAIN
) -> Document:
    tokens: list[Token] = []
    line_idx: list[list[int]] = []
    for line in lines:
        idxs: list[int] = []
        for tx in line:
            kind = TokenKind.NUMERAL if tx.replace(".", "").isdigit() else TokenKind.WORD
            idxs.append(len(tokens))
            tokens.append(Token(text=tx, kind=kind, status=status))
        line_idx.append(idxs)
    return Document(id=doc_id, script_id="lineara", tokens=tokens, lines=line_idx)


_BALANCING = [["A-B", "2"], ["C-D", "3"], ["KU-RO", "5"]]


def test_intact_balancing_account_is_checkable() -> None:
    assert is_checkable_account(_doc(_BALANCING)) is True


def test_within_tolerance_is_checkable() -> None:
    # items 5 vs KU-RO 6: |diff| 1 <= max(1, 0.6) -> eligible
    assert is_checkable_account(_doc([["A-B", "2"], ["C-D", "3"], ["KU-RO", "6"]])) is True


def test_off_balance_beyond_tolerance_rejected() -> None:
    # items 5 vs KU-RO 10: |diff| 5 > max(1, 1.0) -> not eligible
    assert is_checkable_account(_doc([["A-B", "2"], ["C-D", "3"], ["KU-RO", "10"]])) is False


def test_bracketed_token_rejected() -> None:
    # balances, but a restored/bracketed token makes it not intact
    assert is_checkable_account(_doc([["[A-B]", "2"], ["C-D", "3"], ["KU-RO", "5"]])) is False


def test_non_certain_status_rejected() -> None:
    assert is_checkable_account(_doc(_BALANCING, status=ReadingStatus.RESTORED)) is False


def test_no_total_rejected() -> None:
    assert is_checkable_account(_doc([["A-B", "2"], ["C-D", "3"]])) is False


def test_checkable_accounts_filters_a_corpus() -> None:
    docs = [
        _doc(_BALANCING, doc_id="good"),
        _doc([["A-B", "2"], ["C-D", "3"], ["KU-RO", "10"]], doc_id="off"),
        _doc(_BALANCING, doc_id="damaged", status=ReadingStatus.UNCLEAR),
    ]
    out = checkable_accounts(docs)
    assert [d.id for d in out] == ["good"]
