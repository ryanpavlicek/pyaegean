"""A16 annotation/domain profile inspection CLI contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass

from typer.testing import CliRunner

from aegean import greek
from aegean.cli import _build_app


runner = CliRunner()


@dataclass(frozen=True)
class _Profile:
    profile_id: str
    sha256: str
    values: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return dict(self.values)


def _install_registry(monkeypatch):  # type: ignore[no-untyped-def]
    annotation = _Profile(
        "pyaegean-canonical-v1",
        "a" * 64,
        {
            "profile_id": "pyaegean-canonical-v1",
            "compatibility": "canonical-output",
            "source_convention": "pyaegean",
        },
    )
    domain = _Profile(
        "papyregularized-v1",
        "b" * 64,
        {"profile_id": "papyregularized-v1", "source_layer": "regularized"},
    )
    monkeypatch.setattr(greek, "list_annotation_profiles", lambda: (annotation,), raising=False)
    monkeypatch.setattr(greek, "list_domain_profiles", lambda: (domain,), raising=False)
    return annotation, domain


def test_annotation_profiles_help_and_list_json(monkeypatch):  # type: ignore[no-untyped-def]
    _install_registry(monkeypatch)
    app = _build_app()

    help_result = runner.invoke(app, ["greek", "annotation-profiles", "--help"])
    assert help_result.exit_code == 0, help_result.output
    assert "list" in help_result.output and "show" in help_result.output

    result = runner.invoke(app, ["greek", "annotation-profiles", "list", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["annotation_profiles"][0]["profile_id"] == "pyaegean-canonical-v1"
    assert payload["domain_profiles"][0]["source_layer"] == "regularized"
    assert payload["annotation_profiles"][0]["sha256"] == "a" * 64

    human = runner.invoke(app, ["greek", "annotation-profiles", "list"])
    assert human.exit_code == 0, human.output
    assert "pyaegean-canonical-v1" in human.output
    assert "canonical-output" in human.output
    assert "regularized" in human.output


def test_annotation_profiles_show_and_unknown_id(monkeypatch):  # type: ignore[no-untyped-def]
    _install_registry(monkeypatch)
    app = _build_app()

    result = runner.invoke(
        app,
        ["greek", "annotation-profiles", "show", "pyaegean-canonical-v1", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "annotation"
    assert payload["profile_id"] == "pyaegean-canonical-v1"
    assert payload["sha256"] == "a" * 64

    domain_result = runner.invoke(
        app,
        ["greek", "annotation-profiles", "show", "papyregularized-v1", "--json"],
    )
    assert domain_result.exit_code == 0, domain_result.output
    domain_payload = json.loads(domain_result.stdout)
    assert domain_payload["kind"] == "domain"
    assert domain_payload["source_layer"] == "regularized"

    missing = runner.invoke(app, ["greek", "annotation-profiles", "show", "missing"])
    assert missing.exit_code == 1
    assert "unknown annotation/domain profile 'missing'" in missing.output
    assert "pyaegean-canonical-v1" in missing.output


def test_text_profile_command_remains_distinct(monkeypatch):  # type: ignore[no-untyped-def]
    _install_registry(monkeypatch)
    app = _build_app()
    result = runner.invoke(app, ["greek", "profile", "λόγος", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["script"] == "greek"


def test_builtin_registry_cli_journey() -> None:
    app = _build_app()
    listed = runner.invoke(app, ["greek", "annotation-profiles", "list", "--json"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.stdout)
    assert [item["profile_id"] for item in payload["annotation_profiles"]] == [
        "pyaegean-canonical-v1",
        "perseus-agdt-v1",
        "proiel-diagnostic-v1",
        "papygreek-agdt-v1",
    ]
    assert [item["profile_id"] for item in payload["domain_profiles"]] == [
        "papygreek-regularized-v1",
        "papygreek-diplomatic-surface-v1",
    ]

    shown = runner.invoke(
        app,
        ["greek", "annotation-profiles", "show", "pyaegean-canonical-v1", "--json"],
    )
    assert shown.exit_code == 0, shown.output
    shown_payload = json.loads(shown.stdout)
    assert shown_payload["kind"] == "annotation"
    assert shown_payload["source_revision"] == "grc-joint-v3"
    assert len(shown_payload["sha256"]) == 64
