"""Tests for the `aegean greek eval` / `greek work` CLI fixes (r44):

* verse ``--drift`` is rejected up front, before any model activation;
* papygreek/nt reject the ud-only ``--bootstrap``/``--by-genre`` (no silent ignore);
* the ``--batch-size`` / ``--documentary`` / ``--track`` / ``--ref`` help strings match
  the guards they document;
* ``--documentary`` activates the paradigm table (Lever B) and restores the prior state;
* the ``greek work`` "read it:" hint only offers ``aegean show`` for a plain top-level
  textpart, and otherwise points at a ``load_work`` call carrying the FULL ref.

The eval guards are exercised with a stubbed ``_greek._activate`` that raises
``SystemExit('REACHED')`` — a guard that fires before it leaves the sentinel out of the
output, a guard that (correctly) does not fire lets ``REACHED`` through. No heavy work runs.
Assertions are on behaviour and plain-print text, never on rich table rendering width.

Plain-module test: imports only the stdlib, pytest, and the installed ``aegean`` package."""

from __future__ import annotations

import inspect

import pytest
from typer.testing import CliRunner


def _app():
    from aegean.cli import _build_app

    return _build_app()


@pytest.fixture()
def reached(monkeypatch):
    """Replace ``_greek._activate`` with a sentinel; ``'REACHED'`` in the output means
    execution passed the up-front guards and hit model activation."""
    from aegean.cli import _greek

    def _boom(**_kw: object) -> None:
        raise SystemExit("REACHED")

    monkeypatch.setattr(_greek, "_activate", _boom)
    return CliRunner()


# --- FIX 1: verse --drift is rejected before activation ----------------------------


def test_verse_drift_rejected_before_activate(reached) -> None:
    r = reached.invoke(_app(), ["greek", "eval", "verse", "--drift"])
    assert r.exit_code != 0, r.output
    assert "no --drift decomposition" in r.output
    # the whole point of the fix: activation is never reached
    assert "REACHED" not in r.output


# --- FIX 2: papygreek/nt reject the ud-only flags (no silent ignore) ----------------


@pytest.mark.parametrize("target", ["papygreek", "nt"])
@pytest.mark.parametrize("flag", ["--bootstrap", "--by-genre"])
def test_papygreek_nt_reject_ud_only_flags(reached, target: str, flag: str) -> None:
    r = reached.invoke(_app(), ["greek", "eval", target, flag])
    assert r.exit_code != 0, r.output
    assert "ud-only" in r.output
    assert f"`eval {target}`" in r.output
    # rejected up front — model activation not reached
    assert "REACHED" not in r.output


def test_valid_flag_combos_still_reach_activation(reached) -> None:
    # the guards must NOT over-reject: --drift on papygreek/nt, --documentary on papygreek,
    # and --bootstrap/--by-genre on ud all remain valid and must reach activation.
    for args in (
        ["greek", "eval", "papygreek", "--drift"],
        ["greek", "eval", "papygreek", "--documentary"],
        ["greek", "eval", "nt", "--drift"],
        ["greek", "eval", "verse", "--track", "tragedy"],
        ["greek", "eval", "ud", "--bootstrap"],
        ["greek", "eval", "ud", "--by-genre"],
    ):
        r = reached.invoke(_app(), args)
        assert "REACHED" in r.output, f"{args} should reach activation: {r.output}"


# --- FIX 3 + FIX 6a: help strings match the guards ---------------------------------


def _eval_help(name: str) -> str:
    return inspect.signature(_import_greek().evaluate).parameters[name].default.help


def _import_greek():
    from aegean.cli import _greek

    return _greek


def test_batch_size_help_lists_all_supported_targets() -> None:
    # the guard accepts ud/nt/papygreek/dbbe/verse; the help must name the two it omitted.
    help_text = _eval_help("batch_size")
    for token in ("ud", "nt", "papygreek", "dbbe", "verse"):
        assert token in help_text, help_text


def test_documentary_help_lists_supported_targets() -> None:
    # the guard accepts ud/nt/papygreek/verse (NOT dbbe): the help lists verse, omits dbbe.
    help_text = _eval_help("documentary")
    assert "verse" in help_text
    assert "dbbe" not in help_text


def test_track_help_drops_hexameter() -> None:
    help_text = _eval_help("track")
    assert "tragedy" in help_text and "all" in help_text
    assert "hexameter" not in help_text


# --- FIX 6b: the --ref Bekker gloss on `greek work` --------------------------------


def test_ref_help_carries_bekker_span_gloss() -> None:
    help_text = inspect.signature(_import_greek().work).parameters["ref"].default.help
    assert "1447a10" in help_text
    assert "span to the next marked line" in help_text


# --- FIX 4: --documentary activates the paradigm table and restores prior state ----


