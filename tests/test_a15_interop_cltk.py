"""Focused A15 CLTK adapter checks (the optional dependency is exercised when present)."""

from __future__ import annotations

import copy
import unicodedata
from importlib import metadata as importlib_metadata

import pytest

from aegean.core.model import SourceAlignment
from aegean.greek.ud import UDEmptyNode, UDMultiwordToken, UDDocument, UDSentence, UDToken
from aegean.io._interop_cltk import from_cltk, make_cltk_process, to_cltk
from aegean.io.interop import InteropDocument, InteropSchemaError, InteropTokenMetadata, decode_sidecar

pytestmark = pytest.mark.framework_interop


def _document() -> InteropDocument:
    raw = "λόγος"
    sentence = UDSentence("s1", raw, (UDToken(1, raw, raw, "NOUN", "XPOS", "Case=Nom", 0, "root"),))
    alignment = SourceAlignment("d", "s1", "1", raw, 0, len(raw), "", raw)
    return InteropDocument(
        UDDocument((sentence,)), raw, "d",
        {("s1", 1): InteropTokenMetadata(alignment=alignment)},
    )


def test_cltk_round_trip_preserves_offsets_and_sidecar() -> None:
    pytest.importorskip("cltk")
    result = to_cltk(_document())
    word = result.value.words[0]
    assert (word.index_char_start, word.index_char_stop) == (0, 5)
    assert result.value.sentence_boundaries == [(0, 5)]
    assert word.upos.tag == "NOUN"
    assert [(item.key, item.value) for item in word.features.features] == [("Case", "Nom")]
    assert word.dependency_relation.code == "root"
    assert result.report.version == importlib_metadata.version("cltk")
    assert result.report.sidecar_fields == (
        "document_identity", "token_metadata", "source_alignment", "sentence_ids",
        "raw_conllu",
    )
    assert result.sidecar is not None
    restored = from_cltk(result.value)
    assert restored.value.source_text == "λόγος"
    assert restored.value.ud.sentences[0].tokens[0].form == "λόγος"


def test_cltk_import_requires_sidecar_unless_lossy() -> None:
    pytest.importorskip("cltk")
    native = to_cltk(_document()).value
    native.metadata.pop("aegean.interop/v1", None)
    with pytest.raises(Exception, match="sidecar"):
        from_cltk(copy.deepcopy(native))
    lossy = from_cltk(native, allow_lossy=True)
    assert lossy.report.lost_fields


def test_cltk_process_is_explicit_and_non_mutating() -> None:
    pytest.importorskip("cltk")
    native = to_cltk(_document()).value
    before = native.model_dump(mode="json")

    class Pipeline:
        def analyze(self, text: str, **_kwargs: object) -> list[object]:
            class Record:
                def __init__(self) -> None:
                    self.text = text
                    self.lemma = "λόγος"
                    self.upos = "NOUN"
                    self.feats = "_"
                    self.head = 0
                    self.relation = "root"

            return [Record()]

    process = make_cltk_process(Pipeline())
    out = process.run(native)
    assert out is not native
    assert out.words[0].lemma == "λόγος"
    assert native.model_dump(mode="json") == before


def test_cltk_native_annotations_xpos_confidence_and_tamper() -> None:
    pytest.importorskip("cltk")
    source = _document()
    token = InteropTokenMetadata(
        alignment=next(iter(source.token_metadata.values())).alignment,
        lemma_source="rule",
        xpos="XPOS",
        feats="Case=Nom",
        upos_confidence=0.91,
        lemma_confidence=0.73,
    )
    document = InteropDocument(source.ud_document, source.source_text, source.document_id, {("s1", 1): token})
    native = to_cltk(document).value
    assert native.words[0].xpos == "XPOS"
    assert native.words[0].annotation_sources["lemma"] == "rule"
    assert native.words[0].confidence == {"upos": 0.91, "lemma": 0.73}
    native.words[0].string = "tampered"
    with pytest.raises(InteropSchemaError, match="native projection hash"):
        from_cltk(native)


