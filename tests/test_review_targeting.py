"""Field queues, independent sampling, bound analysis identity, and review journeys."""

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
from aegean.core.model import Document, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.io import from_text
from aegean.io.review import (
    REVIEW_COLUMNS, apply_merged, apply_review_table, from_review_table,
    merge_review_tables, to_review_table,
)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, str]], columns: tuple[str, ...] = REVIEW_COLUMNS) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _corpus() -> Corpus:
    records = [
        {"lemma_verified": "true"},
        {"upos_verified": "TRUE"},
        {"feats_verified": "true"},
        {"lemma_verified": "true", "upos_verified": "true", "feats_verified": "true"},
        {"morph": "source", "morph_verified": "true", "feats_verified": "false"},
        {"lemma_verified": " true ", "upos_verified": "yes"},
    ]
    tokens = [Token(text=f"fixture-{index}", kind=TokenKind.WORD, position=index, line_no=0,
                    annotations={"lemma": "prediction", "upos": "NOUN", "feats": "",
                                 "lemma_source": "neural", "review_recommended": "false", **record})
              for index, record in enumerate(records)]
    return Corpus([Document("d", "greek", tokens, [list(range(len(tokens)))])],
                  script_id="greek", provenance=Provenance("constructed review fixture"))


@pytest.mark.parametrize("fields,positions", [
    (("lemma",), [1, 2, 4, 5]),
    (("pos",), [0, 2, 4, 5]),
    (("morph",), [0, 1, 5]),
    (("lemma", "pos", "morph"), [0, 1, 2, 4, 5]),
])
def test_unverified_queues_use_only_each_requested_fields_marker(
    tmp_path: Path, fields: tuple[str, ...], positions: list[int],
) -> None:
    corpus = _corpus()
    path = tmp_path / "queue.csv"
    assert to_review_table(corpus, path, selection="unverified", fields=fields) == len(positions)
    rows = _rows(path)
    assert [int(row["position"]) for row in rows] == positions
    for row in rows:
        annotations = corpus.documents[0].tokens[int(row["position"])].annotations
        keys = {"lemma": "lemma", "pos": "upos", "morph": "morph" if annotations.get("morph") else "feats"}
        assert json.loads(row["review_fields"]) == list(fields)
        assert json.loads(row["inclusion_reasons"]) == [
            f"unverified:{name}" for name in fields
            if annotations.get(f"{keys[name]}_verified", "").lower() != "true"
        ]
    # Imported/resolved/neural labels never imply a field verification.
    assert all(not row["needs_review"] for row in rows)


def test_seeded_sample_is_reproducible_and_separate_from_the_existing_flag(tmp_path: Path) -> None:
    base = _corpus()
    tokens = [replace(base.documents[0].tokens[0], text=f"fixture-{index}", position=index,
                      annotations={"lemma": "prediction", "upos": "NOUN",
                                   "review_recommended": "true" if index % 5 == 0 else "false"})
              for index in range(40)]
    corpus = Corpus([replace(base.documents[0], tokens=tokens, lines=[list(range(40))])])
    first, repeated, other = (tmp_path / name for name in ("a.csv", "b.csv", "c.csv"))
    assert to_review_table(corpus, first, selection="sample", sample_size=8, seed=71) == 8
    assert to_review_table(corpus, repeated, selection="sample", sample_size=8, seed=71) == 8
    assert first.read_bytes() == repeated.read_bytes()
    to_review_table(corpus, other, selection="sample", sample_size=8, seed=72)
    positions = {int(row["position"]) for row in _rows(first)}
    assert len(positions) == 8 and all(position % 5 for position in positions)
    assert positions != {int(row["position"]) for row in _rows(other)}
    assert all(json.loads(row["inclusion_reasons"]) == [
        "sample:unflagged", "sample_seed:71", "sample_population:32", "sample_size:8",
    ] for row in _rows(first))
    assert to_review_table(corpus, other, selection="sample", sample_size=100, seed=71) == 32
    assert to_review_table(corpus, other, selection="sample", sample_size=0) == 0
    assert _rows(other) == []


@pytest.mark.parametrize("kwargs", [
    {"fields": []}, {"fields": "pos"}, {"fields": ["sense"]}, {"fields": ["pos", "pos"]},
    {"selection": "sample"}, {"selection": "sample", "sample_size": -1},
    {"selection": "sample", "sample_size": True}, {"sample_size": 1}, {"seed": True},
])
def test_invalid_queue_options_do_not_replace_an_artifact(tmp_path: Path, kwargs: dict[str, object]) -> None:
    path = tmp_path / "queue.csv"
    path.write_text("existing", encoding="utf-8")
    with pytest.raises(ValueError):
        to_review_table(_corpus(), path, **kwargs)  # type: ignore[arg-type]
    assert path.read_text(encoding="utf-8") == "existing"