def _stub_documentary(monkeypatch, *, prior_active: bool):
    """Wire the documentary CLI path with no heavy work; return (state, calls).

    ``state['active_during']`` records whether the paradigm table was active while the
    (faked) scorer ran; ``calls`` counts the use/disable_paradigms invocations."""
    from aegean import greek
    from aegean.cli import _greek
    from aegean.greek import joint, paradigms

    state: dict[str, object] = {}
    calls = {"use": 0, "disable": 0}
    sentinel = object()

    monkeypatch.setattr(_greek, "_activate", lambda **_kw: None)  # never load a real model
    monkeypatch.setattr(joint, "active", lambda: sentinel)  # skip the inner neural activate
    monkeypatch.setattr(greek, "use_documentary_reconciliation", lambda **_kw: None)
    monkeypatch.setattr(greek, "use_documentary_lemma_rescue", lambda: None)
    monkeypatch.setattr(greek, "disable_documentary_reconciliation", lambda: None)
    monkeypatch.setattr(greek, "disable_documentary_lemma_rescue", lambda: None)
    # monkeypatch records/ restores the real module global; the stubs then drive it.
    monkeypatch.setattr(paradigms, "_ACTIVE", sentinel if prior_active else None)

    def _use(*_a: object, **_k: object) -> object:
        calls["use"] += 1
        paradigms._ACTIVE = sentinel
        return sentinel

    def _disable() -> None:
        calls["disable"] += 1
        paradigms._ACTIVE = None

    monkeypatch.setattr(greek, "use_paradigms", _use)
    monkeypatch.setattr(greek, "disable_paradigms", _disable)

    def _fake_eval(*, progress: object = None, batch_size: int | None = None) -> dict[str, float]:
        state["active_during"] = paradigms.active() is not None
        return {"upos": 0.9431, "lemma": 0.8636}

    monkeypatch.setattr(greek, "evaluate_on_papygreek", _fake_eval)
    return state, calls


def test_documentary_activates_paradigms_and_restores_off(monkeypatch) -> None:
    from aegean.greek import paradigms

    state, calls = _stub_documentary(monkeypatch, prior_active=False)
    r = CliRunner().invoke(_app(), ["greek", "eval", "papygreek", "--documentary", "--json"])
    assert r.exit_code == 0, r.output
    # paradigms were active while the scorer ran (Lever B needs the table)
    assert state["active_during"] is True
    assert calls["use"] == 1
    # prior state was off, so the run turned them back off
    assert calls["disable"] == 1
    assert paradigms.active() is None


def test_documentary_leaves_already_active_paradigms_on(monkeypatch) -> None:
    from aegean.greek import paradigms

    state, calls = _stub_documentary(monkeypatch, prior_active=True)
    r = CliRunner().invoke(_app(), ["greek", "eval", "papygreek", "--documentary", "--json"])
    assert r.exit_code == 0, r.output
    assert state["active_during"] is True
    # prior state was on: cleanup must NOT disable it
    assert calls["disable"] == 0
    assert paradigms.active() is not None


def test_non_documentary_run_never_touches_paradigms(monkeypatch) -> None:
    state, calls = _stub_documentary(monkeypatch, prior_active=False)
    r = CliRunner().invoke(_app(), ["greek", "eval", "papygreek", "--json"])
    assert r.exit_code == 0, r.output
    assert state["active_during"] is False  # scorer ran with paradigms off
    assert calls["use"] == 0 and calls["disable"] == 0


def test_documentary_failure_restores_every_state(monkeypatch) -> None:
    """A scorer/download failure must not poison the long-lived REPL session."""
    from unittest.mock import Mock

    from aegean import greek
    from aegean.greek import paradigms

    _state, calls = _stub_documentary(monkeypatch, prior_active=False)
    reconciliation_off = Mock()
    rescue_off = Mock()
    monkeypatch.setattr(greek, "disable_documentary_reconciliation", reconciliation_off)
    monkeypatch.setattr(greek, "disable_documentary_lemma_rescue", rescue_off)
    monkeypatch.setattr(
        greek,
        "evaluate_on_papygreek",
        lambda **_kw: (_ for _ in ()).throw(RuntimeError("scorer exploded")),
    )

    r = CliRunner().invoke(_app(), ["greek", "eval", "papygreek", "--documentary"])
    assert r.exit_code != 0 and isinstance(r.exception, RuntimeError)
    reconciliation_off.assert_called_once_with()
    rescue_off.assert_called_once_with()
    assert calls["disable"] == 1
    assert paradigms.active() is None


