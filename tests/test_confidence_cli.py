"""Calibrated confidence through the surface seam: `_view`, the CLI (`greek pipeline`
/ `greek explain --confidence`), and the TUI adapter.

The library surface (pipeline/explain/joint) is pinned in test_confidence_surface.py;
this file pins the ONE parity seam (`aegean._view`) and the two front ends that render
it, so the confidence column cannot drift between the CLI, the TUI workbench, and the
reader analysis.

CI note: the calibrated path needs the joint model, which is stubbed via
tests/test_joint.py's ``_stub_model`` (numpy only — ``pytest.importorskip('numpy')``),
never onnxruntime; the default-off and formatting checks need nothing heavy.
"""

from __future__ import annotations

import json

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean.cli import _build_app  # noqa: E402

runner = CliRunner()

TEXT = "ὁ λόγος ἐστί"  # stub: ὁ NEURAL / λόγος IDENTITY / ἐστί NEURAL


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


def ok(app, *args: str) -> str:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, list(args))
    assert res.exit_code == 0, res.output
    return res.output


def err(app, *args: str) -> str:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, list(args))
    assert res.exit_code != 0, res.output
    return res.output


def _calibration():  # type: ignore[no-untyped-def]
    from aegean.greek.calibrate import Calibration

    return Calibration(
        temperature={"upos": 1.34, "lemma": 0.66},
        fitted_on="synthetic (unit test)", date="2026-07-11",
    )


def _activate_stub(monkeypatch):  # type: ignore[no-untyped-def]
    """Make a stubbed joint model + a synthetic calibration the active state (auto-reverted
    by monkeypatch), so a `--confidence` run produces real calibrated numbers without ONNX."""
    from aegean.greek import calibrate, joint
    from test_joint import _stub_model

    monkeypatch.setattr(joint, "_ACTIVE", _stub_model())
    monkeypatch.setattr(calibrate, "_ACTIVE", _calibration())


def _wide_console(monkeypatch):  # type: ignore[no-untyped-def]
    """Render the rich table wide enough that a new right-hand column is not clipped by the
    default 80-col capture width (the cli-help-test-width class), with a fresh console."""
    import aegean.cli._common as common

    monkeypatch.setattr(common, "_console", None)
    monkeypatch.setenv("COLUMNS", "220")


# ── _view: the shared row mapping ────────────────────────────────────────────
def test_view_rows_have_no_confidence_keys_by_default() -> None:
    # The offline cascade produces no confidence. A4 source-alignment columns are
    # independent of the optional calibrated-confidence columns.
    from aegean._view import pipeline_rows

    rows = pipeline_rows("ἦν ὁ λόγος.")
    assert rows
    for r in rows:
        assert "upos_confidence" not in r and "lemma_confidence" not in r
    assert set(rows[0]) == {
        "sentence", "index", "text", "upos", "lemma", "lemma_source",
        "lemma_resolved", "lemma_verified", "review_recommended", "lemma_known",
        "head", "relation", "xpos", "feats", "neural_analyzed",
        "analysis_complete", "analysis_warning", "analysis_receipt",
        "boundary_policy", "boundary_policy_id", "boundary_provenance",
        "boundary_confidence", "boundary_start_char", "boundary_end_char",
        "alignment_document_id", "alignment_sentence_id",
        "alignment_source_token_id", "alignment_original_text",
        "alignment_start_char", "alignment_end_char",
        "alignment_whitespace_before", "alignment_normalized_text",
        "alignment_normalization_ops",
    }


def test_view_rows_from_records_add_confidence_columns_when_present() -> None:
    from aegean._view import pipeline_rows_from_records
    from aegean.greek.lemmatize import LemmaSource
    from aegean.greek.pipeline import TokenRecord

    recs = [
        TokenRecord(0, 1, "ὁ", "DET", "ὁ", LemmaSource.NEURAL,
                    upos_confidence=0.98, lemma_confidence=0.90),
        TokenRecord(0, 2, "λόγος", "NOUN", "λόγος", LemmaSource.IDENTITY,
                    upos_confidence=0.80, lemma_confidence=None),
    ]
    rows = pipeline_rows_from_records(recs)
    # the column is all-or-nothing: both keys on every row once any record carries one
    assert all("upos_confidence" in r and "lemma_confidence" in r for r in rows)
    assert rows[0]["upos_confidence"] == 0.98 and rows[0]["lemma_confidence"] == 0.90
    # the per-row value is still None for a head with no calibrated number (IDENTITY lemma)
    assert rows[1]["lemma_confidence"] is None


