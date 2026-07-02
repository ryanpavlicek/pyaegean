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
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import typer

from ._common import JSON_OPT, RESULT_OPT, emit_result, table


def register(app: typer.Typer) -> None:
    app.command()(doctor)


_MIN_PYTHON = (3, 10)

# extra -> (modules that must be importable, what the extra unlocks). Detection
# is find_spec-only, so nothing heavy is actually imported: onnxruntime,
# geopandas, matplotlib and friends all stay unloaded while doctor runs.
_EXTRAS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("data", ("pandas",), "DataFrame interop (to_dataframe)"),
    ("neural", ("onnxruntime", "tokenizers", "numpy"), "the neural Greek pipeline"),
    ("anthropic", ("anthropic",), "the Anthropic provider (aegean.ai)"),
    ("openai", ("openai",), "the OpenAI, Grok, and OpenRouter providers (aegean.ai)"),
    ("gemini", ("google.genai",), "the Gemini provider (aegean.ai)"),
    ("epidoc", ("lxml",), "schema-valid EpiDoc export"),
    ("geo", ("geopandas", "shapely"), "the geospatial layer (aegean.geo)"),
    ("viz", ("matplotlib",), "one-line plots (aegean plot)"),
    ("parquet", ("pyarrow",), "Parquet export"),
    ("cli", ("typer", "rich", "prompt_toolkit"), "this command-line interface"),
    ("mcp", ("mcp",), "the aegean-mcp server"),
    ("tui", ("textual",), "the terminal UI (aegean tui)"),
)

# The fetchable neural model bundles, surfaced in their own section (they are
# regular datasets; this answers "are the models here?" directly).
_MODEL_BUNDLES = ("grc-joint", "grc-lemma-neural")

# Store files that only exist mid-download or mid-extraction; found at rest
# they are leftovers from an interrupted fetch. Longest suffix first so
# ``name.part.info`` strips to ``name``, not ``name.info``.
_ORPHAN_SUFFIXES = (".part.info", ".part", ".extract")


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


def build_report() -> dict[str, Any]:
    """The full doctor report as one JSON-ready document (measured, offline)."""
    issues: list[dict[str, Any]] = []
    versions = _versions_section(issues)
    extras = _extras_section()
    store = _store_section(issues)
    models = _models_section(store)
    cache = _cache_section()
    return {
        "ok": not issues,
        "issues": issues,
        "versions": versions,
        "extras": extras,
        "data_store": store,
        "models": models,
        "analysis_cache": cache,
    }


# ── section 1: versions ──────────────────────────────────────────────────────
def _python_ok(version_info: Any | None = None) -> bool:
    """Whether the running Python meets pyaegean's floor (3.10)."""
    vi = sys.version_info if version_info is None else version_info
    return bool(tuple(vi[:2]) >= _MIN_PYTHON)


def _versions_section(issues: list[dict[str, Any]]) -> dict[str, Any]:
    import platform

    import aegean

    ok = _python_ok()
    if not ok:
        issues.append(
            {
                "section": "versions",
                "message": f"Python {platform.python_version()} is below pyaegean's 3.10 floor",
                "fix": "run pyaegean on Python 3.10 or newer",
            }
        )
    return {
        "python": platform.python_version(),
        "python_ok": ok,
        "pyaegean": aegean.__version__,
        "platform": platform.platform(),
    }


# ── section 2: optional extras (informational) ───────────────────────────────
def _module_present(name: str) -> bool:
    """Whether ``name`` is importable, without importing it (find_spec only)."""
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):  # a broken/half-removed parent package
        return False


def _extras_section() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for extra, modules, unlocks in _EXTRAS:
        missing = [m for m in modules if not _module_present(m)]
        out.append(
            {
                "extra": extra,
                "modules": list(modules),
                "installed": not missing,
                "missing": missing,
                "unlocks": unlocks,
                "pip": f'pip install "pyaegean[{extra}]"',
            }
        )
    return out


