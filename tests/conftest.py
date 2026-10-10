"""Shared pytest configuration.

The Textual TUI Pilot tests (``test_tui_*.py``) drive a live Textual app and are timing-sensitive:
each waits up to ~30 s for the screen to settle. Run several of them at once (as ``pytest-xdist``
would, spreading tests across worker processes) and they contend for the CPU, so a settle can miss
its deadline and spuriously time out. This hook pins every TUI test to a single ``xdist`` group, so
under ``pytest -n N --dist loadgroup`` they all run serially on one worker while the rest of the
suite parallelizes — fast *and* reliable. It is a no-op without ``-n`` (a plain serial run).
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-neural-integration",
        action="store_true",
        help="fail neural integration runs on any skip or zero passing tests",
    )


class _RequiredNeuralIntegration:
    def __init__(self) -> None:
        self.skipped: list[str] = []
        self.passed = 0

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.skipped:
            self.skipped.append(report.nodeid)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.skipped:
            self.skipped.append(report.nodeid)
        if report.when == "call" and report.passed:
            self.passed += 1

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        if self.skipped or not session.testscollected or not self.passed:
            if session.exitstatus == pytest.ExitCode.OK:
                session.exitstatus = pytest.ExitCode.TESTS_FAILED
            reporter = session.config.pluginmanager.get_plugin("terminalreporter")
            if reporter is not None:
                reporter.write_sep(
                    "=",
                    "required neural integration failed: "
                    f"{len(self.skipped)} skips, {session.testscollected} collected, "
                    f"{self.passed} passed",
                    red=True,
                )


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--require-neural-integration"):
        if getattr(config.option, "numprocesses", None):
            raise pytest.UsageError("required neural integration must run sequentially")
        config.pluginmanager.register(_RequiredNeuralIntegration())


def _neural_unavailable(message: str, *, required: bool) -> None:
    if required:
        pytest.fail(message)
    pytest.skip(message)


@contextmanager
def _cached_neural_backend(*, required: bool = False) -> Iterator[Any]:
    """Activate cached neural support without fetching; restore the prior facade."""
    for dependency in ("numpy", "onnxruntime", "tokenizers"):
        if importlib.util.find_spec(dependency) is None:
            _neural_unavailable(f"{dependency} not installed (the [neural] extra)", required=required)

    from aegean import data, greek
    from aegean.greek import joint, runtime

    selected = joint._resolve_neural_variant("default")
    assert selected.dataset is not None
    spec = data._REMOTE.get(selected.dataset)
    assert spec is not None, "default neural model is not registered"
    root = data.cache_dir()
    if not data.is_downloaded(spec, root):
        remnants = [
            root / (selected.dataset + suffix)
            for suffix in (".part", ".part.info", ".extract", ".old", ".sha256")
            if (root / (selected.dataset + suffix)).exists()
        ]
        assert not remnants, f"incomplete neural cache entry: {remnants}"
        _neural_unavailable(
            "neural model not cached; run scripts/check_neural_integration.py --provision",
            required=required,
        )

    def no_download(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("cached-only neural check attempted a download")

    previous_pipeline = runtime.default_pipeline()
    previous_active = joint._ACTIVE
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PYAEGEAN_ORT_PROVIDERS", "CPUExecutionProvider")
        patch.setattr(data, "_download", no_download)
        try:
            greek.use_neural_pipeline(variant="default")
            model = joint.active()
            assert model is not None, "neural activation did not install a backend"
            yield model
        finally:
            runtime._set_default_pipeline(previous_pipeline)
            joint._ACTIVE = previous_active


@pytest.fixture(scope="module")
def cached_neural_model() -> Iterator[Any]:
    """Optional real-model checks skip absence, while corrupt cached models fail."""
    with _cached_neural_backend() as model:
        yield model


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "test_tui_" in str(item.fspath):
            item.add_marker(pytest.mark.xdist_group("tui"))