def test_view_rows_from_records_omit_confidence_when_all_none() -> None:
    # every record None -> no column, byte-identical to the pre-feature mapping
    from aegean._view import pipeline_rows_from_records
    from aegean.greek.lemmatize import LemmaSource
    from aegean.greek.pipeline import TokenRecord

    recs = [TokenRecord(0, 1, "ὁ", "DET", "ὁ", LemmaSource.ATTESTED)]
    rows = pipeline_rows_from_records(recs)
    assert "upos_confidence" not in rows[0] and "lemma_confidence" not in rows[0]


def test_format_confidence_two_decimals_and_dash_for_none() -> None:
    from aegean._view import format_confidence

    assert format_confidence(0.976, 0.912) == "0.98/0.91"
    assert format_confidence(0.976, None) == "0.98/—"  # model-only lemma head
    assert format_confidence(None, 0.5) == "—/0.50"
    assert format_confidence(None, None) == "—"


# ── CLI: greek pipeline --confidence ─────────────────────────────────────────
def test_pipeline_confidence_shows_column_and_json_floats(app, monkeypatch) -> None:
    pytest.importorskip("numpy")
    _activate_stub(monkeypatch)

    # --json carries the raw floats / None
    res = runner.invoke(app, ["greek", "pipeline", TEXT, "--confidence", "--json"])
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert all("upos_confidence" in r and "lemma_confidence" in r for r in rows)
    by_text = {r["text"]: r for r in rows}
    assert isinstance(by_text["ὁ"]["upos_confidence"], float)
    # lemma confidence is model-only: a NEURAL lemma has a float, the IDENTITY one is None
    assert isinstance(by_text["ὁ"]["lemma_confidence"], float)
    assert by_text["λόγος"]["lemma_confidence"] is None
    for r in rows:
        assert 0.0 <= r["upos_confidence"] <= 1.0

    # the human table gains a 'conf' column
    _wide_console(monkeypatch)
    out = ok(app, "greek", "pipeline", TEXT, "--confidence")
    assert "conf" in out


def test_pipeline_without_confidence_is_byte_identical(app) -> None:
    # The regression pin: absent --confidence, the CLI emits exactly the shared-view rows
    # (no confidence keys), even though the machinery now exists.
    from aegean._view import pipeline_rows

    text = "ἦν ὁ λόγος."
    res = runner.invoke(app, ["greek", "pipeline", text, "--json"])
    assert res.exit_code == 0, res.output
    rows = json.loads(res.stdout)
    assert rows == pipeline_rows(text)
    assert all("upos_confidence" not in r for r in rows)


def test_pipeline_confidence_missing_calibration_is_one_clean_line(app, monkeypatch) -> None:
    # The bundled calibration is absent -> use_calibration() raises -> the established
    # one clean line with the next step, never a traceback (monkeypatch the bundled path).
    import aegean.data as data_mod
    from aegean.greek import calibrate

    monkeypatch.setattr(calibrate, "_ACTIVE", None)

    def _missing(*parts: str) -> object:
        raise FileNotFoundError("no calibration.json")

    monkeypatch.setattr(data_mod, "load_bundled_json", _missing)
    msg = err(app, "greek", "pipeline", "ὁ λόγος", "--confidence")
    assert "the shipped calibration file is missing" in msg
    assert "reinstall pyaegean or run use_calibration(path)" in msg
    assert "Traceback" not in msg


def test_pipeline_confidence_controls_appear_in_help(app) -> None:
    res = runner.invoke(app, ["greek", "pipeline", "--help"])
    assert res.exit_code == 0, res.output
    assert "--confidence-domain" in res.output and "LABEL" in res.output
    assert "--confidence-policy" in res.output and "PATH" in res.output


