"""The `aegean ai` group: the generative layer from the shell.

Every result here is **exploratory** — a labeled model hypothesis with its
grounding evidence, never a citable fact. Requires a provider SDK (an extra
such as ``pyaegean[anthropic]``) and its API key in the environment.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from ._common import (
    JSON_OPT,
    RESULT_OPT,
    console,
    emit_json,
    emit_result,
    fail,
    load_corpus,
    read_text,
    writing,
)

if TYPE_CHECKING:
    from aegean.ai import GroundingItem

ai_app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help="Generative (exploratory, key-gated): translate, gloss, summarize, hypotheses, ask, extract, eval, providers.",
    no_args_is_help=True,
)

PROVIDER_OPT = typer.Option(
    "anthropic", "--provider", help="anthropic, openai, grok, gemini, or openrouter."
)
MODEL_OPT = typer.Option(None, "--model", help="Provider model override.")


def _client(provider: str, model: str | None) -> object:
    from aegean import ai

    try:
        return ai.get_client(provider, model=model)
    except (ai.UnknownProvider, ai.ProviderNotInstalled, ai.MissingAPIKey) as exc:
        raise fail(str(exc)) from None


def _run(capability: "object") -> object:
    """Invoke a capability thunk, mapping the AI layer's errors to clean exits.

    Provider SDK/key problems surface lazily (at completion time), so the
    guard must wrap the call itself, not just client construction."""
    from aegean import ai

    try:
        return capability()  # type: ignore[operator]
    except (ai.AIError, ai.UnknownProvider, ai.ProviderNotInstalled, ai.MissingAPIKey) as exc:
        raise fail(str(exc)) from None


def _emit_result(result: object, json_out: bool, trace: bool = False) -> None:
    if json_out:
        emit_json(result)
        return
    labeled = getattr(result, "labeled", None)
    text = labeled() if callable(labeled) else getattr(result, "text", str(result))
    console().print(text, markup=False)
    if trace:
        trace_fn = getattr(result, "trace", None)
        if callable(trace_fn):
            console().print(trace_fn(), style="dim", markup=False)
            return
    provider = getattr(result, "provider", "")
    model = getattr(result, "model", "")
    grounding = getattr(result, "grounding", ())
    console().print(
        f"exploratory · {provider}:{model} · grounded on {len(grounding)} item(s) "
        "(--trace to audit them)",
        style="dim", markup=False,
    )


def _write_ai_result(result: object, output: Path) -> None:
    """Save an exploratory AI result: ``.json`` (text + provenance + grounding + parsed data,
    keeping the exploratory flag) or ``.txt`` (the labeled text). Never drops the label."""
    suffix = output.suffix.lower()
    if suffix == ".json":
        to_dict = getattr(result, "to_dict", None)
        payload = to_dict() if callable(to_dict) else {"text": getattr(result, "text", str(result))}
        with writing(output):
            output.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    elif suffix in (".txt", ""):
        labeled = getattr(result, "labeled", None)
        text = labeled() if callable(labeled) else getattr(result, "text", str(result))
        with writing(output):
            output.write_text(text + "\n", encoding="utf-8")
    else:
        raise fail(f"AI --output {output.name!r}: use a .json or .txt extension")


def _warn(message: str) -> None:
    """One dim line to stderr — the CLI's warning surface (stdout stays clean for --json)."""
    from rich.console import Console

    Console(stderr=True).print(f"aegean: {message}", style="dim", markup=False, highlight=False)


AI_OUTPUT_OPT = typer.Option(
    None, "--output", "-o",
    help="Save the result to a file (.json: text + provenance + grounding; .txt: labeled text).",
)

TRACE_OPT = typer.Option(False, "--trace", help="Print the grounding provenance trace.")


