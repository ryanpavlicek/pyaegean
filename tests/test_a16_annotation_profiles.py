"""A16 typed annotation/domain profile contracts."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from aegean.greek.annotation_profiles import (
    AmbiguityDisclosure,
    AnalysisProfile,
    AnnotationProfile,
    DomainProfile,
    LabelMapping,
    PostprocessingStep,
    ProfileEvidence,
    ProfileError,
    ProfileMappingError,
    ProfileSchemaError,
    list_annotation_profiles,
    canonical_analysis_profile,
    list_domain_profiles,
    get_annotation_profile,
    get_domain_profile,
)


def _evidence() -> ProfileEvidence:
    return ProfileEvidence("fixture", "claims-registry", "fixture.json", "fixture scope")


def _mapping(*, reversible: bool = True, **kwargs: object) -> LabelMapping:
    pairs = kwargs.pop("pairs", (("NOUN", "N"), ("VERB", "V")))
    return LabelMapping(
        field="upos",
        source_profile="source-v1",
        target_profile="target-v1",
        pairs=pairs,
        reversible=reversible,
        **kwargs,
    )


def _annotation() -> AnnotationProfile:
    return AnnotationProfile(
        profile_id="fixture-v1",
        source_convention="fixture",
        source_revision="fixture-revision",
        source_license="CC0-1.0",
        compatibility="canonical",
        output_fields=("FORM", "UPOS"),
        relation_scheme="fixture-relations",
        normalization=("NFC",),
        model_segmentation="pretokenized",
        document_segmentation="sentence-boundaries",
        mappings=(_mapping(),),
        supported_domains=("fixture-domain",),
        raw_requirements=("retain source rows",),
        ambiguities=(),
        evidence=(_evidence(),),
    )


def test_profile_values_are_frozen_and_canonical() -> None:
    profile = _annotation()
    assert isinstance(profile, AnnotationProfile)
    assert profile.to_json() == json.dumps(
        profile.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    assert AnnotationProfile.from_json(profile.to_json()) == profile
    assert profile.sha256 == AnnotationProfile.from_json(profile.to_json()).sha256
    with pytest.raises(FrozenInstanceError):
        profile.profile_id = "other"  # type: ignore[misc]


def test_all_typed_records_round_trip_and_hash() -> None:
    evidence = _evidence()
    disclosure = AmbiguityDisclosure("ambiguous", "UPOS", "context matters", "refuse inverse")
    mapping = _mapping(reversible=False, losses=("many-to-one",))
    step = PostprocessingStep(
        "documentary-reconciliation",
        parameters=(("aggressive", False),),
        resource_id="seed-v1",
        evidence=(evidence,),
    )
    domain = DomainProfile(
        profile_id="fixture-domain-v1",
        domains=("documentary",),
        source_layer="reg",
        annotation_profile_id="fixture-v1",
        normalization=("NFC",),
        segmentation=("sentences",),
        evidence=(evidence,),
        limitations=("descriptive scope only",),
    )
    for value, cls in (
        (evidence, ProfileEvidence),
        (disclosure, AmbiguityDisclosure),
        (mapping, LabelMapping),
        (step, PostprocessingStep),
        (domain, DomainProfile),
    ):
        assert cls.from_json(value.to_json()) == value
        assert len(value.sha256) == 64
    composed = AnalysisProfile(
        "fixture-analysis-v1",
        "fixture-v1",
        "fixture-v1",
        domain_profile=domain.profile_id,
        postprocessing=(step,),
    )
    assert AnalysisProfile.from_json(composed.to_json()) == composed
    assert len(composed.sha256) == 64


def test_json_loader_rejects_duplicate_and_unknown_keys() -> None:
    with pytest.raises(ProfileSchemaError, match="duplicate"):
        ProfileEvidence.from_json(
            '{"evidence_id":"a","kind":"k","source":"s","scope":"x","scope":"y","schema_version":1}'
        )
    with pytest.raises(ProfileSchemaError, match="fields mismatch"):
        ProfileEvidence.from_dict(
            {"evidence_id": "a", "kind": "k", "source": "s", "scope": "x"}
        )
    with pytest.raises(ProfileSchemaError, match="schema version 1"):
        ProfileEvidence.from_dict(
            {
                "evidence_id": "a",
                "kind": "k",
                "source": "s",
                "scope": "x",
                "schema_version": 2,
            }
        )
    raw = _annotation().to_dict()
    raw["unknown"] = True
    with pytest.raises(ProfileSchemaError, match="unknown"):
        AnnotationProfile.from_dict(raw)


def test_profile_json_rejects_pathological_size_and_depth_cleanly() -> None:
    oversized = '{"evidence_id":"' + ("x" * (1024 * 1024)) + '"}'
    with pytest.raises(ProfileSchemaError, match="size limit"):
        ProfileEvidence.from_json(oversized)
    nested = "[" * 2000 + "null" + "]" * 2000
    with pytest.raises(ProfileSchemaError):
        ProfileEvidence.from_json(nested)
    with pytest.raises(ProfileSchemaError, match="size limit"):
        ProfileEvidence("id", "kind", "x" * (1024 * 1024), "scope").to_json()


def test_mapping_is_directional_and_only_bijections_have_inverse() -> None:
    mapping = _mapping()
    assert mapping.forward("NOUN") == "N"
    assert mapping.inverse("N") == "NOUN"
    with pytest.raises(ProfileMappingError):
        mapping.forward("ADJ")
    assert mapping.forward("ADJ", strict=False) is None

    lossy = _mapping(reversible=False, pairs=(("NOUN", "N"), ("PROPN", "N")), losses=("POS collapse",))
    with pytest.raises(ProfileMappingError, match="not reversible"):
        lossy.inverse("N")


def test_mapping_rejects_undeclared_loss_and_invalid_bijection() -> None:
    with pytest.raises(ProfileMappingError, match="bijective"):
        LabelMapping("upos", "a", "b", (("x", "z"), ("y", "z")), True)
    with pytest.raises(ProfileMappingError, match="loss disclosure"):
        LabelMapping("upos", "a", "b", (("x", "z"), ("y", "z")), False)
    with pytest.raises(ProfileMappingError, match="context"):
        LabelMapping("upos", "a", "b", (("x", "z"),), False, context="tree", losses=("context",)).forward("x")
    assert (
        LabelMapping(
            "upos",
            "a",
            "b",
            (("x", "z"),),
            False,
            context="lexical or tree context required",
            losses=("context",),
        ).forward("x", context="source sentence 17")
        == "z"
    )


def test_registry_is_read_only_and_unknown_ids_fail() -> None:
    annotations = list_annotation_profiles()
    domains = list_domain_profiles()
    assert {profile.profile_id for profile in annotations} == {
        "pyaegean-canonical-v1",
        "perseus-agdt-v1",
        "proiel-diagnostic-v1",
        "papygreek-agdt-v1",
    }
    assert {profile.profile_id for profile in domains} == {
        "papygreek-regularized-v1",
        "papygreek-diplomatic-surface-v1",
    }
    with pytest.raises(TypeError):
        annotations[0] = get_annotation_profile("pyaegean-canonical-v1")  # type: ignore[index]
    with pytest.raises(ProfileError, match="unknown"):
        get_annotation_profile("missing-v1")
    with pytest.raises(ProfileError, match="unknown"):
        get_domain_profile("missing-v1")


def test_builtins_disclose_convention_and_orig_layer() -> None:
    proiel = get_annotation_profile("proiel-diagnostic-v1")
    assert proiel.compatibility == "diagnostic-only"
    assert any("scheme-absent" in item.code for item in proiel.ambiguities)
    assert any(item.code == "native-xml-evaluation-projection" for item in proiel.ambiguities)
    assert any(item.evidence_id == "proiel_convention_decomposition" for item in proiel.evidence)
    orig = get_domain_profile("papygreek-diplomatic-surface-v1")
    assert orig.source_layer == "orig"
    assert any("FORM" in limitation for limitation in orig.limitations)
    assert any("regularized" in limitation for limitation in orig.limitations)


def test_canonical_composed_profile_has_no_hidden_postprocessing() -> None:
    profile = canonical_analysis_profile()
    assert profile.inference_annotation_profile == "pyaegean-canonical-v1"
    assert profile.output_annotation_profile == "pyaegean-canonical-v1"
    assert profile.domain_profile is None
    assert profile.postprocessing == ()


def test_builtin_evidence_resolves_to_claim_rows_and_artifacts() -> None:
    root = Path(__file__).resolve().parents[1]
    claims = json.loads((root / "training" / "results" / "published-claims.json").read_text(encoding="utf-8"))
    values = (*list_annotation_profiles(), *list_domain_profiles())
    for profile in values:
        if hasattr(profile, "source_revision"):
            assert profile.source_revision and profile.source_license
        for evidence in profile.evidence:
            if evidence.kind != "claims-registry":
                continue
            assert evidence.evidence_id in claims
            assert (root / evidence.source).is_file()


def test_declared_sequence_order_is_preserved() -> None:
    profile = AnnotationProfile(
        profile_id="ordered-v1",
        source_convention="fixture",
        source_revision="r1",
        source_license="CC0-1.0",
        compatibility="canonical",
        output_fields=("LEMMA", "FORM", "UPOS"),
        relation_scheme="fixture",
        normalization=("NFD", "NFC"),
        model_segmentation="model",
        document_segmentation="document",
        mappings=(),
        supported_domains=(),
        raw_requirements=("second", "first"),
        ambiguities=(),
        evidence=(),
    )
    restored = AnnotationProfile.from_json(profile.to_json())
    assert restored.output_fields == ("LEMMA", "FORM", "UPOS")
    assert restored.normalization == ("NFD", "NFC")
    assert restored.raw_requirements == ("second", "first")
