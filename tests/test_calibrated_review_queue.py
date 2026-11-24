"""Tests for calibrated-risk review prioritization, review budgets, and confidence persistence."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.greek.annotate import annotate_corpus
from aegean.io.review import apply_review_table, to_review_table


def _annotated_corpus_with_confidences() -> Corpus:
    docs = [
        Document(
            id="doc_a",
            script_id="greek",
            transcription="ἐν ἀρχῇ ἦν λόγος",
            tokens=[
                Token(
                    text="ἐν",
                    kind=TokenKind.WORD,
                    position=0,
                    line_no=1,
                    annotations={
                        "lemma": "ἐν",
                        "upos": "ADP",
                        "lemma_source": "neural_lookup",
                        "confidence_lemma": "0.990000",
                        "confidence_pos": "0.980000",
                        "analysis_generation": "gen-1",
                        "analysis_kind": "neural",
                        "analysis_configuration": "{}",
                        "analysis_receipt": "unknown",
                    },
                ),
                Token(
                    text="ἀρχῇ",
                    kind=TokenKind.WORD,
                    position=1,
                    line_no=1,
                    annotations={
                        "lemma": "ἀρχή",
                        "upos": "NOUN",
                        "lemma_source": "neural_edit",
                        "confidence_lemma": "0.420000",
                        "confidence_pos": "0.910000",
                        "analysis_generation": "gen-1",
                        "analysis_kind": "neural",
                        "analysis_configuration": "{}",
                        "analysis_receipt": "unknown",
                    },
                ),
                Token(
                    text="ἦν",
                    kind=TokenKind.WORD,
                    position=2,
                    line_no=1,
                    annotations={
                        "lemma": "εἰμί",
                        "upos": "AUX",
                        "lemma_source": "neural_lookup",
                        "confidence_lemma": "0.950000",
                        "confidence_pos": "0.350000",
                        "analysis_generation": "gen-1",
                        "analysis_kind": "neural",
                        "analysis_configuration": "{}",
                        "analysis_receipt": "unknown",
                    },
                ),
                Token(
                    text="λόγος",
                    kind=TokenKind.WORD,
                    position=3,
                    line_no=1,
                    annotations={
                        "lemma": "λόγος",
                        "upos": "NOUN",
                        "lemma_source": "identity",
                        "confidence_lemma": "0.180000",
                        "confidence_pos": "0.880000",
                        "analysis_generation": "gen-1",
                        "analysis_kind": "neural",
                        "analysis_configuration": "{}",
                        "analysis_receipt": "unknown",
                    },
                ),
            ],
            lines=[[0, 1, 2, 3]],
        ),
        Document(
            id="doc_b",
            script_id="greek",
            transcription="θεός",
            tokens=[
                Token(
                    text="θεός",
                    kind=TokenKind.WORD,
                    position=0,
                    line_no=1,
                    annotations={
                        "lemma": "θεός",
                        "upos": "NOUN",
                        "lemma_source": "neural_lookup",
                        "confidence_lemma_unavailable": "unsupported_source",
                        "analysis_generation": "gen-1",
                        "analysis_kind": "neural",
                        "analysis_configuration": "{}",
                        "analysis_receipt": "unknown",
                    },
                ),
            ],
            lines=[[0]],
        ),
    ]
    return Corpus(docs, script_id="greek")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_calibrated_risk_orders_lowest_confidence_first_and_respects_budget(tmp_path: Path) -> None:
    corpus = _annotated_corpus_with_confidences()
    full_csv = tmp_path / "queue_full.csv"
    n = to_review_table(corpus, full_csv, priority="calibrated_risk")
    assert n == 5

    rows = _read_csv(full_csv)
    assert [r["token"] for r in rows] == ["λόγος", "ἀρχῇ", "ἦν", "ἐν", "θεός"]
    assert "priority:calibrated_risk" in json.loads(rows[0]["inclusion_reasons"])
    assert "calibrated_confidence:0.180000" in json.loads(rows[0]["inclusion_reasons"])
    assert "calibrated_confidence:unavailable" in json.loads(rows[-1]["inclusion_reasons"])

    # Budget=2 caps to the 2 highest-risk tokens and round-trips through editable layout.
    ed_csv = tmp_path / "queue_top2.csv"
    n2 = to_review_table(
        corpus, ed_csv, layout="editable", priority="calibrated_risk", budget=2
    )
    assert n2 == 2
    ed_rows = _read_csv(ed_csv)
    assert [r["token"] for r in ed_rows] == ["λόγος", "ἀρχῇ"]

    # Reviewer edits the highest-risk token and applies cleanly.
    ed_rows[0]["decision_lemma"] = "correct"
    ed_rows[0]["correct_lemma"] = "Λόγος"
    ed_rows[0]["reviewer"] = "editor1"
    with ed_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(ed_rows[0].keys()))
        writer.writeheader()
        writer.writerows(ed_rows)

    applied = apply_review_table(ed_csv, corpus)
    assert applied.corpus.get("doc_a").tokens[3].annotations["lemma"] == "Λόγος"
    assert applied.corpus.get("doc_a").tokens[3].annotations["lemma_verified"] == "true"


def test_calibrated_risk_multifield_uses_minimum_confidence(tmp_path: Path) -> None:
    corpus = _annotated_corpus_with_confidences()
    out_csv = tmp_path / "multi.csv"
    to_review_table(
        corpus, out_csv, fields=("lemma", "pos"), priority="calibrated_risk", budget=3
    )
    rows = _read_csv(out_csv)
    # Min(lemma, pos): λόγος=0.18, ἦν=0.35 (from pos!), ἀρχῇ=0.42
    assert [r["token"] for r in rows] == ["λόγος", "ἦν", "ἀρχῇ"]


def test_calibrated_risk_dependency_sentences_preserve_internal_token_order(tmp_path: Path) -> None:
    doc = Document(
        id="doc_dep",
        script_id="greek",
        transcription="ὁ λόγος . ἐν ἀρχῇ .",
        tokens=[
            Token(
                text="ὁ", kind=TokenKind.WORD, position=0, line_no=1,
                annotations={
                    "lemma": "ὁ", "upos": "DET", "head": "2", "deprel": "det",
                    "dependency_sentence_id": "s1", "dependency_index": "1",
                    "confidence_lemma": "0.99", "confidence_head": "0.95", "confidence_deprel": "0.96",
                },
            ),
            Token(
                text="λόγος", kind=TokenKind.WORD, position=1, line_no=1,
                annotations={
                    "lemma": "λόγος", "upos": "NOUN", "head": "0", "deprel": "root",
                    "dependency_sentence_id": "s1", "dependency_index": "2",
                    "confidence_lemma": "0.92", "confidence_head": "0.90", "confidence_deprel": "0.94",
                },
            ),
            Token(
                text="ἐν", kind=TokenKind.WORD, position=2, line_no=2,
                annotations={
                    "lemma": "ἐν", "upos": "ADP", "head": "2", "deprel": "case",
                    "dependency_sentence_id": "s2", "dependency_index": "1",
                    "confidence_lemma": "0.98", "confidence_head": "0.97", "confidence_deprel": "0.98",
                },
            ),
            Token(
                text="ἀρχῇ", kind=TokenKind.WORD, position=3, line_no=2,
                annotations={
                    "lemma": "ἀρχή", "upos": "NOUN", "head": "0", "deprel": "root",
                    "dependency_sentence_id": "s2", "dependency_index": "2",
                    "confidence_lemma": "0.31", "confidence_head": "0.40", "confidence_deprel": "0.35",
                },
            ),
        ],
        lines=[[0, 1], [2, 3]],
    )
    corpus = Corpus([doc], script_id="greek")
    out_csv = tmp_path / "dep.csv"
    to_review_table(
        corpus,
        out_csv,
        fields=("lemma", "head", "deprel"),
        priority="calibrated_risk",
    )
    rows = _read_csv(out_csv)
    # Sentence s2 (min conf 0.31) comes before s1 (min conf 0.90), and s2 keeps natural order [ἐν, ἀρχῇ]!
    assert [r["token"] for r in rows] == ["ἐν", "ἀρχῇ", "ὁ", "λόγος"]


def test_calibrated_risk_adversarial_guards_and_stale_confidence_clearing(tmp_path: Path) -> None:
    # Corpus without calibrated confidences must fail cleanly.
    plain = Corpus(
        [
            Document(
                id="d1",
                script_id="greek",
                transcription="λόγος",
                tokens=[
                    Token(
                        text="λόγος",
                        kind=TokenKind.WORD,
                        position=0,
                        line_no=1,
                        annotations={"lemma": "λόγος", "upos": "NOUN"},
                    )
                ],
                lines=[[0]],
            )
        ],
        script_id="greek",
    )
    with pytest.raises(ValueError, match="requires calibrated confidence annotations"):
        to_review_table(plain, tmp_path / "fail.csv", priority="calibrated_risk")

    corpus = _annotated_corpus_with_confidences()
    with pytest.raises(ValueError, match="budget is only valid"):
        to_review_table(corpus, tmp_path / "b.csv", priority="document", budget=2)
    with pytest.raises(ValueError, match="nonnegative integer"):
        to_review_table(corpus, tmp_path / "b2.csv", priority="calibrated_risk", budget=-1)
    with pytest.raises(ValueError, match="requires the active neural Greek pipeline"):
        annotate_corpus(plain, with_confidence=True)
    with pytest.raises(ValueError, match="confidence_domain requires with_confidence=True"):
        annotate_corpus(plain, confidence_domain="literary")

    # Re-annotating clears stale confidence_* annotations so old confidences never leak.
    reannotated = annotate_corpus(corpus)
    for tok in reannotated.get("doc_a").tokens:
        assert not any(k.startswith("confidence_") for k in tok.annotations)


def test_cli_review_export_calibrated_risk_editable_journey(tmp_path: Path) -> None:
    pytest.importorskip("typer")
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    corpus = _annotated_corpus_with_confidences()
    src_json = tmp_path / "annotated.json"
    corpus.to_json(src_json)
    out_csv = tmp_path / "queue.csv"

    runner = CliRunner()
    res = runner.invoke(
        _build_app(),
        [
            "review",
            "export",
            str(src_json),
            "-o",
            str(out_csv),
            "--layout",
            "editable",
            "--priority",
            "calibrated-risk",
            "--budget",
            "2",
        ],
    )
    assert res.exit_code == 0, res.output
    rows = _read_csv(out_csv)
    assert [r["token"] for r in rows] == ["λόγος", "ἀρχῇ"]
