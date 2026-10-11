"""Scholarly field decisions survive CSV, merged sessions, storage, and reanalysis."""

from __future__ import annotations

import csv
import json
import shlex
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegean import greek
from aegean.cli import _build_app, _review
from aegean.core.corpus import Corpus
from aegean.io import from_text
from aegean.io.review import (
    REVIEW_COLUMNS, apply_merged, apply_review_table, from_review_table,
    merge_review_tables, to_review_table,
)


def _corpus() -> Corpus:
    corpus = from_text("\t λόγος  \nνόμου", doc_id="research")
    tokens = [replace(token, annotations={
        "lemma": "λόγος" if token.text == "λόγος" else "νόμος", "upos": "NOUN",
        "feats": "Case=Nom|Number=Sing", "lemma_source": "neural",
        "lemma_verified": "false", "review_recommended": "false",
        "head": "0", "deprel": "root",
    }) for token in corpus.documents[0].tokens]
    return Corpus([replace(corpus.documents[0], tokens=tokens)], provenance=corpus.provenance,
                  script_id=corpus.script_id)


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, str]], columns: tuple[str, ...] = REVIEW_COLUMNS) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _table(path: Path, corpus: Corpus, **edits: str) -> Path:
    to_review_table(corpus, path)
    rows = _read(path)
    rows[0].update(edits)
    _write(path, rows)
    return path


@pytest.mark.parametrize("suffix", ["json", "db"])
@pytest.mark.parametrize("via_cli", [False, True])
def test_accept_unchanged_field_persists_evidence_without_verifying_other_fields(
    tmp_path: Path, suffix: str, via_cli: bool,
) -> None:
    corpus = _corpus()
    original = corpus.to_json()
    source = tmp_path / "source.json"
    corpus.to_json(source)
    table = _table(tmp_path / "review.csv", corpus, decision_lemma="accept",
                   reviewer="Smith, Alice", reviewer_note="checked the cited passage",
                   reviewer_evidence="https://example.org/edition#3")
    output = tmp_path / f"reviewed.{suffix}"
    if via_cli:
        result = CliRunner().invoke(_build_app(), [
            "review", "apply", str(source), str(table), "-o", str(output),
        ])
        assert result.exit_code == 0, result.output
    else:
        result = apply_review_table(table, corpus)
        assert (result.rows, result.corrections, result.corrected, result.decisions, result.reviewed) == (2, 0, 0, 1, 1)
        if suffix == "json":
            result.corpus.to_json(output)
        else:
            result.corpus.to_sql(output)
    reloaded = Corpus.from_json(output) if suffix == "json" else Corpus.from_sql(output)
    ann = reloaded.documents[0].tokens[0].annotations
    assert ann["lemma"] == ann["lemma__pred"] == "λόγος"
    assert ann["lemma_source"] == "neural"
    assert ann["lemma_verified"] == "true" and ann["lemma_review_decision"] == "accept"
    assert ann["lemma_reviewed_by"] == "Smith, Alice"
    assert ann["lemma_review_note"] == "checked the cited passage"
    assert ann["lemma_review_evidence"] == "https://example.org/edition#3"
    assert not any(key in ann for key in ("upos_verified", "feats_verified", "head_verified", "deprel_verified"))
    history = json.loads(ann["review_history"])
    assert len(history) == 1
    assert {key: history[0][key] for key in ("field", "action", "prediction", "value", "reviewer", "note", "evidence")} == {
        "field": "lemma", "action": "accept", "prediction": "λόγος", "value": "λόγος",
        "reviewer": "Smith, Alice", "note": "checked the cited passage",
        "evidence": "https://example.org/edition#3",
    }
    assert to_review_table(reloaded, tmp_path / "remaining.csv", selection="unverified") == 1
    assert corpus.to_json() == original and source.read_text(encoding="utf-8") == original
    assert reloaded.documents[0].source_text == corpus.documents[0].source_text


