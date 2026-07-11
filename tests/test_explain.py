"""`explain_pipeline`: the plain-language rendering of pipeline evidence classes.

Pinned by output contract, not "it runs":

- offline cascade: a seed lemma explains as SEED, a rule recovery as RULE, a baseline
  miss as UNRESOLVED + review, punctuation as PUNCT;
- the explanations mirror `pipeline`'s records field-for-field (the never-diverge
  invariant);
- under an active joint model (stubbed, no ONNX — the tests/test_joint.py pattern):
  a real prediction explains as NEURAL with the joint-pipeline note, an identity
  fall-through as IDENTITY + review, morphology filled from FEATS;
- adversarial inputs (empty, whitespace, punctuation-only, a pathological long token)
  yield clean results, never a traceback;
- `render_explanations` aligns columns and flags review rows;
- the CLI `aegean greek explain` renders the table and emits the same rows as --json.
"""

from __future__ import annotations

import json

import pytest

from aegean.greek.explain import (
    TokenExplanation,
    explain_pipeline,
    render_explanations,
)
from aegean.greek.lemmatize import LemmaSource


# ── offline cascade: each evidence class explained correctly ─────────────────
def test_offline_evidence_classes_explained():
    exps = explain_pipeline("ἦν νόμου πατρός.")
    assert [e.token for e in exps] == ["ἦν", "νόμου", "πατρός", "."]
    by_token = {e.token: e for e in exps}

    seed = by_token["ἦν"]  # closed-class / seed-table hit
    assert (seed.lemma, seed.lemma_source, seed.needs_review) == ("εἰμί", LemmaSource.SEED, False)
    assert "seed table" in seed.note

    rule = by_token["νόμου"]  # ending-rule recovery
    assert (rule.lemma, rule.lemma_source, rule.needs_review) == ("νόμος", LemmaSource.RULE, False)
    assert "rule" in rule.note

    miss = by_token["πατρός"]  # baseline miss: honest, flagged
    assert (miss.lemma, miss.lemma_source, miss.needs_review) == (
        "πατρός", LemmaSource.UNRESOLVED, True,
    )
    assert "review" in miss.note

    dot = by_token["."]
    assert (dot.lemma, dot.lemma_source, dot.needs_review) == (".", LemmaSource.PUNCT, False)

    assert all(e.upos for e in exps)  # the analysis fields come through
    assert seed.morphology is None  # the offline cascade fills no FEATS


def test_explanations_mirror_pipeline_records_exactly():
    """The never-diverge invariant: every field is derived from the very record
    `pipeline` produced for that token, nothing re-run or re-decided."""
    from aegean.greek.pipeline import pipeline

    text = "ἐν ἀρχῇ ἦν ὁ λόγος. καὶ νόμου πατρός;"
    recs = pipeline(text)
    exps = explain_pipeline(text)
    assert len(exps) == len(recs) > 0
    for r, e in zip(recs, exps):
        assert (e.token, e.upos, e.lemma) == (r.text, r.upos, r.lemma)
        assert e.lemma_source is r.lemma_source
        assert e.needs_review is (not r.lemma_known)
        assert e.morphology == r.feats
        assert e.note


