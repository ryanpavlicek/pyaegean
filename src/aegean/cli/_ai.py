"""The `aegean ai` group: the generative layer from the shell.

Every result here is **exploratory** — a labeled model hypothesis with its
grounding evidence, never a citable fact. Requires a provider SDK (an extra
such as ``pyaegean[anthropic]``) and, for a hosted provider, its API key in
the environment (the ``local`` provider needs a running local server, no key).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

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
    help="Generative (exploratory; API key per hosted provider, none for local): translate, gloss, summarize, hypotheses, ask, extract, eval, providers.",
    no_args_is_help=True,
)

PROVIDER_OPT = typer.Option(
    "anthropic", "--provider",
    help="anthropic, openai, grok, gemini, openrouter, or local (Ollama/LM Studio/llama.cpp).",
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


def _write_ai_result(result: object, output: Path, *, trace: bool = False) -> None:
    """Save an exploratory AI result: ``.json`` (text + provenance + grounding + parsed data,
    keeping the exploratory flag) or ``.txt`` (the labeled text). Translation text
    exports append the audit trace so concise output cannot discard saved notes
    or drafts. Never drops the label."""
    from aegean._atomic import atomic_path

    suffix = output.suffix.lower()
    if suffix == ".json":
        to_dict = getattr(result, "to_dict", None)
        payload = to_dict() if callable(to_dict) else {"text": getattr(result, "text", str(result))}
        with writing(output):
            with atomic_path(output) as tmp:
                tmp.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
    elif suffix in (".txt", ""):
        labeled = getattr(result, "labeled", None)
        text = labeled() if callable(labeled) else getattr(result, "text", str(result))
        trace_fn = getattr(result, "trace", None)
        data = getattr(result, "data", None)
        translation_audit = (
            getattr(result, "kind", "") == "translate"
            and isinstance(data, dict) and "format_status" in data
        )
        if (trace or translation_audit) and callable(trace_fn):
            text += "\n\n" + trace_fn()
        with writing(output):
            with atomic_path(output) as tmp:
                tmp.write_text(text + "\n", encoding="utf-8")
    else:
        raise fail(f"AI --output {output.name!r}: use a .json or .txt extension")


def _warn(message: str) -> None:
    """One dim line to stderr — the CLI's warning surface (stdout stays clean for --json)."""
    from rich.console import Console

    Console(stderr=True).print(f"aegean: {message}", style="dim", markup=False, highlight=False)


AI_OUTPUT_OPT = typer.Option(
    None, "--output", "-o",
    help="Save the result (.json: complete structured result; .txt: labeled text, "
    "including the audit trace for translations).",
)

TRACE_OPT = typer.Option(False, "--trace", help="Print the grounding provenance trace.")


def _read_source_context(inline: str | None, path: Path | None) -> str | None:
    """Read optional source context before activating analysis or a provider."""
    if inline is not None and path is not None:
        raise fail("--source-context and --source-context-file are mutually exclusive")
    context = inline
    if path is not None:
        try:
            # Preserve source line endings; the BOM is a file encoding signature.
            with path.open(encoding="utf-8-sig", newline="") as stream:
                context = stream.read()
        except UnicodeError:
            raise fail(f"source context file {path} must be UTF-8") from None
        except OSError as exc:
            raise fail(f"could not read source context file {path}: {exc}") from None
    return context


@contextmanager
def _translation_dictionaries(names: list[str]) -> Iterator[None]:
    """Scope explicit activation to one command, including an interactive REPL."""
    if not names:
        yield
        return
    from aegean.greek import koine, lexicon, lexicons

    previous = dict(lexicons._ACTIVE)
    previous_lsj, previous_dodson = lexicon.active(), koine.active()
    try:
        for name in dict.fromkeys(names):
            try:
                lexicons.use_lexicon(name)
            except Exception as exc:
                raise fail(f"could not activate dictionary {name!r}: {exc}") from None
        yield
    finally:
        lexicons._ACTIVE.clear()
        lexicons._ACTIVE.update(previous)
        lexicon._ACTIVE, koine._ACTIVE = previous_lsj, previous_dodson


