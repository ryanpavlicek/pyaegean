"""The surface-parity guard: scripts/surface-manifest.json is the ledger of which
user-facing capability is surfaced on which of the four secondary surfaces (the
browser demo, the MCP server, the walkthrough notebooks, and the terminal UI).

This test makes the ledger load-bearing so the recurring "a surface silently fell
behind" drift class fails a test in the same commit:

* every function the browser demo registers (docs/demo/index.html + demo.py) is
  named by exactly one capability's ``demo`` coverage, and every demo-covered
  capability names a real demo function, checked in both directions;
* every MCP tool in ``aegean.mcp_server.TOOLS`` is named by exactly one
  capability's ``mcp`` coverage, and back;
* every capability records a decision for all four surfaces, each either
  ``covered`` with a location or ``excluded`` with a reason from the controlled
  vocabulary (no silent absence);
* the manifest is valid against its own schema (stdlib json only).

So adding a demo card or an MCP tool without a manifest entry fails, and adding a
capability without deciding its four surface fates fails.

Plain-module test: imports only the stdlib and the installed ``aegean`` package,
and reaches the repo files through ``__file__`` (no repo root on sys.path).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_MANIFEST_PATH = _REPO / "scripts" / "surface-manifest.json"
_DEMO_DIR = _REPO / "docs" / "demo"

# The four secondary surfaces the ledger tracks (the Python API and the CLI carry
# every capability and are not tracked). Pinned here so a surface can't be dropped
# from the manifest silently.
_SURFACES = ("demo", "mcp", "notebooks", "tui")

# The controlled vocabulary of exclusion reasons. Pinned in the test AND asserted
# equal to the manifest's own ``exclusion_reasons`` keys, so the documented set and
# the enforced set can never drift apart.
_VOCAB = frozenset(
    {
        "needs-network",
        "needs-fetch",
        "needs-neural-model",
        "needs-api-key",
        "needs-sqlite3",
        "heavy-dep",
        "file-path-ux",
        "not-applicable",
    }
)

_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


# ── loaders ──────────────────────────────────────────────────────────────────
def _load_manifest() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return data


def _capabilities() -> list[dict[str, Any]]:
    caps = _load_manifest()["capabilities"]
    assert isinstance(caps, list) and caps, "manifest has no capabilities"
    return caps


def _demo_registered_functions() -> set[str]:
    """The function names the demo actually wires up in index.html's init loop
    (``for (const name of [...])``), i.e. the JS function-list."""
    html = (_DEMO_DIR / "index.html").read_text(encoding="utf-8")
    m = re.search(r"for \(const name of \[(.*?)\]", html, re.S)
    assert m, "could not find the demo tool-name list in index.html"
    names = set(re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', m.group(1)))
    assert names, "the demo tool-name list parsed empty"
    return names


def _demo_defined_functions() -> set[str]:
    """The top-level functions actually defined in docs/demo/demo.py (via ast, no
    import needed)."""
    tree = ast.parse((_DEMO_DIR / "demo.py").read_text(encoding="utf-8"))
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


def _mcp_tool_names() -> set[str]:
    """The MCP tools the server registers (aegean.mcp_server.TOOLS)."""
    from aegean import mcp_server

    names = {fn.__name__ for fn in mcp_server.TOOLS}
    assert names, "aegean.mcp_server.TOOLS is empty"
    return names


def _covered_where(surface: str) -> list[str]:
    """Every ``where`` value across capabilities whose ``surface`` is covered
    (a list, so duplicate claims are detectable)."""
    out: list[str] = []
    for cap in _capabilities():
        entry = cap["surfaces"][surface]
        if entry["status"] == "covered":
            out.append(entry["where"])
    return out


# ── schema ───────────────────────────────────────────────────────────────────
def test_manifest_is_valid_against_its_schema() -> None:
    data = _load_manifest()

    assert list(data.get("surfaces", ())) == list(_SURFACES), (
        "manifest 'surfaces' must list exactly the four tracked surfaces"
    )
    reasons = data.get("exclusion_reasons")
    assert isinstance(reasons, dict) and reasons, "manifest needs exclusion_reasons"
    assert set(reasons) == set(_VOCAB), (
        "the manifest's exclusion_reasons keys must equal the enforced vocabulary "
        f"(missing {set(_VOCAB) - set(reasons)}, extra {set(reasons) - set(_VOCAB)})"
    )

    seen_ids: set[str] = set()
    for cap in _capabilities():
        assert set(cap) <= {"id", "since", "python_api", "summary", "surfaces"}, (
            f"unexpected keys on capability {cap.get('id')!r}: "
            f"{set(cap) - {'id', 'since', 'python_api', 'summary', 'surfaces'}}"
        )
        for req in ("id", "since", "python_api", "surfaces"):
            assert req in cap, f"capability {cap.get('id')!r} is missing {req!r}"

        cid = cap["id"]
        assert isinstance(cid, str) and _ID_RE.match(cid), f"bad capability id {cid!r}"
        assert cid not in seen_ids, f"duplicate capability id {cid!r}"
        seen_ids.add(cid)

        assert isinstance(cap["since"], str) and _VERSION_RE.match(cap["since"]), (
            f"capability {cid!r} has a non-semver 'since': {cap['since']!r}"
        )
        assert isinstance(cap["python_api"], str) and cap["python_api"].strip(), (
            f"capability {cid!r} needs a non-empty python_api"
        )
        if "summary" in cap:
            assert isinstance(cap["summary"], str) and cap["summary"].strip()

        surfaces = cap["surfaces"]
        assert isinstance(surfaces, dict) and set(surfaces) == set(_SURFACES), (
            f"capability {cid!r} must decide exactly the four surfaces, got {set(surfaces)}"
        )
        for name, entry in surfaces.items():
            _check_surface_entry(cid, name, entry)


def _check_surface_entry(cid: str, name: str, entry: Any) -> None:
    assert isinstance(entry, dict), f"{cid}.{name} must be an object"
    status = entry.get("status")
    assert status in ("covered", "excluded"), (
        f"{cid}.{name} status must be 'covered' or 'excluded', got {status!r}"
    )
    if status == "covered":
        assert set(entry) <= {"status", "where", "note"}, (
            f"{cid}.{name} (covered) has unexpected keys {set(entry) - {'status', 'where', 'note'}}"
        )
        assert isinstance(entry.get("where"), str) and entry["where"].strip(), (
            f"{cid}.{name} is covered but has no 'where'"
        )
    else:
        assert set(entry) <= {"status", "reason", "note"}, (
            f"{cid}.{name} (excluded) has unexpected keys {set(entry) - {'status', 'reason', 'note'}}"
        )
        assert entry.get("reason") in _VOCAB, (
            f"{cid}.{name} is excluded with reason {entry.get('reason')!r}, "
            f"not in the vocabulary {sorted(_VOCAB)}"
        )
    if "note" in entry:
        assert isinstance(entry["note"], str) and entry["note"].strip()


def test_every_capability_decides_all_four_surfaces() -> None:
    """No silent absence: every capability names a status for each of the four
    surfaces (schema validation already checks the shape; this pins the intent)."""
    for cap in _capabilities():
        for surface in _SURFACES:
            assert surface in cap["surfaces"], (
                f"capability {cap['id']!r} never decides its {surface!r} fate"
            )


# ── demo parity (both directions) ────────────────────────────────────────────
def test_demo_functions_and_manifest_agree() -> None:
    registered = _demo_registered_functions()
    covered_list = _covered_where("demo")
    covered = set(covered_list)

    # no capability claims the same demo function twice
    assert len(covered_list) == len(covered), (
        "a demo function is claimed by more than one capability: "
        f"{sorted(x for x in covered_list if covered_list.count(x) > 1)}"
    )
    # forward: every registered demo function is in the manifest
    assert registered <= covered, (
        "demo functions with no manifest entry (add a capability whose demo.where "
        f"names them): {sorted(registered - covered)}"
    )
    # backward: every demo-covered capability names a currently-registered function
    assert covered <= registered, (
        "manifest claims demo coverage for functions the demo does not register: "
        f"{sorted(covered - registered)}"
    )
    # and each named function actually exists in demo.py
    defined = _demo_defined_functions()
    assert covered <= defined, (
        "manifest names demo functions that do not exist in demo.py: "
        f"{sorted(covered - defined)}"
    )


def test_demo_registered_functions_exist_in_demo_module() -> None:
    """Sanity: index.html only wires functions that demo.py actually defines
    (independent of the manifest, so a broken JS list is caught here too)."""
    missing = _demo_registered_functions() - _demo_defined_functions()
    assert not missing, f"index.html registers undefined demo functions: {sorted(missing)}"


# ── MCP parity (both directions) ─────────────────────────────────────────────
def test_mcp_tools_and_manifest_agree() -> None:
    tools = _mcp_tool_names()
    covered_list = _covered_where("mcp")
    covered = set(covered_list)

    assert len(covered_list) == len(covered), (
        "an MCP tool is claimed by more than one capability: "
        f"{sorted(x for x in covered_list if covered_list.count(x) > 1)}"
    )
    # forward: every registered MCP tool is in the manifest
    assert tools <= covered, (
        "MCP tools with no manifest entry (add a capability whose mcp.where names "
        f"them): {sorted(tools - covered)}"
    )
    # backward: every mcp-covered capability names a real tool
    assert covered <= tools, (
        "manifest claims MCP coverage for tools that are not in TOOLS: "
        f"{sorted(covered - tools)}"
    )
