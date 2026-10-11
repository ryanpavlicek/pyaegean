"""Complete-sentence dependency decisions are optional, source-bound, and atomic."""

from __future__ import annotations

import csv
import importlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegean import greek
from aegean.cli import _build_app, _review
from aegean.core.corpus import Corpus
from aegean.core.model import TokenKind
from aegean.greek import joint
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.neural_contract import AnalysisReceipt
from aegean.greek.pipeline import TokenRecord
from aegean.io import from_text
from aegean.io.review import (
    REVIEW_COLUMNS, apply_merged, apply_review_table, from_review_table,
    merge_review_tables, to_review_table,
)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _corpus() -> Corpus:
    corpus = from_text("λόγος νόμου. πατήρ υἱοῦ.", doc_id="research")
    doc = corpus.documents[0]
    tokens = []
    for index, token in enumerate(doc.tokens):
        sentence, ordinal = divmod(index, 3)
        assert token.alignment is not None
        tokens.append(replace(token, alignment=replace(token.alignment, sentence_id=f"s{sentence}"),
            annotations={"lemma": token.text, "upos": "PUNCT" if token.kind is TokenKind.PUNCT else "NOUN",
                         "head": "0" if ordinal == 0 else "1",
                         "deprel": "root" if ordinal == 0 else "punct" if ordinal == 2 else "nmod",
                         "feats": "" if ordinal == 2 else "Case=Nom", "lemma_source": "external",
                         "review_recommended": "false"}))
    return Corpus([replace(doc, tokens=tokens)], script_id=corpus.script_id, provenance=corpus.provenance)


def _table(path: Path, corpus: Corpus, *, reviewer: str = "Alice") -> list[dict[str, str]]:
    assert to_review_table(corpus, path, fields=("head", "deprel"), reviewer=reviewer) == 6
    return _rows(path)


def _swap_root(rows: list[dict[str, str]]) -> None:
    rows[0].update(decision_head="correct", correct_head="2", decision_deprel="correct", correct_deprel="nsubj")
    rows[1].update(decision_head="correct", correct_head="0", decision_deprel="correct", correct_deprel="root")


@pytest.mark.parametrize("suffix", ["json", "db"])
def test_dependency_export_edit_merge_apply_reopen_preserves_tree_and_attribution(
    tmp_path: Path, suffix: str,
) -> None:
    corpus = _corpus()
    before = corpus.to_json()
    alice, bob = tmp_path / "alice.csv", tmp_path / "bob.csv"
    rows = _table(alice, corpus, reviewer="Smith, Alice")
    _swap_root(rows)
    for row in rows[:2]:
        row.update(reviewer_note="sentence roles checked", reviewer_evidence="edition p. 3")
    _write(alice, rows)
    rows = _table(bob, corpus, reviewer="Bob")
    rows[2].update(decision_deprel="accept", reviewer_note="punctuation checked", reviewer_evidence="edition p. 4")
    _write(bob, rows)
    assert [row["dependency_index"] for row in rows] == ["1", "2", "3", "1", "2", "3"]
    assert json.loads(rows[0]["dependency_sentence_context"])[2]["text"] == "."
    merged = merge_review_tables([alice, bob], corpus)
    assert not merged.conflicts and len(merged.rows) == 6  # Includes blank context rows.
    destination = tmp_path / "merged.csv"
    merged.to_csv(destination)
    direct = apply_merged(merged, corpus)
    reviewed = from_review_table(destination, corpus)
    assert direct.provenance is not None and reviewed.provenance is not None
    assert direct.provenance.notes[:-1] == reviewed.provenance.notes[:-1]
    assert "merged from 2 review tables" in direct.provenance.notes[-1]
    assert "merged from" not in reviewed.provenance.notes[-1]
    # Direct merged apply records the merge; CSV apply records only the landed table.
    direct.provenance = replace(direct.provenance, notes=reviewed.provenance.notes)
    assert direct.to_json() == reviewed.to_json()
    output = tmp_path / f"reviewed.{suffix}"
    if suffix == "json":
        reviewed.to_json(output)
        reopened = Corpus.from_json(output)
    else:
        reviewed.to_sql(output)
        reopened = Corpus.from_sql(output)
    tokens = reopened.documents[0].tokens
    assert [token.annotations["head"] for token in tokens[:3]] == ["2", "0", "1"]
    assert [token.annotations["deprel"] for token in tokens[:3]] == ["nsubj", "root", "punct"]
    assert tokens[0].annotations["head__pred"] == "0" and tokens[1].annotations["head__pred"] == "1"
    assert tokens[0].annotations["head_reviewed_by"] == "Smith, Alice"
    assert tokens[0].annotations["deprel_review_evidence"] == "edition p. 3"
    assert tokens[2].annotations["deprel_verified"] == "true" and tokens[2].annotations["deprel_reviewed_by"] == "Bob"
    assert "head_verified" not in tokens[2].annotations
    assert all("lemma_verified" not in token.annotations and "sense_verified" not in token.annotations for token in tokens)
    assert [token.annotations for token in tokens[3:]] == [token.annotations for token in corpus.documents[0].tokens[3:]]
    replay = apply_review_table(destination, reopened)
    assert replay.corrected == replay.reviewed == 0 and replay.corpus.to_json() == reopened.to_json()
    assert corpus.to_json() == before


