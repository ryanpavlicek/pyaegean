"""Normalize a hosted corpus asset's token text to NFC, and prove the diff is only that.

The epigraphic corpora were built from editions transcribed in a mix of composed and
decomposed Unicode, so one word is stored under two spellings. Byte comparison then splits
the frequency counts and a word search finds only one of them: ``χάριν`` matches 1 of its 98
occurrences in EDH.

This rewrites an existing asset rather than rebuilding from upstream on purpose. A rebuild
would fold in whatever the source repositories have changed since, mixing an unrelated diff
into a correction that must be auditable; normalizing the shipped bytes keeps the change
provably equal to ``unicodedata.normalize("NFC", ...)`` on ``Token.text`` and nothing else.
``scripts/_epidoc.py`` applies the same normalization at build time, so a future rebuild
starts correct.

Usage::

    python scripts/normalize_corpus_nfc.py <corpus-id> <in.json> <out.json>
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path
from typing import Any


def _walk_tokens(payload: dict[str, Any]):
    for document in payload.get("documents", []):
        for token in document.get("tokens", []):
            yield document, token


def normalize_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    """Return the NFC-normalized payload and a census of what changed."""
    stats = {"tokens": 0, "changed": 0, "documents_touched": 0}
    touched: set[str] = set()
    for document, token in _walk_tokens(payload):
        stats["tokens"] += 1
        text = token.get("text")
        if not isinstance(text, str):
            continue
        composed = unicodedata.normalize("NFC", text)
        if composed != text:
            token["text"] = composed
            stats["changed"] += 1
            touched.add(str(document.get("id")))
    stats["documents_touched"] = len(touched)
    return payload, stats


def verify(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Every difference between the two payloads must be an NFC normalization of a token's
    text. Anything else is reported, and the caller must not ship the result."""
    problems: list[str] = []
    docs_before = before.get("documents", [])
    docs_after = after.get("documents", [])
    if len(docs_before) != len(docs_after):
        problems.append(f"document count changed: {len(docs_before)} -> {len(docs_after)}")
        return problems
    for da, db in zip(docs_before, docs_after):
        if da.get("id") != db.get("id"):
            problems.append(f"document id changed: {da.get('id')} -> {db.get('id')}")
            continue
        ta, tb = da.get("tokens", []), db.get("tokens", [])
        if len(ta) != len(tb):
            problems.append(f"{da.get('id')}: token count {len(ta)} -> {len(tb)}")
            continue
        for index, (x, y) in enumerate(zip(ta, tb)):
            keys = set(x) | set(y)
            for key in keys:
                if x.get(key) == y.get(key):
                    continue
                if key != "text":
                    problems.append(f"{da.get('id')} token {index}: field {key!r} changed")
                elif unicodedata.normalize("NFC", x.get("text", "")) != y.get("text"):
                    problems.append(f"{da.get('id')} token {index}: text change is not NFC")
        for key in set(da) | set(db):
            if key == "tokens":
                continue
            if da.get(key) != db.get(key):
                problems.append(f"{da.get('id')}: document field {key!r} changed")
    for key in set(before) | set(after):
        if key == "documents":
            continue
        if before.get(key) != after.get(key):
            problems.append(f"payload field {key!r} changed")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__)
        return 2
    _, corpus_id, source, target = argv
    raw = Path(source).read_text(encoding="utf-8")
    original = json.loads(raw)
    payload = json.loads(raw)  # an independent copy to mutate
    payload, stats = normalize_payload(payload)
    problems = verify(original, payload)
    print(f"{corpus_id}: {stats['tokens']} tokens, {stats['changed']} normalized, "
          f"{stats['documents_touched']} documents touched")
    if problems:
        print(f"REFUSING TO WRITE: {len(problems)} unexpected difference(s)")
        for line in problems[:20]:
            print(f"  {line}")
        return 1
    # Match the source asset's serialization exactly (indent 2, non-ASCII kept, CRLF), so
    # the byte diff against the shipped asset contains nothing but the normalized words.
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    Path(target).write_bytes(text.replace(chr(10), "\r\n").encode("utf-8"))
    print(f"  verified: every difference is an NFC normalization of Token.text -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
