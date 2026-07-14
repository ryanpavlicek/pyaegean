"""Focused A16 receipt/profile binding checks (no model asset required)."""

from __future__ import annotations

import pytest

from dataclasses import replace

from aegean.core.model import SourceAlignment
from aegean.data import DataNotAvailableError
from aegean.greek.annotation_profiles import AnalysisProfile, PostprocessingStep
from aegean.greek.documentary import _documentary_analysis_profile
from aegean.greek import documentary
from aegean.greek.joint import SentenceAnalysis, _JointModel
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.neural_contract import AnalysisReceipt, ReceiptMismatchError
from aegean.greek.paradigms import ParadigmLexicon
from aegean.greek.pipeline import TokenRecord
from aegean.io import bundle_from_document, dumps_interop_bundle, loads_interop_bundle
from aegean.io.interop import InteropSchemaError, from_conllu, from_token_records, to_conllu


def _receipt() -> AnalysisReceipt:
    return AnalysisReceipt(
        schema_version=1,
        source_schema_version=1,
        model_id="test-model",
        dataset="test-dataset",
        asset_sha256=None,
        asset_sha256_enforced=False,
        bundle_manifest_sha256=None,
        bundle_schema_version=None,
        tokenizer_revision=None,
        package_version="test",
        python_version="test",
        runtime_versions=(),
        execution_providers=("CPUExecutionProvider",),
        annotation_profile="pyaegean-canonical-v1",
        normalization="NFC",
        segmentation="pretokenized",
        preprocessing_version="test",
        special_token_policy=None,
        max_subwords=None,
        input_tokens=1,
        analyzed_tokens=1,
        truncated=False,
        windowed=False,
    )


def test_profile_binding_roundtrips_schema3_and_keeps_runtime_assertion_separate() -> None:
    profile = AnalysisProfile(
        profile_id="documentary-papygreek-v1",
        inference_annotation_profile="pyaegean-canonical-v1",
        output_annotation_profile="pyaegean-canonical-v1",
        postprocessing=(PostprocessingStep(step_id="reconcile"),),
    )
    bound = _receipt().with_analysis_profile(profile)

    assert bound.schema_version == 3
    assert bound.output_profile_id == profile.profile_id
    assert bound.postprocessing == ("reconcile",)
    assert AnalysisReceipt.from_json(bound.to_json()) == bound
    bound.assert_same_analysis_profile(AnalysisReceipt.from_json(bound.to_json()))

    changed = bound.with_analysis_profile(
        AnalysisProfile(
            profile_id=profile.profile_id,
            inference_annotation_profile="pyaegean-canonical-v1",
            output_annotation_profile="pyaegean-canonical-v1",
            domain_profile="papygreek-regularized-v1",
            postprocessing=profile.postprocessing,
        )
    )
    with pytest.raises(ReceiptMismatchError):
        bound.assert_same_analysis_profile(changed)
    # Runtime identity deliberately ignores the composed output profile.
    bound.assert_same_runtime(changed)

    with pytest.raises(ReceiptMismatchError, match="inference convention"):
        _receipt().with_analysis_profile(
            AnalysisProfile(
                profile_id="wrong-inference-v1",
                inference_annotation_profile="other-inference-v1",
                output_annotation_profile="pyaegean-canonical-v1",
            )
        )
    with pytest.raises(ReceiptMismatchError, match="schema-3"):
        _receipt().assert_same_analysis_profile(_receipt())


def test_schema3_can_omit_optional_confidence_hashes() -> None:
    profile = AnalysisProfile(
        profile_id="canonical-v1",
        inference_annotation_profile="pyaegean-canonical-v1",
        output_annotation_profile="pyaegean-canonical-v1",
    )
    bound = _receipt().with_analysis_profile(profile)
    payload = bound.to_dict()
    assert "calibration_sha256" not in payload
    assert "confidence_policy_sha256" not in payload
    assert AnalysisReceipt.from_dict(payload) == bound


def test_schema3_confidence_hashes_roundtrip_and_rejects_profile_tampering() -> None:
    profile = AnalysisProfile(
        profile_id="canonical-v1",
        inference_annotation_profile="pyaegean-canonical-v1",
        output_annotation_profile="pyaegean-canonical-v1",
    )
    bound = _receipt().with_analysis_profile(profile)
    with_confidence = replace(
        bound,
        calibration_sha256="d" * 64,
        confidence_policy_sha256="e" * 64,
    )
    assert AnalysisReceipt.from_json(with_confidence.to_json()) == with_confidence

    payload = bound.to_dict()
    payload["output_profile_sha256"] = "f" * 64
    with pytest.raises(ReceiptMismatchError):
        bound.assert_same_analysis_profile(AnalysisReceipt.from_dict(payload))
    payload["postprocessing"] = [""]
    with pytest.raises(ValueError):
        AnalysisReceipt.from_dict(payload)
    payload = bound.to_dict()
    payload["output_profile_id"] = " "
    with pytest.raises(ValueError, match="trimmed"):
        AnalysisReceipt.from_dict(payload)

    duplicate = bound.to_json().replace(
        '"output_profile_id":"canonical-v1"',
        '"output_profile_id":"canonical-v1","output_profile_id":"other-v1"',
    )
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        AnalysisReceipt.from_json(duplicate)