def test_dependency_sampling_expands_only_selected_sentences_with_context_reasons(tmp_path: Path) -> None:
    corpus = _corpus()
    path = tmp_path / "sample.csv"
    assert to_review_table(corpus, path, selection="sample", sample_size=1, seed=3, fields=("deprel",)) == 3
    rows = _rows(path)
    assert len({row["dependency_sentence_id"] for row in rows}) == 1
    assert [row["dependency_index"] for row in rows] == ["1", "2", "3"]
    reasons = [json.loads(row["inclusion_reasons"]) for row in rows]
    assert sum("sample:unflagged" in reason for reason in reasons) == 1
    assert sum(reason[0].startswith("sentence_context:") for reason in reasons) == 2
    assert rows[2]["token"] == "."
    assert to_review_table(corpus, tmp_path / "words.csv") == 4  # Default is still words-only.


@pytest.mark.parametrize("edits,match", [
    ({0: {"decision_head": "correct", "correct_head": "99"}}, "outside its sentence"),
    ({0: {"decision_head": "correct", "correct_head": "-1"}}, "must be an integer"),
    ({0: {"decision_head": "correct", "correct_head": "1.0"}}, "must be an integer"),
    ({0: {"decision_head": "correct", "correct_head": "²"}}, "must be an integer"),
    ({0: {"decision_head": "correct", "correct_head": "1"}}, "own token"),
    ({1: {"decision_head": "correct", "correct_head": "0", "decision_deprel": "correct", "correct_deprel": "root"}}, "exactly one root"),
    ({0: {"decision_head": "correct", "correct_head": "2", "decision_deprel": "correct", "correct_deprel": "dep"}}, "cycle|exactly one root"),
    ({1: {"decision_deprel": "correct", "correct_deprel": "root"}}, "root head and root relation"),
    ({1: {"decision_deprel": "correct", "correct_deprel": "invalid relation"}}, "without whitespace"),
    ({0: {"dependency_sentence_id": "s1", "decision_head": "accept"}}, "ownership or context"),
    ({0: {"dependency_index": "2", "decision_head": "accept"}}, "ownership or context"),
    ({0: {"dependency_sentence_context": "[]", "decision_head": "accept"}}, "ownership or context"),
    ({0: {"review_snapshot": "", "decision_head": "accept"}}, "bound review snapshot"),
])
def test_invalid_dependency_edits_never_land_any_sentence_or_lexical_edits(
    tmp_path: Path, edits: dict[int, dict[str, str]], match: str,
) -> None:
    corpus = _corpus()
    before = corpus.to_json()
    path = tmp_path / "invalid.csv"
    rows = _table(path, corpus)
    rows[3].update(decision_lemma="correct", correct_lemma="λέξις")
    for index, change in edits.items():
        rows[index].update(change)
    _write(path, rows)
    with pytest.raises(ValueError, match=match):
        from_review_table(path, corpus)
    assert corpus.to_json() == before