def test_cltk_sidecar_retains_mwt_and_empty_rows() -> None:
    pytest.importorskip("cltk")
    tokens = (
        UDToken(1, "a", "a", "NOUN", "_", "_", 0, "root"),
        UDToken(2, "b", "b", "NOUN", "_", "_", 1, "obj"),
    )
    rows = (UDMultiwordToken(1, 2, "ab"), *tokens, UDEmptyNode(2, 1))
    sentence = UDSentence("s1", "a b", tokens, rows=rows)
    result = to_cltk(InteropDocument(UDDocument((sentence,)), "a b", "d"))
    assert result.sidecar is not None
    payload = decode_sidecar(result.sidecar)["payload"]
    assert "1-2" in payload["conllu"] and "2.1" in payload["conllu"]


def test_cltk_raw_offsets_are_not_rebased_to_normalized_text() -> None:
    pytest.importorskip("cltk")
    raw = "ἄνθρωπος"
    normalized = unicodedata.normalize("NFD", raw)
    sentence = UDSentence("s1", raw, (UDToken(1, raw, raw, "NOUN", "_", "_", 0, "root"),))
    alignment = SourceAlignment("d", "s1", "1", raw, 0, len(raw), "", normalized, ("NFD",))
    result = to_cltk(InteropDocument(UDDocument((sentence,)), raw, "d", {("s1", 1): InteropTokenMetadata(alignment=alignment)}))
    word = result.value.words[0]
    assert (word.index_char_start, word.index_char_stop) == (0, len(raw))
    assert result.value.raw == raw and result.value.normalized_text == normalized


def test_cltk_lossy_missing_governor_is_retained_as_absence() -> None:
    pytest.importorskip("cltk")
    from cltk.core.data_types import Doc, Language, Word

    native = Doc(language=Language(name="Ancient Greek", glottolog_id="grc"), raw="a", words=[Word(string="a", index_token=0, index_sentence=0, governor=None)])
    restored = from_cltk(native, allow_lossy=True)
    assert restored.value.token_metadata[("sent-0", 1)].head is None
    assert any("governor=None" in warning for warning in restored.report.warnings)


def test_cltk_process_rejects_cardinality_mismatch() -> None:
    pytest.importorskip("cltk")
    native = to_cltk(_document()).value

    class Pipeline:
        def analyze(self, _text: str, **_kwargs: object) -> list[object]:
            return []

    with pytest.raises(InteropSchemaError, match="returned 0 records"):
        make_cltk_process(Pipeline()).run(native)


def test_cltk_multisentence_indices_boundaries_and_lossy_boundary_recovery() -> None:
    pytest.importorskip("cltk")
    source = "A b\nC"
    first = UDSentence(
        "first", "A b",
        (
            UDToken(1, "A", "a", "NOUN", "_", "_", 2, "nsubj"),
            UDToken(2, "b", "b", "VERB", "_", "_", 0, "root"),
        ),
    )
    second = UDSentence(
        "second", "C", (UDToken(1, "C", "c", "NOUN", "_", "_", 0, "root"),)
    )
    metadata = {
        ("first", 1): InteropTokenMetadata(
            alignment=SourceAlignment("d", "first", "1", "A", 0, 1, "", "A")
        ),
        ("first", 2): InteropTokenMetadata(
            alignment=SourceAlignment("d", "first", "2", "b", 2, 3, " ", "b")
        ),
        ("second", 1): InteropTokenMetadata(
            alignment=SourceAlignment("d", "second", "3", "C", 4, 5, "\n", "C")
        ),
    }
    result = to_cltk(
        InteropDocument(UDDocument((first, second)), source, "d", metadata)
    )
    assert [(word.index_sentence, word.index_token) for word in result.value.words] == [
        (0, 0), (0, 1), (1, 0)
    ]
    assert result.value.sentence_boundaries == [(0, 3), (4, 5)]
    result.value.metadata.pop("aegean.interop/v1")
    lossy = from_cltk(result.value, allow_lossy=True)
    assert [
        (
            lossy.value.sentence_metadata[sentence.sent_id].boundary_start_char,
            lossy.value.sentence_metadata[sentence.sent_id].boundary_end_char,
        )
        for sentence in lossy.value.sentences
    ] == [(0, 3), (4, 5)]