@ai_app.command()
def translate(
    text: str = typer.Argument(..., help="Text to translate ('-' reads stdin)."),
    script: str = typer.Option("greek", "--script", help="greek or lineara."),
    target: str = typer.Option("English", "--target", help="Target language."),
    mode: str = typer.Option(
        "morphology", "--mode",
        help="Greek grounding style: morphology (default; deterministic morphology + "
        "clause skeleton, no glosses), full (morphology + concise common-sense-first "
        "glosses, gated to rare words), lemma (legacy lemma lines + gated LSJ glosses), "
        "none.",
    ),
    glosses: bool = typer.Option(
        True, "--glosses/--no-glosses",
        help="Whether the gloss-bearing modes (full, lemma) add their glosses. "
        "Superseded by --mode; --no-glosses drops the glosses on those modes.",
    ),
    verify: bool = typer.Option(
        False, "--verify",
        help="Greek only: translate raw first, then check the draft against the full "
        "grounding and repair only definite errors. Catches more errors on hard text "
        "without letting the grounding bias the draft, at the cost of a second model call.",
    ),
    provider: str = PROVIDER_OPT,
    model: str | None = MODEL_OPT,
    output: Path | None = AI_OUTPUT_OPT,
    trace: bool = TRACE_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Hybrid translation: local morphology/lexicon/transliteration grounding → LLM
    (exploratory). The default morphology-first grounding gives the model deterministic
    morphology, case-role, and clause structure rather than auto-selected dictionary
    senses. With --verify (Greek), translate raw then check and repair against the
    grounding: the analysis cannot bias the draft, though a wrong analysis can still
    mislead the repair."""
    import warnings

    from aegean import translate as tr

    client = _client(provider, model)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = _run(
                lambda: tr.translate(
                    read_text(text), script=script, target=target,
                    mode=mode, glosses=glosses, verify=verify, client=client,  # type: ignore[arg-type]
                )
            )
    except ValueError as exc:  # unknown grounding mode, validated before any model call
        raise fail(str(exc)) from None
    for w in caught:  # e.g. the lemmatizer-quality note — surface it, not a raw UserWarning
        if issubclass(w.category, UserWarning):
            _warn(str(w.message))
    if output is not None:
        _write_ai_result(result, output)
        return
    _emit_result(result, json_out, trace)


@ai_app.command()
def gloss(
    text: str = typer.Argument(..., help="Text to gloss word-by-word ('-' reads stdin)."),
    source: str = typer.Option("Ancient Greek", "--source", help="Source language label."),
    provider: str = PROVIDER_OPT,
    model: str | None = MODEL_OPT,
    output: Path | None = AI_OUTPUT_OPT,
    trace: bool = TRACE_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Interlinear word-by-word gloss (exploratory)."""
    from aegean import ai

    client = _client(provider, model)
    result = _run(lambda: ai.gloss(read_text(text), source=source, client=client))  # type: ignore[arg-type]
    if output is not None:
        _write_ai_result(result, output)
        return
    _emit_result(result, json_out, trace)


@ai_app.command()
def summarize(
    text: str = typer.Argument(..., help="Text to summarize ('-' reads stdin)."),
    corpus: str | None = typer.Option(
        None, "--corpus", help="Ground on this corpus's frequent words for context."
    ),
    provider: str = PROVIDER_OPT,
    model: str | None = MODEL_OPT,
    output: Path | None = AI_OUTPUT_OPT,
    trace: bool = TRACE_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """A short, grounded summary of a passage (exploratory)."""
    from aegean import ai

    grounding: list[GroundingItem] = []
    if corpus:
        grounding = ai.corpus_context(load_corpus(corpus))
    client = _client(provider, model)
    result = _run(lambda: ai.summarize(read_text(text), grounding=grounding, client=client))  # type: ignore[arg-type]
    if output is not None:
        _write_ai_result(result, output)
        return
    _emit_result(result, json_out, trace)


@ai_app.command()
def hypotheses(
    text: str = typer.Argument(..., help="An undeciphered (Linear A) sequence ('-' reads stdin)."),
    corpus: str | None = typer.Option(
        None, "--corpus", help="Ground on this corpus's frequent words (e.g. lineara)."
    ),
    provider: str = PROVIDER_OPT,
    model: str | None = MODEL_OPT,
    output: Path | None = AI_OUTPUT_OPT,
    trace: bool = TRACE_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Cautious decipherment hypotheses for an undeciphered sequence (strictly exploratory)."""
    from aegean import ai

    grounding: list[GroundingItem] = []
    if corpus:
        grounding = ai.corpus_context(load_corpus(corpus))
    client = _client(provider, model)
    result = _run(
        lambda: ai.decipher_hypotheses(read_text(text), grounding=grounding, client=client)  # type: ignore[arg-type]
    )
    if output is not None:
        _write_ai_result(result, output)
        return
    _emit_result(result, json_out, trace)


@ai_app.command()
def ask(
    question: str = typer.Argument(
        ..., help="A question to answer over corpus grounding ('-' reads stdin)."
    ),
    corpus: str | None = typer.Option(
        None, "--corpus", help="Ground on this corpus's frequent words."
    ),
    provider: str = PROVIDER_OPT,
    model: str | None = MODEL_OPT,
    output: Path | None = AI_OUTPUT_OPT,
    trace: bool = TRACE_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Answer a question strictly from the provided grounding (exploratory)."""
    from aegean import ai

    grounding: list[GroundingItem] = []
    if corpus:
        grounding = ai.corpus_context(load_corpus(corpus))
    client = _client(provider, model)
    result = _run(lambda: ai.ask(read_text(question), grounding=grounding, client=client))  # type: ignore[arg-type]
    if output is not None:
        _write_ai_result(result, output)
        return
    _emit_result(result, json_out, trace)


@ai_app.command()
def extract(
    text: str = typer.Argument(..., help="Source to extract structured data from ('-' reads stdin)."),
    fields: str | None = typer.Option(
        None, "--fields", help="Comma-separated field names for the JSON object (e.g. lemma,pos,gloss)."
    ),
    instruction: str = typer.Option(
        "Extract the structured data from the following.", "--instruction", help="What to extract."
    ),
    corpus: str | None = typer.Option(None, "--corpus", help="Ground on this corpus's frequent words."),
    provider: str = PROVIDER_OPT,
    model: str | None = MODEL_OPT,
    output: Path | None = AI_OUTPUT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Structured (JSON) extraction — prints the parsed data, for piping into tools.

    `aegean ai extract "OLE S 1" --fields commodity,amount` → {"commodity": "OLE", …}.
    Exploratory: the extraction is a model hypothesis, not a verified parse."""
    from aegean import ai

    schema = {f.strip(): "" for f in fields.split(",") if f.strip()} if fields else None
    grounding: list[GroundingItem] = []
    if corpus:
        grounding = ai.corpus_context(load_corpus(corpus))
    client = _client(provider, model)
    result = _run(
        lambda: ai.extract(
            read_text(text), instruction=instruction, schema=schema,
            grounding=grounding, client=client,  # type: ignore[arg-type]
        )
    )
    data = getattr(result, "data", None)
    if output is not None:
        _write_ai_result(result, output)
        return
    if json_out:
        emit_json(data if data is not None else {"raw": getattr(result, "text", "")})
        return
    if data is not None:
        emit_json(data)  # structured output is JSON even in the default view
    else:
        console().print(getattr(result, "text", ""), markup=False)
        console().print("(could not parse JSON from the response)", style="dim", markup=False)


@ai_app.command()
def eval(
    provider: str = PROVIDER_OPT,
    model: str | None = MODEL_OPT,
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Grounded-generation eval: score the built-in cases for grounding fidelity.

    Measures how faithfully a provider uses its grounding — groundedness (does it
    reference the supplied evidence?) and fabrication rate (does it assert beyond
    it?). The AI layer's analogue of the lemmatizer's held-out accuracy."""
    from aegean import ai

    client = _client(provider, model)
    report = _run(lambda: ai.run_eval(ai.DEFAULT_CASES, client))  # type: ignore[arg-type]
    if emit_result(report, json_output=json_out, output=output):
        return
    from ._common import table

    console().print(getattr(report, "summary", lambda: "")(), markup=False)
    table(
        "grounded-generation cases",
        ["case", "grounded", "clean", "missing", "fabricated"],
        [
            [
                r.name, f"{r.groundedness:.2f}", "yes" if r.clean else "NO",
                ", ".join(r.missing) or "-", ", ".join(r.fabricated) or "-",
            ]
            for r in getattr(report, "cases", ())
        ],
    )


@ai_app.command()
def providers(json_out: bool = JSON_OPT) -> None:
    """List the registered AI providers."""
    from aegean import ai

    names = sorted(ai.list_providers())
    if json_out:
        emit_json(names)
    else:
        print("\n".join(names))
