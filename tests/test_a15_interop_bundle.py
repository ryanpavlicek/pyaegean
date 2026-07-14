"""A15 portable-bundle correctness, tamper, and persistence contracts."""

from __future__ import annotations

import builtins
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

import pytest

from aegean.core.model import SourceAlignment, TokenFormState
from aegean.core.provenance import Provenance
from aegean.greek.confidence import ConfidenceResult, SentenceConfidence, TokenConfidence
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.neural_contract import AnalysisReceipt
from aegean.greek.ud import UDDocument, UDSentence, UDToken
from aegean.io._interop_bundle import (
    InteropBundle,
    bundle_from_document,
    dumps_interop_bundle,
    loads_interop_bundle,
    read_interop_bundle,
    write_interop_bundle,
)
from aegean.io.interop import (
    InteropDocument,
    InteropSchemaError,
    InteropSentenceMetadata,
    InteropTokenMetadata,
    from_conllu,
)


FIXTURE = Path(__file__).parent / "fixtures" / "ud" / "sample-ud-test.conllu"


def _report_sha256(value: dict[str, object]) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _bundle() -> InteropBundle:
    # This long-standing fixture intentionally contains an invalid empty node
    # so the permissive CoNLL-U reader's opaque-preservation path is covered.
    document = from_conllu(FIXTURE, strict=False).value
    return bundle_from_document(document, target="conllu")


def _fixture_text() -> str:
    with FIXTURE.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _receipt() -> AnalysisReceipt:
    return AnalysisReceipt(
        schema_version=1,
        source_schema_version=1,
        model_id="synthetic-model",
        dataset="synthetic",
        asset_sha256=None,
        asset_sha256_enforced=False,
        bundle_manifest_sha256=None,
        bundle_schema_version=None,
        tokenizer_revision=None,
        package_version="test",
        python_version="test",
        runtime_versions=(("runtime", "test"),),
        execution_providers=("test",),
        annotation_profile="canonical:test",
        normalization="NFC",
        segmentation="pretokenized",
        preprocessing_version="test",
        special_token_policy=None,
        max_subwords=512,
        input_tokens=1,
        analyzed_tokens=1,
        truncated=False,
        windowed=False,
    )


def _confidence(task: str, value: float) -> ConfidenceResult:
    return ConfidenceResult(
        task=task,
        value=value,
        calibration_id="a" * 64,
        scope="synthetic-test",
        model="synthetic-model",
        source="synthetic",
        domain="classical",
        n=10,
        ece=0.05,
    )


def _all_fields_document() -> InteropDocument:
    source = "λόγος"
    receipt = _receipt()
    token_confidence = TokenConfidence(index=0, upos=_confidence("upos", 0.9))
    sentence_confidence = SentenceConfidence(
        result=_confidence("sentence", 0.8), components=("upos",)
    )
    native = UDDocument(
        (
            UDSentence(
                "sentence-1",
                source,
                (
                    UDToken(
                        1,
                        source,
                        source,
                        "NOUN",
                        "N--",
                        "Case=Nom",
                        0,
                        "root",
                    ),
                ),
            ),
        )
    )
    return InteropDocument(
        native,
        source_text=source,
        document_id="document-1",
        token_metadata={
            ("sentence-1", 1): InteropTokenMetadata(
                alignment=SourceAlignment(
                    "document-1",
                    "sentence-1",
                    "source-token-1",
                    source,
                    0,
                    len(source),
                    "",
                    source,
                ),
                form_state=TokenFormState(
                    diplomatic=source,
                    regularized=source,
                    normalized=source,
                    model_input=source,
                    model_input_ops=("unicode:nfc",),
                    model_input_source="normalized",
                ),
                lemma_source=LemmaSource.ATTESTED,
                lemma_source_path="synthetic-lexicon",
                confidence=token_confidence,
                analysis_receipt=receipt,
                head=0,
                relation="root",
                xpos="N--",
                feats="Case=Nom",
                upos_confidence=0.9,
                lemma_confidence=0.85,
                neural_analyzed=True,
                analysis_complete=True,
                analysis_warning="synthetic test warning",
            )
        },
        sentence_metadata={
            "sentence-1": InteropSentenceMetadata(
                confidence=sentence_confidence,
                boundary_policy="synthetic",
                boundary_policy_id="synthetic-v1",
                boundary_provenance="test fixture",
                boundary_confidence=0.95,
                boundary_start_char=0,
                boundary_end_char=len(source),
                analysis_receipt=receipt,
            )
        },
        annotation_profile="canonical:test",
        provenance=Provenance(
            source="Synthetic fixture",
            license="CC0",
            citation="Synthetic fixture (2026).",
            url="https://example.invalid/fixture",
            notes=("all-fields contract",),
            data_version="1",
            edition_fidelity="normalized",
        ),
    )


def test_bundle_is_deterministic_and_recovers_full_structural_document() -> None:
    bundle = _bundle()
    first = dumps_interop_bundle(bundle)
    second = dumps_interop_bundle(_bundle())
    assert first == second

    restored = loads_interop_bundle(first)
    assert restored.target == "conllu"
    assert restored.report.lossless
    assert restored.document.ud_document.dumps() == _fixture_text()
    first_sentence = restored.document.ud_document.sentences[0]
    assert [row.id for row in first_sentence.rows] == [1, 2, 3, "4-5", 4, 5, "5.1"]
    assert first_sentence.empty_nodes[0].deps_raw == "_"


