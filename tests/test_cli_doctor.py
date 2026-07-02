"""`aegean doctor`, exercised offline through CliRunner against an isolated
PYAEGEAN_CACHE: a healthy environment exits 0 with OK rows and the all-clear
summary; a planted orphan .part flips the exit to 1, naming the file and the
`aegean data remove` fix; a store pointed at a FILE (the reliable Windows
stand-in for an unwritable directory) reports the data-store issue; the --json
report shape is pinned key-for-key with live-measured values (dataset bytes,
cache entries, extras). Analysis-cache global state is neutralized per test so
runs are order-independent."""

from __future__ import annotations

import json

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

import aegean  # noqa: E402
from aegean import data  # noqa: E402
from aegean.cli import _build_app, _doctor  # noqa: E402

runner = CliRunner()

PAYLOAD = b"a" * 4096  # 4096 B renders as "4.1 kB" in the human table


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


@pytest.fixture()
def store(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """An isolated, existing data store; returns its root directory."""
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    root = tmp_path / "cache" / "pyaegean"
    root.mkdir(parents=True)
    return root


@pytest.fixture(autouse=True)
def quiet_analysis_cache(monkeypatch):  # type: ignore[no-untyped-def]
    """Deterministic analysis-cache state: disabled, env not consulted."""
    from aegean import cache as analysis_cache

    monkeypatch.delenv("PYAEGEAN_ANALYSIS_CACHE", raising=False)
    monkeypatch.setattr(analysis_cache, "_active", None)
    monkeypatch.setattr(analysis_cache, "_env_checked", True)


def _output(res) -> str:  # type: ignore[no-untyped-def]
    """stdout plus stderr, across click versions that do or don't mix them."""
    out = res.output
    try:
        out += res.stderr
    except (ValueError, AttributeError):
        pass
    return out


def _stdout(res) -> str:  # type: ignore[no-untyped-def]
    try:
        return res.stdout  # this click separates stdout from stderr
    except (ValueError, AttributeError):
        return res.output


def _doctor_json(app, expect_exit: int):  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["doctor", "--json"])
    assert res.exit_code == expect_exit, _output(res)
    return json.loads(_stdout(res))


# ── healthy environment: exit 0, OK rows, all-clear summary ──────────────────
def test_healthy_env_exits_0_with_ok_rows_and_summary(app, store) -> None:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 0, _output(res)
    out = _output(res)
    assert "OK" in out  # at least the version rows carry the OK glyph
    assert "ISSUE" not in out
    assert "all checks passed" in out


