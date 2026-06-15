"""Saving analysis & AI results to files: write_result (.json/.csv/.txt), the `-o` option on
analysis commands, and ExploratoryResult serialization (which keeps the exploratory flag)."""

from __future__ import annotations

import csv
import json

from aegean.ai.client import ExploratoryResult
from aegean.ai.grounding import GroundingItem


def test_exploratory_result_round_trip() -> None:
    r = ExploratoryResult(
        text="a king", kind="gloss", provider="anthropic", model="m", prompt_version="v1",
        grounding=(GroundingItem("βασιλεύς", source="lexicon:LSJ", ref="qa-si-re-u"),),
        exploratory=True, data={"x": 1},
    )
    d = r.to_dict()
    assert d["exploratory"] is True and d["text"] == "a king"
    assert ExploratoryResult.from_dict(d) == r
    assert json.loads(r.to_json())["kind"] == "gloss"


def test_exploratory_to_json_file_keeps_exploratory_flag(tmp_path) -> None:
    r = ExploratoryResult(text="t", kind="translate", provider="p", model="m", prompt_version="v")
    p = tmp_path / "r.json"
    assert r.to_json(p) is None
    assert json.loads(p.read_text(encoding="utf-8"))["exploratory"] is True


def test_write_result_json_csv_txt(tmp_path) -> None:
    from aegean.cli._common import write_result

    data = [{"item": "A", "count": 3}, {"item": "B", "count": 1}]
    pj, pc, pt = tmp_path / "r.json", tmp_path / "r.csv", tmp_path / "r.txt"
    write_result(data, pj)
    write_result(data, pc)
    write_result(data, pt)
    assert json.loads(pj.read_text(encoding="utf-8")) == data
    rows = list(csv.DictReader(pc.read_text(encoding="utf-8").splitlines()))
    assert rows[0] == {"item": "A", "count": "3"}
    assert "item\tcount" in pt.read_text(encoding="utf-8")


def test_cli_stats_output_csv_and_json(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    app = _build_app()
    pj, pc = tmp_path / "s.json", tmp_path / "s.csv"
    assert CliRunner().invoke(app, ["stats", "lineara", "--top", "5", "-o", str(pj)]).exit_code == 0
    assert CliRunner().invoke(app, ["stats", "lineara", "--top", "5", "-o", str(pc)]).exit_code == 0
    assert len(json.loads(pj.read_text(encoding="utf-8"))) == 5
    assert len(list(csv.DictReader(pc.read_text(encoding="utf-8").splitlines()))) == 5


def test_cli_analyze_cooccur_output(tmp_path) -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    p = tmp_path / "co.csv"
    r = CliRunner().invoke(
        _build_app(), ["analyze", "cooccur", "lineara", "KU-RO", "--top", "5", "-o", str(p)]
    )
    assert r.exit_code == 0, r.output
    rows = list(csv.DictReader(p.read_text(encoding="utf-8").splitlines()))
    assert rows and "word" in rows[0]


def test_cli_ai_save_helper_keeps_label(tmp_path) -> None:
    from aegean.cli._ai import _write_ai_result

    r = ExploratoryResult(
        text="a king", kind="translate", provider="anthropic", model="m", prompt_version="v"
    )
    pj, pt = tmp_path / "a.json", tmp_path / "a.txt"
    _write_ai_result(r, pj)
    _write_ai_result(r, pt)
    assert json.loads(pj.read_text(encoding="utf-8"))["exploratory"] is True
    assert "[EXPLORATORY" in pt.read_text(encoding="utf-8")
