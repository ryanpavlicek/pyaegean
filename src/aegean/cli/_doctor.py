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

from pathlib import Path
from typing import Any

import typer

from .._doctor import build_report
from ._common import JSON_OPT, RESULT_OPT, emit_result, table


def register(app: typer.Typer) -> None:
    app.command()(doctor)


def doctor(
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Check the local environment: versions, extras, data store, models, cache.

    Entirely offline: no network is touched and nothing is downloaded; every
    value is measured live. Missing optional extras are informational (their
    install line is shown), not problems. Exits 0 when everything is healthy,
    1 when any issue was found; --json emits the whole report as one document.
    """
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
