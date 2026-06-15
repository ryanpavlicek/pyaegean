"""`aegean analyze cooccur` must return a deterministic order so docs/examples are
reproducible across runs (the per-document word sets iterate in hash order, which would
otherwise shuffle rows tied at the same shared-document count)."""

from __future__ import annotations

import json


def test_cooccur_deterministic_order() -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    r = CliRunner().invoke(
        _build_app(), ["analyze", "cooccur", "lineara", "KU-RO", "--top", "8", "--json"]
    )
    assert r.exit_code == 0, r.output
    rows = json.loads(r.stdout)
    assert rows, "expected co-occurring words for KU-RO"
    # rows are sorted by (-shared_documents, word) — the deterministic tie-break
    keys = [(-row["shared_documents"], row["word"]) for row in rows]
    assert keys == sorted(keys)
    assert rows[0]["word"] == "KI-RO"  # the single unambiguous top hit
