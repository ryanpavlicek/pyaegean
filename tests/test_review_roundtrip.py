"""The human review round-trip: to_review_table -> corrections -> from_review_table.

Offline: a synthetic corpus + a hand-edited CSV, plus the CLI export/apply commands. Verifies
the table shape, the needs-review triage, the join-by-position correction, provenance stamping,
and that annotate_corpus fills the annotations the table draws on."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from aegean import greek
from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.io import REVIEW_COLUMNS, from_review_table, needs_review_flag, to_review_table


def _corpus() -> Corpus:
    toks = [
        Token(text="νόμου", kind=TokenKind.WORD, line_no=0, position=0,
              annotations={"lemma": "νόμος", "upos": "NOUN", "lemma_source": "rule",
                           "lemma_known": "true"}),
        Token(text=",", kind=TokenKind.PUNCT, line_no=0, position=1),
        Token(text="πατρός", kind=TokenKind.WORD, line_no=0, position=2,
              annotations={"lemma": "πατρός", "upos": "NOUN", "lemma_source": "unresolved",
                           "lemma_known": "false"}),
    ]
    doc = Document(id="d1", script_id="greek", tokens=toks, lines=[[0, 1, 2]])
    return Corpus([doc], provenance=Provenance(source="t", license="x", citation="Test 2026"),
                  script_id="greek")


def test_needs_review_flag_reads_the_evidence_class() -> None:
    assert needs_review_flag({"lemma_source": "identity"}) is True
    assert needs_review_flag({"lemma_source": "unresolved"}) is True
    assert needs_review_flag({"lemma_source": "attested"}) is False
    assert needs_review_flag({"lemma_source": "neural"}) is False
    assert needs_review_flag({"lemma_known": "false"}) is True   # fallback when no source key
    assert needs_review_flag({}) is False                        # gold token: not flagged


def test_to_review_table_shape_and_greek(tmp_path) -> None:
    path = tmp_path / "review.csv"
    n = to_review_table(_corpus(), path)
    assert n == 2  # two WORD tokens; the comma is skipped
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert tuple(rows[0]) == REVIEW_COLUMNS
    body = {r[4]: r for r in rows[1:]}  # keyed by token text (Greek survives the BOM round-trip)
    assert set(body) == {"νόμου", "πατρός"}
    cols = {c: i for i, c in enumerate(REVIEW_COLUMNS)}
    assert body["πατρός"][cols["needs_review"]] == "yes"        # unresolved -> flagged
    assert body["νόμου"][cols["needs_review"]] == ""            # rule -> grounded
    assert body["νόμου"][cols["source_citation"]] == "Test 2026"


def test_only_needs_review_filters_rows(tmp_path) -> None:
    path = tmp_path / "flagged.csv"
    n = to_review_table(_corpus(), path, only_needs_review=True)
    assert n == 1
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["token"] for r in rows] == ["πατρός"]


def _write_edits(path: Path, edits: dict[str, dict[str, str]]) -> None:
    """Rewrite a review CSV, applying {token: {column: value}} edits."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for col, val in edits.get(r["token"], {}).items():
            r[col] = val
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(REVIEW_COLUMNS))
        w.writeheader()
        w.writerows(rows)


def test_apply_corrections_round_trip(tmp_path) -> None:
    c = _corpus()
    path = tmp_path / "r.csv"
    to_review_table(c, path)
    _write_edits(path, {"πατρός": {"correct_lemma": "πατήρ", "reviewer_note": "gen sg"}})

    fixed = from_review_table(path, c, reviewer="me")
    tok = {t.position: t for t in fixed.documents[0].tokens}[2]
    assert tok.annotations["lemma"] == "πατήρ"          # corrected
    assert tok.annotations["lemma__pred"] == "πατρός"   # machine value preserved
    assert tok.annotations["reviewed_by"] == "me"
    assert tok.annotations["review_status"] == "corrected"
    assert tok.annotations["review_note"] == "gen sg"
    note = fixed.provenance.notes[-1]
    assert note.startswith("review:") and "1 tokens" in note
    # the untouched token keeps its original lemma and gains no review stamp
    kept = {t.position: t for t in fixed.documents[0].tokens}[0]
    assert kept.annotations["lemma"] == "νόμος" and "review_status" not in kept.annotations


def test_apply_all_blank_is_a_noop(tmp_path) -> None:
    c = _corpus()
    path = tmp_path / "blank.csv"
    to_review_table(c, path)  # no edits
    fixed = from_review_table(path, c, reviewer="me")
    for orig, new in zip(c.documents[0].tokens, fixed.documents[0].tokens):
        assert new.annotations == orig.annotations       # nothing changed
    assert fixed.provenance.notes == c.provenance.notes  # no review note appended


def test_annotate_corpus_fills_word_annotations() -> None:
    # a corpus with bare word tokens (no annotations), baseline pipeline
    toks = [Token(text=t, kind=TokenKind.WORD, line_no=0, position=i)
            for i, t in enumerate(["νόμου", "πατρός"])]
    toks.append(Token(text=".", kind=TokenKind.PUNCT, line_no=0, position=2))
    c = Corpus([Document(id="d", script_id="greek", tokens=toks, lines=[[0, 1, 2]])],
               script_id="greek")
    out = greek.annotate_corpus(c)
    by_pos = {t.position: t for t in out.documents[0].tokens}
    assert by_pos[0].annotations["lemma"] == "νόμος" and by_pos[0].annotations["lemma_source"] == "rule"
    assert by_pos[2].annotations == {}  # punctuation is left untouched


def test_cli_review_export_and_apply(tmp_path) -> None:
    typer_testing = pytest.importorskip("typer.testing")
    from aegean.cli import _build_app

    runner = typer_testing.CliRunner()
    corpus_path = tmp_path / "c.json"
    _corpus().to_json(corpus_path)
    table = tmp_path / "t.csv"

    r1 = runner.invoke(_build_app(), ["review", "export", str(corpus_path), "-o", str(table)])
    assert r1.exit_code == 0, r1.output
    assert table.exists()
    _write_edits(table, {"πατρός": {"correct_lemma": "πατήρ"}})

    out = tmp_path / "fixed.json"
    r2 = runner.invoke(
        _build_app(),
        ["review", "apply", str(corpus_path), str(table), "-o", str(out), "--reviewer", "me"],
    )
    assert r2.exit_code == 0, r2.output
    reloaded = Corpus.from_json(out)
    tok = {t.position: t for t in reloaded.documents[0].tokens}[2]
    assert tok.annotations["lemma"] == "πατήρ" and tok.annotations["lemma__pred"] == "πατρός"
