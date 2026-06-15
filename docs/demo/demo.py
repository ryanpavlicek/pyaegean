"""The Python the browser demo runs under Pyodide.

Stable, pure-Python 0.8.x APIs only: the Greek pipeline + scansion and the bundled Linear A
corpus all run entirely client-side. The neural tier is deliberately excluded (it needs
onnxruntime, which doesn't run in the browser) and so is the generative AI layer. Each
function returns a JSON string for easy consumption from JavaScript. This module is exercised
by tests/test_web_demo.py, so the demo's logic can't silently rot.
"""

from __future__ import annotations

import json
from typing import Any


def greek_pipeline(text: str) -> str:
    """Per-token (text, UPOS, lemma) for a Greek sentence — the baseline pipeline."""
    from aegean import greek

    recs = [
        {"text": r.text, "upos": r.upos, "lemma": r.lemma}
        for r in greek.pipeline(text)
    ]
    return json.dumps(recs, ensure_ascii=False)


def greek_scan(text: str, meter: str = "hexameter") -> str:
    """Scan a Greek verse line; returns the glyph pattern or a decline reason."""
    from aegean import greek

    try:
        sc = greek.scan_line(text, meter)
        out: dict[str, Any] = {"scans": True, "meter": sc.meter, "pattern": sc.pattern}
    except greek.ScansionError as exc:
        out = {"scans": False, "error": str(exc)}
    return json.dumps(out, ensure_ascii=False)


def betacode(text: str) -> str:
    """Convert Beta Code (plain-ASCII polytonic Greek) to Unicode."""
    from aegean import greek

    return json.dumps({"unicode": greek.betacode_to_unicode(text)}, ensure_ascii=False)


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
