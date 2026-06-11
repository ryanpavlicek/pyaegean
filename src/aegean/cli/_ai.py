"""The `aegean ai` group: the generative layer from the shell.

Every result here is **exploratory** — a labeled model hypothesis with its
grounding evidence, never a citable fact. Requires a provider SDK (an extra
such as ``pyaegean[anthropic]``) and its API key in the environment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ._common import JSON_OPT, console, emit_json, fail, load_corpus, read_text

if TYPE_CHECKING:
    from aegean.ai import GroundingItem

ai_app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help="Generative (exploratory, key-gated): translate, gloss, hypotheses, ask.",
    no_args_is_help=True,
)

PROVIDER_OPT = typer.Option(
    "anthropic", "--provider", help="anthropic, openai, grok, or gemini."
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


TRACE_OPT = typer.Option(False, "--trace", help="Print the grounding provenance trace.")


@ai_app.command()
def translate(
    text: str = typer.Argument(..., help="Text to translate ('-' reads stdin)."),
    script: str = typer.Option("greek", "--script", help="greek or lineara."),
    target: str = typer.Option("English", "--target", help="Target language."),
    provider: str = PROVIDER_OPT,
    model: str | None = MODEL_OPT,
    trace: bool = TRACE_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Hybrid translation: local lexicon/transliteration grounding → LLM (exploratory)."""
    from aegean import translate as tr

    client = _client(provider, model)
    result = _run(
        lambda: tr.translate(read_text(text), script=script, target=target, client=client)  # type: ignore[arg-type]
    )
    _emit_result(result, json_out, trace)


@ai_app.command()
def gloss(
    text: str = typer.Argument(..., help="Text to gloss word-by-word ('-' reads stdin)."),
    source: str = typer.Option("Ancient Greek", "--source", help="Source language label."),
    provider: str = PROVIDER_OPT,
    model: str | None = MODEL_OPT,
    trace: bool = TRACE_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Interlinear word-by-word gloss (exploratory)."""
    from aegean import ai

    client = _client(provider, model)
    result = _run(lambda: ai.gloss(read_text(text), source=source, client=client))  # type: ignore[arg-type]
    _emit_result(result, json_out, trace)


@ai_app.command()
def hypotheses(
    text: str = typer.Argument(..., help="An undeciphered (Linear A) sequence."),
    corpus: str | None = typer.Option(
        None, "--corpus", help="Ground on this corpus's frequent words (e.g. lineara)."
    ),
    provider: str = PROVIDER_OPT,
    model: str | None = MODEL_OPT,
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
    _emit_result(result, json_out, trace)


@ai_app.command()
def ask(
    question: str = typer.Argument(..., help="A question to answer over corpus grounding."),
    corpus: str | None = typer.Option(
        None, "--corpus", help="Ground on this corpus's frequent words."
    ),
    provider: str = PROVIDER_OPT,
    model: str | None = MODEL_OPT,
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
    _emit_result(result, json_out, trace)


@ai_app.command()
def providers(json_out: bool = JSON_OPT) -> None:
    """List the registered AI providers."""
    from aegean import ai

    names = sorted(ai.list_providers())
    if json_out:
        emit_json(names)
    else:
        print("\n".join(names))
