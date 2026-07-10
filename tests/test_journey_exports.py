"""End-to-end export journeys: what survives each interchange format, verified by re-reading.

Four journeys, each asserting actual round-tripped values:

1. Tabular (CSV/Parquet) token-level export carries the per-token editorial ``status``
   column and spreads ``Token.annotations`` (e.g. lemma) into columns.
2. EpiDoc round-trips token text and `ReadingStatus` exactly, and — per the documented
   `to_epidoc` contract — drops ``Token.annotations``; a silent contract change fails here.
3. The workbench schema carries token text only: on re-import every token is CERTAIN and
   unannotated (the documented `to_workbench` flattening), and `from_workbench_export`'s
   ``script_id`` kwarg labels the corpus (default stays ``lineara``).
4. The CLI ``export`` of a filtered corpus re-reads to exactly the filtered subset,
   for both CSV (token level) and EpiDoc.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

import aegean
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind
from aegean.io import from_epidoc, from_workbench_export, to_csv, to_parquet, to_workbench, write_epidoc


# ── fixtures ──────────────────────────────────────────────────────────────────
def _greek_status_corpus() -> Corpus:
    """One Greek document, three WORD tokens spanning three reading statuses, each with a lemma."""
    toks = [
        Token("λόγος", TokenKind.WORD, line_no=0, position=0,
              status=ReadingStatus.CERTAIN, annotations={"lemma": "λόγος"}),
        Token("θεοῦ", TokenKind.WORD, line_no=0, position=1,
              status=ReadingStatus.UNCLEAR, annotations={"lemma": "θεός"}),
        Token("ἦν", TokenKind.WORD, line_no=0, position=2,
              status=ReadingStatus.RESTORED, annotations={"lemma": "εἰμί"}),
    ]
    doc = Document(id="G1", script_id="greek", tokens=toks, lines=[[0, 1, 2]],
                   meta=DocumentMeta(site="Athens", name="G1"))
    return Corpus([doc], script_id="greek")


def _lineara_annotated_corpus() -> Corpus:
    """A Linear A document whose tokens carry statuses + annotations the workbench can't hold."""
    toks = [
        Token("KU-RO", TokenKind.WORD, ("KU", "RO"), line_no=0, position=0,
              status=ReadingStatus.CERTAIN, annotations={"note": "total marker"}),
        Token("DA-RO", TokenKind.WORD, ("DA", "RO"), line_no=0, position=1,
              status=ReadingStatus.RESTORED, annotations={"note": "supplied"}),
        Token("PA-RO", TokenKind.WORD, ("PA", "RO"), line_no=0, position=2,
              status=ReadingStatus.UNCLEAR, annotations={"note": "damaged"}),
    ]
    doc = Document(id="HT X 1", script_id="lineara", tokens=toks, lines=[[0, 1, 2]],
                   meta=DocumentMeta(site="Haghia Triada"))
    return Corpus([doc], script_id="lineara")


@pytest.fixture(scope="module")
def cli_app():  # type: ignore[no-untyped-def]
    pytest.importorskip("typer")
    from aegean.cli import _build_app

    return _build_app()


