"""A4 alignment propagation through user-facing rows, tables, and review."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

import aegean
from aegean import SourceAlignment
from aegean._view import pipeline_rows
from aegean.core.corpus import Corpus
from aegean.core.model import Document
from aegean.greek import tokenize_aligned
from aegean.io.review import REVIEW_COLUMNS, from_review_table, to_review_table
from aegean.io.tabular import _progress_dataframe
from aegean.tui.data import document_detail


SOURCE = "  α\u0301\tλόγος.\r\n"


def _corpus() -> Corpus:
    tokens = tokenize_aligned(SOURCE, document_id="source-doc")
    annotated = [
        replace(
            token,
            annotations=(
                {"lemma": "λόγος", "upos": "NOUN", "lemma_source": "rule"}
                if token.text == "λόγος"
                else dict(token.annotations)
            ),
        )
        for token in tokens
    ]
    document = Document(
        id="source-doc",
        script_id="greek",
        tokens=annotated,
        lines=[list(range(len(annotated)))],
        source_text=SOURCE,
    )
    document.validate_source_alignment()
    return Corpus([document], script_id="greek")


def test_public_alignment_type_and_pipeline_rows_are_lossless_json() -> None:
    assert SourceAlignment is aegean.core.SourceAlignment
    rows = pipeline_rows(SOURCE)
    assert rows
    assert json.loads(json.dumps(rows, ensure_ascii=False)) == rows

    for row in rows:
        start = row["alignment_start_char"]
        end = row["alignment_end_char"]
        assert SOURCE[start:end] == row["alignment_original_text"]
        assert row["alignment_document_id"] == "input"
        assert row["alignment_source_token_id"]
    assert rows[0]["alignment_whitespace_before"] == "  "
    assert rows[0]["alignment_normalized_text"] == "ά"
    assert rows[0]["alignment_normalization_ops"] == ["unicode:nfc"]


def test_dataframe_progress_and_tui_preserve_alignment() -> None:
    pytest.importorskip("pandas")
    corpus = _corpus()
    expected = corpus.to_dataframe("token")
    calls: list[tuple[int, int]] = []
    actual = _progress_dataframe(corpus, "token", lambda done, total: calls.append((done, total)))
    assert actual.equals(expected)
    assert calls == [(1, 1)]

    detail = document_detail(corpus, "source-doc")
    assert detail.source_text == SOURCE
    flat = [token for line in detail.lines for token in line.tokens]
    assert flat[0].alignment is not None
    assert flat[0].alignment["original_text"] == "α\u0301"
    assert flat[0].alignment["normalization_ops"] == ("unicode:nfc",)


def _edit_review(path: Path, **changes: str) -> None:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    row = next(value for value in rows if value["token"] == "λόγος")
    row.update(changes)
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REVIEW_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def test_review_prefers_stable_source_identity_and_rejects_changed_span(tmp_path) -> None:
    corpus = _corpus()
    table = tmp_path / "review.csv"
    assert to_review_table(corpus, table) == 2
    _edit_review(table, correct_lemma="λέξις")

    # Positions are a compatibility/display field. The stable source-token ID is
    # the primary A4 join, so an annotation-only journey survives renumbering.
    original_document = corpus.documents[0]
    moved_tokens = [
        replace(token, position=(token.position or 0) + 20)
        for token in original_document.tokens
    ]
    moved = Corpus(
        [replace(original_document, tokens=moved_tokens)],
        provenance=corpus.provenance,
        script_id=corpus.script_id,
    )
    corrected = from_review_table(table, moved)
    word = next(token for token in corrected.documents[0].tokens if token.text == "λόγος")
    assert word.annotations["lemma"] == "λέξις"
    assert word.alignment == next(
        token.alignment for token in original_document.tokens if token.text == "λόγος"
    )

    tampered = tmp_path / "tampered.csv"
    assert to_review_table(corpus, tampered) == 2
    _edit_review(tampered, correct_lemma="λέξις", alignment_start_char="0")
    with pytest.raises(ValueError, match="source alignment"):
        from_review_table(tampered, corpus)


def test_review_table_flattens_every_alignment_field(tmp_path) -> None:
    path = tmp_path / "review.csv"
    to_review_table(_corpus(), path)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["alignment_document_id"] == "source-doc"
    assert row["alignment_sentence_id"] == "source-doc:sentence:0"
    assert row["alignment_source_token_id"]
    assert row["alignment_original_text"] == "α\u0301"
    assert row["alignment_start_char"] == "2"
    assert row["alignment_end_char"] == "4"
    assert row["alignment_whitespace_before"] == "  "
    assert row["alignment_normalized_text"] == "ά"
    assert json.loads(row["alignment_normalization_ops"]) == ["unicode:nfc"]
    assert row["token"] == "α\u0301"