def test_legacy_unchanged_value_and_note_never_imply_acceptance(tmp_path: Path) -> None:
    corpus = _corpus()
    path = _table(tmp_path / "old.csv", corpus, correct_lemma="λόγος", reviewer_note="a note")
    legacy_columns = ("doc_id", "position", "token", "pred_lemma", "correct_lemma", "reviewer_note")
    _write(path, _read(path), legacy_columns)
    result = apply_review_table(path, corpus, reviewer="Alice")
    assert (result.corrections, result.corrected, result.decisions, result.reviewed) == (1, 0, 0, 0)
    assert result.corpus.to_json() == corpus.to_json()
    rows = _read(path)
    rows[0]["correct_lemma"] = "λέξις"
    _write(path, rows, legacy_columns)
    fixed = from_review_table(path, corpus, reviewer="Alice")
    assert fixed.documents[0].tokens[0].annotations["lemma_review_decision"] == "correct"


@pytest.mark.parametrize("action", ["defer", "reject"])
def test_defer_reject_remove_verification_and_keep_prediction_history(tmp_path: Path, action: str) -> None:
    corpus = _corpus()
    accepted = from_review_table(_table(tmp_path / "accepted.csv", corpus, decision_lemma="accept"), corpus)
    path = _table(tmp_path / "next.csv", accepted, decision_lemma=action, reviewer="Bob",
                  reviewer_note="reading is uncertain", reviewer_evidence="edition p. 5")
    reviewed = from_review_table(path, accepted)
    ann = reviewed.documents[0].tokens[0].annotations
    assert ann["lemma"] == "λόγος" and ann["lemma_verified"] == "false"
    assert ann["lemma_review_decision"] == action and ann["review_recommended"] == "true"
    assert [record["action"] for record in json.loads(ann["review_history"])] == ["accept", action]
    assert to_review_table(reviewed, tmp_path / "remaining.csv", selection="unverified") == 2


def test_correct_again_preserves_first_prediction_and_every_decision(tmp_path: Path) -> None:
    corpus = _corpus()
    first = from_review_table(_table(tmp_path / "a.csv", corpus, decision_lemma="correct",
                                    correct_lemma="λέξις", reviewer="Alice"), corpus)
    second = from_review_table(_table(tmp_path / "b.csv", first, decision_lemma="correct",
                                     correct_lemma="ῥῆμα", reviewer="Bob"), first)
    ann = second.documents[0].tokens[0].annotations
    assert ann["lemma"] == "ῥῆμα" and ann["lemma__pred"] == "λόγος"
    assert ann["lemma_source__pred"] == "neural"
    assert [record["prediction"] for record in json.loads(ann["review_history"])] == ["λόγος", "λέξις"]


@pytest.mark.parametrize("same_prediction", [False, True])
def test_reannotation_marks_affected_decisions_stale_retaining_morphology_review(
    tmp_path: Path, same_prediction: bool,
) -> None:
    corpus = _corpus()
    path = _table(tmp_path / "review.csv", corpus, decision_lemma="accept", decision_pos="accept",
                  decision_morph="accept", reviewer="Alice", reviewer_evidence="edition p. 3")
    accepted = from_review_table(path, corpus)
    history = accepted.documents[0].tokens[0].annotations["review_history"]
    lemma = "λόγος" if same_prediction else "λέξις"
    fresh = greek.annotate_corpus(accepted, tag_sentence=lambda forms: [(lemma, "NOUN") for _ in forms])
    fresh.to_json(tmp_path / "fresh.json")
    fresh = Corpus.from_json(tmp_path / "fresh.json")
    ann = fresh.documents[0].tokens[0].annotations
    assert ann["lemma_review_decision"] == ann["upos_review_decision"] == "stale"
    assert ann.get("lemma_verified") != "true" and ann.get("upos_verified") != "true"
    assert ann["feats_review_decision"] == "accept" and ann["feats_verified"] == "true"
    assert ann["review_history"] == history and ann["lemma__pred"] == "λόγος"


