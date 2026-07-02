"""The Python the browser demo runs under Pyodide.

Stable, pure-Python 0.8.x APIs only — everything here runs entirely client-side: the Greek
pipeline + scansion + word analysis, the bundled Koine (Dodson) lexicon, the offline Greek
work catalogue, the deciphered-syllabary Greek bridge, the bundled Linear A corpus
(sign search + accounting), the bundled Cypriot (IG XV 1) inscription corpus, the file importer,
the stdlib EpiDoc reader, and cross-script phonetic comparison. The
neural tier is excluded (it needs onnxruntime, which doesn't run in the browser), as are the
network-only backends (load_work/load_nt, LSJ/treebank) and the generative AI layer. Each
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