@pytest.mark.parametrize("option", ["--confidence-domain", "--confidence-policy"])
def test_pipeline_confidence_controls_require_confidence(app, option, tmp_path) -> None:
    value = "papyri" if option == "--confidence-domain" else str(tmp_path / "policy.json")
    res = runner.invoke(app, ["greek", "pipeline", TEXT, option, value])
    assert res.exit_code != 0
    assert f"{option} requires --confidence" in res.output


@pytest.mark.parametrize("payload", ["{", '{"schema_version":99,"thresholds":{"upos":0.5}}'])
def test_pipeline_confidence_policy_rejects_malformed_json(app, tmp_path, payload) -> None:
    path = tmp_path / "policy.json"
    path.write_text(payload, encoding="utf-8")
    res = runner.invoke(
        app,
        ["greek", "pipeline", TEXT, "--confidence", "--confidence-policy", str(path)],
    )
    assert res.exit_code != 0
    assert "could not load confidence policy" in res.output
    assert "Traceback" not in res.output


def test_pipeline_confidence_policy_rejects_tampering_and_missing_file(app, tmp_path) -> None:
    from aegean.greek import AbstentionPolicy

    policy = AbstentionPolicy({"upos": 0.75}, name="cli-test")
    tampered = policy.to_dict()
    tampered["thresholds"]["upos"] = 0.8
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    missing_path = tmp_path / "missing.json"
    for path in (tampered_path, missing_path):
        res = runner.invoke(
            app,
            ["greek", "pipeline", TEXT, "--confidence", "--confidence-policy", str(path)],
        )
        assert res.exit_code != 0
        assert "could not load confidence policy" in res.output


def test_pipeline_confidence_forwarding_preserves_default_shape(app, monkeypatch) -> None:
    from aegean import greek
    from aegean.cli import _greek

    seen: dict[str, object] = {}

    def fake_pipeline(text: str, **kwargs: object) -> list[object]:
        seen["text"] = text
        seen.update(kwargs)
        return []

    monkeypatch.setattr(_greek, "_activate", lambda **_kwargs: None)
    monkeypatch.setattr(greek, "pipeline", fake_pipeline)
    res = runner.invoke(app, ["greek", "pipeline", TEXT, "--json"])
    assert res.exit_code == 0, res.output
    assert seen == {
        "text": TEXT,
        "parse": False,
        "with_confidence": False,
        "long_input": "strict",
        "sentence_policy": "default",
    }


def test_pipeline_confidence_forwards_only_explicit_controls(app, monkeypatch, tmp_path) -> None:
    from aegean import greek
    from aegean.cli import _greek
    from aegean.greek import AbstentionPolicy

    policy = AbstentionPolicy({"upos": 0.75}, name="cli-test")
    path = tmp_path / "policy.json"
    policy.save(path)
    seen: dict[str, object] = {}

    def fake_pipeline(_text: str, **kwargs: object) -> list[object]:
        seen.update(kwargs)
        return []

    monkeypatch.setattr(_greek, "_activate", lambda **_kwargs: None)
    monkeypatch.setattr(_greek, "_ensure_calibration", lambda: None)
    monkeypatch.setattr(greek, "pipeline", fake_pipeline)
    res = runner.invoke(
        app,
        [
            "greek",
            "pipeline",
            TEXT,
            "--confidence",
            "--confidence-domain",
            "papyri",
            "--confidence-policy",
            str(path),
            "--json",
        ],
    )
    assert res.exit_code == 0, res.output
    assert seen["with_confidence"] is True
    assert seen["confidence_domain"] == "papyri"
    assert seen["confidence_policy"] == policy