def test_documentary_profile_hash_binds_modes_and_paradigm_resource() -> None:
    conservative = _documentary_analysis_profile(
        reconcile=True, rescue=False, aggressive=False, paradigm_lexicon=None
    )
    aggressive = _documentary_analysis_profile(
        reconcile=True, rescue=False, aggressive=True, paradigm_lexicon=None
    )
    with_paradigm = _documentary_analysis_profile(
        reconcile=True,
        rescue=True,
        aggressive=False,
        paradigm_lexicon=ParadigmLexicon({"λόγος": [{"lemma": "λόγος"}]}),
    )
    with_other_paradigm = _documentary_analysis_profile(
        reconcile=True,
        rescue=True,
        aggressive=False,
        paradigm_lexicon=ParadigmLexicon({"λόγος": [{"lemma": "λόγος"}], "νέα": [{"lemma": "νέος"}]}),
    )
    assert conservative.profile_id == aggressive.profile_id
    assert conservative.output_annotation_profile == "papygreek-agdt-v1"
    rescue_only = _documentary_analysis_profile(
        reconcile=False, rescue=True, aggressive=False, paradigm_lexicon=None
    )
    assert rescue_only.output_annotation_profile == "pyaegean-canonical-v1"
    assert conservative.sha256 != aggressive.sha256
    assert with_paradigm.sha256 != conservative.sha256
    assert with_paradigm.sha256 != with_other_paradigm.sha256
    assert tuple(step.step_id for step in with_paradigm.postprocessing) == (
        "pyaegean-documentary-reconciliation-v1",
        "pyaegean-documentary-lemma-rescue-v1",
        "pyaegean-seed-lemma-table-v1",
        "pyaegean-paradigm-lexicon-v1",
    )


def test_documentary_wrapper_binds_profile_when_reconciliation_is_a_noop() -> None:
    analysis = SentenceAnalysis(
        tokens=("καί",),
        upos=("CCONJ",),
        xpos=("c--------",),
        feats=("_",),
        head=(0,),
        deprel=("root",),
        lemma=("καί",),
        lemma_resolved=(True,),
        receipt=_receipt(),
    )
    original = (analysis.upos, analysis.xpos, analysis.lemma)
    model = documentary._DocumentaryModel(object())
    old_state = (documentary._RECONCILE, documentary._RESCUE, documentary._AGGRESSIVE)
    documentary._RECONCILE = True
    documentary._RESCUE = False
    documentary._AGGRESSIVE = False
    try:
        result = model._apply(analysis)
    finally:
        documentary._RECONCILE, documentary._RESCUE, documentary._AGGRESSIVE = old_state
    assert (result.upos, result.xpos, result.lemma) == original
    assert result.receipt is not None
    assert result.receipt.schema_version == 3
    assert result.receipt.postprocessing == ("pyaegean-documentary-reconciliation-v1",)


def test_documentary_wrapper_preserves_custom_inference_profile_identity() -> None:
    custom_receipt = replace(_receipt(), annotation_profile="custom-profile-v1")
    analysis = SentenceAnalysis(
        tokens=("καί",),
        upos=("CCONJ",),
        xpos=("c--------",),
        feats=("_",),
        head=(0,),
        deprel=("root",),
        lemma=("καί",),
        lemma_resolved=(True,),
        receipt=custom_receipt,
    )
    model = documentary._DocumentaryModel(object())
    old_state = (documentary._RECONCILE, documentary._RESCUE, documentary._AGGRESSIVE)
    documentary._RECONCILE = True
    documentary._RESCUE = False
    documentary._AGGRESSIVE = False
    try:
        result = model._apply(analysis)
    finally:
        documentary._RECONCILE, documentary._RESCUE, documentary._AGGRESSIVE = old_state

    assert result.receipt is not None
    expected = _documentary_analysis_profile(
        reconcile=True,
        rescue=False,
        aggressive=False,
        paradigm_lexicon=None,
        inference_annotation_profile="custom-profile-v1",
    )
    assert expected.inference_annotation_profile == "custom-profile-v1"
    assert expected.output_annotation_profile == "papygreek-agdt-v1"
    assert result.receipt.output_profile_sha256 == expected.sha256


