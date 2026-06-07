"""Parity with the workbench numerals.ts golden values."""

from aegean.core.numerals import (
    check_balances,
    format_value,
    line_value,
    parse_account_lines,
    parse_value,
)


def test_parse_value():
    assert parse_value("197") == 197
    assert parse_value("¾") == 0.75
    assert parse_value("³⁄₄") == 0.75
    assert parse_value("3/4") == 0.75
    assert parse_value("5/0") is None
    assert parse_value("KU-RO") is None
    assert parse_value("") is None


def test_format_value():
    assert format_value(5) == "5"
    assert format_value(31.75) == "31¾"
    assert format_value(0.5) == "½"
    assert format_value(2.51) == "2.51"


def test_line_value():
    assert line_value(["5", "³⁄₄"]) == 5.75
    assert line_value(["GRA", "10", "VIN", "5"]) == 15
    assert line_value(["KU-RO"]) == 0


def test_account_roles():
    lines = parse_account_lines(
        [["GRA", "5"], ["KU-RO", "5"], ["KI-RO", "2"], ["PO-TO-KU-RO", "7"]]
    )
    assert [l.role for l in lines] == ["item", "total", "deficit", "grand-total"]


def test_balance_balanced_and_discrepant():
    bal = check_balances(parse_account_lines([["GRA", "10"], ["VIN", "5"], ["KU-RO", "15"]]))
    assert len(bal) == 1
    assert bal[0].balances and bal[0].computed_sum == 15 and bal[0].marker == "KU-RO"

    disc = check_balances(parse_account_lines([["GRA", "10"], ["KU-RO", "12"]]))
    assert not disc[0].balances and disc[0].difference == -2


def test_deficit_excluded_and_section_reset():
    bal = check_balances(parse_account_lines([["GRA", "10"], ["KI-RO", "3"], ["KU-RO", "10"]]))
    assert bal[0].balances and bal[0].computed_sum == 10

    secs = check_balances(
        parse_account_lines([["GRA", "4"], ["KU-RO", "4"], ["VINa", "9"], ["KU-RO", "9"]])
    )
    assert len(secs) == 2 and secs[0].computed_sum == 4 and secs[1].computed_sum == 9
