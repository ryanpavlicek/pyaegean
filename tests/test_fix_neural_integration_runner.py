"""Required integration runs cannot pass without executing their checks."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_neural_integration_under_test", ROOT / "scripts" / "check_neural_integration.py"
)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_runner_enforces_required_cpu_tests_and_propagates_failure(monkeypatch: Any) -> None:
    prepared: list[bool] = []
    commands: list[tuple[list[str], dict[str, Any]]] = []
    monkeypatch.setenv("PYTEST_ADDOPTS", "-n 8 --collect-only")
    monkeypatch.setenv("PYAEGEAN_ORT_PROVIDERS", "CUDAExecutionProvider")
    monkeypatch.setattr(runner, "_prepare_model", lambda *, provision: prepared.append(provision))

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append((command, kwargs))
        return subprocess.CompletedProcess(command, 5)

    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.main(["--provision"]) == 5
    assert prepared == [True]
    command, kwargs = commands[0]
    assert command[:3] == [sys.executable, "-m", "pytest"]
    assert "--require-neural-integration" in command
    assert command[command.index("-m", 3) + 1] == "neural_integration"
    assert command[-1] == str(ROOT / "tests" / "test_neural_integration.py")
    assert "addopts=" in command
    assert "-n" not in command
    assert kwargs["cwd"] == ROOT and kwargs["timeout"] == 900
    assert "PYTEST_ADDOPTS" not in kwargs["env"]
    assert kwargs["env"]["PYAEGEAN_ORT_PROVIDERS"] == "CPUExecutionProvider"
    assert kwargs["env"]["CUDA_VISIBLE_DEVICES"] == ""
    assert kwargs["env"]["OMP_NUM_THREADS"] == "1"


@pytest.mark.parametrize("failure", [RuntimeError("missing dependency"), RuntimeError("missing model")])
def test_setup_failure_stops_the_runner(monkeypatch: Any, capsys: Any, failure: Exception) -> None:
    def prepare(**_kwargs: Any) -> None:
        raise failure

    monkeypatch.setattr(runner, "_prepare_model", prepare)
    monkeypatch.setattr(runner.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("ran pytest"))
    assert runner.main([]) == 1
    assert str(failure) in capsys.readouterr().err


def test_model_provisioning_is_explicit_and_limited_to_the_default_pin(
    monkeypatch: Any, tmp_path: Path,
) -> None:
    from aegean import data
    from aegean.greek import joint

    selected = joint._resolve_neural_variant("default")
    calls: list[str] = []
    monkeypatch.setattr(joint, "_require_neural_extra", lambda: None)
    monkeypatch.setattr(data, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(data, "fetch", lambda name: calls.append(name))
    with pytest.raises(RuntimeError, match="not cached"):
        runner._prepare_model(provision=False)
    assert calls == []
    runner._prepare_model(provision=True)
    assert calls == [selected.dataset]
    (tmp_path / str(selected.dataset)).mkdir()
    runner._prepare_model(provision=False)
    assert calls == [selected.dataset]


def test_unpinned_url_override_is_rejected_before_provision(monkeypatch: Any, tmp_path: Path) -> None:
    from aegean import data
    from aegean.greek import joint

    monkeypatch.setattr(joint, "_require_neural_extra", lambda: None)
    monkeypatch.setattr(data, "cache_dir", lambda: tmp_path)
    monkeypatch.setenv("PYAEGEAN_GRC_JOINT_URL", "https://example.invalid/model.tar.gz")
    monkeypatch.setattr(data, "fetch", lambda *_args: pytest.fail("downloaded unpinned model"))
    with pytest.raises(RuntimeError, match="enforced registry pin"):
        runner._prepare_model(provision=True)


def test_missing_neural_extra_is_rejected_before_asset_access(monkeypatch: Any) -> None:
    from aegean import data
    from aegean.greek import joint

    def missing_extra() -> None:
        raise joint.NeuralPipelineNotLoadedError("missing [neural] extra")

    monkeypatch.setattr(joint, "_require_neural_extra", missing_extra)
    monkeypatch.setattr(data, "versions", lambda: pytest.fail("read assets before checking extras"))
    with pytest.raises(joint.NeuralPipelineNotLoadedError, match="missing"):
        runner._prepare_model(provision=True)


@pytest.mark.parametrize("failure", [OSError("cannot launch pytest"), subprocess.TimeoutExpired("pytest", 900)])
def test_launch_failure_or_timeout_cannot_pass(monkeypatch: Any, failure: Exception) -> None:
    monkeypatch.setattr(runner, "_prepare_model", lambda **_kwargs: None)

    def run(*_args: Any, **_kwargs: Any) -> None:
        raise failure

    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.main([]) == 1


@pytest.mark.parametrize(
    "source,expected",
    [
        ("def test_pass():\n    assert 2 + 2 == 4\n", 0),
        ("import pytest\ndef test_skip():\n    pytest.skip('unavailable')\n", 1),
        ("import pytest\npytest.skip('unavailable', allow_module_level=True)\n", 5),
        ("# Empty test module\n", 5),
        ("def test_fail():\n    assert False\n", 1),
        ("import pytest\n@pytest.mark.xfail\ndef test_xfail():\n    assert False\n", 1),
        (
            "import pytest\n@pytest.fixture\ndef model():\n"
            "    raise RuntimeError('activation failed')\n"
            "def test_activation(model):\n    assert model is not None\n",
            1,
        ),
        (
            "import pytest\ndef test_pass():\n    assert True\n"
            "def test_skip():\n    pytest.skip('unavailable')\n",
            1,
        ),
    ],
    ids=["pass", "skip", "collection-skip", "empty", "failure", "xfail", "activation", "mixed"],
)
def test_required_gate_checks_actual_pytest_results(
    tmp_path: Path, source: str, expected: int,
) -> None:
    (tmp_path / "conftest.py").write_text(
        (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    target = tmp_path / "test_required.py"
    target.write_text(source, encoding="utf-8")
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    env.pop("PYTEST_ADDOPTS", None)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--require-neural-integration", str(target)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    if expected != 0 and "FAILED" not in result.stdout and "ERROR" not in result.stdout:
        assert "required neural integration failed" in result.stdout
