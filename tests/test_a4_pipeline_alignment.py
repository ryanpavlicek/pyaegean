"""Focused A4 source-alignment and pipeline propagation checks."""

from __future__ import annotations

from dataclasses import replace

from aegean.core.model import Token, TokenKind
from aegean.greek.runtime import GreekPipeline
from aegean.greek.tokenize import tokenize, tokenize_aligned


def test_aligned_tokens_round_trip_exact_source_and_gaps() -> None:
    text = "  α\u0301\r\n''στι\u00a0δʹ; β.  "
    tokens = tokenize_aligned(text, document_id="doc-1")

    assert [token.text for token in tokens] == ["α\u0301", "'", "'στι", "δʹ", ";", "β", "."]
    assert [token.kind for token in tokens] == [
        TokenKind.WORD,
        TokenKind.PUNCT,
        TokenKind.WORD,
        TokenKind.WORD,
        TokenKind.PUNCT,
        TokenKind.WORD,
        TokenKind.PUNCT,
    ]

    rebuilt = "".join(
        token.alignment.whitespace_before + token.alignment.original_text
        for token in tokens
    ) + text[tokens[-1].alignment.end_char :]
    assert rebuilt == text
    assert tokens[0].alignment.start_char == 2
    assert tokens[0].alignment.end_char == 4
    assert tokens[0].alignment.whitespace_before == "  "
    assert tokens[1].alignment.whitespace_before == "\r\n"
    assert tokens[3].alignment.whitespace_before == "\u00a0"


def test_aligned_ids_are_stable_opaque_and_ordinal_based() -> None:
    text = "α α\u0301 ά α"
    first = tokenize_aligned(text, document_id="same")
    second = tokenize_aligned(text, document_id="same")
    changed_document = tokenize_aligned(text, document_id="other")
    changed_source = tokenize_aligned(text + " ", document_id="same")

    ids = [token.alignment.source_token_id for token in first]
    assert ids == [token.alignment.source_token_id for token in second]
    assert len(ids) == len(set(ids)) == 4
    assert ids != [token.alignment.source_token_id for token in changed_document]
    assert ids != [token.alignment.source_token_id for token in changed_source]
    assert first[1].alignment.normalized_text == first[2].alignment.normalized_text == "ά"
    assert first[1].alignment.normalization_ops == ("unicode:nfc",)
    assert first[2].alignment.normalization_ops == ()


def test_sentence_ids_follow_legacy_pipeline_boundaries() -> None:
    text = "α. β; γ· δ"
    tokens = tokenize_aligned(text, document_id="sentences")
    sentence_ids = [token.alignment.sentence_id for token in tokens]
    assert sentence_ids == [
        "sentences:sentence:0",
        "sentences:sentence:0",
        "sentences:sentence:1",
        "sentences:sentence:1",
        "sentences:sentence:2",
        "sentences:sentence:2",
        "sentences:sentence:3",
    ]

    records = GreekPipeline().analyze(text, document_id="sentences")
    assert [record.sentence for record in records] == [0, 0, 1, 1, 2, 2, 3]
    assert [record.alignment.sentence_id for record in records] == sentence_ids
    assert [record.text for record in records] == [token.text for token in tokens]


def test_legacy_values_and_record_equality_ignore_alignment() -> None:
    text = "α, β"
    legacy = tokenize(text)
    aligned = tokenize_aligned(text)
    assert legacy == [
        Token("α", TokenKind.WORD, position=0),
        Token(",", TokenKind.PUNCT, position=1),
        Token("β", TokenKind.WORD, position=2),
    ]
    assert legacy == aligned

    record = GreekPipeline().analyze("α", document_id="one")[0]
    without_alignment = replace(record, alignment=None)
    assert record == without_alignment
    assert record.alignment is not None


def test_empty_input_has_no_alignment_records() -> None:
    assert tokenize_aligned("", document_id="empty") == []
    assert GreekPipeline().analyze("", document_id="empty") == []