def test_pipeline_json_surfaces_structured_policy_and_unavailable_detail(app, monkeypatch) -> None:
    from aegean import greek
    from aegean.cli import _greek
    from aegean.greek.confidence import ConfidenceResult, SentenceConfidence, TokenConfidence
    from aegean.greek.lemmatize import LemmaSource
    from aegean.greek.pipeline import TokenRecord

    unavailable = ConfidenceResult(task="upos", value=None, reason="missing_calibration")
    token_confidence = TokenConfidence(index=0, upos=unavailable)
    sentence_confidence = SentenceConfidence(
        ConfidenceResult(task="sentence", value=None, reason="missing_calibration")
    )
    record = TokenRecord(
        0,
        1,
        "λόγος",
        "NOUN",
        "λόγος",
        LemmaSource.NEURAL,
        token_confidence=token_confidence,
        sentence_confidence=sentence_confidence,
    )
    monkeypatch.setattr(_greek, "_activate", lambda **_kwargs: None)
    monkeypatch.setattr(_greek, "_ensure_calibration", lambda: None)
    monkeypatch.setattr(greek, "pipeline", lambda _text, **_kwargs: [record])
    res = runner.invoke(app, ["greek", "pipeline", TEXT, "--confidence", "--json"])
    assert res.exit_code == 0, res.output
    row = json.loads(res.stdout)[0]
    assert row["token_confidence"]["upos"]["reason"] == "missing_calibration"
    assert row["sentence_confidence"]["result"]["reason"] == "missing_calibration"


# ── CLI: greek explain --confidence ──────────────────────────────────────────
def test_explain_confidence_appends_the_calibrated_phrase(app, monkeypatch) -> None:
    pytest.importorskip("numpy")
    _activate_stub(monkeypatch)

    out = ok(app, "greek", "explain", TEXT, "--confidence")
    assert "calibrated confidence" in out
    assert "UPOS " in out

    res = runner.invoke(app, ["greek", "explain", TEXT, "--confidence", "--json"])
    assert res.exit_code == 0, res.output
    notes = " ".join(r["note"] for r in json.loads(res.stdout))
    assert "calibrated confidence" in notes


def test_explain_without_confidence_has_no_calibrated_phrase(app, monkeypatch) -> None:
    pytest.importorskip("numpy")
    _activate_stub(monkeypatch)  # active, but the flag is off
    out = ok(app, "greek", "explain", TEXT)
    assert "calibrated confidence" not in out


# ── TUI adapter (textual-free) ───────────────────────────────────────────────
def test_confidence_available_requires_neural_and_calibration(monkeypatch) -> None:
    pytest.importorskip("numpy")
    from aegean.greek import calibrate, joint
    from aegean.tui import data as adapter
    from test_joint import _stub_model

    monkeypatch.setattr(joint, "_ACTIVE", None)
    monkeypatch.setattr(calibrate, "_ACTIVE", None)
    assert adapter.confidence_available() is False

    monkeypatch.setattr(joint, "_ACTIVE", _stub_model())
    assert adapter.confidence_available() is False  # calibration still missing

    monkeypatch.setattr(calibrate, "_ACTIVE", _calibration())
    assert adapter.confidence_available() is True


def test_tui_greek_pipeline_rows_carry_confidence_when_requested(monkeypatch) -> None:
    pytest.importorskip("numpy")
    from aegean.tui import data as adapter

    _activate_stub(monkeypatch)
    result = adapter.greek_pipeline(TEXT, with_confidence=True)
    assert result.ok
    by_text = {r["text"]: r for r in result.rows}
    assert isinstance(by_text["ὁ"]["upos_confidence"], float)
    assert by_text["λόγος"]["lemma_confidence"] is None  # model-only

    # and off by default -> no keys (byte-identical to before)
    plain = adapter.greek_pipeline(TEXT)
    assert all("upos_confidence" not in r for r in plain.rows)


def test_tui_offline_analysis_gains_conf_column_when_available(monkeypatch) -> None:
    pytest.importorskip("numpy")
    from aegean.tui import data as adapter

    # no confidence: the offline analysis keeps its 5-column shape
    plain = adapter._greek_offline(TEXT)
    assert plain.ok and plain.columns == ("#", "token", "POS", "lemma", "check")

    # neural + calibration active: the reader's offline analysis grows a 'conf' column
    _activate_stub(monkeypatch)
    conf = adapter._greek_offline(TEXT)
    assert conf.ok
    assert conf.columns == ("#", "token", "POS", "lemma", "check", "conf")
    assert len(conf.rows[0]) == 6
    # the conf cell for the IDENTITY token has a UPOS number but a '—' lemma head
    by_text = {row[1]: row for row in conf.rows}
    assert by_text["λόγος"][-1].endswith("/—")
