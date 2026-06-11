"""Top-level corpus commands: info, load, show, search, query, stats, dispersion,
keyness, balance, cite, export, geo, sign, bridge."""

from __future__ import annotations

from pathlib import Path

import typer

from ._common import (
    CORPUS_ARG,
    JSON_OPT,
    apply_meta_filters,
    console,
    emit_json,
    fail,
    load_corpus,
    table,
)

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
    app.command()(balance)
    app.command()(cite)
    app.command()(export)
    app.command()(geo)
    app.command()(sign)
    app.command()(bridge)


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
        None, "--output", "-o", help="Write the (filtered) corpus as round-trippable JSON."
    ),
    limit: int = typer.Option(20, "--limit", help="Documents listed without --output."),
    json_out: bool = JSON_OPT,
) -> None:
    """Filter a corpus by metadata; list matches or export them as JSON."""
    c = apply_meta_filters(load_corpus(corpus), site, period, scribe, support)
    if output is not None:
        c.to_json(output)
        print(f"wrote {len(c)} documents to {output}")
        return
    rows = [
        {"id": d.id, "site": d.meta.site, "period": d.meta.period, "words": len(d.words)}
        for d in list(c)[: limit if limit > 0 else None]
    ]
    if json_out:
        emit_json({"matched": len(c), "documents": rows})
        return
    table(
        f"{corpus}: {len(c)} matching document(s)" + (f" (showing {len(rows)})" if len(rows) < len(c) else ""),
        ["id", "site", "period", "words"],
        [[r["id"], str(r["site"]), str(r["period"]), str(r["words"])] for r in rows],
    )


def show(
    corpus: str = CORPUS_ARG,
    doc_id: str = typer.Argument(..., help="Document id, e.g. HT13."),
    json_out: bool = JSON_OPT,
) -> None:
    """Display one document: metadata and line-by-line tokens."""
    c = load_corpus(corpus)
    doc = c.get(doc_id)
    if doc is None:
        raise fail(f"no document {doc_id!r} in {corpus!r}")
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
    json_out: bool = JSON_OPT,
) -> None:
    """Find words matching a wildcard sign pattern, with frequencies."""
    from aegean.analysis import word_matches_sign_pattern

    c = load_corpus(corpus)
    hits = [(w, n) for w, n in c.word_frequencies() if word_matches_sign_pattern(w, pattern)]
    if json_out:
        emit_json({"pattern": pattern, "matches": [{"word": w, "count": n} for w, n in hits]})
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
    limit: int = typer.Option(25, "--limit", help="Rows shown in human output."),
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
            raise fail(f"unknown field {field!r}; see `aegean query {corpus} --fields`")
        kind = FIELDS[field].kind
        parsed: object = value
        if kind == "number":
            parsed = int(value)
        elif kind == "boolean":
            parsed = value.lower() in ("1", "true", "yes")
        rows.append(FilterRow(field, parsed, connector="or" if connector == "or" else "and", negate=negate))
    c = load_corpus(corpus)
    res = c.query(rows, output_kind)
    if json_out:
        emit_json(
            {
                "description": res.description,
                "inscriptions": [d.id for d in res.inscriptions],
                "words": [{"word": w, "count": n} for w, n in res.words],
                "citation": res.cite() if res.provenance else "",
            }
        )
        return
    if output_kind == "inscriptions":
        shown = res.inscriptions[: limit if limit > 0 else None]
        table(
            f"{res.description or 'all'} → {len(res.inscriptions)} inscription(s)",
            ["id", "site", "words"],
            [[d.id, d.meta.site, str(len(d.words))] for d in shown],
        )
    else:
        shown_w = res.words[: limit if limit > 0 else None]
        table(
            f"{res.description or 'all'} → {len(res.words)} word(s)",
            ["word", "count"],
            [[w, str(n)] for w, n in shown_w],
        )
    console().print(res.cite(), style="dim", markup=False)


def stats(
    corpus: str = CORPUS_ARG,
    signs: bool = typer.Option(False, "--signs", help="Sign frequencies instead of words."),
    top: int = typer.Option(20, "--top", help="How many rows."),
    json_out: bool = JSON_OPT,
) -> None:
    """Frequency tables: words (default) or individual signs."""
    c = load_corpus(corpus)
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
    if json_out:
        emit_json([{"item": w, "count": n} for w, n in pairs])
        return
    table(title, ["item", "count"], [[w, str(n)] for w, n in pairs])


