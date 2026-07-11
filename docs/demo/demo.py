"""The Python the browser demo runs under Pyodide.

Stable, pure-Python core APIs only. Everything here runs entirely client-side: the Greek
pipeline + scansion + word analysis, accent placement, sandhi resolution, syllable
quantities, the offline lemmatizer, the bundled Koine (Dodson) lexicon, the bundled New
Testament sample (John 1 + Philemon), the curated idiom lexicon, the offline Greek
work catalogue, the deciphered-syllabary Greek bridge, the bundled Linear A corpus
(sign search + accounting + statistics + compound queries + numerals), the sign
inventories of all four Aegean scripts, the bundled Linear B / Cypriot (IG XV 1) /
Cypro-Minoan corpora, the find-site gazetteer, citation + fingerprinting, the file importer,
the stdlib EpiDoc reader/writer, cross-script phonetic comparison, the pipeline evidence-class
explanation, corpus-health diagnostics, the editorial-apparatus profile, Linear B scribal
dossiers, Linear A seriation, and catalogued sign-variant (allograph) groups. The
neural tier is excluded (it needs onnxruntime, which doesn't run in the browser) — so is the
neural pipeline's calibrated confidence — as are the network-only backends (load_work, the
full-NT fetch, LSJ/treebank, the fetched paradigm table) and the generative AI layer. Each
function returns a JSON string for easy consumption from JavaScript. This module is exercised
by tests/test_web_demo.py, so the demo's logic can't silently rot.
"""

from __future__ import annotations

import json
from typing import Any


def betacode(text: str) -> str:
    """Convert Beta Code (plain-ASCII polytonic Greek) to Unicode."""
    from aegean import greek

    return json.dumps({"unicode": greek.betacode_to_unicode(text)}, ensure_ascii=False)


def greek_pipeline(text: str) -> str:
    """Per-token (text, UPOS, lemma) for a Greek sentence — the baseline pipeline."""
    from aegean import greek

    recs = [
        {"text": r.text, "upos": r.upos, "lemma": r.lemma}
        for r in greek.pipeline(text)
    ]
    return json.dumps(recs, ensure_ascii=False)


def greek_word(word: str) -> str:
    """Analyse one Greek word: syllables, accent, reconstructed pronunciation, morphology."""
    from aegean import greek

    word = word.strip().split()[0] if word.strip() else word
    acc = greek.accentuation(word)
    morph = [
        {"lemma": a.lemma, "pos": a.pos, "features": a.features()}
        for a in greek.analyze(word)[:4]
    ]
    out = {
        "word": word,
        "syllables": greek.syllabify(word),
        "accent": f"{acc.classification} ({acc.accent_type})",
        "ipa_attic": greek.to_ipa(word),
        "ipa_koine": greek.to_ipa(word, "koine"),
        "morphology": morph,
    }
    return json.dumps(out, ensure_ascii=False)


def greek_scan(text: str, meter: str = "hexameter") -> str:
    """Scan a Greek verse line; returns the glyph pattern or a decline reason."""
    from aegean import greek

    try:
        sc = greek.scan_line(text, meter)
        out: dict[str, Any] = {"scans": True, "meter": sc.meter, "pattern": sc.pattern}
    except greek.ScansionError as exc:
        out = {"scans": False, "error": str(exc)}
    return json.dumps(out, ensure_ascii=False)


def gloss_nt(word: str) -> str:
    """Gloss a Koine (New Testament) Greek word from the bundled Dodson lexicon (offline)."""
    from aegean import greek

    greek.use_dodson()
    word = word.strip().split()[0] if word.strip() else word
    return json.dumps({"word": word, "gloss": greek.gloss_nt(word) or ""}, ensure_ascii=False)


def catalog(query: str, limit: int = 15) -> str:
    """Search the offline catalogue of ~1,778 loadable Greek works (author/title/free text)."""
    from aegean import greek

    hits = [
        {"id": w["id"], "author": w["author"], "title": w["title"],
         "greek": w.get("greek_title", "")}
        for w in greek.catalog(query.strip() or None)
    ]
    return json.dumps(
        {"query": query, "total": len(hits), "matches": hits[:limit]}, ensure_ascii=False
    )