def test_cltk_native_signature_covers_unmapped_public_word_state() -> None:
    pytest.importorskip("cltk")
    result = to_cltk(_document())
    result.value.words[0].stem = "tampered"
    with pytest.raises(InteropSchemaError, match="native projection hash"):
        from_cltk(result.value, sidecar=result.sidecar)


def test_cltk_process_preserves_pipeline_metadata_and_unrelated_word_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("cltk")
    numpy = pytest.importorskip("numpy")
    import socket
    from cltk.core.data_types import Pipeline

    native = to_cltk(_document()).value
    native.metadata["custom"] = {"kept": True}
    native.backend = "spacy"
    native.model = "comparison-model"
    native.pipeline = Pipeline(description="existing", glottolog_id="grc")
    native.words[0].stem = "λογ"
    native.words[0].embedding = numpy.array([1.0, 2.0])

    def no_network(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", no_network)

    class LocalPipeline:
        def analyze(self, text: str, **_kwargs: object) -> list[dict[str, object]]:
            return [{
                "text": text,
                "lemma": "λόγος",
                "upos": "NOUN",
                "feats": "Case=Nom",
                "head": 0,
                "relation": "root",
            }]

    output = make_cltk_process(LocalPipeline()).run(native)
    assert output is not native
    assert output.pipeline is native.pipeline
    assert output.metadata["custom"] == {"kept": True}
    assert "aegean.interop/v1" not in output.metadata
    assert output.backend == "spacy" and output.model == "comparison-model"
    assert output.words[0].stem == "λογ"
    assert output.words[0].embedding is not native.words[0].embedding
    output.words[0].embedding[0] = 9.0
    assert native.words[0].embedding[0] == 1.0
    assert "aegean.interop/v1" in native.metadata


def test_cltk_process_treats_uncomputed_optional_annotations_as_absent() -> None:
    pytest.importorskip("cltk")
    from aegean.greek.pipeline import LemmaSource, TokenRecord

    native = to_cltk(_document()).value

    class LocalPipeline:
        def analyze(self, text: str, **_kwargs: object) -> list[TokenRecord]:
            return [
                TokenRecord(
                    sentence=0,
                    index=1,
                    text=text,
                    upos="NOUN",
                    lemma="λόγος",
                    lemma_source=LemmaSource.ATTESTED,
                )
            ]

    output = make_cltk_process(LocalPipeline(), parse=False).run(native)
    word = output.words[0]
    assert word.governor == 0
    assert word.dependency_relation.code == "root"
    assert word.xpos == "XPOS"
    assert [(item.key, item.value) for item in word.features.features] == [
        ("Case", "Nom")
    ]


def test_cltk_lossy_import_rejects_reordered_native_words() -> None:
    pytest.importorskip("cltk")
    from cltk.core.data_types import Doc, Language, Word

    native = Doc(
        language=Language(name="Ancient Greek", glottolog_id="grc"),
        words=[
            Word(string="b", index_sentence=1, index_token=0, governor=0),
            Word(string="a", index_sentence=0, index_token=0, governor=0),
        ],
    )
    with pytest.raises(InteropSchemaError, match="sentence and token order"):
        from_cltk(native, allow_lossy=True)


def test_cltk_rejects_non_greek_documents() -> None:
    pytest.importorskip("cltk")
    from cltk.core.data_types import Doc, Language, Word

    native = Doc(
        language=Language(name="Latin", glottolog_id="lati1261"),
        raw="a",
        words=[Word(string="a", index_sentence=0, index_token=0, governor=0)],
    )
    with pytest.raises(InteropSchemaError, match="Ancient Greek"):
        from_cltk(native, allow_lossy=True)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("feats", "NotAFeature=Unknown", "cannot represent pipeline UD features"),
        ("relation", "not-a-ud-relation", "cannot represent pipeline dependency relation"),
    ],
)
def test_cltk_process_refuses_annotations_it_cannot_represent(
    field: str, value: str, message: str
) -> None:
    pytest.importorskip("cltk")
    native = to_cltk(_document()).value

    class Pipeline:
        def analyze(self, text: str, **_kwargs: object) -> list[dict[str, object]]:
            record: dict[str, object] = {
                "text": text,
                "lemma": "λόγος",
                "upos": "NOUN",
                "feats": "Case=Nom",
                "head": 0,
                "relation": "root",
            }
            record[field] = value
            return [record]

    with pytest.raises(InteropSchemaError, match=message):
        make_cltk_process(Pipeline()).run(native)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("index", True, "non-integer token index"),
        ("sentence", False, "non-integer sentence index"),
        ("head", -1, "invalid head"),
        ("upos_confidence", float("nan"), "invalid upos_confidence"),
    ],
)
def test_cltk_process_validates_record_indices_heads_and_confidence(
    field: str, value: object, message: str
) -> None:
    pytest.importorskip("cltk")
    native = to_cltk(_document()).value

    class Pipeline:
        def analyze(self, text: str, **_kwargs: object) -> list[dict[str, object]]:
            record: dict[str, object] = {
                "text": text,
                "lemma": "λόγος",
                "upos": "NOUN",
                "feats": "Case=Nom",
                "head": 0,
                "relation": "root",
            }
            record[field] = value
            return [record]

    with pytest.raises(InteropSchemaError, match=message):
        make_cltk_process(Pipeline()).run(native)