def test_bundle_native_state_is_deeply_immutable_and_json_safe() -> None:
    bundle = _bundle()
    assert isinstance(bundle.native, MappingProxyType)
    with pytest.raises(TypeError):
        bundle.native["conllu"] = "changed"  # type: ignore[index]
    assert loads_interop_bundle(dumps_interop_bundle(bundle)).native == bundle.native


def test_bundle_writer_is_atomic_and_reader_revalidates(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "interop.json"
    written = write_interop_bundle(_bundle(), destination)
    assert written == destination
    restored = read_interop_bundle(destination)
    assert restored.document.ud_document.dumps() == _fixture_text()


def test_bundle_rejects_native_sidecar_and_report_tampering() -> None:
    raw = json.loads(dumps_interop_bundle(_bundle()))

    changed_native = json.loads(json.dumps(raw))
    changed_native["native"]["conllu"] += "# changed\n"
    with pytest.raises(InteropSchemaError, match="native projection hash"):
        loads_interop_bundle(json.dumps(changed_native))

    changed_sidecar = json.loads(json.dumps(raw))
    sidecar = json.loads(changed_sidecar["sidecar"])
    sidecar["payload"]["document_id"] = "changed"
    changed_sidecar["sidecar"] = json.dumps(sidecar)
    with pytest.raises(InteropSchemaError, match="payload hash"):
        loads_interop_bundle(json.dumps(changed_sidecar))

    changed_report = json.loads(json.dumps(raw))
    changed_report["report"]["lost_fields"] = ["source_text"]
    changed_report["report"]["lossless"] = False
    changed_report["report_sha256"] = _report_sha256(changed_report["report"])
    with pytest.raises(InteropSchemaError, match="lossless adapter result"):
        loads_interop_bundle(json.dumps(changed_report))

    changed_warning = json.loads(json.dumps(raw))
    changed_warning["report"]["warnings"] = ["invented warning"]
    with pytest.raises(InteropSchemaError, match="report hash"):
        loads_interop_bundle(json.dumps(changed_warning))

    changed_direction = json.loads(json.dumps(raw))
    changed_direction["report"]["direction"] = "import"
    changed_direction["report_sha256"] = _report_sha256(changed_direction["report"])
    with pytest.raises(InteropSchemaError, match="direction must be export"):
        loads_interop_bundle(json.dumps(changed_direction))


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ('{"schema":"x","schema":"y"}', "duplicate JSON key"),
        ('{"value":NaN}', "non-finite JSON number"),
        ("[]", "JSON object"),
    ],
)
def test_bundle_rejects_duplicate_nonfinite_and_wrong_shape(
    payload: str, message: str
) -> None:
    with pytest.raises(InteropSchemaError, match=message):
        loads_interop_bundle(payload)


def test_bundle_writer_and_reader_share_native_size_bound() -> None:
    bundle = _bundle()
    with pytest.raises(InteropSchemaError, match="native projection exceeds"):
        InteropBundle(
            target=bundle.target,
            target_version=bundle.target_version,
            native={"conllu": "x" * (8 * 1024 * 1024 + 1)},
            sidecar=bundle.sidecar,
            report=bundle.report,
        )


def test_bundle_rejects_excessively_nested_native_json_cleanly() -> None:
    raw = json.loads(dumps_interop_bundle(_bundle()))
    nested: object = "leaf"
    for _ in range(110):
        nested = [nested]
    raw["native"]["nested"] = nested
    with pytest.raises(InteropSchemaError, match="nesting depth"):
        loads_interop_bundle(json.dumps(raw))


@pytest.mark.parametrize("target", ["spacy", "stanza", "cltk"])
def test_framework_bundles_roundtrip_without_target_import_on_read(
    target: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip(target)
    document = from_conllu(FIXTURE, strict=False).value
    serialized = dumps_interop_bundle(
        bundle_from_document(document, target=target)
    )
    original_import = builtins.__import__

    def blocked(name: str, *args: object, **kwargs: object):
        if name == target or name.startswith(f"{target}."):
            raise AssertionError(f"reading a bundle imported {target}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    restored = loads_interop_bundle(serialized)
    assert restored.target == target
    assert restored.report.lossless
    assert restored.document.ud_document.dumps() == _fixture_text()


@pytest.mark.parametrize("target", ["spacy", "stanza", "cltk"])
def test_framework_bundle_native_projection_tampering_is_rejected(
    target: str,
) -> None:
    pytest.importorskip(target)
    document = from_conllu(FIXTURE, strict=False).value
    raw = json.loads(
        dumps_interop_bundle(bundle_from_document(document, target=target))
    )
    raw["native"]["injected"] = True
    with pytest.raises(InteropSchemaError, match="native projection hash"):
        loads_interop_bundle(json.dumps(raw))


@pytest.mark.parametrize("target", ["conllu", "spacy", "stanza", "cltk"])
def test_all_typed_metadata_roundtrips_through_every_portable_bundle(
    target: str,
) -> None:
    if target != "conllu":
        pytest.importorskip(target)
    original = _all_fields_document()
    restored = loads_interop_bundle(
        dumps_interop_bundle(bundle_from_document(original, target=target))
    )
    assert restored.report.lossless
    assert restored.document.to_dict() == original.to_dict()
