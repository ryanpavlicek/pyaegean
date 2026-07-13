"""``aegean doctor`` — the one-command, offline environment check.

Answers "why doesn't X work" in one run: Python and pyaegean versions, which
optional extras are importable, the state of the local data store (location,
size, per-dataset download state, leftover partial downloads, writability),
whether the neural model bundles are downloaded, and the opt-in analysis
cache. Entirely offline: no network is touched and nothing is downloaded;
every reported value is measured live from the machine it runs on.

A missing optional extra is informational (reported with its install line),
never an issue: the zero-dependency core is a supported configuration. Issues
are things that break an advertised behavior — a Python below the 3.10 floor,
an unusable or unwritable data store, a leftover partial download.

The report itself is built by ``aegean._doctor.build_report`` (typer-free, so
the terminal UI can render the same report in a ``[tui]``-only environment);
this module adds the command registration and the rich rendering.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from .._doctor import build_report
from ._common import JSON_OPT, RESULT_OPT, emit_json, emit_result, fail, load_corpus, table, to_plain, writing


def register(app: typer.Typer) -> None:
    doctor_app = typer.Typer(no_args_is_help=False)
    doctor_app.callback(invoke_without_command=True)(doctor)
    doctor_app.command("corpus")(doctor_corpus)
    app.add_typer(doctor_app, name="doctor")


def doctor(
    ctx: typer.Context,
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Check the local environment: versions, extras, data store, models, cache.

    Entirely offline: no network is touched and nothing is downloaded; every
    value is measured live. Missing optional extras are informational (their
    install line is shown), not problems. Exits 0 when everything is healthy,
    1 when any issue was found; --json emits the whole report as one document.

    Use `aegean doctor corpus <id>` for a corpus health report instead.
    """
    if ctx.invoked_subcommand is not None:
        return  # a subcommand (corpus) handles the run
    report = build_report()
    code = 0 if report["ok"] else 1
    if emit_result(report, json_output=json_out, output=output):
        raise typer.Exit(code=code)
    _render(report)
    issues = report["issues"]
    if issues:
        print(f"doctor: {len(issues)} issue{'s' if len(issues) != 1 else ''} found")
    else:
        print("doctor: all checks passed")
    raise typer.Exit(code=code)


CORPUS_HEALTH_ARG = typer.Argument(
    ..., help="A corpus id (lineara, nt, damos, …), a Greek work id, a path to a "
              ".json/.db corpus, or '-' for JSON on stdin."
)


def doctor_corpus(
    corpus: str = CORPUS_HEALTH_ARG,
    deep: bool = typer.Option(
        False, "--deep", help="Run the full report (adds the Aegean sign-frequency scan)."
    ),
    json_out: bool = JSON_OPT,
    output: Path | None = RESULT_OPT,
) -> None:
    """A descriptive health report for one corpus: reading-status profile, provenance /
    citation completeness, Aegean accounting reconciliation (a discrepancy is a lead, not
    a verdict), numeral anomalies, annotation review state, and — with --deep — sign
    outliers. Offline. --json emits the structured report; -o writes .md / .json / .txt.
    """
    c = load_corpus(corpus)
    report = c.diagnose(level="full" if deep else "quick")
    if output is not None:
        _write_corpus_report(report, output)
    if json_out:
        emit_json(report)
    if output is not None or json_out:
        raise typer.Exit()
    report.print(console=None)


def _write_corpus_report(report: Any, output: Path) -> None:
    from aegean._atomic import atomic_path

    suffix = output.suffix.lower()
    if suffix in (".md", ".markdown"):
        with writing(output):
            with atomic_path(output) as tmp:
                tmp.write_text(report.to_markdown(), encoding="utf-8")
    elif suffix == ".json":
        with writing(output):
            with atomic_path(output) as tmp:
                tmp.write_text(
                    json.dumps(to_plain(report), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
    elif suffix in (".txt", ""):
        with writing(output):
            with atomic_path(output) as tmp:
                tmp.write_text(report.to_text(), encoding="utf-8")
    else:
        raise fail(f"output {output.name!r}: use a .md, .json, or .txt extension")
    print(f"wrote {output}", file=sys.stderr)


def _render(report: dict[str, Any]) -> None:
    from ._data import _human_size

    v = report["versions"]
    python_state = v["python"] if v["python_ok"] else f"{v['python']} (pyaegean needs 3.10+)"
    table(
        "versions",
        ["", "check", "value"],
        [
            ["OK" if v["python_ok"] else "ISSUE", "python", python_state],
            ["OK", "pyaegean", v["pyaegean"]],
            ["OK", "platform", v["platform"]],
        ],
    )

    extra_rows: list[list[str]] = []
    for e in report["extras"]:
        if e["installed"]:
            extra_rows.append(["OK", e["extra"], "installed", e["unlocks"]])
        else:
            state = (
                "not installed"
                if len(e["missing"]) == len(e["modules"])
                else f"partial (missing: {', '.join(e['missing'])})"
            )
            extra_rows.append(["-", e["extra"], state, f"{e['unlocks']} · {e['pip']}"])
    table(
        "optional extras (missing ones are informational, not problems)",
        ["", "extra", "state", "unlocks / install"],
        extra_rows,
    )

    store = report["data_store"]
    if store["path"] is None:
        table(
            "data store",
            ["", "item", "state"],
            [
                [
                    "ISSUE",
                    "location",
                    f"unavailable: {store['error']} · "
                    "fix: point PYAEGEAN_CACHE at a writable directory",
                ]
            ],
        )
    else:
        rows: list[list[str]] = [
            [
                "OK" if store["writable"] else "ISSUE",
                "writable",
                "yes" if store["writable"] else "no · fix: point PYAEGEAN_CACHE at a "
                "writable directory",
            ],
            ["-", "total size", _human_size(int(store["total_bytes"]))],
        ]
        for d in store["datasets"]:
            state = (
                f"downloaded ({_human_size(int(d['bytes']))})"
                if d["downloaded"]
                else "not downloaded"
            )
            rows.append(["-", d["name"], state])
        for o in store["orphans"]:
            rows.append(["ISSUE", o["file"], f"leftover partial download · fix: {o['fix']}"])
        table(f"data store: {store['path']}", ["", "item", "state"], rows)

    model_rows: list[list[str]] = []
    for m in report["models"]:
        if m["downloaded"] is None:
            model_rows.append(["-", m["name"], "unknown (data store unavailable)"])
        elif m["downloaded"]:
            model_rows.append(["OK", m["name"], "downloaded"])
        else:
            model_rows.append(["-", m["name"], f"not downloaded · {m['fetch']}"])
    table(
        "neural model bundles (informational; fetched on demand)",
        ["", "model", "state"],
        model_rows,
    )

    c = report["analysis_cache"]
    if c["enabled"]:
        size = _human_size(int(c["bytes"])) if c["bytes"] is not None else "?"
        entries = int(c["entries"])
        state = f"on · {entries} entr{'y' if entries == 1 else 'ies'} · {size} · {c['path']}"
    elif c["enabled"] is None:
        state = f"unavailable: {c['error']}"
    else:
        state = "off · set PYAEGEAN_ANALYSIS_CACHE=1 (or a path) to enable"
    table(
        "analysis cache (opt-in, informational)",
        ["", "item", "state"],
        [["-", "analysis cache", state]],
    )
