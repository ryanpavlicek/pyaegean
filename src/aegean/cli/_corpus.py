"""Top-level corpus commands: info, load, show, search, query, stats, dispersion,
keyness, cache, balance, cite, export, combine, import, geo, sign, bridge."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from ._common import (
    CORPUS_ARG,
    JSON_OPT,
    RESULT_OPT,
    apply_meta_filters,
    console,
    emit_json,
    emit_result,
    fail,
    load_corpus,
    resolve_doc,
    table,
    write_corpus,
    writing,
)


def hint(message: str) -> None:
    """Print a one-line dim hint naming the next command (the `aegean geo` model)."""
    console().print(message, style="dim", markup=False)


SITE_OPT = typer.Option(None, "--site", help="Keep documents from this find-site.")
PERIOD_OPT = typer.Option(None, "--period", help="Keep documents from this period.")
SCRIBE_OPT = typer.Option(None, "--scribe", help="Keep documents by this scribe.")
SUPPORT_OPT = typer.Option(None, "--support", help="Keep documents on this support.")


def register(app: typer.Typer) -> None:
    app.command()(info)
    app.command()(load)
    app.command()(show)
    app.command()(search)
    app.command()(query)
    app.command()(stats)
    app.command()(dispersion)
    app.command()(keyness)
    app.command(name="cache")(cache_cmd)
    app.command()(balance)
    app.command()(cite)
    app.command()(export)
    app.command()(combine)
    app.command(name="import")(import_)
    app.command()(geo)
    app.command()(sign)
    app.command()(bridge)


def combine(
    sources: list[str] = typer.Argument(
        ..., help="Two or more corpora to merge: ids, .json/.db files, work ids, or '-'."
    ),
    output: Path = typer.Option(..., "--output", "-o", help="Destination .json or .db file."),
    on_conflict: str = typer.Option(
        "error", "--on-conflict",
        help="Duplicate document ids across sources: error, first, last, or suffix.",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Merge several corpora into one and save it; each source is resolved like any corpus
    argument (id, .json/.db file, Greek work id, or '-').

    Example — all of Homer in one database:
    aegean combine tlg0012.tlg001 tlg0012.tlg002 -o homer.db"""
    import aegean

    if on_conflict not in ("error", "first", "last", "suffix"):
        raise fail("--on-conflict must be 'error', 'first', 'last', or 'suffix'")
    loaded = [load_corpus(s) for s in sources]
    try:
        merged = aegean.combine(loaded, dedupe=on_conflict)
    except ValueError as exc:
        # the library error names the Python keyword; the CLI user has --on-conflict
        msg = str(exc).replace(
            "pass dedupe='first', 'last', or 'suffix'",
            "pass --on-conflict first, last, or suffix",
        )
        raise fail(msg) from None
    write_corpus(merged, output)
    print(f"wrote {len(merged)} documents to {output} (merged {len(loaded)} sources)",
          file=sys.stderr)
    if json_out:
        emit_json({"written": len(merged), "path": str(output), "sources": len(loaded)})