def lexicon_link(word: str) -> str:
    """A Logeion deep-link for a Greek word (lemmatized first) — covers dictionaries not hosted here."""
    from aegean import greek

    word = word.strip().split()[0] if word.strip() else word
    url = greek.lexicon_link(word) if word else ""
    return json.dumps({"word": word, "url": url}, ensure_ascii=False)


def bridge(script: str, word: str) -> str:
    """Read a deciphered syllabic word (Linear B / Cypriot) as Greek — the bundled bridge."""
    if script == "linearb":
        from aegean.scripts.linearb.lexicon import gloss, greek_reading
    elif script == "cypriot":
        from aegean.scripts.cypriot.lexicon import gloss, greek_reading
    else:
        return json.dumps({"error": f"bridge supports linearb / cypriot, not {script!r}"})
    reading = greek_reading(word.strip())
    if reading is None:
        return json.dumps(
            {"error": f"{word!r} has no attested Greek reading in the bundled {script} lexicon"}
        )
    return json.dumps(
        {"script": script, "word": word, "greek": reading[0], "gloss": gloss(word) or reading[1]},
        ensure_ascii=False,
    )


def cypriot_inscription(doc_id: str = "IG XV 1, 95") -> str:
    """Read a real inscription from the bundled Cypriot *Inscriptiones Graecae* XV 1 corpus:
    its find-place, transliteration line(s), Greek reading (where the text is Greek), and the
    source-edition link."""
    import aegean

    doc = aegean.load("cypriot").get(doc_id.strip())
    if doc is None:
        return json.dumps({"error": f"no inscription {doc_id!r} in the Cypriot IG XV 1 corpus"})
    notes = doc.meta.notes or ()
    source_url = next((n for n in notes if str(n).startswith("http")), "")
    greek = next((str(n)[len("Greek:"):].strip() for n in notes if str(n).startswith("Greek:")), "")
    lines = [" ".join(doc.tokens[i].text for i in idxs) for idxs in doc.lines]
    return json.dumps(
        {
            "id": doc.id,
            "site": doc.meta.site,
            "name": doc.meta.name,
            "lines": lines,
            "greek": greek,
            "source_url": source_url,
        },
        ensure_ascii=False,
    )


def lineara_search(pattern: str, limit: int = 40) -> str:
    """Wildcard sign-pattern search over the bundled Linear A corpus (e.g. 'KU-*-RO')."""
    import aegean
    from aegean.analysis import word_matches_sign_pattern

    corpus = aegean.load("lineara")
    hits = [
        {"word": w, "count": n}
        for w, n in corpus.word_frequencies()
        if word_matches_sign_pattern(w, pattern)
    ][:limit]
    return json.dumps({"pattern": pattern, "matches": hits}, ensure_ascii=False)


def lineara_balance(doc_id: str) -> str:
    """Reconcile a Linear A tablet's stated KU-RO total against the sum of its line items."""
    import aegean
    from aegean.analysis import balance_check

    doc = aegean.load("lineara").get(doc_id.strip())
    if doc is None:
        return json.dumps({"error": f"no document {doc_id!r} in the Linear A corpus"})
    checks = [
        {"marker": c.marker, "stated": c.stated_total, "computed": c.computed_sum,
         "difference": c.difference, "items": c.item_count, "balances": c.balances}
        for c in balance_check(doc)
    ]
    return json.dumps({"doc": doc_id, "checks": checks}, ensure_ascii=False)


def import_text(text: str) -> str:
    """Turn the user's own text into a Corpus and report its size + most frequent words."""
    from aegean import io

    corpus = io.from_text(text, doc_id="your-text")
    doc = corpus.documents[0]
    return json.dumps(
        {
            "documents": len(corpus),
            "tokens": len(doc.tokens),
            "top": [{"word": w, "count": n} for w, n in corpus.word_frequencies()[:10]],
        },
        ensure_ascii=False,
    )


