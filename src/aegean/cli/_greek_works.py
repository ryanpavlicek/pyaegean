"""Literary work, catalog, and New Testament loading commands for ``aegean greek``."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from ._common import (
    JSON_OPT,
    RESULT_OPT,
    console,
    emit_json,
    emit_result,
    fail,
    table,
    to_plain,
    write_corpus,
)


def _work_all(
    author: str | None,
    *,
    source: str,
    limit: int,
    dry_run: bool,
    assume_yes: bool,
    json_out: bool,
) -> None:
    """`greek work all [author]`: bulk-fetch every catalogue work by an author (or all)."""
    import os

    from aegean.data import DataNotAvailableError, FetchAborted
    from aegean.greek import GitHubRateLimitError, WorkFetchResult
    from aegean.greek import catalog as greek_catalog
    from aegean.greek import fetch_works, list_fetched_works

    if source not in ("auto", "perseus", "first1k"):
        raise fail("--source must be auto, perseus, or first1k")
    src = None if source == "auto" else source
    rows = greek_catalog(author=author, source=src)
    fetched_ids = {w["id"] for w in list_fetched_works()}
    pending = [r for r in rows if r["id"] not in fetched_ids]

    if not rows:
        if json_out:
            emit_json({"mode": "all", "author": author, "matched": 0, "works": []})
        else:
            who = f"author {author!r}" if author else "the catalogue"
            hint = f" — try `aegean greek catalog {author}`" if author else ""
            print(f"no works match {who}{hint}")
        return

    if dry_run:
        preview = [
            {"id": r["id"], "author": r["author"], "title": r["title"],
             "status": "cached" if r["id"] in fetched_ids else "pending"}
            for r in rows
        ]
        if json_out:
            emit_json({"mode": "all", "author": author, "matched": len(rows), "dry_run": True,
                       "to_fetch": len(pending), "cached": len(rows) - len(pending), "works": preview})
            return
        table(f"greek work all {author or ''} (dry run)".strip(),
              ["id", "author", "title", "status"],
              [[p["id"], p["author"], p["title"], p["status"]] for p in preview])
        print(f"\n{len(pending)} to fetch, {len(rows) - len(pending)} already cached. "
              "Run without --dry-run to fetch.")
        return

    if len(pending) > 50 and not assume_yes and not json_out:
        has_token = bool(os.environ.get("PYAEGEAN_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN"))
        rate = ("5,000/hr (token set)" if has_token
                else "~60/hr unauthenticated — set PYAEGEAN_GITHUB_TOKEN to raise it")
        if sys.stdin.isatty():
            if not typer.confirm(f"Fetch {len(pending)} works? Each needs a GitHub API call ({rate})."):
                raise fail("aborted")
        else:
            raise fail(f"{len(pending)} works exceeds the safe unauthenticated batch — "
                       "pass --yes to confirm or --limit N to cap")

    lim = limit if limit > 0 else None
    results: list[WorkFetchResult] = []
    stopped: str | None = None
    note: str | None = None

    def progress(i: int, total: int, w: dict[str, str]) -> None:
        print(f"[{i}/{total}] {w['id']} ({w.get('author', '')} — {w.get('title', '')})…",
              file=sys.stderr)

    # --json stays quiet on stderr so its stdout is a clean, parseable document
    on_progress = None if json_out else progress
    try:
        for res in fetch_works(author=author, works=rows, source=src, limit=lim, on_progress=on_progress):
            results.append(res)
            if not json_out:
                print(f"    {res.status}" + (f": {res.error}" if res.error else ""), file=sys.stderr)
    except GitHubRateLimitError as exc:
        stopped, note = "rate_limit", str(exc)
    except FetchAborted:
        stopped = "aborted"
    except KeyboardInterrupt:
        stopped, note = "aborted", "interrupted — already-cached works are kept"
    except DataNotAvailableError as exc:
        stopped, note = "failed", str(exc)

    summary = {
        "mode": "all", "author": author, "matched": len(rows),
        "fetched": sum(r.status == "fetched" for r in results),
        "cached": sum(r.status == "cached" for r in results),
        "failed": sum(r.status == "failed" for r in results),
        "stopped": stopped,
        "works": [to_plain(r) for r in results],
    }
    if note:
        summary["message"] = note
    if json_out:
        emit_json(summary)
        return
    table(f"greek work all {author or ''}".strip(),
          ["id", "author", "title", "status"],
          [[r.id, r.author, r.title, r.status] for r in results])
    print(f"\nfetched {summary['fetched']}, cached {summary['cached']}, failed {summary['failed']}"
          + (f" — stopped: {stopped}" if stopped else ""), file=sys.stderr)
    if note:
        print(note, file=sys.stderr)


def _bare_textpart(ref: str) -> bool:
    """A ref that names one plain top-level textpart — the only shape a whole-work
    ``aegean show`` can reconstruct. Milestones (a letter: '17a'/'1447a10'), nested
    parts and line ranges (a '.'/'-': '1.2'/'1.1-1.50') and sibling lists (a ',')
    address parts that reload as synthetic documents show cannot resolve."""
    return not any(ch in ref for ch in ",.-") and not any(ch.isalpha() for ch in ref)


def work(
    work_id: str | None = typer.Argument(
        None, help="CTS-style work id, e.g. tlg0012.tlg001 (Iliad); or 'all' to bulk-fetch by author."
    ),
    author: str | None = typer.Argument(
        None, help="With 'all': fetch every work by this author (case-insensitive)."
    ),
    ref: str | None = typer.Option(
        None, "--ref",
        help="Select a section by the work's citation scheme: '1' (book/section), '1.2' "
        "(chapter), '1.1-1.50' (lines), a margin milestone ('17a' Stephanus, or '1447a10' "
        "Bekker for the span to the next marked line); comma list for siblings. A wrong ref "
        "names the work's declared scheme; greek.citation_scheme(id) reports it.",
    ),
    source: str = typer.Option("auto", "--source", help="auto, perseus, or first1k."),
    edition: str | None = typer.Option(None, "--edition", help="Pick a specific edition file."),
    limit: int = typer.Option(
        0, "--limit", "--top", help="With 'all': cap NEW downloads (0 = all)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="With 'all': show what would be fetched; fetch nothing."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="With 'all': skip the confirmation prompt for large sets."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o",
        help="Save the corpus to a .json or .db/.sqlite file (by extension).",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Fetch a real Greek work (Perseus canonical-greekLit / First1KGreek, CC BY-SA).

    The TEI file is fetched once to the cache (pinned commit = reproducible),
    parsed into one document per book/chapter — or, with --ref, just the
    addressed textpart or verse line-range.

    `aegean greek work all AUTHOR` bulk-fetches every work by an author (case-
    insensitive), e.g. `aegean greek work all homer`; `aegean greek works
    --downloaded` lists what is already on disk.

    Don't know the id? `aegean greek works` lists well-known ones; any Perseus
    canonical-greekLit / First1KGreek id works (browse them at scaife.perseus.org)."""
    from aegean.data import DataNotAvailableError
    from aegean.greek import list_fetched_works, load_work

    if work_id is not None and work_id.lower() == "all":
        if output is not None:
            raise fail("-o is not used with 'all' (works land in the cache; "
                       "save one with `aegean greek work <id> -o file.json`)")
        _work_all(author, source=source, limit=limit, dry_run=dry_run,
                  assume_yes=yes, json_out=json_out)
        return
    if author is not None:
        raise fail("the second argument is only used with 'all' "
                   "(single-work section selection uses --ref)")
    if work_id is None:
        raise fail(
            "give a work id (e.g. tlg0012.tlg001) — `aegean greek works` lists "
            "well-known ids; `aegean greek catalog NAME` searches ~1,800; "
            "`aegean greek work all AUTHOR` fetches a whole author"
        )
    if source not in ("auto", "perseus", "first1k"):
        raise fail("--source must be auto, perseus, or first1k")
    was_cached = any(w["id"] == work_id for w in list_fetched_works())
    try:
        c = load_work(work_id, ref=ref, source=source, edition=edition)
    except (DataNotAvailableError, ValueError) as exc:
        exit1 = fail(str(exc))
        if "." not in work_id or "tlg" not in work_id.lower():
            # the id isn't even work-shaped: the catalog searches by name
            print(f"search it by name:  aegean greek catalog {work_id}", file=sys.stderr)
        raise exit1 from None
    if output is not None:
        write_corpus(c, output)
        print(f"wrote {len(c)} documents to {output}", file=sys.stderr)
        return
    path = next((w["path"] for w in list_fetched_works() if w["id"] == work_id), None)
    summary = {
        "work": work_id,
        "documents": len(c),
        "tokens": sum(len(d.tokens) for d in c),
        "first": c.documents[0].id if len(c) else "",
        "name": c.documents[0].meta.name if len(c) else "",
        "source": c.provenance.source if c.provenance else "",
        "data_version": c.provenance.data_version if c.provenance else "",
        "cached": was_cached,
        "path": path,
    }
    if json_out:
        emit_json(summary)
        return
    table(f"{work_id}", ["field", "value"],
          [[k, str(v)] for k, v in summary.items() if k not in ("work", "cached", "path")])
    if path is not None:
        status = "already cached at" if was_cached else "downloaded to"
        print(f"{status}  {path}", file=sys.stderr)
    if len(c):
        section = str(summary["first"]).split(":", 1)[-1]
        if ref is None or _bare_textpart(ref):
            # a plain top-level textpart resolves against a whole-work `aegean show`
            print(f"read it:  aegean show {work_id} {section}")
        else:
            # milestone/nested/range/comma refs address parts a reloaded whole-work `show`
            # cannot reconstruct; this call reproduces exactly this selection (the full ref)
            print(f'read it:  aegean.greek.load_work("{work_id}", ref="{ref}")  (Python)')
    if c.provenance is not None and c.provenance.citation:
        print(f"cite it:  {c.provenance.citation}")


