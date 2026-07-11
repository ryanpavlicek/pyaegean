"""Opt-in logging for the pyaegean library — stdlib ``logging`` only, off by default.

The library follows the standard-library guidance for a package: it attaches a
``logging.NullHandler`` to its top-level ``aegean`` logger and otherwise never
configures global logging or writes to stderr. Nothing is emitted until the user
opts in with `set_verbosity`, which attaches a single terse stderr handler and
raises the ``aegean`` logger's level. The existing print-based CLI progress lines
are a separate concern and are unaffected by this layer — this is for the
Python-API user who wants to see the fetch/load/build journey.

Module code obtains a logger via `get_logger("data")` (``aegean.data``) and logs
INFO at the genuinely informative step boundaries (fetching, extracting, loading a
corpus) and DEBUG for internals (cache hits, checksum verification). It never logs
token or text content — corpora can be license-restricted, so only ids and counts
are logged.

``set_verbosity`` works both as a plain call (persists) and as a context manager
(restores the prior state on exit). The ``PYAEGEAN_LOG`` environment variable
(``debug``/``info``/``warning``) turns logging on at first use without a code change.
"""

from __future__ import annotations

import logging
import os
import sys
from types import TracebackType

__all__ = ["get_logger", "set_verbosity"]

_ROOT_NAME = "aegean"

# The level names accepted as strings by set_verbosity / PYAEGEAN_LOG. Integer
# levels (e.g. logging.INFO) are accepted directly.
_LEVELS: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

# Attach a NullHandler once, at import, so the library never emits (or warns about
# a missing handler) unless the user opts in. This is the documented library
# pattern; it does no I/O and no formatting work.
_root = logging.getLogger(_ROOT_NAME)
_root.addHandler(logging.NullHandler())

# The single stderr handler that set_verbosity / the env override attach on opt-in.
# None until the user opts in; installed at most once.
_opt_in_handler: logging.Handler | None = None

# Whether the PYAEGEAN_LOG override has been consulted yet (checked once, at first
# use — the first get_logger call, which happens when the first aegean submodule
# that logs is imported).
_env_applied = False


def _coerce_level(level: str | int) -> int:
    """Turn a user-supplied level into a logging int, or raise a clear ValueError."""
    if isinstance(level, bool):  # bool is an int subclass; reject it explicitly
        raise ValueError(_bad_level_msg(level))
    if isinstance(level, int):
        return level
    if isinstance(level, str):
        key = level.strip().lower()
        if key in _LEVELS:
            return _LEVELS[key]
    raise ValueError(_bad_level_msg(level))


def _bad_level_msg(level: object) -> str:
    names = ", ".join(sorted(_LEVELS, key=lambda n: _LEVELS[n]))
    return (
        f"unknown log level {level!r}; use one of {names} "
        "(case-insensitive) or a logging level int"
    )


def _install_handler() -> None:
    """Attach the terse stderr handler to the ``aegean`` logger, at most once."""
    global _opt_in_handler
    if _opt_in_handler is None:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        _root.addHandler(handler)
        _opt_in_handler = handler


def _remove_handler() -> None:
    """Detach the opt-in stderr handler if present (used by the context-manager exit)."""
    global _opt_in_handler
    if _opt_in_handler is not None:
        _root.removeHandler(_opt_in_handler)
        _opt_in_handler = None


def _apply_env_override() -> None:
    """Honor ``PYAEGEAN_LOG`` the first time any logger is requested.

    A valid value turns logging on at that level; an empty or unrecognized value is
    ignored (a bad env var must never break ``import aegean`` or a first call)."""
    global _env_applied
    if _env_applied:
        return
    _env_applied = True
    raw = os.environ.get("PYAEGEAN_LOG")
    if not raw:
        return
    try:
        level = _coerce_level(raw)
    except ValueError:
        return
    _install_handler()
    _root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """The module logger for ``aegean.<name>`` (e.g. ``get_logger("data")``).

    Cheap and side-effect-free except for consulting ``PYAEGEAN_LOG`` once, so
    calling it at module import does not slow ``import aegean`` or emit anything."""
    _apply_env_override()
    full = name if name == _ROOT_NAME or name.startswith(_ROOT_NAME + ".") else f"{_ROOT_NAME}.{name}"
    return logging.getLogger(full)


class _Verbosity:
    """The object `set_verbosity` returns: a no-op when ignored (a plain call), or a
    context manager that restores the prior level and handler state on exit."""

    def __init__(self, prior_level: int, had_handler: bool) -> None:
        self._prior_level = prior_level
        self._had_handler = had_handler

    def __enter__(self) -> "_Verbosity":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        _root.setLevel(self._prior_level)
        if not self._had_handler:
            _remove_handler()


def set_verbosity(level: str | int) -> _Verbosity:
    """Turn on pyaegean's library logging at ``level`` and route it to stderr.

    ``level`` is ``"debug"``, ``"info"``, or ``"warning"`` (case-insensitive), or a
    ``logging`` level int (``logging.INFO``). Usable two ways:

    - as a plain call — ``aegean.set_verbosity("info")`` — which persists until
      changed;
    - as a context manager — ``with aegean.set_verbosity("debug"): ...`` — which
      restores the previous level (and removes the stderr handler if it added one)
      on exit.

    The library attaches nothing and prints nothing until this is called (or
    ``PYAEGEAN_LOG`` is set); it never touches the root logger or `logging.basicConfig`,
    so it does not interfere with an application's own logging configuration.

    Raises ``ValueError`` naming the valid levels for an unrecognized ``level``."""
    new_level = _coerce_level(level)
    prior_level = _root.level
    had_handler = _opt_in_handler is not None
    _install_handler()
    _root.setLevel(new_level)
    return _Verbosity(prior_level, had_handler)