def import_(
    source: str = typer.Argument(
        ..., help="A .txt file, a folder of text files, or a .csv to import."
    ),
    output: Path = typer.Option(..., "--output", "-o", help="Destination .json or .db corpus file."),
    script: str = typer.Option(
        "greek", "--script", help="Script id for the text (greek, nt, lineara, linearb, …)."
    ),
    split: str = typer.Option(
        "whole", "--split",
        help="For text: 'whole' (one doc), 'paragraph' (blank-line blocks), or 'line'.",
    ),
    doc_id: str | None = typer.Option(None, "--id", help="Base document id (default: the file name)."),
    glob: str = typer.Option("*.txt", "--glob", help="For a folder: which files to import."),
    text_col: str = typer.Option("text", "--text-col", help="For CSV: the column holding the text."),
    id_col: str | None = typer.Option(None, "--id-col", help="For CSV: the column holding the id."),
    encoding: str = typer.Option("utf-8", "--encoding", help="Text encoding to read with."),
    workbench: bool = typer.Option(
        False, "--workbench", help="Treat SOURCE as a Linear A Workbench export (JSON) and import that."
    ),
    epidoc: bool = typer.Option(
        False, "--epidoc", help="Treat SOURCE as EpiDoc TEI (a file or a folder of .xml) and import it."
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Import your OWN text into a corpus you can then analyse, search, and export.

    SOURCE is a plain-text file, a folder of text files, or a CSV. The result is written to
    -o (.json or .db) and then works anywhere a corpus is accepted:

      aegean import myplato.txt -o myplato.json   &&   aegean stats myplato.json
      aegean import poems/ -o corpus.db --split line
      aegean import rows.csv -o corpus.json --text-col line --id-col id
      aegean import inscriptions/ -o ins.json --epidoc --script greek   # any EpiDoc TEI edition"""
    import json

    from aegean import io as aegean_io
    from aegean.core.script import registered_scripts

    known_scripts = sorted(set(registered_scripts()) | {"nt"})
    if script not in known_scripts:
        from aegean.core.resolve import suggest

        close = suggest(script, known_scripts, n=1)
        did = f" — did you mean {close[0]!r}?" if close else ""
        raise fail(f"unknown script {script!r}{did} (one of: {', '.join(known_scripts)})")
    p = Path(source)
    try:
        if workbench:
            corpus = aegean_io.from_workbench_export(p)
        elif epidoc:
            corpus = aegean_io.from_epidoc(p, script_id=script)
        elif p.is_dir():
            corpus = aegean_io.from_text_dir(
                p, script_id=script, glob=glob, split=split, encoding=encoding
            )
        elif p.suffix.lower() == ".csv":
            if id_col is not None:
                import csv as _csv

                with p.open(encoding=encoding, newline="") as fh:
                    header = next(_csv.reader(fh), [])
                if id_col not in header:
                    raise fail(
                        f"--id-col {id_col!r} is not a column of {p.name}; "
                        f"columns: {', '.join(header)}"
                    )
            corpus = aegean_io.from_csv(
                p, text_col=text_col, id_col=id_col, script_id=script, encoding=encoding
            )
        else:
            corpus = aegean_io.from_text_file(
                p, script_id=script, split=split, doc_id=doc_id, encoding=encoding
            )
    except json.JSONDecodeError as exc:
        raise fail(f"{source}: invalid JSON — {exc}") from None
    except UnicodeDecodeError as exc:
        raise fail(
            f"cannot decode {source} with encoding {encoding!r} ({exc}); "
            "try another --encoding (e.g. --encoding latin-1)"
        ) from None
    except (FileNotFoundError, NotADirectoryError, ValueError, LookupError) as exc:
        raise fail(str(exc)) from None
    write_corpus(corpus, output)
    print(f"wrote {len(corpus)} document(s) to {output}", file=sys.stderr)
    if json_out:
        emit_json({"written": len(corpus), "path": str(output), "source": source})
        return
    hint(f"explore it:  aegean stats {output}")


def info(corpus: str = CORPUS_ARG, json_out: bool = JSON_OPT) -> None:
    """Corpus overview: size, provenance, license, citation."""
    c = load_corpus(corpus)
    prov = c.provenance
    data = {
        "corpus": corpus,
        "documents": len(c),
        "words": sum(len(d.words) for d in c),
        "tokens": sum(len(d.tokens) for d in c),
        "signs_in_inventory": len(c.sign_inventory) if c.sign_inventory else 0,
        "source": prov.source if prov else "",
        "license": prov.license if prov else "",
        "citation": prov.cite() if prov else "",
    }
    if json_out:
        emit_json(data)
        return
    table(
        f"aegean corpus: {corpus}",
        ["field", "value"],
        [[k, str(v)] for k, v in data.items() if k != "corpus"],
    )


def load(
    corpus: str = CORPUS_ARG,
    site: str | None = SITE_OPT,
    period: str | None = PERIOD_OPT,
    scribe: str | None = SCRIBE_OPT,
    support: str | None = SUPPORT_OPT,
    output: Path | None = typer.Option(
        None, "--output", "-o",
        help="Save the (filtered) corpus to a .json or .db/.sqlite file (by extension).",
    ),
    limit: int = typer.Option(20, "--limit", "--top", help="Documents listed without --output (0 = all)."),
    json_out: bool = JSON_OPT,
) -> None:
    """Filter a corpus by metadata; list matches or save them as a reusable corpus."""
    c = apply_meta_filters(load_corpus(corpus), site, period, scribe, support)
    if output is not None:
        write_corpus(c, output)
        print(f"wrote {len(c)} documents to {output}", file=sys.stderr)
        if json_out:
            emit_json({"written": len(c), "path": str(output)})
        return
    rows = [
        {"id": d.id, "site": d.meta.site, "period": d.meta.period, "words": len(d.words)}
        for d in list(c)[: limit if limit > 0 else None]
    ]
    if json_out:
        emit_json({"matched": len(c), "documents": rows})
        return
    if not rows and any(v is not None for v in (site, period, scribe, support)):
        hint(
            f"0 matches — filters are exact; 'aegean load {corpus}' without filters "
            "shows the site/period values"
        )
        return
    table(
        f"{corpus}: {len(c)} matching document(s)" + (f" (showing {len(rows)})" if len(rows) < len(c) else ""),
        ["id", "site", "period", "words"],
        [[r["id"], str(r["site"]), str(r["period"]), str(r["words"])] for r in rows],
    )


def show(
    corpus: str = CORPUS_ARG,
    doc_id: str = typer.Argument(
        ...,
        help="Document id (HT13; for a Greek work the book alone works: 1). "
        "Case and spacing are forgiven.",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Display one document: metadata and line-by-line tokens."""
    c = load_corpus(corpus)
    doc = resolve_doc(c, corpus, doc_id)
    lines = [[doc.tokens[i].text for i in line] for line in doc.lines]
    if json_out:
        emit_json(
            {
                "id": doc.id,
                "script": doc.script_id,
                "meta": {
                    "site": doc.meta.site, "period": doc.meta.period,
                    "scribe": doc.meta.scribe, "support": doc.meta.support,
                    "findspot": doc.meta.findspot, "name": doc.meta.name,
                },
                "lines": lines,
            }
        )
        return
    meta_bits = [
        f"{k}={v}"
        for k, v in (
            ("site", doc.meta.site), ("period", doc.meta.period),
            ("scribe", doc.meta.scribe), ("support", doc.meta.support),
        )
        if v
    ]
    console().print(f"{doc.id}  {'  '.join(meta_bits)}", style="bold", markup=False)
    for n, line in enumerate(lines, 1):
        console().print(f"  {n}: {' '.join(line)}", markup=False)


def search(
    corpus: str = CORPUS_ARG,
    pattern: str = typer.Argument(..., help='Sign pattern, e.g. "KU-*-RO" (* = any one sign).'),
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Find words matching a wildcard sign pattern, with frequencies."""
    from aegean.analysis import word_matches_sign_pattern

    c = load_corpus(corpus)
    hits = [(w, n) for w, n in c.word_frequencies() if word_matches_sign_pattern(w, pattern)]
    payload = {"pattern": pattern, "matches": [{"word": w, "count": n} for w, n in hits]}
    if emit_result(payload, json_output=json_out, output=output):
        return
    if not hits:
        hint(
            f"no matches — '*' is one sign ('KU-*-RO'); "
            f"'aegean stats {corpus}' lists frequent words"
        )
        return
    table(f"{pattern!r}: {len(hits)} word(s)", ["word", "count"], [[w, str(n)] for w, n in hits])


def query(
    corpus: str = CORPUS_ARG,
    where: list[str] = typer.Option(
        [], "--where",
        help='A filter row "field=value" ANDed with the previous row; prefix the field with '
        '"!" to negate, or "or:" to OR it (e.g. --where site-is="Haghia Triada" '
        '--where or:word-prefix=KU). List the fields with `aegean query CORPUS --fields`.',
    ),
    output_kind: str = typer.Option(
        "inscriptions", "--output-kind", help="Result type: inscriptions or words."
    ),
    fields: bool = typer.Option(False, "--fields", help="List the queryable fields and exit."),
    output: Path | None = typer.Option(
        None, "--output", "-o",
        help="Save the matched inscriptions as a reusable corpus (.json or .db); "
        "inscriptions output only.",
    ),
    limit: int = typer.Option(
        25, "--limit", "--top",
        help="Rows listed, human and JSON alike (0 = all); JSON always carries the "
        "untruncated matched totals.",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Run the compound-query engine (text/prefix/sign-pattern/co-occurrence predicates)."""
    from aegean.analysis import FIELDS, FilterRow

    if fields:
        if json_out:
            emit_json({k: {"label": f.label, "scope": f.scope, "kind": f.kind} for k, f in FIELDS.items()})
        else:
            table("queryable fields", ["field", "label", "scope", "kind"],
                  [[k, f.label, f.scope, f.kind] for k, f in FIELDS.items()])
        return
    if output_kind not in ("inscriptions", "words"):
        raise fail("--output-kind must be 'inscriptions' or 'words'")
    rows = []
    for spec in where:
        if "=" not in spec:
            raise fail(f"bad --where {spec!r}; expected field=value")
        field, value = spec.split("=", 1)
        connector: str = "and"
        negate = False
        if field.startswith("or:"):
            connector, field = "or", field[3:]
        if field.startswith("!"):
            negate, field = True, field[1:]
        if field not in FIELDS:
            from aegean.core.resolve import suggest

            close = suggest(field, FIELDS, n=1)
            if close:
                raise fail(
                    f"unknown field {field!r} — did you mean {close[0]!r}? "
                    f"(`aegean query {corpus} --fields` lists all)"
                )
            raise fail(f"unknown field {field!r}; see `aegean query {corpus} --fields`")
        kind = FIELDS[field].kind
        parsed: object = value
        if kind == "number":
            try:
                parsed = int(value)
            except ValueError:
                raise fail(f"--where {field} expects a number, got {value!r}") from None
        elif kind == "boolean":
            parsed = value.lower() in ("1", "true", "yes")
        rows.append(FilterRow(field, parsed, connector="or" if connector == "or" else "and", negate=negate))
    c = load_corpus(corpus)
    res = c.query(rows, output_kind)
    if output is not None:
        if output_kind != "inscriptions":
            raise fail("--output saves inscriptions; drop --output-kind words")
        write_corpus(res.to_corpus(c), output)
        print(f"wrote {len(res.inscriptions)} inscriptions to {output}", file=sys.stderr)
        return
    cap = limit if limit > 0 else None
    if json_out:
        emit_json(
            {
                "description": res.description,
                "matched": {"inscriptions": len(res.inscriptions), "words": len(res.words)},
                "inscriptions": [d.id for d in res.inscriptions[:cap]],
                "words": [{"word": w, "count": n} for w, n in res.words[:cap]],
                "citation": res.cite() if res.provenance else "",
            }
        )
        return
    if not (res.inscriptions if output_kind == "inscriptions" else res.words):
        hint(
            "0 matches — values are exact ('site-is=Haghia Triada'); "
            f"'aegean query {corpus} --fields' lists the fields"
        )
        return
    if output_kind == "inscriptions":
        shown = res.inscriptions[:cap]
        table(
            f"{res.description or 'all'} → {len(res.inscriptions)} inscription(s)",
            ["id", "site", "words"],
            [[d.id, d.meta.site, str(len(d.words))] for d in shown],
        )
    else:
        shown_w = res.words[:cap]
        table(
            f"{res.description or 'all'} → {len(res.words)} word(s)",
            ["word", "count"],
            [[w, str(n)] for w, n in shown_w],
        )
    console().print(res.cite(), style="dim", markup=False)


def stats(
    corpus: str = CORPUS_ARG,
    signs: bool = typer.Option(False, "--signs", help="Sign frequencies instead of words."),
    top: int = typer.Option(20, "--top", "--limit", help="How many rows (0 = all)."),
    site: str | None = SITE_OPT,
    period: str | None = PERIOD_OPT,
    scribe: str | None = SCRIBE_OPT,
    support: str | None = SUPPORT_OPT,
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Frequency tables: words (default) or individual signs, optionally metadata-filtered."""
    c = apply_meta_filters(load_corpus(corpus), site, period, scribe, support)
    if signs:
        from collections import Counter

        counter: Counter[str] = Counter()
        for d in c:
            for t in d.tokens:
                for s in t.signs or (t.text.split("-") if "-" in t.text else [t.text]):
                    counter[s] += 1
        pairs = counter.most_common(top if top > 0 else None)
        title = f"{corpus}: top {len(pairs)} signs"
    else:
        pairs = c.word_frequencies()[: top if top > 0 else None]
        title = f"{corpus}: top {len(pairs)} words"
    payload = [{"item": w, "count": n} for w, n in pairs]
    if emit_result(payload, json_output=json_out, output=output):
        return
    table(title, ["item", "count"], [[w, str(n)] for w, n in pairs])


def dispersion(
    corpus: str = CORPUS_ARG,
    item: str | None = typer.Argument(None, help="One item; omit to rank the whole corpus."),
    signs: bool = typer.Option(False, "--signs", help="Sign dispersion instead of words."),
    top: int = typer.Option(20, "--top", "--limit", help="How many rows (ranking mode; 0 = all)."),
    min_frequency: int = typer.Option(2, "--min-frequency", help="Skip rarer items (ranking mode)."),
    site: str | None = SITE_OPT,
    period: str | None = PERIOD_OPT,
    scribe: str | None = SCRIBE_OPT,
    support: str | None = SUPPORT_OPT,
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """How evenly items spread across documents (Gries' DP; 0 = even, 1 = concentrated)."""
    from ..analysis import stats as _stats

    c = apply_meta_filters(load_corpus(corpus), site, period, scribe, support)
    kind = "signs" if signs else "words"
    try:
        rows = (
            [_stats.dispersion(c, item, kind=kind)]
            if item
            else _stats.dispersions(c, kind=kind, min_frequency=min_frequency, top=top)
        )
    except ValueError as e:
        raise fail(str(e)) from None
    payload = [vars(r) for r in rows]
    if emit_result(payload, json_output=json_out, output=output):
        return
    table(
        f"{corpus}: dispersion ({kind})",
        ["item", "freq", "range/parts", "DP", "DPnorm"],
        [
            [r.item, str(r.frequency), f"{r.range}/{r.parts}", f"{r.dp:.3f}", f"{r.dp_norm:.3f}"]
            for r in rows
        ],
    )


def keyness(
    corpus: str = CORPUS_ARG,
    reference: str | None = typer.Option(
        None, "--reference", help="Reference corpus name; omit to compare a subset vs the rest."
    ),
    site: str | None = SITE_OPT,
    period: str | None = PERIOD_OPT,
    scribe: str | None = SCRIBE_OPT,
    support: str | None = SUPPORT_OPT,
    signs: bool = typer.Option(False, "--signs", help="Sign keyness instead of words."),
    top: int = typer.Option(20, "--top", "--limit", help="How many rows (0 = all)."),
    min_target: int = typer.Option(2, "--min-target", help="Skip items rarer than this in both."),
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Key items of a (sub)corpus against a reference (log-likelihood G² + log-ratio).

    Either name a second corpus (--reference), or give metadata filters
    (--site/--period/...) to compare that subset against the rest of the same corpus.
    """
    from ..analysis import stats as _stats

    c = load_corpus(corpus)
    filtered = apply_meta_filters(c, site, period, scribe, support)
    if reference is not None:
        target, ref = filtered, load_corpus(reference)
        ref_label = reference
    else:
        if filtered is c:
            raise fail(
                "give --reference CORPUS, or a filter (--site/--period/…) to split this corpus"
            )
        target = filtered
        subset_ids = {d.id for d in filtered.documents}
        ref = [d for d in c.documents if d.id not in subset_ids]
        ref_label = "rest"
    kind = "signs" if signs else "words"
    try:
        rows = _stats.keyness(target, ref, kind=kind, min_target=min_target)[
            : top if top > 0 else None
        ]
    except ValueError as e:
        raise fail(str(e)) from None
    payload = [vars(r) for r in rows]
    if emit_result(payload, json_output=json_out, output=output):
        return
    table(
        f"{corpus}: keyness vs {ref_label} ({kind})",
        ["item", "target", "reference", "G2", "log-ratio", "p"],
        [
            [
                r.item,
                f"{r.target_count}/{r.target_total}",
                f"{r.reference_count}/{r.reference_total}",
                f"{r.log_likelihood:.2f}",
                f"{r.log_ratio:+.2f}",
                f"{r.p_value:.2g}",
            ]
            for r in rows
        ],
    )


def cache_cmd(
    clear: bool = typer.Option(False, "--clear", help="Wipe every cached entry."),
    json_out: bool = JSON_OPT,
) -> None:
    """Inspect (or --clear) the opt-in analysis cache.

    The cache is off by default; enable it per shell with PYAEGEAN_ANALYSIS_CACHE=1
    (or a path) so expensive analyses (dispersion, keyness, clustering) are reused
    across runs. Not the store of fetched corpora and models: that is
    `aegean data store`."""
    from ..cache import clear as _clear
    from ..cache import stats as _stats

    if clear:
        _clear()
    info = _stats()
    if json_out:
        emit_json(info)
        return
    if not info["enabled"]:
        console().print(
            "analysis cache: off — set PYAEGEAN_ANALYSIS_CACHE=1 (or a path) to enable",
            markup=False,
        )
        return
    console().print(
        f"analysis cache: on · {info['entries']} entr{'y' if info['entries'] == 1 else 'ies'} · "
        f"{info['path']}" + ("  (cleared)" if clear else ""),
        markup=False,
    )


def balance(
    corpus: str = CORPUS_ARG,
    doc_id: str | None = typer.Argument(None, help="One document; omit to sweep the corpus."),
    strict: bool = typer.Option(
        False, "--strict", help="Exit 1 if any checked total fails to balance."
    ),
    site: str | None = SITE_OPT,
    period: str | None = PERIOD_OPT,
    scribe: str | None = SCRIBE_OPT,
    support: str | None = SUPPORT_OPT,
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Accounting reconciliation: stated totals (KU-RO / TO-SO) vs summed items."""
    from aegean.analysis import balance_check

    c = apply_meta_filters(load_corpus(corpus), site, period, scribe, support)
    docs = [resolve_doc(c, corpus, doc_id)] if doc_id else list(c)
    results = []
    for d in docs:
        assert d is not None
        for chk in balance_check(d):
            results.append(
                {
                    "doc": d.id, "marker": chk.marker, "stated": chk.stated_total,
                    "computed": chk.computed_sum, "difference": chk.difference,
                    "items": chk.item_count, "balances": chk.balances,
                }
            )
    if not emit_result(results, json_output=json_out, output=output):
        if not results:
            hint(
                "no stated totals — balance reads accounting tablets (KU-RO / TO-SO): "
                "lineara, linearb, damos"
            )
        else:
            table(
                f"{corpus}: {len(results)} total line(s) checked",
                ["doc", "marker", "stated", "computed", "diff", "balances"],
                [
                    [str(r["doc"]), str(r["marker"]), str(r["stated"]), str(r["computed"]),
                     str(r["difference"]), "yes" if r["balances"] else "NO"]
                    for r in results
                ],
            )
    if strict and any(not r["balances"] for r in results):
        raise typer.Exit(code=1)


def cite(
    corpus: str = CORPUS_ARG,
    style: str = typer.Option("plain", "--style", help="plain, bibtex, or apa."),
    site: str | None = SITE_OPT,
    period: str | None = PERIOD_OPT,
    scribe: str | None = SCRIBE_OPT,
    support: str | None = SUPPORT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Cite the corpus — or, with filters, the exact subset — in one line."""
    c = apply_meta_filters(load_corpus(corpus), site, period, scribe, support)
    try:
        citation = c.cite(style)
    except ValueError as exc:
        raise fail(str(exc)) from None
    if json_out:
        emit_json({"corpus": corpus, "style": style, "citation": citation})
        return
    print(citation)


def export(
    corpus: str = CORPUS_ARG,
    fmt: str = typer.Option(
        ..., "--format", "-f", help="json, csv, parquet, epidoc, sqlite, or workbench."
    ),
    output: Path = typer.Option(..., "--output", "-o", help="Destination file."),
    level: str = typer.Option(
        "document", "--level",
        help="For csv/parquet: document, token, or word (token carries NT lemma/morph/Strong's/gloss).",
    ),
    site: str | None = SITE_OPT,
    period: str | None = PERIOD_OPT,
    scribe: str | None = SCRIBE_OPT,
    support: str | None = SUPPORT_OPT,
) -> None:
    """Export a (filtered) corpus: lossless JSON, tabular CSV/Parquet, EpiDoc TEI, or a SQLite DB.

    ``--level token`` (csv/parquet) emits one row per token, spreading any per-token
    annotations — the Greek NT's lemma/morph/Strong's/gloss — into columns."""
    if fmt not in ("json", "csv", "parquet", "epidoc", "sqlite", "workbench"):
        raise fail(f"unknown format {fmt!r}; use json, csv, parquet, epidoc, sqlite, or workbench")
    if level not in ("document", "token", "word"):
        raise fail(f"--level must be 'document', 'token', or 'word'; got {level!r}")
    c = apply_meta_filters(load_corpus(corpus), site, period, scribe, support)
    try:
        with writing(output):
            if fmt == "json":
                c.to_json(output)
            elif fmt == "csv":
                from aegean.io import to_csv

                to_csv(c, output, level=level)
            elif fmt == "parquet":
                from aegean.io import to_parquet

                to_parquet(c, output, level=level)
            elif fmt == "epidoc":
                from aegean.io import write_epidoc

                write_epidoc(c, output)
            elif fmt == "sqlite":
                from aegean.db import to_sqlite

                to_sqlite(c, output)
            else:
                from aegean.io import to_workbench

                to_workbench(c, output)
    except (ImportError, ValueError) as exc:  # a missing extra's pip hint, or a bad value
        raise fail(str(exc)) from None
    print(f"wrote {len(c)} documents to {output} ({fmt})", file=sys.stderr)


def geo(
    corpus: str = CORPUS_ARG,
    word: str | None = typer.Option(
        None, "--word", help="Map where this word is attested (per-site counts) instead of every site."
    ),
    level: str = typer.Option(
        "site", "--level", help="GeoJSON granularity (with --output): site or inscription."
    ),
    site: str | None = SITE_OPT,
    period: str | None = PERIOD_OPT,
    scribe: str | None = SCRIBE_OPT,
    support: str | None = SUPPORT_OPT,
    output: Path | None = typer.Option(
        None, "--output", "-o",
        help="Write GeoJSON (.json or .geojson) here instead of printing a table.",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Geographic view: find-site coordinates, or with --word the per-site attestations of one
    word (GeoJSON needs the \\[geo] extra; the table does not).

    Only provenanced inscription corpora yield rows (lineara, linearb, cypriot, cyprominoan,
    sigla, damos); alphabetic Greek corpora (greek, nt, work ids) carry no find-spot. --word
    matching is case-insensitive."""
    if level not in ("site", "inscription"):
        raise fail(f"--level must be 'site' or 'inscription'; got {level!r}")
    if output is not None and output.suffix.lower() not in (".json", ".geojson"):
        raise fail(f"output {output.name!r}: GeoJSON takes a .json or .geojson extension")
    c = apply_meta_filters(load_corpus(corpus), site, period, scribe, support)
    from aegean.geo import site_coordinates

    coords = site_coordinates()
    if word is not None:
        if output is not None:
            try:
                from aegean.geo import word_distribution

                gdf = word_distribution(c, word)
            except ImportError as exc:  # the missing extra's own pip-install one-liner
                raise fail(str(exc)) from None
            with writing(output):
                output.write_text(gdf.to_json(), encoding="utf-8")
            print(f"wrote {len(gdf)} features to {output}", file=sys.stderr)
            return
        from collections import Counter

        counts: Counter[str] = Counter()
        target = word.casefold()
        for d in c:
            if d.meta.site in coords and any(t.text.casefold() == target for t in d.words):
                counts[d.meta.site] += 1
        wrows = [
            {"site": s, "lat": coords[s].lat, "lon": coords[s].lon, "count": n}
            for s, n in counts.most_common()
        ]
        if json_out:
            emit_json(wrows)
            return
        if not wrows:
            print(f"{corpus}: {word!r} is not attested at any mapped find-site.")
            return
        table(
            f"{corpus}: {word!r} attested at {len(wrows)} located site(s)",
            ["site", "lat", "lon", "count"],
            [[str(r["site"]), str(r["lat"]), str(r["lon"]), str(r["count"])] for r in wrows],
        )
        return
    if output is not None:
        try:
            from aegean.geo import to_geodataframe

            gdf = to_geodataframe(c, level=level)
        except (ImportError, ValueError) as exc:  # missing extra, or a library-level bad value
            raise fail(str(exc)) from None
        with writing(output):
            output.write_text(gdf.to_json(), encoding="utf-8")
        print(f"wrote {len(gdf)} features to {output}", file=sys.stderr)
        return
    sites = {d.meta.site for d in c if d.meta.site}
    rows = [
        {
            "site": s, "lat": coords[s].lat, "lon": coords[s].lon,
            "pleiades": coords[s].pleiades or "", "contested": coords[s].contested or "",
        }
        for s in sorted(sites)
        if s in coords
    ]
    if json_out:
        emit_json(rows)
        return
    if not rows:
        print(
            f"{corpus}: no mapped find-sites. geo maps provenanced inscription corpora "
            "(lineara, linearb, cypriot, cyprominoan, sigla, damos); alphabetic Greek corpora "
            "carry no find-spot."
        )
        return
    table(
        f"{corpus}: {len(rows)} located site(s) of {len(sites)}",
        ["site", "lat", "lon", "pleiades", "contested"],
        [
            [str(r["site"]), str(r["lat"]), str(r["lon"]), str(r["pleiades"]),
             "disputed" if r["contested"] else ""]
            for r in rows
        ],
    )


def sign(
    script: str = typer.Argument(..., help="lineara, linearb, cypriot, or cyprominoan."),
    label: str = typer.Argument(..., help="Sign label (e.g. KU, AB01) or a single glyph."),
    json_out: bool = JSON_OPT,
) -> None:
    """Look up one sign in a script's inventory: glyph, codepoint, sound value."""
    c = load_corpus(script)
    inv = c.sign_inventory
    if inv is None:
        raise fail(f"{script!r} has no sign inventory")
    s = inv.by_label(label) if hasattr(inv, "by_label") else None
    if s is None:
        s = next((x for x in inv if x.label == label or x.glyph == label), None)
    if s is None:
        norm = label.upper()
        s = next((x for x in inv if x.label.upper() == norm), None)
    if s is None:
        from aegean.core.resolve import suggest

        labels = [x.label for x in inv]
        near = suggest(label, labels, n=5)
        folded = label.casefold()
        if folded:  # widen with case-folded prefix/substring candidates (the resolve_doc model)
            for cand in sorted(labels):
                if len(near) >= 5:
                    break
                if cand not in near and (folded in cand.casefold() or cand.casefold() in folded):
                    near.append(cand)
        close = f" close: {', '.join(near[:5])}." if near else ""
        raise fail(f"no sign {label!r} in the {script} inventory ({len(inv)} signs).{close}")
    data = {
        "label": s.label, "glyph": s.glyph or "",
        "codepoint": f"U+{s.codepoint:04X}" if s.codepoint is not None else "",
        "phonetic": s.phonetic or "", "attrs": dict(s.attrs),
    }
    if json_out:
        emit_json(data)
        return
    table(f"{script} sign {s.label}", ["field", "value"],
          [[k, str(v)] for k, v in data.items() if k != "attrs" and v] +
          [[f"attrs.{k}", str(v)] for k, v in s.attrs.items()])


def bridge(
    script: str = typer.Argument(..., help="linearb or cypriot."),
    word: str = typer.Argument(..., help="Transliterated word, e.g. po-me or pa-si-le-u-se."),
    json_out: bool = JSON_OPT,
) -> None:
    """Read a deciphered syllabic word as Greek (the Greek-reading bridge)."""
    if script == "linearb":
        from aegean.scripts.linearb.lexicon import gloss as _gloss, greek_reading
    elif script == "cypriot":
        from aegean.scripts.cypriot.lexicon import gloss as _gloss, greek_reading  # type: ignore[no-redef]
    else:
        raise fail("bridge supports the deciphered syllabic scripts: linearb, cypriot")
    reading = greek_reading(word)
    if reading is None:
        raise fail(f"{word!r} has no attested Greek reading in the bundled {script} lexicon")
    data = {"word": word, "greek": reading[0], "gloss": _gloss(word) or reading[1]}
    if json_out:
        emit_json(data)
        return
    print(f"{word} → {data['greek']}   ({data['gloss']})")