def nt(
    book: str | None = typer.Argument(
        None, help="NT book name, e.g. John (omit to load all 27 books)."
    ),
    passage: str | None = typer.Argument(
        None, help="Chapter or range to read: '1', '1-3', or '1.1-1.18' (verses)."
    ),
    ref: str | None = typer.Option(
        None, "--ref", help="Alias for the passage argument ('1', '1-3', '1.1-1.18')."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o",
        help="Save the corpus to a .json or .db/.sqlite file (by extension).",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Read the Greek New Testament (Nestle 1904): gold lemma / morph / Strong's + Koine gloss.

    Name a BOOK, and optionally a chapter or range, to read it:
    `aegean greek nt John 1`, `aegean greek nt Matt 1-3`. With no BOOK, loads all 27 books
    (a summary). Tokens carry per-word annotations — `aegean export <file> -f csv --level token`
    spreads them into columns. `aegean greek nt-books` lists the book names."""
    from aegean.data import DataNotAvailableError
    from aegean.greek import load_nt

    if passage is not None and ref is not None:
        raise fail("give the passage as a positional OR --ref, not both")
    selection = passage or ref
    try:
        c = load_nt(book, ref=selection)
    except (DataNotAvailableError, ValueError, KeyError, LookupError) as exc:
        # the library speaks Python (greek.nt_books()); the CLI speaks CLI
        msg = str(exc).replace(
            "greek.nt_books() lists all 27", "`aegean greek nt-books` lists all 27"
        )
        raise fail(msg) from None
    if output is not None:
        write_corpus(c, output)
        print(f"wrote {len(c)} documents to {output}", file=sys.stderr)
        return
    summary = {
        "scope": book or "whole NT",
        "ref": selection or "",
        "documents": len(c),
        "tokens": sum(len(d.tokens) for d in c),
        "first": c.documents[0].id if len(c) else "",
        "source": c.provenance.source if c.provenance else "",
        "data_version": c.provenance.data_version if c.provenance else "",
    }
    if json_out:
        emit_json(summary)
        return
    # No book -> a summary (rendering all 27 books is not useful). A named book -> read the text.
    if book is None:
        table("Greek NT", ["field", "value"], [[k, str(v)] for k, v in summary.items()])
        if len(c):
            print("read a book:  aegean greek nt John 1   (a chapter or range, e.g. Matt 1-3)")
        return
    if not len(c):
        raise fail("that selection has no text")
    header = f"{summary['scope']} {selection or ''}".strip()
    console().print(
        f"{header}  ({summary['documents']} chapter"
        f"{'' if summary['documents'] == 1 else 's'}, {summary['tokens']} tokens)",
        style="bold", markup=False,
    )
    for doc in c:
        console().print(doc.meta.name or doc.id, style="bold cyan", markup=False)
        for line in doc.lines:
            if not line:
                continue
            verse = doc.tokens[line[0]].line_no
            label = str(verse) if verse is not None else "-"
            text = " ".join(doc.tokens[i].text for i in line)
            console().print(f"  {label}: {text}", markup=False)


def works(
    downloaded: bool = typer.Option(
        False, "--downloaded", "--local",
        help="List Greek works already downloaded to the cache, instead of the curated set.",
    ),
    remove: str | None = typer.Option(
        None, "--remove", help="Delete one downloaded work by id (e.g. tlg0012.tlg001)."
    ),
    remove_author: str | None = typer.Option(
        None, "--remove-author",
        help="Delete every downloaded work by an author (case-insensitive substring).",
    ),
    remove_all: bool = typer.Option(
        False, "--remove-all", help="Delete ALL downloaded Greek works from the cache."
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """List a curated catalog of well-known Greek works loadable with `aegean greek work`.

    Every id here is verified. It is a starting point, not the whole canon — `work` takes
    any Perseus canonical-greekLit / First1KGreek id; browse them at scaife.perseus.org.

    `--downloaded` lists instead the works already fetched to your local cache. Delete
    downloaded works with `--remove <id>`, `--remove-author <name>`, or `--remove-all`
    (the only way a fetched work leaves disk; re-fetch with `aegean greek work <id>`)."""
    if remove is not None or remove_author is not None or remove_all:
        from aegean.greek import list_fetched_works, remove_fetched_works

        before = {w["id"]: w for w in list_fetched_works()}
        removed = remove_fetched_works(
            [remove] if remove else None, author=remove_author, remove_all=remove_all
        )
        if json_out:
            emit_json({"removed": removed})
            return
        if not removed:
            if remove:
                print(f"{remove!r} is not a downloaded work "
                      "(`aegean greek works --downloaded` lists what is).")
            elif remove_author:
                print(f"no downloaded works by an author matching {remove_author!r} "
                      "(`aegean greek works --downloaded` lists what is).")
            else:
                print("no Greek works are downloaded.")
            return
        for rid in removed:
            meta = before.get(rid, {})
            label = f"{meta.get('author', '')} — {meta.get('title', '')}".strip(" —") or rid
            print(f"removed {rid}  ({label})")
        print(f"\nremoved {len(removed)} work{'' if len(removed) == 1 else 's'} from the cache.")
        return

    if downloaded:
        from aegean.greek import list_fetched_works

        fw = list_fetched_works()
        if json_out:
            emit_json({"downloaded": fw})
            return
        if not fw:
            print("No Greek works downloaded yet. Fetch one with `aegean greek work <id>`, "
                  "or a whole author with `aegean greek work all <author>`.")
            return

        def _sz(n: int) -> str:
            return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{n / 1024:.0f} KB"

        table("Downloaded Greek works", ["id", "author", "title", "source", "size"],
              [[w["id"], w["author"], w["title"], w["source"], _sz(w["bytes"])] for w in fw])
        print(f"\n{len(fw)} work{'' if len(fw) == 1 else 's'} in the cache. "
              "Read one with `aegean show <id> <section>`.")
        return

    from aegean.greek import popular_works

    ws = popular_works()
    if json_out:
        emit_json(ws)
        return
    table("Popular Greek works", ["id", "author", "title"],
          [[w["id"], w["author"], w["title"]] for w in ws])
    print("\nLoad one with, e.g.:  aegean greek work tlg0012.tlg001 --ref 1.1-1.10")
    print("This is a curated subset — search the full ~1,800-work canon with `aegean greek catalog`")


def catalog(
    query: str | None = typer.Argument(
        None, help="Free-text filter across id, author, and title (English or Greek)."
    ),
    author: str | None = typer.Option(None, "--author", "-a", help="Filter by author (substring)."),
    title: str | None = typer.Option(None, "--title", "-t", help="Filter by title (English or Greek)."),
    source: str | None = typer.Option(None, "--source", help="Limit to 'perseus' or 'first1k'."),
    limit: int = typer.Option(
        40, "--limit", "--top", "-n",
        help="Max rows (0 = all); --json and -o keep the untruncated count in 'matched'.",
    ),
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Search the full discovery catalogue (~1,800 works) of loadable Greek texts.

    Every work with a Greek edition in Perseus canonical-greekLit + First1KGreek — far more
    than the 25 in `aegean greek works`. Bundled metadata, no network. Pass any id to
    `aegean greek work`.

    Examples:  aegean greek catalog sappho   |   aegean greek catalog --author plato"""
    from aegean.greek import catalog as greek_catalog

    if source is not None and source not in ("perseus", "first1k"):
        raise fail("--source must be perseus or first1k")
    rows = greek_catalog(query, author=author, title=title, source=source)
    total = len(rows)
    shown = rows if limit <= 0 else rows[:limit]
    if emit_result({"matched": total, "works": shown}, json_output=json_out, output=output):
        return
    if not total:
        print("No works match. Try a looser filter, or browse https://scaife.perseus.org")
        return
    table(
        f"Greek works ({total} match{'' if total == 1 else 'es'})",
        ["id", "author", "title", "greek", "src"],
        [[r["id"], r["author"], r["title"], r.get("greek_title", ""), r["source"]] for r in shown],
    )
    if limit > 0 and total > limit:
        print(f"\n… and {total - limit} more — narrow with --author/--title, or --limit 0 to list all (-o to save).")
    print("Load one with, e.g.:  aegean greek work tlg0012.tlg001 --ref 1.1-1.10")


def nt_books_cmd(json_out: bool = JSON_OPT) -> None:
    """List the 27 books of the Greek New Testament and the names `gloss-nt`/load_nt accept."""
    from aegean.greek import nt_books

    books = nt_books()
    if json_out:
        emit_json(books)
        return
    table("New Testament books (Nestle 1904)", ["book", "accepted names"],
          [[b["name"], ", ".join(b["aliases"])] for b in books])
    print("\nLoad one:  aegean greek nt John --ref 1.1-1.18")

def register(greek_app: typer.Typer) -> None:
    """Attach the literary-work and NT catalog commands to ``greek_app``."""
    greek_app.command("work")(work)
    greek_app.command("nt")(nt)
    greek_app.command("works")(works)
    greek_app.command("catalog")(catalog)
    greek_app.command("nt-books")(nt_books_cmd)