def test_complete_sentence_cycle_detection_even_with_one_valid_root(tmp_path: Path) -> None:
    corpus = _corpus()
    path = tmp_path / "cycle.csv"
    rows = _table(path, corpus)
    rows[1].update(decision_head="correct", correct_head="3")
    rows[2].update(decision_head="correct", correct_head="2")
    _write(path, rows)
    with pytest.raises(ValueError, match="cycle"):
        from_review_table(path, corpus)


def test_missing_context_and_stale_unreviewed_context_are_both_rejected(tmp_path: Path) -> None:
    corpus = _corpus()
    path = tmp_path / "incomplete.csv"
    rows = _table(path, corpus)
    rows[0].update(decision_deprel="accept")
    _write(path, rows[:2] + rows[3:])  # Missing punctuation from the touched sentence.
    with pytest.raises(ValueError, match="complete sentence"):
        from_review_table(path, corpus)
    _write(path, rows)
    corpus.documents[0].tokens[2].annotations["deprel"] = "dep"
    before = corpus.to_json()
    with pytest.raises(ValueError, match="prediction changed since export"):
        from_review_table(path, corpus)
    assert corpus.to_json() == before


def test_sentence_conflict_holds_all_its_dependency_decisions_but_retains_lexical_agreement(tmp_path: Path) -> None:
    corpus = _corpus()
    alice, bob = tmp_path / "alice.csv", tmp_path / "bob.csv"
    rows = _table(alice, corpus, reviewer="Alice")
    _swap_root(rows)
    rows[0].update(decision_lemma="accept")
    _write(alice, rows)
    rows = _table(bob, corpus, reviewer="Bob")
    rows[0].update(decision_head="accept", decision_deprel="accept")
    _write(bob, rows)
    with pytest.raises(ValueError, match="conflicting"):
        merge_review_tables([alice, bob], corpus)
    merged = merge_review_tables([alice, bob], corpus, on_conflict="report")
    assert {conflict.field for conflict in merged.conflicts} == {"head", "deprel"}
    assert all(not row[f"decision_{field}"] and not row[f"correct_{field}"]
               for row in merged.rows[:3] for field in ("head", "deprel"))
    reviewed = apply_merged(merged, corpus)
    assert [token.annotations["head"] for token in reviewed.documents[0].tokens] == ["0", "1", "1", "0", "1", "1"]
    assert reviewed.documents[0].tokens[0].annotations["lemma_verified"] == "true"
    assert not any("head_verified" in token.annotations for token in reviewed.documents[0].tokens)
    assert merged.reviewers == ("Alice",)


@pytest.mark.parametrize("kind", ["missing", "partial", "noncontiguous", "wrong_document", "bad_index"])
def test_dependency_ownership_cannot_be_inferred_or_changed(tmp_path: Path, kind: str) -> None:
    corpus = _corpus()
    doc = corpus.documents[0]
    if kind == "missing":
        doc.tokens = [replace(token, alignment=replace(token.alignment, sentence_id=None)) for token in doc.tokens]
    elif kind == "partial":
        doc.tokens[1] = replace(doc.tokens[1], alignment=replace(doc.tokens[1].alignment, sentence_id=None))
    elif kind == "noncontiguous":
        doc.tokens[3] = replace(doc.tokens[3], alignment=replace(doc.tokens[3].alignment, sentence_id="s0"))
        doc.tokens[5] = replace(doc.tokens[5], alignment=replace(doc.tokens[5].alignment, sentence_id="s0"))
    elif kind == "wrong_document":
        doc.tokens[1] = replace(doc.tokens[1], alignment=replace(doc.tokens[1].alignment, document_id="foreign"))
    else:
        doc.tokens[1].annotations["dependency_index"] = "9"
    path = tmp_path / "review.csv"
    path.write_text("existing", encoding="utf-8")
    with pytest.raises(ValueError, match="sentence|indices"):
        to_review_table(corpus, path, fields=("head",))
    assert path.read_text(encoding="utf-8") == "existing"


