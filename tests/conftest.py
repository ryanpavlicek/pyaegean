"""Shared pytest configuration.

The Textual TUI Pilot tests (``test_tui_*.py``) drive a live Textual app and are timing-sensitive:
each waits up to ~30 s for the screen to settle. Run several of them at once (as ``pytest-xdist``
would, spreading tests across worker processes) and they contend for the CPU, so a settle can miss
its deadline and spuriously time out. This hook pins every TUI test to a single ``xdist`` group, so
under ``pytest -n N --dist loadgroup`` they all run serially on one worker while the rest of the
suite parallelizes — fast *and* reliable. It is a no-op without ``-n`` (a plain serial run).
"""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "test_tui_" in str(item.fspath):
            item.add_marker(pytest.mark.xdist_group("tui"))
