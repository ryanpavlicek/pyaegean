"""Structural drift guards for the browser demo (docs/demo/).

``index.html`` installs pyaegean through ``micropip.install("pyaegean")`` with no version
pin, so the published page runs the repository's ``demo.py`` against the wheel released on
PyPI. ``tests/test_web_demo.py`` runs that same module against this working tree. They are
two different libraries, and only the released one is what a visitor executes.

Two guards close the gap:

* ``test_released_wheel_runs_every_card_default`` installs the released wheel into a
  throwaway virtual environment and calls every card's default input through it. It needs
  the network, so it carries the ``released_wheel`` marker and runs in its own CI cell.
* ``test_every_card_default_input_is_real`` and ``test_every_label_code_suggestion_is_real``
  take the page's own default values and the ``<code>`` suggestions in its labels and call
  them against the working tree. They run in the ordinary suite, offline.

Both read the card-to-function mapping out of ``index.html`` itself, from the ``data-tool``
buttons and the JavaScript ``handlers`` map, so a new card is covered without being listed
here.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from html.parser import HTMLParser
from itertools import product
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator

import pytest

_DEMO_DIR = Path(__file__).resolve().parents[1] / "docs" / "demo"

# A <code> element inside a card's label is read as a value to type unless something says
# otherwise. The form rules below cover markup, call expressions, dotted identifiers, CLI
# lines and bare notation; a code whose form is indistinguishable from a real input is
# listed here with the reason it is prose.
_NOT_AN_INPUT: dict[tuple[str, str], str] = {
    ("bal", "KU-RO"): "names the accounting marker the card reconciles, not a tablet id",
    ("ser", "Haghia Triada"): (
        "1,110 Linear A tablets: the label names it as the site to seriate from the "
        "installed package rather than in the browser, so it is never called here"
    ),
}

# Coverage the extraction must reach. A rule that stopped recognising suggestions would
# otherwise leave the guard green with nothing left to check.
_MIN_SUGGESTIONS = 40
_MIN_CARDS_WITH_SUGGESTIONS = 15

_TEXTAREA = re.compile(r"(<textarea\b[^>]*>)(.*?)(</textarea>)", re.S)
_HANDLER_KEY = re.compile(r"^\s*(\w+):\s*\(\)\s*=>", re.M)


def _prose_reason(text: str) -> str | None:
    """Why a ``<code>`` element is prose rather than a value to type, or ``None``."""
    if "<" in text or ">" in text:
        return "a markup tag name"
    if "(" in text:
        return "a call expression"
    if re.match(r"^\w+\.\w", text):
        return "a dotted Python identifier"
    if re.match(r"^aegean(\s|$)", text):
        return "a CLI invocation"
    if len(text) == 1 and not text.isalnum():
        return "a bare notation character"
    return None


@dataclass
class _Field:
    """One input a card's handler reads: a text box, a dropdown, or a checkbox."""

    id: str
    kind: str
    default: Any
    options: tuple[str, ...] = ()


@dataclass
class _Card:
    tool: str
    function: str
    fields: list[_Field]
    suggestions: list[str] = field(default_factory=list)
    prose: list[tuple[str, str]] = field(default_factory=list)

    @property
    def defaults(self) -> tuple[Any, ...]:
        return tuple(f.default for f in self.fields)

    def candidate_args(self, value: str) -> Iterator[tuple[Any, ...]]:
        """Argument tuples that offer ``value`` to one of the card's own inputs.

        The value goes into each field in turn, text boxes first, with the card's other
        dropdowns ranging over their options: the bridge card reads a Cypriot word only
        when its script dropdown is on Cypriot, and the citation card takes a corpus id in
        its dropdown rather than in its site box.
        """
        seen: set[tuple[Any, ...]] = set()
        positions = [i for i, f in enumerate(self.fields) if f.kind == "text"]
        positions += [i for i, f in enumerate(self.fields) if f.kind == "select"]
        for at in positions:
            others = [i for i, f in enumerate(self.fields) if f.kind == "select" and i != at]
            for combo in product(*[self.fields[i].options for i in others]):
                args = list(self.defaults)
                args[at] = value
                for i, option in zip(others, combo):
                    args[i] = option
                key = tuple(args)
                if key not in seen:
                    seen.add(key)
                    yield key