@pytest.mark.parametrize("merge", [False, True])
def test_changed_prediction_source_requires_fresh_decisions(tmp_path: Path, merge: bool) -> None:
    corpus = _corpus()
    alice = _table(tmp_path / "alice.csv", corpus, decision_lemma="accept", reviewer="Alice")
    bob = _table(tmp_path / "bob.csv", corpus, decision_lemma="accept", reviewer="Bob")
    changed = _corpus()
    changed.documents[0].tokens[0].annotations["lemma_source"] = "rule"
    with pytest.raises(ValueError, match="changed since export"):
        if merge:
            merge_review_tables([alice, bob], changed)
        else:
            from_review_table(alice, changed)


def test_acceptance_is_idempotent_but_reconsidering_a_stale_decision_retains_history(tmp_path: Path) -> None:
    corpus = _corpus()
    path = _table(tmp_path / "review.csv", corpus, decision_lemma="accept", reviewer="Alice")
    accepted = from_review_table(path, corpus)
    repeated = apply_review_table(path, accepted)
    assert repeated.reviewed == 0 and repeated.corpus.to_json() == accepted.to_json()
    # Even when a replacement backend returns identical lemma/source strings,
    # reconsidering a stale decision is a new scholarly decision.
    stale = _corpus()
    stale.documents[0].tokens[0] = replace(stale.documents[0].tokens[0], annotations={
        **accepted.documents[0].tokens[0].annotations, "lemma_review_decision": "stale",
        "lemma_verified": "false",
    })
    reconsidered = from_review_table(_table(tmp_path / "fresh.csv", stale, decision_lemma="accept",
                                           reviewer="Alice"), stale)
    assert len(json.loads(reconsidered.documents[0].tokens[0].annotations["review_history"])) == 2


def test_aligned_merged_session_preserves_whitespace_and_individual_field_attribution(tmp_path: Path) -> None:
    corpus = _corpus()
    alice = _table(tmp_path / "alice.csv", corpus, decision_lemma="accept", reviewer="Smith, Alice",
                   reviewer_note="lemma checked", reviewer_evidence="edition p. 3")
    bob = _table(tmp_path / "bob.csv", corpus, decision_pos="correct", correct_pos="PROPN",
                 reviewer="Bob", reviewer_note="proper name", reviewer_evidence="index p. 9")
    merged = merge_review_tables([alice, bob], corpus)
    alignment = corpus.documents[0].tokens[0].alignment
    assert alignment is not None and alignment.whitespace_before == "\t "
    assert merged.rows[0]["alignment_whitespace_before"] == "\t "
    direct = apply_merged(merged, corpus)
    destination = tmp_path / "merged.csv"
    merged.to_csv(destination)
    persisted = from_review_table(destination, corpus)
    assert direct.documents[0].tokens[0].annotations == persisted.documents[0].tokens[0].annotations
    ann = persisted.documents[0].tokens[0].annotations
    assert ann["lemma_reviewed_by"] == "Smith, Alice" and ann["upos_reviewed_by"] == "Bob"
    assert ann["lemma_review_evidence"] == "edition p. 3" and ann["upos_review_evidence"] == "index p. 9"
    assert ann["lemma_review_note"] == "lemma checked" and ann["upos_review_note"] == "proper name"
    assert {(record["field"], record["reviewer"]) for record in json.loads(ann["review_history"])} == {
        ("lemma", "Smith, Alice"), ("upos", "Bob"),
    }


def test_accept_vs_correction_conflicts_hold_field_and_keep_agreed_morphology(tmp_path: Path) -> None:
    corpus = _corpus()
    alice = _table(tmp_path / "alice.csv", corpus, decision_lemma="accept", decision_morph="accept", reviewer="Alice")
    bob = _table(tmp_path / "bob.csv", corpus, decision_lemma="correct", correct_lemma="λέξις", reviewer="Bob")
    merged = merge_review_tables([alice, bob], corpus, on_conflict="report")
    assert len(merged.conflicts) == 1 and merged.conflicts[0].field == "lemma"
    assert {option.action for option in merged.conflicts[0].options} == {"accept", "correct"}
    ann = apply_merged(merged, corpus).documents[0].tokens[0].annotations
    assert ann["lemma_verified"] == "false" and "lemma_review_decision" not in ann
    assert ann["feats_verified"] == "true" and ann["feats_reviewed_by"] == "Alice"


