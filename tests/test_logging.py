"""The opt-in stdlib logging layer (`aegean.set_verbosity` / `aegean._log`).

Off by default (nothing to stderr), a call or a context manager, honoring PYAEGEAN_LOG,
and emitting the fetch/load/build INFO sequence a Python-API user wonders about. No
network: fetch is exercised with a file:// URL, load with a registered in-memory loader."""

from __future__ import annotations

import logging

import pytest

import aegean
from aegean import _log, data
from aegean.core.corpus import Corpus, register_loader
from aegean.core.model import Document, Token, TokenKind
from aegean.data import DataSpec


@pytest.fixture(autouse=True)
def _restore_logging_state():
    """Snapshot and restore the ``aegean`` logger + module globals around each test, so a
    plain ``set_verbosity`` call (which deliberately persists) never leaks into another test."""
    root = _log._root
    saved_level = root.level
    saved_handlers = list(root.handlers)
    saved_opt = _log._opt_in_handler
    saved_env = _log._env_applied
    try:
        yield
    finally:
        root.setLevel(saved_level)
        for h in list(root.handlers):
            if h not in saved_handlers:
                root.removeHandler(h)
        for h in saved_handlers:
            if h not in root.handlers:
                root.addHandler(h)
        _log._opt_in_handler = saved_opt
        _log._env_applied = saved_env


def _clean_default_state(monkeypatch) -> None:
    """Force the pristine no-opt-in state (no stderr handler, delegating level)."""
    monkeypatch.delenv("PYAEGEAN_LOG", raising=False)
    _log._remove_handler()
    _log._root.setLevel(logging.NOTSET)
    _log._env_applied = True  # already consulted; do not re-apply from the ambient env


# ── set_verbosity as a plain call ─────────────────────────────────────────────
def test_set_verbosity_call_sets_level():
    aegean.set_verbosity("info")
    assert _log._root.level == logging.INFO
    aegean.set_verbosity("debug")
    assert _log._root.level == logging.DEBUG  # a later call persists the new level


def test_set_verbosity_accepts_logging_int():
    aegean.set_verbosity(logging.WARNING)
    assert _log._root.level == logging.WARNING


def test_opt_in_writes_to_stderr(capsys):
    aegean.set_verbosity("info")
    _log.get_logger("data").info("hello %s", "world")
    err = capsys.readouterr().err
    assert "aegean.data: hello world" in err  # terse "name: message" format


# ── set_verbosity as a context manager ────────────────────────────────────────
def test_context_manager_restores_prior_level():
    aegean.set_verbosity("warning")  # establish a prior level + handler
    before = _log._root.level
    with aegean.set_verbosity("debug"):
        assert _log._root.level == logging.DEBUG
    assert _log._root.level == before  # restored on exit


def test_context_manager_removes_handler_it_added(monkeypatch):
    _clean_default_state(monkeypatch)
    assert _log._opt_in_handler is None
    with aegean.set_verbosity("info"):
        assert _log._opt_in_handler is not None
    # It added the handler and set the level, so exit undoes both.
    assert _log._opt_in_handler is None
    assert _log._root.level == logging.NOTSET


# ── the load journey emits the expected INFO sequence, nothing at WARNING ──────
def test_load_that_fetches_emits_info_sequence(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    src = tmp_path / "blob.bin"
    src.write_bytes(b"payload-bytes")
    monkeypatch.setitem(
        data._REMOTE, "logblob", DataSpec(name="logblob", url=src.as_uri(), license="x")
    )

    def _loader() -> Corpus:
        data.fetch("logblob")  # a real fetch from the file:// URL → aegean.data INFO
        doc = Document(
            id="d1", script_id="greek", tokens=[Token("α", TokenKind.WORD)], lines=[[0]]
        )
        return Corpus([doc], script_id="greek")

    register_loader("logtest", _loader)

    with caplog.at_level(logging.INFO, logger="aegean"):
        aegean.load("logtest")

    msgs = [(r.name, r.getMessage()) for r in caplog.records]
    assert ("aegean.data", "fetching dataset 'logblob'") in msgs
    assert ("aegean.core", "loading corpus 'logtest'") in msgs
    assert ("aegean.core", "loaded corpus 'logtest' (1 documents)") in msgs
    # nothing token/text content, and nothing at WARNING or above
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)


def test_no_content_logged_only_ids_and_counts(tmp_path, monkeypatch, caplog):
    # A sanity check that the load path logs the id + count, never the token text.
    doc = Document(
        id="secretdoc", script_id="greek", tokens=[Token("απορρητο", TokenKind.WORD)],
        lines=[[0]],
    )
    register_loader("nocontent", lambda: Corpus([doc], script_id="greek"))
    with caplog.at_level(logging.DEBUG, logger="aegean"):
        aegean.load("nocontent")
    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert "nocontent" in blob  # the id is logged
    assert "απορρητο" not in blob  # the token text is not


# ── default is silent ─────────────────────────────────────────────────────────
def test_default_no_opt_in_is_silent(monkeypatch, capsys):
    _clean_default_state(monkeypatch)
    log = _log.get_logger("data")
    log.info("should be filtered")
    log.warning("should not reach stderr")  # only the NullHandler, no stream output
    out, err = capsys.readouterr()
    assert out == ""
    assert err == ""
    assert _log._opt_in_handler is None


# ── PYAEGEAN_LOG env honored at first use ─────────────────────────────────────
def test_env_var_turns_logging_on(monkeypatch):
    _clean_default_state(monkeypatch)
    monkeypatch.setenv("PYAEGEAN_LOG", "info")
    _log._env_applied = False  # simulate first use with the env set
    _log.get_logger("data")  # first logger request consults the env
    assert _log._root.level == logging.INFO
    assert _log._opt_in_handler is not None


def test_env_var_garbage_is_ignored(monkeypatch):
    _clean_default_state(monkeypatch)
    monkeypatch.setenv("PYAEGEAN_LOG", "louder-please")
    _log._env_applied = False
    _log.get_logger("data")  # must not raise on a bad env value
    assert _log._root.level == logging.NOTSET  # unchanged
    assert _log._opt_in_handler is None


# ── adversarial: bad level → clean ValueError naming valid levels ─────────────
def test_garbage_level_string_raises_naming_valid_levels():
    with pytest.raises(ValueError) as excinfo:
        aegean.set_verbosity("loud")
    msg = str(excinfo.value)
    for name in ("debug", "info", "warning"):
        assert name in msg


def test_bool_level_rejected():
    # bool is an int subclass; a stray True must not silently become level 1.
    with pytest.raises(ValueError):
        aegean.set_verbosity(True)


def test_non_string_non_int_level_rejected():
    with pytest.raises(ValueError):
        aegean.set_verbosity(3.5)  # type: ignore[arg-type]


def test_set_verbosity_is_exported():
    assert aegean.set_verbosity is _log.set_verbosity
    assert "set_verbosity" in aegean.__all__
