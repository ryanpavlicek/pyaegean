"""Public-API stability guard for pyaegean.

The deprecation policy (CONTRIBUTING.md) treats the public API as a contract:
deprecate in a minor, remove no sooner than the next minor, warnings name the
replacement. This script enforces the mechanical half of that contract: nothing
public disappears or changes signature without showing up red at the gate.

  1. snapshot   `python scripts/check_api.py --snapshot` walks the public surface
     of the ``aegean`` package and writes ``scripts/api-baseline.json`` (sorted,
     deterministic). Re-run it at each release cut to fold in additions.
  2. check      `python scripts/check_api.py` re-walks the current source and
     diffs it against the baseline. REMOVED names, REMOVED/RENAMED parameters,
     and CHANGED signatures exit 1 with a per-item report (these need a
     deprecation cycle). ADDED names and compatible loosenings (a new optional
     parameter, a newly gained default, a new return annotation) exit 0 and are
     listed as informational.

The walk is purely static (griffe, ``allow_inspection=False``): no module under
``src/`` is imported, so the lazy/optional heavy extras never load and the check
stays offline and fast (a couple of seconds).

What counts as public:

  * every module whose dotted path has no ``_``-prefixed segment;
  * in a module WITH ``__all__``: exactly the exported names (aliases resolve to
    their target's signature, recorded at the exported location);
  * in a module WITHOUT ``__all__``: names defined there that do not start with
    ``_`` (plain imports are not re-exports);
  * on a class: members not starting with ``_``, plus ``__init__``;
  * for functions/methods: parameter names, parameter kinds, whether each
    parameter has a default, and whether a return annotation is present.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

import griffe

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / "scripts" / "api-baseline.json"
DEFAULT_SEARCH_PATH = ROOT / "src"
DEFAULT_PACKAGE = "aegean"
BASELINE_FORMAT = 1

Entry = dict[str, Any]

_VARIADIC_KINDS = {"variadic positional", "variadic keyword"}
_POSITIONAL_KINDS = {"positional-only", "positional or keyword"}


# ── walking ──────────────────────────────────────────────────────────────────


def _function_entry(fn: griffe.Function) -> Entry:
    return {
        "kind": "function",
        "params": [
            {"name": p.name, "kind": p.kind.value, "default": p.default is not None}
            for p in fn.parameters
        ],
        "returns": fn.returns is not None,
    }


def _describe(obj: griffe.Object) -> Entry:
    if isinstance(obj, griffe.Function):
        return _function_entry(obj)
    return {"kind": obj.kind.value}


def _record(path: str, member: griffe.Object | griffe.Alias, names: dict[str, Entry]) -> None:
    """Record one public member (resolving an alias to its target's signature)."""
    if member.is_alias:
        assert isinstance(member, griffe.Alias)
        try:
            target = member.final_target
        except Exception:  # AliasResolutionError / CyclicAliasError: external or unresolvable
            names[path] = {"kind": "alias", "target": member.target_path}
            return
        entry = _describe(target)
        if target.path != path:
            entry["canonical"] = target.path  # informational only, never diffed
        names[path] = entry
        return
    if isinstance(member, griffe.Function):
        names[path] = _function_entry(member)
    elif isinstance(member, griffe.Class):
        names[path] = {"kind": "class"}
        _walk_class(member, path, names)
    else:
        names[path] = {"kind": member.kind.value}


def _walk_class(cls: griffe.Class, path: str, names: dict[str, Entry]) -> None:
    for name, member in sorted(cls.members.items()):
        if name.startswith("_") and name != "__init__":
            continue
        _record(f"{path}.{name}", member, names)


def _export_names(mod: griffe.Module) -> set[str] | None:
    """The module's ``__all__`` as plain strings, or None when undefined."""
    if mod.exports is None:
        return None
    out: set[str] = set()
    for item in mod.exports:
        out.add(item if isinstance(item, str) else getattr(item, "name", str(item)))
    return out


def _walk_module(mod: griffe.Module, names: dict[str, Entry]) -> None:
    names[mod.path] = {"kind": "module"}
    exports = _export_names(mod)
    for name, member in sorted(mod.members.items()):
        if not member.is_alias and isinstance(member, griffe.Module):
            # A real submodule is importable directly regardless of the parent's
            # __all__; recurse into every non-private one.
            if not name.startswith("_"):
                _walk_module(member, names)
            continue
        if exports is not None:
            if name not in exports:
                continue
        elif name.startswith("_") or member.is_alias:
            # No __all__: definitions are public, plain imports are not re-exports.
            continue
        _record(f"{mod.path}.{name}", member, names)


def walk_api(package: str, search_path: pathlib.Path) -> dict[str, Entry]:
    """Statically walk ``package`` under ``search_path`` into a {dotted path: entry} map."""
    loaded = griffe.load(
        package,
        search_paths=[search_path],
        submodules=True,
        allow_inspection=False,  # static only: never imports, so heavy extras never load
        store_source=False,
    )
    if not isinstance(loaded, griffe.Module):
        raise SystemExit(f"FAIL public-api: {package!r} did not load as a module")
    names: dict[str, Entry] = {}
    _walk_module(loaded, names)
    return names


# ── diffing ──────────────────────────────────────────────────────────────────


def _diff_params(path: str, old: Entry, new: Entry, breaking: list[str], info: list[str]) -> None:
    old_ps: list[dict[str, Any]] = old.get("params", [])
    new_ps: list[dict[str, Any]] = new.get("params", [])
    old_by = {p["name"]: p for p in old_ps}
    new_by = {p["name"]: p for p in new_ps}

    renamed_new: set[str] = set()
    for i, p in enumerate(old_ps):
        name = p["name"]
        if name not in new_by:
            # Rename heuristic: an unfamiliar name of the same kind sits at the old index.
            if (
                i < len(new_ps)
                and new_ps[i]["name"] not in old_by
                and new_ps[i]["kind"] == p["kind"]
            ):
                breaking.append(f"{path}: parameter '{name}' renamed to '{new_ps[i]['name']}'")
                renamed_new.add(new_ps[i]["name"])
            else:
                breaking.append(f"{path}: parameter '{name}' removed")
            continue
        q = new_by[name]
        if p["kind"] != q["kind"]:
            breaking.append(
                f"{path}: parameter '{name}' kind changed ({p['kind']} -> {q['kind']})"
            )
        if p["default"] and not q["default"]:
            breaking.append(f"{path}: parameter '{name}' lost its default (now required)")
        elif q["default"] and not p["default"]:
            info.append(f"{path}: parameter '{name}' gained a default")

    for q in new_ps:
        name = q["name"]
        if name in old_by or name in renamed_new:
            continue
        if q["kind"] in _VARIADIC_KINDS or q["default"]:
            info.append(f"{path}: new optional parameter '{name}'")
        else:
            breaking.append(f"{path}: new required parameter '{name}'")

    # Relative order of the positional parameters both sides share must not change.
    positional_both = {
        n
        for n in old_by
        if n in new_by
        and old_by[n]["kind"] in _POSITIONAL_KINDS
        and new_by[n]["kind"] in _POSITIONAL_KINDS
    }
    order_old = [p["name"] for p in old_ps if p["name"] in positional_both]
    order_new = [p["name"] for p in new_ps if p["name"] in positional_both]
    if order_old != order_new:
        breaking.append(
            f"{path}: positional parameters reordered ({', '.join(order_old)} -> "
            f"{', '.join(order_new)})"
        )


def _diff_entry(path: str, old: Entry, new: Entry, breaking: list[str], info: list[str]) -> None:
    old_kind, new_kind = old.get("kind"), new.get("kind")
    if old_kind != new_kind:
        breaking.append(f"{path}: kind changed ({old_kind} -> {new_kind})")
        return
    if old_kind != "function":
        return
    _diff_params(path, old, new, breaking, info)
    if old.get("returns") and not new.get("returns"):
        breaking.append(f"{path}: return annotation removed")
    elif new.get("returns") and not old.get("returns"):
        info.append(f"{path}: return annotation added")


def _collapse(paths: set[str]) -> list[str]:
    """Only the topmost paths of a removed/added subtree (children are implied)."""
    return sorted(p for p in paths if p.rsplit(".", 1)[0] not in paths)


def compare(
    baseline: dict[str, Entry], current: dict[str, Entry]
) -> tuple[list[str], list[str]]:
    """Diff two walks. Returns (breaking, informational) report lines."""
    breaking: list[str] = []
    info: list[str] = []
    removed = set(baseline) - set(current)
    added = set(current) - set(baseline)
    for path in _collapse(removed):
        breaking.append(f"{path}: removed ({baseline[path].get('kind', '?')})")
    for path in _collapse(added):
        info.append(f"{path}: added ({current[path].get('kind', '?')})")
    for path in sorted(set(baseline) & set(current)):
        _diff_entry(path, baseline[path], current[path], breaking, info)
    return breaking, info


# ── modes ────────────────────────────────────────────────────────────────────


def write_snapshot(baseline_path: pathlib.Path, package: str, search_path: pathlib.Path) -> None:
    names = walk_api(package, search_path)
    payload = {"format": BASELINE_FORMAT, "package": package, "names": names}
    baseline_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {baseline_path}: {len(names)} public names")
    print("OK  snapshot")


def run_check(baseline_path: pathlib.Path, package: str, search_path: pathlib.Path) -> int:
    if not baseline_path.is_file():
        raise SystemExit(
            f"FAIL public-api: no baseline at {baseline_path} — run "
            "`python scripts/check_api.py --snapshot` first"
        )
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    if payload.get("format") != BASELINE_FORMAT:
        raise SystemExit(
            f"FAIL public-api: baseline format {payload.get('format')!r} != "
            f"{BASELINE_FORMAT} — re-run `python scripts/check_api.py --snapshot`"
        )
    baseline: dict[str, Entry] = payload["names"]
    current = walk_api(package, search_path)
    breaking, info = compare(baseline, current)
    print(f"baseline {len(baseline)} public names; current {len(current)}")
    if info:
        print(f"informational ({len(info)}) — additions fold into the snapshot at release:")
        for line in info:
            print(f"  + {line}")
    if breaking:
        print(f"breaking ({len(breaking)}) — these need a deprecation cycle:")
        for line in breaking:
            print(f"  - {line}")
        print(
            "FAIL public-api: removed/changed public symbols. The policy "
            "(CONTRIBUTING.md) is deprecate in a minor, remove no sooner than the "
            "next minor, with a DeprecationWarning naming the replacement. After a "
            "completed deprecation cycle (or a deliberate, documented break), "
            "refresh the baseline with `python scripts/check_api.py --snapshot`."
        )
        return 1
    print(f"OK  public-api: no breaking changes ({len(info)} informational)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--snapshot", action="store_true", help="write the baseline instead of checking"
    )
    ap.add_argument("--baseline", type=pathlib.Path, default=DEFAULT_BASELINE)
    ap.add_argument("--package", default=DEFAULT_PACKAGE)
    ap.add_argument("--search-path", type=pathlib.Path, default=DEFAULT_SEARCH_PATH)
    args = ap.parse_args()
    if args.snapshot:
        write_snapshot(args.baseline, args.package, args.search_path)
        return 0
    return run_check(args.baseline, args.package, args.search_path)


if __name__ == "__main__":
    sys.exit(main())
