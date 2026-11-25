"""``aegean library …`` — unified corpus, text, lexicon, and model manager.

One command group for every resource pyaegean supports: bundled corpora,
downloadable corpora, Biblical & Koine Greek bundles, all ~1,778 Perseus /
First1KGreek literary works, 48 Greek patristic commentaries, lexica, models,
and named packs (``biblical``, ``aegean``, ``epigraphy``, ``lexica``,
``neural``).
"""

from __future__ import annotations

import sys

import typer

from ._common import JSON_OPT, console, emit_json, fail, table
from ._complete import (
    shell_complete_library_category,
    shell_complete_library_install_target,
    shell_complete_library_remove_target,
)

library_app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help=(
        "Manage all corpora, Biblical texts, Greek literary works, commentaries, "
        "lexica, and models in one place."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _status_badge(status: str, nbytes: int | None, size_hint: str) -> str:
    from aegean.library import format_size

    if status == "bundled":
        return "[green]bundled[/green]"
    if status == "installed":
        sz = format_size(nbytes) if nbytes else ""
        return f"[green]installed[/green] ({sz})" if sz else "[green]installed[/green]"
    return f"[dim]available[/dim] ({size_hint})" if size_hint else "[dim]available[/dim]"


def _render_status(json_out: bool = False) -> None:
    from aegean.library import format_size, summary

    snap = summary()
    if json_out:
        emit_json(snap)
        return

    c = console()
    c.print(
        f"[bold cyan]Local library[/bold cyan]  [dim]{snap['store_path']}[/dim]\n"
        f"  [green]{snap['bundled_count']} bundled[/green] · "
        f"[green]{snap['downloaded_count']} downloaded[/green] "
        f"({snap['installed_size'] or '0 B'} on disk)\n"
    )

    cat_labels = {
        "corpus": "Corpora (Aegean & Greek)",
        "bible": "Biblical & Koine Greek",
        "work": "Greek literary works",
        "commentary": "Patristic commentaries",
        "lexicon": "Greek dictionaries",
        "model": "NLP & neural models",
        "other": "Benchmarks & media",
    }
    rows: list[list[str]] = []
    for key, label in cat_labels.items():
        info = snap["categories"][key]
        rows.append(
            [
                key,
                label,
                str(info["bundled"]),
                str(info["downloaded"]),
                str(info["available"]),
                format_size(info["bytes"]) if info["bytes"] else "—",
            ]
        )
    table(
        "Resources by category",
        ["category", "group", "bundled", "downloaded", "available", "on disk"],
        rows,
    )

    pack_rows: list[list[str]] = []
    for p in snap["packs"]:
        prog = f"{p['installed_count']}/{p['total_count']}"
        state = "[green]complete[/green]" if p["complete"] else f"{prog} installed"
        pack_rows.append([p["id"], p["title"], state, p["size_hint"]])
    table(
        "Installable packs  (`aegean library install <pack>`)",
        ["pack", "contents", "status", "size"],
        pack_rows,
    )
    c.print(
        "[dim]Examples: aegean library install biblical · aegean library search Plato · "
        "aegean library list --installed · aegean library remove <name>[/dim]"
    )


@library_app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    json_out: bool = JSON_OPT,
) -> None:
    """Show local library status when invoked without a subcommand."""
    if ctx.invoked_subcommand is None:
        _render_status(json_out=json_out)


@library_app.command("status")
def status_cmd(json_out: bool = JSON_OPT) -> None:
    """Show installed resources, disk usage, and pack completion across all categories."""
    _render_status(json_out=json_out)


@library_app.command("packs")
def packs_cmd(json_out: bool = JSON_OPT) -> None:
    """List named resource packs for one-command installation."""
    from aegean.library import list_packs

    packs = list_packs()
    if json_out:
        emit_json([p.to_dict() for p in packs])
        return

    rows: list[list[str]] = []
    for st in packs:
        p = st.pack
        state = (
            "[green]complete[/green]"
            if st.complete
            else f"{st.installed_count}/{st.total_count} installed"
        )
        rows.append([p.id, p.title, state, p.size_hint, ", ".join(p.items)])
    table(
        "Named packs  (`aegean library install <pack>`)",
        ["pack", "title", "status", "size", "items"],
        rows,
    )