def epidoc_import(xml: str) -> str:
    """Read a pasted EpiDoc TEI document into a Corpus (stdlib XML parser, fully offline)."""
    import os
    import tempfile
    import xml.etree.ElementTree as ET

    from aegean import io

    if not xml.strip():
        return json.dumps({"error": "paste an EpiDoc <TEI> document"})
    path = os.path.join(tempfile.mkdtemp(), "in.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    try:
        corpus = io.from_epidoc(path, script_id="greek")
    except ET.ParseError as exc:
        return json.dumps({"error": f"could not parse EpiDoc XML: {exc}"})
    if not corpus.documents:
        return json.dumps({"error": "no <div type='edition'> or <body> tokens found"})
    doc = corpus.documents[0]
    return json.dumps(
        {
            "id": doc.id,
            "site": doc.meta.site,
            "documents": len(corpus),
            "tokens": len(doc.tokens),
            "preview": [t.text for t in doc.tokens[:12]],
        },
        ensure_ascii=False,
    )


def phonetic_compare(syllabic: str, greek_word: str) -> str:
    """Phonetic closeness of a Linear B spelling to a Greek word (defective-script aware)."""
    from aegean.analysis import phonetic_compare as compare

    cmp = compare(syllabic.strip(), "linearb", greek_word.strip(), "greek")
    return json.dumps(
        {"syllabic": syllabic, "greek": greek_word, "similarity": round(cmp.similarity, 3)},
        ensure_ascii=False,
    )


# the corpora bundled inside the wheel: the only ones the browser can load with no network
_BUNDLED_CORPORA = ("lineara", "linearb", "cypriot", "cyprominoan", "greek")


def accent_word(word: str, lemma: str = "") -> str:
    """Place the accent on an unaccented Greek word: recessive (finite verbs) by default,
    persistent when a lemma is supplied."""
    from aegean import greek

    word = word.strip().split()[0] if word.strip() else word
    lemma = lemma.strip()
    p = greek.place_accent(word, recessive=not lemma, lemma=lemma or None)
    return json.dumps(
        {
            "word": word,
            "accented": p.form,
            "accent": p.accent_type,
            "classification": p.classification,
            "certain": p.certain,
            "note": p.note,
        },
        ensure_ascii=False,
    )


def sandhi(token: str) -> str:
    """Resolve crasis, elision, and movable-nu in one token (never guesses an expansion)."""
    from aegean import greek

    token = token.strip().split()[0] if token.strip() else token
    f = greek.resolve_sandhi(token)
    out: dict[str, Any] = {
        "surface": f.surface,
        "words": list(f.words),
        "kind": f.kind or "none",
        "uncertain": f.uncertain,
        "note": f.note,
    }
    if f.alternatives:
        out["alternatives"] = list(f.alternatives)
    return json.dumps(out, ensure_ascii=False)


def prosody_word(word: str) -> str:
    """Metrical quantity (heavy / light / common) of each syllable of a Greek word."""
    from aegean import greek

    word = word.strip().split()[0] if word.strip() else word
    return json.dumps(
        {
            "word": word,
            "syllables": [{"syllable": s, "quantity": q} for s, q in greek.scan(word)],
        },
        ensure_ascii=False,
    )


def lemmatize_word(word: str) -> str:
    """Offline lemma + POS for one Greek word; ``known=False`` is an honest miss (the word
    comes back unchanged rather than as a fabricated dictionary form)."""
    from aegean import greek

    word = word.strip().split()[0] if word.strip() else word
    lemma, known = greek.lemmatize_verbose(word)
    return json.dumps(
        {"word": word, "lemma": lemma, "known": known, "pos": greek.pos_tag(word) or ""},
        ensure_ascii=False,
    )


def text_profile(text: str) -> str:
    """Observable features of a raw text: writing system, polytonic vs bare vowels, a Beta Code
    look, majuscule share, editorial marks, numeral density. Describes what the characters ARE,
    never a genre or an "out of domain" guess."""
    import dataclasses

    from aegean import greek

    return json.dumps(dataclasses.asdict(greek.profile_text(text)), ensure_ascii=False)


_NT_SAMPLE_BOOKS = {
    "john": "John", "jn": "John", "jhn": "John",
    "philemon": "Phlm", "phlm": "Phlm", "phm": "Phlm",
}


def nt_verse(ref: str) -> str:
    """One verse of the bundled New Testament sample (John 1 + Philemon 1, Nestle 1904),
    with the gold lemma, Robinson morph, Strong's number, and UPOS per token — no network.
    Greek strings are NFC-folded, as in ``greek.load_nt`` (the source edition mixes oxia
    and tonos precomposition)."""
    import unicodedata

    from aegean.data import load_bundled_json
    from aegean.scripts.greek.nt import robinson_to_upos

    def nfc(s: str) -> str:
        return unicodedata.normalize("NFC", s)

    usage = "use book chapter.verse, e.g. 'John 1.1' or 'Philemon 1.4'"
    parts = ref.strip().split()
    if len(parts) < 2:
        return json.dumps({"error": usage})
    book = _NT_SAMPLE_BOOKS.get("".join(parts[:-1]).lower().rstrip("."))
    if book is None:
        return json.dumps(
            {"error": "the bundled offline sample has John 1 and Philemon 1 only; " + usage}
        )
    chap, _, verse = parts[-1].partition(".")
    if not (chap.isdigit() and verse.isdigit()):
        return json.dumps({"error": usage})
    payload = dict(load_bundled_json("greek", "nt_sample.json"))
    rec = next(
        (r for r in payload["documents"]
         if r["book"] == book and int(r["chapter"]) == int(chap)),
        None,
    )
    if rec is None:
        return json.dumps(
            {"error": f"{book} {chap} is not in the bundled offline sample "
                      "(John 1 and Philemon 1 only)"}
        )
    toks = [t for t in rec["tokens"] if int(t["v"]) == int(verse)]
    if not toks:
        return json.dumps({"error": f"no verse {verse} in {rec['id']}"})
    return json.dumps(
        {
            "ref": f"{book} {int(chap)}.{int(verse)}",
            "text": " ".join(nfc(t["t"]) for t in toks),
            "tokens": [
                {
                    "text": nfc(t["t"]),
                    "lemma": nfc(t.get("lemma", "")),
                    "morph": t.get("morph", ""),
                    "strongs": t.get("strongs", ""),
                    "upos": robinson_to_upos(t.get("morph", "")),
                }
                for t in toks
            ],
            "source": "Nestle 1904 (morphology CC0); bundled offline sample: John 1 + Philemon 1",
        },
        ensure_ascii=False,
    )


def idioms(text: str) -> str:
    """Detect curated Greek idioms in a text and gloss their non-literal meaning (offline)."""
    from aegean.ai import idiom_glosses

    return json.dumps(
        {
            "text": text,
            "idioms": [{"gloss": i.content, "surface": i.ref} for i in idiom_glosses(text)],
        },
        ensure_ascii=False,
    )


def lineara_stats(site: str = "Haghia Triada") -> str:
    """Corpus statistics on the bundled Linear A corpus: the most evenly dispersed words
    (Gries' DP) plus the words key to one find-site against the rest (G² / log-ratio).
    Deterministic counts over transliterated sign-groups, not meanings."""
    import aegean
    from aegean.analysis import dispersions, keyness
    from aegean.core.corpus import Corpus

    la = aegean.load("lineara")
    site = site.strip()
    target = la.filter(site=site)
    if not target.documents:
        sites = sorted({d.meta.site for d in la.documents if d.meta.site})
        return json.dumps(
            {"error": f"no documents from site {site!r}", "sites": sites}, ensure_ascii=False
        )
    rest = Corpus(
        [d for d in la.documents if d.meta.site != site],
        la.sign_inventory, la.provenance, la.script_id,
    )
    return json.dumps(
        {
            "dispersion": [
                {"word": d.item, "count": d.frequency, "docs": d.range,
                 "dp_norm": round(d.dp_norm, 3)}
                for d in dispersions(la, top=5)
            ],
            "site": site,
            "keyness": [
                {"word": k.item, "site_count": k.target_count, "elsewhere": k.reference_count,
                 "g2": round(k.log_likelihood, 1), "log_ratio": round(k.log_ratio, 2)}
                for k in [r for r in keyness(target, rest) if r.log_ratio > 0][:5]
            ],
        },
        ensure_ascii=False,
    )


def lineara_query(site: str, sign: str) -> str:
    """Compound query over the bundled Linear A corpus: site AND word-contains-sign,
    words output (count = document frequency)."""
    import aegean
    from aegean.analysis import FilterRow

    rows = []
    if site.strip():
        rows.append(FilterRow("site-is", site.strip()))
    if sign.strip():
        rows.append(FilterRow("word-contains-sign", sign.strip(), "and" if rows else None))
    if not rows:
        return json.dumps({"error": "give a site and/or a sign to filter on"})
    res = aegean.load("lineara").query(rows, output="words")
    return json.dumps(
        {
            "filters": [{"field": r.field, "value": r.value} for r in rows],
            "total": len(res.words),
            "words": [{"word": w, "docs": n} for w, n in res.words[:20]],
        },
        ensure_ascii=False,
    )


def numerals(text: str) -> str:
    """Parse Aegean numeral tokens (integers, fraction glyphs, ≈-approximations) and sum them."""
    from aegean.core.numerals import format_value, parse_value

    readings = []
    for tok in text.split():
        v = parse_value(tok)
        readings.append(
            {
                "token": tok,
                "value": round(v, 4) if v is not None else None,
                "display": format_value(v) if v is not None else None,
            }
        )
    total = sum(r["value"] for r in readings if r["value"] is not None)
    return json.dumps(
        {"readings": readings, "sum": round(total, 4), "sum_display": format_value(total)},
        ensure_ascii=False,
    )


def sign_info(script: str, label: str) -> str:
    """Look a sign up in a script's inventory: glyph, Unicode codepoint, sound value.
    Undeciphered scripts carry their caveat in the output."""
    from aegean.core.script import get_script

    try:
        inv = get_script(script.strip()).sign_inventory
    except KeyError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    label = label.strip()
    s = inv.by_label(label) or inv.by_label(label.upper()) or inv.by_label(label.lower())
    if s is None:
        s = inv.by_glyph(label)
    if s is None:
        return json.dumps(
            {"error": f"no sign {label!r} in the {script} inventory"}, ensure_ascii=False
        )
    out = {
        "script": script,
        "label": s.label,
        "glyph": s.glyph or "",
        "codepoint": f"U+{s.codepoint:04X}" if s.codepoint is not None else "",
        "sound_value": s.phonetic or "",
    }
    if script == "lineara":
        out["note"] = (
            "Linear A is undeciphered: a sound value here is exploratory, projected from "
            "the Linear B comparison, not a reading."
        )
    elif script == "cyprominoan":
        out["note"] = (
            "Cypro-Minoan is undeciphered: signs have identities but no agreed sound values."
        )
    return json.dumps(out, ensure_ascii=False)


def linearb_tablet(doc_id: str = "PY Ta 641") -> str:
    """Read a tablet from the bundled Linear B corpus: its lines plus every word with an
    attested Greek reading in the bundled lexicon."""
    import aegean
    from aegean.scripts.linearb.lexicon import gloss, greek_reading

    corpus = aegean.load("linearb")
    doc = corpus.get(doc_id.strip())
    if doc is None:
        return json.dumps(
            {"error": f"no tablet {doc_id!r} in the bundled Linear B corpus",
             "ids": [d.id for d in corpus.documents]},
            ensure_ascii=False,
        )
    readings = []
    seen: set[str] = set()
    for t in doc.tokens:
        if t.text in seen:
            continue
        seen.add(t.text)
        r = greek_reading(t.text)
        if r is not None:
            readings.append({"word": t.text, "greek": r[0], "gloss": gloss(t.text) or r[1]})
    return json.dumps(
        {
            "id": doc.id,
            "site": doc.meta.site,
            "name": doc.meta.name,
            "period": doc.meta.period,
            "lines": [" ".join(doc.tokens[i].text for i in idxs) for idxs in doc.lines],
            "readings": readings,
        },
        ensure_ascii=False,
    )


def cyprominoan_doc(doc_id: str = "cm-enkomi-ball") -> str:
    """Display a bundled Cypro-Minoan document: sign groups only — the script is
    undeciphered, so no sound values or readings are offered."""
    import aegean

    corpus = aegean.load("cyprominoan")
    doc = corpus.get(doc_id.strip())
    if doc is None:
        return json.dumps(
            {"error": f"no document {doc_id!r} in the Cypro-Minoan corpus",
             "ids": [d.id for d in corpus.documents]},
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "id": doc.id,
            "site": doc.meta.site,
            "name": doc.meta.name,
            "support": doc.meta.support,
            "sign_groups": [t.text for t in doc.tokens],
            "note": ("Cypro-Minoan is undeciphered: the corpus carries sign identities only; "
                     "no transliteration into sound values or Greek is offered."),
        },
        ensure_ascii=False,
    )