def dispersion(
    corpus: str = CORPUS_ARG,
    item: str | None = typer.Argument(None, help="One item; omit to rank the whole corpus."),
    signs: bool = typer.Option(False, "--signs", help="Sign dispersion instead of words."),
    top: int = typer.Option(20, "--top", help="How many rows (ranking mode)."),
    min_frequency: int = typer.Option(2, "--min-frequency", help="Skip rarer items (ranking mode)."),
    json_out: bool = JSON_OPT,
) -> None:
    """How evenly items spread across documents (Gries' DP; 0 = even, 1 = concentrated)."""
    from ..analysis import stats as _stats

    c = load_corpus(corpus)
    kind = "signs" if signs else "words"
    try:
        rows = (
            [_stats.dispersion(c, item, kind=kind)]
            if item
            else _stats.dispersions(c, kind=kind, min_frequency=min_frequency, top=top)
        )
    except ValueError as e:
        raise fail(str(e)) from None
    if json_out:
        emit_json([vars(r) for r in rows])
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
    top: int = typer.Option(20, "--top", help="How many rows."),
    min_target: int = typer.Option(2, "--min-target", help="Skip items rarer than this in both."),
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
    if json_out:
        emit_json([vars(r) for r in rows])
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


def balance(
    corpus: str = CORPUS_ARG,
    doc_id: str | None = typer.Argument(None, help="One document; omit to sweep the corpus."),
    strict: bool = typer.Option(
        False, "--strict", help="Exit 1 if any checked total fails to balance."
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Accounting reconciliation: stated totals (KU-RO / TO-SO) vs summed items."""
    from aegean.analysis import balance_check

    c = load_corpus(corpus)
    docs = [c.get(doc_id)] if doc_id else list(c)
    if doc_id and docs[0] is None:
        raise fail(f"no document {doc_id!r} in {corpus!r}")
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
    if json_out:
        emit_json(results)
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
) -> None:
    """Cite the corpus — or, with filters, the exact subset — in one line."""
    c = apply_meta_filters(load_corpus(corpus), site, period, scribe, support)
    try:
        print(c.cite(style))
    except ValueError as exc:
        raise fail(str(exc)) from None


def export(
    corpus: str = CORPUS_ARG,
    fmt: str = typer.Option(..., "--format", "-f", help="json, csv, parquet, or epidoc."),
    output: Path = typer.Option(..., "--output", "-o", help="Destination file."),
    site: str | None = SITE_OPT,
    period: str | None = PERIOD_OPT,
    scribe: str | None = SCRIBE_OPT,
    support: str | None = SUPPORT_OPT,
) -> None:
    """Export a (filtered) corpus: lossless JSON, tabular CSV/Parquet, or EpiDoc TEI."""
    c = apply_meta_filters(load_corpus(corpus), site, period, scribe, support)
    if fmt == "json":
        c.to_json(output)
    elif fmt == "csv":
        from aegean.io import to_csv

        to_csv(c, output)
    elif fmt == "parquet":
        from aegean.io import to_parquet

        to_parquet(c, output)
    elif fmt == "epidoc":
        from aegean.io import write_epidoc

        write_epidoc(c, output)
    else:
        raise fail(f"unknown format {fmt!r}; use json, csv, parquet, or epidoc")
    print(f"wrote {len(c)} documents to {output} ({fmt})")


def geo(
    corpus: str = CORPUS_ARG,
    level: str = typer.Option("site", "--level", help="site or inscription."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write GeoJSON here instead of printing a table."
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Geographic view: find-site coordinates (GeoJSON needs the [geo] extra)."""
    c = load_corpus(corpus)
    if output is not None:
        from aegean.geo import to_geodataframe

        gdf = to_geodataframe(c, level=level)
        output.write_text(gdf.to_json(), encoding="utf-8")
        print(f"wrote {len(gdf)} features to {output}")
        return
    from aegean.geo import site_coordinates

    sites = {d.meta.site for d in c if d.meta.site}
    coords = site_coordinates()
    rows = [
        {"site": s, "lat": coords[s].lat, "lon": coords[s].lon, "pleiades": coords[s].pleiades or ""}
        for s in sorted(sites)
        if s in coords
    ]
    if json_out:
        emit_json(rows)
        return
    table(
        f"{corpus}: {len(rows)} located site(s) of {len(sites)}",
        ["site", "lat", "lon", "pleiades"],
        [[str(r["site"]), str(r["lat"]), str(r["lon"]), str(r["pleiades"])] for r in rows],
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
        raise fail(f"no sign {label!r} in the {script} inventory ({len(inv)} signs)")
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
