"""Corpus health report (`aegean.core.diagnose` / `Corpus.diagnose` / `aegean doctor corpus`).

Three dimensions, per the house rule:

- correctness: the real, pinned numbers on the bundled Linear A corpus (reading-status
  counts, accounting reconciliation, sign outliers) and the not-applicable degradation on
  the alphabetic-Greek corpora; the caveat wording in `to_markdown`;
- adversarial: an empty corpus, a zero-token document, and a corpus carrying hostile
  annotation values all produce a clean report, never a traceback;
- journey: diagnose -> to_markdown -> written to disk -> re-read -> content-asserted.

Plus the CLI surface (`aegean doctor corpus`), including the established did-you-mean error.
"""

from __future__ import annotations

import json

import pytest

import aegean
from aegean.core.corpus import Corpus
from aegean.core.diagnose import ACCOUNTING_CAVEAT, DiagnoseReport
from aegean.core.model import Document, Token, TokenKind


# ── correctness: the bundled Linear A numbers ─────────────────────────────────
def test_lineara_reading_status_and_accounting_are_the_known_numbers():
    r = aegean.load("lineara").diagnose()
    assert isinstance(r, DiagnoseReport)
    assert r.script_id == "lineara" and r.n_documents == 1721

    s = r.reading_status
    assert s.lost == 552          # standalone erased-sign runs -> text not preserved
    assert s.unclear == 120       # damaged-at-break words + bracketed uncertain readings
    assert s.restored == 0
    assert s.documents_with_apparatus == 366
    assert s.certain + s.unclear + s.restored + s.lost == s.total_tokens

    a = r.accounting
    assert a.applicable is True
    assert a.documents_with_total == 37            # tablets carrying a stated total
    assert a.intact_and_balancing == 7             # checkable_accounts: the clean drill set
    assert a.balanced == 14 and a.discrepant == 23  # split within/without tolerance
    assert a.balanced + a.discrepant == a.documents_with_total
    # the discrepant ids are real document ids and are surfaced as leads
    assert len(a.discrepant_ids) == 23
    assert all(aegean.load("lineara").get(i) is not None for i in a.discrepant_ids[:5])


def test_lineara_numeral_and_review_sections():
    r = aegean.load("lineara").diagnose()
    # the loader's numeral classification is internally consistent (nothing looks
    # numeric yet fails to parse)
    assert r.numerals.applicable is True and r.numerals.anomaly_count == 0
    # the bundled corpus carries no sourced-lemmatization evidence classes
    assert r.review.applicable is False


def test_lineara_sign_outliers_only_in_full_mode():
    quick = aegean.load("lineara").diagnose()
    assert quick.signs.applicable is True and quick.signs.computed is False

    full = aegean.load("lineara").diagnose(level="full")
    sg = full.signs
    assert sg.applicable is True and sg.computed is True
    assert sg.distinct_signs == 162
    assert sg.hapax_count == 56
    assert sg.out_of_inventory_distinct == 66
    assert sg.out_of_inventory_occurrences == 157
    # examples are observable (doc, token, sign) triples, capped
    assert sg.out_of_inventory_examples and len(sg.out_of_inventory_examples) <= 10


# ── correctness: alphabetic-Greek corpora degrade to not-applicable ───────────
@pytest.mark.parametrize("corpus_id", ["nt", "greek"])
def test_greek_corpora_have_no_accounting_and_carry_provenance(corpus_id):
    r = aegean.load(corpus_id).diagnose(level="full")
    assert r.script_id == "greek"
    # accounting / numeral / sign checks are not-applicable, never an error
    assert r.accounting.applicable is False
    assert r.numerals.applicable is False
    assert r.signs.applicable is False
    assert "not an Aegean" in r.signs.note
    # provenance is present and the corpus can be cited
    p = r.provenance
    assert p.has_provenance is True and p.has_license is True
    assert p.can_cite is True and p.citation


# ── correctness: the caveat wording travels in the markdown ───────────────────
def test_markdown_carries_the_metrology_caveat():
    md = aegean.load("lineara").diagnose().to_markdown()
    assert "a lead, not a verdict on the scribe" in md
    assert ACCOUNTING_CAVEAT in md
    assert md.startswith("# Corpus health report: lineara")
    # the caveat is only asserted where accounting applies; a Greek corpus omits it
    greek_md = aegean.load("greek").diagnose().to_markdown()
    assert "a lead, not a verdict" not in greek_md


def test_to_dataframe_is_a_flat_section_table():
    pd = pytest.importorskip("pandas")
    df = aegean.load("lineara").diagnose(level="full").to_dataframe()
    assert list(df.columns) == ["section", "check", "value"]
    assert (df["section"] == "reading status").any()
    # the pinned lost count appears as a cell value
    lost_rows = df[(df["section"] == "reading status") & (df["check"] == "lost")]
    assert lost_rows["value"].iloc[0] == "552"
    assert isinstance(df, pd.DataFrame)


def test_level_is_validated():
    with pytest.raises(ValueError, match="level must be 'quick' or 'full'"):
        aegean.load("greek").diagnose(level="deep")


