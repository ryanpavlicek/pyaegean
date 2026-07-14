"""Focused A15 spaCy adapter checks (real spaCy remains optional)."""

from __future__ import annotations

from importlib import metadata as importlib_metadata

import pytest

from aegean.core.model import SourceAlignment
from aegean.greek.ud import UDDocument, UDSentence, UDToken
from aegean.io._interop_spacy import from_spacy, to_spacy
from aegean.io.interop import (
    InteropDocument,
    InteropSchemaError,
    InteropTokenMetadata,
)

pytestmark = pytest.mark.framework_interop


def _document() -> InteropDocument:
    first = UDSentence(
        "s1", "A b", (UDToken(1, "A", "a", "NOUN", "X", "Case=Nom", 2, "nsubj"), UDToken(2, "b", "b", "VERB", "Y", "_", 0, "root"))
    )
    second = UDSentence("s2", "C", (UDToken(1, "C", "c", "NOUN", "X", "_", 0, "root"),))
    metadata = {
        ("s1", 1): InteropTokenMetadata(alignment=SourceAlignment("d", "s1", "1", "A", 0, 1, "", "A")),
        ("s1", 2): InteropTokenMetadata(alignment=SourceAlignment("d", "s1", "2", "b", 2, 3, " ", "b")),
        ("s2", 1): InteropTokenMetadata(alignment=SourceAlignment("d", "s2", "3", "C", 4, 5, " ", "C")),
    }
    return InteropDocument(UDDocument((first, second)), "A b C", "d", metadata)


def test_spacy_strict_import_requires_sidecar() -> None:
    pytest.importorskip("spacy")
    from spacy.tokens import Doc
    from spacy.vocab import Vocab

    native = Doc(Vocab(), words=["A"], spaces=[False])
    with pytest.raises(Exception, match="sidecar"):
        from_spacy(native)


def test_spacy_explicit_lossy_projection_reports_exact_missing_fields() -> None:
    pytest.importorskip("spacy")
    native = to_spacy(_document()).value
    native.user_data.clear()
    projected = from_spacy(native, allow_lossy=True)
    assert projected.report.lost_fields == (
        "document_identity", "token_metadata", "source_alignment", "form_state",
        "lemma_provenance", "confidence", "receipts", "analysis_state",
        "sentence_metadata", "profile", "provenance", "sentence_ids", "MWT",
        "empty_nodes", "enhanced_dependencies", "misc", "opaque_rows", "comments",
        "row_order", "raw_conllu",
    )


def test_spacy_real_heads_sentence_boundaries_and_docbin_settings() -> None:
    pytest.importorskip("spacy")
    from spacy.tokens import DocBin

    result = to_spacy(_document())
    doc = result.value
    assert [(token.text, token.head.i) for token in doc] == [("A", 1), ("b", 1), ("C", 2)]
    assert [(token.lemma_, token.pos_, token.tag_, str(token.morph)) for token in doc] == [
        ("a", "NOUN", "X", "Case=Nom"),
        ("b", "VERB", "Y", ""),
        ("c", "NOUN", "X", ""),
    ]
    assert [sentence.text for sentence in doc.sents] == ["A b", "C"]
    assert result.report.version == importlib_metadata.version("spacy")
    assert result.report.sidecar_fields == (
        "document_identity", "token_metadata", "source_alignment", "sentence_ids",
        "raw_conllu",
    )
    keep = DocBin(store_user_data=True)
    keep.add(doc)
    kept = list(keep.get_docs(doc.vocab))[0]
    assert from_spacy(kept).value.ud.sentences[1].tokens[0].form == "C"
    drop = DocBin(store_user_data=False)
    drop.add(doc)
    dropped = list(drop.get_docs(doc.vocab))[0]
    with pytest.raises(Exception, match="sidecar"):
        from_spacy(dropped)


def test_spacy_sidecar_tampering_and_canonical_nonmutation() -> None:
    pytest.importorskip("spacy")
    document = _document()
    before = document.to_dict()
    result = to_spacy(document)
    result.value[0].lemma_ = "tampered"
    with pytest.raises(Exception, match="native projection"):
        from_spacy(result.value, sidecar=result.sidecar)
    assert document.to_dict() == before


def test_spacy_rejects_conflicting_attached_and_supplied_sidecars() -> None:
    pytest.importorskip("spacy")
    result = to_spacy(_document())
    result.value.user_data["aegean.interop/v1"] = "different"
    with pytest.raises(InteropSchemaError, match="conflicts with supplied sidecar"):
        from_spacy(result.value, sidecar=result.sidecar)


def test_spacy_alignment_handles_repeated_unicode_whitespace_and_trailing_text() -> None:
    pytest.importorskip("spacy")
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
    exported = to_spacy(document)
    assert [token.whitespace_ for token in exported.value] == [" ", " ", " ", " "]
    assert exported.report.warnings
    assert from_spacy(exported.value, sidecar=exported.sidecar).value.source_text == source


def test_spacy_does_not_invent_space_before_unaligned_nonwhitespace_tail() -> None:
    pytest.importorskip("spacy")
    sentence = UDSentence(
        "s", "A", (UDToken(1, "A", "a", "NOUN", "_", "_", 0, "root"),)
    )
    document = InteropDocument(
        UDDocument((sentence,)),
        "AX",
        "d",
        {
            ("s", 1): InteropTokenMetadata(
                alignment=SourceAlignment("d", "s", "1", "A", 0, 1, "", "A")
            )
        },
    )
    exported = to_spacy(document)
    assert exported.value[0].whitespace_ == ""
    assert exported.value.text == "A"
    assert exported.report.warnings


def test_spacy_warns_when_leading_or_empty_document_source_is_sidecar_only() -> None:
    pytest.importorskip("spacy")
    sentence = UDSentence(
        "s", "A", (UDToken(1, "A", "a", "NOUN", "_", "_", 0, "root"),)
    )
    leading = InteropDocument(
        UDDocument((sentence,)),
        " A",
        "d",
        {
            ("s", 1): InteropTokenMetadata(
                alignment=SourceAlignment("d", "s", "1", "A", 1, 2, " ", "A")
            )
        },
    )
    assert to_spacy(leading).report.warnings
    assert to_spacy(InteropDocument(UDDocument(()), "unmapped", "d")).report.warnings


def test_spacy_lossy_import_uses_sentence_local_ids_without_fabricated_alignment() -> None:
    pytest.importorskip("spacy")
    native = to_spacy(_document()).value
    native.user_data.clear()
    restored = from_spacy(native, allow_lossy=True).value
    assert [[token.id for token in sentence.tokens] for sentence in restored.sentences] == [
        [1, 2], [1]
    ]
    assert restored.document_id is None
    assert restored.token_metadata == {}