# ── the joint neural pipeline, stubbed (the tests/test_joint.py pattern) ─────
def _stub_joint_model(np):  # mirrors tests/test_joint.py::_stub_model
    """A _JointModel whose _run returns deterministic logits, no ONNX involved.

    Sentence: ['ὁ', 'λόγος', 'ἐστί'] → DET NOUN VERB; ὁ resolves via the form
    lookup, ἐστί via (form|UPOS), λόγος via an edit script whose output equals
    the surface (an honest identity fall-through)."""
    from aegean.greek import joint

    m = object.__new__(joint._JointModel)  # skip __init__ (no artifact on disk)
    m._np = np
    m.inv = {"upos": dict(enumerate(["DET", "NOUN", "VERB", "X"])),
             "deprel": dict(enumerate(["det", "nsubj", "root", "dep"]))}
    for i in range(9):
        m.inv[f"x{i}"] = {0: "-", 1: "l", 2: "n", 3: "v"}
    m.trees = [["sub", "λόγος"]]  # script 0 rewrites anything to λόγος
    m.lookup_form = {"ὁ": "ὁ"}
    m.lookup_form_upos = {"ἐστί|VERB": "εἰμί"}
    m.lookup_lower = {}

    by_form = {"ὁ": (0, 1), "λόγος": (1, 2), "ἐστί": (2, 3)}

    def fake_run(words):
        n = len(words)
        word_pos = list(range(1, n + 1))
        seq = n + 2

        def tag(labels, n_labels):
            a = np.full((1, seq, n_labels), -9.0)
            for w, lab in enumerate(labels):
                a[0, word_pos[w], lab] = 9.0
            return a

        out = {"upos": tag([by_form.get(w, (3, 0))[0] for w in words], 4),
               "x0": tag([by_form.get(w, (3, 0))[1] for w in words], 4)}
        for i in range(1, 9):
            out[f"x{i}"] = tag([0] * n, 4)
        arc = np.full((1, n, n + 1), -9.0)
        rel = np.full((1, 4, n, n + 1), -9.0)
        for w in range(n):
            h = w + 2 if w < n - 1 else 0
            arc[0, w, h] = 9.0
            rel[0, min(w, 2) if w < n - 1 else 2, w, h] = 9.0
        out["arc"] = arc
        out["rel"] = rel
        out["lemma"] = np.full((1, n, 1), 0.0)  # script 0 for everyone
        out["_word_pos"] = word_pos
        out["_kept"] = list(range(n))
        return out

    m._run = fake_run
    return m


def test_neural_records_reflected_with_joint_note(monkeypatch):
    np = pytest.importorskip("numpy")
    from aegean.greek import joint

    monkeypatch.setattr(joint, "_ACTIVE", _stub_joint_model(np))
    exps = explain_pipeline("ὁ λόγος ἐστί")
    assert [e.lemma for e in exps] == ["ὁ", "λόγος", "εἰμί"]
    assert [e.upos for e in exps] == ["DET", "NOUN", "VERB"]
    assert [e.lemma_source for e in exps] == [
        LemmaSource.NEURAL, LemmaSource.IDENTITY, LemmaSource.NEURAL,
    ]
    assert [e.needs_review for e in exps] == [False, True, False]
    assert "joint neural pipeline" in exps[0].note  # says the neural stack produced it
    assert all(e.morphology == "_" for e in exps)  # FEATS reflected from the records


def test_neural_identity_fallthrough_explains_as_identity(monkeypatch):
    """A token the model cannot lemmatize (identity fall-through) must explain as
    IDENTITY + needs_review, even though its lemma equals the surface form."""
    np = pytest.importorskip("numpy")
    from aegean.greek import joint

    model = _stub_joint_model(np)
    model.lookup_form = {}  # clear every lemma source so all three fall through
    model.lookup_form_upos = {}
    model.lookup_lower = {}
    model.trees = []
    monkeypatch.setattr(joint, "_ACTIVE", model)
    exps = explain_pipeline("ὁ λόγος ἐστί")
    assert [e.token for e in exps] == ["ὁ", "λόγος", "ἐστί"]
    for e in exps:
        assert e.lemma == e.token  # the surface form is shown...
        assert e.lemma_source is LemmaSource.IDENTITY  # ...and honestly classed
        assert e.needs_review is True
        assert "review" in e.note and "neural" in e.note


# ── adversarial inputs: clean results, never a traceback ─────────────────────
def test_explain_empty_and_whitespace_inputs():
    assert explain_pipeline("") == []
    assert explain_pipeline("   \n\t  ") == []
    assert render_explanations([]) == "(no tokens)"