@library_app.command("list")
def list_cmd(
    category: str | None = typer.Argument(
        None,
        help="Optional category: corpus, bible, work, commentary, lexicon, model, other.",
        autocompletion=shell_complete_library_category,
    ),
    installed: bool = typer.Option(False, "--installed", "-i", help="Show bundled and downloaded items."),
    downloaded: bool = typer.Option(False, "--downloaded", "-d", help="Show downloaded items only."),
    available: bool = typer.Option(False, "--available", "-a", help="Show not-yet-downloaded items only."),
    show_all: bool = typer.Option(False, "--all", help="Include all ~1,778 Greek literary works."),
    query: str | None = typer.Option(None, "--query", "-q", help="Filter by id, title, author, or alias."),
    limit: int | None = typer.Option(None, "--limit", "-n", help="Cap the number of rows displayed."),
    json_out: bool = JSON_OPT,
) -> None:
    """List corpora, Biblical texts, Greek works, commentaries, lexica, and models."""
    from aegean.library import list_items

    flags = [f for f, on in (("installed", installed), ("downloaded", downloaded), ("available", available)) if on]
    if len(flags) > 1:
        raise fail("use only one of --installed, --downloaded, or --available")
    status_filter = flags[0] if flags else None

    try:
        items = list_items(
            category=category,
            status=status_filter,
            query=query,
            include_works=show_all,
            limit=limit,
        )
    except ValueError as exc:
        raise fail(str(exc)) from None

    if json_out:
        emit_json([it.to_dict() for it in items])
        return

    if not items:
        console().print("No matching library items.")
        return

    cap = limit if limit is not None else (60 if category in ("work", "commentary") or show_all else len(items))
    shown = items[:cap]
    rows = [
        [
            it.id,
            it.category,
            _status_badge(it.status, it.bytes, it.size_hint),
            it.title,
        ]
        for it in shown
    ]
    title = f"Library items ({len(items)} total)"
    if category:
        title = f"Library: {category} ({len(items)} total)"
    table(title, ["id", "category", "status", "title"], rows)
    if len(items) > len(shown):
        console().print(
            f"[dim]Showing {len(shown)} of {len(items)} — pass --limit N or `aegean library search <query>` to narrow.[/dim]"
        )


@library_app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Search term (id, author, English or Greek title, alias)."),
    category: str | None = typer.Option(
        None,
        "--category",
        "-c",
        help="Restrict to one category (corpus, bible, work, commentary, lexicon, model, other).",
        autocompletion=shell_complete_library_category,
    ),
    installed: bool = typer.Option(False, "--installed", "-i", help="Only search installed items."),
    limit: int = typer.Option(30, "--limit", "-n", help="Maximum matches to show."),
    json_out: bool = JSON_OPT,
) -> None:
    """Search across all corpora, Biblical bundles, 1,778 Greek works, commentaries, lexica, and models."""
    from aegean.library import search

    try:
        hits = search(
            query,
            category=category,
            status="installed" if installed else None,
            limit=limit,
        )
    except ValueError as exc:
        raise fail(str(exc)) from None

    if json_out:
        emit_json([it.to_dict() for it in hits])
        return

    if not hits:
        console().print(f"No library items matching {query!r}.")
        return

    rows = [
        [
            it.id,
            it.category,
            _status_badge(it.status, it.bytes, it.size_hint),
            it.title,
        ]
        for it in hits
    ]
    table(f"Search results for {query!r} ({len(hits)})", ["id", "category", "status", "title"], rows)
    console().print("[dim]Install any match with: aegean library install <id>[/dim]")


