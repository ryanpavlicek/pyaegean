"""Focused A15 Stanza adapter checks (real Stanza remains optional)."""

from __future__ import annotations

import json
from importlib import metadata as importlib_metadata

import pytest

from aegean.greek.ud import UDDocument, UDSentence, UDToken
from aegean.greek.ud import UDEmptyNode, UDMultiwordToken, UDDependency, UDNodeID
from aegean.core.model import SourceAlignment
from aegean.io._interop_stanza import from_stanza, to_stanza
from aegean.io.interop import (
    InteropDocument,
    InteropSchemaError,
    InteropTokenMetadata,
)

pytestmark = pytest.mark.framework_interop


def _document() -> InteropDocument:
    sentence = UDSentence(
        "s1", "A b", (UDToken(1, "A", "a", "NOUN", "X", "Case=Nom", 2, "nsubj"), UDToken(2, "b", "b", "VERB", "Y", "_", 0, "root"))
    )
    metadata = {
        ("s1", 1): InteropTokenMetadata(
            alignment=SourceAlignment("d", "s1", "1", "A", 0, 1, "", "A")
        ),
        ("s1", 2): InteropTokenMetadata(
            alignment=SourceAlignment("d", "s1", "2", "b", 2, 3, " ", "b")
        ),
    }
    return InteropDocument(UDDocument((sentence,)), "A b", "d", metadata)


def test_stanza_strict_import_requires_sidecar() -> None:
    pytest.importorskip("stanza")
    from stanza.models.common.doc import Document

    with pytest.raises(Exception, match="sidecar"):
        from_stanza(Document([], text=""))


def test_stanza_explicit_lossy_projection_reports_exact_missing_fields() -> None:
    pytest.importorskip("stanza")
    native = to_stanza(_document()).value
    if hasattr(native, "_aegean_interop_sidecar"):
        delattr(native, "_aegean_interop_sidecar")
    projected = from_stanza(native, sidecar=None, allow_lossy=True)
    assert projected.report.lost_fields == (
        "document_identity", "token_metadata", "source_alignment", "form_state",
        "lemma_provenance", "confidence", "receipts", "analysis_state",
        "sentence_metadata", "profile", "provenance", "empty_nodes",
        "opaque_rows", "comments", "row_order", "raw_conllu",
    )


def test_stanza_real_offsets_and_external_sidecar_serializer_caveat() -> None:
    pytest.importorskip("stanza")
    result = to_stanza(_document())
    native = result.value
    assert native.text == "A b"
    assert native.sentences[0].words[1].start_char == 2
    assert native.sentences[0].words[1].head == 0
    assert result.report.version == importlib_metadata.version("stanza")
    assert result.report.sidecar_fields == (
        "document_identity", "token_metadata", "source_alignment", "raw_conllu"
    )
    # Stanza's generic serializer is target-owned; the portable pyaegean sidecar
    # is deliberately returned separately and is what guarantees reimport.
    assert result.sidecar is not None
    serialized = native.to_dict()
    assert isinstance(serialized, list)
    assert "aegean.interop" not in json.dumps(serialized)
    from stanza.models.common.doc import Document

    reloaded = Document.from_serialized(native.to_serialized())
    assert not hasattr(reloaded, "_aegean_interop_sidecar")
    restored = from_stanza(native, sidecar=result.sidecar)
    assert restored.value == _document()


def test_stanza_sidecar_preserves_mwt_empty_and_row_order() -> None:
    pytest.importorskip("stanza")
    first = UDToken(1, "ab", "a", "NOUN", "X", "_", 0, "root")
    second = UDToken(2, "cd", "c", "NOUN", "X", "_", 1, "dep")
    sentence = UDSentence(
        "s1", "abcd", (first, second),
        rows=(UDMultiwordToken(1, 2, "abcd"), first, second, UDEmptyNode(2, 1, deps=(UDDependency(UDNodeID.parse("2"), "dep"),), deps_raw="2:dep")),
    )
    document = InteropDocument(UDDocument((sentence,)), "abcd", "d")
    result = to_stanza(document)
    assert tuple(result.value.sentences[0].tokens[0].id) == (1, 2)
    assert [word.text for word in result.value.sentences[0].words] == ["ab", "cd"]
    restored = from_stanza(result.value, sidecar=result.sidecar)
    rows = restored.value.ud.sentences[0].rows
    assert [row.id for row in rows] == ["1-2", 1, 2, "2.1"]

    delattr(result.value, "_aegean_interop_sidecar")
    lossy = from_stanza(result.value, allow_lossy=True)
    assert lossy.value.ud.sentences[0].multiword_tokens[0].id == "1-2"
    assert "MWT_row_state" in lossy.report.lost_fields