@ai_app.command()
def translate(
    text: str = typer.Argument(..., help="Text to translate ('-' reads stdin)."),
    script: str = typer.Option("greek", "--script", help="greek or lineara."),
    target: str = typer.Option("English", "--target", help="Target language."),
    source_context: str | None = typer.Option(
        None, "--source-context",
        help="Source context supplied as text (edition, genre, speaker or surrounding passage).",
    ),
    source_context_file: Path | None = typer.Option(
        None, "--source-context-file",
        help="Read source context from a UTF-8 file; mutually exclusive with --source-context.",
    ),
    max_tokens: int = typer.Option(
        2048, "--max-tokens", min=1,
        help="Output-token limit for each translation or checking call (default: 2048).",
    ),
    style: str = typer.Option(
        "annotated", "--style",
        help="annotated shows uncertainty and correction notes; concise keeps the reading "
        "short. JSON and --trace retain notes and the checking draft in either style.",
    ),
    mode: str = typer.Option(
        "morphology", "--mode",
        help="Greek grounding style: morphology (default; provisional morphology + "
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
        "grounding and repair only definite source contradictions. This second model "
        "call remains exploratory and is not scholarly verification.",
    ),
    check_policy: str = typer.Option(
        "standard", "--check-policy",
        help="standard or clauses; clauses requires --verify and retains explicit "
        "role, negation, qualification and speech-act checks with literal span validation.",
    ),
    lexical_evidence: str = typer.Option(
        "concise", "--lexical-evidence",
        help="concise or contextual; contextual selects bounded excerpts from active "
        "dictionaries. Requires Greek full/lemma mode (or --verify) and glosses.",
    ),
    dictionary: list[str] = typer.Option(
        [], "--dictionary",
        help="Activate a hosted dictionary for this command; repeat for several. "
        "May fetch its cache on first use. Requires Greek full/lemma mode or --verify, with glosses.",
    ),
    greek_backend: str = typer.Option(
        "default", "--greek-backend",
        help="Greek analysis owner: default (module facade), baseline (isolated "
        "zero-dependency), or neural (isolated grc-joint model; requires [neural]).",
    ),
    greek_variant: str = typer.Option(
        "default",
        "--greek-variant",
        help="For --greek-backend neural: default, fast, compact, or balanced. "
        "Reserved labels fail until a qualified artifact is released.",
    ),
    greek_long_input: str = typer.Option(
        "strict",
        "--greek-long-input",
        help="Greek neural long-input policy: strict, partial, or windowed.",
    ),
    grounding_failure: str = typer.Option(
        "best-effort", "--grounding-failure",
        help="Grounding failure policy: best-effort keeps available evidence; strict "
        "stops before a provider call when required local analysis fails.",
    ),
    provider: str = PROVIDER_OPT,
    model: str | None = MODEL_OPT,
    output: Path | None = AI_OUTPUT_OPT,
    trace: bool = TRACE_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Hybrid translation: local morphology/lexicon/transliteration grounding → LLM
    (exploratory). Morphology-first grounding supplies provisional token and clause
    analyses. Optional --verify (Greek) generates an ungrounded draft and checks
    it against that evidence. The draft, uncertainty and model-reported changes
    remain available through JSON or --trace; checking is not human review."""
    import warnings

    from aegean import translate as tr

    context = _read_source_context(source_context, source_context_file)
    context_options: dict[str, Any] = {"source_context": context} if context is not None else {}
    if style not in ("annotated", "concise"):
        raise fail("--style must be annotated or concise")
    if check_policy not in ("standard", "clauses"):
        raise fail("--check-policy must be standard or clauses")
    if check_policy == "clauses" and (not verify or script != "greek"):
        raise fail("--check-policy clauses requires --verify and --script greek")
    try:
        tr._validate_lexical_evidence(
            lexical_evidence, script=script,
            mode="full" if verify and script == "greek" else mode, glosses=glosses,
        )
    except ValueError as exc:
        raise fail(str(exc)) from None
    if greek_backend not in ("default", "baseline", "neural"):
        raise fail("--greek-backend must be default, baseline, or neural")
    if grounding_failure not in ("best-effort", "strict"):
        raise fail("--grounding-failure must be best-effort or strict")
    if greek_long_input not in ("strict", "partial", "windowed"):
        raise fail("--greek-long-input must be strict, partial, or windowed")
    if script == "greek" and not verify and mode not in ("morphology", "full", "lemma", "none"):
        raise fail("--mode must be morphology, full, lemma, or none")
    if script != "greek" and greek_backend != "default":
        raise fail("--greek-backend applies only to --script greek")
    if script != "greek" and greek_variant != "default":
        raise fail("--greek-variant applies only to --script greek")
    if greek_backend != "neural" and greek_variant != "default":
        raise fail("--greek-variant requires --greek-backend neural")
    if script != "greek" and greek_long_input != "strict":
        raise fail("--greek-long-input applies only to --script greek")

    if dictionary:
        from aegean.greek import lexicons

        if script != "greek" or not glosses or (not verify and mode not in ("full", "lemma")):
            raise fail("--dictionary requires Greek full/lemma mode or --verify, with glosses")
        hosted = {info.id for info in lexicons.lexica() if info.hosted}
        if any(name not in hosted for name in dictionary):
            raise fail("--dictionary must name a hosted dictionary: " + ", ".join(sorted(hosted)))

    with _translation_dictionaries(dictionary):
        greek_pipeline = None
        if greek_backend != "default":
            from aegean.greek import GreekPipeline

            if greek_backend == "baseline":
                greek_pipeline = GreekPipeline()
            else:
                try:
                    greek_pipeline = GreekPipeline.neural(variant=greek_variant)
                except Exception as exc:
                    raise fail(f"could not activate the neural Greek pipeline: {exc}") from None

        client = _client(provider, model)
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = _run(
                    lambda: tr.translate(
                        read_text(text), script=script, target=target,
                        max_tokens=max_tokens,
                        mode=cast(tr.GroundingMode, mode), glosses=glosses, verify=verify,
                        check_policy=check_policy,
                        lexical_evidence=cast(Literal["concise", "contextual"], lexical_evidence),
                        style=cast(Literal["annotated", "concise"], style),
                        greek_pipeline=greek_pipeline,
                        greek_long_input=cast(tr.GreekLongInput, greek_long_input),
                        grounding_failure=cast(tr.GroundingFailure, grounding_failure),
                        client=client,  # type: ignore[arg-type]
                        **context_options,
                    )
                )
        except (ValueError, tr.GroundingError) as exc:
            raise fail(str(exc)) from None
        for w in caught:  # e.g. the lemmatizer-quality note — surface it, not a raw UserWarning
            if issubclass(w.category, UserWarning):
                _warn(str(w.message))
        if output is not None:
            _write_ai_result(result, output, trace=trace)
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
