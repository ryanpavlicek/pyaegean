"""Tests for the PROIEL UD-fold convention decomposition (aegean.greek.proiel).

The published UD-PROIEL UFeats/UAS/LAS are capped by annotation-convention divergence; these
tests check the MEASUREMENT that separates that cap from real disagreement. All offline: the
decomposition core runs on synthetic folds whose convention split is known by construction, and
one end-to-end test reproduces the recomputed metrics against the official CoNLL-18 evaluator
(cached) so the decomposition is proven faithful to the published numbers, not a new metric.

The decomposition changes NO published number and fits nothing to the fold; the correctness
tests here pin the exact known-by-construction numbers, the reproduction test pins faithfulness,
and the adversarial tests pin the empty / all-shared / all-absent / malformed edges."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegean.greek.proiel import (
    ConventionReport,
    NeuralPipelineRequiredError,
    _decompose_conventions,
    _MODEL_FEATURE_TYPES,
    _UNIVERSAL_FEATURES,
    proiel_convention_report,
)

# (feats, head, deprel) per token — the fields the decomposition compares.
_ConvTok = tuple[str, int, str]


# --- the model's emittable feature inventory is pinned against renderer drift ---------


def test_model_feature_types_are_the_ten_agdt_scheme_features() -> None:
    # udfeats.feats_from_xpos renders exactly these 10 UD feature types from the 9-position
    # AGDT postag. A change to the renderer that adds/drops a type must trip this pin.
    assert _MODEL_FEATURE_TYPES == {
        "Person", "Number", "Tense", "Aspect", "Mood", "VerbForm", "Voice",
        "Gender", "Case", "Degree",
    }
    # every emittable type is a universal feature the evaluator scores
    assert _MODEL_FEATURE_TYPES <= _UNIVERSAL_FEATURES


def test_universal_features_absent_from_the_model_scheme() -> None:
    # the scheme-absent universal features (PROIEL can use, the model can never emit) include
    # the article's Definite and the pronoun PronType — the drivers of the UFeats convention gap
    absent = _UNIVERSAL_FEATURES - _MODEL_FEATURE_TYPES
    assert {"Definite", "PronType", "Polarity", "Poss", "Reflex"} <= absent


# --- decomposition correctness on a fold whose split is known by construction ----------


def _known_fold() -> tuple[list[list[_ConvTok]], list[list[_ConvTok]]]:
    """A 5-word fold engineered so every count below is hand-verifiable."""
    gold = [
        [
            ("Case=Nom|Definite=Def", 2, "det"),               # Definite is scheme-absent
            ("Case=Nom|Gender=Masc|Number=Sing", 0, "root"),
            ("Case=Acc|Gender=Fem", 2, "obj"),
        ],
        [
            ("_", 2, "cc"),
            ("PronType=Dem|Case=Gen", 0, "root"),              # PronType is scheme-absent
        ],
    ]
    system = [
        [
            ("Case=Nom", 2, "det"),                            # missing Definite → UFeats miss (blocked)
            ("Case=Nom|Gender=Masc|Number=Sing", 0, "root"),   # exact → correct
            ("Case=Nom|Gender=Fem", 2, "obl"),                 # Case value wrong + relabel obj→obl
        ],
        [
            ("_", 2, "cc"),                                    # exact → correct
            ("Case=Gen", 0, "root"),                           # missing PronType → UFeats miss (blocked)
        ],
    ]
    return gold, system


def test_ufeats_convention_split_is_exact() -> None:
    r = _decompose_conventions(*_known_fold())
    assert r.n_words == 5
    assert r.ufeats_correct == 2                 # only the two exact-bundle matches
    assert r.ufeats == pytest.approx(0.4)
    # two words carry a scheme-absent feature (Definite, PronType) → unavoidable misses
    assert r.n_scheme_blocked_words == 2
    assert r.n_shared_only_words == 3
    assert r.shared_only_correct == 2            # the exact match + the empty-feats word
    assert r.shared_subset_ufeats == pytest.approx(2 / 3)
    # the two additive parts of the gap
    assert r.gap_scheme_absent == pytest.approx(0.4)
    assert r.gap_shared_disagreement == pytest.approx(0.2)


def test_ufeats_gap_is_additive() -> None:
    r = _decompose_conventions(*_known_fold())
    assert r.gap_scheme_absent + r.gap_shared_disagreement == pytest.approx(r.ufeats_gap)


def test_per_feature_table_is_exact() -> None:
    r = _decompose_conventions(*_known_fold())
    by = {s.feature: s for s in r.feature_stats}
    # Case appears on 4 gold words; the model agrees on 3 of the 4 values (Acc→Nom is the miss)
    assert by["Case"].gold_count == 4
    assert by["Case"].emitted_by_model_scheme is True
    assert by["Case"].agreement_on_shared == pytest.approx(0.75)
    # scheme-absent features: counted, flagged, zero agreement
    assert by["Definite"].gold_count == 1 and by["Definite"].emitted_by_model_scheme is False
    assert by["Definite"].agreement_on_shared == 0.0
    assert by["PronType"].emitted_by_model_scheme is False
    assert by["Gender"].gold_count == 2 and by["Gender"].agreement_on_shared == pytest.approx(1.0)
    # scheme_absent_features helper surfaces exactly the two, by count
    assert {s.feature for s in r.scheme_absent_features} == {"Definite", "PronType"}
    # feature_stats sorted by gold_count desc
    counts = [s.gold_count for s in r.feature_stats]
    assert counts == sorted(counts, reverse=True)


def test_las_convention_split_is_exact() -> None:
    r = _decompose_conventions(*_known_fold())
    assert r.uas_correct == 5 and r.uas == pytest.approx(1.0)   # every head matches gold
    assert r.las_correct == 4 and r.las == pytest.approx(0.8)
    assert r.label_only_errors == 1                            # obj→obl, attachment was right
    assert r.label_only_share == pytest.approx(0.2)
    assert len(r.deprel_confusions) == 1
    top = r.deprel_confusions[0]
    assert (top.gold, top.predicted, top.count) == ("obj", "obl", 1)
    assert r.deprel_top_share == pytest.approx(1.0)


def test_las_identity_uas_minus_las_is_label_only() -> None:
    r = _decompose_conventions(*_known_fold())
    assert r.uas - r.las == pytest.approx(r.label_only_share)
    assert r.las_correct == r.uas_correct - r.label_only_errors


def test_deprel_subtypes_are_stripped_like_the_evaluator() -> None:
    # gold obl:arg vs predicted obl is a MATCH (LAS ignores subtypes); nsubj:pass vs obj is not
    gold = [[("_", 0, "root"), ("_", 1, "obl:arg"), ("_", 1, "nsubj:pass")]]
    system = [[("_", 0, "root"), ("_", 1, "obl"), ("_", 1, "obj")]]
    r = _decompose_conventions(gold, system)
    assert r.las_correct == 2                       # root + obl:arg/obl
    assert r.label_only_errors == 1
    top = r.deprel_confusions[0]
    assert (top.gold, top.predicted, top.count) == ("nsubj", "obj", 1)


def test_language_specific_features_are_dropped_before_scoring() -> None:
    # a non-universal feature (InflClass) the evaluator ignores must not be counted, must not
    # block, and must not appear in the per-feature table
    gold = [[("Case=Nom|InflClass=IndEurX", 0, "root")]]
    system = [[("Case=Nom", 0, "root")]]
    r = _decompose_conventions(gold, system)
    assert r.ufeats_correct == 1                     # InflClass dropped → both sides {Case=Nom}
    assert r.n_scheme_blocked_words == 0             # InflClass isn't a scored scheme-absent type
    assert {s.feature for s in r.feature_stats} == {"Case"}


# --- faithfulness: recomputed metrics reproduce the official evaluator ------------------


def _emit_conllu(forms: list[list[str]], toks: list[list[_ConvTok]]) -> str:
    """A CoNLL-U string from parallel forms + (feats, head, deprel) tokens."""
    out: list[str] = []
    for si, (sent_forms, sent_toks) in enumerate(zip(forms, toks), start=1):
        out.append(f"# sent_id = s{si}")
        for i, (form, (feats, head, deprel)) in enumerate(zip(sent_forms, sent_toks), start=1):
            out.append("\t".join((str(i), form, "_", "_", "_", feats, str(head), deprel, "_", "_")))
        out.append("")
    return "\n".join(out) + "\n"


def _eval_available() -> object | None:
    from aegean.data import cache_dir
    from aegean.greek.ud import _CACHE_SUBDIR, _eval_module

    if not (cache_dir() / _CACHE_SUBDIR / "conll18_ud_eval.py").exists():
        try:
            return _eval_module()
        except Exception:
            return None
    return _eval_module()


def test_recomputed_metrics_match_the_official_evaluator(tmp_path: Path) -> None:
    """The published-row-unchanged invariant: the decomposition's ufeats/uas/las reproduce the
    official CoNLL-18 evaluator EXACTLY on the same predictions, so it accounts for the published
    number rather than replacing it with a different measurement."""
    ev = _eval_available()
    if ev is None:
        pytest.skip("official evaluator unavailable offline")

    forms = [["ὁ", "λόγος", "ἦν"], ["καὶ", "θεός"]]
    gold_toks: list[list[_ConvTok]] = [
        [
            ("Case=Nom|Definite=Def", 2, "det"),
            ("Case=Nom|Gender=Masc|Number=Sing", 3, "nsubj"),
            ("Mood=Ind|Number=Sing|Person=3|Tense=Past|VerbForm=Fin|Voice=Act", 0, "root"),
        ],
        [("_", 2, "cc"), ("Case=Nom|Gender=Masc|Number=Sing", 0, "root")],
    ]
    pred_toks: list[list[_ConvTok]] = [
        [
            ("Case=Nom", 2, "det"),                             # missing Definite → UFeats miss
            ("Case=Nom|Gender=Masc|Number=Sing", 3, "obj"),     # relabel nsubj→obj (label-only)
            ("Mood=Ind|Number=Sing|Person=3|Tense=Past|VerbForm=Fin|Voice=Act", 0, "root"),
        ],
        [("_", 2, "cc"), ("Case=Nom|Gender=Masc|Number=Sing", 0, "root")],
    ]
    gold_path = tmp_path / "gold.conllu"
    gold_path.write_text(_emit_conllu(forms, gold_toks), encoding="utf-8")

    report = proiel_convention_report(source=gold_path, predictions=pred_toks)

    from aegean.greek.ud import _score_conllu_text

    official = _score_conllu_text(
        ev, gold_path.read_text(encoding="utf-8"), _emit_conllu(forms, pred_toks),
        ["ufeats", "uas", "las"],
    )
    assert report.ufeats == pytest.approx(official["ufeats"], abs=1e-9)
    assert report.uas == pytest.approx(official["uas"], abs=1e-9)
    assert report.las == pytest.approx(official["las"], abs=1e-9)
    # and the hand-computed values, for good measure
    assert report.ufeats == pytest.approx(0.8)   # 4/5 bundles match
    assert report.las == pytest.approx(0.8)       # 1 label-only error out of 5
    assert report.uas == pytest.approx(1.0)


# --- adversarial edges -----------------------------------------------------------------


def test_empty_fold_is_all_zero_no_division_error() -> None:
    r = _decompose_conventions([], [])
    assert isinstance(r, ConventionReport)
    assert r.n_words == 0
    assert r.ufeats == 0.0 and r.uas == 0.0 and r.las == 0.0
    assert r.shared_subset_ufeats == 0.0 and r.gap_scheme_absent == 0.0
    assert r.deprel_top_share == 0.0 and r.deprel_concentration(5) == 0.0
    assert r.summary() == "PROIEL convention decomposition: no words"
    assert r.scheme_absent_features == ()


def test_all_shared_scheme_no_convention_gap() -> None:
    gold = [[("Case=Nom|Gender=Masc|Number=Sing", 0, "root"), ("Case=Gen", 1, "nmod")]]
    r = _decompose_conventions(gold, gold)          # perfect prediction
    assert r.n_scheme_blocked_words == 0
    assert r.gap_scheme_absent == 0.0
    assert r.ufeats == pytest.approx(1.0) and r.shared_subset_ufeats == pytest.approx(1.0)
    assert r.scheme_absent_features == ()


def test_all_scheme_absent_shared_subset_is_empty() -> None:
    # every word carries Definite (scheme-absent) → no shared-only words, no crash
    gold = [[("Definite=Def", 0, "root"), ("Definite=Ind|Case=Acc", 1, "obj")]]
    system = [[("_", 0, "root"), ("Case=Acc", 1, "obj")]]
    r = _decompose_conventions(gold, system)
    assert r.n_scheme_blocked_words == 2 and r.n_shared_only_words == 0
    assert r.gap_scheme_absent == pytest.approx(r.ufeats_gap)
    assert r.shared_subset_ufeats == 0.0            # guarded: n_shared_only == 0
    assert r.ufeats == 0.0                          # neither bundle can match


def test_length_mismatch_raises() -> None:
    # gold/prediction sentence-count mismatch is a loud error, not a silent wrong result
    with pytest.raises(ValueError):
        _decompose_conventions([[("_", 0, "root")]], [])
    # token-count mismatch within a sentence too
    with pytest.raises(ValueError):
        _decompose_conventions([[("_", 0, "root"), ("_", 1, "obj")]], [[("_", 0, "root")]])


def test_report_without_pipeline_or_predictions_raises(tmp_path: Path) -> None:
    from aegean.greek import joint

    if joint.active() is not None:
        pytest.skip("neural pipeline is active in this session")
    gold_path = tmp_path / "g.conllu"
    gold_path.write_text("# sent_id = s1\n1\tλόγος\t_\t_\t_\t_\t0\troot\t_\t_\n\n", encoding="utf-8")
    with pytest.raises(NeuralPipelineRequiredError):
        proiel_convention_report(source=gold_path)


def test_public_function_loads_gold_from_conllu(tmp_path: Path) -> None:
    # proiel_convention_report reads FEATS/HEAD/DEPREL from a CoNLL-U fold and decomposes it
    gold_path = tmp_path / "g.conllu"
    gold_path.write_text(
        "# sent_id = s1\n"
        "1\tτὸ\tὁ\tDET\t_\tCase=Nom|Definite=Def\t2\tdet\t_\t_\n"
        "2\tἔργον\tἔργον\tNOUN\t_\tCase=Nom|Gender=Neut|Number=Sing\t0\troot\t_\t_\n\n",
        encoding="utf-8",
    )
    preds: list[list[_ConvTok]] = [
        [("Case=Nom", 2, "det"), ("Case=Nom|Gender=Neut|Number=Sing", 0, "root")]
    ]
    r = proiel_convention_report(source=gold_path, predictions=preds)
    assert r.n_words == 2
    assert r.n_scheme_blocked_words == 1            # the article carries Definite
    assert r.shared_only_correct == 1              # ἔργον matches exactly
    assert r.las == pytest.approx(1.0)             # heads + labels all right
