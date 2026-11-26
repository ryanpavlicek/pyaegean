"""Ancient Greek NLP, scansion, catalogue, work, and lexicon MCP tools."""

from __future__ import annotations

from typing import Any

from ._common import _dictionary_unavailable, _did_you_mean

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
    command, and the terminal UI emit identical rows. ``review_recommended`` selects
    identity/unresolved lemma fallbacks; False does not certify correctness or human
    verification and does not assess POS, morphology, or dependencies. The baseline is
    a deterministic first pass whose rule and lookup results may still be wrong."""
    from .._view import pipeline_rows

    return pipeline_rows(text)


def greek_explain(text: str) -> list[dict[str, Any]]:
    """Explain what the (baseline, offline) Greek pipeline did to each token.

    One row per token, in pipeline order, carrying ``token``, ``upos``, ``lemma``,
    ``lemma_source`` (the lemma's evidence class: attested / neural_lookup / neural_edit /
    neural / rule / seed / paradigm / identity / unresolved / punct / user),
    ``needs_review`` (``True`` selects identity/unresolved lemma fallbacks;
    False does not certify correctness or human verification),
    ``morphology`` (the UD FEATS string when a neural backend filled one, else ``None``),
    and ``note`` (a one-line, plain-language account of what that evidence class means).
    The evidence class records provenance, not a correctness verdict. The flag does not
    assess POS, morphology, or dependencies. There are deliberately no confidence
    numbers (the neural pipeline's calibrated confidence needs the trained model, which
    this server does not load). This tool runs the pipeline over ``text`` and renders
    the records it gets back, exactly as ``greek_pipeline`` maps its own, so the two
    cannot disagree about the same text; they share no state, so calling both analyzes
    that text twice."""
    from ..greek import explain_pipeline

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




def greek_scan(text: str, meter: str = "hexameter") -> dict[str, Any]:
    """Scan a Greek verse line. ``meter`` is 'hexameter' / 'pentameter' / 'trimeter' or an
    aeolic line type ('sapphic_hendecasyllable', 'glyconic', …). Reports the glyph pattern,
    or ``scans: false`` with the reason if the line does not fit."""
    from .. import greek

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
    offset: int = 0,
) -> dict[str, Any]:
    """Search the bundled catalogue of ~1,800 loadable Greek works (Perseus
    canonical-greekLit + First1KGreek): id, author, English and Greek title.

    All filters are case-insensitive substrings combined with AND; ``query`` matches
    across id, author, and both titles; ``source`` limits to 'perseus' or 'first1k'.
    ``limit`` caps the returned rows (limit <= 0 returns all from ``offset``; ``total``
    is always the full match count, and ``truncated`` / ``next_offset`` report whether
    more rows remain). Bundled metadata: offline and instant. Pass an id to
    ``greek_work`` to load the text itself (fetched into the local data store on its
    first use)."""
    from ..greek import catalog

    if offset < 0:
        return {"error": f"offset must be >= 0; got {offset}"}
    if source not in (None, "perseus", "first1k"):
        return {"error": f"unknown source {source!r}; choose 'perseus' or 'first1k'"}
    works = catalog(query, author=author, title=title, source=source)
    end = None if limit <= 0 else offset + limit
    page = works[offset:end]
    has_more = (offset + len(page)) < len(works)
    return {
        "total": len(works),
        "offset": offset,
        "truncated": has_more,
        "next_offset": (offset + len(page)) if has_more else None,
        "works": page,
    }


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
    from ..data import DataNotAvailableError
    from ..greek import load_work

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
    ``full`` adds the complete entry body, not just the concise gloss.

    Dodson is bundled and answers immediately. Every other dictionary is fetched into
    the local data store on first use, and the call blocks for the whole fetch: the
    compressed index runs from 0.13 MB (abbott-smith) through 0.6 MB (autenrieth),
    1.3 MB (cunliffe), and 2.3 MB (middle-liddell) to 15.4 MB (lsj), plus whatever the
    network costs. Should the prebuilt lsj index be unreachable, the fallback is the
    27-file Perseus LSJ TEI source, a far larger download built into an index locally.

    Later calls are offline but not free: the index is loaded and parsed on the first
    call of a session, and lsj expands to a 60 MB, 116,414-entry table. With the index
    already in the store, that first call costs roughly 0.2 s for abbott-smith, 0.5 s
    for autenrieth and cunliffe, 0.8 s for middle-liddell, and about 6 s for lsj;
    lookups after it are immediate. Times are machine-dependent."""
    from .. import greek

    # This surface answers with a structured result, so a wrong argument type is reported
    # the same way a wrong dictionary name is, not raised out of a lookup helper.
    if not isinstance(word, str):
        return {"error": f"word must be a string, got {type(word).__name__}"}
    if not isinstance(dictionary, str):
        return {"error": f"dictionary must be a string, got {type(dictionary).__name__}"}

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
    # offline call (a network / HTTP / sha256 failure, or a damaged file in the store)
    # raises out of use_lexicon. Report what happened here — the index could not be
    # obtained — rather than a raw traceback or a loader remediation an agent has no
    # repository to perform.
    from ..data import DataNotAvailableError

    try:
        greek.use_lexicon(dictionary)
        e = greek.entry(word, dictionary=dictionary)
    except (DataNotAvailableError, ValueError, OSError):
        return {"error": _dictionary_unavailable(dictionary)}
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
    from .. import greek

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