def geo_word(query: str) -> str:
    """Find-site coordinates from the bundled Pleiades-aligned gazetteer: a site by name, or
    every site where a Linear A word occurs."""
    import aegean
    from aegean.geo import site_coordinates

    coords = site_coordinates()
    q = query.strip()
    for key, c in coords.items():
        if key.lower() == q.lower():
            return json.dumps(
                {"site": key, "lat": c.lat, "lon": c.lon, "region": c.region,
                 "pleiades": c.pleiades_uri or "", "contested": c.contested or ""},
                ensure_ascii=False,
            )
    word = q.upper()
    counts: dict[str, int] = {}
    for d in aegean.load("lineara").documents:
        if d.meta.site and any(t.text == word for t in d.tokens):
            counts[d.meta.site] = counts.get(d.meta.site, 0) + 1
    if not counts:
        return json.dumps(
            {"error": f"{q!r} matches no gazetteer site and no Linear A word"},
            ensure_ascii=False,
        )
    sites = []
    for site, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        c = coords.get(site)
        sites.append(
            {"site": site, "documents": n,
             "lat": c.lat if c else None, "lon": c.lon if c else None,
             "pleiades": (c.pleiades_uri or "") if c else "",
             "contested": (c.contested or "") if c else ""}
        )
    return json.dumps({"word": word, "sites": sites}, ensure_ascii=False)


