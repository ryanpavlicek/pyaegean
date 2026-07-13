"""Small cross-process lock files with ownership and heartbeat protection.

The lock is intentionally dependency-free: acquisition is an atomic ``O_EXCL``
create, a daemon heartbeat keeps a live holder from looking stale during a long
operation, and a random ownership token prevents an old holder from deleting a
successor's lock after stale-lock recovery.
"""

from __future__ import annotations

import os
import pathlib
import threading
import time
import uuid
from types import TracebackType


class FileLock:
    """An advisory lock represented by ``path``.

    ``stale_after`` bounds recovery from a process that died without cleanup;
    ``heartbeat_every`` must be comfortably smaller so a live long-running holder
    never crosses that boundary. The file is removed on normal release only when
    its random token still belongs to this instance.
    """

    def __init__(
        self,
        path: str | pathlib.Path,
        *,
        stale_after: float = 3600.0,
        poll_every: float = 0.5,
        heartbeat_every: float = 30.0,
    ) -> None:
        if stale_after <= 0 or poll_every <= 0 or heartbeat_every <= 0:
            raise ValueError("lock timing values must be positive")
        if heartbeat_every >= stale_after:
            raise ValueError("heartbeat_every must be smaller than stale_after")
        self.path = pathlib.Path(path)
        self.stale_after = stale_after
        self.poll_every = poll_every
        self.heartbeat_every = heartbeat_every
        self._token = uuid.uuid4().hex
        self._stop = threading.Event()
        self._heartbeat: threading.Thread | None = None

    def _contents(self) -> str:
        return f"{os.getpid()} {self._token}\n"

    def _owns(self) -> bool:
        try:
            return self.path.read_text(encoding="ascii") == self._contents()
        except OSError:
            return False

    def _refresh(self) -> bool:
        """Refresh our lock's mtime, or return false if ownership changed."""
        if not self._owns():
            return False
        try:
            os.utime(self.path, None)  # unlike Path.touch(), never recreates a removed lock
        except OSError:
            return False
        return self._owns()

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(self.heartbeat_every):
            if not self._refresh():
                return

    def _break_if_stale(self) -> bool:
        """Remove a still-stale observed lock; return whether a retry is useful."""
        try:
            before = self.path.stat()
            owner = self.path.read_bytes()
        except OSError:
            return True  # it disappeared while observed
        if time.time() - before.st_mtime <= self.stale_after:
            return False
        # Recheck both identity and age immediately before unlinking. A heartbeat
        # between the observations makes this a live lock and cancels recovery.
        try:
            after = self.path.stat()
            if (
                after.st_mtime_ns != before.st_mtime_ns
                or self.path.read_bytes() != owner
                or time.time() - after.st_mtime <= self.stale_after
            ):
                return False
            self.path.unlink()
        except FileNotFoundError:
            return True
        except OSError:
            return False  # still present but not removable: poll, never busy-spin
        return True

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if not self._break_if_stale():
                    time.sleep(self.poll_every)
                continue
            try:
                os.write(fd, self._contents().encode("ascii"))
            except BaseException:
                os.close(fd)
                self.path.unlink(missing_ok=True)
                raise
            os.close(fd)
            self._heartbeat = threading.Thread(
                target=self._heartbeat_loop,
                name=f"pyaegean-lock-{self.path.name}",
                daemon=True,
            )
            self._heartbeat.start()
            return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._stop.set()
        if self._heartbeat is not None:
            self._heartbeat.join(timeout=max(1.0, self.heartbeat_every * 2))
        if self._owns():
            self.path.unlink(missing_ok=True)