class _CardParser(HTMLParser):
    """Collect each ``div.card``'s inputs, its labels' ``<code>`` elements, and its tool."""

    def __init__(self, textareas: dict[str, str]) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[dict[str, Any]] = []
        self._textareas = textareas
        self._depth = 0
        self._card: dict[str, Any] | None = None
        self._label: dict[str, Any] | None = None
        self._code: list[str] | None = None
        self._select: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "div":
            if self._card is not None:
                self._depth += 1
            elif "card" in a.get("class", "").split():
                self._card = {"fields": {}, "labels": [], "tool": None}
                self._depth = 1
                return
        if self._card is None:
            return
        if tag == "input" and a.get("id"):
            checkbox = a.get("type") == "checkbox"
            self._card["fields"][a["id"]] = _Field(
                a["id"],
                "checkbox" if checkbox else "text",
                "checked" in a if checkbox else a.get("value", ""),
            )
        elif tag == "textarea" and a.get("id"):
            self._card["fields"][a["id"]] = _Field(a["id"], "text", self._textareas[a["id"]])
        elif tag == "select" and a.get("id"):
            self._select = a["id"]
            self._card["fields"][a["id"]] = _Field(a["id"], "select", None)
        elif tag == "option" and self._select:
            f = self._card["fields"][self._select]
            f.options = (*f.options, a.get("value", ""))
            if f.default is None or "selected" in a:
                f.default = a.get("value", "")
        elif tag == "label":
            self._label = {"for": a.get("for"), "codes": []}
        elif tag == "code" and self._label is not None:
            self._code = []
        elif tag == "button" and a.get("data-tool"):
            self._card["tool"] = a["data-tool"]

    def handle_data(self, data: str) -> None:
        if self._code is not None:
            self._code.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._card is None:
            return
        if tag == "code" and self._code is not None:
            assert self._label is not None
            self._label["codes"].append("".join(self._code).strip())
            self._code = None
        elif tag == "label" and self._label is not None:
            self._card["labels"].append(self._label)
            self._label = None
        elif tag == "select":
            self._select = None
        elif tag == "div":
            self._depth -= 1
            if self._depth == 0:
                self.cards.append(self._card)
                self._card = None


def _handler_calls(html: str) -> dict[str, tuple[str, list[str]]]:
    """Map each ``data-tool`` name to the demo function its handler calls, and that call's
    argument expressions, read out of the page's ``handlers`` object."""
    script = html[html.index("const handlers = {"):]
    keys = [(m.start(), m.group(1)) for m in _HANDLER_KEY.finditer(script)]
    calls: dict[str, tuple[str, list[str]]] = {}
    for m in re.finditer(r'call\("(\w+)"', script):
        opened = script.index("(", m.start())
        depth, end = 1, opened + 1
        while depth:
            depth += {"(": 1, ")": -1}.get(script[end], 0)
            end += 1
        args: list[str] = []
        buf: list[str] = []
        nested = 0
        for ch in script[opened + 1:end - 1]:
            nested += {"(": 1, ")": -1}.get(ch, 0)
            if ch == "," and nested == 0:
                args.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
        if "".join(buf).strip():
            args.append("".join(buf).strip())
        owner = [name for at, name in keys if at < m.start()][-1]
        calls[owner] = (m.group(1), args[1:])
    return calls