# ── journey 1: epigraphy status survives tabular export ───────────────────────
def test_csv_token_export_carries_status_and_annotations(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    out = tmp_path / "tokens.csv"
    to_csv(_greek_status_corpus(), out, level="token")

    with open(out, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames is not None and "status" in reader.fieldnames
        rows = list(reader)

    # row-aligned: the status and lemma columns line up with the text column
    assert [r["text"] for r in rows] == ["λόγος", "θεοῦ", "ἦν"]
    assert [r["status"] for r in rows] == ["certain", "unclear", "restored"]
    assert [r["lemma"] for r in rows] == ["λόγος", "θεός", "εἰμί"]


def test_parquet_token_export_carries_status_and_annotations(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    pd = pytest.importorskip("pandas")
    out = tmp_path / "tokens.parquet"
    to_parquet(_greek_status_corpus(), out, level="token")

    df = pd.read_parquet(out)
    assert list(df["text"]) == ["λόγος", "θεοῦ", "ἦν"]
    assert list(df["status"]) == ["certain", "unclear", "restored"]
    assert list(df["lemma"]) == ["λόγος", "θεός", "εἰμί"]


# ── journey 2: the EpiDoc contract, pinned ─────────────────────────────────────
def test_epidoc_roundtrip_keeps_text_and_status_drops_annotations(tmp_path: Path) -> None:
    """Text + ReadingStatus survive write→read exactly; annotations do NOT (documented loss).

    `to_epidoc` documents that ``Token.annotations`` (lemma, morphology, evidence class,
    review stamps) are not serialized — EpiDoc carries the edition text and apparatus, not
    an analysis layer. This test pins both halves of that contract: if annotations ever
    start (or stop) surviving silently, it fails."""
    toks = [
        Token("μῆνιν", TokenKind.WORD, line_no=0, position=0,
              status=ReadingStatus.CERTAIN,
              annotations={"lemma": "μῆνις", "upos": "NOUN",
                           "lemma_source": "attested", "review_status": "accepted"}),
        Token("ἄειδε", TokenKind.WORD, line_no=0, position=1,
              status=ReadingStatus.UNCLEAR,
              annotations={"lemma": "ἀείδω", "upos": "VERB",
                           "lemma_source": "neural", "review_status": "pending"}),
    ]
    doc = Document(id="IL1", script_id="greek", tokens=toks, lines=[[0, 1]],
                   meta=DocumentMeta(name="Iliad 1.1"))
    out = tmp_path / "epidoc"
    write_epidoc(Corpus([doc], script_id="greek"), out)

    back = from_epidoc(out, script_id="greek")
    assert [d.id for d in back] == ["IL1"]
    back_toks = back.documents[0].tokens
    # texts and per-token statuses survive exactly (UNCLEAR stays UNCLEAR)
    assert [t.text for t in back_toks] == ["μῆνιν", "ἄειδε"]
    assert [t.status for t in back_toks] == [ReadingStatus.CERTAIN, ReadingStatus.UNCLEAR]
    # the documented loss: annotations come back empty for every token
    assert all(not t.annotations for t in back_toks)


# ── journey 3: the workbench contract, pinned ──────────────────────────────────
def test_workbench_roundtrip_flattens_status_and_drops_annotations() -> None:
    """Texts survive the to_workbench → from_workbench_export round trip; statuses flatten
    to CERTAIN and annotations vanish (the documented workbench-schema loss)."""
    back = from_workbench_export(to_workbench(_lineara_annotated_corpus()))

    doc = back.get("HT X 1")
    assert doc is not None
    assert [t.text for t in doc.tokens] == ["KU-RO", "DA-RO", "PA-RO"]
    # the export carries token text only: RESTORED and UNCLEAR both re-import as CERTAIN
    assert [t.status for t in doc.tokens] == [ReadingStatus.CERTAIN] * 3
    assert all(not t.annotations for t in doc.tokens)


def test_from_workbench_export_script_id_kwarg() -> None:
    records = to_workbench(_lineara_annotated_corpus())

    relabeled = from_workbench_export(records, script_id="greek")
    assert relabeled.script_id == "greek"
    assert all(d.script_id == "greek" for d in relabeled)  # documents are not rebranded lineara

    assert from_workbench_export(records).script_id == "lineara"  # the default is unchanged


# ── journey 4: CLI export of a filtered subset re-reads to that subset ─────────
def test_cli_csv_export_matches_filtered_subset(cli_app, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("pandas")
    from typer.testing import CliRunner

    out = tmp_path / "out.csv"
    res = CliRunner().invoke(
        cli_app,
        ["export", "lineara", "--site", "Zakros", "-f", "csv", "-o", str(out),
         "--level", "token"],
    )
    assert res.exit_code == 0, res.output

    with open(out, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames is not None and "status" in reader.fieldnames
        rows = list(reader)

    subset = aegean.load("lineara").filter(site="Zakros")
    # one CSV row per token, in corpus order, carrying the real per-token status;
    # a token-less fragment contributes no rows, so compare token-bearing docs
    expected = [(d.id, t.text, t.status.value) for d in subset.documents for t in d.tokens]
    assert [(r["doc_id"], r["text"], r["status"]) for r in rows] == expected
    assert {r["doc_id"] for r in rows} == {d.id for d in subset.documents if d.tokens}
    # the status column is meaningful on this subset (it has non-certain readings)
    assert {r["status"] for r in rows} == {t.status.value for d in subset for t in d.tokens}
    assert len({r["status"] for r in rows}) > 1


def test_cli_epidoc_export_reimports_to_the_subset(cli_app, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    outdir = tmp_path / "epi"
    res = CliRunner().invoke(
        cli_app,
        ["export", "lineara", "--site", "Zakros", "-f", "epidoc", "-o", str(outdir)],
    )
    assert res.exit_code == 0, res.output

    back = from_epidoc(outdir, script_id="lineara")
    subset = aegean.load("lineara").filter(site="Zakros")
    assert sorted(d.id for d in back) == sorted(d.id for d in subset)

    # sample the token-richest document: its token texts survive in order
    sample = max(subset.documents, key=lambda d: len(d.tokens))
    back_doc = back.get(sample.id)
    assert back_doc is not None
    assert [t.text for t in back_doc.tokens] == [t.text for t in sample.tokens]
