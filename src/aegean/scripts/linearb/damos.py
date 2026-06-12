"""DAMOS — the Database of Mycenaean at Oslo, as a loadable Linear B corpus (opt-in, fetched).

DAMOS (https://damos.hf.uio.no, Aurora 2015) is the most complete edition of the
Mycenaean (Linear B) corpus, published under **CC BY-NC-SA 4.0**. pyaegean's
``damos-corpus`` release asset is the transliterations + core metadata decoded from
the DAMOS public web API into compact JSON (``scripts/build_damos_corpus.py``); this
module fetches that asset to the cache (never bundled — NonCommercial data stays out
of the Apache-2.0 wheel) and exposes it through the standard corpus model. The
NonCommercial + ShareAlike obligations pass through to you; cite DAMOS in academic
work (see ``NOTICE``).

This is the openly-licensed full Linear B corpus the bundled sample stands in for:
``aegean.load("damos")`` gives ~5,900 tablets (Knossos, Pylos, Thebes, …) with their
DAMOS transliterations, where ``aegean.load("linearb")`` gives only a curated sample.
"""

from __future__ import annotations

import re
from typing import Any

# A leading line label: ``.1``, ``.2``, ``.10``, ``.a``, ``.A``, ``.lat.`` …
_LINE_LABEL_RE = re.compile(r"^\.[A-Za-z0-9]+\.?$")
# Word dividers in Mycenaean transliteration: comma and slash.
_DIVIDERS = {",", "/"}


def _tokens_for_line(line: str, line_no: int, start_pos: int) -> list[Any]:
    """Tokenise one DAMOS content line, reusing the Linear B classifier.

    Strips a leading line label, maps the comma/slash word dividers to separator
    tokens, peels supraliteral quotes (``'me-no'``) before classifying, and lets
    ``loader.classify`` assign WORD / NUMERAL / LOGOGRAM / editorial status to the
    rest. Returns the tokens (positions already assigned)."""
    from ...core.model import Token, TokenKind
    from .loader import classify

    pieces = line.split()
    if pieces and _LINE_LABEL_RE.match(pieces[0]):
        pieces = pieces[1:]
    out: list[Any] = []
    pos = start_pos
    for piece in pieces:
        if piece in _DIVIDERS:
            out.append(Token(piece, TokenKind.SEPARATOR, (piece,), None, line_no, pos))
        else:
            inner = piece
            if len(inner) >= 2 and inner[0] == "'" and inner[-1] == "'":
                inner = inner[1:-1]  # supraliteral insertion written above the line
            out.append(classify(inner, line_no, pos))
        pos += 1
    return out


def _build_document(rec: dict[str, Any]) -> Any:
    from ...core.model import Document, DocumentMeta

    content = rec.get("content") or ""
    tokens: list[Any] = []
    lines: list[list[int]] = []
    for li, raw_line in enumerate(content.splitlines()):
        if not raw_line.strip():
            continue
        line_tokens = _tokens_for_line(raw_line, li, len(tokens))
        if not line_tokens:
            continue
        idxs = list(range(len(tokens), len(tokens) + len(line_tokens)))
        tokens.extend(line_tokens)
        lines.append(idxs)
    heading = rec.get("heading") or f"DAMOS {rec.get('id')}"
    # v2 find context: the area (e.g. "PY, Room 8") plus the grid ref when given.
    findspot = " — ".join(
        s for s in (rec.get("find_area"), rec.get("find_spot")) if s
    )
    meta = DocumentMeta(
        site=rec.get("site") or "",
        support=rec.get("support") or "",
        scribe=rec.get("scribe") or "",
        findspot=findspot,
        period=rec.get("chronology") or "",
        name=heading,
    )
    return Document(
        id=heading,
        script_id="linearb",
        tokens=tokens,
        lines=lines,
        transcription=content,
        meta=meta,
    )


def load_damos() -> Any:
    """Load the DAMOS Linear B corpus as a `Corpus` (opt-in, fetched).

    Fetches the ``damos-corpus`` release asset (a few MB JSON; sha256-pinned;
    **CC BY-NC-SA 4.0** — the NonCommercial obligation passes to you) on first
    use, then loads offline from the cache. One `Document` per tablet, carrying
    the DAMOS transliteration (verbatim in ``transcription``) tokenised into
    words / numerals / logograms, with the site, chronology, **scribal hand**
    (``meta.scribe``, e.g. ``"117"``), find context (``meta.findspot``), and
    object class (``meta.support``: tablet / stirrup jar / nodule / label) in
    the metadata — so ``corpus.filter(scribe="117")`` and scribal-hand keyness
    work directly. Cite DAMOS in academic work (see ``NOTICE``)."""
    import json as _json

    from ...core.corpus import Corpus
    from ...core.provenance import Provenance
    from ...data import fetch
    from .inventory import linear_b_inventory

    path = fetch("damos-corpus")
    payload = _json.loads(path.read_text(encoding="utf-8"))
    meta = payload.get("_meta", {})
    docs = [_build_document(rec) for rec in payload["documents"]]
    provenance = Provenance(
        source="DAMOS — Database of Mycenaean at Oslo (F. Aurora), decoded dataset",
        license="CC BY-NC-SA 4.0 (as published by DAMOS; NonCommercial — fetched, never bundled)",
        citation=str(
            meta.get(
                "cite",
                "Aurora, F. (2015). DAMOS (Database of Mycenaean at Oslo). "
                "Procedia - Social and Behavioral Sciences, 198, 21-31.",
            )
        ),
        url="https://damos.hf.uio.no",
        data_version=f"damos-corpus-v{meta.get('version', 1)}@{meta.get('generated', '')}",
        notes=(
            "Mycenaean (Linear B) corpus; transliterations + core metadata decoded from "
            "the DAMOS public API. Word boundaries follow DAMOS (comma/slash dividers). "
            "v2 carries the DAMOS-curated scribal hand (meta.scribe), find context "
            "(meta.findspot), and object class (meta.support).",
        ),
    )
    return Corpus(docs, sign_inventory=linear_b_inventory(), provenance=provenance, script_id="linearb")


# loadable by name: aegean.load("damos") — fetches the corpus to the cache on first use
from ...core.corpus import register_loader  # noqa: E402

register_loader("damos", load_damos)
