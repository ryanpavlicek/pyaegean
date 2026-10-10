"""Release dependency and source-identity contracts for the actual workflow graph."""

from __future__ import annotations

import ast
import copy
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
CI_JOBS = (
    "test", "geo", "interop", "neural-integration", "demo-released-wheel",
    "notebooks", "build", "footprint",
)
SELECTED_SHA = "1" * 40
OTHER_SHA = "2" * 40


def _workflow(name: str) -> dict[str, Any]:
    # BaseLoader preserves the GitHub Actions `on` key instead of YAML 1.1 boolean coercion.
    return yaml.load(
        (ROOT / ".github" / "workflows" / f"{name}.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )


def _evaluate(expression: str, context: dict[str, Any], *, success: bool = True) -> Any:
    """Evaluate the workflow's small expression subset without executing Python source."""
    expression = expression.strip()
    if expression.startswith("${{"):
        assert expression.endswith("}}")
        expression = expression[3:-2].strip()
    expression = expression.replace("&&", " and ").replace("||", " or ")

    def visit(node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return context.get(node.id, "")
        if isinstance(node, ast.Attribute):
            value = visit(node.value)
            return value.get(node.attr, "") if isinstance(value, dict) else ""
        if isinstance(node, ast.BoolOp):
            # GitHub's || supplies fallback values, not just boolean results.
            result = visit(node.values[0])
            for value in node.values[1:]:
                if isinstance(node.op, ast.Or) and result:
                    return result
                if isinstance(node.op, ast.And) and not result:
                    return result
                result = visit(value)
            return result
        if isinstance(node, ast.Compare):
            assert len(node.ops) == len(node.comparators) == 1
            left, right = visit(node.left), visit(node.comparators[0])
            if isinstance(node.ops[0], ast.Eq):
                return left == right
            if isinstance(node.ops[0], ast.NotEq):
                return left != right
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            arguments = [visit(argument) for argument in node.args]
            if node.func.id == "startsWith":
                return str(arguments[0]).lower().startswith(str(arguments[1]).lower())
            if node.func.id == "success":
                return success
            if node.func.id == "always":
                return True
            if node.func.id in {"failure", "cancelled"}:
                return False
        raise AssertionError(f"Unsupported workflow expression: {ast.dump(node)}")

    return visit(ast.parse(expression, mode="eval").body)


def _needs(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else needs


def _context(event: str, target: str = "pypi", tag: str = "v0.59.0") -> dict[str, Any]:
    return {
        "github": {
            "event_name": event,
            "sha": SELECTED_SHA,
            "ref": "refs/heads/selected-branch",
            "event": {"release": {"tag_name": tag}},
        },
        "inputs": {"target": target},
    }


def _run_jobs(
    workflow: dict[str, Any], context: dict[str, Any], outcomes: dict[str, str] | None = None,
) -> dict[str, str]:
    """Schedule the parsed DAG with Actions' implicit success() dependency condition."""
    outcomes = outcomes or {}
    pending = dict(workflow["jobs"])
    results: dict[str, str] = {}
    while pending:
        ready = [name for name, job in pending.items() if set(_needs(job)) <= results.keys()]
        assert ready, "Workflow dependencies are cyclic or reference absent jobs"
        for name in ready:
            job = pending.pop(name)
            success = all(results[dependency] == "success" for dependency in _needs(job))
            condition = job.get("if", "success()")
            explicit_status = re.search(r"\b(?:success|always|failure|cancelled)\s*\(", condition)
            should_run = (success or explicit_status is not None) and bool(
                _evaluate(condition, context, success=success)
            )
            results[name] = outcomes.get(name, "success") if should_run else "skipped"
    return results


def _checkout(job: dict[str, Any]) -> dict[str, Any]:
    checkouts = [
        step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")
    ]
    assert len(checkouts) == 1
    return checkouts[0]


def _assert_validation_blocks_publishing(
    release: dict[str, Any], context: dict[str, Any], result: str,
) -> None:
    states = _run_jobs(release, context, {"validate": result})
    assert states["validate"] == result
    assert states["build"] == states["pypi"] == states["testpypi"] == "skipped"


def test_ci_call_reuses_every_authoritative_job_and_same_commit() -> None:
    ci = _workflow("ci")
    assert {"push", "pull_request", "workflow_call"} <= ci["on"].keys()
    ref_input = ci["on"]["workflow_call"]["inputs"]["ref"]
    assert ref_input["required"] == "true" and ref_input["type"] == "string"
    assert set(ci["jobs"]) == set(CI_JOBS)
    assert ci["jobs"]["test"]["strategy"]["matrix"]["python-version"] == [
        "3.10", "3.11", "3.12", "3.13", "3.14",
    ]
    for job in ci["jobs"].values():
        assert "if" not in job, "Required validation must run for release calls too"
        ref = _checkout(job)["with"]["ref"]
        caller = {"inputs": {"ref": SELECTED_SHA}, "github": {"sha": OTHER_SHA}}
        assert _evaluate(ref, caller) == SELECTED_SHA
        assert _evaluate(ref, {"inputs": {}, "github": {"sha": OTHER_SHA}}) == OTHER_SHA


@pytest.mark.parametrize(
    "event,target",
    [("release", "pypi"), ("workflow_dispatch", "pypi"), ("workflow_dispatch", "testpypi")],
)
def test_validation_and_build_use_release_or_manual_selected_commit(
    event: str, target: str,
) -> None:
    release = _workflow("release")
    context = _context(event, target)
    source = release["jobs"]["source"]
    assert _evaluate(_checkout(source)["with"]["ref"], context) == SELECTED_SHA
    resolved = {"steps": {"source": {"outputs": {"sha": SELECTED_SHA}}}}
    assert _evaluate(source["outputs"]["sha"], resolved) == SELECTED_SHA
    context["needs"] = {"source": {"outputs": {"sha": SELECTED_SHA}, "result": "success"}}
    validate = release["jobs"]["validate"]
    assert validate["uses"] == "./.github/workflows/ci.yml"
    assert _needs(validate) == ["source"]
    assert _evaluate(validate["with"]["ref"], context) == SELECTED_SHA
    assert _evaluate(_checkout(release["jobs"]["build"])["with"]["ref"], context) == SELECTED_SHA


@pytest.mark.parametrize("checkout_sha", [SELECTED_SHA, OTHER_SHA])
def test_source_resolution_exports_verified_commit_or_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, checkout_sha: str,
) -> None:
    source = _workflow("release")["jobs"]["source"]
    step = next(step for step in source["steps"] if step.get("id") == "source")
    assert step["shell"] == "python"
    output = tmp_path / "output"
    monkeypatch.setenv(
        "EXPECTED_SHA", _evaluate(step["env"]["EXPECTED_SHA"], _context("release")),
    )
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    def checked_out_commit(command: list[str], *, text: bool) -> str:
        assert command == ["git", "rev-parse", "HEAD"] and text is True
        return checkout_sha + "\n"

    monkeypatch.setattr(subprocess, "check_output", checked_out_commit)
    script = compile(step["run"], "<release source resolution>", "exec")
    if checkout_sha == SELECTED_SHA:
        exec(script, {})
        assert output.read_text(encoding="utf-8") == f"sha={SELECTED_SHA}\n"
    else:
        with pytest.raises(SystemExit, match="differs from the selected event commit"):
            exec(script, {})
        assert not output.exists()


@pytest.mark.parametrize(
    "event,target,tag,publisher",
    [
        ("release", "", "v0.59.0", "pypi"),
        ("workflow_dispatch", "pypi", "", "pypi"),
        ("workflow_dispatch", "testpypi", "", "testpypi"),
        ("release", "", "grc-joint-v3", None),
        ("release", "", "corpus-data-v2", None),
        ("push", "pypi", "v0.59.0", None),
    ],
)
def test_release_event_conditions_and_asset_release_guard(
    event: str, target: str, tag: str, publisher: str | None,
) -> None:
    release = _workflow("release")
    assert release["on"]["release"]["types"] == ["published"]
    assert release["on"]["workflow_dispatch"]["inputs"]["target"]["options"] == ["testpypi", "pypi"]
    states = _run_jobs(release, _context(event, target, tag))
    assert {name for name in ("pypi", "testpypi") if states[name] == "success"} == (
        {publisher} if publisher else set()
    )
    for name in ("source", "validate", "build"):
        assert states[name] == ("success" if publisher else "skipped")


@pytest.mark.parametrize("ci_job", CI_JOBS)
@pytest.mark.parametrize("result", ["failure", "cancelled"])
@pytest.mark.parametrize("event,target", [("release", "pypi"), ("workflow_dispatch", "testpypi")])
def test_every_called_ci_failure_blocks_both_publishers(
    ci_job: str, result: str, event: str, target: str,
) -> None:
    ci_results = _run_jobs(_workflow("ci"), _context(event, target), {ci_job: result})
    assert ci_results[ci_job] == result
    # A reusable workflow fails/cancels when one of its required jobs fails/cancels.
    _assert_validation_blocks_publishing(_workflow("release"), _context(event, target), result)


@pytest.mark.parametrize("job", ["source", "validate", "build"])
@pytest.mark.parametrize("result", ["failure", "cancelled", "skipped"])
@pytest.mark.parametrize("target", ["pypi", "testpypi"])
def test_failed_or_skipped_prerequisites_never_publish(job: str, result: str, target: str) -> None:
    states = _run_jobs(_workflow("release"), _context("workflow_dispatch", target), {job: result})
    assert states[job] == result
    assert states["pypi"] == states["testpypi"] == "skipped"


def test_dependency_guard_detects_removal_of_validation_dependency() -> None:
    release = copy.deepcopy(_workflow("release"))
    release["jobs"]["build"]["needs"] = ["source"]
    with pytest.raises(AssertionError):
        _assert_validation_blocks_publishing(release, _context("release"), "failure")


def test_neural_job_provisions_real_model_and_requires_bounded_cpu_execution() -> None:
    job = _workflow("ci")["jobs"]["neural-integration"]
    assert 0 < int(job["timeout-minutes"]) <= 30
    assert "strategy" not in job
    assert job["env"]["CUDA_VISIBLE_DEVICES"] == ""
    for variable in (
        "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
    ):
        assert job["env"][variable] == "1"
    commands = [shlex.split(step["run"]) for step in job["steps"] if "run" in step]
    assert ["pip", "install", "-e", ".[dev,neural]"] in commands
    integration_command = ["python", "scripts/check_neural_integration.py", "--provision"]
    integration_step = next(
        step for step in job["steps"]
        if "run" in step and shlex.split(step["run"]) == integration_command
    )
    assert integration_step["env"]["PYAEGEAN_CACHE"] == "${{ runner.temp }}/neural-integration"


def test_oidc_only_reaches_publishers_and_failures_cannot_be_ignored() -> None:
    for workflow_name in ("ci", "release"):
        workflow = _workflow(workflow_name)
        assert workflow["permissions"] == {"contents": "read"}
        for name, job in workflow["jobs"].items():
            publisher = workflow_name == "release" and name in {"pypi", "testpypi"}
            if publisher:
                assert job["permissions"] == {"id-token": "write"}
            else:
                assert "id-token" not in job.get("permissions", {})
            for executable in [job, *job.get("steps", [])]:
                assert executable.get("continue-on-error", "false") == "false"
