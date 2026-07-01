"""Linear B accounting markers: case-insensitive matching + the to-so-de total.

The on-demand DAMOS corpus transliterates in lowercase (to-so, o-pe-ro) while the
canonical marker sets are uppercase; exact-match comparison found zero totals across
the whole corpus and leaked the markers into account_dossiers as "holders". These
tests pin the case-folded matching, the to-so-de total formula, and that Linear A
KU-RO behavior is untouched.
"""

from __future__ import annotations

from aegean.analysis import account_dossiers, balance_check
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.core.numerals import (
    LINEAR_A_MARKERS,
    LINEAR_B_MARKERS,
    check_balances,
    markers_for,
    parse_account_lines,
    parse_value,
)


def _doc(lines: list[list[str]], *, script_id: str, doc_id: str = "t", site: str = "") -> Document:
    tokens: list[Token] = []
    line_idx: list[list[int]] = []
    for line in lines:
        idxs: list[int] = []
        for tx in line:
            kind = TokenKind.NUMERAL if parse_value(tx) is not None else TokenKind.WORD
            idxs.append(len(tokens))
            tokens.append(Token(text=tx, kind=kind))
        line_idx.append(idxs)
    return Document(
        id=doc_id, script_id=script_id, tokens=tokens, lines=line_idx,
        meta=DocumentMeta(support="Tablet", site=site),
    )


class TestMarkerCaseFolding:
    def test_lowercase_to_so_is_a_total(self) -> None:
        # DAMOS-style lowercase transliteration
        lines = parse_account_lines(
            [["te-ra", "GRA", "10"], ["po-ti", "GRA", "5"], ["to-so", "GRA", "15"]],
            LINEAR_B_MARKERS,
        )
        assert [line.role for line in lines] == ["item", "item", "total"]
        checks = check_balances(lines, LINEAR_B_MARKERS)
        assert len(checks) == 1
        assert checks[0].balances
        assert checks[0].computed_sum == 15
        assert checks[0].stated_total == 15
        assert checks[0].marker == "to-so"  # reported as written on the tablet

    def test_lowercase_o_pe_ro_is_a_deficit(self) -> None:
        # the deficit line is excluded from the section sum
        lines = parse_account_lines(
            [["ko-wa", "10"], ["o-pe-ro", "3"], ["to-so", "10"]], LINEAR_B_MARKERS
        )
        assert [line.role for line in lines] == ["item", "deficit", "total"]
        checks = check_balances(lines, LINEAR_B_MARKERS)
        assert checks[0].balances and checks[0].computed_sum == 10

    def test_uppercase_still_matches(self) -> None:
        lines = parse_account_lines([["VIR", "7"], ["TO-SO", "7"]], LINEAR_B_MARKERS)
        assert lines[1].role == "total"

    def test_to_so_jo_is_not_a_total(self) -> None:
        # exact lexeme match only: the genitive TO-SO-JO is not a total formula
        lines = parse_account_lines([["TO-SO-JO", "5"]], LINEAR_B_MARKERS)
        assert lines[0].role == "item"
        assert not LINEAR_B_MARKERS.is_marker("to-so-jo")

    def test_markers_methods(self) -> None:
        assert LINEAR_B_MARKERS.is_total("to-so")
        assert LINEAR_B_MARKERS.is_total("TO-SA")
        assert LINEAR_B_MARKERS.is_deficit("o-pe-ro-si")
        assert not LINEAR_B_MARKERS.is_grand_total("to-so")
        assert LINEAR_A_MARKERS.is_total("ku-ro")
        assert LINEAR_A_MARKERS.is_grand_total("po-to-ku-ro")
        assert not LINEAR_A_MARKERS.is_marker("su-ki-ri-ta")


class TestToSoDe:
    def test_to_so_de_is_a_total(self) -> None:
        # the "and so much" variant total formula, 143 tokens in DAMOS
        assert "TO-SO-DE" in LINEAR_B_MARKERS.total
        lines = parse_account_lines(
            [["ko-wo", "4"], ["ko-wa", "2"], ["to-so-de", "6"]], LINEAR_B_MARKERS
        )
        assert lines[2].role == "total"
        checks = check_balances(lines, LINEAR_B_MARKERS)
        assert checks[0].balances and checks[0].marker == "to-so-de"


class TestBalanceCheckRouting:
    def test_linearb_document_end_to_end(self) -> None:
        doc = _doc(
            [["da-mo", "GRA", "12"], ["pa-ro", "GRA", "8"], ["to-so", "GRA", "20"]],
            script_id="linearb", doc_id="KN Xx 1",
        )
        checks = balance_check(doc)
        assert len(checks) == 1
        assert checks[0].balances
        assert checks[0].item_count == 2
        assert checks[0].marker == "to-so"

    def test_lineara_ku_ro_unchanged(self) -> None:
        # the Linear A path (bundled golden behavior) is unaffected
        doc = _doc(
            [["A-DU", "GRA", "30"], ["DA-RE", "VIN", "5"], ["KU-RO", "35"]],
            script_id="lineara", doc_id="HT 1",
        )
        checks = balance_check(doc)
        assert len(checks) == 1
        assert checks[0].balances and checks[0].marker == "KU-RO"

    def test_markers_for_linearb_totals(self) -> None:
        assert markers_for("linearb").total == frozenset({"TO-SO", "TO-SA", "TO-SO-DE"})


class TestDossierExclusion:
    def test_lowercase_markers_never_dossiers(self) -> None:
        # every marker heads a counted line; none may surface as an account holder
        doc = _doc(
            [
                ["e-ko-to", "VIR", "3"],
                ["to-so", "VIR", "3"],
                ["to-sa", "GRA", "2"],
                ["to-so-de", "GRA", "5"],
                ["o-pe-ro", "GRA", "1"],
            ],
            script_id="linearb", doc_id="KN Xx 2", site="Knossos",
        )
        ds = account_dossiers([doc])
        assert [d.word for d in ds] == ["e-ko-to"]
        assert ds[0].entry_count == 1
        assert ds[0].total_value == 3
