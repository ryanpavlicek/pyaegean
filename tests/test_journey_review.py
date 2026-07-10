"""End-to-end journeys for the human-in-the-loop review loop.

Covers the documented CLI round-trip (`aegean import` -> `review export --annotate` ->
correct in the CSV -> `review apply --annotate`) plus the `aegean.io.review` safety
contracts: token-mismatch refusal, duplicate-row conflicts, orphaned corrections,
malformed-CSV errors, the CSV formula-injection guard, feats-keyed morphology
corrections, and the export row filter (blank predictions, position-None exclusion)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aegean import greek
from aegean import io as aegean_io
from aegean.cli import _build_app
from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.io import from_review_table, to_review_table
from aegean.io.review import REVIEW_COLUMNS

TEXT = "ἐν ἀρχῇ ἦν ὁ λόγος καὶ πατρός."


def _read_rows(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(REVIEW_COLUMNS))
        w.writeheader()
        w.writerows(rows)


def _stderr(result) -> str:
    try:
        return result.stderr
    except Exception:  # stderr not captured separately on this click version
        return ""


def _one_token_corpus(text: str, annotations: dict[str, str] | None = None) -> Corpus:
    tok = Token(
        text=text, kind=TokenKind.WORD, position=0, annotations=dict(annotations or {})
    )
    doc = Document(id="d", script_id="greek", tokens=[tok], lines=[[0]])
    return Corpus([doc], script_id="greek")


# 1. The documented CLI review loop from a user-imported file -------------------------------


def test_cli_review_loop_from_imported_file(tmp_path) -> None:
    app = _build_app()
    runner = CliRunner()

    src = tmp_path / "mytext.txt"
    src.write_text(TEXT, encoding="utf-8")
    cjson = tmp_path / "c.json"
    r = runner.invoke(app, ["import", str(src), "-o", str(cjson)])
    assert r.exit_code == 0, r.output + _stderr(r)

    tcsv = tmp_path / "t.csv"
    r = runner.invoke(app, ["review", "export", str(cjson), "-o", str(tcsv), "--annotate"])
    assert r.exit_code == 0, r.output + _stderr(r)
    # the printed next-step hint tells the user to repeat --annotate on apply
    assert "review apply" in r.output
    assert "--annotate" in r.output

    rows = _read_rows(tcsv)
    assert [row["token"] for row in rows] == ["ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος", "καὶ", "πατρός"]
    logos = next(row for row in rows if row["token"] == "λόγος")
    assert logos["pred_lemma"] == "λόγος"
    assert logos["evidence_class"] != ""
    patros = next(row for row in rows if row["token"] == "πατρός")
    assert patros["pred_lemma"] == "πατρός"  # the machine value the reviewer sees (honest miss)
    patros["correct_lemma"] = "πατήρ"
    _write_rows(tcsv, rows)

    fixed = tmp_path / "fixed.json"
    r = runner.invoke(
        app,
        ["review", "apply", str(cjson), str(tcsv), "-o", str(fixed),
         "--reviewer", "R", "--annotate"],
    )
    assert r.exit_code == 0, r.output + _stderr(r)

    data = json.loads(fixed.read_text(encoding="utf-8"))
    tokens = {t["text"]: t for t in data["documents"][0]["tokens"]}
    pat = tokens["πατρός"]["annotations"]
    assert pat["lemma"] == "πατήρ"                 # the reviewer's correction landed
    assert pat["lemma__pred"] == "πατρός"          # the machine value the reviewer saw, kept
    assert pat["lemma__pred"] != ""
    assert pat["review_status"] == "corrected"
    assert pat["reviewed_by"] == "R"
    # an uncorrected token still carries its (accepted) machine annotation, unstamped
    log = tokens["λόγος"]["annotations"]
    assert log["lemma"] == "λόγος"
    assert "review_status" not in log
    notes = (data.get("provenance") or {}).get("notes", [])
    assert any(n.startswith("review: 1 tokens corrected by R") for n in notes)


# 2. Token-mismatch safety -------------------------------------------------------------------


def test_apply_against_different_corpus_raises_mismatch(tmp_path) -> None:
    a = greek.annotate_corpus(aegean_io.from_text("ἦν ὁ λόγος", doc_id="d"))
    table = tmp_path / "t.csv"
    assert to_review_table(a, table) == 3
    rows = _read_rows(table)
    assert rows[2]["token"] == "λόγος"
    rows[2]["correct_lemma"] = "λέξις"
    _write_rows(table, rows)

    # same doc id and positions, DIFFERENT token texts: the correction must never land
    b = aegean_io.from_text("καὶ θεὸς ἄνθρωπος", doc_id="d")
    with pytest.raises(ValueError, match="different token"):
        from_review_table(table, b)


# 3. Duplicate-row conflict ------------------------------------------------------------------


def test_duplicate_rows_with_conflicting_corrections_raise(tmp_path) -> None:
    c = aegean_io.from_text("ἦν ὁ λόγος", doc_id="d")
    table = tmp_path / "t.csv"
    to_review_table(c, table)
    rows = _read_rows(table)
    dup_a = dict(rows[2], correct_lemma="λέξις")
    dup_b = dict(rows[2], correct_lemma="ῥῆμα")
    _write_rows(table, [rows[0], rows[1], dup_a, dup_b])
    with pytest.raises(ValueError, match="duplicate rows"):
        from_review_table(table, c)


def test_identical_duplicate_rows_do_not_raise(tmp_path) -> None:
    c = aegean_io.from_text("ἦν ὁ λόγος", doc_id="d")
    table = tmp_path / "t.csv"
    to_review_table(c, table)
    rows = _read_rows(table)
    dup = dict(rows[2], correct_lemma="λέξις")
    _write_rows(table, [rows[0], rows[1], dup, dict(dup)])
    fixed = from_review_table(table, c)
    ann = fixed.documents[0].tokens[2].annotations
    assert ann["lemma"] == "λέξις"  # the (single, agreed) correction applied once


# 4. Orphaned corrections --------------------------------------------------------------------


def test_orphaned_correction_raises_and_blank_orphan_does_not(tmp_path) -> None:
    c = aegean_io.from_text("ἦν ὁ λόγος", doc_id="d")
    table = tmp_path / "t.csv"
    to_review_table(c, table)
    rows = _read_rows(table)
    orphan = dict(rows[0], doc_id="nope", position="99", correct_lemma="τι")
    _write_rows(table, rows + [orphan])
    with pytest.raises(ValueError, match="match no token"):
        from_review_table(table, c)

    # the same orphan row with NO correction filled in is ignored, not an error
    orphan["correct_lemma"] = ""
    _write_rows(table, rows + [orphan])
    fixed = from_review_table(table, c)
    assert [t.text for t in fixed.documents[0].tokens] == ["ἦν", "ὁ", "λόγος"]


# 5. Malformed CSV ---------------------------------------------------------------------------


def test_malformed_csv_raises_valueerror_and_cli_fails_cleanly(tmp_path) -> None:
    c = aegean_io.from_text("ἦν ὁ λόγος", doc_id="d")
    table = tmp_path / "bad.csv"
    # an unclosed quote swallows the rest of the file into one ever-growing field
    table.write_text(
        'doc_id,position,token,correct_lemma\nd,0,"unclosed ' + "x" * 200_000 + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="malformed review CSV"):
        from_review_table(table, c)

    cjson = tmp_path / "c.json"
    c.to_json(cjson)
    out = tmp_path / "fixed.json"
    r = CliRunner().invoke(
        _build_app(), ["review", "apply", str(cjson), str(table), "-o", str(out)]
    )
    combined = r.output + _stderr(r)
    assert r.exit_code == 1
    assert "Traceback" not in combined
    assert "malformed review CSV" in combined
    assert not out.exists()  # nothing was written on failure


# 6. Formula-injection guard round-trip ------------------------------------------------------


def test_formula_injection_guard_round_trips(tmp_path) -> None:
    c = _one_token_corpus("=SUM(A1)")
    table = tmp_path / "t.csv"
    assert to_review_table(c, table) == 1
    raw = table.read_text(encoding="utf-8-sig")
    assert "'=SUM" in raw       # neutralized: a spreadsheet shows text, never runs a formula
    assert ",=SUM" not in raw   # no cell starts with a live "="

    rows = _read_rows(table)
    rows[0]["correct_lemma"] = "τι"
    _write_rows(table, rows)
    fixed = from_review_table(table, c)  # guard stripped on read: no token-mismatch error
    ann = fixed.documents[0].tokens[0].annotations
    assert ann["lemma"] == "τι"
    assert ann["review_status"] == "corrected"


# 7. Feats-keyed morphology correction -------------------------------------------------------


def test_morph_correction_lands_on_feats_key(tmp_path) -> None:
    c = _one_token_corpus(
        "λόγοις", {"lemma": "λόγος", "upos": "NOUN", "feats": "Case=Dat|Number=Plur"}
    )
    table = tmp_path / "t.csv"
    to_review_table(c, table)
    rows = _read_rows(table)
    assert rows[0]["pred_morph"] == "Case=Dat|Number=Plur"

    rows[0]["correct_morph"] = "Case=Dat|Number=Sing"
    _write_rows(table, rows)
    fixed = from_review_table(table, c)
    ann = fixed.documents[0].tokens[0].annotations
    assert ann["feats"] == "Case=Dat|Number=Sing"       # the key that supplied the prediction
    assert ann["feats__pred"] == "Case=Dat|Number=Plur"
    assert "morph" not in ann
    assert "morph__pred" not in ann


# 8. Export without annotations pins the blank-prediction contract --------------------------


def test_export_of_unannotated_corpus_has_blank_predictions(tmp_path) -> None:
    c = aegean_io.from_text("ἦν ὁ λόγος", doc_id="d")
    table = tmp_path / "t.csv"
    assert to_review_table(c, table) == 3
    rows = _read_rows(table)
    assert len(rows) == 3
    assert [row["pred_lemma"] for row in rows] == ["", "", ""]
    assert [row["needs_review"] for row in rows] == ["", "", ""]


# 9. Position-None tokens are not exported ---------------------------------------------------


def test_position_none_word_token_is_not_exported(tmp_path) -> None:
    tokens = [
        Token(text="λόγος", kind=TokenKind.WORD, position=0),
        Token(text="θεός", kind=TokenKind.WORD, position=None),  # no join key: unexportable
    ]
    doc = Document(id="d", script_id="greek", tokens=tokens, lines=[[0, 1]])
    c = Corpus([doc], script_id="greek")
    table = tmp_path / "t.csv"
    assert to_review_table(c, table) == 1
    rows = _read_rows(table)
    assert [row["token"] for row in rows] == ["λόγος"]
