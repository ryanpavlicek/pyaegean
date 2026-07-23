"""Focused contracts for the canonical Greek joint-training dataset builder."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).parent.parent / "training"
sys.path.insert(0, str(_DIR))
spec = importlib.util.spec_from_file_location(
    "build_full_dataset_canonical", _DIR / "build_full_dataset.py"
)
assert spec is not None and spec.loader is not None
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_builder_help_is_safe_for_default_console_encoding() -> None:
    result = subprocess.run(
        [sys.executable, str(_DIR / "build_full_dataset.py"), "--help"],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "--with-extras" in result.stdout


def _word(
    token_id: int,
    head: int,
    relation: str,
    *,
    form: str = "λόγος",
    lemma: str = "λόγος",
    xpos: str = "n-s---mn-",
) -> dict[str, str]:
    return {
        "id": str(token_id),
        "head": str(head),
        "relation": relation,
        "form": form,
        "lemma": lemma,
        "xpos": xpos,
        "source_head": str(head),
        "source_relation": relation,
        "source_xpos": xpos,
        "source_lemma": lemma,
    }


def test_policy_is_bound_to_all_three_source_revisions() -> None:
    policy = builder.load_label_policy()
    assert policy["policy_id"] == "greek-joint-canonical-v3"
    assert set(policy["sources"]) == {"agdt", "gorman", "pedalion"}
    assert all(len(source["revision"]) == 40 for source in policy["sources"].values())
    assert "punctuation_lemma" in policy["shared_rules"]
    assert "lemma_grave_accent" in policy["shared_rules"]
    # The interrogative-lemma and non-cc coordinator migrations are deliberately
    # absent: they contradict the pinned evaluation folds' own conventions.
    assert "interrogative_tis_lemma" not in policy["shared_rules"]


def test_leaf_apos_is_appos_and_original_labels_remain_addressable() -> None:
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 1, "APOS", form="Σωκράτης", lemma="Σωκράτης"),
    ]
    row = builder.row_from_attrs("toy.xml", "1", attrs)
    assert row["deprel"] == ["root", "appos"]
    assert row["source"] == "agdt"
    assert row["source_token_ids"] == ["1", "2"]
    assert len(row["source_label_sha256"]) == 64
    assert row["source_label_sha256"] == builder._source_label_sha256(attrs)
    attrs[1]["source_relation"] = "ATR"
    assert row["source_label_sha256"] != builder._source_label_sha256(attrs)


def test_structurally_confirmed_coordinator_normalizes_pedalion_b_to_cconj() -> None:
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 1, "COORD", form="δὲ", lemma="δέ", xpos="b--------"),
    ]
    audit: dict[str, object] = {}
    row = builder.row_from_attrs("pedalion:toy.xml", "1", attrs, source="pedalion", audit=audit)
    assert row["deprel"][1] == "cc"
    assert row["xpos"][1] == "c--------"
    assert row["upos"][1] == "CCONJ"
    summary = builder._finalize_audit(audit)
    assert summary["pedalion"]["upos_changes"] == {"X->CCONJ": 1}
    assert summary["pedalion"]["xpos_changes"] == {"b--------->c--------": 1}


def test_ambiguous_auxy_use_is_not_flattened_into_coordination() -> None:
    # AuxY never becomes deprel cc, and non-cc coordinators are never migrated
    # to CCONJ: the pinned evaluation folds disagree with each other on that
    # convention (Perseus dev is ADV-majority, PapyGreek CCONJ-majority), so
    # both καί and δέ take the Pedalion particle mapping to ADV.
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 1, "AuxY", form="καὶ", lemma="καί", xpos="b--------"),
        _word(3, 1, "AuxY", form="δὲ", lemma="δέ", xpos="b--------"),
    ]
    row = builder.row_from_attrs("pedalion:toy.xml", "1", attrs, source="pedalion")
    assert row["deprel"][1] == "advmod" and row["deprel"][2] == "advmod"
    assert row["upos"][1] == "ADV" and row["xpos"][1] == "d--------"
    assert row["upos"][2] == "ADV" and row["xpos"][2] == "d--------"


def test_coordinator_pos_is_unchanged_when_surface_is_outside_closed_lexicon() -> None:
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 1, "COORD", form="λόγος", lemma="λόγος", xpos="b--------"),
    ]
    row = builder.row_from_attrs("pedalion:toy.xml", "1", attrs, source="pedalion")
    assert row["deprel"][1] == "cc"
    assert row["xpos"][1] == "b--------"
    assert row["upos"][1] == "X"


def test_punctuation_placeholder_lemma_becomes_the_mark_itself() -> None:
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 1, "AuxX", form=",", lemma="punc", xpos="u--------"),
        _word(3, 1, "AuxK", form="·", lemma="punc", xpos="u--------"),
        _word(4, 1, "AuxG", form="<", lemma="punc", xpos="u--------"),
    ]
    audit: dict[str, object] = {}
    row = builder.row_from_attrs("gorman:toy.xml", "1", attrs, source="gorman", audit=audit)
    assert row["lemma"] == ["λέγω", ",", "·", "<"]
    summary = builder._finalize_audit(audit)
    assert summary["gorman"]["lemma_changes"] == {
        "punc->,": 1,
        "punc->·": 1,
        "punc-><": 1,
    }


def test_punctuation_placeholder_lemma_is_kept_on_a_word_form() -> None:
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="punc", xpos="v3spia---"),
    ]
    row = builder.row_from_attrs("gorman:toy.xml", "1", attrs, source="gorman")
    assert row["lemma"] == ["punc"]


def test_grave_accent_lemmas_are_rewritten_to_the_acute_citation_form() -> None:
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 1, "AuxC", form="ἢ", lemma="ἢ", xpos="c--------"),
        _word(3, 1, "AuxZ", form="μὴ", lemma="μὴ", xpos="d--------"),
        _word(4, 1, "ATR", form="ἀγαθὸς", lemma="ἀγαθός", xpos="a-s---mn-"),
    ]
    audit: dict[str, object] = {}
    row = builder.row_from_attrs("toy.xml", "1", attrs, audit=audit)
    assert row["lemma"] == ["λέγω", "ἤ", "μή", "ἀγαθός"]
    summary = builder._finalize_audit(audit)
    assert summary["agdt"]["lemma_changes"] == {"ἢ->ἤ": 1, "μὴ->μή": 1}


def test_correct_lemmas_pass_through_canonicalization_unchanged() -> None:
    for form, lemma in (
        (",", ","),
        ("λέγει", "λέγω"),
        ("ἤ", "ἤ"),
        ("Σωκράτης", "Σωκράτης"),
    ):
        assert builder._canonical_lemma(form, lemma) == lemma


def test_closed_set_lemma_with_cc_becomes_cconj_beyond_the_surface_lexicon() -> None:
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 1, "COORD", form="ἠδ̓", lemma="ἠδέ", xpos="g--------"),
    ]
    row = builder.row_from_attrs("toy.xml", "1", attrs)
    assert row["deprel"][1] == "cc"
    assert row["xpos"][1] == "c--------"
    assert row["upos"][1] == "CCONJ"


def test_pedalion_particle_coordinator_with_auxy_becomes_adv_not_x() -> None:
    attrs = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 1, "AuxY", form="καὶ", lemma="καί", xpos="b--------"),
    ]
    row = builder.row_from_attrs("pedalion:toy.xml", "1", attrs, source="pedalion")
    assert row["deprel"][1] == "advmod"
    assert row["xpos"][1] == "d--------"
    assert row["upos"][1] == "ADV"


def test_non_cc_coordinators_keep_their_source_labels() -> None:
    # The pinned evaluation folds contradict each other on the non-cc
    # coordinator convention, so ἀλλά, δέ, and τε keep their source POS
    # whenever the conversion did not emit cc — even in clearly connective or
    # coordination-adjacent contexts.
    attrs = [
        _word(1, 2, "AuxY", form="ἀλλὰ", lemma="ἀλλά", xpos="d--------"),
        _word(2, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(3, 2, "AuxY", form="δὲ", lemma="δέ", xpos="d--------"),
    ]
    row = builder.row_from_attrs("toy.xml", "1", attrs)
    assert row["upos"][0] == "ADV" and row["xpos"][0] == "d--------"
    assert row["upos"][2] == "ADV" and row["xpos"][2] == "d--------"
    # τε beside real coordination structure still keeps its source POS.
    coordinated = [
        _word(1, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(2, 4, "OBJ_CO", form="λόγους", lemma="λόγος", xpos="n-p---ma-"),
        _word(3, 2, "AuxY", form="τε", lemma="τε", xpos="d--------"),
        _word(4, 1, "COORD", form="καὶ", lemma="καί", xpos="c--------"),
        _word(5, 4, "OBJ_CO", form="μύθους", lemma="μῦθος", xpos="n-p---ma-"),
    ]
    row = builder.row_from_attrs("toy.xml", "2", coordinated)
    assert row["deprel"][1] == "obj" and row["deprel"][4] == "conj"
    assert row["upos"][2] == "ADV" and row["xpos"][2] == "d--------"


def test_cop_attached_eimi_is_aux_never_verb() -> None:
    upos = ["NOUN", "VERB", "ADJ"]
    tree = [(3, "nsubj"), (3, "cop"), (0, "root")]
    attrs = [
        {"lemma": "ἄνθρωπος"},
        {"lemma": "εἰμί"},
        {"lemma": "ἀγαθός"},
    ]
    assert builder._copula_upos_pass(attrs, upos, tree) == ["NOUN", "AUX", "ADJ"]
    # a VERB eimi that is not cop stays VERB (existential main verb)
    tree_root = [(2, "nsubj"), (0, "root"), (2, "obl")]
    assert builder._copula_upos_pass(attrs, upos, tree_root)[1] == "VERB"


def test_en_surface_never_carries_lemma_eis() -> None:
    attrs = [
        _word(1, 2, "AuxP", form="ἐν", lemma="εἰς", xpos="r--------"),
        _word(2, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
    ]
    row = builder.row_from_attrs("toy.xml", "1", attrs)
    assert row["lemma"][0] == "ἐν"


def test_suppletive_aorist_eip_forms_take_lemma_eipon() -> None:
    attrs = [
        _word(1, 0, "PRED", form="εἶπεν", lemma="λέγω", xpos="v3saia---"),
        _word(2, 1, "OBJ", form="λόγον", lemma="λέγω", xpos="n-s---ma-"),
    ]
    row = builder.row_from_attrs("toy.xml", "1", attrs)
    assert row["lemma"][0] == "εἶπον"
    assert row["lemma"][1] == "λέγω"  # non-verb, non-eip form untouched


def test_tis_lemmas_pass_through_unchanged() -> None:
    # PapyGreek's pinned gold lemmatizes the interrogative paradigm under
    # unaccented τις, so the accent-normalization rule is deliberately absent.
    attrs = [
        _word(1, 2, "ATR", form="τίνος", lemma="τις", xpos="p-s---mg-"),
        _word(2, 0, "PRED", form="λέγει", lemma="λέγω", xpos="v3spia---"),
        _word(3, 2, "OBJ", form="τὶ", lemma="τίς", xpos="p-s---na-"),
    ]
    row = builder.row_from_attrs("toy.xml", "1", attrs)
    assert row["lemma"][0] == "τις"
    assert row["lemma"][2] == "τίς"


def test_impersonal_dei_needs_positive_structural_evidence() -> None:
    xpos = ["v3spia---", "n-s---mg-", "v--pna---"]
    tree = [(0, "root"), (1, "obl"), (1, "ccomp")]
    attrs = [
        {"form": "δεῖ", "lemma": "δέω"},
        {"form": "ἀνδρός", "lemma": "ἀνήρ"},
        {"form": "λέγειν", "lemma": "λέγω"},
    ]
    assert builder._lemma_pass(attrs, xpos, tree)[0] == "δεῖ"
    # a nominative subject blocks the impersonal reading
    xpos_subj = ["v3spia---", "n-s---mn-"]
    tree_subj = [(0, "root"), (1, "nsubj")]
    attrs_subj = [{"form": "δεῖ", "lemma": "δέω"}, {"form": "ἀνήρ", "lemma": "ἀνήρ"}]
    assert builder._lemma_pass(attrs_subj, xpos_subj, tree_subj)[0] == "δέω"
    # genitive of quantity (πολλοῦ δεῖ) stays δέω per LSJ δέω B.2
    xpos_quant = ["a-s---mg-", "v3spia---"]
    tree_quant = [(2, "advmod"), (0, "root")]
    attrs_quant = [{"form": "πολλοῦ", "lemma": "πολύς"}, {"form": "δεῖ", "lemma": "δέω"}]
    assert builder._lemma_pass(attrs_quant, xpos_quant, tree_quant)[1] == "δέω"


def test_agdt_loader_skips_protected_identity_before_emission() -> None:
    fixture = Path(__file__).parent / "fixtures" / "ud"
    audit: dict[str, object] = {}
    rows = builder.load_agdt_full(
        fixture,
        skip_ids={("sample.tb.xml", "1")},
        audit=audit,
    )
    assert [(row["file"], row["sid"]) for row in rows] == [("sample.tb.xml", "2")]
    assert builder._finalize_audit(audit)["agdt"]["sentences"] == 1


def test_split_validation_rejects_protected_training_identity() -> None:
    train = [{"file": "source.xml", "sid": "2", "source": "agdt"}]
    dev = [{"file": "source.xml", "sid": "1", "source": "agdt"}]
    builder.validate_split_separation(
        train,
        dev,
        dev_ids={("source.xml", "1")},
        test_ids={("source.xml", "3")},
    )
    train[0]["sid"] = "3"
    with pytest.raises(ValueError, match="protected AGDT"):
        builder.validate_split_separation(
            train,
            dev,
            dev_ids={("source.xml", "1")},
            test_ids={("source.xml", "3")},
        )


def test_manifest_binds_policy_sources_outputs_and_detects_tampering(tmp_path: Path) -> None:
    source = tmp_path / "source.xml"
    source.write_text("<treebank/>", encoding="utf-8")
    for name in (
        "full-train.jsonl",
        "full-dev.jsonl",
        "lemma-scripts.json",
        "lemma-lookup.json",
        "full-stats.json",
    ):
        (tmp_path / name).write_text("{}\n", encoding="utf-8")
    train = [{"file": "train.xml", "sid": "1", "source": "agdt"}]
    dev = [{"file": "dev.xml", "sid": "1", "source": "agdt"}]
    manifest = builder.build_training_manifest(
        output_dir=tmp_path,
        source_paths={"agdt": [source]},
        train=train,
        dev=dev,
        dev_ids={("dev.xml", "1")},
        test_ids={("test.xml", "1")},
        extras_audit=None,
        transform_audit={},
    )
    path = tmp_path / "training-data-manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    checked = builder.verify_training_manifest(path)
    assert checked["policy"]["policy_id"] == "greek-joint-canonical-v3"
    assert checked["policy"]["hash_mode"] == "canonical-json"
    assert checked["policy"]["sha256"] == builder.canonical_sha256(builder.LABEL_POLICY)
    assert checked["sources"]["agdt"]["files"][0]["sha256"] == builder._sha256_file(source)

    (tmp_path / "full-train.jsonl").write_text('{"changed":true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="generated-output record mismatch"):
        builder.verify_training_manifest(path)

    hostile = dict(manifest)
    hostile["outputs"] = [dict(record) for record in manifest["outputs"]]
    hostile["outputs"][0]["path"] = "../full-train.jsonl"
    hostile = builder.stamp_document(hostile, "manifest_sha256")
    path.write_text(json.dumps(hostile, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid generated-output path"):
        builder.verify_training_manifest(path)
