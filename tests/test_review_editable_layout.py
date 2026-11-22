"""Tests for editable-first review CSV layout with SHA-256-bound immutable companion."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from aegean.core.corpus import Corpus
from aegean.core.model import Document, SourceAlignment, Token, TokenFormState, TokenKind
from aegean.core.provenance import Provenance
from aegean.io.review import (
    EDITABLE_REVIEW_COLUMNS,
    REVIEW_COLUMNS,
    apply_merged,
    apply_review_table,
    from_review_table,
    merge_review_tables,
    review_companion_path,
    to_review_table,
)


def _annotated_tragedy_corpus() -> Corpus:
    """Build a multi-clause Greek sentence with punctuation, alignment whitespace,
    typed TokenFormState, and full dependency sentence ownership."""
    raw_words = [
        ("μῆνιν", "μῆνις", "NOUN", "Case=Acc|Gender=Fem|Number=Sing", "2", "obj", ""),
        ("ἄειδε", "ἀείδω", "VERB", "Mood=Imp|Number=Sing|Person=2|Tense=Pres|Voice=Act", "0", "root", " "),
        (",", ",", "PUNCT", "", "2", "punct", ""),
        ("θεά", "θεά", "NOUN", "Case=Voc|Gender=Fem|Number=Sing", "2", "vocative", "\n  "),
        (",", ",", "PUNCT", "", "4", "punct", ""),
        ("Πηληϊάδεω", "Πηληϊάδης", "PROPN", "Case=Gen|Gender=Masc|Number=Sing", "7", "nmod", " "),
        ("Ἀχιλῆος", "Ἀχιλλεύς", "PROPN", "Case=Gen|Gender=Masc|Number=Sing", "1", "nmod", " "),
        ("οὐλομένην", "οὐλόμενος", "ADJ", "Case=Acc|Gender=Fem|Number=Sing", "1", "amod", " "),
        ("·", "·", "PUNCT", "", "2", "punct", ""),
    ]
    tokens: list[Token] = []
    offset = 0
    for idx, (surface, lemma, upos, feats, head, deprel, ws) in enumerate(raw_words):
        start = offset + len(ws)
        end = start + len(surface)
        offset = end
        kind = TokenKind.PUNCT if upos == "PUNCT" else TokenKind.WORD
        tokens.append(
            Token(
                text=surface,
                kind=kind,
                position=idx,
                line_no=1 if idx < 3 else 2,
                alignment=SourceAlignment(
                    document_id="doc1",
                    sentence_id="doc1:s1",
                    source_token_id=f"doc1:t{idx}",
                    original_text=surface,
                    start_char=start,
                    end_char=end,
                    whitespace_before=ws,
                    normalized_text=surface,
                    normalization_ops=(),
                ),
                form_state=TokenFormState(
                    diplomatic=surface,
                    regularized=surface,
                    normalized=surface,
                    model_input=surface,
                    model_input_source="normalized",
                ),
                annotations={
                    "ref": f"1.{1 if idx < 3 else 2}",
                    "lemma": lemma,
                    "upos": upos,
                    "feats": feats,
                    "head": head,
                    "deprel": deprel,
                    "lemma_source": "neural_edit" if idx == 0 else "neural_lookup",
                    "review_recommended": "true" if idx == 0 else "false",
                    "dependency_sentence_id": "doc1:s1",
                    "dependency_index": str(idx + 1),
                    "analysis_kind": "neural",
                    "analysis_generation": "v3-test",
                },
            )
        )
    doc = Document(
        id="doc1",
        script_id="greek",
        lines=["μῆνιν ἄειδε,", "  θεά, Πηληϊάδεω Ἀχιλῆος οὐλομένην·"],
        tokens=tokens,
        source_text="μῆνιν ἄειδε,\n  θεά, Πηληϊάδεω Ἀχιλῆος οὐλομένην·",
    )
    prov = Provenance(source="unit-test", citation="Test 1.1-2")
    return Corpus([doc], provenance=prov, script_id="greek")


def _edit_csv(
    path: Path,
    edits: dict[str, dict[str, str]],
    *,
    strip_bom: bool = False,
    crlf: bool = False,
) -> None:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames is not None
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    for row in rows:
        key = row.get("row_id") or f"{row['doc_id']}#{row['position']}"
        if key in edits:
            row.update(edits[key])
    encoding = "utf-8" if strip_bom else "utf-8-sig"
    lineterminator = "\r\n" if crlf else "\n"
    with open(path, "w", encoding=encoding, newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator=lineterminator)
        w.writeheader()
        w.writerows(rows)


def test_editable_layout_writes_compact_csv_and_hash_bound_companion(tmp_path: Path) -> None:
    corpus = _annotated_tragedy_corpus()
    csv_path = tmp_path / "pilot.csv"
    n = to_review_table(
        corpus,
        csv_path,
        fields=("lemma", "pos", "morph", "head", "deprel"),
        reviewer="alice",
        layout="editable",
    )
    assert n == 9
    companion = review_companion_path(csv_path)
    assert companion.is_file()

    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        assert tuple(reader.fieldnames or ()) == EDITABLE_REVIEW_COLUMNS
        assert len(EDITABLE_REVIEW_COLUMNS) < len(REVIEW_COLUMNS)
        rows = list(reader)
    assert len(rows) == 9
    assert "review_snapshot" not in rows[0]
    assert "dependency_sentence_context" not in rows[0]
    assert "alignment_whitespace_before" not in rows[0]
    assert rows[0]["row_id"] == "doc1:t0"

    comp_data = json.loads(companion.read_text(encoding="utf-8"))
    assert comp_data["schema"] == "pyaegean-review-companion/1"
    assert comp_data["layout"] == "editable"
    assert comp_data["row_count"] == 9
    assert comp_data["rows"]["doc1:t3"]["alignment_whitespace_before"] == "\n  "

    # Default layout="full" writes 60-column CSV and no companion
    full_path = tmp_path / "full.csv"
    to_review_table(corpus, full_path, fields=("lemma", "head", "deprel"))
    assert not review_companion_path(full_path).exists()
    with open(full_path, encoding="utf-8-sig", newline="") as f:
        assert tuple(csv.DictReader(f).fieldnames or ()) == REVIEW_COLUMNS


def test_editable_layout_survives_spreadsheet_roundtrip_with_whitespace_and_punctuation(
    tmp_path: Path,
) -> None:
    corpus = _annotated_tragedy_corpus()
    csv_path = tmp_path / "sheet.csv"
    to_review_table(
        corpus,
        csv_path,
        fields=("lemma", "pos", "head", "deprel"),
        reviewer="alice",
        layout="editable",
    )
    # Simulate Excel/Sheets saving without BOM, with CRLF, and padded editable values
    _edit_csv(
        csv_path,
        {
            "doc1:t0": {
                "decision_lemma": " accept ",
                "reviewer_note": " confirmed Homeric lemma ",
                "reviewer_evidence": " LSJ s.v. μῆνις ",
            },
            "doc1:t7": {
                "decision_lemma": "correct",
                "correct_lemma": "ὄλλυμι",
                "decision_head": "correct",
                "correct_head": "2",
                "decision_deprel": "correct",
                "correct_deprel": "xcomp",
            },
        },
        strip_bom=True,
        crlf=True,
    )

    app = apply_review_table(csv_path, corpus)
    assert app.rows == 9
    assert app.reviewed == 2
    assert app.corrected == 1

    tok0 = app.corpus.documents[0].tokens[0]
    tok3 = app.corpus.documents[0].tokens[3]
    tok7 = app.corpus.documents[0].tokens[7]
    assert tok0.annotations["lemma_verified"] == "true"
    assert tok0.annotations["lemma_review_decision"] == "accept"
    assert tok3.alignment is not None and tok3.alignment.whitespace_before == "\n  "
    assert tok7.annotations["lemma"] == "ὄλλυμι"
    assert tok7.annotations["lemma__pred"] == "οὐλόμενος"
    assert tok7.annotations["head"] == "2"
    assert tok7.annotations["deprel"] == "xcomp"

    # Repeat-apply of the same editable table is idempotent
    reapplied = from_review_table(csv_path, app.corpus)
    assert reapplied.documents[0].tokens[7].annotations["lemma"] == "ὄλλυμι"


def test_editable_layout_two_reader_merge_cycle_detection_and_merged_editable_export(
    tmp_path: Path,
) -> None:
    corpus = _annotated_tragedy_corpus()
    a_csv = tmp_path / "reader_a.csv"
    b_csv = tmp_path / "reader_b.csv"
    for path, who in ((a_csv, "alice"), (b_csv, "bob")):
        to_review_table(
            corpus,
            path,
            fields=("lemma", "head", "deprel"),
            reviewer=who,
            layout="editable",
        )

    # Agreed lemma correction + individually valid head edits (1->4 and 4->1) that form a cycle!
    _edit_csv(
        a_csv,
        {
            "doc1:t0": {
                "decision_lemma": "correct",
                "correct_lemma": "μῆνις_epic",
                "decision_head": "correct",
                "correct_head": "4",
                "reviewer_note": "alice note",
            },
        },
    )
    _edit_csv(
        b_csv,
        {
            "doc1:t0": {
                "decision_lemma": "correct",
                "correct_lemma": "μῆνις_epic",
                "reviewer_note": "bob note",
            },
            "doc1:t3": {
                "decision_head": "correct",
                "correct_head": "1",
                "reviewer_note": "bob head note",
            },
        },
    )

    merged = merge_review_tables([a_csv, b_csv], corpus, on_conflict="report")
    # Combined 1->4 and 4->1 forms a cycle, so dependency edits roll back as conflict,
    # while agreed lemma correction survives cleanly!
    assert len(merged.conflicts) == 1
    assert merged.conflicts[0].field == "head"
    assert "combined tree invalid" in merged.conflicts[0].options[0].note

    # Write merged output in editable layout and apply via from_review_table
    merged_csv = tmp_path / "merged.csv"
    merged.to_csv(merged_csv, layout="editable")
    assert review_companion_path(merged_csv).is_file()

    applied_via_csv = from_review_table(merged_csv, corpus)
    applied_direct = apply_merged(merged, corpus)
    assert applied_via_csv.documents[0].tokens[0].annotations["lemma"] == "μῆνις_epic"
    assert applied_direct.documents[0].tokens[0].annotations["lemma"] == "μῆνις_epic"
    assert applied_via_csv.documents[0].tokens[0].annotations["head"] == "2"
    assert applied_via_csv.documents[0].tokens[3].annotations["head"] == "2"
    assert "alice" in applied_via_csv.documents[0].tokens[0].annotations["lemma_reviewed_by"]
    assert "bob" in applied_via_csv.documents[0].tokens[0].annotations["lemma_reviewed_by"]


def test_editable_layout_fails_closed_on_missing_or_tampered_companion_and_stale_corpus(
    tmp_path: Path,
) -> None:
    corpus = _annotated_tragedy_corpus()
    csv_path = tmp_path / "guarded.csv"
    to_review_table(corpus, csv_path, fields=("lemma",), reviewer="alice", layout="editable")
    companion = review_companion_path(csv_path)

    # 1. Tampered companion digest
    bad = json.loads(companion.read_text(encoding="utf-8"))
    bad["rows"]["doc1:t0"]["token"] = "TAMPERED"
    companion.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        apply_review_table(csv_path, corpus)

    # Restore valid export
    to_review_table(corpus, csv_path, fields=("lemma",), reviewer="alice", layout="editable")

    # 2. Missing companion
    saved_companion = companion.read_text(encoding="utf-8")
    companion.unlink()
    with pytest.raises(ValueError, match="companion snapshot"):
        apply_review_table(csv_path, corpus)
    companion.write_text(saved_companion, encoding="utf-8")

    # 3. Mutated read-only display column in CSV
    _edit_csv(csv_path, {"doc1:t0": {"token": "μῆνιν_edited"}})
    with pytest.raises(ValueError, match="read-only column 'token'"):
        apply_review_table(csv_path, corpus)

    # 4. Stale corpus (mutated after export) still rejected via rehydrated snapshot
    to_review_table(corpus, csv_path, fields=("lemma",), reviewer="alice", layout="editable")
    _edit_csv(csv_path, {"doc1:t0": {"decision_lemma": "accept"}})
    mutated_tok = replace(
        corpus.documents[0].tokens[0],
        annotations={**corpus.documents[0].tokens[0].annotations, "lemma": "different"},
    )
    mutated_doc = replace(
        corpus.documents[0],
        tokens=[mutated_tok, *corpus.documents[0].tokens[1:]],
    )
    stale_corpus = Corpus([mutated_doc], provenance=corpus.provenance, script_id="greek")
    with pytest.raises(ValueError, match="changed since export"):
        apply_review_table(csv_path, stale_corpus)