def cite_bundled(corpus_id: str, site: str = "") -> str:
    """Cite a bundled corpus (or a site-filtered subset): plain + BibTeX + content
    fingerprint. The citation names the exact subset used."""
    import aegean

    corpus_id = corpus_id.strip().lower()
    if corpus_id not in _BUNDLED_CORPORA:
        return json.dumps(
            {"error": f"bundled corpora only: {', '.join(_BUNDLED_CORPORA)}"}, ensure_ascii=False
        )
    corpus = aegean.load(corpus_id)
    if site.strip():
        corpus = corpus.filter(site=site.strip())
        if not corpus.documents:
            return json.dumps(
                {"error": f"no documents in {corpus_id!r} with site {site.strip()!r}"},
                ensure_ascii=False,
            )
    try:
        plain, bibtex = corpus.cite(), corpus.cite("bibtex")
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    return json.dumps(
        {
            "corpus": corpus_id,
            "documents": len(corpus.documents),
            "citation": plain,
            "bibtex": bibtex,
            "fingerprint": corpus.fingerprint(),
        },
        ensure_ascii=False,
    )


def export_epidoc(corpus_id: str, doc_id: str) -> str:
    """Export one bundled-corpus document as an EpiDoc TEI XML string (in-memory, no files).
    The output round-trips through the Read EpiDoc card."""
    import aegean
    from aegean.io import to_epidoc

    corpus_id = corpus_id.strip().lower()
    if corpus_id not in _BUNDLED_CORPORA:
        return json.dumps(
            {"error": f"bundled corpora only: {', '.join(_BUNDLED_CORPORA)}"}, ensure_ascii=False
        )
    doc = aegean.load(corpus_id).get(doc_id.strip())
    if doc is None:
        return json.dumps(
            {"error": f"no document {doc_id!r} in the {corpus_id} corpus"}, ensure_ascii=False
        )
    return json.dumps({"id": doc.id, "xml": to_epidoc(doc)}, ensure_ascii=False)


