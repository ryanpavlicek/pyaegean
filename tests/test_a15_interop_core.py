"""Focused stdlib interoperability-core checks."""

import hashlib
import json
import subprocess
import sys

import pytest

from aegean.core.model import SourceAlignment
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.pipeline import TokenRecord
from aegean.io.interop import (
    MAX_SIDECAR_BYTES,
    InteropDocument,
    InteropSentenceMetadata,
    InteropLossError,
    InteropReport,
    InteropSchemaError,
    InteropTokenMetadata,
    decode_sidecar,
    from_conllu,
    from_token_records,
    to_conllu,
)
from aegean.greek.ud import UDDocument, UDSentence, UDToken


def _records():
    return [
        TokenRecord(
            0,
            1,
            "κα",
            "NOUN",
            "κα",
            LemmaSource.IDENTITY,
            alignment=SourceAlignment("d", "s1", "a", "κα", 0, 2, "", "κα"),
            head=None,
            relation=None,
        ),
        TokenRecord(
            0,
            2,
            "β",
            "NOUN",
            "β",
            LemmaSource.IDENTITY,
            alignment=SourceAlignment("d", "s1", "b", "β", 3, 4, "\t", "β"),
            head=1,
            relation="dep",
        ),
    ]


def test_raw_crlf_passthrough():
    raw = "# sent_id = s1\r\n# text = α\r\n1\tα\tα\tNOUN\t_\t_\t0\troot\t_\t_\r\n\r\n"
    result = from_conllu(raw)
    assert to_conllu(result.value).value == raw
    assert result.report.native_fields == (
        "ud_document", "conllu_rows", "comments", "raw_columns"
    )


def test_rich_crlf_preserves_native_block():
    raw = "# sent_id = s1\r\n# text = α\r\n1\tα\tα\tNOUN\t_\t_\t0\troot\t_\t_\r\n\r\n"
    native = from_conllu(raw).value.ud_document
    exported = to_conllu(InteropDocument(native, source_text="α", document_id="d"))
    assert exported.value.endswith(raw)
    assert from_conllu(exported.value).value.ud_document.dumps() == raw


def test_rich_sidecar_roundtrip_and_missing_head():
    document = from_token_records(_records(), source_text="κα\tβ", document_id="d")
    exported = to_conllu(document)
    imported = from_conllu(exported.value).value
    assert imported.source_text == "κα\tβ"
    assert imported.token_metadata[("s1", 1)].head is None
    with pytest.raises(InteropLossError):
        to_conllu(document, include_sidecar=False)


def test_sidecar_metadata_tampering_and_duplicate_keys():
    document = from_token_records(_records(), source_text="κα\tβ", document_id="d")
    exported = to_conllu(document)
    line = exported.value.splitlines()[0]
    envelope = json.loads(line.split(" = ", 1)[1])
    envelope["payload"]["source_text"] = "wrong"
    tampered = "# aegean.interop = " + json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n" + "\n".join(exported.value.splitlines()[1:])
    with pytest.raises(InteropSchemaError):
        from_conllu(tampered)


def test_alignment_never_text_searches_and_validates_gap():
    rows = _records()
    rows[1] = TokenRecord(
        0, 2, "β", "NOUN", "β", LemmaSource.IDENTITY,
        alignment=SourceAlignment("d", "s1", "b", "β", 2, 3, "", "β"), head=1, relation="dep",
    )
    with pytest.raises(InteropSchemaError):
        from_token_records(rows, source_text="κα\tβ", document_id="d")


def test_complete_alignment_rejects_unrecorded_nonwhitespace_gaps() -> None:
    native = UDDocument(
        (
            UDSentence(
                "s",
                "ab",
                (
                    UDToken(1, "a", "a", "X", "_", "_", 0, "root"),
                    UDToken(2, "b", "b", "X", "_", "_", 1, "dep"),
                ),
            ),
        )
    )
    with pytest.raises(InteropSchemaError, match="whitespace gap"):
        InteropDocument(
            native,
            source_text="aXb",
            document_id="d",
            token_metadata={
                ("s", 1): InteropTokenMetadata(
                    alignment=SourceAlignment("d", "s", "1", "a", 0, 1, "", "a")
                ),
                ("s", 2): InteropTokenMetadata(
                    alignment=SourceAlignment("d", "s", "2", "b", 2, 3, "", "b")
                ),
            },
        )


