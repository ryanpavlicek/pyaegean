"""Command dictionary choices do not change later translations in the REPL."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from aegean import translate
from aegean.ai.client import LLMClient, LLMResponse, ProviderCallError
from aegean.cli import _ai, _build_app
from aegean.greek import GreekPipeline, koine, lexicon, lexicons
from aegean.greek.lemmatize import LemmaSource
from aegean.greek.lexicons import LexiconInfo
from aegean.greek.lexindex import IndexLexicon
from aegean.greek.pipeline import TokenRecord


_SOURCE = "λέγω"
_COMMAND = [
    "ai", "translate", _SOURCE, "--mode", "lemma",
    "--lexical-evidence", "contextual", "--json",
]


class _Client(LLMClient):
    provider = "dictionary-scope-fixture"

    def __init__(self):
        super().__init__("dictionary-scope-model")
        self.prompts: list[str] = []
        self.fail = False

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        self.prompts.append(prompt)
        if self.fail:
            raise ProviderCallError("fixture provider completion failed")
        return LLMResponse(
            json.dumps({"translation": "I speak.", "uncertainties": [], "changes": []}),
            self.provider, self.model,
        )


class _Pipeline(GreekPipeline):
    def analyze(self, text, *, parse=False, with_confidence=False, long_input="strict"):
        return [TokenRecord(
            sentence=0, index=1, text=_SOURCE, lemma=_SOURCE, upos="VERB",
            lemma_source=LemmaSource.ATTESTED,
        )]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(lexicons, "_ACTIVE", {})
    monkeypatch.setattr(lexicons, "_SPECS", {})
    monkeypatch.setattr(lexicon, "_ACTIVE", None)
    monkeypatch.setattr(koine, "_ACTIVE", None)
    pipeline = _Pipeline()
    monkeypatch.setattr(translate, "_selected_pipeline", lambda supplied: (pipeline, "explicit"))
    monkeypatch.setattr(translate, "_rich_lemmatizer_active", lambda supplied: True)
    instance = _Client()
    monkeypatch.setattr(_ai, "_client", lambda provider, model: instance)
    return instance


def _info(identifier):
    return LexiconInfo(identifier, identifier, "classical", "example", "Example edition", True)


def _index(identifier, body):
    return IndexLexicon(_info(identifier), {_SOURCE: {"hw": _SOURCE, "def": body}})


def _lsj(body):
    return lexicon.LSJLexicon({_SOURCE: {
        "hw": _SOURCE, "key": "le/gw", "lead": "", "short": body,
        "senses": [{"m": "I", "l": 1, "t": body}],
    }})


def _dodson(body):
    return koine.DodsonLexicon({"1": koine.DodsonEntry("1", _SOURCE, body, body)})


def _register_replacements():
    shared = _index("shared", "REPLACEMENT SHARED ENTRY")
    fresh = _index("fresh", "TEMPORARY NEW DICTIONARY ENTRY")
    lsj = _lsj("REPLACEMENT LSJ ENTRY")
    dodson = _dodson("REPLACEMENT DODSON ENTRY")

    def load_lsj():
        lexicon._ACTIVE = lsj
        return lexicons._LSJAdapter(lsj)

    def load_dodson():
        koine._ACTIVE = dodson
        return lexicons._DodsonAdapter(dodson)

    lexicons.register_lexicon(_info("shared"), lambda: shared)
    lexicons.register_lexicon(_info("fresh"), lambda: fresh)
    lexicons.register_lexicon(_info("lsj"), load_lsj)
    lexicons.register_lexicon(_info("dodson"), load_dodson)


def _seed_preexisting():
    lsj = _lsj("PREEXISTING LSJ ENTRY")
    dodson = _dodson("PREEXISTING DODSON ENTRY")
    lexicon._ACTIVE = lsj
    koine._ACTIVE = dodson
    registry = {
        "shared": _index("shared", "PREEXISTING SHARED ENTRY"),
        "lsj": lexicons._LSJAdapter(lsj),
        "dodson": lexicons._DodsonAdapter(dodson),
    }
    lexicons._ACTIVE.update(registry)
    return registry, lsj, dodson


def _assert_restored(previous):
    registry, lsj, dodson = previous
    assert lexicons._ACTIVE.keys() == registry.keys()
    assert all(lexicons._ACTIVE[name] is backend for name, backend in registry.items())
    assert lexicon.active() is lsj
    assert koine.active() is dodson


def test_repl_dictionary_option_affects_only_the_named_translation(client):
    _register_replacements()
    first = " ".join([*_COMMAND, "--dictionary", "fresh"])
    second = " ".join(_COMMAND)
    result = CliRunner().invoke(_build_app(), ["repl"], input=f"{first}\n{second}\n:exit\n")
    assert result.exit_code == 0, result.output
    assert len(client.prompts) == 2
    assert "TEMPORARY NEW DICTIONARY ENTRY" in client.prompts[0]
    assert "TEMPORARY NEW DICTIONARY ENTRY" not in client.prompts[1]
    assert '"no-active-dictionaries"' in result.output
    assert lexicons.active_lexica() == []
    assert lexicon.active() is None
    assert koine.active() is None


def test_dictionary_scope_restores_preexisting_entries_and_legacy_backends(client):
    previous = _seed_preexisting()
    _register_replacements()
    result = CliRunner().invoke(_build_app(), [
        *_COMMAND, "--dictionary", "shared", "--dictionary", "lsj",
        "--dictionary", "dodson", "--dictionary", "fresh",
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert {"lexicon:shared", "lexicon:lsj", "lexicon:dodson", "lexicon:fresh"} <= {
        item["source"] for item in payload["grounding"]
    }
    for marker in ["REPLACEMENT SHARED ENTRY", "REPLACEMENT LSJ ENTRY",
                   "REPLACEMENT DODSON ENTRY", "TEMPORARY NEW DICTIONARY ENTRY"]:
        assert marker in client.prompts[0]
    assert "PREEXISTING" not in client.prompts[0]
    _assert_restored(previous)
    following = CliRunner().invoke(_build_app(), _COMMAND)
    assert following.exit_code == 0, following.output
    assert "PREEXISTING SHARED ENTRY" in client.prompts[1]
    assert "PREEXISTING LSJ ENTRY" in client.prompts[1]
    assert "PREEXISTING DODSON ENTRY" in client.prompts[1]
    assert "REPLACEMENT" not in client.prompts[1]
    assert "TEMPORARY NEW DICTIONARY ENTRY" not in client.prompts[1]


@pytest.mark.parametrize("stage", ["activation", "construction", "completion", "output"])
def test_dictionary_scope_restores_state_after_command_failure(client, monkeypatch, tmp_path, stage):
    previous = _seed_preexisting()
    _register_replacements()
    arguments = [
        *_COMMAND, "--dictionary", "shared", "--dictionary", "lsj",
        "--dictionary", "dodson", "--dictionary", "fresh",
    ]
    if stage == "activation":
        def broken_loader():
            lexicon._ACTIVE = _lsj("FAILED LOADER LSJ")
            koine._ACTIVE = _dodson("FAILED LOADER DODSON")
            lexicons._ACTIVE["partially-loaded"] = _index("partially-loaded", "PARTIAL ENTRY")
            raise RuntimeError("fixture dictionary activation failed")

        lexicons.register_lexicon(_info("broken"), broken_loader)
        arguments.extend(["--dictionary", "broken"])
    elif stage == "construction":
        def unavailable(provider, model):
            raise _ai.fail("fixture provider construction failed")

        monkeypatch.setattr(_ai, "_client", unavailable)
    elif stage == "completion":
        client.fail = True
    else:
        arguments.extend(["--output", str(tmp_path / "untouched.invalid")])

    result = CliRunner().invoke(_build_app(), arguments)
    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    _assert_restored(previous)
    assert not list(tmp_path.iterdir())
    assert len(client.prompts) == (1 if stage in {"completion", "output"} else 0)
