"""Jupyter ``_repr_html_`` rendering for the headline value objects.

These check that each object renders a non-empty HTML string with the expected
content, and — importantly — that every interpolated value is escaped, so
corpus- or user-derived text can never inject markup into a notebook.
"""

from __future__ import annotations

import aegean
from aegean import greek
from aegean.ai.client import ExploratoryResult
from aegean.core.model import Document, Sign, SignInventory, Token, TokenKind


def test_corpus_repr_html() -> None:
    corpus = aegean.load("lineara")
    html = corpus._repr_html_()
    assert "<table" in html
    assert "documents" in html
    assert "lineara" in html


def test_document_repr_html() -> None:
    doc = aegean.load("lineara").get("HT13")
    assert doc is not None
    html = doc._repr_html_()
    assert "HT13" in html
    assert "KU-RO" in html
    assert "words" in html


def test_sign_inventory_repr_html() -> None:
    inv = aegean.get_script("lineara").sign_inventory
    html = inv._repr_html_()
    assert "<table" in html
    assert "inventory" in html
    assert "KU" in html


def test_line_scansion_repr_html() -> None:
    sc = greek.scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ")
    html = sc._repr_html_()
    assert "hexameter" in html
    assert sc.pattern in html
    assert "dactyl" in html


def test_analysis_repr_html() -> None:
    a = greek.analyze("λόγον")[0]
    html = a._repr_html_()
    assert "λόγος" in html
    assert "acc" in html
    # An out-of-vocabulary, reconstructed lemma is flagged in the rendering.
    oov = [x for x in greek.analyze("ἵππον") if x.pos == "NOUN"][0]
    assert not oov.lemma_certain
    assert "reconstructed" in oov._repr_html_()


def test_exploratory_result_repr_html() -> None:
    r = ExploratoryResult(
        text="a tentative reading",
        kind="decipher",
        provider="anthropic",
        model="claude",
        prompt_version="1",
        grounding=("KU-RO → total",),
    )
    html = r._repr_html_()
    assert "EXPLORATORY" in html
    assert "a tentative reading" in html
    assert "KU-RO" in html  # grounding listed


def test_repr_html_escapes_untrusted_text() -> None:
    # Document id and token text are escaped — no raw markup leaks through.
    doc = Document(
        id="<x>",
        script_id="t",
        tokens=[Token(text="<script>alert(1)</script>", kind=TokenKind.WORD)],
        lines=[[0]],
    )
    html = doc._repr_html_()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;x&gt;" in html

    # SignInventory escapes a hostile label too.
    inv = SignInventory([Sign(label="<b>x</b>")], script_id="t")
    inv_html = inv._repr_html_()
    assert "<b>x</b>" not in inv_html
    assert "&lt;b&gt;x&lt;/b&gt;" in inv_html
