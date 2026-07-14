"""Focused CLI journey checks for lossless CoNLL-U inspection/export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean.cli import _build_app  # noqa: E402


runner = CliRunner()
FIXTURE = Path(__file__).parent / "fixtures" / "ud" / "sample-ud-test.conllu"


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


def test_conllu_inspect_reports_structure_and_projection(app):  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["greek", "conllu", "inspect", str(FIXTURE), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)

    assert payload["n_sentences"] == 2
    assert payload["n_comments"] == 5
    assert payload["n_data_rows"] == 10
    assert payload["n_syntactic_tokens"] == 8
    assert payload["n_multiword_ranges"] == 1
    assert payload["n_empty_nodes"] == 1
    assert payload["n_opaque_rows"] == 0
    assert payload["projection"] == {
        "policy": "syntactic_words_v1",
        "kind": "syntactic_words",
        "model_tokens": 8,
        "structural_rows_omitted": 2,
        "omitted_multiword_ranges": 1,
        "omitted_empty_nodes": 1,
        "enhanced_dependencies_present": False,
    }
    first = payload["sentences"][0]
    assert first["projection"]["ordinal_to_id"] == [[1, 1], [2, 2], [3, 3], [4, 4], [5, 5]]
    assert first["projection"]["omitted_multiword_ranges"] == ["4-5"]
    assert first["projection"]["omitted_empty_nodes"] == ["5.1"]


def test_conllu_inspect_can_save_json_summary(app, tmp_path):  # type: ignore[no-untyped-def]
    output = tmp_path / "summary.json"
    result = runner.invoke(
        app, ["greek", "conllu", "inspect", str(FIXTURE), "-o", str(output)]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text(encoding="utf-8"))["n_sentences"] == 2
    assert f"wrote {output}" in result.output


def test_conllu_export_writes_source_bytes_atomically(app, tmp_path):  # type: ignore[no-untyped-def]
    output = tmp_path / "roundtrip.conllu"
    result = runner.invoke(
        app, ["greek", "conllu", "export", str(FIXTURE), "-o", str(output)]
    )
    assert result.exit_code == 0, result.output
    assert output.read_bytes() == FIXTURE.read_bytes()
    assert f"wrote {output}" in result.output


def test_conllu_export_stdout_contains_only_source_text(app):  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["greek", "conllu", "export", str(FIXTURE)])
    assert result.exit_code == 0, result.output
    # Click's text capture normalizes CRLF; the content and row structure remain unchanged.
    assert result.stdout == FIXTURE.read_text(encoding="utf-8")
    assert getattr(result, "stderr", "") == ""


def test_conllu_crlf_export_preserves_newlines(app, tmp_path):  # type: ignore[no-untyped-def]
    source = tmp_path / "crlf.conllu"
    raw = (
        "# sent_id = crlf\r\n"
        "# text = λόγος\r\n"
        "1\tλόγος\tλόγος\tNOUN\t_\t_\t0\troot\t_\tSpaceAfter=No\r\n"
        "\r\n"
    ).encode("utf-8")
    source.write_bytes(raw)
    output = tmp_path / "crlf-copy.conllu"
    result = runner.invoke(
        app, ["greek", "conllu", "export", str(source), "--strict", "-o", str(output)]
    )
    assert result.exit_code == 0, result.output
    assert output.read_bytes() == raw


def test_conllu_lenient_inspect_counts_opaque_rows(app, tmp_path):  # type: ignore[no-untyped-def]
    source = tmp_path / "malformed.conllu"
    source.write_text("# sent_id = bad\n1\tλόγος\tλόγος\tNOUN\t_\t_\t0\troot\t_\n\n", encoding="utf-8")
    result = runner.invoke(app, ["greek", "conllu", "inspect", str(source), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["n_sentences"] == 1
    assert payload["n_opaque_rows"] == 1
    assert payload["n_syntactic_tokens"] == 0


def test_conllu_strict_rejects_malformed_rows(app, tmp_path):  # type: ignore[no-untyped-def]
    source = tmp_path / "malformed.conllu"
    source.write_text("# sent_id = bad\n1\tλόγος\tλόγος\tNOUN\t_\t_\t0\troot\t_\n\n", encoding="utf-8")
    result = runner.invoke(app, ["greek", "conllu", "inspect", str(source), "--strict"])
    assert result.exit_code == 1
    assert "expected 10 tab-separated CoNLL-U columns" in result.output
    assert "Traceback" not in result.output