# ── adversarial: empty / zero-token / hostile-annotation corpora ──────────────
def test_empty_corpus_reports_cleanly():
    for script in ("lineara", "greek"):
        r = Corpus([], script_id=script).diagnose(level="full")
        assert r.n_documents == 0 and r.n_tokens == 0
        assert r.reading_status.total_tokens == 0
        assert r.review.density == 0.0  # no division-by-zero
        # markdown and text still render
        assert r.to_markdown().startswith("# Corpus health report")
        assert r.to_text()


def test_zero_token_document_does_not_crash():
    c = Corpus.from_records([{"id": "E1", "words": []}], script_id="lineara")
    r = c.diagnose(level="full")
    assert r.n_documents == 1 and r.n_tokens == 0
    assert r.accounting.documents_with_total == 0
    assert r.signs.computed is True  # ran the scan over an empty token stream


def test_hostile_annotation_values_produce_a_clean_report():
    # a WORD token with a nonsense evidence class + a non-bool lemma_known, and a
    # numeral-kind token whose text cannot parse (an anomaly the report must catch)
    hostile = Token(
        text="foo", kind=TokenKind.WORD, signs=("fo", "o"), line_no=0, position=0,
        annotations={"lemma_source": "!!bogus!!", "lemma_known": "maybe"},
    )
    bad_numeral = Token(text="12X", kind=TokenKind.NUMERAL, line_no=0, position=1)
    doc = Document(id="H1", script_id="lineara", tokens=[hostile, bad_numeral], lines=[[0, 1]])
    r = Corpus([doc], script_id="lineara").diagnose(level="full")
    # no traceback; the odd evidence class registers as annotated but not low-confidence
    assert r.review.applicable is True and r.review.needs_review == 0
    # the unparseable numeral is surfaced as an anomaly
    assert r.numerals.anomaly_count == 1
    assert r.numerals.examples[0] == ("H1", "12X")
    # no sign inventory on a hand-built corpus -> a note, not a crash
    assert r.signs.computed is True and "no sign inventory" in r.signs.note
    assert r.to_markdown()  # renders


def test_hostile_lemma_known_false_is_flagged_for_review():
    # the io/review fallback: lemma_known == "false" (case-insensitive) needs review
    tok = Token(
        text="w", kind=TokenKind.WORD, line_no=0, position=0,
        annotations={"lemma_known": "FALSE"},
    )
    doc = Document(id="D1", script_id="greek", tokens=[tok], lines=[[0]])
    r = Corpus([doc], script_id="greek").diagnose()
    assert r.review.applicable is True
    assert r.review.needs_review == 1 and r.review.word_tokens == 1
    assert r.review.density == 1.0


# ── journey: diagnose -> markdown -> file -> re-read -> assert ────────────────
def test_journey_markdown_round_trips_through_a_file(tmp_path):
    r = aegean.load("lineara").diagnose(level="full")
    out = tmp_path / "reports" / "health.md"
    out.parent.mkdir(parents=True)
    out.write_text(r.to_markdown(), encoding="utf-8")

    reread = out.read_text(encoding="utf-8")
    assert reread == r.to_markdown()
    assert "a lead, not a verdict on the scribe" in reread   # caveat survived
    assert "| lost | 552 |" in reread                         # a pinned number survived
    assert "| documents with a stated total | 37 |" in reread


# ── CLI: aegean doctor corpus ─────────────────────────────────────────────────
@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    typer = pytest.importorskip("typer")  # noqa: F841
    from aegean.cli import _build_app

    return _build_app()


def _run(app, *args):  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    return CliRunner().invoke(app, list(args))


def test_cli_corpus_health_renders_with_the_caveat(app):
    res = _run(app, "doctor", "corpus", "lineara")
    assert res.exit_code == 0, res.output
    assert "Accounting" in res.output
    assert "a lead, not a verdict on the scribe" in res.output


def test_cli_unknown_corpus_uses_the_did_you_mean_path(app):
    res = _run(app, "doctor", "corpus", "linera")
    assert res.exit_code == 1
    assert "did you mean" in res.output and "lineara" in res.output
    assert "Traceback" not in res.output


def test_cli_json_emits_the_structured_report(app):
    res = _run(app, "doctor", "corpus", "lineara", "--json")
    assert res.exit_code == 0, res.output
    d = json.loads(res.stdout if hasattr(res, "stdout") else res.output)
    assert d["accounting"]["applicable"] is True
    assert d["accounting"]["documents_with_total"] == 37
    assert d["reading_status"]["lost"] == 552


def test_cli_deep_writes_markdown_file(app, tmp_path):
    out = tmp_path / "out" / "la.md"
    res = _run(app, "doctor", "corpus", "lineara", "--deep", "-o", str(out))
    assert res.exit_code == 0, res.output
    assert f"wrote {out}" in res.output
    body = out.read_text(encoding="utf-8")
    assert "a lead, not a verdict on the scribe" in body
    assert "Sign-frequency outliers" in body  # --deep ran the sign scan


def test_cli_bad_output_extension_is_a_clean_error(app, tmp_path):
    res = _run(app, "doctor", "corpus", "lineara", "-o", str(tmp_path / "x.pdf"))
    assert res.exit_code == 1
    assert "use a .md, .json, or .txt extension" in res.output


def test_cli_bare_doctor_still_runs_the_env_check(app):
    # converting doctor into a group must not break the environment check
    res = _run(app, "doctor", "--json")
    assert res.exit_code == 0
    payload = json.loads(res.stdout if hasattr(res, "stdout") else res.output)
    assert "versions" in payload and "data_store" in payload
