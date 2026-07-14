"""Public-API stability guard for pyaegean.

The deprecation policy (CONTRIBUTING.md) treats the public API as a contract:
deprecate in a minor, remove no sooner than the next minor, warnings name the
replacement. This script enforces the mechanical half of that contract: nothing
public disappears or changes signature without showing up red at the gate.

  1. snapshot   `python scripts/check_api.py --snapshot` preserves the existing
     format-1 compatibility names and merges additions from the reviewed facade
     manifest (``scripts/api-manifest.json``) into ``scripts/api-baseline.json``.
     Unlisted internal paths are never snapshotted automatically.
  2. check      `python scripts/check_api.py` re-walks the current source and
     diffs it against the baseline. REMOVED names, REMOVED/RENAMED parameters,
     and CHANGED signatures exit 1 with a per-item report (these need a
     deprecation cycle). ADDED names and compatible loosenings (a new optional
     parameter, a newly gained default, a new return annotation) exit 0 and are
     listed as informational.

The walk is purely static (griffe, ``allow_inspection=False``): no module under
``src/`` is imported, so the lazy/optional heavy extras never load and the check
stays offline and fast (a couple of seconds).

Compatibility names are checked against a full static walk. Additions are
limited to modules and symbols selected by the reviewed manifest, so adding
an unlisted implementation module does not silently make it public.

What counts as public in a manifest-selected module:

  * the module itself, after its dotted path passes manifest validation;
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
DEFAULT_MANIFEST = ROOT / "scripts" / "api-manifest.json"
DEFAULT_SEARCH_PATH = ROOT / "src"
DEFAULT_PACKAGE = "aegean"
BASELINE_FORMAT = 1
MANIFEST_FORMAT = 1

Entry = dict[str, Any]

_VARIADIC_KINDS = {"variadic positional", "variadic keyword"}
_POSITIONAL_KINDS = {"positional-only", "positional or keyword"}


# -- walking -----------------------------------------------------------------


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
        if not isinstance(item, str):
            raise ValueError(f"{mod.path}: __all__ entries must be strings, got {item!r}")
        out.add(item)
    return out


def _walk_module(
    mod: griffe.Module,
    names: dict[str, Entry],
    *,
    recurse_modules: bool = True,
) -> None:
    """Walk one module, optionally descending into imported submodules.

    The compatibility walk descends through every public module so that old
    baseline names can never disappear silently.  A facade walk visits only
    the explicitly listed module itself; imported submodules are selected by
    their own manifest entries.  This distinction is what keeps a newly-added
    internal module out of the contract while retaining legacy obligations.
    """
    names[mod.path] = {"kind": "module"}
    exports = _export_names(mod)
    if exports is not None:
        missing = sorted(name for name in exports if name not in mod.members)
        if missing:
            raise ValueError(
                f"{mod.path}: __all__ names not defined or imported: {', '.join(missing)}"
            )
    for name, member in sorted(mod.members.items()):
        if not member.is_alias and isinstance(member, griffe.Module):
            if recurse_modules:
                # A real submodule is importable directly regardless of the parent's
                # __all__; recurse into every non-private one.
                if not name.startswith("_"):
                    _walk_module(member, names, recurse_modules=True)
            elif exports is not None and name in exports:
                # The module itself is a formally exported member, but its
                # implementation descendants require a separate manifest entry.
                names[f"{mod.path}.{name}"] = {"kind": "module"}
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
    try:
        _walk_module(loaded, names)
    except ValueError as exc:
        raise SystemExit(f"FAIL public-api: {exc}") from None
    return names


def _load_static_module(module_path: str, search_path: pathlib.Path) -> griffe.Module:
    loaded = griffe.load(
        module_path,
        search_paths=[search_path],
        submodules=True,
        allow_inspection=False,
        store_source=False,
    )
    if not isinstance(loaded, griffe.Module):
        raise ValueError(f"{module_path!r} did not load as a module")
    return loaded


def _lookup_member(mod: griffe.Module, dotted_path: str) -> griffe.Object | griffe.Alias:
    current: griffe.Object | griffe.Alias = mod
    for segment in dotted_path.split("."):
        members = getattr(current, "members", None)
        if members is None or segment not in members:
            raise ValueError(f"{dotted_path}: no such member in {mod.path}")
        current = members[segment]
    return current


def _record_selected_symbol(
    symbol_path: str,
    search_path: pathlib.Path,
    names: dict[str, Entry],
    root: griffe.Module | None = None,
) -> None:
    parent_path, _, symbol = symbol_path.rpartition(".")
    if not parent_path or not symbol:
        raise ValueError(f"manifest symbol {symbol_path!r} is not a dotted member path")
    if root is None:
        parent = _load_static_module(parent_path, search_path)
    else:
        if parent_path == root.path:
            parent = root
        else:
            parent = _lookup_member(root, parent_path[len(root.path) + 1 :])
        if not isinstance(parent, griffe.Module):
            raise ValueError(f"{parent_path!r} did not resolve to a module")
    exports = _export_names(parent)
    if exports is not None and symbol not in exports:
        raise ValueError(
            f"{symbol_path}: selected symbol is not explicitly exported by {parent_path}"
        )
    member = _lookup_member(parent, symbol)
    _record(symbol_path, member, names)


def _validate_manifest_shape(payload: Any, package: str) -> tuple[list[str], list[str]]:
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")
    if payload.get("format") != MANIFEST_FORMAT:
        raise ValueError(
            f"manifest format {payload.get('format')!r} != {MANIFEST_FORMAT}"
        )
    if payload.get("package") != package:
        raise ValueError(
            f"manifest package {payload.get('package')!r} != requested package {package!r}"
        )
    modules = payload.get("modules")
    if not isinstance(modules, list) or not modules or not all(
        isinstance(item, str) for item in modules
    ):
        raise ValueError("manifest 'modules' must be a non-empty list of dotted strings")
    symbols = payload.get("symbols", [])
    if not isinstance(symbols, list) or not all(isinstance(item, str) for item in symbols):
        raise ValueError("manifest 'symbols' must be a list of dotted strings")
    if len(set(modules)) != len(modules):
        raise ValueError("manifest 'modules' contains duplicates")
    if len(set(symbols)) != len(symbols):
        raise ValueError("manifest 'symbols' contains duplicates")
    prefix = package + "."
    for path in [*modules, *symbols]:
        if not path or (path != package and not path.startswith(prefix)):
            raise ValueError(f"manifest path {path!r} is outside package {package!r}")
        if any(not part or part.startswith("_") for part in path.split(".")):
            raise ValueError(f"manifest path {path!r} contains a private/empty segment")
    for path in symbols:
        if "." not in path:
            raise ValueError(f"manifest symbol {path!r} must include a parent module")
    return modules, symbols


def load_manifest(path: pathlib.Path, package: str) -> tuple[list[str], list[str]]:
    """Load and validate the reviewed facade manifest."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"FAIL public-api: cannot read manifest {path}: {exc}") from None
    try:
        return _validate_manifest_shape(payload, package)
    except ValueError as exc:
        raise SystemExit(f"FAIL public-api: {exc}") from None