def _receipt(count: int) -> AnalysisReceipt:
    return AnalysisReceipt(
        schema_version=1, source_schema_version=1, model_id="fixture-joint",
        dataset="constructed", asset_sha256="a" * 64, asset_sha256_enforced=True,
        bundle_manifest_sha256="b" * 64, bundle_schema_version=1,
        tokenizer_revision="c" * 64, package_version="fixture", python_version="fixture",
        runtime_versions=(), execution_providers=("CPUExecutionProvider",),
        annotation_profile="pyaegean-canonical-v1", normalization="NFC",
        segmentation="pretokenized", preprocessing_version="fixture", special_token_policy=None,
        max_subwords=256, input_tokens=count, analyzed_tokens=count, truncated=False, windowed=False,
    )


def _fake_neural(monkeypatch: pytest.MonkeyPatch) -> list[list[TokenKind]]:
    calls: list[list[TokenKind]] = []
    monkeypatch.setattr(joint, "active", lambda: object())

    def analyze(tokens, **kwargs):
        calls.append([token.kind for token in tokens])
        receipt = _receipt(len(tokens))
        output = []
        sentence = 0
        index = 1
        for token in tokens:
            output.append(TokenRecord(sentence=sentence, index=index, text=token.text,
                lemma=token.text, upos="PUNCT" if token.kind is TokenKind.PUNCT else "NOUN",
                lemma_source=LemmaSource.PUNCT if token.kind is TokenKind.PUNCT else LemmaSource.NEURAL,
                head=0 if index == 1 else 1, relation="root" if index == 1 else "punct" if token.kind is TokenKind.PUNCT else "dep",
                feats="" if token.kind is TokenKind.PUNCT else "Case=Nom", xpos="fixture",
                analysis_receipt=receipt, alignment=token.alignment, form_state=token.form_state))
            index += 1
            if token.text == ".":
                sentence += 1
                index = 1
        return output

    monkeypatch.setattr(importlib.import_module("aegean.greek.pipeline"), "pipeline_tokens", analyze)
    return calls


def test_neural_receipts_persist_without_changing_the_default_source_morphology_or_punctuation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls = _fake_neural(monkeypatch)
    corpus = _corpus()
    corpus.documents[0].tokens[0].annotations.update(morph="source morph", morph_verified="true")
    punctuation = corpus.documents[0].tokens[2].annotations.copy()
    annotated = greek.annotate_corpus(corpus)
    assert calls == [[TokenKind.WORD] * 4]
    assert annotated.documents[0].tokens[0].annotations["morph"] == "source morph"
    assert annotated.documents[0].tokens[0].annotations["morph_verified"] == "true"
    assert annotated.documents[0].tokens[2].annotations == punctuation
    assert annotated.documents[0].tokens[0].annotations["analysis_receipt"] == _receipt(4).to_json()
    path = tmp_path / "review.csv"
    to_review_table(annotated, path)
    binding = json.loads(_rows(path)[0]["review_snapshot"])
    assert json.loads(binding["analysis"]["receipt"])["asset_sha256"] == "a" * 64