def _analyzed() -> Corpus:
    return greek.annotate_corpus(from_text("\t λόγος νόμου", doc_id="research"),
                                tag_sentence=lambda forms: [(form, "NOUN") for form in forms])


@pytest.mark.parametrize("suffix", ["json", "db"])
def test_export_edit_merge_apply_reopen_preserves_field_evidence_and_replay(
    tmp_path: Path, suffix: str,
) -> None:
    corpus = _analyzed()
    before = corpus.to_json()
    alice, bob = tmp_path / "alice.csv", tmp_path / "bob.csv"
    to_review_table(corpus, alice, selection="unverified", fields=("lemma", "pos"), reviewer="Smith, Alice")
    to_review_table(corpus, bob, selection="unverified", fields=("lemma", "pos"), reviewer="Bob")
    rows = _rows(alice)
    rows[0].update(decision_lemma="correct", correct_lemma="λέξις", reviewer_note="reading checked",
                   reviewer_evidence="edition p. 3")
    _write(alice, rows)
    rows = _rows(bob)
    rows[0].update(decision_pos="accept", reviewer_note="noun checked", reviewer_evidence="index p. 9")
    _write(bob, rows)
    merged = merge_review_tables([alice, bob], corpus)
    merged_path = tmp_path / "merged.csv"
    merged.to_csv(merged_path)
    direct = apply_merged(merged, corpus)
    persisted = from_review_table(merged_path, corpus)
    assert direct.provenance is not None and persisted.provenance is not None
    assert direct.provenance.notes[:-1] == persisted.provenance.notes[:-1]
    assert "merged from 2 review tables" in direct.provenance.notes[-1]
    assert "merged from" not in persisted.provenance.notes[-1]
    # Direct merged apply records the merge; CSV apply records only the landed table.
    direct.provenance = replace(direct.provenance, notes=persisted.provenance.notes)
    assert direct.to_json() == persisted.to_json()
    destination = tmp_path / f"reviewed.{suffix}"
    if suffix == "json":
        persisted.to_json(destination)
        reopened = Corpus.from_json(destination)
    else:
        persisted.to_sql(destination)
        reopened = Corpus.from_sql(destination)
    ann = reopened.documents[0].tokens[0].annotations
    assert ann["lemma"] == "λέξις" and ann["lemma__pred"] == "λόγος"
    assert ann["lemma_verified"] == ann["upos_verified"] == "true"
    assert ann["lemma_reviewed_by"] == "Smith, Alice" and ann["upos_reviewed_by"] == "Bob"
    assert ann["lemma_review_evidence"] == "edition p. 3" and ann["upos_review_evidence"] == "index p. 9"
    history = json.loads(ann["review_history"])
    assert {(event["field"], event["reviewer"]) for event in history} == {("lemma", "Smith, Alice"), ("upos", "Bob")}
    assert all(event["snapshot"] == _rows(merged_path)[0]["review_snapshot_sha256"] for event in history)
    assert not any(key in ann for key in ("sense_verified", "head_verified", "deprel_verified"))
    replay = apply_review_table(merged_path, reopened)
    assert replay.reviewed == replay.corrected == 0 and replay.corpus.to_json() == reopened.to_json()
    assert to_review_table(reopened, tmp_path / "remaining.csv", selection="unverified", fields=("pos",)) == 1
    assert corpus.to_json() == before


def test_identical_reannotation_is_observable_and_never_reuses_an_old_snapshot(tmp_path: Path) -> None:
    corpus = _analyzed()
    path = tmp_path / "old.csv"
    to_review_table(corpus, path)
    first_bytes = path.read_bytes()
    to_review_table(corpus, tmp_path / "same.csv")
    assert (tmp_path / "same.csv").read_bytes() == first_bytes  # export is a true no-op
    rows = _rows(path)
    rows[0].update(decision_pos="accept")
    _write(path, rows)
    fresh = greek.annotate_corpus(corpus, tag_sentence=lambda forms: [(form, "NOUN") for form in forms])
    old_ann, fresh_ann = (value.documents[0].tokens[0].annotations for value in (corpus, fresh))
    assert old_ann["lemma"] == fresh_ann["lemma"] and old_ann["upos"] == fresh_ann["upos"]
    assert old_ann["analysis_generation"] != fresh_ann["analysis_generation"]
    before = fresh.to_json()
    with pytest.raises(ValueError, match="analysis identity changed"):
        from_review_table(path, fresh)
    with pytest.raises(ValueError, match="analysis identity changed"):
        merge_review_tables([path], fresh)
    assert fresh.to_json() == before
    to_review_table(fresh, tmp_path / "new.csv")
    assert _rows(tmp_path / "new.csv")[0]["review_snapshot_sha256"] != rows[0]["review_snapshot_sha256"]