def test_empty_metadata_is_valid_with_source_text():
    native = from_conllu("# sent_id = s1\n# text = α\n1\tα\tα\tNOUN\t_\t_\t0\troot\t_\t_\n\n").value.ud_document
    document = InteropDocument(native, source_text="", document_id="d")
    assert document.token_metadata == {}
    assert to_conllu(document).sidecar is not None


def test_sentence_metadata_without_token_metadata():
    native = from_conllu("# sent_id = s1\n# text = α\n1\tα\tα\tNOUN\t_\t_\t0\troot\t_\t_\n\n").value.ud_document
    document = InteropDocument(native, sentence_metadata={"s1": InteropSentenceMetadata()})
    assert to_conllu(document).sidecar is not None


def test_all_structural_conllu_rows_and_duplicate_misc_roundtrip_exactly():
    raw = (
        "# newdoc id = d\r\n"
        "# sent_id = s1\r\n"
        "# text = οὐκ ἔστι\r\n"
        "1-2\tοὐκ\t_\t_\t_\t_\t_\t_\t_\tA=1|A=2\r\n"
        "1\tοὐκ\tοὐ\tPART\t_\tPolarity=Neg\t2\tadvmod\t2:advmod\tA=1|A=2\r\n"
        "2\tἔστι\tεἰμί\tVERB\t_\t_\t0\troot\t0:root\tSpaceAfter=No\r\n"
        "2.1\t_\tτις\tPRON\t_\t_\t_\t_\t2:dep\tCopyOf=2\r\n"
        "\r\n"
        "# trailing document comment\r\n"
        "\r\n"
    )
    imported = from_conllu(raw)
    assert imported.value.ud_document.sentences[0].tokens[0].misc_raw == "A=1|A=2"
    assert to_conllu(imported.value).value == raw
    assert imported.report.native_fields == (
        "ud_document", "conllu_rows", "comments", "raw_columns", "mwt",
        "empty_nodes", "enhanced_dependencies", "misc",
    )


def test_sidecar_rejects_duplicate_unknown_nonfinite_and_oversized_json():
    for value, message in (
        ('{"schema":"a","schema":"b"}', "duplicate JSON key"),
        ('{"value":NaN}', "non-finite JSON number"),
        ("x" * (MAX_SIDECAR_BYTES + 1), "exceeds maximum size"),
    ):
        with pytest.raises(InteropSchemaError, match=message):
            decode_sidecar(value)

    rich = to_conllu(
        from_token_records(_records(), source_text="κα\tβ", document_id="d")
    )
    assert rich.sidecar is not None
    envelope = json.loads(rich.sidecar)
    envelope["schema"] = "aegean.interop/v999"
    with pytest.raises(InteropSchemaError, match="unsupported sidecar schema"):
        decode_sidecar(json.dumps(envelope))