# ── section 3: the data store ────────────────────────────────────────────────
def _probe_writable(root: Path) -> bool:
    """Whether the store directory accepts a write, proven by one (os.access is
    unreliable on Windows, so a real probe file is created and removed)."""
    import uuid

    probe = root / f".doctor-{uuid.uuid4().hex}.probe"
    try:
        probe.write_bytes(b"")
    except OSError:
        return False
    try:
        probe.unlink()
    except OSError:  # pragma: no cover - written but undeletable is still writable
        pass
    return True


def _store_section(issues: list[dict[str, Any]]) -> dict[str, Any]:
    from aegean.data import _REMOTE

    from ._data import _on_disk_bytes

    try:
        from aegean.data import cache_dir

        root = cache_dir()
    except OSError as exc:
        issues.append(
            {
                "section": "data store",
                "message": f"store directory unavailable: {exc}",
                "fix": "point PYAEGEAN_CACHE at a writable directory",
            }
        )
        return {
            "path": None,
            "writable": False,
            "total_bytes": None,
            "datasets": [],
            "orphans": [],
            "error": str(exc),
        }

    writable = _probe_writable(root)
    if not writable:
        issues.append(
            {
                "section": "data store",
                "message": f"store directory is not writable: {root}",
                "fix": "point PYAEGEAN_CACHE at a writable directory",
            }
        )

    total = 0
    orphans: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        total += _on_disk_bytes(child)
        name = child.name
        suffix = next((s for s in _ORPHAN_SUFFIXES if name.endswith(s)), None)
        if suffix is None:
            continue
        dataset = name[: -len(suffix)]
        fix = f"aegean data remove {dataset}" if dataset in _REMOTE else f"delete {child}"
        orphans.append({"file": name, "dataset": dataset, "fix": fix})
        issues.append(
            {
                "section": "data store",
                "message": f"leftover partial download: {name}",
                "fix": fix,
            }
        )

    datasets = []
    for name in sorted(_REMOTE):  # the same per-dataset state `aegean data list` reports
        entry = root / name
        downloaded = entry.exists()
        datasets.append(
            {
                "name": name,
                "downloaded": downloaded,
                "bytes": _on_disk_bytes(entry) if downloaded else None,
            }
        )
    return {
        "path": str(root),
        "writable": writable,
        "total_bytes": total,
        "datasets": datasets,
        "orphans": orphans,
        "error": None,
    }


# ── section 4: neural model bundles (informational) ──────────────────────────
def _models_section(store: dict[str, Any]) -> list[dict[str, Any]]:
    from aegean.data import _REMOTE

    by_name = {d["name"]: d for d in store["datasets"]}
    out: list[dict[str, Any]] = []
    for name in _MODEL_BUNDLES:
        row = by_name.get(name)
        downloaded: bool | None
        if store["path"] is None:
            downloaded = None  # the store itself is unavailable; nothing to measure
        else:
            downloaded = bool(row and row["downloaded"])
        spec = _REMOTE.get(name)
        out.append(
            {
                "name": name,
                "downloaded": downloaded,
                "note": spec.note if spec is not None else "",
                "fetch": f"aegean data fetch {name}",
            }
        )
    return out


# ── section 5: the opt-in analysis cache (informational) ────────────────────
def _cache_section() -> dict[str, Any]:
    from aegean import cache as analysis_cache

    try:
        info = analysis_cache.stats()
    except OSError as exc:  # PYAEGEAN_ANALYSIS_CACHE set but its directory unusable
        return {"enabled": None, "path": None, "entries": None, "bytes": None, "error": str(exc)}
    size: int | None = None
    if info.get("path"):
        p = Path(str(info["path"]))
        if p.exists():
            size = p.stat().st_size
    return {
        "enabled": info["enabled"],
        "path": info["path"],
        "entries": info["entries"],
        "bytes": size,
        "error": None,
    }


# ── human rendering ──────────────────────────────────────────────────────────
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