def walk_facade(
    package: str,
    search_path: pathlib.Path,
    modules: list[str],
    symbols: list[str] | None = None,
) -> dict[str, Entry]:
    """Static walk of only the manifest-selected facade modules and symbols."""
    names: dict[str, Entry] = {}
    try:
        root = _load_static_module(package, search_path)
        for module_path in modules:
            if module_path == package:
                mod = root
            else:
                mod = _lookup_member(root, module_path[len(package) + 1 :])
                if not isinstance(mod, griffe.Module):
                    raise ValueError(f"{module_path!r} did not resolve to a module")
            _walk_module(mod, names, recurse_modules=False)
        for symbol_path in symbols or []:
            _record_selected_symbol(symbol_path, search_path, names, root)
    except (ValueError, griffe.LoadingError) as exc:
        raise SystemExit(f"FAIL public-api: {exc}") from None
    return names


# -- diffing -----------------------------------------------------------------


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


# -- modes -------------------------------------------------------------------


def _read_baseline(path: pathlib.Path, package: str) -> dict[str, Entry] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"FAIL public-api: cannot read baseline {path}: {exc}") from None
    if not isinstance(payload, dict):
        raise SystemExit("FAIL public-api: baseline must be a JSON object")
    if payload.get("format") != BASELINE_FORMAT:
        raise SystemExit(
            f"FAIL public-api: baseline format {payload.get('format')!r} != "
            f"{BASELINE_FORMAT} - re-run `python scripts/check_api.py --snapshot`"
        )
    baseline_package = payload.get("package")
    if baseline_package is not None and baseline_package != package:
        raise SystemExit(
            f"FAIL public-api: baseline package {baseline_package!r} != requested package "
            f"{package!r}"
        )
    names = payload.get("names")
    if not isinstance(names, dict) or not all(
        isinstance(path, str) and isinstance(entry, dict) for path, entry in names.items()
    ):
        raise SystemExit("FAIL public-api: baseline 'names' must be an object of entries")
    return names