def test_stanza_alignment_handles_repeated_unicode_whitespace_and_trailing_text() -> None:
    pytest.importorskip("stanza")
    source = "e\u0301\te\u0301\nβ  ! trailing"
    forms = ("e\u0301", "e\u0301", "β", "!")
    starts = (0, 3, 6, 9)
    ends = (2, 5, 7, 10)
    gaps = ("", "\t", "\n", "  ")
    sentence = UDSentence(
        "s1", " ".join(forms),
        tuple(UDToken(index, form, form, "X", "_", "_", 0 if index == 1 else 1, "root" if index == 1 else "dep") for index, form in enumerate(forms, 1)),
    )
    metadata = {
        ("s1", index): InteropTokenMetadata(
            alignment=SourceAlignment("d", "s1", str(index), form, start, end, gap, form)
        )
        for index, (form, start, end, gap) in enumerate(zip(forms, starts, ends, gaps), 1)
    }
    document = InteropDocument(UDDocument((sentence,)), source, "d", metadata)
    exported = to_stanza(document)
    assert [word.start_char for word in exported.value.sentences[0].words] == list(starts)
    assert exported.value.sentences[0].tokens[0].spaces_after == "\t"
    assert from_stanza(exported.value, sidecar=exported.sidecar).value.source_text == source


def test_stanza_native_tampering_is_rejected() -> None:
    pytest.importorskip("stanza")
    result = to_stanza(_document())
    result.value.sentences[0].words[0].head = 1
    with pytest.raises(Exception, match="native projection"):
        from_stanza(result.value, sidecar=result.sidecar)


def test_stanza_rejects_conflicting_attached_and_supplied_sidecars() -> None:
    pytest.importorskip("stanza")
    result = to_stanza(_document())
    setattr(result.value, "_aegean_interop_sidecar", "different")
    with pytest.raises(InteropSchemaError, match="conflicts with supplied sidecar"):
        from_stanza(result.value, sidecar=result.sidecar)


def test_stanza_lossy_import_generates_only_missing_sentence_ids() -> None:
    pytest.importorskip("stanza")
    from stanza.models.common.doc import Document

    native = Document(
        [
            [{"id": 1, "text": "A", "head": 0, "deprel": "root"}],
            [{"id": 1, "text": "B", "head": 0, "deprel": "root"}],
        ],
        text="A B",
    )
    for sentence in native.sentences:
        sentence.sent_id = None
    projected = from_stanza(native, allow_lossy=True)
    assert [sentence.sent_id for sentence in projected.value.sentences] == [
        "sent-0",
        "sent-1",
    ]
    assert "sent_id" not in projected.report.native_fields
    assert "sentence_ids" in projected.report.lost_fields


def test_stanza_multisentence_ids_offsets_and_exact_inter_sentence_whitespace() -> None:
    pytest.importorskip("stanza")
    source = "A\tb\nC  D tail"
    first = UDSentence(
        "source-a",
        "A b",
        (
            UDToken(1, "A", "a", "NOUN", "_", "_", 2, "nsubj"),
            UDToken(2, "b", "b", "VERB", "_", "_", 0, "root"),
        ),
    )
    second = UDSentence(
        "source-b",
        "C D",
        (
            UDToken(1, "C", "c", "NOUN", "_", "_", 0, "root"),
            UDToken(2, "D", "d", "NOUN", "_", "_", 1, "dep"),
        ),
    )
    metadata = {
        ("source-a", 1): InteropTokenMetadata(
            alignment=SourceAlignment("d", "source-a", "1", "A", 0, 1, "", "A")
        ),
        ("source-a", 2): InteropTokenMetadata(
            alignment=SourceAlignment("d", "source-a", "2", "b", 2, 3, "\t", "b")
        ),
        ("source-b", 1): InteropTokenMetadata(
            alignment=SourceAlignment("d", "source-b", "3", "C", 4, 5, "\n", "C")
        ),
        ("source-b", 2): InteropTokenMetadata(
            alignment=SourceAlignment("d", "source-b", "4", "D", 7, 8, "  ", "D")
        ),
    }
    result = to_stanza(
        InteropDocument(UDDocument((first, second)), source, "d", metadata)
    )
    assert [sentence.sent_id for sentence in result.value.sentences] == [
        "source-a", "source-b"
    ]
    assert [word.start_char for sentence in result.value.sentences for word in sentence.words] == [
        0, 2, 4, 7
    ]
    assert [token.spaces_after for sentence in result.value.sentences for token in sentence.tokens] == [
        "\t", "\n", "  ", " tail"
    ]
    assert from_stanza(result.value).value.source_text == source


def test_stanza_does_not_fabricate_offsets_without_complete_alignment() -> None:
    pytest.importorskip("stanza")
    sentence = UDSentence(
        "s", "A", (UDToken(1, "A", "a", "NOUN", "_", "_", 0, "root"),)
    )
    result = to_stanza(InteropDocument(UDDocument((sentence,)), "A", "d"))
    assert result.value.text == "A"
    assert result.value.sentences[0].words[0].start_char is None
    assert "text" in result.report.native_fields
    assert "offsets" not in result.report.native_fields
    assert result.report.warnings
    assert from_stanza(result.value).value.source_text == "A"


@pytest.mark.parametrize("sent_id", [" leading", "trailing ", "line\rbreak"])
def test_stanza_rejects_sentence_ids_its_comment_parser_would_change(
    sent_id: str,
) -> None:
    pytest.importorskip("stanza")
    sentence = UDSentence(
        sent_id, "A", (UDToken(1, "A", "a", "NOUN", "_", "_", 0, "root"),)
    )
    with pytest.raises(InteropSchemaError, match="sentence IDs"):
        to_stanza(InteropDocument(UDDocument((sentence,))))