def test_paradigm_resource_snapshots_caller_data() -> None:
    source = {"λόγος": [{"lemma": "λόγος"}]}
    lexicon = ParadigmLexicon(source)
    digest = lexicon.resource_sha256
    source["λόγος"][0]["lemma"] = "tampered"
    source["νέα"] = [{"lemma": "νέος"}]
    assert lexicon.resource_sha256 == digest
    assert lexicon.lemmatize("λόγος") == "λόγος"
    assert lexicon.lemmatize("νέα") is None


def test_paradigm_constructor_rejects_malformed_data_and_resource_identity() -> None:
    for malformed in (None, {"x": "bad"}, {"x": [{"lemma": 1}]}, {"x": [{"lemma": ""}]}):
        with pytest.raises(DataNotAvailableError, match="malformed|not a paradigm index"):
            ParadigmLexicon(malformed)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="resource identity"):
        ParadigmLexicon({"x": [{"lemma": "x"}]}, resource_id=" ")


def test_plain_joint_receipt_binds_canonical_profile() -> None:
    model = object.__new__(_JointModel)
    model.manifest = type(
        "Manifest",
        (),
        {
            "model_id": "test-model",
            "dataset": "test-dataset",
            "asset_sha256": None,
            "asset_sha256_enforced": False,
            "manifest_sha256": None,
            "schema_version": 1,
            "tokenizer_revision": None,
            "max_subwords": 256,
            "annotation_profile": "pyaegean-canonical-v1",
            "normalization": "NFC",
            "segmentation": "pretokenized",
            "preprocessing_version": "test",
            "special_token_policy": "two-token",
        },
    )()
    model._sess = type("Session", (), {"get_providers": lambda self: ["CPUExecutionProvider"]})()
    receipt = model._receipt(input_tokens=1, analyzed_tokens=1, truncated=False)
    assert receipt is not None
    assert receipt.schema_version == 3
    assert receipt.output_profile_id == "pyaegean-canonical-analysis-v1"
    assert receipt.postprocessing == ()

    model.manifest.annotation_profile = "custom-profile-v1"
    custom_receipt = model._receipt(input_tokens=1, analyzed_tokens=1, truncated=False)
    assert custom_receipt is not None
    assert custom_receipt.schema_version == 1
    assert custom_receipt.output_profile_id is None


def _interop_records(
    first_receipt: AnalysisReceipt, second_receipt: AnalysisReceipt
) -> list[TokenRecord]:
    return [
        TokenRecord(
            0,
            1,
            "α",
            "NOUN",
            "α",
            LemmaSource.IDENTITY,
            alignment=SourceAlignment("doc", "s1", "t1", "α", 0, 1, "", "α"),
            analysis_receipt=first_receipt,
        ),
        TokenRecord(
            1,
            1,
            "β",
            "NOUN",
            "β",
            LemmaSource.IDENTITY,
            alignment=SourceAlignment("doc", "s2", "t2", "β", 2, 3, " ", "β"),
            analysis_receipt=second_receipt,
        ),
    ]


def test_interop_roundtrip_requires_one_output_profile_for_the_document() -> None:
    profile = AnalysisProfile(
        profile_id="canonical-v1",
        inference_annotation_profile="pyaegean-canonical-v1",
        output_annotation_profile="pyaegean-canonical-v1",
    )
    receipt = _receipt().with_analysis_profile(profile)
    document = from_token_records(
        _interop_records(receipt, receipt), source_text="α β", document_id="doc"
    )
    exported = to_conllu(document)
    imported = from_conllu(exported.value).value
    assert imported.annotation_profile == "pyaegean-canonical-v1"
    assert {
        metadata.analysis_receipt.output_profile_sha256
        for metadata in imported.sentence_metadata.values()
        if metadata.analysis_receipt is not None
    } == {profile.sha256}

    portable = loads_interop_bundle(
        dumps_interop_bundle(bundle_from_document(document, target="conllu"))
    ).document
    assert {
        metadata.analysis_receipt.output_profile_sha256
        for metadata in portable.sentence_metadata.values()
        if metadata.analysis_receipt is not None
    } == {profile.sha256}

    other_profile = replace(profile, profile_id="other-v1")
    other_receipt = _receipt().with_analysis_profile(other_profile)
    with pytest.raises(InteropSchemaError, match="more than one output analysis profile"):
        from_token_records(
            _interop_records(receipt, other_receipt),
            source_text="α β",
            document_id="doc",
        )


def test_interop_rejects_mixed_legacy_and_profile_bound_receipts() -> None:
    profile = AnalysisProfile(
        profile_id="canonical-v1",
        inference_annotation_profile="pyaegean-canonical-v1",
        output_annotation_profile="pyaegean-canonical-v1",
    )
    with pytest.raises(InteropSchemaError, match="more than one output analysis profile"):
        from_token_records(
            _interop_records(_receipt(), _receipt().with_analysis_profile(profile)),
            source_text="α β",
            document_id="doc",
        )