@pytest.mark.parametrize("change", ["model", "receipt", "configuration", "presence", "source", "other_output", "citation"])
def test_snapshots_bind_available_identity_output_presence_and_whole_source_context(
    tmp_path: Path, change: str,
) -> None:
    corpus = _corpus()
    corpus.documents[0].tokens[0].annotations.update(model_id="one", model_sha256="a" * 64,
        analysis_receipt="receipt-one", analysis_configuration="configuration-one")
    path = tmp_path / "review.csv"
    to_review_table(corpus, path)
    rows = _rows(path)
    rows[0].update(decision_pos="accept")
    _write(path, rows)
    changed = Corpus.from_json(corpus.to_json())
    token = changed.documents[0].tokens[0]
    if change == "model":
        token.annotations["model_sha256"] = "b" * 64
    elif change == "receipt":
        token.annotations["analysis_receipt"] = "receipt-two"
    elif change == "configuration":
        token.annotations["analysis_configuration"] = "configuration-two"
    elif change == "presence":
        del token.annotations["feats"]  # Empty and absent morphology are distinct outputs.
    elif change == "source":
        changed.documents[0].tokens[1] = replace(changed.documents[0].tokens[1], text="different-context")
    elif change == "other_output":
        token.annotations["head"] = "0"
    else:
        changed.provenance = replace(changed.provenance, citation="different edition")
    before = changed.to_json()
    with pytest.raises(ValueError, match="changed since export"):
        from_review_table(path, changed)
    assert changed.to_json() == before


def test_external_and_custom_snapshot_identity_is_explicitly_unknown(tmp_path: Path) -> None:
    for name, corpus in (("external", _corpus()), ("custom", _analyzed())):
        path = tmp_path / f"{name}.csv"
        to_review_table(corpus, path)
        binding = json.loads(_rows(path)[0]["review_snapshot"])
        assert binding["analysis"]["kind"] == name
        assert binding["analysis"]["receipt"] == "unknown"
        if name == "external":
            assert binding["analysis"]["configuration"] == binding["analysis"]["generation"] == "unknown"
        else:
            assert json.loads(binding["analysis"]["configuration"])["custom_callable_identity"] == "unknown"


@pytest.mark.parametrize("edit,match", [
    ({"review_snapshot": "{"}, "invalid review snapshot JSON"),
    ({"review_snapshot": "[]"}, "digest"),
    ({"review_snapshot_sha256": "0" * 64}, "digest"),
    ({"review_snapshot": "", "review_snapshot_sha256": ""}, "snapshot is missing"),
    ({"pred_pos": "VERB"}, "prediction changed since export"),
    ({"alignment_original_text": ""}, "source alignment"),
    ({"alignment_source_token_id": ""}, "source alignment"),
])
def test_hostile_snapshot_edits_fail_cleanly_without_partial_apply(
    tmp_path: Path, edit: dict[str, str], match: str,
) -> None:
    corpus = _analyzed()
    path = tmp_path / "hostile.csv"
    to_review_table(corpus, path)
    rows = _rows(path)
    rows[0].update(decision_pos="accept")
    rows[1].update(decision_lemma="correct", correct_lemma="νόμος", **edit)
    _write(path, rows)
    before = corpus.to_json()
    with pytest.raises(ValueError, match=match):
        from_review_table(path, corpus)
    assert corpus.to_json() == before


