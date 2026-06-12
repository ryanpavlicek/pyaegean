"""The grounded-generation eval harness: scoring logic + end-to-end with stubs."""

from __future__ import annotations

from aegean import ai
from aegean.ai.client import LLMClient, LLMResponse
from aegean.ai.eval import CaseResult, EvalReport, GroundingCase, run_eval, score_text


class ScriptedClient(LLMClient):
    """Answers from a {needle: reply} table, matched against the prompt; else a
    default. Lets a test simulate a faithful vs a fabricating model."""

    provider = "scripted"

    def __init__(self, replies=None, default="(no answer)", model="s-1", **kw):
        super().__init__(model, **kw)
        self.replies = replies or {}
        self.default = default

    def _complete(self, *, prompt, system, max_tokens):
        for needle, reply in self.replies.items():
            if needle in prompt:
                return LLMResponse(reply, self.provider, self.model)
        return LLMResponse(self.default, self.provider, self.model)


# ── scoring ──────────────────────────────────────────────────────────────────


def test_score_text_grounded_and_clean():
    case = GroundingCase(
        name="c", prompt="?", must_use=("total", "account"), must_avoid=("deciphered",)
    )
    r = score_text("This is likely a TOTAL of the ACCOUNT entries.", case)
    assert isinstance(r, CaseResult)
    assert set(r.used) == {"total", "account"} and r.missing == ()
    assert r.groundedness == 1.0 and r.clean is True


def test_score_text_partial_and_fabricated():
    case = GroundingCase(
        name="c", prompt="?", must_use=("total", "account"), must_avoid=("deciphered",)
    )
    r = score_text("It is now fully DECIPHERED as a total.", case)
    assert r.used == ("total",) and r.missing == ("account",)
    assert r.groundedness == 0.5
    assert r.fabricated == ("deciphered",) and r.clean is False


def test_score_text_no_requirements_is_grounded():
    r = score_text("anything", GroundingCase(name="c", prompt="?"))
    assert r.groundedness == 1.0 and r.clean is True


# ── run_eval end to end ──────────────────────────────────────────────────────


def test_run_eval_faithful_vs_fabricating():
    cases = (
        GroundingCase(
            name="gloss", prompt="What does λόγος mean?", kind="ask",
            grounding=("λόγος: reckoning, word",),
            must_use=("reckoning",), must_avoid=("fish",),
        ),
        GroundingCase(
            name="decline", prompt="Etymology of A-DU?", kind="ask",
            must_use=("insufficient",), must_avoid=("Proto-Indo-European",),
        ),
    )

    faithful = ScriptedClient(replies={
        "λόγος": "λόγος means reckoning or word.",
        "A-DU": "The evidence is insufficient to say.",
    })
    rep = run_eval(cases, faithful)
    assert isinstance(rep, EvalReport) and rep.n == 2
    assert rep.groundedness == 1.0 and rep.fabrication_rate == 0.0
    assert "groundedness 1.00" in rep.summary()

    fabricating = ScriptedClient(replies={
        "λόγος": "λόγος is a kind of fish.",
        "A-DU": "A-DU derives from Proto-Indo-European roots.",
    })
    rep2 = run_eval(cases, fabricating)
    assert rep2.groundedness == 0.0          # neither must_use referenced
    assert rep2.fabrication_rate == 1.0      # both fabricated


def test_default_cases_run_with_a_stub():
    # A stub that says nothing useful: groundedness low, but the harness runs.
    rep = run_eval(ai.DEFAULT_CASES, ScriptedClient(default="I am not sure."))
    assert rep.n == len(ai.DEFAULT_CASES)
    assert 0.0 <= rep.groundedness <= 1.0
    assert 0.0 <= rep.fabrication_rate <= 1.0


def test_default_cases_are_well_formed():
    for c in ai.DEFAULT_CASES:
        assert c.name and c.prompt and c.kind in {
            "ask", "decipher", "gloss", "summarize", "translate"
        }


# ── CLI ──────────────────────────────────────────────────────────────────────


def test_cli_eval_runs(monkeypatch):
    from typer.testing import CliRunner

    from aegean.ai import client as client_mod
    from aegean.cli import _build_app

    monkeypatch.setitem(client_mod._PROVIDERS, "scripted", ScriptedClient)
    runner = CliRunner()
    r = runner.invoke(_build_app(), ["ai", "eval", "--provider", "scripted", "--json"])
    assert r.exit_code == 0, r.output
    assert "groundedness" in r.output