def explain(text: str) -> str:
    """Explain what the offline pipeline did to each token: the lemma's evidence class
    (attested / rule / seed / paradigm / identity / unresolved / punct), whether the token
    needs review, and a one-line note saying what that class means. Rendered from the same
    records the pipeline returns, never a re-run; there are no confidence numbers by design
    (the neural pipeline's calibrated confidence needs the model, which is out of the browser)."""
    from aegean import greek

    tokens = [
        {
            "token": e.token,
            "upos": e.upos,
            "lemma": e.lemma,
            "source": e.lemma_source.value,
            "review": e.needs_review,
            "morphology": e.morphology or "",
            "note": e.note,
        }
        for e in greek.explain_pipeline(text)
    ]
    return json.dumps({"text": text, "tokens": tokens}, ensure_ascii=False)


def diagnose_corpus(corpus_id: str, deep: bool = False) -> str:
    """A descriptive corpus-health report for a bundled corpus: reading-status profile,
    accounting reconciliation (a discrepancy is a lead, not a verdict), numeral anomalies,
    provenance and citation, annotation-review state, and (deep) sign-frequency outliers.
    Every check that does not apply to a corpus is marked so, never an error."""
    import aegean
    from aegean.core.diagnose import ACCOUNTING_CAVEAT

    corpus_id = corpus_id.strip().lower()
    if corpus_id not in _BUNDLED_CORPORA:
        return json.dumps(
            {"error": f"bundled corpora only: {', '.join(_BUNDLED_CORPORA)}"}, ensure_ascii=False
        )
    rep = aegean.load(corpus_id).diagnose("full" if deep else "quick")
    s, a, nm, rv, sg, p = (
        rep.reading_status, rep.accounting, rep.numerals, rep.review, rep.signs, rep.provenance,
    )
    out: dict[str, Any] = {
        "corpus": corpus_id,
        "documents": rep.n_documents,
        "tokens": rep.n_tokens,
        "reading_status": {
            "certain": s.certain, "unclear": s.unclear, "restored": s.restored,
            "lost": s.lost, "documents_with_apparatus": s.documents_with_apparatus,
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
                "density": round(rv.density, 4),
            }
            if rv.applicable
            else {"applicable": False, "note": rv.note}
        ),
    }
    if deep and sg.applicable and sg.computed:
        out["signs"] = {
            "distinct": sg.distinct_signs,
            "hapax": sg.hapax_count,
            "out_of_inventory_occurrences": sg.out_of_inventory_occurrences,
            "out_of_inventory_distinct": sg.out_of_inventory_distinct,
        }
    return json.dumps(out, ensure_ascii=False)