def test_explain_punctuation_only():
    exps = explain_pipeline(", . ;")
    assert len(exps) == 3
    for e in exps:
        assert e.lemma_source is LemmaSource.PUNCT
        assert e.needs_review is False
        assert e.lemma == e.token
    assert "(no tokens)" not in render_explanations(exps)


def test_explain_pathological_long_token():
    word = "αβγδε" * 2000  # one 10,000-char nonsense token
    exps = explain_pipeline(word)
    assert len(exps) == 1
    e = exps[0]
    assert e.token == word
    assert e.lemma_source is LemmaSource.UNRESOLVED
    assert e.needs_review is True
    assert "review" in render_explanations(exps)


# ── render: aligned plain-text table ─────────────────────────────────────────
def test_render_aligns_columns_and_flags_review():
    exps = explain_pipeline("ἦν νόμου πατρός.")
    out = render_explanations(exps)
    lines = out.splitlines()
    assert len(lines) == 1 + len(exps)
    header = lines[0]
    for col in ("token", "upos", "lemma", "source", "review", "morphology", "note"):
        assert col in header
    upos_col = header.index("upos")
    for line, e in zip(lines[1:], exps):
        assert line[:upos_col].rstrip() == e.token  # column 1 padded to one shared width
        assert line[upos_col:].startswith(e.upos)  # column 2 starts where the header does
    review_line = next(line for line in lines[1:] if "πατρός" in line)
    assert "unresolved" in review_line and "review" in review_line
    grounded_line = next(line for line in lines[1:] if "νόμου" in line)
    assert " review " not in grounded_line  # grounded rows leave the review cell blank


def test_render_is_plain_text():
    exps = [TokenExplanation(
        token="[x]", upos="X", lemma="[x]", lemma_source=LemmaSource.PUNCT,
        needs_review=False, morphology=None, note="punctuation or numeral",
    )]
    out = render_explanations(exps)
    assert "[x]" in out  # brackets render literally: no markup layer involved


# ── CLI: aegean greek explain ─────────────────────────────────────────────────
@pytest.fixture(scope="module")
def app():
    pytest.importorskip("typer")
    from aegean.cli import _build_app

    return _build_app()


def _invoke(app, *args: str):
    from typer.testing import CliRunner

    return CliRunner().invoke(app, list(args))


def test_cli_explain_renders_the_table(app):
    res = _invoke(app, "greek", "explain", "ἦν νόμου πατρός.")
    assert res.exit_code == 0, res.output
    out = res.output
    assert "εἰμί" in out and "νόμος" in out
    assert "seed" in out and "rule" in out and "unresolved" in out
    assert "review" in out
    assert "Traceback" not in out


def test_cli_explain_json_rows_match_the_dataclass(app):
    res = _invoke(app, "greek", "explain", "ἦν.", "--json")
    assert res.exit_code == 0, res.output
    data = json.loads(res.output[res.output.index("["):])
    assert [row["token"] for row in data] == ["ἦν", "."]
    assert set(data[0]) == {
        "token", "upos", "lemma", "lemma_source", "needs_review", "morphology", "note",
    }
    assert data[0]["lemma"] == "εἰμί"
    assert data[0]["lemma_source"] == "seed"  # the enum flattens to its value
    assert data[0]["needs_review"] is False
    assert data[1]["lemma_source"] == "punct"


def test_cli_explain_empty_input_is_clean(app):
    res = _invoke(app, "greek", "explain", "")
    assert res.exit_code == 0, res.output
    assert "(no tokens)" in res.output
    assert "Traceback" not in res.output


def test_cli_explain_writes_result_file(app, tmp_path):
    out_file = tmp_path / "explain.json"
    res = _invoke(app, "greek", "explain", "ἦν.", "-o", str(out_file))
    assert res.exit_code == 0, res.output
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data[0]["lemma_source"] == "seed"
