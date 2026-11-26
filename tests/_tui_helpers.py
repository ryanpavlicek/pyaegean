"""Shared module-scoped Textual Pilot session helper for TUI tests.

Booting a fresh ``AegeanApp`` takes ~0.8-1.5 s per test (plus ~1.5 s to populate
the 1,721-row Linear A table). Reusing one booted ``AegeanApp`` per test module
preserves every individual ``test_*`` node and assertion while eliminating
redundant Textual app startup overhead.

Textual binds ``active_app`` and ``active_message_pump`` ContextVars inside the
``async with app.run_test(...)`` task context. Keeping the entire session inside
one persistent driver task ensures every ``run()`` call and final teardown execute
in the exact same ``contextvars.Context`` where ``run_test()`` was entered.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")


class TuiSession:
    """Persistent event loop + mounted ``AegeanApp`` / Textual ``Pilot``."""

    def __init__(self, *, size: tuple[int, int] = (120, 40)) -> None:
        self._size = size
        self._loop = asyncio.new_event_loop()
        self._queue: asyncio.Queue[tuple[Callable[[Any, Any], Awaitable[Any]], asyncio.Future[Any]] | None] | None = None
        self._driver_task: asyncio.Task[None] | None = None
        self.app: Any = None
        self.pilot: Any = None

    def start(self) -> TuiSession:
        from aegean.tui.app import AegeanApp

        ready: asyncio.Future[None] = self._loop.create_future()
        queue: asyncio.Queue[tuple[Callable[[Any, Any], Awaitable[Any]], asyncio.Future[Any]] | None] = asyncio.Queue()
        self._queue = queue

        async def _driver() -> None:
            try:
                self.app = AegeanApp()
                async with self.app.run_test(size=self._size) as pilot:
                    self.pilot = pilot
                    await pilot.pause()
                    if not ready.done():
                        ready.set_result(None)
                    while True:
                        item = await queue.get()
                        if item is None:
                            break
                        fn, fut = item
                        try:
                            result = await fn(self.app, pilot)
                        except BaseException as exc:
                            if not fut.done():
                                fut.set_exception(exc)
                        else:
                            if not fut.done():
                                fut.set_result(result)
            except BaseException as exc:
                if not ready.done():
                    ready.set_exception(exc)
                else:
                    raise

        self._driver_task = self._loop.create_task(_driver())
        self._loop.run_until_complete(ready)
        return self

    def run(self, fn: Callable[[Any, Any], Awaitable[T]]) -> T:
        assert self._queue is not None and self._driver_task is not None
        fut: asyncio.Future[T] = self._loop.create_future()
        self._queue.put_nowait((fn, fut))
        return self._loop.run_until_complete(fut)

    def close(self) -> None:
        try:
            if self._queue is not None and self._driver_task is not None:
                self._queue.put_nowait(None)
                self._loop.run_until_complete(self._driver_task)
        finally:
            self._loop.close()
