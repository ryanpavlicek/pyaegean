"""A15 CLI interoperability bundle journeys and hostile-input contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean.cli import _build_app  # noqa: E402
from aegean.io._interop_bundle import read_interop_bundle  # noqa: E402
from aegean.io.interop import from_conllu  # noqa: E402


runner = CliRunner()
VALID_CONLLU = (
    "# sent_id = s1\n"
    "# text = AB\n"
    "1-2\tAB\t_\t_\t_\t_\t_\t_\t_\t_\n"
    "1\tA\ta\tNOUN\t_\t_\t0\troot\t0:root\t_\n"
    "2\tB\tb\tNOUN\t_\t_\t1\tdep\t1:dep\t_\n"
    "2.1\tC\tc\tX\t_\t_\t_\t_\t1:dep\t_\n"
    "\n"
)


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "source.conllu"
    source.write_text(VALID_CONLLU, encoding="utf-8", newline="")
    return source


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


def test_interop_help_exposes_the_three_step_workflow(app) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["greek", "interop", "--help"])
    assert result.exit_code == 0, result.output
    assert all(command in result.output for command in ("export", "import", "report"))


def test_interop_conllu_export_report_import_journey(app, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    source = _source(tmp_path)
    bundle_path = tmp_path / "nested" / "document.interop.json"
    exported = runner.invoke(
        app,
        [
            "greek", "interop", "export", str(source),
            "--target", "conllu", "-o", str(bundle_path), "--json",
        ],
    )
    assert exported.exit_code == 0, exported.output
    export_report = json.loads(exported.stdout)
    assert export_report["schema"] == "aegean.interop-bundle/v1"
    assert export_report["target"] == "conllu"
    assert export_report["lossless"] is True
    bundle = read_interop_bundle(bundle_path)
    assert bundle.document.ud_document.sentences[0].multiword_tokens[0].id == "1-2"

    reported = runner.invoke(
        app, ["greek", "interop", "report", str(bundle_path), "--json"]
    )
    assert reported.exit_code == 0, reported.output
    report_payload = json.loads(reported.stdout)
    assert {key: value for key, value in report_payload.items() if key != "source"} == {
        key: value for key, value in export_report.items() if key != "source"
    }
    assert report_payload["source"] == str(bundle_path)

    output = tmp_path / "recovered.conllu"
    imported = runner.invoke(
        app,
        ["greek", "interop", "import", str(bundle_path), "-o", str(output), "--json"],
    )
    assert imported.exit_code == 0, imported.output
    import_report = json.loads(imported.stdout)
    assert import_report["output"] == str(output)
    assert from_conllu(output).value.ud_document.dumps() == from_conllu(
        source
    ).value.ud_document.dumps()


def test_interop_rejects_unknown_target_before_writing(app, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "does-not-exist.conllu"
    output = tmp_path / "never.json"
    result = runner.invoke(
        app,
        [
            "greek", "interop", "export", str(source),
            "--target", "unknown", "-o", str(output),
        ],
    )
    assert result.exit_code == 1
    assert "target must be one of" in result.output
    assert "does-not-exist" not in result.output
    assert "Traceback" not in result.output
    assert not output.exists()


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        '{"schema":"x","schema":"y"}',
        '{"value":Infinity}',
    ],
)
def test_interop_hostile_bundle_is_clean_and_does_not_replace_output(
    app, tmp_path: Path, payload: str
) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "bad.json"
    source.write_text(payload, encoding="utf-8")
    output = tmp_path / "existing.conllu"
    output.write_text("keep", encoding="utf-8")
    result = runner.invoke(
        app, ["greek", "interop", "import", str(source), "-o", str(output)]
    )
    assert result.exit_code == 1
    assert "could not import interoperability bundle" in result.output
    assert "Traceback" not in result.output
    assert output.read_text(encoding="utf-8") == "keep"


def test_interop_report_human_output_discloses_all_field_classes(
    app, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    source = _source(tmp_path)
    bundle_path = tmp_path / "document.json"
    result = runner.invoke(
        app,
        [
            "greek", "interop", "export", str(source),
            "--target", "conllu", "-o", str(bundle_path),
        ],
    )
    assert result.exit_code == 0, result.output
    report = runner.invoke(app, ["greek", "interop", "report", str(bundle_path)])
    assert report.exit_code == 0, report.output
    assert all(label in report.output for label in ("native", "sidecar", "lost"))


@pytest.mark.parametrize("target", ["spacy", "stanza", "cltk"])
def test_interop_cli_builds_and_recovers_each_real_framework_bundle(
    app, tmp_path: Path, target: str
) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip(target)
    source = _source(tmp_path)
    bundle_path = tmp_path / f"{target}.json"
    exported = runner.invoke(
        app,
        [
            "greek", "interop", "export", str(source), "--target", target,
            "-o", str(bundle_path), "--json",
        ],
    )
    assert exported.exit_code == 0, exported.output
    payload = json.loads(exported.stdout)
    assert payload["target"] == target and payload["lossless"] is True
    recovered = tmp_path / f"{target}.conllu"
    imported = runner.invoke(
        app,
        ["greek", "interop", "import", str(bundle_path), "-o", str(recovered)],
    )
    assert imported.exit_code == 0, imported.output
    assert recovered.read_text(encoding="utf-8") == VALID_CONLLU