def test_snapshot_json_duplicate_keys_and_duplicate_csv_headers_are_rejected(tmp_path: Path) -> None:
    corpus = _corpus()
    path = tmp_path / "hostile.csv"
    to_review_table(corpus, path)
    rows = _rows(path)
    rows[0].update(decision_pos="accept", review_snapshot='{"schema":"a","schema":"b"}')
    _write(path, rows)
    with pytest.raises(ValueError, match="duplicate JSON keys"):
        from_review_table(path, corpus)
    path.write_text("doc_id,position,decision_pos,decision_pos\nd,0,accept,reject\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        from_review_table(path, corpus)


def test_export_writer_cannot_emit_a_snapshot_its_reader_refuses(tmp_path: Path) -> None:
    corpus = _corpus()
    corpus.documents[0].tokens[0].annotations["model_identity"] = "x" * csv.field_size_limit()
    path = tmp_path / "existing.csv"
    path.write_text("existing", encoding="utf-8")
    with pytest.raises(ValueError, match="field size limit"):
        to_review_table(corpus, path)
    assert path.read_text(encoding="utf-8") == "existing"


def test_cli_annotated_export_uses_the_saved_analysis_for_apply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_review, "_activate", lambda **kwargs: None)
    # A deterministic fixture backend avoids downloads while exercising actual generation identity.
    real_annotate = greek.annotate_corpus
    monkeypatch.setattr(greek, "annotate_corpus", lambda corpus: real_annotate(
        corpus, tag_sentence=lambda forms: [(form, "NOUN") for form in forms]))
    source = tmp_path / "source name;literal.json"
    from_text("λόγος νόμου").to_json(source)
    table = tmp_path / "new directory" / "review name.csv"
    runner = CliRunner()
    result = runner.invoke(_build_app(), ["review", "export", str(source), "-o", str(table),
        "--annotate", "--field", "pos", "--selection", "sample", "--sample-size", "1", "--seed", "19"])
    assert result.exit_code == 0, result.output
    hint = next(line.split("then:", 1)[1].strip() for line in result.output.splitlines() if "then:" in line)
    command = shlex.split(hint)
    assert command[:3] == ["aegean", "review", "apply"] and "--annotate" not in command
    snapshot_path = Path(command[3])
    assert snapshot_path.exists() and snapshot_path != source
    generated = Corpus.from_json(snapshot_path)
    assert generated.documents[0].tokens[0].annotations["analysis_generation"]
    rows = _rows(table)
    rows[0].update(decision_pos="accept", reviewer="Alice")
    _write(table, rows)
    output = tmp_path / "reviewed.db"
    applied = runner.invoke(_build_app(), ["review", "apply", str(snapshot_path), str(table), "-o", str(output)])
    assert applied.exit_code == 0, applied.output
    assert sum(token.annotations.get("upos_verified") == "true"
               for token in Corpus.from_sql(output).documents[0].tokens) == 1
    assert all(not token.annotations for token in Corpus.from_json(source).documents[0].tokens)


@pytest.mark.parametrize("existing", [False, True])
def test_cli_never_replaces_a_user_snapshot_and_cleans_failed_exports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: bool,
) -> None:
    monkeypatch.setattr(_review, "_activate", lambda **kwargs: None)
    source, table, saved = (tmp_path / name for name in ("source.json", "table.csv", "analysis.json"))
    _analyzed().to_json(source)
    monkeypatch.setattr(greek, "annotate_corpus", lambda corpus: corpus)
    if existing:
        saved.write_text("user artifact", encoding="utf-8")
    else:
        monkeypatch.setattr("aegean.io.to_review_table", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("export failed")))
    result = CliRunner().invoke(_build_app(), ["review", "export", str(source), "-o", str(table),
        "--annotate", "--annotated-output", str(saved)])
    assert result.exit_code == 1
    assert not table.exists()
    if existing:
        assert saved.read_text(encoding="utf-8") == "user artifact"
    else:
        assert not saved.exists() and "export failed" in result.output
    assert not list(tmp_path.glob(".review-analysis-*"))


def test_nonreview_research_paths_remain_available(tmp_path: Path) -> None:
    corpus = _analyzed()
    assert all("review_history" not in token.annotations for token in corpus.documents[0].tokens)
    from aegean.db import search

    database = tmp_path / "provisional.db"
    corpus.to_sql(database)
    assert search(database, "λόγος", view="lemma") == [("research", 0, "λόγος")]
    destination = tmp_path / "provisional.json"
    corpus.to_json(destination)
    assert Corpus.from_json(destination).to_json() == corpus.to_json()


@pytest.mark.parametrize("marker", [None, False, True, 1, [], {}])
def test_nonstring_verification_markers_remain_unverified(tmp_path: Path, marker: object) -> None:
    corpus = _corpus()
    corpus.documents[0].tokens[3].annotations["upos_verified"] = marker  # type: ignore[assignment]
    path = tmp_path / "unverified.csv"
    to_review_table(corpus, path, selection="unverified", fields=("pos",))
    assert "3" in {row["position"] for row in _rows(path)}


