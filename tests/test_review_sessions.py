"""Multi-reviewer review sessions: merge several corrected copies of one export.

Covers `merge_review_tables` / `apply_merged` / the `aegean review merge` CLI across the
three dimensions the project requires:

- correctness: agreeing / disjoint / conflicting reviewer fixtures with exact outcomes, plus
  reviewer identity (column vs file-name fallback), note merging, and the merged audit trail;
- adversarial: a table from a DIFFERENT export, duplicate reviewer names, empty tables, an
  invalid ``on_conflict``, and the 0.32.0 single-reviewer guards (wrong-corpus token mismatch,
  orphaned corrections, in-file duplicate conflicts) still firing through the merge path;
- journey: export -> two reviewers correct copies -> merge -> apply -> re-read the corpus and
  assert both corrections, the ``<field>__pred`` audit trail, and both reviewer stamps.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from aegean import io as aegean_io
from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.io import (
    apply_merged,
    from_review_table,
    merge_review_tables,
    to_review_table,
)
from aegean.io.review import REVIEW_COLUMNS


# ── fixtures / helpers ─────────────────────────────────────────────────────


def _corpus() -> Corpus:
    """A three-word Greek corpus with known annotations (so predictions are deterministic)."""
    toks = [
        Token(text="ἦν", kind=TokenKind.WORD, line_no=0, position=0,
              annotations={"lemma": "εἰμί", "upos": "VERB"}),
        Token(text="ὁ", kind=TokenKind.WORD, line_no=0, position=1,
              annotations={"lemma": "ὁ", "upos": "DET"}),
        Token(text="λόγος", kind=TokenKind.WORD, line_no=0, position=2,
              annotations={"lemma": "λόγος", "upos": "NOUN"}),
    ]
    doc = Document(id="d", script_id="greek", tokens=toks, lines=[[0, 1, 2]])
    return Corpus([doc], provenance=Provenance(source="t", license="x", citation="Test 2026"),
                  script_id="greek")


def _read(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(REVIEW_COLUMNS))
        w.writeheader()
        w.writerows(rows)


def _copy(path: Path, corpus: Corpus, edits: dict[str, dict[str, str]]) -> Path:
    """Write a reviewer's corrected copy: export ``corpus`` to ``path``, then apply per-token
    ``edits`` ({token_text: {column: value}})."""
    to_review_table(corpus, path)
    rows = _read(path)
    for r in rows:
        for col, val in edits.get(r["token"], {}).items():
            r[col] = val
    _write(path, rows)
    return path


def _annotations(corpus: Corpus) -> dict[str, dict[str, str]]:
    return {t.text: dict(t.annotations) for doc in corpus.documents for t in doc.tokens}


# ── correctness: agreeing / disjoint / conflicting ─────────────────────────


def test_reviewers_agree_merges_one_clean_correction(tmp_path) -> None:
    c = _corpus()
    a = _copy(tmp_path / "alice.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "reviewer": "alice"}})
    b = _copy(tmp_path / "bob.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "reviewer": "bob"}})

    merged = merge_review_tables([a, b], c)  # default on_conflict="error"; no disagreement
    assert len(merged.rows) == 1
    assert merged.conflicts == ()
    assert merged.reviewers == ("alice", "bob")  # both credited for the agreed value

    out = apply_merged(merged, c)
    ann = _annotations(out)["λόγος"]
    assert ann["lemma"] == "λέξις"
    assert ann["lemma__pred"] == "λόγος"          # the machine value survives in the audit trail
    assert ann["review_status"] == "corrected"
    assert ann["reviewed_by"] == "alice, bob"     # both reviewers stamped on the token
    note = out.provenance.notes[-1]
    assert note.startswith("review: 1 tokens corrected by alice, bob")
    assert "merged from 2 review tables" in note


def test_disjoint_corrections_both_apply(tmp_path) -> None:
    c = _corpus()
    a = _copy(tmp_path / "alice.csv", c,
              {"ὁ": {"correct_lemma": "ho-fix", "reviewer": "alice"}})
    b = _copy(tmp_path / "bob.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "reviewer": "bob"}})

    merged = merge_review_tables([a, b], c)
    assert len(merged.rows) == 2
    assert merged.conflicts == ()

    ann = _annotations(apply_merged(merged, c))
    assert ann["ὁ"]["lemma"] == "ho-fix" and ann["ὁ"]["reviewed_by"] == "alice"
    assert ann["λόγος"]["lemma"] == "λέξις" and ann["λόγος"]["reviewed_by"] == "bob"
    assert ann["ἦν"].get("review_status") is None  # untouched token unstamped


def test_conflicting_corrections_are_surfaced_not_resolved(tmp_path) -> None:
    c = _corpus()
    a = _copy(tmp_path / "alice.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "reviewer": "alice"}})
    b = _copy(tmp_path / "bob.csv", c,
              {"λόγος": {"correct_lemma": "ῥῆμα", "reviewer": "bob"}})

    # error mode raises, listing the conflict
    with pytest.raises(ValueError, match="conflicting correction"):
        merge_review_tables([a, b], c, on_conflict="error")

    # report mode returns the conflict and applies nothing (no agreed subset here)
    merged = merge_review_tables([a, b], c, on_conflict="report")
    assert merged.rows == ()
    assert len(merged.conflicts) == 1
    conf = merged.conflicts[0]
    assert (conf.doc_id, conf.position, conf.token, conf.field) == ("d", 2, "λόγος", "lemma")
    assert {(o.reviewer, o.value) for o in conf.options} == {("alice", "λέξις"), ("bob", "ῥῆμα")}

    out = apply_merged(merged, c)
    assert _annotations(out)["λόγος"]["lemma"] == "λόγος"          # never silently resolved
    assert "review_status" not in _annotations(out)["λόγος"]
    assert out.provenance.notes == c.provenance.notes             # nothing applied, no note


def test_partial_conflict_applies_agreed_field_holds_disputed_field(tmp_path) -> None:
    c = _corpus()
    # both agree the lemma, disagree the POS
    a = _copy(tmp_path / "alice.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "correct_pos": "PROPN", "reviewer": "alice"}})
    b = _copy(tmp_path / "bob.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "correct_pos": "NOUN2", "reviewer": "bob"}})

    merged = merge_review_tables([a, b], c, on_conflict="report")
    assert len(merged.rows) == 1                       # the token still has a clean field
    assert [k.field for k in merged.conflicts] == ["pos"]

    ann = _annotations(apply_merged(merged, c))["λόγος"]
    assert ann["lemma"] == "λέξις"                     # agreed field lands
    assert "upos__pred" not in ann and ann["upos"] == "NOUN"  # disputed field untouched


def test_only_one_reviewer_corrected_a_token(tmp_path) -> None:
    c = _corpus()
    a = _copy(tmp_path / "alice.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "reviewer": "alice"}})
    b = _copy(tmp_path / "bob.csv", c, {})  # bob accepted everything

    merged = merge_review_tables([a, b], c)
    assert len(merged.rows) == 1 and merged.reviewers == ("alice",)
    assert _annotations(apply_merged(merged, c))["λόγος"]["reviewed_by"] == "alice"


# ── reviewer identity + notes ──────────────────────────────────────────────


def test_reviewer_identity_falls_back_to_file_name(tmp_path) -> None:
    c = _corpus()
    # no reviewer column filled: identity comes from the file stem
    a = _copy(tmp_path / "alice.csv", c, {"ὁ": {"correct_lemma": "ho-fix"}})
    b = _copy(tmp_path / "bob.csv", c, {"λόγος": {"correct_lemma": "λέξις"}})

    merged = merge_review_tables([a, b], c)
    assert merged.reviewers == ("alice", "bob")
    ann = _annotations(apply_merged(merged, c))
    assert ann["ὁ"]["reviewed_by"] == "alice" and ann["λόγος"]["reviewed_by"] == "bob"


def test_notes_merge_verbatim_for_one_and_attributed_for_many(tmp_path) -> None:
    c = _corpus()
    # disjoint token: alice's note stays verbatim
    a = _copy(tmp_path / "alice.csv", c,
              {"ὁ": {"correct_lemma": "ho-fix", "reviewer": "alice", "reviewer_note": "article"}})
    # agreed token: both leave a note -> attributed
    a2 = _read(a)
    for r in a2:
        if r["token"] == "λόγος":
            r.update(correct_lemma="λέξις", reviewer="alice", reviewer_note="word")
    _write(a, a2)
    b = _copy(tmp_path / "bob.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "reviewer": "bob", "reviewer_note": "logos"}})

    merged = merge_review_tables([a, b], c)
    ann = _annotations(apply_merged(merged, c))
    assert ann["ὁ"]["review_note"] == "article"                 # single contributor: verbatim
    assert ann["λόγος"]["review_note"] == "alice: word; bob: logos"  # many: attributed


def test_export_can_prestamp_the_reviewer_column(tmp_path) -> None:
    c = _corpus()
    path = tmp_path / "for-alice.csv"
    to_review_table(c, path, reviewer="alice")
    rows = _read(path)
    assert all(r["reviewer"] == "alice" for r in rows)


# ── MergedReview.to_csv round-trips and applies via `from_review_table` ─────


def test_merged_to_csv_round_trips_through_apply(tmp_path) -> None:
    c = _corpus()
    a = _copy(tmp_path / "alice.csv", c,
              {"ὁ": {"correct_lemma": "ho-fix", "reviewer": "alice"}})
    b = _copy(tmp_path / "bob.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "reviewer": "bob"}})
    merged = merge_review_tables([a, b], c)

    out_csv = tmp_path / "merged.csv"
    merged.to_csv(out_csv)
    # the written table is a valid review table with the same columns
    with open(out_csv, encoding="utf-8-sig", newline="") as f:
        assert tuple(next(csv.reader(f))) == REVIEW_COLUMNS

    # applying the merged CSV via the ordinary single-table path lands both corrections and
    # carries the per-row reviewer stamps forward
    fixed = from_review_table(out_csv, c)
    ann = _annotations(fixed)
    assert ann["ὁ"]["lemma"] == "ho-fix" and ann["ὁ"]["reviewed_by"] == "alice"
    assert ann["λόγος"]["lemma"] == "λέξις" and ann["λόγος"]["reviewed_by"] == "bob"


def test_formula_injection_guard_survives_the_merge_path(tmp_path) -> None:
    c = _corpus()
    a = _copy(tmp_path / "alice.csv", c,
              {"λόγος": {"correct_lemma": "=EVIL()", "reviewer": "alice"}})
    b = _copy(tmp_path / "bob.csv", c,
              {"λόγος": {"correct_lemma": "=EVIL()", "reviewer": "bob"}})
    merged = merge_review_tables([a, b], c)
    out_csv = tmp_path / "merged.csv"
    merged.to_csv(out_csv)
    raw = out_csv.read_text(encoding="utf-8-sig")
    assert "'=EVIL()" in raw and ",=EVIL()" not in raw   # neutralized on write
    # the guard is stripped on read, so the correction still lands cleanly
    assert _annotations(apply_merged(merged, c))["λόγος"]["lemma"] == "=EVIL()"


# ── the 0.32.0 single-reviewer guards still fire through the merge path ─────


def test_wrong_corpus_token_mismatch_still_raises_through_merge(tmp_path) -> None:
    c = _corpus()
    a = _copy(tmp_path / "alice.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "reviewer": "alice"}})
    b = _copy(tmp_path / "bob.csv", c,
              {"ὁ": {"correct_lemma": "ho-fix", "reviewer": "bob"}})
    merged = merge_review_tables([a, b], c)

    # apply the (valid) merge to a DIFFERENT corpus: same ids/positions, different tokens
    other_toks = [Token(text=t, kind=TokenKind.WORD, line_no=0, position=i)
                  for i, t in enumerate(["καὶ", "θεὸς", "ἄνθρωπος"])]
    other = Corpus([Document(id="d", script_id="greek", tokens=other_toks, lines=[[0, 1, 2]])],
                   provenance=Provenance(source="o", license="x"), script_id="greek")
    with pytest.raises(ValueError, match="different token"):
        apply_merged(merged, other)


def test_orphaned_merged_correction_matches_no_token(tmp_path) -> None:
    c = _corpus()
    # a reviewer adds a spurious extra row whose (doc_id, position) is not in the corpus -> the
    # merge must flag it as matching no token (the 0.32.0 orphan guard, up front)
    def _with_orphan(name: str, reviewer: str) -> Path:
        path = tmp_path / name
        to_review_table(c, path)
        rows = _read(path)
        orphan = dict(rows[0], doc_id="d", position="99", token="ξένος",
                      correct_lemma="τι", reviewer=reviewer)
        _write(path, rows + [orphan])
        return path

    with pytest.raises(ValueError, match="match no token"):
        merge_review_tables([_with_orphan("a.csv", "alice"),
                             _with_orphan("b.csv", "bob")], c)


def test_in_file_duplicate_conflict_raises_through_merge(tmp_path) -> None:
    c = _corpus()
    good = _copy(tmp_path / "alice.csv", c,
                 {"λόγος": {"correct_lemma": "λέξις", "reviewer": "alice"}})
    # bob's file carries duplicate rows for one token with conflicting corrections
    bob = tmp_path / "bob.csv"
    to_review_table(c, bob)
    rows = _read(bob)
    dup_a = dict(rows[2], correct_lemma="ῥῆμα", reviewer="bob")
    dup_b = dict(rows[2], correct_lemma="μῦθος", reviewer="bob")
    _write(bob, [rows[0], rows[1], dup_a, dup_b])
    with pytest.raises(ValueError, match="duplicate rows"):
        merge_review_tables([good, bob], c, on_conflict="report")


# ── adversarial ────────────────────────────────────────────────────────────


def test_table_from_a_different_export_is_rejected(tmp_path) -> None:
    c1 = _corpus()
    # a copy exported from a DIFFERENT corpus (same ids/positions, different tokens)
    other_toks = [Token(text=t, kind=TokenKind.WORD, line_no=0, position=i)
                  for i, t in enumerate(["καὶ", "θεὸς", "ἄνθρωπος"])]
    c2 = Corpus([Document(id="d", script_id="greek", tokens=other_toks, lines=[[0, 1, 2]])],
                provenance=Provenance(source="o", license="x"), script_id="greek")
    a = _copy(tmp_path / "alice.csv", c1,
              {"λόγος": {"correct_lemma": "λέξις", "reviewer": "alice"}})
    b = _copy(tmp_path / "bob.csv", c2,
              {"ἄνθρωπος": {"correct_lemma": "X", "reviewer": "bob"}})
    with pytest.raises(ValueError, match="different token than the corpus"):
        merge_review_tables([a, b], c1, on_conflict="report")


def test_duplicate_reviewer_names_are_rejected(tmp_path) -> None:
    c = _corpus()
    a = _copy(tmp_path / "x.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "reviewer": "same"}})
    b = _copy(tmp_path / "y.csv", c,
              {"ὁ": {"correct_lemma": "ho-fix", "reviewer": "same"}})
    with pytest.raises(ValueError, match="appear in more than one table"):
        merge_review_tables([a, b], c, on_conflict="report")


def test_one_table_naming_two_reviewers_is_rejected(tmp_path) -> None:
    c = _corpus()
    path = tmp_path / "mixed.csv"
    to_review_table(c, path)
    rows = _read(path)
    rows[1].update(correct_lemma="ho-fix", reviewer="alice")
    rows[2].update(correct_lemma="λέξις", reviewer="bob")  # two reviewers in one file
    _write(path, rows)
    b = _copy(tmp_path / "b.csv", c, {"ἦν": {"correct_lemma": "εἰμί2", "reviewer": "carol"}})
    with pytest.raises(ValueError, match="names more than one reviewer"):
        merge_review_tables([path, b], c, on_conflict="report")


def test_empty_tables_merge_to_a_noop(tmp_path) -> None:
    c = _corpus()
    for name in ("e1.csv", "e2.csv"):
        with open(tmp_path / name, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerow(REVIEW_COLUMNS)  # header only, no rows
    merged = merge_review_tables([tmp_path / "e1.csv", tmp_path / "e2.csv"], c)
    assert merged.rows == () and merged.conflicts == () and merged.reviewers == ()
    out = apply_merged(merged, c)
    assert out.provenance.notes == c.provenance.notes  # no-op leaves provenance untouched


def test_invalid_on_conflict_and_empty_paths_raise(tmp_path) -> None:
    c = _corpus()
    a = _copy(tmp_path / "a.csv", c, {"λόγος": {"correct_lemma": "λέξις", "reviewer": "alice"}})
    with pytest.raises(ValueError, match="on_conflict must be"):
        merge_review_tables([a], c, on_conflict="nonsense")
    with pytest.raises(ValueError, match="no review tables"):
        merge_review_tables([], c)


# ── journey: export -> two reviewers -> merge -> apply -> re-read ───────────


def test_journey_two_reviewers_merge_apply_reread(tmp_path) -> None:
    typer_testing = pytest.importorskip("typer.testing")
    from aegean.cli import _build_app

    runner = typer_testing.CliRunner()
    app = _build_app()

    # 1. import a user's text and export the review table
    src = tmp_path / "text.txt"
    src.write_text("ἐν ἀρχῇ ἦν ὁ λόγος", encoding="utf-8")
    cjson = tmp_path / "c.json"
    assert runner.invoke(app, ["import", str(src), "-o", str(cjson)]).exit_code == 0

    corpus = aegean_io.from_text("ἐν ἀρχῇ ἦν ὁ λόγος", doc_id=Path(src).stem)
    from aegean import greek
    annotated = greek.annotate_corpus(corpus)
    annotated.to_json(cjson)  # the corpus apply will read (annotated, matches the CLI --annotate)

    base = tmp_path / "base.csv"
    to_review_table(annotated, base)
    base_rows = _read(base)
    pred = {r["token"]: r["pred_lemma"] for r in base_rows}
    # corrections chosen to differ from the machine prediction, so a real edit is recorded
    fix_logos = pred["λόγος"] + "-A"
    fix_arche = pred["ἀρχῇ"] + "-B"

    # 2. two reviewers each correct their own copy, on DIFFERENT tokens
    alice = tmp_path / "alice.csv"
    _write(alice, [dict(r, correct_lemma=fix_logos, reviewer="alice")
                   if r["token"] == "λόγος" else dict(r) for r in base_rows])
    bob = tmp_path / "bob.csv"
    _write(bob, [dict(r, correct_lemma=fix_arche, reviewer="bob")
                 if r["token"] == "ἀρχῇ" else dict(r) for r in base_rows])

    # 3. merge (CLI), writing the agreed table
    merged_csv = tmp_path / "merged.csv"
    r = runner.invoke(app, ["review", "merge", str(alice), str(bob),
                            "--corpus", str(cjson), "-o", str(merged_csv)])
    assert r.exit_code == 0, r.output
    assert merged_csv.exists()

    # 4. apply the merged table and re-read the corrected corpus
    fixed = tmp_path / "fixed.json"
    r = runner.invoke(app, ["review", "apply", str(cjson), str(merged_csv), "-o", str(fixed)])
    assert r.exit_code == 0, r.output

    data = json.loads(fixed.read_text(encoding="utf-8"))
    toks = {t["text"]: t["annotations"] for t in data["documents"][0]["tokens"]}
    # both corrections landed with the full <field>__pred audit trail and reviewer stamps
    assert toks["λόγος"]["lemma"] == fix_logos
    assert toks["λόγος"]["lemma__pred"] == pred["λόγος"]
    assert toks["λόγος"]["reviewed_by"] == "alice"
    assert toks["ἀρχῇ"]["lemma"] == fix_arche
    assert toks["ἀρχῇ"]["lemma__pred"] == pred["ἀρχῇ"]
    assert toks["ἀρχῇ"]["reviewed_by"] == "bob"
    # an untouched token keeps its accepted machine lemma, unstamped
    assert "review_status" not in toks["ἦν"]
    note = (data.get("provenance") or {}).get("notes", [])[-1]
    assert note.startswith("review: 2 tokens corrected by alice, bob")


def test_cli_merge_error_mode_exits_nonzero_on_conflict(tmp_path) -> None:
    typer_testing = pytest.importorskip("typer.testing")
    from aegean.cli import _build_app

    c = _corpus()
    cjson = tmp_path / "c.json"
    c.to_json(cjson)
    a = _copy(tmp_path / "alice.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "reviewer": "alice"}})
    b = _copy(tmp_path / "bob.csv", c,
              {"λόγος": {"correct_lemma": "ῥῆμα", "reviewer": "bob"}})

    runner = typer_testing.CliRunner()
    app = _build_app()
    # default (error) mode: the conflict is shown and the command fails
    r = runner.invoke(app, ["review", "merge", str(a), str(b), "--corpus", str(cjson)])
    assert r.exit_code == 1
    combined = r.output + (r.stderr if hasattr(r, "stderr") else "")
    assert "unresolved conflict" in combined
    # report mode: same conflict, but a clean exit
    r = runner.invoke(app, ["review", "merge", str(a), str(b),
                            "--corpus", str(cjson), "--on-conflict", "report"])
    assert r.exit_code == 0, r.output


def test_cli_merge_needs_at_least_two_tables(tmp_path) -> None:
    typer_testing = pytest.importorskip("typer.testing")
    from aegean.cli import _build_app

    c = _corpus()
    cjson = tmp_path / "c.json"
    c.to_json(cjson)
    a = _copy(tmp_path / "alice.csv", c,
              {"λόγος": {"correct_lemma": "λέξις", "reviewer": "alice"}})
    r = typer_testing.CliRunner().invoke(
        _build_app(), ["review", "merge", str(a), "--corpus", str(cjson)]
    )
    assert r.exit_code == 1
    assert "at least two" in (r.output + (r.stderr if hasattr(r, "stderr") else ""))