def apparatus(corpus_id: str) -> str:
    """The editorial-apparatus profile of a bundled corpus, in one uniform shape: the
    four reading-status counts, how many documents carry any non-certain text, the
    alternate-reading tally, and a legend of only the apparatus that actually occurs
    (Leiden underdots/brackets, EpiDoc <unclear>/<supplied>/<gap>)."""
    import aegean
    from aegean.core.apparatus import apparatus_summary

    corpus_id = corpus_id.strip().lower()
    if corpus_id not in _BUNDLED_CORPORA:
        return json.dumps(
            {"error": f"bundled corpora only: {', '.join(_BUNDLED_CORPORA)}"}, ensure_ascii=False
        )
    summ = apparatus_summary(aegean.load(corpus_id))
    return json.dumps(
        {
            "corpus": corpus_id,
            "documents": summ.n_documents,
            "tokens": summ.n_tokens,
            "status_counts": summ.status_counts,
            "non_certain": summ.non_certain,
            "documents_with_apparatus": summ.documents_with_apparatus,
            "alt_reading_tokens": summ.alt_reading_tokens,
            "marker_notes": list(summ.marker_notes),
        },
        ensure_ascii=False,
    )


def linearb_dossiers(min_docs: str = "2") -> str:
    """Group the bundled Linear B tablets into archival dossiers by shared find-site AND
    series prefix (the standard Mycenological working unit, e.g. the Knossos Np tablets).
    ``min_docs`` keeps only groupings that large. The bundled sample records scribal-hand
    attributions for just a couple of tablets, so hand breakdowns are usually empty here;
    the full corpus (aegean.load('damos')) fills them in."""
    import aegean
    from aegean.analysis.hands import dossiers

    try:
        md = max(1, int(str(min_docs)))
    except (TypeError, ValueError):
        md = 1
    ds = dossiers(aegean.load("linearb"), min_docs=md)
    return json.dumps(
        {
            "min_docs": md,
            "total": len(ds),
            "dossiers": [
                {
                    "site": d.site,
                    "series": d.series,
                    "documents": d.doc_count,
                    "doc_ids": d.doc_ids,
                    "hands": d.hands,
                    "periods": d.periods,
                }
                for d in ds
            ],
        },
        ensure_ascii=False,
    )