def test_typed_sidecar_rejects_malformed_provenance_scalars() -> None:
    document = from_token_records(_records(), source_text="κα\tβ", document_id="d")
    exported = to_conllu(document)
    assert exported.sidecar is not None
    envelope = json.loads(exported.sidecar)
    envelope["payload"]["provenance"] = {
        "source": ["not", "text"],
        "license": "",
        "citation": "",
        "url": "",
        "schema_version": "bad",
        "notes": [],
        "data_version": "",
        "edition_fidelity": "",
    }
    payload = json.dumps(
        envelope["payload"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    envelope["payload_sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    with pytest.raises(InteropSchemaError, match="provenance source"):
        decode_sidecar(json.dumps(envelope))


def test_sidecar_writer_obeys_the_reader_size_bound():
    document = InteropDocument(
        UDDocument(()), source_text="x" * (MAX_SIDECAR_BYTES + 1), document_id="d"
    )
    with pytest.raises(InteropSchemaError, match="exceeds maximum size"):
        to_conllu(document)


def test_native_tamper_is_detected_even_when_structure_remains_valid():
    exported = to_conllu(
        from_token_records(_records(), source_text="κα\tβ", document_id="d")
    )
    tampered = exported.value.replace("\tβ\tβ\t", "\tγ\tβ\t", 1)
    with pytest.raises(InteropSchemaError, match="native projection hash"):
        from_conllu(tampered)


def test_document_rejects_bad_heads_ids_boundaries_and_source_offsets():
    with pytest.raises(InteropSchemaError, match="contiguous"):
        InteropDocument(
            UDDocument((UDSentence("s", "α", (UDToken(2, "α", "α", "NOUN", "_", "_", 0, "root"),)),))
        )
    with pytest.raises(InteropSchemaError, match="outside"):
        InteropDocument(
            UDDocument((UDSentence("s", "α", (UDToken(1, "α", "α", "NOUN", "_", "_", 2, "dep"),)),))
        )
    native = from_conllu(
        "# sent_id = s\n# text = α\n1\tα\tα\tNOUN\t_\t_\t0\troot\t_\t_\n\n"
    ).value.ud_document
    with pytest.raises(InteropSchemaError, match="boundary"):
        InteropDocument(
            native,
            source_text="α",
            sentence_metadata={
                "s": InteropSentenceMetadata(boundary_start_char=0, boundary_end_char=2)
            },
        )
    with pytest.raises(InteropSchemaError, match="source slice"):
        InteropDocument(
            native,
            source_text="β",
            document_id="d",
            token_metadata={
                ("s", 1): InteropTokenMetadata(
                    alignment=SourceAlignment("d", "s", "t", "α", 0, 1, "", "α")
                )
            },
        )


def test_partial_alignment_validates_its_immediate_whitespace_without_text_search():
    native = from_conllu(
        "# sent_id = s\n# text = α β γ\n"
        "1\tα\tα\tNOUN\t_\t_\t0\troot\t_\t_\n"
        "2\tβ\tβ\tNOUN\t_\t_\t1\tdep\t_\t_\n"
        "3\tγ\tγ\tNOUN\t_\t_\t1\tdep\t_\t_\n\n"
    ).value.ud_document
    document = InteropDocument(
        native,
        source_text="α β γ",
        document_id="d",
        token_metadata={
            ("s", 3): InteropTokenMetadata(
                alignment=SourceAlignment("d", "s", "third", "γ", 4, 5, " ", "γ")
            )
        },
    )
    assert document.token_metadata[("s", 3)].alignment is not None


def test_missing_and_explicit_empty_metadata_values_stay_distinct():
    native = from_conllu(
        "# sent_id = s\n# text = α β\n"
        "1\tα\tα\tNOUN\t_\t_\t0\troot\t_\t_\n"
        "2\tβ\tβ\tNOUN\t_\t_\t1\tdep\t_\t_\n\n"
    ).value.ud_document
    document = InteropDocument(
        native,
        token_metadata={
            ("s", 1): InteropTokenMetadata(analysis_warning=None),
            ("s", 2): InteropTokenMetadata(analysis_warning=""),
        },
    )
    restored = from_conllu(to_conllu(document).value).value
    assert restored.token_metadata[("s", 1)].analysis_warning is None
    assert restored.token_metadata[("s", 2)].analysis_warning == ""


def test_explicit_lossy_report_lists_only_fields_actually_dropped():
    native = from_conllu(
        "# sent_id = s\n# text = α\n1\tα\tα\tNOUN\t_\t_\t0\troot\t_\t_\n\n"
    ).value.ud_document
    document = InteropDocument(
        native,
        token_metadata={("s", 1): InteropTokenMetadata(relation=None)},
    )
    projected = to_conllu(document, include_sidecar=False, allow_lossy=True)
    assert projected.sidecar is None
    assert projected.report.lost_fields == ("token_metadata",)
    assert projected.value == native.dumps()


def test_token_records_use_normalized_form_without_losing_original_source():
    original = "α\u0314"
    normalized = "ἁ"
    record = TokenRecord(
        0,
        1,
        normalized,
        "NOUN",
        normalized,
        LemmaSource.IDENTITY,
        alignment=SourceAlignment(
            "d", "s", "t", original, 0, len(original), "", normalized,
            ("unicode:nfc",),
        ),
        head=0,
        relation="root",
    )
    document = from_token_records([record], source_text=original, document_id="d")
    assert document.ud_document.sentences[0].tokens[0].form == normalized
    restored = from_conllu(to_conllu(document).value).value
    assert restored.source_text == original
    assert restored.token_metadata[("s", 1)].alignment.original_text == original


def test_token_record_and_alignment_order_are_never_silently_repaired():
    with pytest.raises(InteropSchemaError, match="sentence and token order"):
        from_token_records(
            list(reversed(_records())), source_text="κα\tβ", document_id="d"
        )

    native = from_conllu(
        "# sent_id = s\n# text = α β\n"
        "1\tα\tα\tNOUN\t_\t_\t0\troot\t_\t_\n"
        "2\tβ\tβ\tNOUN\t_\t_\t1\tdep\t_\t_\n\n"
    ).value.ud_document
    with pytest.raises(InteropSchemaError, match="UD token order"):
        InteropDocument(
            native,
            source_text="α β",
            document_id="d",
            token_metadata={
                ("s", 1): InteropTokenMetadata(
                    alignment=SourceAlignment("d", "s", "later", "β", 2, 3, " ", "β")
                ),
                ("s", 2): InteropTokenMetadata(
                    alignment=SourceAlignment("d", "s", "earlier", "α", 0, 1, "", "α")
                ),
            },
        )


def test_document_rejects_cycles_partial_boundaries_and_metadata_drift():
    with pytest.raises(InteropSchemaError, match="cycle"):
        InteropDocument(
            UDDocument(
                (
                    UDSentence(
                        "s",
                        "α β",
                        (
                            UDToken(1, "α", "α", "NOUN", "_", "_", 2, "dep"),
                            UDToken(2, "β", "β", "NOUN", "_", "_", 1, "dep"),
                        ),
                    ),
                )
            )
        )
    native = from_conllu(
        "# sent_id = s\n# text = α\n1\tα\tα\tNOUN\t_\t_\t0\troot\t_\t_\n\n"
    ).value.ud_document
    with pytest.raises(InteropSchemaError, match="both start and end"):
        InteropDocument(
            native,
            source_text="α",
            sentence_metadata={"s": InteropSentenceMetadata(boundary_start_char=0)},
        )
    with pytest.raises(InteropSchemaError, match="metadata relation"):
        InteropDocument(
            native,
            token_metadata={
                ("s", 1): InteropTokenMetadata(relation="not-root")
            },
        )


def test_reports_require_exact_disjoint_field_classes():
    with pytest.raises(InteropSchemaError, match="disjoint"):
        InteropReport(
            native_fields=("form",),
            sidecar_fields=("form",),
            target="spacy",
            direction="export",
        )
    with pytest.raises(InteropSchemaError, match="duplicates"):
        InteropReport(
            lost_fields=("offset", "offset"),
            target="spacy",
            direction="export",
        )
    malformed = InteropReport(
        target="spacy", direction="export"
    ).to_dict()
    malformed["native_fields"] = 3
    with pytest.raises(InteropSchemaError, match="invalid interop report"):
        InteropReport.from_dict(malformed)


def test_importing_interop_facade_never_imports_optional_frameworks():
    code = r'''
import builtins
import sys

real_import = builtins.__import__
targets = {"spacy", "stanza", "cltk"}

def blocked(name, *args, **kwargs):
    if name.split(".", 1)[0] in targets:
        raise AssertionError(f"unexpected optional import: {name}")
    return real_import(name, *args, **kwargs)

builtins.__import__ = blocked
import aegean
import aegean.io
import aegean.io._interop_spacy
import aegean.io._interop_stanza
import aegean.io._interop_cltk
assert not targets.intersection(sys.modules)
'''
    completed = subprocess.run(
        [sys.executable, "-I", "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
