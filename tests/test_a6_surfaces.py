"""A6 editorial-form state at user-facing rows and review boundaries."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aegean import mcp_server
from aegean._view import pipeline_rows_from_records
from aegean.core.corpus import Corpus
from aegean.core.model import (
    Document,
    FormSegment,
    ReadingStatus,
    SourceMarkupRef,
    Token,
    TokenFormState,
    TokenKind,
)
from aegean.io.review import REVIEW_COLUMNS, from_review_table, to_review_table
from aegean.io.tabular import _progress_dataframe
from aegean.io.tabular import to_csv
from aegean.io.workbench import to_workbench
from aegean.tui.data import document_detail
from aegean.greek.lemmatize import LemmaSource


def _state() -> TokenFormState:
    return TokenFormState(
        diplomatic="a-b",
        regularized="ab",
        normalized="ab",
        model_input="ab",
        segments=(
            FormSegment("a"),
            FormSegment(
                "b",
                ReadingStatus.RESTORED,
                SourceMarkupRef("ed-1", "text/body/w[1]", "supplied"),
            ),
            FormSegment("", ReadingStatus.LOST),
        ),
        model_input_ops=("join",),
        model_input_source="normalized",
    )


def _corpus() -> Corpus:
    token = Token(
        "a-b",
        TokenKind.WORD,
        position=0,
        annotations={
            "form_diplomatic": "spoof",
            "form_segments": "spoof",
            "lemma": "a-b",
            "upos": "X",
            "lemma_source": "identity",
        },
        form_state=_state(),
    )
    doc = Document("d", "greek", [token], [[0]])
    return Corpus([doc], script_id="greek")


def _record_with_state() -> SimpleNamespace:
    return SimpleNamespace(
        sentence=0,
        index=1,
        text="a-b",
        upos="NOUN",
        lemma="a-b",
        lemma_source=LemmaSource.RULE,
        lemma_resolved=True,
        lemma_verified=False,
        review_recommended=False,
        head=None,
        relation=None,
        xpos=None,
        feats=None,
        neural_analyzed=None,
        analysis_complete=True,
        analysis_warning=None,
        analysis_receipt=None,
        boundary_policy=None,
        boundary_policy_id=None,
        boundary_provenance=None,
        boundary_confidence=None,
        boundary_start_char=None,
        boundary_end_char=None,
        alignment=None,
        upos_confidence=None,
        lemma_confidence=None,
        form_state=_state(),
    )


def test_pipeline_rows_are_json_ready_and_state_is_distinct() -> None:
    rows = pipeline_rows_from_records([_record_with_state()])
    row = rows[0]
    assert json.loads(json.dumps(rows, ensure_ascii=False)) == rows
    assert row["form_diplomatic"] == "a-b"
    assert row["form_diplomatic"] != "spoof"
    assert row["form_model_input"] == "ab"
    assert row["form_model_input_ops"] == ["join"]
    assert row["form_segments"][1]["status"] == "restored"
    assert row["form_supplied_text"] == "b"
    assert row["form_lost_text"] == ""
    assert row["form_editorial_status"] == "lost"
    assert row["form_has_damage"] is True
    assert row["form_has_uncertainty"] is False
    assert row["boundary_policy"] is None
    assert row["boundary_start_char"] is None


def test_tabular_progress_matches_corpus_with_canonical_form_columns() -> None:
    pytest.importorskip("pandas")
    corpus = _corpus()
    expected = corpus.to_dataframe("token")
    actual = _progress_dataframe(corpus, "token", lambda _done, _total: None)
    assert actual.equals(expected)
    row = actual.iloc[0]
    assert row["form_diplomatic"] == "a-b"
    assert row["form_diplomatic"] != "spoof"
    assert json.loads(row["form_segments"])[1]["status"] == "restored"


def test_tabular_progress_csv_bytes_match_default(tmp_path: Path) -> None:
    pytest.importorskip("pandas")
    corpus = _corpus()
    ordinary = tmp_path / "ordinary.csv"
    reported = tmp_path / "reported.csv"
    to_csv(corpus, ordinary, level="token")
    to_csv(corpus, reported, level="token", progress=lambda _done, _total: None)
    assert ordinary.read_bytes() == reported.read_bytes()


def _edit_review(path: Path, **changes: str) -> None:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0].update(changes)
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REVIEW_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def test_review_state_columns_are_guarded_and_tamper_refused(tmp_path: Path) -> None:
    corpus = _corpus()
    path = tmp_path / "review.csv"
    assert to_review_table(corpus, path) == 1
    with open(path, encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["form_diplomatic"] == "a-b"
    assert json.loads(row["form_segments"])[2]["status"] == "lost"
    assert json.loads(row["form_state_json"])["regularized"] == "ab"

    _edit_review(path, correct_lemma="ab", form_diplomatic="tampered")
    with pytest.raises(ValueError, match="form state"):
        from_review_table(path, corpus)


def test_review_guard_distinguishes_absent_and_empty_optional_forms(tmp_path: Path) -> None:
    state = TokenFormState(diplomatic="a", regularized=None)
    token = Token("a", TokenKind.WORD, position=0, form_state=state)
    corpus = Corpus([Document("d", "greek", [token], [[0]])], script_id="greek")
    path = tmp_path / "review.csv"
    to_review_table(corpus, path)

    tampered = TokenFormState(diplomatic="a", regularized="")
    changed = Corpus(
        [Document("d", "greek", [Token("a", TokenKind.WORD, position=0, form_state=tampered)], [[0]])],
        script_id="greek",
    )
    _edit_review(path, correct_lemma="a")
    with pytest.raises(ValueError, match="form state"):
        from_review_table(path, changed)


def test_old_review_file_without_form_columns_remains_compatible(tmp_path: Path) -> None:
    corpus = _corpus()
    path = tmp_path / "review.csv"
    to_review_table(corpus, path)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    old_columns = [col for col in REVIEW_COLUMNS if not col.startswith("form_")]
    old = tmp_path / "old-review.csv"
    with open(old, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=old_columns)
        writer.writeheader()
        writer.writerow({col: row[col] for col in old_columns})
    with open(old, encoding="utf-8-sig", newline="") as handle:
        old_rows = list(csv.DictReader(handle))
    old_rows[0]["correct_lemma"] = "ab"
    with open(old, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=old_columns)
        writer.writeheader()
        writer.writerows(old_rows)
    corrected = from_review_table(old, corpus)
    assert corrected.documents[0].tokens[0].annotations["lemma"] == "ab"


def test_tui_and_mcp_show_form_state_without_dataclass_leak(monkeypatch) -> None:
    corpus = _corpus()
    detail = document_detail(corpus, "d")
    cell = detail.lines[0].tokens[0]
    assert cell.form_state is not None
    assert cell.form_state["diplomatic"] == "a-b"
    json.dumps(cell.form_state, ensure_ascii=False)

    monkeypatch.setattr(mcp_server, "_load_corpus", lambda _name: (corpus, None))
    shown = mcp_server.show_document("custom", "d")
    assert shown["lines"] == [["a-b"]]
    assert shown["tokens"][0]["form_diplomatic"] == "a-b"
    assert shown["tokens"][0]["form_state"]["diplomatic"] == "a-b"
    json.dumps(shown, ensure_ascii=False)


def test_cli_show_displays_form_state_in_json_and_human_output(monkeypatch) -> None:
    pytest.importorskip("typer")
    from typer.testing import CliRunner

    from aegean.cli import _build_app
    from aegean.cli import _corpus as corpus_commands

    monkeypatch.setattr(corpus_commands, "load_corpus", lambda _name: _corpus())
    runner = CliRunner()
    app = _build_app()

    machine = runner.invoke(app, ["show", "custom", "d", "--json"])
    assert machine.exit_code == 0, machine.output
    payload = json.loads(machine.stdout)
    assert payload["tokens"][0]["form_diplomatic"] == "a-b"
    assert payload["tokens"][0]["form_state"]["regularized"] == "ab"

    human = runner.invoke(app, ["show", "custom", "d"])
    assert human.exit_code == 0, human.output
    assert "diplomatic='a-b'" in human.stdout
    assert "regularized='ab'" in human.stdout


def test_tui_reader_renders_the_editorial_form_distinction() -> None:
    pytest.importorskip("textual")
    from aegean.tui.widgets import _reader_token_text

    cell = document_detail(_corpus(), "d").lines[0].tokens[0]
    rendered = _reader_token_text(cell)
    assert rendered.startswith("a-b")
    assert "[regularized ab]" in rendered


def test_workbench_shape_retains_documented_lossy_form_decision() -> None:
    record = to_workbench(_corpus())[0]
    assert not any(key.startswith("form_") for key in record)