def test_explicit_neural_dependencies_capture_complete_domain_and_invalidate_replaced_reviews(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls = _fake_neural(monkeypatch)
    corpus = _corpus()
    first = greek.annotate_corpus(corpus, with_dependencies=True)
    assert calls == [[TokenKind.WORD, TokenKind.WORD, TokenKind.PUNCT] * 2]
    tokens = first.documents[0].tokens
    assert [token.annotations["dependency_index"] for token in tokens] == ["1", "2", "3", "1", "2", "3"]
    assert [token.annotations["head"] for token in tokens] == ["0", "1", "1", "0", "1", "1"]
    assert [token.annotations["dependency_sentence_id"] for token in tokens] == ["research:analysis-sentence:0"] * 3 + ["research:analysis-sentence:1"] * 3
    path = tmp_path / "review.csv"
    to_review_table(first, path, fields=("head", "deprel", "morph"))
    rows = _rows(path)
    rows[0].update(decision_head="accept", decision_deprel="accept", decision_morph="accept")
    _write(path, rows)
    reviewed = from_review_table(path, first)
    second = greek.annotate_corpus(reviewed, with_dependencies=True)
    assert second.documents[0].tokens[0].annotations["head_review_decision"] == "stale"
    assert second.documents[0].tokens[0].annotations["deprel_review_decision"] == "stale"
    assert second.documents[0].tokens[0].annotations["feats_review_decision"] == "stale"
    assert all(second.documents[0].tokens[0].annotations.get(f"{key}_verified") != "true"
               for key in ("head", "deprel", "feats"))
    assert second.documents[0].tokens[0].annotations["review_history"] == reviewed.documents[0].tokens[0].annotations["review_history"]
    with pytest.raises(ValueError, match="analysis identity changed"):
        from_review_table(path, second)


def test_dependency_annotation_requires_neural_without_modifying_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(joint, "active", lambda: None)
    corpus = _corpus()
    before = corpus.to_json()
    with pytest.raises(ValueError, match="requires the active neural"):
        greek.annotate_corpus(corpus, with_dependencies=True)
    assert corpus.to_json() == before


def test_cli_dependency_annotation_export_and_atomic_apply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_neural(monkeypatch)
    monkeypatch.setattr(_review, "_activate", lambda **kwargs: None)
    source, snapshot, table, destination = (tmp_path / name for name in ("source.json", "analysis.json", "review.csv", "reviewed.json"))
    _corpus().to_json(source)
    runner = CliRunner()
    export = runner.invoke(_build_app(), ["review", "export", str(source), "-o", str(table), "--annotate",
        "--annotated-output", str(snapshot), "--field", "head", "--field", "deprel"])
    assert export.exit_code == 0, export.output
    assert len(_rows(table)) == 6
    assert Corpus.from_json(snapshot).documents[0].tokens[2].annotations["dependency_index"] == "3"
    rows = _rows(table)
    _swap_root(rows)
    _write(table, rows)
    applied = runner.invoke(_build_app(), ["review", "apply", str(snapshot), str(table), "-o", str(destination)])
    assert applied.exit_code == 0, applied.output
    assert [token.annotations["head"] for token in Corpus.from_json(destination).documents[0].tokens[:3]] == ["2", "0", "1"]
    rows[2].update(decision_head="correct", correct_head="9")
    _write(table, rows)
    destination.write_text("existing user output", encoding="utf-8")
    invalid = runner.invoke(_build_app(), ["review", "apply", str(snapshot), str(table), "-o", str(destination)])
    assert invalid.exit_code == 1 and "outside its sentence" in invalid.output
    assert destination.read_text(encoding="utf-8") == "existing user output"



def test_partial_punctuation_ownership_cannot_hide_an_out_of_range_head(tmp_path: Path) -> None:
    corpus = _corpus()
    doc = corpus.documents[0]
    doc.tokens[2].annotations["head"] = "99"
    path = tmp_path / "complete.csv"
    rows = _table(path, corpus)
    rows[0].update(decision_head="accept")
    _write(path, rows)
    with pytest.raises(ValueError, match="outside its sentence"):
        from_review_table(path, corpus)
    doc.tokens[2] = replace(doc.tokens[2], alignment=replace(doc.tokens[2].alignment, sentence_id=None))
    destination = tmp_path / "partial.csv"
    destination.write_text("existing", encoding="utf-8")
    with pytest.raises(ValueError, match="sentence IDs must be complete"):
        to_review_table(corpus, destination, fields=("head",))
    assert destination.read_text(encoding="utf-8") == "existing"


def test_partial_explicit_dependency_index_cannot_change_the_parse_domain(tmp_path: Path) -> None:
    corpus = _corpus()
    corpus.documents[0].tokens[0].annotations["dependency_index"] = "1"
    with pytest.raises(ValueError, match="indices must be complete"):
        to_review_table(corpus, tmp_path / "partial.csv", fields=("head",))


def test_extreme_numeric_head_is_a_clean_error_and_preserves_corpus(tmp_path: Path) -> None:
    corpus = _corpus()
    path = tmp_path / "extreme.csv"
    rows = _table(path, corpus)
    rows[0].update(decision_head="correct", correct_head="9" * 10000)
    rows[3].update(decision_lemma="correct", correct_lemma="λέξις")
    _write(path, rows)
    before = corpus.to_json()
    with pytest.raises(ValueError):
        from_review_table(path, corpus)
    assert corpus.to_json() == before