def test_cltk_process_rejects_invalid_input_before_calling_pipeline() -> None:
    pytest.importorskip("cltk")
    from cltk.core.data_types import Doc, Language, Word

    native = Doc(
        language=Language(name="Ancient Greek", glottolog_id="grc"),
        raw="ab",
        words=[
            Word(string="a", index_sentence=0, index_token=1, governor=0),
            Word(string="b", index_sentence=0, index_token=0, governor=0),
        ],
    )

    class Pipeline:
        def analyze(self, _text: str, **_kwargs: object) -> list[object]:
            raise AssertionError("invalid input must fail before pipeline execution")

    with pytest.raises(InteropSchemaError, match="sentence and token order"):
        make_cltk_process(Pipeline()).run(native)


def test_cltk_reports_structural_ids_omitted_from_the_native_doc() -> None:
    pytest.importorskip("cltk")
    first = UDToken(1, "a", "a", "X", "_", "_", 0, "root")
    second = UDToken(2, "b", "b", "X", "_", "_", 1, "dep")
    sentence = UDSentence(
        "s1",
        "ab",
        (first, second),
        rows=(
            UDMultiwordToken(1, 2, "ab"),
            first,
            second,
            UDEmptyNode(2, 1),
        ),
    )
    result = to_cltk(InteropDocument(UDDocument((sentence,))))
    assert result.report.omitted_ids == ("s1:1-2", "s1:2.1")


def test_cltk_lossy_report_names_every_unmapped_public_field() -> None:
    pytest.importorskip("cltk")
    native = to_cltk(_document()).value
    native.metadata.pop("aegean.interop/v1")
    native.summary = "summary that the canonical envelope does not represent"
    native.words[0].stem = "λογ"
    native.words[0].embedding = pytest.importorskip("numpy").array([1.0])
    projected = from_cltk(native, allow_lossy=True)
    assert "summary" in projected.report.lost_fields
    assert "word.stem" in projected.report.lost_fields
    assert "summary" not in projected.report.native_fields
    assert "word.stem" not in projected.report.native_fields
    assert "word.embedding" in projected.report.lost_fields
