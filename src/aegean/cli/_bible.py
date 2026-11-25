"""``aegean bible …`` — the Biblical & Koine Greek specialist CLI suite.

Covers multi-edition Greek New Testament reading and variant comparison, early
2nd–5th c. CE manuscript witnesses (*nomina sacra* and diplomatic MES),
Strong's / Extended Strong's lexicon and root trees, word studies, concordance
search, Septuagint (LXX) reading and Psalm-number conversion, and Greek
patristic commentaries (NT *Catenae* and Origen).

All commands work in the shell, in ``aegean repl``, and in the TUI ``:``
console, and every command supports ``--json`` for machine-readable output.
"""

from __future__ import annotations

from typing import Any

import typer

from ._common import console, emit_json, fail

bible_app = typer.Typer(
    help=(
        "Biblical & Koine Greek specialist tools: Greek NT editions, early manuscripts, "
        "Strong's lexicon, word studies, concordance, Septuagint (LXX), and patristic Catenae."
    ),
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _format_root_lines(node: dict[str, Any], prefix: str = "") -> list[str]:
    sid = node.get("strongs", "")
    lemma = node.get("lemma", "")
    gloss = node.get("gloss", "")
    label = f"{sid} {lemma}".strip()
    if gloss:
        label += f" — {gloss}"
    lines = [f"{prefix}{label}"]
    children = node.get("roots") or []
    for i, child in enumerate(children):
        last = i == len(children) - 1
        branch = "└─ " if last else "├─ "
        ext = "   " if last else "│  "
        sub = _format_root_lines(child, prefix=prefix + ext)
        if sub:
            lines.append(f"{prefix}{branch}{sub[0][len(prefix + ext):]}")
            lines.extend(sub[1:])
    return lines


@bible_app.command("read")
def read_cmd(
    book: str = typer.Argument(..., help="Book name or abbreviation (e.g. John, Rom, Gen, Ps, Wis)."),
    ref: str | None = typer.Argument(None, help="Chapter or verse range (e.g. 1, 1.1-18, 3.16)."),
    edition: str = typer.Option(
        "nestle1904",
        "--edition",
        "-e",
        help="Greek NT edition: nestle1904, sblgnt, srgnt, byz, or tr.",
    ),
    lxx: bool = typer.Option(False, "--lxx", help="Read from the Septuagint (LXX) instead of the NT."),
    interlinear: bool = typer.Option(
        False,
        "--interlinear",
        "-i",
        help="Print word-by-word interlinear table (surface, lemma, morph, Strong's, gloss).",
    ),
    offline: bool = typer.Option(False, "--offline", help="Never fetch over the network (use local cache/bundled sample)."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Read a Greek New Testament or Septuagint (LXX) passage."""
    import aegean.biblical as bib

    try:
        corp = (
            bib.load_lxx(book, ref=ref, offline=offline)
            if lxx
            else bib.load_nt(book, ref=ref, edition=edition, offline=offline)
        )
    except Exception as exc:
        raise fail(str(exc)) from None

    if json_out:
        verses: list[dict[str, Any]] = []
        for doc in corp:
            by_ref: dict[str, list[dict[str, Any]]] = {}
            for tok in doc.tokens:
                vkey = str(tok.annotations.get("ref") or tok.line_no or "")
                by_ref.setdefault(vkey, []).append(
                    {"text": tok.text, **{k: v for k, v in tok.annotations.items()}}
                )
            for vkey, toks in by_ref.items():
                vlabel = vkey.rpartition(".")[2] if "." in vkey else vkey
                vnum: int | str = int(vlabel) if vlabel.isdigit() else vlabel
                verses.append(
                    {
                        "document": doc.id,
                        "verse": vnum,
                        "ref": vkey,
                        "text": " ".join(t["text"] for t in toks),
                        "tokens": toks,
                    }
                )
        emit_json(
            {
                "book": book,
                "ref": ref,
                "source": "lxx" if lxx else edition,
                "citation": getattr(corp.provenance, "citation", ""),
                "verses": verses,
            }
        )
        return

    c = console()
    from rich.table import Table

    title = getattr(corp.provenance, "citation", "") or f"{book} {ref or ''}".strip()
    c.print(f"[bold cyan]{title}[/bold cyan]")
    for doc in corp:
        if interlinear:
            table = Table(title=doc.id, show_lines=False)
            table.add_column("Ref", style="dim")
            table.add_column("Surface", style="bold")
            table.add_column("Lemma", style="green")
            table.add_column("Morph", style="magenta")
            table.add_column("Strong's", style="cyan")
            table.add_column("Gloss")
            for tok in doc.tokens:
                ann = tok.annotations
                table.add_row(
                    str(ann.get("ref", tok.line_no or "")),
                    tok.text,
                    str(ann.get("lemma", "")),
                    str(ann.get("morph", "")),
                    str(ann.get("strongs", "")),
                    str(ann.get("gloss", "")),
                )
            c.print(table)
        else:
            c.print(f"\n[bold]{doc.meta.name or doc.id}[/bold]")
            by_ref_txt: dict[str, list[str]] = {}
            for tok in doc.tokens:
                vkey = str(tok.annotations.get("ref") or tok.line_no or "")
                vlabel = vkey.rpartition(".")[2] if "." in vkey else vkey
                by_ref_txt.setdefault(vlabel, []).append(tok.text)
            for vlabel, words in by_ref_txt.items():
                prefix = f"[dim]{vlabel}[/dim] " if vlabel else ""
                c.print(f"  {prefix}{' '.join(words)}")


@bible_app.command("compare")
def compare_cmd(
    book: str = typer.Argument(..., help="NT book name (e.g. John, Matt, Rom)."),
    ref: str = typer.Argument(..., help="Verse or range (e.g. 1.18, 1.1-5)."),
    editions: str | None = typer.Option(
        None,
        "--editions",
        "-e",
        help="Comma-separated editions (default: nestle1904,sblgnt,srgnt,byz,tr).",
    ),
    offline: bool = typer.Option(False, "--offline", help="Do not fetch missing assets over the network."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Compare a Greek NT passage across editions with word-level variant diffs."""
    import aegean.biblical as bib

    ed_list = [e.strip() for e in editions.split(",") if e.strip()] if editions else None
    try:
        cmp = bib.compare_editions(book, ref, editions=ed_list, offline=offline)
    except Exception as exc:
        raise fail(str(exc)) from None

    if json_out:
        emit_json(cmp.to_dict())
        return

    c = console()
    c.print(
        f"[bold cyan]{cmp.book} {cmp.ref}[/bold cyan] — "
        f"{len(cmp.verses)} verse(s), {cmp.variant_verse_count} with textual variants"
    )
    for v in cmp.verses:
        status = "[green]identical[/green]" if v.identical else f"[yellow]{len(v.variants)} variant(s)[/yellow]"
        c.print(f"\n[bold]{v.ref}[/bold]  ({status})")
        for ed, txt in v.texts.items():
            c.print(f"  [cyan]{ed:10s}[/cyan]  {txt}")
        for diff in v.variants:
            lhs = " ".join(diff.base_words) or "∅"
            rhs = " ".join(diff.edition_words) or "∅"
            c.print(f"    [yellow]Δ {diff.edition}[/yellow] ({diff.kind}): {lhs} → {rhs}")


@bible_app.command("witnesses")
def witnesses_cmd(
    book: str = typer.Argument(..., help="NT book name (e.g. John, Rom, 1Pet)."),
    ref: str = typer.Argument(..., help="Verse or range (e.g. 1.18, 18.37-38)."),
    sigla: str | None = typer.Option(
        None,
        "--sigla",
        "-s",
        help="Comma-separated sigla/names (e.g. P66,P75,01,03,A,D).",
    ),
    hand: str = typer.Option("original", "--hand", help="Scribal hand: original or corrected."),
    diplomatic: bool = typer.Option(False, "--diplomatic", "-d", help="Show raw CNTR MES diplomatic transcription."),
    no_expand: bool = typer.Option(False, "--no-expand", help="Keep nomina sacra abbreviated (=θσ, =ιυ)."),
    offline: bool = typer.Option(False, "--offline", help="Do not fetch missing assets over the network."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Compare extant 2nd–5th century CE Greek NT manuscripts for a passage."""
    import aegean.biblical as bib

    sig_list = [s.strip() for s in sigla.split(",") if s.strip()] if sigla else None
    try:
        rows = bib.compare_witnesses(
            book,
            ref,
            sigla=sig_list,
            hand=hand,
            expand_nomina_sacra=not no_expand,
            offline=offline,
        )
    except Exception as exc:
        raise fail(str(exc)) from None

    if json_out:
        emit_json([r.to_dict() for r in rows])
        return

    c = console()
    for vc in rows:
        c.print(f"\n[bold cyan]{vc.ref}[/bold cyan] ({len(vc.witnesses)} extant early witness(es), hand={hand})")
        for w in vc.witnesses:
            text = w.reading.diplomatic if diplomatic else w.reading.readable
            c.print(f"  [bold]{w.siglum:4s}[/bold] [dim]({w.alias}, {w.century})[/dim]  {text}")
            if w.reading.nomina_sacra and not diplomatic:
                ns = ", ".join(f"{a}→{e}" for a, e in w.reading.nomina_sacra)
                c.print(f"       [dim]nomina sacra: {ns}[/dim]")
            if w.reading.corrections:
                corrs = ", ".join(f"{o or '∅'} → {n or '∅'}" for o, n in w.reading.corrections)
                c.print(f"       [dim]corrections: {corrs}[/dim]")


@bible_app.command("strongs")
def strongs_cmd(
    query: str = typer.Argument(..., help="Strong's ID (G3056, 3056), Greek lemma (λόγος), or English gloss."),
    roots: bool = typer.Option(False, "--roots", "-r", help="Show recursive etymological root tree."),
    search: bool = typer.Option(False, "--search", "-s", help="Search entries by Greek/transliteration/English gloss."),
    fetch: bool = typer.Option(False, "--fetch", help="Fetch the full 11,142-entry Extended Strong's asset if not cached."),
    limit: int = typer.Option(15, "--limit", "--top", "-n", help="Maximum hits when searching (0 = all)."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Look up or search Strong's & Extended Strong's Greek Lexicon entries."""
    import aegean.biblical as bib

    try:
        if search:
            hits = bib.search_strongs(query, limit=limit, allow_fetch=fetch)
            if json_out:
                emit_json([h.to_dict() for h in hits])
                return
            c = console()
            from rich.table import Table

            table = Table(title=f"Strong's search: {query!r} ({len(hits)} hit(s))")
            table.add_column("Strong's", style="cyan")
            table.add_column("Lemma", style="bold")
            table.add_column("Translit", style="dim")
            table.add_column("Gloss")
            for h in hits:
                table.add_row(h.strongs, h.lemma, h.translit, h.gloss)
            c.print(table)
            return

        entry = bib.strongs_entry(query, allow_fetch=fetch)
        if entry is None:
            raise fail(f"no Strong's Greek entry matched {query!r}")
        tree = bib.strongs_roots(entry.strongs, allow_fetch=False) if roots else None
    except typer.Exit:
        raise
    except Exception as exc:
        raise fail(str(exc)) from None

    if json_out:
        out = entry.to_dict()
        if tree is not None:
            out["root_tree"] = tree
        emit_json(out)
        return

    c = console()
    c.print(f"[bold cyan]{entry.strongs}[/bold cyan]  [bold]{entry.lemma}[/bold]  [dim]{entry.translit}  {entry.morph}[/dim]")
    c.print(f"  [green]Gloss:[/green] {entry.gloss}")
    if entry.definition and entry.definition != entry.gloss:
        c.print(f"  [bold]Definition:[/bold] {entry.definition[:600]}")
    if entry.derivation:
        c.print(f"  [bold]Derivation:[/bold] {entry.derivation}")
    if entry.hebrew:
        c.print(f"  [bold]Hebrew eq.:[/bold] {', '.join(entry.hebrew)}")
    if entry.kjv_def:
        c.print(f"  [dim]KJV usage: {entry.kjv_def}[/dim]")
    c.print(f"  [dim]Source: {entry.source}[/dim]")
    if tree is not None:
        c.print("\n[bold]Root family tree:[/bold]")
        for line in _format_root_lines(tree):
            c.print(f"  {line}")


@bible_app.command("word-study")
def word_study_cmd(
    query: str = typer.Argument(..., help="Strong's ID (G3056, 26) or Greek lemma (λόγος, ἀγάπη)."),
    book: str | None = typer.Option(None, "--book", "-b", help="Restrict concordance to one NT book."),
    limit: int = typer.Option(15, "--limit", "--top", "-n", help="Maximum concordance verses to display (0 = all)."),
    offline: bool = typer.Option(False, "--offline", help="Use local cache / bundled sample without network."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Run a unified Koine Greek word study (lexicon, roots, NT distribution, morphology, concordance)."""
    import aegean.biblical as bib

    try:
        ws = bib.word_study(query, book=book, limit=limit, offline=offline)
    except Exception as exc:
        raise fail(str(exc)) from None

    if json_out:
        emit_json(ws.to_dict())
        return

    c = console()
    c.print(f"[bold cyan]Word Study: {ws.lemma}[/bold cyan]  [dim]({ws.strongs or 'no Strongs'} · {ws.scope})[/dim]")
    if ws.entry is not None:
        c.print(f"  [green]Gloss:[/green] {ws.entry.gloss}")
        if ws.entry.derivation:
            c.print(f"  [bold]Derivation:[/bold] {ws.entry.derivation}")
    if ws.roots and ws.roots.get("roots"):
        c.print("  [bold]Roots:[/bold]")
        for line in _format_root_lines(ws.roots):
            c.print(f"    {line}")
    if ws.lexicon_entries:
        for lname, gloss in ws.lexicon_entries.items():
            c.print(f"  [magenta]{lname}:[/magenta] {gloss}")
    c.print(f"\n  [bold]Occurrences:[/bold] {ws.total_occurrences}")
    if ws.by_book:
        top_books = ", ".join(f"{k} ({v})" for k, v in list(ws.by_book.items())[:10])
        c.print(f"  [bold]By book:[/bold] {top_books}")
    if ws.by_morph:
        top_morph = ", ".join(f"{k} ({v})" for k, v in list(ws.by_morph.items())[:8])
        c.print(f"  [bold]Morphology:[/bold] {top_morph}")
    if ws.occurrences:
        c.print(f"\n  [bold]Sample concordance ({len(ws.occurrences)} of {ws.total_occurrences}):[/bold]")
        for hit in ws.occurrences:
            c.print(f"    [cyan]{hit.ref:12s}[/cyan] [{hit.morph}] {hit.verse_text}")


@bible_app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Search query (lemma, surface text, Strong's ID, Robinson morph, or gloss)."),
    by: str = typer.Option("lemma", "--by", help="Match field: lemma, text, strongs, morph, or gloss."),
    book: str | None = typer.Option(None, "--book", "-b", help="Restrict to one NT or LXX book."),
    section: str | None = typer.Option(None, "--section", help="Restrict LXX search to one section (Pentateuch, Wisdom, ...)."),
    edition: str = typer.Option("nestle1904", "--edition", "-e", help="NT edition."),
    lxx: bool = typer.Option(False, "--lxx", help="Search the Septuagint (LXX) instead of the New Testament."),
    limit: int = typer.Option(25, "--limit", "--top", "-n", help="Maximum hits to return (0 = all)."),
    offline: bool = typer.Option(False, "--offline", help="Use local cache / bundled sample without network."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Search the Greek New Testament or Septuagint (LXX) concordance."""
    import aegean.biblical as bib

    if lxx:
        try:
            lxx_hits = bib.search_lxx(
                query, book=book, section=section, limit=limit, offline=offline
            )
        except Exception as exc:
            raise fail(str(exc)) from None
        if json_out:
            emit_json([h.to_dict() for h in lxx_hits])
            return
        c = console()
        from rich.table import Table

        table = Table(title=f"Septuagint (LXX) Concordance: {query!r} ({len(lxx_hits)} hit(s))")
        table.add_column("Ref", style="cyan")
        table.add_column("Matched", style="bold green")
        table.add_column("Verse")
        for lh in lxx_hits:
            table.add_row(lh.ref, ", ".join(lh.matched_words[:3]), lh.verse_text[:110])
        c.print(table)
        return

    try:
        hits = bib.search_bible(query, by=by, book=book, edition=edition, limit=limit, offline=offline)
    except Exception as exc:
        raise fail(str(exc)) from None

    if json_out:
        emit_json([h.to_dict() for h in hits])
        return

    c = console()
    from rich.table import Table

    table = Table(title=f"Greek NT Concordance: {by}={query!r} ({len(hits)} hit(s))")
    table.add_column("Ref", style="cyan")
    table.add_column("Form", style="bold")
    table.add_column("Lemma", style="green")
    table.add_column("Morph", style="magenta")
    table.add_column("Verse")
    for h in hits:
        table.add_row(h.ref, h.surface, h.lemma, h.morph, h.verse_text[:100])
    c.print(table)


@bible_app.command("commentary")
def commentary_cmd(
    book: str | None = typer.Argument(None, help="Biblical book name (e.g. John, Matt, Rom, Gen, Ps)."),
    kind: str | None = typer.Option(None, "--kind", "-k", help="Filter by 'catena' or 'origen'."),
    read: bool = typer.Option(False, "--read", help="Fetch and print sections of the commentary text."),
    search: str | None = typer.Option(None, "--search", "-s", help="Search commentary text for a Greek term (e.g. λόγος)."),
    work_id: str | None = typer.Option(None, "--work-id", help="Explicit TLG work ID (e.g. tlg4102.tlg005)."),
    ref: str | None = typer.Option(None, "--ref", help="Optional section reference when reading."),
    limit: int = typer.Option(5, "--limit", "--top", "-n", help="Maximum excerpts/sections when reading or searching (0 = all)."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """List, read, or search Greek patristic biblical commentaries (NT Catenae & Origen)."""
    import aegean.biblical as bib

    try:
        if read or search:
            if book is None and work_id is None:
                raise fail("--read / --search requires a BOOK name or --work-id")
            excerpts = bib.commentary_excerpt(
                book or "John",
                work_id=work_id,
                kind=kind,
                ref=ref,
                query=search,
                limit=limit,
            )
            if json_out:
                emit_json([e.to_dict() for e in excerpts])
                return
            c = console()
            if not excerpts:
                c.print("[dim]No matching commentary sections found.[/dim]")
                return
            head = excerpts[0]
            c.print(f"[bold cyan]{head.author} — {head.title}[/bold cyan]  [dim]({head.work_id})[/dim]")
            for ex in excerpts:
                tag = f"  [green](matched: {', '.join(ex.matched_words)})[/green]" if ex.matched_words else ""
                c.print(f"\n[bold]§ {ex.section_id}[/bold]{tag}\n  {ex.text}")
            return

        rows = bib.patristic_commentaries(book, kind=kind)
    except typer.Exit:
        raise
    except Exception as exc:
        raise fail(str(exc)) from None

    if json_out:
        emit_json(rows)
        return

    c = console()
    from rich.table import Table

    table = Table(title=f"Greek Patristic Commentaries ({len(rows)} volume(s))")
    table.add_column("Book", style="cyan")
    table.add_column("Work ID", style="dim")
    table.add_column("Author", style="green")
    table.add_column("Title")
    for r in rows:
        table.add_row(r["book"], r["work_id"], r["author"], r["title"])
    c.print(table)


@bible_app.command("books")
def books_cmd(
    collection: str = typer.Argument(
        "nt",
        help="What to list: 'nt' (27 books), 'lxx' (55 books), 'editions' (5), or 'witnesses' (13).",
    ),
    section: str | None = typer.Option(None, "--section", help="Optional LXX section filter (Pentateuch, Wisdom, ...)."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """List available NT books, Septuagint (LXX) books, NT editions, or early manuscript witnesses."""
    import aegean.biblical as bib

    col = collection.strip().lower()
    if col == "nt":
        rows = bib.nt_books()
    elif col == "lxx":
        rows = bib.lxx_books(section=section)
    elif col == "editions":
        rows = bib.nt_editions()
    elif col == "witnesses":
        rows = bib.witnesses()
    else:
        raise fail(f"unknown collection {collection!r}; expected 'nt', 'lxx', 'editions', or 'witnesses'")

    if json_out:
        emit_json(rows)
        return

    c = console()
    from rich.table import Table

    if col == "nt":
        table = Table(title="Greek New Testament Books (27)")
        table.add_column("OSIS", style="cyan")
        table.add_column("Aliases")
        for r in rows:
            table.add_row(r["name"], ", ".join(r["aliases"]))
    elif col == "lxx":
        table = Table(title=f"Septuagint (LXX) Books ({len(rows)})")
        table.add_column("Name", style="cyan")
        table.add_column("Title", style="bold")
        table.add_column("Section", style="green")
        table.add_column("Work ID", style="dim")
        for r in rows:
            table.add_row(r["name"], r["title"], r["section"], r["work_id"])
    elif col == "editions":
        table = Table(title="Greek New Testament Editions (5)")
        table.add_column("ID", style="cyan")
        table.add_column("Edition", style="bold")
        table.add_column("License", style="dim")
        for r in rows:
            table.add_row(r["id"], r["name"], r["license"])
    else:
        table = Table(title="Early Greek NT Manuscript Witnesses (13)")
        table.add_column("Siglum", style="cyan")
        table.add_column("Alias", style="bold")
        table.add_column("Manuscript")
        table.add_column("Date", style="green")
        table.add_column("Text Type", style="dim")
        for r in rows:
            table.add_row(r["siglum"], r["alias"], r["name"], r["century"], r["text_type"])
    c.print(table)


@bible_app.command("psalm")
def psalm_cmd(
    number: int = typer.Argument(..., help="Psalm number to convert (LXX 1–151 or MT 1–150)."),
    from_system: str = typer.Option("mt", "--from", help="Input numbering system: 'mt' (Masoretic/English) or 'lxx' (Septuagint)."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Convert Psalm numbers between Masoretic (Hebrew/English) and Septuagint (LXX) numbering."""
    import aegean.biblical as bib

    src = from_system.strip().lower()
    try:
        if src == "mt":
            mapped = bib.psalm_mt_to_lxx(number)
            target = "lxx"
        elif src == "lxx":
            mapped = bib.psalm_lxx_to_mt(number)
            target = "mt"
        else:
            raise ValueError(f"--from must be 'mt' or 'lxx', got {from_system!r}")
    except Exception as exc:
        raise fail(str(exc)) from None

    if json_out:
        emit_json({"from": src, "input": number, "to": target, "psalms": list(mapped)})
        return

    c = console()
    if not mapped:
        c.print(f"[cyan]LXX Psalm {number}[/cyan] has no Masoretic counterpart (extra-canonical in MT).")
    else:
        rhs = ", ".join(str(n) for n in mapped)
        c.print(f"[cyan]{src.upper()} Psalm {number}[/cyan] ↔ [bold green]{target.upper()} Psalm {rhs}[/bold green]")