def test_documentary_run_preserves_preexisting_levers(monkeypatch) -> None:
    """An already-configured REPL session is restored exactly, not blindly disabled."""
    from unittest.mock import Mock

    from aegean import greek

    _stub_documentary(monkeypatch, prior_active=True)
    use_reconciliation = Mock()
    use_rescue = Mock()
    disable_reconciliation = Mock()
    disable_rescue = Mock()
    monkeypatch.setattr(greek, "documentary_reconciliation_active", lambda: True)
    monkeypatch.setattr(greek, "documentary_lemma_rescue_active", lambda: True)
    monkeypatch.setattr(greek, "use_documentary_reconciliation", use_reconciliation)
    monkeypatch.setattr(greek, "use_documentary_lemma_rescue", use_rescue)
    monkeypatch.setattr(greek, "disable_documentary_reconciliation", disable_reconciliation)
    monkeypatch.setattr(greek, "disable_documentary_lemma_rescue", disable_rescue)

    r = CliRunner().invoke(
        _app(), ["greek", "eval", "papygreek", "--documentary", "--json"]
    )
    assert r.exit_code == 0, r.output
    use_reconciliation.assert_not_called()
    use_rescue.assert_not_called()
    disable_reconciliation.assert_not_called()
    disable_rescue.assert_not_called()


# --- FIX 5: the `greek work` "read it:" hint ---------------------------------------


def _stub_work(monkeypatch):
    """Make ``greek work`` return a one-document corpus (no network); the doc id mirrors
    what ``load_work`` produces for the given ref."""
    from aegean.core import Corpus, Document, Token, TokenKind

    def _first_segment(ref: str | None) -> str:
        if ref is None:
            return "17"  # a whole-work load's first top-level textpart
        if "," in ref:
            return ref.split(",")[0]  # a comma list resolves to one doc per part
        return ref

    def _fake_load_work(work_id: str, *, ref: str | None = None, source: str = "auto",
                        edition: str | None = None) -> Corpus:
        seg = _first_segment(ref)
        tok = Token(text="λόγος", kind=TokenKind.WORD)
        doc = Document(id=f"{work_id}:{seg}", script_id="greek", tokens=[tok], lines=[[0]])
        return Corpus(documents=[doc])

    # `greek work` imports these from aegean.greek at call time
    from aegean import greek

    monkeypatch.setattr(greek, "load_work", _fake_load_work)
    monkeypatch.setattr(greek, "list_fetched_works", lambda: [])


def _read_it_line(output: str) -> str:
    for line in output.splitlines():
        if line.strip().startswith("read it:"):
            return line
    raise AssertionError(f"no 'read it:' line in output:\n{output}")


def test_hint_no_ref_uses_show(monkeypatch) -> None:
    _stub_work(monkeypatch)
    r = CliRunner().invoke(_app(), ["greek", "work", "tlg0059.tlg002"])
    assert r.exit_code == 0, r.output
    assert "aegean show tlg0059.tlg002 17" in _read_it_line(r.output)


def test_hint_bare_textpart_uses_show(monkeypatch) -> None:
    _stub_work(monkeypatch)
    r = CliRunner().invoke(_app(), ["greek", "work", "tlg0059.tlg002", "--ref", "18"])
    assert r.exit_code == 0, r.output
    assert "aegean show tlg0059.tlg002 18" in _read_it_line(r.output)


@pytest.mark.parametrize(
    ("work_id", "ref"),
    [
        ("tlg0059.tlg002", "17a"),      # Stephanus sub-page milestone
        ("tlg0086.tlg034", "1447a10"),  # Bekker page-relative line
        ("tlg0012.tlg001", "1.1-1.50"),  # verse line-range
    ],
)
def test_hint_complex_ref_uses_load_work(monkeypatch, work_id: str, ref: str) -> None:
    _stub_work(monkeypatch)
    r = CliRunner().invoke(_app(), ["greek", "work", work_id, "--ref", ref])
    assert r.exit_code == 0, r.output
    line = _read_it_line(r.output)
    # a milestone/range ref cannot be reconstructed by a whole-work `show`
    assert "aegean show" not in line
    assert f'load_work("{work_id}", ref="{ref}")' in line


def test_hint_comma_list_carries_full_ref(monkeypatch) -> None:
    _stub_work(monkeypatch)
    r = CliRunner().invoke(_app(), ["greek", "work", "tlg0059.tlg002", "--ref", "17,18"])
    assert r.exit_code == 0, r.output
    line = _read_it_line(r.output)
    # the whole comma list must survive, not just the first entry ("17")
    assert 'ref="17,18"' in line
    assert "aegean show" not in line


# --- the _bare_textpart classifier itself -----------------------------------------


def test_bare_textpart_classifier() -> None:
    from aegean.cli._greek import _bare_textpart

    assert _bare_textpart("1") is True
    assert _bare_textpart("18") is True
    assert _bare_textpart("17a") is False       # milestone (a letter)
    assert _bare_textpart("1447a10") is False    # Bekker (letters)
    assert _bare_textpart("1.2") is False        # nested (a dot)
    assert _bare_textpart("1.1-1.50") is False   # range (dot + hyphen)
    assert _bare_textpart("17,18") is False      # sibling list (a comma)