def _textarea_defaults(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _TEXTAREA.finditer(html):
        ident = re.search(r'id="(\w+)"', m.group(1))
        assert ident, f"textarea without an id: {m.group(1)!r}"
        out[ident.group(1)] = m.group(2)
    return out


@lru_cache(maxsize=1)
def _cards() -> tuple[_Card, ...]:
    html = (_DEMO_DIR / "index.html").read_text(encoding="utf-8")
    # A textarea holds literal markup (the EpiDoc card's TEI sample). Those tags would read
    # as page structure, so the body is taken verbatim and the element emptied for parsing.
    parser = _CardParser(_textarea_defaults(html))
    parser.feed(_TEXTAREA.sub(lambda m: m.group(1) + m.group(3), html))
    handlers = _handler_calls(html)
    cards: list[_Card] = []
    for raw in parser.cards:
        tool = raw["tool"]
        if tool is None:
            continue
        function, arg_exprs = handlers[tool]
        fields: list[_Field] = []
        for expr in arg_exprs:
            m = re.fullmatch(r'val\("(\w+)"\)', expr) or re.fullmatch(
                r'document\.getElementById\("(\w+)"\)\.checked', expr
            )
            assert m, f"{tool}: unrecognised handler argument {expr!r}"
            fields.append(raw["fields"][m.group(1)])
        card = _Card(tool, function, fields)
        typed = {f.id for f in fields if f.kind == "text"}
        for label in raw["labels"]:
            # Only a label bound to a box the visitor types into offers typed input: a
            # dropdown-only card's <code> elements are the option names it displays.
            bound = label["for"] in typed
            for code in label["codes"]:
                why = (
                    "the label is bound to no typed field"
                    if not bound
                    else _NOT_AN_INPUT.get((tool, code)) or _prose_reason(code)
                )
                if why:
                    card.prose.append((code, why))
                else:
                    card.suggestions.append(code)
        cards.append(card)
    return tuple(cards)


@lru_cache(maxsize=1)
def _demo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_pyaegean_demo_drift", _DEMO_DIR / "demo.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _payload_error(payload: Any) -> str | None:
    return payload["error"] if isinstance(payload, dict) and "error" in payload else None


# ------------------------------------------------------------------ the page's own inputs


def test_every_card_is_extracted() -> None:
    """The extraction sees every card on the page and resolves each to a demo function."""
    html = (_DEMO_DIR / "index.html").read_text(encoding="utf-8")
    cards = _cards()
    buttons = html.count('data-tool="')
    assert len(cards) == buttons, (
        f"the page has {buttons} tool buttons but {len(cards)} were extracted: "
        f"{sorted(c.tool for c in cards)}"
    )
    assert len(cards) == len({c.tool for c in cards}), "two cards share one tool name"
    demo = _demo()
    for card in cards:
        assert card.fields, f"{card.tool}: no inputs resolved"
        assert callable(getattr(demo, card.function))


def test_every_card_default_input_is_real() -> None:
    """Every card's shipped default value produces a result, not an error payload: this is
    what a visitor gets by pressing the button without typing anything."""
    demo = _demo()
    failures = []
    for card in _cards():
        try:
            payload = json.loads(getattr(demo, card.function)(*card.defaults))
        except Exception as exc:
            failures.append(f"{card.tool}: {card.function}{card.defaults} raised {exc!r}")
            continue
        err = _payload_error(payload)
        if err:
            failures.append(f"{card.tool}: {card.function}{card.defaults} -> error: {err}")
    assert not failures, "card defaults that do not work:\n" + "\n".join(failures)


def test_every_label_code_suggestion_is_real() -> None:
    """Every value a card's label offers in ``<code>`` is accepted by one of that card's own
    inputs, so a label cannot suggest something the demo refuses."""
    demo = _demo()
    cards = _cards()
    exercised = 0
    failures = []
    # Exploratory analyses disclose their caveats by warning (the seriation card does so for
    # a site whose similarity leaves the axis partly undetermined). The subject here is the
    # returned payload, so those disclosures are not this test's output.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for card in cards:
            for suggestion in card.suggestions:
                attempts: list[Any] = []
                accepted = False
                for args in card.candidate_args(suggestion):
                    attempts.append(args)
                    try:
                        payload = json.loads(getattr(demo, card.function)(*args))
                    except Exception as exc:
                        attempts[-1] = f"{args} raised {exc!r}"
                        continue
                    if _payload_error(payload) is None:
                        accepted = True
                        break
                exercised += 1
                if not accepted:
                    failures.append(
                        f"{card.tool}: {suggestion!r} refused by {card.function}{attempts}"
                    )
    assert not failures, "label suggestions no card input accepts:\n" + "\n".join(failures)
    assert exercised >= _MIN_SUGGESTIONS, f"only {exercised} suggestions were recognised"
    with_suggestions = sum(1 for c in cards if c.suggestions)
    assert with_suggestions >= _MIN_CARDS_WITH_SUGGESTIONS, (
        f"only {with_suggestions} cards contributed a suggestion"
    )


def test_code_elements_skipped_as_prose_stay_accurate() -> None:
    """The two page-specific skips still describe the page.

    The accounting card names ``KU-RO`` in prose, so that skip has to stay live: were the
    label to stop mentioning it, the entry would be stale. The seriation card marks up no
    Haghia Triada suggestion at all: its 1,110 Linear A tablets are a workload its label
    directs to the installed package, and offering it in ``<code>`` would read as something
    to type into the browser.
    """
    skipped = {(c.tool, code): why for c in _cards() for code, why in c.prose}
    assert ("bal", "KU-RO") in skipped, (
        "the accounting card no longer names KU-RO in its label, so its _NOT_AN_INPUT "
        "entry is stale"
    )
    assert skipped[("bal", "KU-RO")] == _NOT_AN_INPUT[("bal", "KU-RO")]
    seriation = next(c for c in _cards() if c.tool == "ser")
    offered = set(seriation.suggestions) | {code for code, _ in seriation.prose}
    assert "Haghia Triada" not in offered, (
        "the seriation card offers Haghia Triada as a value to type; it is 1,110 tablets, "
        "which the label directs to the installed package"
    )


# ----------------------------------------------------------- the wheel the page installs


# pip failures that mean the index could not be reached. A reachable index with no
# pyaegean on it is a finding, not a skip, so "no matching distribution" is absent here:
# a blocked or unroutable index reports one of these first.
_INDEX_UNREACHABLE = (
    "temporary failure in name resolution",
    "connection",
    "network is unreachable",
    "read timed out",
    "retries exceeded",
    "proxyerror",
    "sslerror",
    "certificate_verify_failed",
)

_DRIVER = '''
import importlib.util, json, sys
from importlib.metadata import version

demo_path, calls_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
import aegean

spec = importlib.util.spec_from_file_location("_released_demo", demo_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
with open(calls_path, encoding="utf-8") as fh:
    calls = json.load(fh)
out = {"aegean_file": aegean.__file__, "version": version("pyaegean"), "calls": []}
for name, args in calls:
    record = {"function": name, "args": args}
    try:
        payload = json.loads(getattr(mod, name)(*args))
    except BaseException as exc:
        record["failure"] = "raised %s: %s" % (type(exc).__name__, exc)
    else:
        if isinstance(payload, dict) and "error" in payload:
            record["failure"] = "error payload: %s" % (payload["error"],)
    out["calls"].append(record)
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False)
'''


def _venv_python(root: Path) -> Path:
    windows = root / "Scripts" / "python.exe"
    return windows if windows.exists() else root / "bin" / "python"


@pytest.mark.released_wheel
def test_released_wheel_runs_every_card_default(tmp_path: Path) -> None:
    """The demo's own defaults work against the pyaegean wheel published on PyPI.

    The published page pins no version, so that wheel is the library a visitor's browser
    runs. A card written against an API only this working tree has would print a raw
    exception on the public page while every offline test stayed green.
    """
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONUTF8"] = "1"
    venv = tmp_path / "released"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True)
    python = _venv_python(venv)
    assert python.exists(), f"no interpreter in the throwaway environment at {venv}"

    install = subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
         "pyaegean"],
        capture_output=True, text=True, env=env, cwd=tmp_path, timeout=900,
    )
    if install.returncode != 0:
        blob = (install.stdout + install.stderr).lower()
        if any(marker in blob for marker in _INDEX_UNREACHABLE):
            pytest.skip("PyPI is unreachable, so the released wheel cannot be tested: "
                        + blob[-400:])
        raise AssertionError(
            f"installing pyaegean from PyPI failed:\n{install.stdout}\n{install.stderr}"
        )

    calls = [[c.function, list(c.defaults)] for c in _cards()]
    calls_path, out_path = tmp_path / "calls.json", tmp_path / "results.json"
    calls_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")
    driver = tmp_path / "driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")

    run = subprocess.run(
        [str(python), str(driver), str(_DEMO_DIR / "demo.py"), str(calls_path), str(out_path)],
        capture_output=True, text=True, env=env, cwd=tmp_path, timeout=1800,
    )
    assert run.returncode == 0, f"the demo could not run under the released wheel:\n{run.stderr}"

    results = json.loads(out_path.read_text(encoding="utf-8"))
    print(f"docs/demo/demo.py checked against released pyaegean {results['version']}")
    assert Path(results["aegean_file"]).is_relative_to(venv), (
        f"the released wheel was shadowed by {results['aegean_file']}"
    )
    assert len(results["calls"]) == len(calls)
    failures = [
        f"{c['function']}{tuple(c['args'])} -> {c['failure']}"
        for c in results["calls"]
        if "failure" in c
    ]
    assert not failures, (
        f"cards that break on released pyaegean {results['version']}, "
        "the version the published page installs:\n" + "\n".join(failures)
    )