def seriate_site(site: str = "Zakros") -> str:
    """Seriate one Linear A find-site's tablets by Brainerd-Robinson sign similarity: a
    deterministic ordering that places compositionally similar tablets next to each other.
    EXPLORATORY: a relative-sequence hypothesis, not a date, with no inherent direction; on
    an undeciphered script the axis may track scribal drift as readily as time."""
    import aegean
    from aegean.analysis.seriation import seriate

    la = aegean.load("lineara")
    site = site.strip()
    sub = la.filter(site=site)
    if not sub.documents:
        sites = sorted({d.meta.site for d in la.documents if d.meta.site})
        return json.dumps(
            {"error": f"no Linear A documents from site {site!r}", "sites": sites},
            ensure_ascii=False,
        )
    try:
        res = seriate(sub)
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    return json.dumps(
        {
            "site": site,
            "documents": len(sub.documents),
            "seriated": len(res.order),
            "order": list(res.ordered_labels() or ()),
            "note": (
                "EXPLORATORY: a compositional-sequence hypothesis with no direction and no "
                "calendar anchor; on undeciphered Linear A the axis may track scribal or "
                "graphotactic drift, not time."
            ),
        },
        ensure_ascii=False,
    )


def allographs(script: str = "linearb") -> str:
    """The catalogued sign-variant groups a script's inventory records: numbered homophone
    series (RA / RA₂ / RA₃) and Cypro-Minoan catalogue-suffix variants (CM012 / CM012B).
    EXPLORATORY and deliberately narrow — this is the catalogue's NAMING, not palaeographic
    allography (the same sign drawn differently by different hands), which the data does not
    carry. Ligature/compound signs are listed separately, never folded into a group."""
    from aegean.analysis.allographs import variant_groups

    try:
        rep = variant_groups(script.strip())
    except KeyError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    return json.dumps(
        {
            "script": rep.script_id,
            "signs": rep.n_signs,
            "groups": [
                {"base": g.base, "members": list(g.members), "kind": g.kind}
                for g in rep.groups
            ],
            "composites": list(rep.composite_signs),
            "note": rep.notes,
        },
        ensure_ascii=False,
    )
