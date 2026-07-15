"""Validate pyaegean's intentionally supported public facade.

The reviewed current facade lives in ``scripts/api-manifest.json``. This script
loads that manifest, statically resolves every selected module and symbol with
Griffe, and fails if the facade is malformed or no longer exists.

It deliberately carries no cumulative snapshot of older package versions. During
the pre-v4 development period, API changes are reviewed against the current
design and recorded in the CHANGELOG instead of preserved through compatibility
shims or a historical baseline.

The walk is purely static (``allow_inspection=False``): no module under ``src/``
is imported, so optional heavy dependencies never load and the check stays
offline and fast.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

import griffe

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "scripts" / "api-manifest.json"
DEFAULT_SEARCH_PATH = ROOT / "src"
DEFAULT_PACKAGE = "aegean"
MANIFEST_FORMAT = 1

Entry = dict[str, Any]



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

    A full walk descends through every public module. A facade walk visits only
    the explicitly listed module itself; imported submodules are selected by
    their own manifest entries. This keeps implementation modules out of the
    supported facade unless they are reviewed explicitly.
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
    parent: griffe.Object | griffe.Alias
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
                selected: griffe.Object | griffe.Alias = root
            else:
                selected = _lookup_member(root, module_path[len(package) + 1 :])
            if not isinstance(selected, griffe.Module):
                raise ValueError(f"{module_path!r} did not resolve to a module")
            _walk_module(selected, names, recurse_modules=False)
        for symbol_path in symbols or []:
            _record_selected_symbol(symbol_path, search_path, names, root)
    except (ValueError, griffe.LoadingError) as exc:
        raise SystemExit(f"FAIL public-api: {exc}") from None
    return names

# -- check -------------------------------------------------------------------


def _manifest_for(
    package: str, manifest_path: pathlib.Path | None
) -> tuple[list[str], list[str]]:
    if manifest_path is None:
        if package != DEFAULT_PACKAGE:
            raise SystemExit(
                "FAIL public-api: --manifest is required for a custom package"
            )
        manifest_path = DEFAULT_MANIFEST
    return load_manifest(manifest_path, package)


def run_check(
    package: str,
    search_path: pathlib.Path,
    manifest_path: pathlib.Path | None = None,
) -> int:
    modules, symbols = _manifest_for(package, manifest_path)
    supported = walk_facade(package, search_path, modules, symbols)
    if not supported:
        raise SystemExit("FAIL public-api: reviewed facade resolved to no names")
    print(
        f"OK  public-api: {len(supported)} current facade names resolve "
        f"({len(modules)} modules, {len(symbols)} explicit symbols)"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--package", default=DEFAULT_PACKAGE)
    ap.add_argument("--search-path", type=pathlib.Path, default=DEFAULT_SEARCH_PATH)
    ap.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=None,
        help="reviewed facade manifest (defaults to scripts/api-manifest.json for aegean)",
    )
    args = ap.parse_args()
    return run_check(args.package, args.search_path, args.manifest)


if __name__ == "__main__":
    sys.exit(main())
