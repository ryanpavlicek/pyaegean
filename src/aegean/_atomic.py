"""Atomic file replacement, so a crash or full disk mid-write never destroys an
existing file.

Writing straight to a user's path (``open(path, "w")`` / ``write_text`` / a pandas
or sqlite writer) truncates the old file at open, so an interruption leaves a
truncated or empty file where the data was. Instead, write to a unique sibling
temp file and ``os.replace`` it into place: the swap is atomic on a POSIX or NTFS
filesystem, so a reader (and a later run) sees either the old complete file or the
new complete file, never a half-written one, and a failed write leaves the
original intact. This is the same discipline the caches and the ``.part`` download
already use; this module shares it across the export paths.
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import uuid
from collections.abc import Iterator


@contextlib.contextmanager
def atomic_path(path: str | pathlib.Path) -> Iterator[pathlib.Path]:
    """Yield a temp path to write; on clean exit, atomically replace ``path`` with it.

    Usage::

        with atomic_path("out.json") as tmp:
            tmp.write_text(data)      # write the temp file
        # out.json now == the temp file, swapped in atomically

    The temp file is a unique sibling in the same directory (so ``os.replace`` is a
    same-filesystem rename), created only if the parent exists (it is created if
    needed). If the body raises, the temp file is removed and ``path`` is left
    untouched, so a failed or interrupted write never corrupts the prior file.
    """
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        yield tmp
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
