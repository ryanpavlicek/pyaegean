"""Clause and tense evidence stays faithful to supplied, fallible Greek analysis.

The retained PapyGreek annotation controls the clause organization here. These
tests validate evidence presentation, not the accuracy of a neural parser or an
English translation. Deliberately wrong/missing parses remain wrong/missing.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from aegean import translate
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.pipeline import TokenRecord
from aegean.greek.udfeats import feats_from_xpos
from aegean.translate import _clause_skeleton, _morphology_items


def _token(
    index: int,
    text: str,
    upos: str,
    lemma: str,
    head: int | None,
    relation: str | None,
    feats: str | None = None,
    *,
    sentence: int = 0,
) -> TokenRecord:
    return TokenRecord(
        sentence=sentence, index=index, text=text, upos=upos, lemma=lemma,
        lemma_source=LemmaSource.ATTESTED, head=head, relation=relation, feats=feats,
    )


@pytest.fixture
def papyrus() -> list[TokenRecord]:
    """The source fixture for 'I want you to know that Valeria and I hope…'."""
    fixture = Path(__file__).parent / "fixtures" / "papygreek" / "sample.conllu"
    selected = False
    records = []
    for line in fixture.read_text(encoding="utf-8").splitlines():
        if line.startswith("# sent_id = "):
            selected = line == "# sent_id = papygreek:bgu.1.261@2"
        if not selected or not line or line.startswith("#"):
            continue
        index, text, lemma, upos, _xpos, feats, head, relation, *_ = line.split("\t")
        records.append(_token(
            int(index), text, upos, lemma, int(head), relation,
            None if feats == "_" else feats,
        ))
    assert len(records) == 16
    return records


@pytest.fixture(autouse=True)
def no_optional_rarity(monkeypatch: pytest.MonkeyPatch) -> None:
    # The controlled fixture needs no downloaded reference corpus.
    monkeypatch.setattr(translate, "_rare_word_line", lambda text, *, analysis: "")


def _clause(skeleton: str, word: str) -> str:
    return next(part for part in skeleton.split(" | ") if f"predicate '{word}'" in part)


def test_papyrus_preserves_subordinate_and_coordinated_subjects(papyrus):
    skeleton = _clause_skeleton(papyrus)
    wanting = _clause(skeleton, "θέλω")
    knowing = _clause(skeleton, "γιγνώσκειν")
    hoping = _clause(skeleton, "εὐχόμεθα")
    birth = _clause(skeleton, "τέκῃ")
    coming = _clause(skeleton, "ἐλθεῖν")

    assert "no explicit subject in supplied parse" in wanting
    assert "ἐγὼ" not in wanting and "Οὐαλερία" not in wanting
    assert "subject σε" in knowing and "dependency ccomp → 'θέλω'" in knowing
    assert "subject ἐγὼ + Οὐαλερία (coordination: καὶ)" in hoping
    assert "dependency ccomp → 'γιγνώσκειν'" in hoping
    assert "subject Ἡροὶς" in birth and "marked by ἐὰν" in birth
    assert "dependency advcl → 'εὐχόμεθα'" in birth
    assert "τίκτω" in birth and "past-tag subj finite" in birth
    assert "no tense-time inference" in birth
    assert "dependency xcomp → 'εὐχόμεθα'" in coming
    assert "past-tag infinitive" in coming and "no tense-time inference" in coming
    assert "no explicit subject in supplied parse" in coming


def test_wrong_attachment_is_visible_and_never_repaired(papyrus):
    wrong = [replace(r, head=3) if r.index == 4 else r for r in papyrus]
    skeleton = _clause_skeleton(wrong)
    assert "subject ἐγὼ + Οὐαλερία" in _clause(skeleton, "θέλω")
    assert "no explicit subject in supplied parse" in _clause(skeleton, "εὐχόμεθα")
    items = _morphology_items("", analysis=wrong)
    syntax = next(item for item in items if item.source == "analysis:syntax")
    assert syntax.status == "predicted"
    assert "Attachments may be wrong" in syntax.content
    assert "subjects are not inferred" in syntax.content
    assert syntax.provenance["inferred_subjects"] is False
    subject = next(item for item in items if item.ref == "ἐγὼ")
    assert subject.provenance["head"] == 3
    assert subject.provenance["relation"] == "nsubj"


def test_missing_parse_does_not_fabricate_clause_structure(papyrus):
    unparsed = [replace(r, head=None, relation=None) for r in papyrus]
    assert _clause_skeleton(unparsed) == ""
    items = _morphology_items("", analysis=unparsed)
    assert not any(item.source == "analysis:syntax" for item in items)
    assert len(items) == sum(r.upos != "PUNCT" for r in papyrus)
    assert all(item.status == "predicted" for item in items)
    assert all(item.provenance["field_status"]["head"] == "unavailable" for item in items)


@pytest.mark.parametrize(
    ("features", "rendered", "no_time_inference"),
    [
        ("Tense=Past|Mood=Sub|VerbForm=Fin", "past-tag subj finite", True),
        ("Tense=Past|VerbForm=Inf", "past-tag infinitive", True),
        ("Tense=Past|VerbForm=Part", "past-tag participle", True),
        ("Tense=Past|VerbForm=Fin", "past-tag finite", True),
        ("Tense=Past|Aspect=Perf|Mood=Sub", "past-tag Aspect=Perf subj", True),
        ("Tense=Past|Aspect=Imp|Mood=Ind", "past-tag Aspect=Imp ind", False),
        ("Tense=Aor|Mood=Sub", "aorist-form subj", True),
        ("Tense=Pres|VerbForm=Inf", "pres infinitive", True),
        ("Tense=Fut|Mood=Opt", "fut opt", True),
    ],
)
def test_tense_evidence_preserves_form_and_raw_ud_features(features, rendered, no_time_inference):
    record = _token(1, "form", "VERB", "lemma", None, None, features)
    item, = _morphology_items("", analysis=[record])
    assert rendered in item.content
    assert f"UD FEATS: {features}" in item.content
    assert item.provenance["raw_feats"] == features
    assert item.provenance["field_status"]["feats"] == "predicted"
    assert ("no tense-time inference" in item.content) is no_time_inference
    if "Tense=Past" in features:
        assert "it alone does not identify Greek tense/aspect or event time" in item.content
        assert "aorist-form" not in item.content


def test_no_features_produces_no_fabricated_tense_or_mood():
    item, = _morphology_items("", analysis=[_token(1, "form", "VERB", "lemma", None, None)])
    assert item.content == "form = lemma (verb)"
    assert item.provenance["raw_feats"] is None
    assert item.provenance["field_status"]["feats"] == "unavailable"


def test_perseus_perfect_participle_is_not_reinterpreted_as_perfective_or_aorist():
    # The supplying convention maps perfect XPOS 'r' to Tense=Past|Aspect=Perf.
    # A universal-language gloss of Perf as 'perfective' would misdescribe it.
    features = feats_from_xpos("v-srpamn-")
    assert "Tense=Past" in features and "Aspect=Perf" in features
    record = _token(1, "γεγραφώς", "VERB", "γράφω", None, None, features)
    item, = _morphology_items("", analysis=[record])
    assert "past-tag Aspect=Perf participle" in item.content
    assert "Aspect tags retain the supplying dataset's convention" in item.content
    assert "perfective" not in item.content and "aorist-form" not in item.content
    assert "no tense-time inference" in item.content


def test_nested_copular_clause_retains_its_copula_and_subject():
    records = [
        _token(1, "λέγει", "VERB", "λέγω", 0, "root"),
        _token(2, "ἀγαθός", "ADJ", "ἀγαθός", 1, "ccomp"),
        _token(3, "ἐστιν", "AUX", "εἰμί", 2, "cop"),
        _token(4, "θεός", "NOUN", "θεός", 2, "nsubj"),
    ]
    main, subordinate = _clause_skeleton(records).split(" | ")
    assert "no explicit subject in supplied parse" in main
    assert subordinate == (
        "predicate ἐστιν + ἀγαθός (predicate adjective); "
        "dependency ccomp → 'λέγει'; subject θεός"
    )


def test_dependency_indices_never_join_across_sentences():
    records = [
        _token(1, "γράφει", "VERB", "γράφω", 0, "root"),
        _token(2, "ἄνθρωπος", "NOUN", "ἄνθρωπος", 1, "nsubj"),
        _token(1, "ἀγαθός", "ADJ", "ἀγαθός", 0, "root", sentence=1),
        _token(2, "θεός", "NOUN", "θεός", 1, "nsubj", sentence=1),
        _token(3, "ἐστιν", "AUX", "εἰμί", 1, "cop", sentence=1),
        _token(4, "οἶδε", "VERB", "οἶδα", 1, "ccomp", sentence=1),
    ]
    first, second, subordinate = _clause_skeleton(records).split(" | ")
    assert "subject ἄνθρωπος" in first and "θεός" not in first and "ἐστιν" not in first
    assert "predicate ἐστιν + ἀγαθός" in second and "subject θεός" in second
    assert "ἄνθρωπος" not in second
    assert "dependency ccomp → 'ἀγαθός'" in subordinate and "γράφει" not in subordinate


def test_unavailable_governor_is_reported_without_cross_sentence_lookup():
    records = [
        _token(1, "λέγει", "VERB", "λέγω", 0, "root"),
        _token(2, "οἶδε", "VERB", "οἶδα", 1, "ccomp", sentence=1),
    ]
    skeleton = _clause_skeleton(records)
    assert "dependency ccomp → unavailable token 1" in _clause(skeleton, "οἶδε")


def test_coordinated_predicate_does_not_inherit_a_subject():
    records = [
        _token(1, "γράφει", "VERB", "γράφω", 0, "root"),
        _token(2, "ἄνθρωπος", "NOUN", "ἄνθρωπος", 1, "nsubj:pass"),
        _token(3, "λέγει", "VERB", "λέγω", 1, "conj"),
    ]
    main, coordinated = _clause_skeleton(records).split(" | ")
    assert "subject ἄνθρωπος" in main
    assert "coordinated predicate 'λέγει'" in coordinated
    assert "no explicit subject in supplied parse" in coordinated
    assert "ἄνθρωπος" not in coordinated


def test_coordinated_nominal_predicate_with_own_subject_does_not_invent_copula():
    records = [
        _token(1, "σοφός", "ADJ", "σοφός", 0, "root"),
        _token(2, "ἐστι", "AUX", "εἰμί", 1, "cop"),
        _token(3, "ἀνὴρ", "NOUN", "ἀνήρ", 1, "nsubj"),
        _token(4, "ἀγαθή", "ADJ", "ἀγαθός", 1, "conj"),
        _token(5, "γυνὴ", "NOUN", "γυνή", 4, "nsubj"),
    ]
    main, coordinated = _clause_skeleton(records).split(" | ")
    assert "predicate ἐστι + σοφός" in main and "subject ἀνὴρ" in main
    assert "coordinated predicate 'ἀγαθή'" in coordinated
    assert "dependency conj → 'σοφός'" in coordinated and "subject γυνὴ" in coordinated
    assert "ἐστι" not in coordinated and "ἀνὴρ" not in coordinated


def test_long_evidence_marks_omitted_predicates_and_coordination():
    records = [_token(1, "root", "VERB", "root", 0, "root")]
    records.extend(_token(i, f"verb{i}", "VERB", f"lemma{i}", 1, "ccomp") for i in range(2, 19))
    records.append(_token(19, "subject", "NOUN", "subject", 1, "nsubj"))
    records.extend(_token(i, f"person{i}", "NOUN", f"person{i}", 19, "conj") for i in range(20, 31))
    skeleton = _clause_skeleton(records)
    assert "(6 further predicates omitted)" in skeleton
    assert "(4 coordinated tokens omitted)" in skeleton
    assert "predicate 'verb18'" not in skeleton
    assert "person30" not in skeleton
    item = next(item for item in _morphology_items("", analysis=records) if item.source == "analysis:syntax")
    assert item.provenance["limits"] == {"predicates": 12, "role_tokens": 8, "markers": 4}
