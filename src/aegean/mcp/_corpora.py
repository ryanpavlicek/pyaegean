"""Corpus, epigraphy, geography, data-store, and full-text search MCP tools."""

from __future__ import annotations

from typing import Any

from ._common import _did_you_mean, _find_doc, _human_size, _load_corpus, _looks_like_path

def list_corpora() -> list[str]:
    """List the corpora that can be loaded by name.

    Five are bundled and load offline; the rest ('damos', 'nt', 'sigla', 'isicily', 'iip',
    'iospe', 'igcyr', 'edh', 'ddbdp') download into the local data store on first use
    (``data_status`` shows what is already stored)."""
    from ..core.corpus import _LOADERS

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
    from .._view import _form_state_fields

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
    corpus: str, pattern: str, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]] | dict[str, Any]:
    """Words matching a wildcard sign pattern (e.g. 'KU-*-RO'), with frequencies.

    ``limit`` caps the matches (limit <= 0 returns every match from ``offset``);
    ``offset`` skips the first ``offset`` matches for pagination."""
    from ..analysis import word_matches_sign_pattern

    if offset < 0:
        return {"error": f"offset must be >= 0; got {offset}"}
    c, err = _load_corpus(corpus)
    if err is not None:
        return err
    out: list[dict[str, Any]] = []
    seen = 0
    for word, count in c.word_frequencies():
        if word_matches_sign_pattern(word, pattern):
            if seen < offset:
                seen += 1
                continue
            out.append({"word": word, "count": count})
            if limit > 0 and len(out) >= limit:
                break
    return out


