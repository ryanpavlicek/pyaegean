"""An MCP server exposing pyaegean to agents (Claude Code and other MCP clients).

The ``[mcp]`` extra installs the Model Context Protocol SDK; ``aegean-mcp`` then runs a
stdio MCP server that wraps the toolkit's read/analysis surface as tools, so an agent can
use pyaegean without writing Python:

* corpora: ``list_corpora``, ``corpus_info``, ``show_document``, ``search_signs``,
  ``balance_accounts``, ``query_corpus`` (the compound query engine), ``cite_corpus``
  (plain / BibTeX / APA, exact subsets included), ``geo_sites`` (find-site coordinates,
  Pleiades ids, per-site word attestations), ``corpus_diagnose`` (a descriptive
  corpus-health report), and ``data_status`` (the local data store);
* Greek: ``greek_pipeline``, ``greek_explain`` (each token's lemma evidence class in
  plain language), ``greek_scan``, ``greek_catalog`` (the ~1,800-work discovery
  catalogue), ``greek_work`` (a work's text by catalogue id, summarized with a capped
  preview), ``greek_gloss`` (the registry dictionaries), and ``koine_gloss`` (the
  bundled Dodson NT lexicon).

Two conventions hold across every tool. Corpora and works are addressed by **registry
name or catalogue work id only**: no tool accepts a filesystem path, so the server
never reads or writes arbitrary local files (a deliberate invariant, not an omission).
Domain misses (an unknown corpus, document, work, dictionary, style, or query field)
return a structured ``{"error": ...}`` payload carrying a did-you-mean hint (for a
work, a pointer to ``greek_catalog``) instead of raising, so an agent can recover in
one step; raised exceptions are reserved for genuine faults. A tool that may need
remote data says so in its description: ``greek_work`` texts and the non-bundled
``greek_gloss`` dictionaries download into the local data store on first use and are
offline after (``data_status`` shows the store).

The tool functions are plain, JSON-returning callables (independently testable);
``build_server`` registers them with FastMCP, imported lazily so ``import aegean`` never
pulls the MCP SDK.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

__all__ = [
    "TOOLS",
    "build_server",
    "main",
    "list_corpora",
    "corpus_info",
    "show_document",
    "search_signs",
    "balance_accounts",
    "query_corpus",
    "cite_corpus",
    "geo_sites",
    "data_status",
    "greek_pipeline",
    "greek_explain",
    "greek_scan",
    "greek_catalog",
    "greek_work",
    "greek_gloss",
    "koine_gloss",
    "corpus_diagnose",
]


def _did_you_mean(name: str, candidates: Iterable[str]) -> str:
    """A parenthetical did-you-mean fragment for an unknown-name error, or ``""``."""
    from .core.resolve import suggest

    close = suggest(name, candidates, n=2)
    if not close:
        return ""
    return f" (did you mean {' or '.join(repr(c) for c in close)}?)"


def _load_corpus(corpus: str) -> tuple[Any, dict[str, Any] | None]:
    """Load a registry corpus, forgiving case; ``(None, {"error": ...})`` when unknown."""
    import aegean
    from .core.corpus import _LOADERS

    ids = sorted(_LOADERS)
    if corpus not in _LOADERS:
        by_fold = {k.casefold(): k for k in ids}
        folded = by_fold.get(corpus.casefold())
        if folded is None:
            return None, {
                "error": f"unknown corpus {corpus!r}{_did_you_mean(corpus, ids)}; "
                f"available: {', '.join(ids)}"
            }
        corpus = folded
    # A fetch-on-demand corpus (damos, sigla) is downloaded on first load; a cold-cache
    # offline/HTTP/checksum failure must surface as the structured error every tool that
    # routes through this helper already handles, not a raw exception.
    from .data import DataNotAvailableError

    try:
        return aegean.load(corpus), None
    except DataNotAvailableError as exc:
        return None, {"error": f"corpus {corpus!r} is not available: {exc}"}


def _find_doc(c: Any, corpus: str, doc_id: str) -> tuple[Any, dict[str, Any] | None]:
    """Resolve a document forgivingly; ``(None, {"error": ...})`` with near hints on a miss."""
    from .core.resolve import resolve_document

    doc, near = resolve_document(c, doc_id)
    if doc is not None:
        return doc, None
    msg = f"no document {doc_id!r} in {corpus!r}"
    if near:
        msg += f"; close: {', '.join(near)}"
    return None, {"error": f"{msg} ({len(c)} documents)"}


def list_corpora() -> list[str]:
    """List the corpora that can be loaded by name.

    Five are bundled and load offline; the rest ('damos', 'nt', 'sigla', 'isicily', 'iip',
    'iospe', 'igcyr', 'edh', 'ddbdp') download into the local data store on first use
    (``data_status`` shows what is already stored)."""
    from .core.corpus import _LOADERS

    return sorted(_LOADERS)


def corpus_info(corpus: str) -> dict[str, Any]:
    """Overview of a corpus: script, document count, source, license, and a citation.

    ``corpus`` is a name from ``list_corpora`` (e.g. 'lineara', 'damos', 'nt'). Loading a
    fetch-on-demand corpus ('nt', 'damos', 'sigla', 'isicily', 'iip', 'iospe', 'igcyr',
    'edh', 'ddbdp') downloads it on first use (a one-time fetch into the local data
    store); check ``data_status`` first to see what is already stored. 'ddbdp' is heavy:
    loading it materialises 57k papyri (prefer ``aegean db search ddbdp`` from the
    shell)."""
    c, err = _load_corpus(corpus)
    if err is not None:
        return err
    prov = c.provenance
    return {
        "corpus": corpus,
        "script_id": c.script_id,
        "documents": len(c),
        "source": prov.source if prov else "",
        "license": prov.license if prov else "",
        "citation": prov.cite() if prov else "",
    }


def show_document(corpus: str, doc_id: str) -> dict[str, Any]:
    """One document's metadata and text, line by line.

    ``doc_id`` is e.g. 'HT13'; case and spacing are forgiven ('ht13', 'py ta 641'
    resolve), and a miss reports the closest ids. A source-aligned document also
    includes its exact ``source_text`` and one alignment object per token."""
    c, err = _load_corpus(corpus)
    if err is not None:
        return err
    doc, err = _find_doc(c, corpus, doc_id)
    if err is not None:
        return err
    from ._view import _form_state_fields

    result: dict[str, Any] = {
        "id": doc.id,
        "site": doc.meta.site,
        "period": doc.meta.period,
        "support": doc.meta.support,
        "scribe": doc.meta.scribe,
        "lines": [[t.text for t in line] for line in doc.line_tokens],
        "transcription": doc.transcription,
        # ``lines`` is the historical text-only shape.  ``tokens`` is additive
        # and carries editorial form state without replacing or mutating it.
        "tokens": [],
    }
    for token in doc.tokens:
        form_fields = _form_state_fields(token.form_state)
        row: dict[str, Any] = {
            "text": token.text,
            "kind": token.kind.value,
            "status": token.status.value,
            **form_fields,
        }
        if token.form_state is not None:
            row["form_state"] = token.form_state.to_dict()
        result["tokens"].append(row)
    if doc.source_text is not None:
        result["source_text"] = doc.source_text
        result["token_alignment"] = [
            (
                {
                    "document_id": token.alignment.document_id,
                    "sentence_id": token.alignment.sentence_id,
                    "source_token_id": token.alignment.source_token_id,
                    "original_text": token.alignment.original_text,
                    "start_char": token.alignment.start_char,
                    "end_char": token.alignment.end_char,
                    "whitespace_before": token.alignment.whitespace_before,
                    "normalized_text": token.alignment.normalized_text,
                    "normalization_ops": list(token.alignment.normalization_ops),
                }
                if token.alignment is not None
                else None
            )
            for token in doc.tokens
        ]
    return result


def search_signs(
    corpus: str, pattern: str, limit: int = 50
) -> list[dict[str, Any]] | dict[str, Any]:
    """Words matching a wildcard sign pattern (e.g. 'KU-*-RO'), with frequencies.

    ``limit`` caps the matches; limit <= 0 returns every match."""
    from .analysis import word_matches_sign_pattern

    c, err = _load_corpus(corpus)
    if err is not None:
        return err
    out: list[dict[str, Any]] = []
    for word, count in c.word_frequencies():
        if word_matches_sign_pattern(word, pattern):
            out.append({"word": word, "count": count})
            if limit > 0 and len(out) >= limit:
                break
    return out


def balance_accounts(
    corpus: str, doc_id: str | None = None
) -> list[dict[str, Any]] | dict[str, Any]:
    """Accounting reconciliation: each stated total (KU-RO / TO-SO) vs the summed items.

    Returns one row per total marker (whole corpus, or one ``doc_id``, forgivingly
    matched): ``doc``, ``marker``, ``stated`` (the written total), ``computed`` (the summed
    items or subtotals), ``difference`` (computed minus stated), ``items`` (the count fed
    into the sum), and ``balances``. An empty list means the document(s) carry no total
    markers. The rows are the shared :func:`aegean._view.balance_rows` mapping, so this
    tool, the ``aegean balance`` command, and the terminal UI cannot disagree."""
    from ._view import balance_rows

    c, err = _load_corpus(corpus)
    if err is not None:
        return err
    if doc_id is not None:
        doc, err = _find_doc(c, corpus, doc_id)
        if err is not None:
            return err
        docs = [doc]
    else:
        docs = list(c.documents)
    rows: list[dict[str, Any]] = []
    for doc in docs:
        rows.extend(balance_rows(doc))
    return rows


def query_corpus(
    corpus: str,
    where: list[dict[str, Any]],
    output_kind: str = "inscriptions",
    limit: int = 50,
) -> dict[str, Any]:
    """Run the compound query engine over a corpus and cite the exact result set.

    Each ``where`` row is ``{"field", "value"}`` plus optional ``"connector"``
    ('and'/'or', default 'and') and ``"negate"`` (default false); rows chain in order,
    and an empty list matches the whole corpus. Fields: id-contains, site-is, scribe-is,
    period-is, support-is, has-image, has-annotation, ins-contains-word (inscription
    scope); word-contains, word-prefix, word-suffix, word-min-syllables,
    word-max-syllables, word-contains-sign, word-cooccurs-with, word-sign-pattern (word
    scope). ``output_kind`` is 'inscriptions' or 'words'; a word's count is its document
    frequency (how many distinct inscriptions carry it), not its token frequency.
    ``limit`` caps the returned id/word lists (limit <= 0 returns all); the totals are
    always the full counts. ``citation`` cites exactly this result set."""
    from .analysis import FIELDS, FilterRow

    c, err = _load_corpus(corpus)
    if err is not None:
        return err
    if output_kind not in ("inscriptions", "words"):
        return {
            "error": f"unknown output_kind {output_kind!r}; choose 'inscriptions' or 'words'"
        }
    rows: list[FilterRow] = []
    for spec in where:
        if not isinstance(spec, dict) or "field" not in spec or "value" not in spec:
            return {
                "error": "each where row needs 'field' and 'value' "
                "(optional 'connector' and 'negate')"
            }
        field = str(spec["field"])
        if field not in FIELDS:
            return {
                "error": f"unknown field {field!r}{_did_you_mean(field, FIELDS)}; "
                f"fields: {', '.join(FIELDS)}"
            }
        connector = spec.get("connector") or "and"
        if connector not in ("and", "or"):
            return {"error": f"unknown connector {connector!r}; choose 'and' or 'or'"}
        value: Any = spec["value"]
        kind = FIELDS[field].kind
        if kind == "number":
            try:
                value = int(value)
            except (TypeError, ValueError):
                return {"error": f"field {field!r} takes a number; got {spec['value']!r}"}
        elif kind == "boolean":
            value = value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes")
        elif not isinstance(value, str):
            value = str(value)
        neg_raw = spec.get("negate", False)
        # Forgiving bool, like the boolean value coercion above: a raw bool() would
        # read the JSON string "false"/"no"/"0" as True and silently invert the query.
        negate = neg_raw if isinstance(neg_raw, bool) else str(neg_raw).strip().lower() in (
            "1", "true", "yes",
        )
        rows.append(
            FilterRow(
                field,
                value,
                connector="or" if connector == "or" else "and",
                negate=negate,
            )
        )
    res = c.query(rows, output_kind)
    cap = None if limit <= 0 else limit
    return {
        "description": res.description or "all",
        "total_inscriptions": len(res.inscriptions),
        "total_words": len(res.words),
        "inscriptions": [d.id for d in res.inscriptions[:cap]],
        "words": [{"word": w, "count": n} for w, n in res.words[:cap]],
        "citation": res.cite() if res.provenance else "",
    }


def cite_corpus(
    corpus: str,
    style: str = "plain",
    site: str | None = None,
    period: str | None = None,
    scribe: str | None = None,
    support: str | None = None,
) -> dict[str, Any]:
    """Cite a corpus (or, with metadata filters, the exact subset) for a paper.

    ``style`` is 'plain' (one line), 'bibtex' (a @misc entry), or 'apa'. Any of ``site``,
    ``period``, ``scribe``, ``support`` filters the corpus first (exact match, combined
    with AND); the citation then names the subset, so it states exactly what was used.
    ``documents`` is the cited document count."""
    c, err = _load_corpus(corpus)
    if err is not None:
        return err
    meta = {
        k: v
        for k, v in (("site", site), ("period", period), ("scribe", scribe), ("support", support))
        if v is not None
    }
    if meta:
        c = c.filter(**meta)
    try:
        citation = c.cite(style)
    except ValueError as exc:
        return {"error": str(exc)}
    return {
        "corpus": corpus,
        "style": style,
        "filters": meta,
        "documents": len(c),
        "citation": citation,
    }


def geo_sites(corpus: str, word: str | None = None) -> dict[str, Any]:
    """Find-site geography for a corpus: coordinates (WGS84), Pleiades ids, and the
    contested-provenance flag; with ``word``, the per-site attestation counts of that
    word (case-insensitive) instead.

    Bundled gazetteer, offline. Only the Aegean inscription corpora yield sites
    (lineara, linearb, cypriot, cyprominoan, sigla, damos); alphabetic Greek corpora
    (greek, nt) carry no find-spot, and the Greek epigraphy corpora record find-places
    outside the Aegean gazetteer, so they yield no rows. A non-empty ``contested`` value
    is the reason a find-spot is disputed; treat such sites as unverified provenance."""
    from .geo import site_coordinates

    c, err = _load_corpus(corpus)
    if err is not None:
        return err
    coords = site_coordinates()
    if word is not None:
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
        payload: dict[str, Any] = {"corpus": corpus, "word": word, "sites": wrows}
        if not wrows:
            payload["note"] = f"{word!r} is not attested at any mapped find-site"
        return payload
    sites = {d.meta.site for d in c if d.meta.site}
    rows = [
        {
            "site": s,
            "lat": coords[s].lat,
            "lon": coords[s].lon,
            "pleiades": coords[s].pleiades,
            "pleiades_uri": coords[s].pleiades_uri,
            "contested": coords[s].contested,
        }
        for s in sorted(sites)
        if s in coords
    ]
    payload = {"corpus": corpus, "sites": rows, "total_sites": len(sites), "located": len(rows)}
    if not rows:
        payload["note"] = (
            "geo maps the Aegean inscription corpora (lineara, linearb, cypriot, "
            "cyprominoan, sigla, damos); Greek corpora either carry no find-spot or "
            "record find-places outside the bundled Aegean gazetteer"
        )
    return payload


def data_status() -> dict[str, Any]:
    """The local data store: every fetchable dataset with its downloaded state, on-disk
    size, size note, and license.

    Read-only (nothing is downloaded or deleted here). The corpora that load by name
    over MCP appear under their asset names ('nt-corpus', 'damos-corpus', 'sigla-corpus',
    'isicily-corpus', 'iip-corpus', 'iospe-corpus', 'igcyr-corpus', 'edh-corpus',
    'ddbdp-corpus'); a dataset that is not downloaded is fetched automatically
    (sha256-verified) the first time something needs it, or explicitly from the shell
    with `aegean data fetch NAME`."""
    from .data import _REMOTE, cache_dir, downloaded_bytes, is_downloaded

    root = cache_dir()
    datasets: list[dict[str, Any]] = []
    for name, spec in sorted(_REMOTE.items()):
        # Route through is_downloaded/downloaded_bytes (not a bare root/name probe) so a
        # dataset that lands under a different filename via an index/extract fetch is seen
        # as downloaded, matching `aegean data list` / `aegean doctor`.
        downloaded = is_downloaded(spec, root)
        size = downloaded_bytes(spec, root) if downloaded else None
        datasets.append(
            {
                "name": name,
                "downloaded": downloaded,
                "bytes": size,
                "size": _human_size(size) if size is not None else "",
                "note": spec.note,
                "license": spec.license,
            }
        )
    return {"store": str(root), "datasets": datasets}


def _human_size(n: int) -> str:
    if n >= 1e9:
        return f"{n / 1e9:.1f} GB"
    if n >= 1e6:
        return f"{n / 1e6:.1f} MB"
    if n >= 1e3:
        return f"{n / 1e3:.1f} kB"
    return f"{n} B"


def greek_pipeline(text: str) -> list[dict[str, Any]]:
    """Run the (baseline, offline) Greek NLP pipeline: one row per token.

    Each row carries ``text``, ``upos``, ``lemma``, ``lemma_source`` (the lemma's
    evidence class: attested / neural_lookup / neural_edit / neural / rule / seed / paradigm /
    identity / unresolved / punct / user), ``lemma_resolved``, ``lemma_verified``, and
    ``review_recommended`` (plus the deprecated ``lemma_known`` alias), sentence/index position, and
    the parser/neural fields (``head``, ``relation``, ``xpos``, ``feats``; ``None`` under
    the baseline), plus ``alignment_*`` source identity, exact text, Unicode span,
    whitespace, and normalization fields. The rows are the shared
    :func:`aegean._view.pipeline_rows` mapping, so this tool, the ``aegean greek pipeline``
    command, and the terminal UI emit identical rows."""
    from ._view import pipeline_rows

    return pipeline_rows(text)


def greek_explain(text: str) -> list[dict[str, Any]]:
    """Explain what the (baseline, offline) Greek pipeline did to each token.

    One row per token, in pipeline order, carrying ``token``, ``upos``, ``lemma``,
    ``lemma_source`` (the lemma's evidence class: attested / neural_lookup / neural_edit /
    neural / rule / seed / paradigm / identity / unresolved / punct / user),
    ``needs_review`` (``True`` marks a lemma
    a human should verify: an ``identity`` fall-through or an ``unresolved`` miss),
    ``morphology`` (the UD FEATS string when a neural backend filled one, else ``None``),
    and ``note`` (a one-line, plain-language account of what that evidence class means).
    The evidence CLASS is the whole trust claim: there are deliberately no confidence
    numbers (the neural pipeline's calibrated confidence needs the trained model, which
    this server does not load). Rendered from the same records ``greek_pipeline`` returns,
    never a re-run, so the two tools cannot disagree."""
    from .greek import explain_pipeline

    return [
        {
            "token": e.token,
            "upos": e.upos,
            "lemma": e.lemma,
            "lemma_source": e.lemma_source.value,
            "needs_review": e.needs_review,
            "morphology": e.morphology,
            "note": e.note,
        }
        for e in explain_pipeline(text)
    ]


def corpus_diagnose(corpus: str, deep: bool = False) -> dict[str, Any]:
    """A descriptive corpus-health report for a corpus, as structured JSON.

    ``corpus`` is a name from ``list_corpora``. Reports, as OBSERVABLE facts: the
    reading-status profile (certain / unclear / restored / lost, and how many documents
    carry apparatus), provenance and citation, the accounting reconciliation for the
    Aegean accounting scripts (a discrepancy is a *lead, not a verdict on the scribe* —
    Aegean metrology is imperfectly understood), numeral-parse anomalies, and the
    annotation-review state. ``deep`` adds a sign-frequency scan (hapax signs and labels
    absent from the inventory) for the Aegean syllabic scripts. Every section that does
    not apply to a corpus is marked ``applicable: false`` rather than raising.

    Loading a fetch-on-demand corpus ('nt', 'damos', 'sigla', 'isicily', 'iip', 'iospe',
    'igcyr', 'edh', 'ddbdp') downloads it on first use; a cold-cache offline failure
    returns the structured error. 'ddbdp' is heavy (57k papyri materialise), and ``deep``
    over a large corpus is expensive; check ``data_status`` first."""
    from .core.diagnose import ACCOUNTING_CAVEAT

    c, err = _load_corpus(corpus)
    if err is not None:
        return err
    rep = c.diagnose("full" if deep else "quick")
    s, a, nm, rv, sg, p = (
        rep.reading_status, rep.accounting, rep.numerals, rep.review, rep.signs, rep.provenance,
    )
    out: dict[str, Any] = {
        "corpus": corpus,
        "script_id": rep.script_id,
        "documents": rep.n_documents,
        "tokens": rep.n_tokens,
        "level": rep.level,
        "reading_status": {
            "certain": s.certain,
            "unclear": s.unclear,
            "restored": s.restored,
            "lost": s.lost,
            "documents_with_apparatus": s.documents_with_apparatus,
            "alt_reading_tokens": s.alt_reading_tokens,
        },
        "provenance": {
            "can_cite": p.can_cite,
            "edition_fidelity": p.edition_fidelity,
            "citation": p.citation,
        },
        "accounting": (
            {
                "applicable": True,
                "documents_with_total": a.documents_with_total,
                "balanced": a.balanced,
                "discrepant": a.discrepant,
                "intact_and_balancing": a.intact_and_balancing,
                "discrepant_ids": list(a.discrepant_ids),
                "caveat": ACCOUNTING_CAVEAT,
            }
            if a.applicable
            else {"applicable": False, "note": a.note}
        ),
        "numerals": (
            {"applicable": True, "anomalies": nm.anomaly_count}
            if nm.applicable
            else {"applicable": False, "note": nm.note}
        ),
        "review": (
            {
                "applicable": True,
                "word_tokens": rv.word_tokens,
                "needs_review": rv.needs_review,
                "density": rv.density,
            }
            if rv.applicable
            else {"applicable": False, "note": rv.note}
        ),
    }
    if sg.applicable and sg.computed:
        out["signs"] = {
            "distinct": sg.distinct_signs,
            "hapax": sg.hapax_count,
            "out_of_inventory_occurrences": sg.out_of_inventory_occurrences,
            "out_of_inventory_distinct": sg.out_of_inventory_distinct,
        }
    return out


def greek_scan(text: str, meter: str = "hexameter") -> dict[str, Any]:
    """Scan a Greek verse line. ``meter`` is 'hexameter' / 'pentameter' / 'trimeter' or an
    aeolic line type ('sapphic_hendecasyllable', 'glyconic', …). Reports the glyph pattern,
    or ``scans: false`` with the reason if the line does not fit."""
    from . import greek

    try:
        sc = greek.scan_line(text, meter)
    except greek.ScansionError as exc:
        return {"meter": meter, "scans": False, "error": str(exc)}
    return {
        "meter": sc.meter,
        "scans": True,
        "pattern": sc.pattern,
        "feet": [f.name for f in sc.feet],
        "caesura": sc.caesura,
    }


def greek_catalog(
    query: str | None = None,
    author: str | None = None,
    title: str | None = None,
    source: str | None = None,
    limit: int = 40,
) -> dict[str, Any]:
    """Search the bundled catalogue of ~1,800 loadable Greek works (Perseus
    canonical-greekLit + First1KGreek): id, author, English and Greek title.

    All filters are case-insensitive substrings combined with AND; ``query`` matches
    across id, author, and both titles; ``source`` limits to 'perseus' or 'first1k'.
    ``limit`` caps the returned rows (limit <= 0 returns all; ``total`` is always the
    full match count). Bundled metadata: offline and instant. Pass an id to
    ``greek_work`` to load the text itself (fetched into the local data store on its
    first use)."""
    from .greek import catalog

    if source not in (None, "perseus", "first1k"):
        return {"error": f"unknown source {source!r}; choose 'perseus' or 'first1k'"}
    works = catalog(query, author=author, title=title, source=source)
    cap = None if limit <= 0 else limit
    return {"total": len(works), "works": works[:cap]}


def greek_work(work_id: str, ref: str | None = None, preview_lines: int = 10) -> dict[str, Any]:
    """Load a real Greek work by its CTS-style catalogue id (e.g. 'tlg0012.tlg001',
    the Iliad), whole or one section, and summarize it with a short text preview.

    ``work_id`` is an id from ``greek_catalog`` (Perseus canonical-greekLit /
    First1KGreek), never a filesystem path. ``ref`` selects a section by citation
    address: '1' (a book), '1.2' (a chapter), '1.1-1.50' (a verse line-range), a
    margin milestone outside the CTS <div> scheme (a Stephanus sub-page '17a', a
    Bekker line '1447a10' or a whole Bekker page-column '1447a'), or a comma list of
    any of these ('1.1,1.5', '17a,17b') giving one section per entry.
    The first use of a work downloads its TEI file into the local data store (a
    one-time, commit-pinned network fetch); later calls are offline, exactly like
    ``greek_gloss``'s dictionaries. Returns the work summary (documents, tokens,
    first document id, name, source, data_version) plus ``preview``: the first
    ``preview_lines`` lines of the first document (preview_lines <= 0 sends none).
    An unknown or malformed id returns a structured error pointing at the catalog."""
    from .data import DataNotAvailableError
    from .greek import load_work

    pointer = "greek_catalog searches the ~1,800 loadable ids by author or title"
    wid = work_id.strip()
    if any(sep in wid for sep in ("/", "\\")) or wid.lower().endswith(
        (".json", ".db", ".sqlite", ".xml")
    ):
        return {
            "error": f"{work_id!r} looks like a filesystem path; greek_work takes a "
            f"CTS-style work id such as 'tlg0012.tlg001' ({pointer})"
        }
    try:
        c = load_work(wid, ref=ref)
    except (DataNotAvailableError, ValueError) as exc:
        return {"error": f"{exc} ({pointer})"}
    first = c.documents[0] if len(c) else None
    preview: list[str] = []
    if first is not None and preview_lines > 0:
        preview = [
            " ".join(t.text for t in line) for line in first.line_tokens[:preview_lines]
        ]
    return {
        "work": wid,
        "documents": len(c),
        "tokens": sum(len(d.tokens) for d in c),
        "first": first.id if first is not None else "",
        "name": first.meta.name if first is not None else "",
        "source": c.provenance.source if c.provenance else "",
        "data_version": c.provenance.data_version if c.provenance else "",
        "preview": preview,
    }


def greek_gloss(word: str, dictionary: str = "lsj", full: bool = False) -> dict[str, Any]:
    """Gloss a Greek word from a registry dictionary: lsj (classical, the default),
    middle-liddell, cunliffe (Homeric), autenrieth (Homeric), abbott-smith, or
    dodson (Koine NT).

    The word is looked up as given and lemmatized on a miss, so inflected forms resolve.
    The first use of a dictionary other than dodson downloads and builds its index (a
    one-time fetch into the local data store, roughly 0.1 to 15 MB depending on the
    dictionary); later calls are offline. ``full`` adds the complete entry body, not
    just the concise gloss."""
    from . import greek

    infos = {i.id: i for i in greek.lexica()}
    hosted = sorted(i for i, info in infos.items() if info.hosted)
    if dictionary not in infos:
        return {
            "error": f"unknown dictionary {dictionary!r}{_did_you_mean(dictionary, hosted)}; "
            f"dictionaries: {', '.join(hosted)}"
        }
    if not infos[dictionary].hosted:
        return {
            "error": f"{dictionary!r} is deep-link only (not hosted); "
            f"hosted dictionaries: {', '.join(hosted)}"
        }
    # The first use of a hosted dictionary fetches and builds its index; a cold-cache
    # offline call (or a network / HTTP / sha256 failure) raises out of use_lexicon.
    # Return the surface's structured error instead of leaking a raw traceback.
    from .data import DataNotAvailableError

    try:
        greek.use_lexicon(dictionary)
        e = greek.entry(word, dictionary=dictionary)
    except (DataNotAvailableError, ValueError) as exc:
        return {"error": f"could not load the {dictionary} dictionary: {exc}"}
    if e is None:
        return {"error": f"no {dictionary} entry for {word!r}"}
    out: dict[str, Any] = {
        "word": word,
        "dictionary": dictionary,
        "headword": e.headword,
        "gloss": e.gloss,
    }
    if full:
        out["definition"] = e.body
    return out


def koine_gloss(word: str) -> dict[str, Any]:
    """Koine (NT) gloss for a Greek word via the bundled Dodson lexicon (offline, CC0)."""
    from . import greek

    greek.use_dodson()
    entry = greek.lookup_nt(word)
    if entry is None:
        return {
            "error": f"no Dodson (Koine NT) entry for {word!r}; "
            "greek_gloss reaches the classical dictionaries"
        }
    return {
        "word": word,
        "lemma": entry.lemma,
        "strongs": entry.strongs,
        "gloss": entry.gloss,
        "definition": entry.definition,
    }


# The tools registered with the server — also the unit-test surface.
TOOLS = (
    list_corpora,
    corpus_info,
    show_document,
    search_signs,
    balance_accounts,
    query_corpus,
    cite_corpus,
    geo_sites,
    data_status,
    greek_pipeline,
    greek_explain,
    greek_scan,
    greek_catalog,
    greek_work,
    greek_gloss,
    koine_gloss,
    corpus_diagnose,
)


def build_server() -> Any:
    """Build a FastMCP server with every pyaegean tool registered (needs the ``[mcp]`` extra)."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("pyaegean")
    for fn in TOOLS:
        server.tool()(fn)
    return server


def main() -> None:
    """Console-script entry point (``aegean-mcp``): serve the tools over stdio."""
    try:
        server = build_server()
    except ModuleNotFoundError as exc:
        import importlib.util
        import sys

        # distinguish "mcp not installed" from "mcp installed but too old for
        # mcp.server.fastmcp (added in 1.2)": the printed fix must actually fix it.
        if importlib.util.find_spec("mcp") is not None:
            msg = "aegean-mcp needs a newer MCP SDK — pip install -U 'mcp>=1.2'"
        else:
            msg = "aegean-mcp needs the [mcp] extra — pip install 'pyaegean[mcp]'"
        print(f"{msg}  ({exc})", file=sys.stderr)
        raise SystemExit(1) from None
    server.run()


if __name__ == "__main__":
    main()
