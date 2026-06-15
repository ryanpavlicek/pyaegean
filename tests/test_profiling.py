"""Corpus profiling: document types, account dossiers, metrology (analysis.profiling).

Ported from the workbench's Document Types, Account Dossiers, and Metrology Lab
modules; anchors are the worked examples extracted from that source.
"""

from __future__ import annotations

import pytest

from aegean.analysis.profiling import (
    account_dossiers,
    document_type_profile,
    metrology_profile,
)
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.core.numerals import parse_value


def _doc(
    lines: list[list[str]], *, doc_id: str = "t", support: str = "", site: str = ""
) -> Document:
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
        id=doc_id, script_id="lineara", tokens=tokens, lines=line_idx,
        meta=DocumentMeta(support=support, site=site),
    )


class TestDocumentTypeProfile:
    def test_worked_example(self) -> None:
        rows = {
            r.type: r
            for r in document_type_profile(
                [
                    _doc([["KU-RO", "SU-KI-RI-TA", "100", "𐄁", "GRA"]], doc_id="D1", support="Tablet", site="HT"),
                    _doc([["DA-RE", "2", "½"]], doc_id="D2", support="tablet", site="HT"),
                    _doc([["A-DU"]], doc_id="D3", support="Nodule", site="ZA"),
                    _doc([["𐄁", "𐄁"]], doc_id="D4", support="", site="KH"),
                ]
            )
        }
        tablet = rows["Tablet"]  # "tablet" folds into "Tablet"
        assert tablet.count == 2
        assert tablet.words_per_doc == pytest.approx(1.5)
        assert tablet.numerals_pct == pytest.approx(100.0)  # both have a numeral
        assert tablet.share_pct == pytest.approx(50.0)
        assert tablet.top_sites == ["HT"]
        unrec = rows["(unrecorded)"]  # empty support
        assert unrec.count == 1
        assert unrec.words_per_doc == 0.0  # only separator tokens
        assert unrec.numerals_pct == 0.0  # the 𐄁 separator is not a numeral

    def test_sorted_by_count_desc(self) -> None:
        rows = document_type_profile(
            [_doc([["A-B"]], support="Tablet"), _doc([["C-D"]], support="Tablet"), _doc([["E-F"]], support="Nodule")]
        )
        assert [r.type for r in rows] == ["Tablet", "Nodule"]


class TestAccountDossiers:
    def test_worked_example(self) -> None:
        ds = account_dossiers(
            [
                _doc(
                    [["A-DU", "GRA", "30"], ["DA-RE", "VIN", "5", "¾"], ["KU-RO", "35"]],
                    doc_id="HT1", site="Haghia Triada",
                ),
                _doc(
                    [["A-DU", "10", "¼", "OLE"], ["GRA", "A-DU", "7"]],
                    doc_id="HT2", site="Haghia Triada",
                ),
            ]
        )
        assert [d.word for d in ds] == ["A-DU", "DA-RE"]  # entry-count desc
        adu = ds[0]
        assert adu.entry_count == 3
        assert adu.tablet_count == 2
        assert adu.total_value == pytest.approx(47.25)
        assert adu.commodities == {"GRA": 1, "OLE": 1}
        assert adu.co_listed == {"DA-RE": 1}
        # KU-RO heads its line but is a total marker -> excluded, never a dossier
        assert all(d.word != "KU-RO" for d in ds)

    def test_requires_numeral_after_head(self) -> None:
        # a lexical head with no following numeral is not a counted ledger line
        assert account_dossiers([_doc([["A-DU", "GRA"]])]) == []


class TestMetrologyProfile:
    def test_worked_example(self) -> None:
        mp = metrology_profile(
            [
                _doc([["OLE", "5", "¾"], ["OLE", "¼"], ["OLE", "2", "½"], ["OVIS", "30"]], doc_id="HT1"),
                _doc([["OVIS", "12"], ["VIR", "½"]], doc_id="HT2"),
            ]
        )
        assert (mp.numeral_tokens, mp.fraction_tokens, mp.integer_tokens) == (8, 4, 4)
        assert mp.distinct_fraction_values == 3
        assert [(r.display, r.count) for r in mp.fraction_rows] == [("1/2", 2), ("3/4", 1), ("1/4", 1)]
        # OVIS (2 entries) and VIR (1) are below the 3-entry threshold
        assert [c.head for c in mp.commodity_profiles] == ["OLE"]
        ole = mp.commodity_profiles[0]
        assert ole.gloss == "olive oil"
        assert ole.entries == 3
        assert ole.fractional_pct == pytest.approx(100.0)
        assert ole.denominators == "2 4"
        assert ole.median == pytest.approx(2.5)
        assert ole.max == pytest.approx(5.75)