@pytest.mark.parametrize("edits,match", [
    ({"decision_lemma": "approve"}, "must be accept"),
    ({"decision_lemma": "correct"}, "requires correct_lemma"),
    ({"decision_lemma": "correct", "correct_lemma": "λόγος"}, "requires accept"),
    ({"decision_lemma": "accept", "correct_lemma": "λέξις"}, "requires a blank"),
    ({"decision_morph": "accept", "pred_morph": ""}, "absent"),
    ({"decision_lemma": "accept", "pred_lemma": "obsolete"}, "changed since export"),
    ({"decision_lemma": "accept", "position": "1.0"}, "unusable position"),
    ({"decision_lemma": "accept", "token": "different"}, "different token"),
    ({"decision_lemma": "accept", "alignment_whitespace_before": " "}, "source alignment"),
])
def test_invalid_or_stale_decisions_never_land(tmp_path: Path, edits: dict[str, str], match: str) -> None:
    corpus = _corpus()
    before = corpus.to_json()
    path = _table(tmp_path / "invalid.csv", corpus, **edits)
    with pytest.raises(ValueError, match=match):
        from_review_table(path, corpus)
    assert corpus.to_json() == before


@pytest.mark.parametrize("encoded, messages", [
    pytest.param("{", ("invalid reviewer_records JSON",), id="invalid-json"),
    pytest.param(
        "[" * 10000 + "0" + "]" * 10000,
        ("invalid reviewer_records JSON", "reviewer_records must attribute the reviewed lemma field"),
        id="deep-json",
    ),
])
def test_malformed_reviewer_attribution_fails_cleanly_without_changing_source(
    tmp_path: Path, encoded: str, messages: tuple[str, ...],
) -> None:
    corpus = _corpus()
    before = corpus.to_json()
    table = _table(tmp_path / "invalid.csv", corpus, decision_lemma="accept",
                   reviewer_records=encoded)
    # A decoder may reject deep JSON, or parse it for the attribution schema to reject.
    with pytest.raises(ValueError) as error:
        from_review_table(table, corpus)
    assert str(error.value) in messages
    assert corpus.to_json() == before

    source = tmp_path / "source.json"
    output = tmp_path / "reviewed.json"
    corpus.to_json(source)
    result = CliRunner().invoke(_build_app(), [
        "review", "apply", str(source), str(table), "-o", str(output),
    ])
    assert result.exit_code == 1
    assert any(message in result.output for message in messages)
    assert not output.exists()
    assert Corpus.from_json(source).to_json() == before


@pytest.mark.parametrize("command", ["export", "merge"])
def test_cli_hints_quote_paths_and_preserve_annotation_backend_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str,
) -> None:
    source = tmp_path / "corpus name;literal.json"
    corpus = _corpus()
    corpus.to_json(source)
    monkeypatch.setattr(_review, "_activate", lambda **kwargs: None)
    monkeypatch.setattr(greek, "annotate_corpus", lambda corpus: corpus)
    output = tmp_path / "review name.csv"
    args = ["review", command]
    if command == "merge":
        alice = _table(tmp_path / "alice.csv", corpus, decision_lemma="accept", reviewer="Alice")
        bob = _table(tmp_path / "bob.csv", corpus, decision_pos="accept", reviewer="Bob")
        args += [str(alice), str(bob), "--corpus", str(source)]
    else:
        args += [str(source)]
    args += ["-o", str(output), "--annotate", "--tagger", "--lemmatizer", "--neural-lemmatizer", "--neural"]
    result = CliRunner().invoke(_build_app(), args)
    assert result.exit_code == 0, result.output
    hint = next(line for line in result.output.splitlines() if "then:" in line).split("then:", 1)[1].strip()
    assert shlex.split(hint) == [
        "aegean", "review", "apply", str(source), str(output), "-o", "corrected.json",
        "--annotate", "--tagger", "--lemmatizer", "--neural-lemmatizer", "--neural",
    ]
