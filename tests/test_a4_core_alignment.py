"""A4 core alignment schema: invariants, persistence, and compatibility."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace

import pytest

from aegean.core.corpus import Corpus
from aegean.core.model import Document, SourceAlignment, Token, TokenKind


def _alignment(**overrides: object) -> SourceAlignment:
    values: dict[str, object] = {
        "document_id": "doc-1",
        "sentence_id": "sent-1",
        "source_token_id": "doc-1:t0:0-4",
        "original_text": "λόγος",
        "start_char": 0,
        "end_char": 5,
        "whitespace_before": "",
        "normalized_text": "λόγος",
        "normalization_ops": (),
    }
    values.update(overrides)
    return SourceAlignment(**values)  # type: ignore[arg-type]


def _corpus_with_alignment() -> Corpus:
    source = "λόγος\tκαί"
    first = _alignment()
    second = _alignment(
        source_token_id="doc-1:t1:6-9",
        original_text="καί",
        start_char=6,
        end_char=9,
        whitespace_before="\t",
        normalized_text="και",
        normalization_ops=("unicode:nfc",),
    )
    doc = Document(
        id="doc-1",
        script_id="greek",
        tokens=[
            Token("λόγος", TokenKind.WORD, position=0, alignment=first),
            Token("καί", TokenKind.WORD, position=1, alignment=second),
        ],
        lines=[[0, 1]],
        source_text=source,
    )
    return Corpus([doc], script_id="greek")


def test_source_alignment_is_immutable_slotted_and_validates_offsets() -> None:
    a = _alignment()
    assert not hasattr(a, "__dict__")
    with pytest.raises(FrozenInstanceError):
        a.start_char = 1  # type: ignore[misc]
    a.validate_source("λόγος", document_id="doc-1")

    with pytest.raises(ValueError, match="length"):
        _alignment(end_char=4)
    with pytest.raises(ValueError, match="non-empty"):
        _alignment(source_token_id="")
    with pytest.raises(ValueError, match="Unicode whitespace"):
        _alignment(whitespace_before=" space")
    with pytest.raises(TypeError, match="integer"):
        _alignment(start_char=True)
    with pytest.raises(ValueError, match="non-empty strings"):
        _alignment(original_text="changed", end_char=7, normalized_text="changed", normalization_ops=("",))
    with pytest.raises(ValueError, match="exactly when"):
        _alignment(normalization_ops=("unicode:nfc",))
    with pytest.raises(ValueError, match="exactly when"):
        _alignment(normalized_text="different")
    with pytest.raises(ValueError, match="outside"):
        a.validate_source("λόγ", document_id="doc-1")
    with pytest.raises(ValueError, match="belongs"):
        a.validate_source("λόγος", document_id="other")
    with pytest.raises(ValueError, match="source slice"):
        a.validate_source("xxxxx", document_id="doc-1")


def test_alignment_preserves_unicode_codepoint_slices_and_legacy_equality() -> None:
    # Combining marks count as separate Python code points, exactly as the stored
    # half-open offsets promise.  SourceAlignment is excluded from Token equality.
    source = "α\u0301 ἄ"
    a = _alignment(
        original_text="α\u0301",
        start_char=0,
        end_char=2,
        normalized_text="ά",
        normalization_ops=("unicode:nfc",),
    )
    a.validate_source(source, document_id="doc-1")
    assert source[a.start_char : a.end_char] == a.original_text
    assert Token("α\u0301", TokenKind.WORD) == Token(
        "α\u0301", TokenKind.WORD, alignment=a
    )
    assert Document("d", "greek", [], []) == Document(
        "d", "greek", [], [], source_text="changed"
    )


def test_json_roundtrip_and_fingerprint_sense_alignment_fields() -> None:
    corpus = _corpus_with_alignment()
    payload = json.loads(corpus.to_json())
    assert payload["_meta"]["schemaVersion"] == 3
    raw_doc = payload["documents"][0]
    assert raw_doc["source_text"] == "λόγος\tκαί"
    assert raw_doc["tokens"][1]["alignment"]["whitespace_before"] == "\t"
    restored = Corpus.from_json(corpus.to_json())
    assert restored.documents[0].source_text == corpus.documents[0].source_text
    assert restored.documents[0].tokens[1].alignment == corpus.documents[0].tokens[1].alignment
    assert restored.fingerprint() == corpus.fingerprint()

    changed_source = _corpus_with_alignment()
    changed_source.documents[0].source_text = "λόγος  καί"
    assert changed_source.fingerprint() != corpus.fingerprint()
    changed_alignment = _corpus_with_alignment()
    changed_alignment.documents[0].tokens[0] = Token(
        "λόγος", TokenKind.WORD, position=0,
        alignment=_alignment(source_token_id="a-different-stable-id"),
    )
    assert changed_alignment.fingerprint() != corpus.fingerprint()


def test_legacy_no_alignment_fingerprint_and_schema_fixture_are_compatible() -> None:
    legacy = Corpus(
        [Document("d", "greek", [Token("A", TokenKind.WORD, position=0)], [[0]])],
        script_id="greek",
    )
    # This value is the schema-1 algorithm's output for the fixture above.  The
    # A4 block is intentionally absent when no source/alignment exists.
    assert legacy.fingerprint() == "894576141a5ade361f89c1897c761dc7aa7481e83c6a20b53264e71bb3c3b01e"

    raw = {
        "_meta": {"tool": "pyaegean", "schemaVersion": 1, "scriptId": "greek"},
        "provenance": None,
        "signInventory": None,
        "documents": [
            {
                "id": "legacy",
                "script_id": "greek",
                "tokens": [{"text": "λόγος", "kind": "word", "position": 0}],
                "lines": [[0]],
            }
        ],
    }
    loaded = Corpus.from_dict(raw)
    assert loaded.documents[0].source_text is None
    assert loaded.documents[0].tokens[0].alignment is None

    future = json.loads(json.dumps(raw))
    future["_meta"]["schemaVersion"] = 4
    with pytest.raises(ValueError, match="schema version 4"):
        Corpus.from_dict(future)


def test_alignment_json_rejects_wrong_source_and_malformed_operations() -> None:
    payload = json.loads(_corpus_with_alignment().to_json())
    payload["documents"][0]["source_text"] = "wrong"
    with pytest.raises(ValueError, match="source slice"):
        Corpus.from_dict(payload)

    payload = json.loads(_corpus_with_alignment().to_json())
    payload["documents"][0]["tokens"][0]["alignment"]["normalization_ops"] = "unicode:nfc"
    with pytest.raises(TypeError, match="JSON array"):
        Corpus.from_dict(payload)


def test_document_alignment_validation_rejects_gaps_duplicates_overlap_and_partial() -> None:
    corpus = _corpus_with_alignment()
    document = corpus.documents[0]

    wrong_gap = replace(document.tokens[1], alignment=replace(
        document.tokens[1].alignment, whitespace_before=" "
    ))
    document.tokens[1] = wrong_gap
    with pytest.raises(ValueError, match="whitespace_before"):
        document.validate_source_alignment()

    document.tokens[1] = replace(document.tokens[1], alignment=replace(
        document.tokens[1].alignment,
        whitespace_before="\t",
        source_token_id=document.tokens[0].alignment.source_token_id,
    ))
    with pytest.raises(ValueError, match="duplicate"):
        document.validate_source_alignment()

    document.tokens[1] = replace(document.tokens[1], alignment=replace(
        document.tokens[1].alignment,
        source_token_id="doc-1:t1:4-7",
        original_text="ς\tκ",
        start_char=4,
        end_char=7,
        whitespace_before="",
    ))
    with pytest.raises(ValueError, match="overlap|source slice"):
        document.validate_source_alignment()

    document.tokens[1] = replace(document.tokens[1], alignment=None)
    with pytest.raises(ValueError, match="missing source alignment"):
        document.validate_source_alignment()

    missing_source = _corpus_with_alignment().documents[0]
    missing_source.source_text = None
    with pytest.raises(ValueError, match="no source_text"):
        missing_source.validate_source_alignment()


def test_alignment_fields_are_flattened_for_token_dataframe() -> None:
    pytest.importorskip("pandas")
    frame = _corpus_with_alignment().to_dataframe(level="token")
    row = frame.loc[frame["text"] == "καί"].iloc[0]
    assert row["alignment_source_token_id"] == "doc-1:t1:6-9"
    assert row["alignment_start_char"] == 6
    assert row["alignment_end_char"] == 9
    assert row["alignment_normalization_ops"] == ("unicode:nfc",)
    assert "alignment_original_text" in frame.columns