def balance_accounts(
    corpus: str,
    doc_id: str | None = None,
    exact: bool = False,
    tolerance: float = 0.10,
    limit: int = 0,
    offset: int = 0,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Accounting reconciliation: each stated total (KU-RO / TO-SO) vs the summed items.

    Returns one row per total marker (whole corpus, or one ``doc_id``, forgivingly
    matched): ``doc``, ``marker``, ``stated`` (the written total), ``computed`` (the summed
    items or subtotals), ``difference`` (computed minus stated), ``items`` (the count fed
    into the sum), and ``balances``. An empty list means the document(s) carry no total
    markers. The rows are the shared :func:`aegean._view.balance_rows` mapping, so this
    tool, the ``aegean balance`` command, and the terminal UI cannot disagree.
    ``exact=True`` uses rational equality without an allowance. The rows also
    expose exact discrepancy and account eligibility (at least one qualifying
    total on intact text); ``tolerance`` retains the legacy absolute-one floor.
    ``limit`` (> 0) and ``offset`` (>= 0) paginate whole-corpus results.
    Arithmetic agreement does not verify disputed readings or metrology."""
    from .._view import balance_rows

    if offset < 0:
        return {"error": f"offset must be >= 0; got {offset}"}
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
    seen = 0
    for doc in docs:
        try:
            doc_rows = balance_rows(doc, exact=exact, tolerance=tolerance)
        except ValueError as exc:
            return {"error": str(exc)}
        for row in doc_rows:
            if seen < offset:
                seen += 1
                continue
            rows.append(row)
            if limit > 0 and len(rows) >= limit:
                return rows
    return rows


def query_corpus(
    corpus: str,
    where: list[dict[str, Any]],
    output_kind: str = "inscriptions",
    limit: int = 50,
    view: str | None = None,
    count_unit: str = "document",
    statuses: list[str] | None = None,
    offset: int = 0,
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
    ``limit`` caps the returned id/word lists (limit <= 0 returns all from ``offset``);
    ``offset`` paginates through results and ``truncated`` / ``next_offset`` report
    whether more entries remain. The totals are always the full counts. ``citation``
    cites exactly this result set.
    ``view`` selects surface/normalized/lemma keys; omitted keeps legacy predicates.
    Normalized/lemma preserve diacritics and iota subscript (NFC, lowercase,
    final-sigma fold). Missing lemmas are excluded. ``count_unit`` selects document
    or token frequency; ``statuses`` selects whole tokens and editorial segments.
    ``metadata`` records normalization, population denominators, and exclusions."""
    from ..analysis import FIELDS, FilterRow

    if offset < 0:
        return {"error": f"offset must be >= 0; got {offset}"}
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
    from typing import cast

    from ..core.word_views import CountUnit, validate_view

    try:
        res = c.query(
            rows, output_kind, view=validate_view(view) if view is not None else None,
            count_unit=cast(CountUnit, count_unit), statuses=statuses,
        )
    except ValueError as exc:
        return {"error": str(exc)}
    end = None if limit <= 0 else offset + limit
    page_ins = [d.id for d in res.inscriptions[offset:end]]
    page_words = [{"word": w, "count": n} for w, n in res.words[offset:end]]
    total_primary = len(res.words) if output_kind == "words" else len(res.inscriptions)
    returned_primary = len(page_words) if output_kind == "words" else len(page_ins)
    has_more = (offset + returned_primary) < total_primary
    return {
        "description": res.description or "all",
        "total_inscriptions": len(res.inscriptions),
        "total_words": len(res.words),
        "offset": offset,
        "truncated": has_more,
        "next_offset": (offset + returned_primary) if has_more else None,
        "inscriptions": page_ins,
        "words": page_words,
        "citation": res.cite() if res.provenance else "",
        "metadata": res.metadata,
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
    from ..geo import _fold_word, _normalize_site, site_coordinates

    c, err = _load_corpus(corpus)
    if err is not None:
        return err
    coords = site_coordinates()
    name_by_norm = {_normalize_site(k): k for k in coords}
    if word is not None:
        from collections import Counter

        counts: Counter[str] = Counter()
        target = _fold_word(word)
        for d in c:
            resolved = name_by_norm.get(_normalize_site(d.meta.site)) if d.meta.site else None
            if resolved is not None and any(_fold_word(t.text) == target for t in d.words):
                counts[resolved] += 1
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
    from ..data import _REMOTE, cache_dir, downloaded_bytes, is_downloaded

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
    from ..core.diagnose import ACCOUNTING_CAVEAT

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




def search_text(
    query: str,
    target: str = "nt",
    book: str | None = None,
    edition: str | None = None,
    limit: int = 20,
    exact: bool = False,
) -> dict[str, Any]:
    """Fast diacritic-insensitive full-text search across any registered corpus
    (lineara, damos, isicily, aphrodisias, crete, apostolic-fathers, pseudepigrapha,
    byzantine, homer-scholia, nt, ddbdp, patrologia), lxx (55 Swete Septuagint books),
    nt-editions (9 NT editions), a Patrologia Graeca volume (e.g. PG073), or a CTS
    work ID (e.g. tlg0012.tlg001). Never accepts filesystem paths; uses local cached
    datasets and SQLite FTS5 sidecar indexes (offline-only, never downloads)."""
    from ..core.resolve import CorpusNotFound
    from ..data import DataNotAvailableError
    from ..search import search_text as _search_text

    q = query.strip()
    if not q:
        return {"error": "query must be a non-empty search string"}
    if _looks_like_path(target):
        return {
            "error": f"target {target!r} looks like a filesystem path; MCP tools accept "
            "registered corpus IDs, lxx, nt-editions, PG volume IDs (e.g. PG073), "
            "or CTS work IDs (e.g. tlg0012.tlg001) only"
        }
    try:
        hits = _search_text(
            q,
            target,
            limit=max(1, min(int(limit), 100)),
            exact=exact,
            book=book,
            edition=edition,
            offline=True,
        )
        return {
            "query": q,
            "target": target,
            "count": len(hits),
            "hits": [h.to_dict() for h in hits],
        }
    except (ValueError, CorpusNotFound, DataNotAvailableError) as exc:
        return {"error": str(exc)}