def test_json_report_shape_and_measured_values(app, store, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import platform

    # A registered dataset already in the store: doctor must report the real
    # on-disk state, so plant the entry directly (no fetch — doctor is offline).
    monkeypatch.setitem(data._REMOTE, "blob", data.DataSpec(name="blob", url="", license="x"))
    (store / "blob").write_bytes(PAYLOAD)

    payload = _doctor_json(app, expect_exit=0)
    assert set(payload) == {
        "ok", "issues", "versions", "extras", "data_store", "models", "analysis_cache",
    }
    assert payload["ok"] is True and payload["issues"] == []

    v = payload["versions"]
    assert set(v) == {"python", "python_ok", "pyaegean", "platform"}
    assert v["python"] == platform.python_version()
    assert v["python_ok"] is True
    assert v["pyaegean"] == aegean.__version__
    assert v["platform"]  # measured, non-empty

    extras = {e["extra"]: e for e in payload["extras"]}
    assert set(extras) == {
        "data", "neural", "anthropic", "openai", "gemini", "epidoc", "geo",
        "viz", "parquet", "cli", "mcp", "tui",
    }
    for e in extras.values():
        assert set(e) == {"extra", "modules", "installed", "missing", "unlocks", "pip"}
    # the CLI extra is provably installed here (this very test imports typer)
    assert extras["cli"]["installed"] is True and extras["cli"]["missing"] == []
    assert extras["cli"]["pip"] == 'pip install "pyaegean[cli]"'

    ds = payload["data_store"]
    assert set(ds) == {"path", "writable", "total_bytes", "datasets", "orphans", "error"}
    assert ds["path"] == str(store)
    assert ds["writable"] is True and ds["error"] is None
    assert ds["orphans"] == []
    assert ds["total_bytes"] >= len(PAYLOAD)
    rows = {d["name"]: d for d in ds["datasets"]}
    assert rows["blob"] == {"name": "blob", "downloaded": True, "bytes": len(PAYLOAD)}
    assert rows["grc-joint"]["downloaded"] is False and rows["grc-joint"]["bytes"] is None

    models = {m["name"]: m for m in payload["models"]}
    assert set(models) == {"grc-joint", "grc-lemma-neural"}
    for m in models.values():
        assert set(m) == {"name", "downloaded", "note", "fetch"}
        assert m["downloaded"] is False  # nothing fetched into the isolated store
        assert m["fetch"] == f"aegean data fetch {m['name']}"

    assert payload["analysis_cache"] == {
        "enabled": False, "path": None, "entries": 0, "bytes": None, "error": None,
    }


# ── orphan partial downloads: exit 1, file named, remove fix given ────────────
def test_orphan_part_flips_exit_to_1_and_names_file_and_fix(app, store) -> None:  # type: ignore[no-untyped-def]
    (store / "nt-corpus.part").write_bytes(b"x" * 2048)

    payload = _doctor_json(app, expect_exit=1)
    assert payload["ok"] is False
    assert payload["data_store"]["orphans"] == [
        {"file": "nt-corpus.part", "dataset": "nt-corpus", "fix": "aegean data remove nt-corpus"}
    ]
    issue = next(i for i in payload["issues"] if i["section"] == "data store")
    assert "nt-corpus.part" in issue["message"]
    assert issue["fix"] == "aegean data remove nt-corpus"

    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 1, _output(res)
    out = _output(res)
    assert "ISSUE" in out
    assert "1 issue found" in out


def test_part_info_orphan_maps_to_its_dataset(app, store) -> None:  # type: ignore[no-untyped-def]
    # .part.info must strip its FULL suffix ('nt-corpus', never 'nt-corpus.part').
    (store / "nt-corpus.part").write_bytes(b"x")
    (store / "nt-corpus.part.info").write_text("{}", encoding="utf-8")
    payload = _doctor_json(app, expect_exit=1)
    orphans = payload["data_store"]["orphans"]
    assert [o["file"] for o in orphans] == ["nt-corpus.part", "nt-corpus.part.info"]
    assert all(o["dataset"] == "nt-corpus" for o in orphans)
    assert all(o["fix"] == "aegean data remove nt-corpus" for o in orphans)
    assert len(payload["issues"]) == 2  # one issue per leftover file


def test_unregistered_orphan_gets_a_delete_fix(app, store) -> None:  # type: ignore[no-untyped-def]
    # A .part whose stem is no registered dataset: `data remove` would refuse
    # it, so the fix must be deleting the file itself.
    (store / "junk.part").write_bytes(b"x")
    payload = _doctor_json(app, expect_exit=1)
    (orphan,) = payload["data_store"]["orphans"]
    assert orphan["dataset"] == "junk"
    assert orphan["fix"] == f"delete {store / 'junk.part'}"


# ── unusable store: PYAEGEAN_CACHE pointing at a FILE ────────────────────────
def test_store_pointed_at_a_file_reports_the_issue(app, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    not_a_dir = tmp_path / "notadir"
    not_a_dir.write_text("x", encoding="utf-8")
    monkeypatch.setenv("PYAEGEAN_CACHE", str(not_a_dir))

    payload = _doctor_json(app, expect_exit=1)
    assert payload["ok"] is False
    ds = payload["data_store"]
    assert ds["path"] is None and ds["writable"] is False
    assert ds["error"]  # the measured OSError text
    assert ds["datasets"] == [] and ds["orphans"] == []
    issue = next(i for i in payload["issues"] if i["section"] == "data store")
    assert "unavailable" in issue["message"]
    assert "PYAEGEAN_CACHE" in issue["fix"]
    # the models section cannot measure anything without a store
    assert all(m["downloaded"] is None for m in payload["models"])

    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 1, _output(res)
    assert "ISSUE" in _output(res)


# ── extras: missing is informational, never an issue ────────────────────────
def test_missing_extra_is_informational_not_an_issue(app, store, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        _doctor,
        "_EXTRAS",
        (("fake", ("aegean_no_such_module_xyz",), "nothing real"),),
    )
    payload = _doctor_json(app, expect_exit=0)  # still exit 0: not a problem
    (entry,) = payload["extras"]
    assert entry["installed"] is False
    assert entry["missing"] == ["aegean_no_such_module_xyz"]
    assert entry["pip"] == 'pip install "pyaegean[fake]"'
    assert payload["ok"] is True and payload["issues"] == []


# ── the Python floor ─────────────────────────────────────────────────────────
def test_python_floor_predicate() -> None:
    assert _doctor._python_ok((3, 9, 13)) is False
    assert _doctor._python_ok((3, 10, 0)) is True
    assert _doctor._python_ok((4, 0, 0)) is True


def test_old_python_is_flagged_as_an_issue(app, store, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(_doctor, "_python_ok", lambda version_info=None: False)
    payload = _doctor_json(app, expect_exit=1)
    assert payload["versions"]["python_ok"] is False
    issue = next(i for i in payload["issues"] if i["section"] == "versions")
    assert "3.10" in issue["message"]

    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 1, _output(res)
    assert "ISSUE" in _output(res)


# ── models + analysis cache report the measured state ────────────────────────
def test_downloaded_model_bundle_is_reported(app, store) -> None:  # type: ignore[no-untyped-def]
    bundle = store / "grc-joint"
    bundle.mkdir()
    (bundle / "model.onnx").write_bytes(b"m" * 128)
    payload = _doctor_json(app, expect_exit=0)  # informational either way
    models = {m["name"]: m for m in payload["models"]}
    assert models["grc-joint"]["downloaded"] is True
    assert models["grc-lemma-neural"]["downloaded"] is False


def test_enabled_analysis_cache_reports_entries_and_size(app, store) -> None:  # type: ignore[no-untyped-def]
    from aegean import cache as analysis_cache

    c = analysis_cache.enable(store / "analysis-cache.sqlite")
    try:
        c.set("k", {"v": 1})
        payload = _doctor_json(app, expect_exit=0)
        info = payload["analysis_cache"]
        assert info["enabled"] is True
        assert info["entries"] == 1  # the one entry just written
        assert info["path"] == str(store / "analysis-cache.sqlite")
        assert info["bytes"] > 0  # the real on-disk sqlite size
    finally:
        analysis_cache.disable()


# ── -o: the shared write helper combines with --json ─────────────────────────
def test_output_file_combines_with_json(app, store, tmp_path) -> None:  # type: ignore[no-untyped-def]
    out_file = tmp_path / "reports" / "doctor.json"  # parent must be created
    res = runner.invoke(app, ["doctor", "--json", "-o", str(out_file)])
    assert res.exit_code == 0, _output(res)
    on_stdout = json.loads(_stdout(res))  # --json still prints to stdout
    on_disk = json.loads(out_file.read_text(encoding="utf-8"))
    assert on_disk == on_stdout
    assert f"wrote {out_file}" in _output(res)  # the wrote-line (stderr)


# ── help: states the offline guarantee ───────────────────────────────────────
def test_help_states_doctor_is_offline(app) -> None:  # type: ignore[no-untyped-def]
    cmd = typer.main.get_command(app).commands["doctor"]
    help_text = cmd.help or ""
    assert "offline" in help_text.lower()
    assert "no network" in help_text.lower()