def _manifest_for(
    package: str, manifest_path: pathlib.Path | None
) -> tuple[list[str], list[str]] | None:
    if manifest_path is None:
        if package != DEFAULT_PACKAGE or not DEFAULT_MANIFEST.is_file():
            return None
        manifest_path = DEFAULT_MANIFEST
    return load_manifest(manifest_path, package)


def write_snapshot(
    baseline_path: pathlib.Path,
    package: str,
    search_path: pathlib.Path,
    manifest_path: pathlib.Path | None = None,
    accept_breaking: bool = False,
) -> None:
    old = _read_baseline(baseline_path, package)
    current_full = walk_api(package, search_path)
    retained: dict[str, Entry] = old or {}
    if old is not None:
        breaking, _ = compare(old, current_full)
        if breaking and not accept_breaking:
            print(f"breaking ({len(breaking)}) - snapshot refused due to legacy breaks:")
            for line in breaking:
                print(f"  - {line}")
            raise SystemExit(
                "FAIL public-api: snapshot would discard or change grandfathered names; "
                "complete the deprecation cycle, then review and repeat with "
                "--accept-breaking-snapshot"
            )
        if breaking:
            print(f"accepted breaking snapshot ({len(breaking)}) after explicit review:")
            for line in breaking:
                print(f"  - {line}")
            # Explicit acceptance retires removed names and refreshes surviving
            # grandfathered entries.  An ordinary old-first merge would otherwise
            # preserve a retired contract forever after its deprecation cycle.
            retained = {path: current_full[path] for path in old if path in current_full}
    manifest = _manifest_for(package, manifest_path)
    if manifest is None:
        # Synthetic/custom packages used by callers that have no reviewed
        # manifest retain the historical full-walk behavior.  The shipped
        # package always has a manifest, so its snapshot is facade-selected.
        names = {**retained, **current_full}
    else:
        modules, symbols = manifest
        current_facade = walk_facade(package, search_path, modules, symbols)
        names = {**retained, **current_facade}
    payload = {"format": BASELINE_FORMAT, "package": package, "names": names}
    baseline_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {baseline_path}: {len(names)} public names")
    print("OK  snapshot")


def run_check(
    baseline_path: pathlib.Path,
    package: str,
    search_path: pathlib.Path,
    manifest_path: pathlib.Path | None = None,
) -> int:
    if not baseline_path.is_file():
        raise SystemExit(
            f"FAIL public-api: no baseline at {baseline_path} - run "
            "`python scripts/check_api.py --snapshot` first"
        )
    baseline = _read_baseline(baseline_path, package)
    assert baseline is not None  # guarded by the is_file check above
    current = walk_api(package, search_path)
    manifest = _manifest_for(package, manifest_path)
    if manifest is None:
        supported = current
    else:
        modules, symbols = manifest
        supported = walk_facade(package, search_path, modules, symbols)

    # Legacy compatibility is always checked against the entire static tree.
    # Only additions come from the reviewed facade selection.
    breaking, legacy_info = compare(baseline, current)
    if manifest is None:
        info = legacy_info
    else:
        # ``compare`` also reports baseline removals as breaking.  Those were
        # already computed from the full walk above; retain only additions and
        # compatible signature loosenings from the selected facade walk.
        _facade_breaking, facade_info = compare(baseline, supported)
        info = facade_info
    print(
        f"baseline {len(baseline)} public names; current {len(current)} "
        f"({len(supported)} supported facade names)"
    )
    if info:
        print(f"informational ({len(info)}) - additions fold into the snapshot at release:")
        for line in info:
            print(f"  + {line}")
    if breaking:
        print(f"breaking ({len(breaking)}) - these need a deprecation cycle:")
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
    ap.add_argument(
        "--accept-breaking-snapshot",
        action="store_true",
        help=(
            "after a completed deprecation cycle, explicitly accept the reported "
            "removals/signature breaks while writing the snapshot"
        ),
    )
    ap.add_argument("--baseline", type=pathlib.Path, default=DEFAULT_BASELINE)
    ap.add_argument("--package", default=DEFAULT_PACKAGE)
    ap.add_argument("--search-path", type=pathlib.Path, default=DEFAULT_SEARCH_PATH)
    ap.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=None,
        help="reviewed facade manifest (defaults to scripts/api-manifest.json for aegean)",
    )
    args = ap.parse_args()
    if args.accept_breaking_snapshot and not args.snapshot:
        ap.error("--accept-breaking-snapshot requires --snapshot")
    if args.snapshot:
        write_snapshot(
            args.baseline,
            args.package,
            args.search_path,
            args.manifest,
            args.accept_breaking_snapshot,
        )
        return 0
    return run_check(args.baseline, args.package, args.search_path, args.manifest)


if __name__ == "__main__":
    sys.exit(main())