@library_app.command("info")
def info_cmd(
    target: str = typer.Argument(
        ...,
        help="Item id, pack name, alias, or work title (e.g. nt-editions, biblical, damos, Iliad).",
        autocompletion=shell_complete_library_install_target,
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Show full metadata, status, license, aliases, and usage for one item or pack."""
    from aegean.library import format_size, get_item, get_pack, list_packs

    pack = get_pack(target)
    if pack is not None:
        st = next(p for p in list_packs() if p.pack.id == pack.id)
        if json_out:
            emit_json(st.to_dict())
            return
        c = console()
        c.print(f"[bold cyan]{pack.id}[/bold cyan] — {pack.title}")
        c.print(f"  {pack.description}")
        c.print(f"  Status: {st.installed_count}/{st.total_count} installed ({pack.size_hint})")
        c.print(f"  Items:  {', '.join(pack.items)}")
        if st.missing_ids:
            c.print(f"  Missing: {', '.join(st.missing_ids)}")
            c.print(f"  Install: [bold]aegean library install {pack.id}[/bold]")
        return

    item = get_item(target)
    if item is None:
        raise fail(f"unknown library item {target!r}; try `aegean library search {target}`")

    if json_out:
        emit_json(item.to_dict())
        return

    c = console()
    c.print(f"[bold cyan]{item.id}[/bold cyan] — {item.title}")
    c.print(f"  Category:    {item.category} ({item.kind})")
    c.print(f"  Status:      {item.status}" + (f" ({format_size(item.bytes)})" if item.bytes else f" ({item.size_hint})"))
    if item.aliases:
        c.print(f"  Aliases:     {', '.join(item.aliases)}")
    if item.author:
        c.print(f"  Author:      {item.author}")
    if item.greek_title:
        c.print(f"  Greek title: {item.greek_title}")
    c.print(f"  License:     {item.license}")
    if item.description:
        c.print(f"  Notes:       {item.description}")
    if item.open_spec:
        c.print(f"  Open:        aegean info {item.open_spec}")
    if not item.installed:
        c.print(f"  Install:     [bold]aegean library install {item.id}[/bold]")
    elif item.removable:
        c.print(f"  Remove:      aegean library remove {item.id}")


@library_app.command("install")
def install_cmd(
    targets: list[str] = typer.Argument(
        ...,
        help=(
            "One or more packs, datasets, corpora, aliases, work IDs, titles, or author:<name> "
            "(e.g. biblical, nt-editions, lxx, damos, Iliad, tlg0012.tlg001, author:Homer)."
        ),
        autocompletion=shell_complete_library_install_target,
    ),
    force: bool = typer.Option(False, "--force", help="Re-download even if already installed."),
    json_out: bool = JSON_OPT,
) -> None:
    """Download and install corpora, Biblical bundles, packs, literary works, lexica, or models."""
    from aegean.data import FetchAborted
    from aegean.library import format_size, install

    def _on_progress(msg: str) -> None:
        if not json_out:
            print(msg, file=sys.stderr, flush=True)

    try:
        results = install(targets, force=force, progress=_on_progress)
    except LookupError as exc:
        raise fail(str(exc)) from None
    except FetchAborted as exc:
        raise fail(str(exc)) from None

    if json_out:
        emit_json([r.to_dict() for r in results])
        if any(r.status == "failed" for r in results):
            raise typer.Exit(1)
        return

    c = console()
    failed = 0
    for r in results:
        if r.status == "installed":
            sz = f" ({format_size(r.bytes)})" if r.bytes else ""
            c.print(f"[green]installed[/green] {r.id}{sz} — {r.title}")
        elif r.status == "already_installed":
            sz = f" ({format_size(r.bytes)})" if r.bytes else ""
            c.print(f"[dim]already installed[/dim] {r.id}{sz}")
        elif r.status == "bundled":
            c.print(f"[dim]bundled[/dim] {r.id} (always available offline)")
        else:
            failed += 1
            c.print(f"[red]failed[/red] {r.id}: {r.error}")
    if failed:
        raise typer.Exit(1)


@library_app.command("remove")
def remove_cmd(
    targets: list[str] | None = typer.Argument(
        None,
        help="Pack, dataset, corpus, work ID, title, or author:<name> to delete from disk.",
        autocompletion=shell_complete_library_remove_target,
    ),
    remove_all: bool = typer.Option(False, "--all", help="Delete every downloaded dataset and Greek work."),
    json_out: bool = JSON_OPT,
) -> None:
    """Delete downloaded datasets, corpora, works, commentaries, or packs to reclaim disk space."""
    from aegean.library import format_size, remove

    if not targets and not remove_all:
        raise fail("specify target(s) to remove or pass --all (see `aegean library list --downloaded`)")

    try:
        results = remove(targets, remove_all=remove_all)
    except (LookupError, ValueError) as exc:
        raise fail(str(exc)) from None

    total_reclaimed = sum(r.bytes_reclaimed for r in results)
    if json_out:
        emit_json(
            {
                "results": [r.to_dict() for r in results],
                "reclaimed_bytes": total_reclaimed,
            }
        )
        if any(r.status == "failed" for r in results):
            raise typer.Exit(1)
        return

    c = console()
    if not results:
        c.print("Nothing to remove: no downloaded items matched.")
        return

    failed = 0
    removed_count = 0
    for r in results:
        if r.status == "removed":
            removed_count += 1
            c.print(
                f"[green]removed[/green] {r.id} ({format_size(r.bytes_reclaimed)} reclaimed)"
            )
        elif r.status == "not_installed":
            c.print(f"[dim]not installed[/dim] {r.id}")
        elif r.status == "bundled":
            c.print(f"[yellow]bundled[/yellow] {r.id}: cannot be removed")
        else:
            failed += 1
            c.print(f"[red]failed[/red] {r.id}: {r.error}")
    if removed_count > 1:
        c.print(f"Reclaimed {format_size(total_reclaimed)} across {removed_count} items.")
    if failed:
        raise typer.Exit(1)
