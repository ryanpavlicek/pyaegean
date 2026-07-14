"""A14 neural JSONL streaming CLI contracts."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from aegean.cli import _build_app


runner = CliRunner()


@pytest.fixture()
def app():  # type: ignore[no-untyped-def]
    return _build_app()


def _stdout(result: object) -> str:
    value = getattr(result, "stdout", None)
    if isinstance(value, str) and value:
        return value
    return getattr(result, "output")


def _stderr(result: object) -> str:
    value = getattr(result, "stderr", None)
    return value if isinstance(value, str) else ""


def test_stream_reads_stdin_and_emits_each_analysis_incrementally(app, monkeypatch):  # type: ignore[no-untyped-def]
    seen: dict[str, object] = {"sentences": []}

    def fake_iter(sentences, **kwargs):  # type: ignore[no-untyped-def]
        seen["kwargs"] = kwargs
        for sentence in sentences:
            cast_seen = seen["sentences"]
            assert isinstance(cast_seen, list)
            cast_seen.append(sentence)
            yield {"tokens": sentence, "ok": True}

    monkeypatch.setattr("aegean.cli._greek._activate", lambda **kwargs: None)
    monkeypatch.setattr("aegean.greek.iter_analyze_sentences", fake_iter)
    result = runner.invoke(
        app,
        ["greek", "stream", "-", "--batch-size", "2", "--long-input", "partial"],
        input='["ὁ", "λόγος"]\n["καί"]\n',
    )
    assert result.exit_code == 0, _stdout(result)
    rows = [json.loads(line) for line in _stdout(result).splitlines() if line.strip()]
    assert rows == [
        {"tokens": ["ὁ", "λόγος"], "ok": True},
        {"tokens": ["καί"], "ok": True},
    ]
    assert seen["sentences"] == [["ὁ", "λόγος"], ["καί"]]
    assert seen["kwargs"] == {
        "batch_size": 2,
        "with_probs": False,
        "long_input": "partial",
        "domain": None,
        "policy": None,
    }


def test_stream_reads_a_path_and_supports_windowed_alias(app, monkeypatch, tmp_path: Path):  # type: ignore[no-untyped-def]
    source = tmp_path / "sentences.jsonl"
    source.write_text('["ἄνδρα"]\n', encoding="utf-8")
    seen: list[object] = []

    def fake_iter(sentences, **kwargs):  # type: ignore[no-untyped-def]
        seen.append(kwargs)
        yield {"tokens": next(iter(sentences))}

    monkeypatch.setattr("aegean.cli._greek._activate", lambda **kwargs: None)
    monkeypatch.setattr("aegean.greek.iter_analyze_sentences", fake_iter)
    result = runner.invoke(app, ["greek", "stream", str(source), "--windowed"])
    assert result.exit_code == 0, _stdout(result)
    assert json.loads(_stdout(result)) == {"tokens": ["ἄνδρα"]}
    assert seen == [
        {
            "batch_size": None,
            "with_probs": False,
            "long_input": "windowed",
            "domain": None,
            "policy": None,
        }
    ]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not-json\n", "JSONL input line 1 is not valid JSON"),
        ('{"tokens": ["λόγος"]}\n', "must be a JSON array of token strings"),
        ('["λόγος", 1]\n', "token 1 must be a string"),
    ],
)
def test_stream_rejects_malformed_jsonl_without_traceback(
    app, monkeypatch, payload: str, message: str
):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("aegean.cli._greek._activate", lambda **kwargs: None)

    def fake_iter(sentences, **kwargs):  # type: ignore[no-untyped-def]
        yield from sentences

    monkeypatch.setattr("aegean.greek.iter_analyze_sentences", fake_iter)
    result = runner.invoke(app, ["greek", "stream", "-"], input=payload)
    assert result.exit_code != 0
    output = _stdout(result)
    assert message in output
    assert "Traceback" not in output


def test_stream_validates_long_input_before_activation(app, monkeypatch):  # type: ignore[no-untyped-def]
    activated = False

    def activate(**kwargs):  # type: ignore[no-untyped-def]
        nonlocal activated
        activated = True

    monkeypatch.setattr("aegean.cli._greek._activate", activate)
    result = runner.invoke(app, ["greek", "stream", "-", "--long-input", "unknown"])
    assert result.exit_code != 0
    assert "--long-input must be strict, partial, or windowed" in _stdout(result)
    assert not activated


def test_stream_help_is_safe_under_windows_cp1252() -> None:
    code = """
import sys
sys.stdout.reconfigure(encoding='cp1252', errors='strict')
from aegean.cli import _build_app
sys.argv = ['aegean', 'greek', 'stream', '--help']
_build_app()()
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=False,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")


def test_stream_missing_path_is_a_clean_error(app, monkeypatch, tmp_path: Path):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("aegean.cli._greek._activate", lambda **kwargs: None)

    def fake_iter(sentences, **kwargs):  # type: ignore[no-untyped-def]
        yield from sentences

    monkeypatch.setattr("aegean.greek.iter_analyze_sentences", fake_iter)
    missing = tmp_path / "missing.jsonl"
    result = runner.invoke(app, ["greek", "stream", str(missing)])
    assert result.exit_code != 0
    assert "could not open JSONL input" in _stdout(result)
    assert "Traceback" not in _stdout(result)


def test_stream_keeps_prior_output_when_a_later_line_fails(app, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("aegean.cli._greek._activate", lambda **kwargs: None)

    def fake_iter(sentences, **kwargs):  # type: ignore[no-untyped-def]
        for sentence in sentences:
            yield {"tokens": sentence}

    monkeypatch.setattr("aegean.greek.iter_analyze_sentences", fake_iter)
    result = runner.invoke(
        app,
        ["greek", "stream", "-"],
        input='["λόγος"]\nnot-json\n',
    )
    assert result.exit_code != 0
    assert '{"tokens":["λόγος"]}' in _stdout(result)
    assert "JSONL input line 2 is not valid JSON" in _stderr(result)
    assert "Traceback" not in (_stdout(result) + _stderr(result))