@pytest.mark.parametrize("aligned", [False, True])
def test_identical_occurrences_have_distinct_snapshots_and_cannot_transplant_approval(
    tmp_path: Path, aligned: bool,
) -> None:
    if aligned:
        corpus = from_text("λόγος λόγος", doc_id="repeated")
        corpus.documents[0].tokens = [replace(token, annotations={"lemma": "λόγος", "upos": "NOUN"})
                                     for token in corpus.documents[0].tokens]
    else:
        tokens = [Token(text="λόγος", kind=TokenKind.WORD, position=index,
                        annotations={"lemma": "λόγος", "upos": "NOUN"}) for index in range(2)]
        corpus = Corpus([Document("repeated", "greek", tokens, [[0, 1]])])
    path = tmp_path / "transplant.csv"
    to_review_table(corpus, path)
    rows = _rows(path)
    assert rows[0]["review_snapshot_sha256"] != rows[1]["review_snapshot_sha256"]
    original_digest = rows[0]["review_snapshot_sha256"]
    rows[0]["position"] = rows[1]["position"]
    for column in rows[1]:
        if column.startswith("alignment_"):
            rows[0][column] = rows[1][column]
    rows[0].update(decision_lemma="correct", correct_lemma="λέξις")
    assert rows[0]["review_snapshot_sha256"] == original_digest
    _write(path, rows[:1])
    before = corpus.to_json()
    with pytest.raises(ValueError, match="token source/alignment identity changed"):
        from_review_table(path, corpus)
    assert corpus.to_json() == before


def test_cleared_source_id_cannot_redirect_review_to_a_repeated_occurrence(tmp_path: Path) -> None:
    corpus = from_text("λόγος λόγος", doc_id="repeated")
    corpus.documents[0].tokens = [replace(token, annotations={"lemma": "λόγος", "upos": "NOUN"})
                                 for token in corpus.documents[0].tokens]
    path = tmp_path / "erased-source.csv"
    to_review_table(corpus, path)
    rows = _rows(path)
    rows[0].update(alignment_source_token_id="", position="1", decision_lemma="correct", correct_lemma="λέξις")
    _write(path, rows[:1])
    before = corpus.to_json()
    with pytest.raises(ValueError, match="source alignment"):
        from_review_table(path, corpus)
    assert corpus.to_json() == before


@pytest.mark.parametrize("changed", ["value", "presence", "source"])
def test_actual_review_replay_does_not_excuse_later_external_output_changes(tmp_path: Path, changed: str) -> None:
    corpus = _analyzed()
    path = tmp_path / "review.csv"
    to_review_table(corpus, path)
    rows = _rows(path)
    rows[0].update(decision_lemma="correct", correct_lemma="λέξις")
    _write(path, rows)
    reviewed = from_review_table(path, corpus)
    assert apply_review_table(path, reviewed).reviewed == 0  # Actual same-correction replay is valid.
    if changed == "value":
        reviewed.documents[0].tokens[0].annotations["lemma"] = "changed externally"
    elif changed == "presence":
        del reviewed.documents[0].tokens[0].annotations["lemma"]
    else:
        reviewed.documents[0].tokens[0].annotations["lemma_source"] = "changed externally"
    rows[0].update(decision_lemma="", correct_lemma="", decision_pos="accept")
    _write(path, rows)
    before = reviewed.to_json()
    with pytest.raises(ValueError, match="changed since export"):
        from_review_table(path, reviewed)
    assert reviewed.to_json() == before


@pytest.mark.parametrize("action", ["accept", "correct", "defer", "reject"])
def test_replay_preserves_actual_decision_and_audit_history(tmp_path: Path, action: str) -> None:
    corpus = _analyzed()
    path = tmp_path / "review.csv"
    to_review_table(corpus, path)
    rows = _rows(path)
    rows[0].update(decision_lemma=action, correct_lemma="λέξις" if action == "correct" else "", reviewer="Alice")
    _write(path, rows)
    reviewed = from_review_table(path, corpus)
    replay = apply_review_table(path, reviewed)
    assert replay.corrected == replay.reviewed == 0
    assert replay.corpus.to_json() == reviewed.to_json()
    assert len(json.loads(replay.corpus.documents[0].tokens[0].annotations["review_history"])) == 1
