"""Accounting reconciliation over real and synthetic documents."""

import aegean
from aegean.analysis import balance_check
from aegean.core.model import Document
from aegean.scripts.lineara.loader import classify


def _doc(raw_lines: list[list[str]]) -> Document:
    tokens = []
    lines = []
    pos = 0
    for li, line in enumerate(raw_lines):
        idx = []
        for w in line:
            tokens.append(classify(w, li, pos))
            idx.append(pos)
            pos += 1
        lines.append(idx)
    return Document(id="X", script_id="lineara", tokens=tokens, lines=lines)


def test_synthetic_balance():
    checks = balance_check(_doc([["GRA", "10"], ["VIN", "5"], ["KU-RO", "15"]]))
    assert len(checks) == 1
    assert checks[0].balances and checks[0].computed_sum == 15

    disc = balance_check(_doc([["GRA", "10"], ["KU-RO", "12"]]))
    assert not disc[0].balances and disc[0].difference == -2


def test_real_corpus_has_reconcilable_tablets():
    c = aegean.load("lineara")
    total_checks = 0
    balanced = 0
    for d in c:
        for ch in balance_check(d):
            total_checks += 1
            assert ch.marker in ("KU-RO", "PO-TO-KU-RO")
            if ch.balances:
                balanced += 1
    # The real corpus contains many KU-RO tablets, and some genuinely balance.
    assert total_checks > 0
    assert balanced > 0
