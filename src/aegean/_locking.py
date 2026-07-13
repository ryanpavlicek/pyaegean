"""Small dependency-free cross-process advisory file locks.

The lock file is persistent; ownership is the operating system lock held on its
first byte, not the pathname's existence.  Kernel ownership is released on
normal close and on process death, avoiding stale leases and check/unlink races.
"""

from __future__ import annotations

import os
import pathlib
import time
from types import TracebackType


class FileLock:
    """A cross-process advisory lock associated with ``path``.

    The timing arguments remain accepted for compatibility. ``poll_every``
    controls acquisition polling; stale and heartbeat timings are validated but
    are unnecessary because the OS releases ownership when a process exits.
    Lock files intentionally remain on disk after release.
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
        self.poll_every = poll_every
        self._fd: int | None = None

    @staticmethod
    def _try_lock(fd: int) -> bool:
        if os.name == "nt":
            import msvcrt

            try:
                os.lseek(fd, 0, os.SEEK_SET)
                getattr(msvcrt, "locking")(fd, getattr(msvcrt, "LK_NBLCK"), 1)
            except OSError:
                return False
            return True
        import fcntl

        try:
            flock = getattr(fcntl, "flock")
            flock(fd, getattr(fcntl, "LOCK_EX") | getattr(fcntl, "LOCK_NB"))
        except OSError:
            return False
        return True

    @staticmethod
    def _unlock(fd: int) -> None:
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            getattr(msvcrt, "locking")(fd, getattr(msvcrt, "LK_UNLCK"), 1)
            return
        import fcntl

        getattr(fcntl, "flock")(fd, getattr(fcntl, "LOCK_UN"))

    def _open(self) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        # Windows byte-range locking requires the byte to exist. Keeping this
        # sentinel also makes the same representation portable across platforms.
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
            os.fsync(fd)
        return fd

    @classmethod
    def is_locked(cls, path: str | pathlib.Path) -> bool:
        """Return whether another process/thread currently owns ``path``."""
        probe = cls(path)
        fd = probe._open()
        try:
            if not probe._try_lock(fd):
                return True
            probe._unlock(fd)
            return False
        finally:
            os.close(fd)

    def __enter__(self) -> "FileLock":
        if self._fd is not None:
            raise RuntimeError("FileLock instance is already held")
        fd = self._open()
        while not self._try_lock(fd):
            time.sleep(self.poll_every)
        self._fd = fd
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            self._unlock(fd)
        finally:
            os.close(fd)
