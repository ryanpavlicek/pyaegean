"""Correctness tests for the TUI library adapter (`aegean.tui.data`).

Plain pytest, no Textual: the adapter is the seam that holds every library call
the screens make, so this is the bulk of the TUI's coverage. Each test asserts
real content (a known count, a known scansion, a known balance), not that a call
runs. The parity block is the anti-drift contract: the adapter and the CLI must
produce identical balance and pipeline rows, routed through the same
`aegean._view` mappings.
"""

from __future__ import annotations

import aegean
from aegean.tui import data as adapter


# ── corpora ──────────────────────────────────────────────────────────────────
def test_list_corpora_returns_the_eight_registered_ids() -> None:
    entries = adapter.list_corpora()
    assert [e.id for e in entries] == list(adapter.CORPUS_IDS)
    assert len(adapter.CORPUS_IDS) == 8
    # every listed id is a real registered loader (the adapter must not drift by
    # naming a corpus that does not exist); the registry may also hold loaders
    # that other tests registered, so this is a subset check, not equality.
    from aegean.core.corpus import _LOADERS

    assert set(adapter.CORPUS_IDS) <= set(_LOADERS)


def test_bundled_corpora_are_downloaded_and_lineara_is_flagged_undeciphered() -> None:
    by_id = {e.id: e for e in adapter.list_corpora()}
    # bundled corpora are always available
    assert by_id["lineara"].downloaded is True and by_id["lineara"].bundled is True
    assert by_id["greek"].bundled is True
    # the fetch-on-demand corpora are not bundled
    assert by_id["damos"].bundled is False and by_id["sigla"].bundled is False
    # undeciphered scripts are flagged for the honesty caveat
    assert by_id["lineara"].undeciphered is True
    assert by_id["cyprominoan"].undeciphered is True
    assert by_id["greek"].undeciphered is False
    assert by_id["nt"].undeciphered is False


def test_sigla_is_flagged_undeciphered_in_the_overview() -> None:
    """SigLA is the Salgarella & Castellan Linear A dataset; Linear A is
    undeciphered, so the corpus overview must flag it (like ``lineara`` and
    ``cyprominoan``) so the honesty caption is not dropped for it. Before the fix
    only ``lineara`` and ``cyprominoan`` were flagged and SigLA read as decipherable."""
    # sigla is registered as a Linear A corpus: its loader lives under the
    # lineara script package, so its script (undeciphered) is Linear A.
    from aegean.scripts.lineara.sigla import load_sigla  # noqa: F401

    # the adapter's undeciphered set and per-corpus flag both include sigla
    assert "sigla" in adapter.UNDECIPHERED
    assert adapter.is_undeciphered("sigla") is True
    by_id = {e.id: e for e in adapter.list_corpora()}
    assert by_id["sigla"].undeciphered is True


def test_is_undeciphered_matches_the_undeciphered_corpora() -> None:
    # Linear A (both bundled lineara and the SigLA dataset) and Cypro-Minoan
    assert adapter.is_undeciphered("lineara") is True
    assert adapter.is_undeciphered("sigla") is True
    assert adapter.is_undeciphered("cyprominoan") is True
    # deciphered corpora are not flagged
    assert adapter.is_undeciphered("linearb") is False
    assert adapter.is_undeciphered("cypriot") is False
    assert adapter.is_undeciphered("nt") is False
    assert adapter.is_undeciphered("greek") is False


def test_load_corpus_loads_a_bundled_corpus() -> None:
    corpus = adapter.load_corpus("lineara")
    assert len(corpus) == 1721


def test_load_corpus_raises_tui_error_on_a_bad_id() -> None:
    import pytest

    with pytest.raises(adapter.TuiError) as exc:
        adapter.load_corpus("no-such-corpus")
    assert "no-such-corpus" in str(exc.value)


# ── documents ─────────────────────────────────────────────────────────────────
def test_document_rows_has_one_row_per_document_with_known_structure() -> None:
    corpus = adapter.load_corpus("lineara")
    rows = adapter.document_rows(corpus)
    assert len(rows) == 1721
    by_id = {r.id: r for r in rows}
    # HT13 is a Linear A accounting tablet (KU-RO total)
    assert by_id["HT13"].structure == "accounting"
    assert by_id["HT13"].n_words > 0


def test_document_detail_carries_tokens_status_and_the_undeciphered_flag() -> None:
    corpus = adapter.load_corpus("lineara")
    detail = adapter.document_detail(corpus, "HT13")
    assert detail.id == "HT13"
    assert detail.undeciphered is True  # Linear A
    assert detail.structure == "accounting"
    # the first physical line begins with KA-U-DE-TA (the transliteration)
    first_line = detail.lines[0]
    assert first_line.number == 1
    assert first_line.tokens[0].text == "KA-U-DE-TA"
    # every token exposes an editorial status a screen can style on
    assert first_line.tokens[0].status in {"certain", "unclear", "restored", "lost"}


def test_document_detail_forgives_the_document_id() -> None:
    corpus = adapter.load_corpus("lineara")
    # the forgiving resolver folds case/space (ht13 -> HT13)
    detail = adapter.document_detail(corpus, "ht13")
    assert detail.id == "HT13"


def test_document_detail_raises_tui_error_for_a_missing_document() -> None:
    import pytest

    corpus = adapter.load_corpus("lineara")
    with pytest.raises(adapter.TuiError):
        adapter.document_detail(corpus, "definitely-not-a-doc")


def test_nt_detail_surfaces_per_token_annotations() -> None:
    # The Greek NT carries gold lemma/morph/Strong's/gloss as token annotations;
    # the detail must pass them through so a screen can show them.
    import pytest

    try:
        corpus = adapter.load_corpus("nt")
    except adapter.TuiError:
        pytest.skip("nt corpus not downloaded in this environment")
    rows = adapter.document_rows(corpus)
    detail = adapter.document_detail(corpus, rows[0].id)
    annotated = [
        tok
        for line in detail.lines
        for tok in line.tokens
        if tok.annotations
    ]
    assert annotated, "expected NT tokens to carry annotations"
    assert any("lemma" in tok.annotations for tok in annotated)


# ── search ────────────────────────────────────────────────────────────────────
def test_search_corpus_matches_a_wildcard_sign_pattern() -> None:
    corpus = adapter.load_corpus("lineara")
    hits = adapter.search_corpus(corpus, "KU-*-RO")
    assert hits, "KU-*-RO should match at least one Linear A word"
    # every hit is a three-sign word starting KU and ending RO
    for word, count in hits:
        signs = word.split("-")
        assert len(signs) == 3 and signs[0] == "KU" and signs[-1] == "RO"
        assert count >= 1
    # results are sorted by descending frequency
    counts = [c for _w, c in hits]
    assert counts == sorted(counts, reverse=True)


def test_search_corpus_empty_pattern_matches_nothing() -> None:
    corpus = adapter.load_corpus("lineara")
    assert adapter.search_corpus(corpus, "") == []


# ── balance (via the shared _view mapping) ────────────────────────────────────
def test_balance_rows_ht13_has_a_kuro_total_that_does_not_balance() -> None:
    corpus = adapter.load_corpus("lineara")
    doc = corpus.get("HT13")
    assert doc is not None
    rows = adapter.balance_rows(doc)
    assert len(rows) == 1
    row = rows[0]
    assert row.doc == "HT13"
    assert row.marker == "KU-RO"
    assert row.stated == 130.5
    assert row.computed == 131.0
    assert row.difference == 0.5
    assert row.balances is False
    assert isinstance(row.balances, bool)


# ── Greek workbench helpers ───────────────────────────────────────────────────
def test_greek_scan_iliad_1_1_matches_the_known_hexameter_pattern() -> None:
    line = "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"
    result = adapter.greek_scan(line, "hexameter")
    assert result.ok
    # the exact glyph pattern greek.scan_line returns for Iliad 1.1
    assert result.summary.startswith("—⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×")
    # six feet, one row each
    assert len(result.rows) == 6
    assert result.rows[0]["foot"] == "dactyl"


def test_greek_scan_bad_meter_returns_error_not_exception() -> None:
    result = adapter.greek_scan("μῆνιν ἄειδε", "not-a-meter")
    assert result.ok is False
    assert "not-a-meter" in result.error
    assert result.rows == []


def test_greek_syllables_splits_a_known_word() -> None:
    result = adapter.greek_syllables("θάλασσα")
    assert result.ok
    assert [r["syllable"] for r in result.rows] == ["θά", "λασ", "σα"]
    assert result.summary == "θά-λασ-σα"


def test_greek_ipa_transcribes_a_known_word() -> None:
    result = adapter.greek_ipa("λόγος", "attic")
    assert result.ok
    assert result.summary == "loɡos"


def test_greek_ipa_bad_period_returns_error() -> None:
    result = adapter.greek_ipa("λόγος", "klingon")
    assert result.ok is False
    assert result.error


def test_greek_pipeline_returns_one_row_per_token_with_known_analysis() -> None:
    result = adapter.greek_pipeline("μῆνιν ἄειδε θεά")
    assert result.ok
    assert [r["text"] for r in result.rows] == ["μῆνιν", "ἄειδε", "θεά"]
    first = result.rows[0]
    assert first["upos"] == "NOUN"
    assert first["lemma"] == "μῆνις"
    assert first["lemma_known"] is True


def test_greek_helpers_return_empty_for_blank_input() -> None:
    for result in (
        adapter.greek_pipeline("  "),
        adapter.greek_scan("  "),
        adapter.greek_syllables(""),
        adapter.greek_ipa(""),
    ):
        assert result.ok and result.rows == []


# ── data store ────────────────────────────────────────────────────────────────
def test_doctor_report_is_the_build_report_verbatim() -> None:
    from aegean._doctor import build_report

    report = adapter.doctor_report()
    assert report["versions"]["pyaegean"] == aegean.__version__
    # same shape and keys as the doctor command's report
    assert set(report) == set(build_report())


def test_dataset_rows_list_the_fetch_on_demand_corpora() -> None:
    names = {r.name for r in adapter.dataset_rows()}
    assert {"damos-corpus", "sigla-corpus", "nt-corpus"} <= names
    for row in adapter.dataset_rows():
        assert isinstance(row.downloaded, bool)


def test_fetch_dataset_unknown_name_raises_tui_error() -> None:
    import pytest

    with pytest.raises(adapter.TuiError):
        adapter.fetch_dataset("no-such-dataset")


def test_fetch_dataset_delegates_to_the_library_fetch_and_reports_progress(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Never hit the network: patch the library fetch, prove the adapter dispatches
    # to it and drives on_progress. Uses a real registered dataset name.
    import pathlib

    import aegean.data as data_mod

    calls: list[str] = []
    progress: list[str] = []

    def fake_fetch(name: str, *, force: bool = False, abort=None) -> pathlib.Path:  # type: ignore[no-untyped-def]
        calls.append(name)
        return pathlib.Path("/fake/store") / name

    monkeypatch.setattr(data_mod, "fetch", fake_fetch)
    path = adapter.fetch_dataset("damos-corpus", on_progress=progress.append)
    assert calls == ["damos-corpus"]
    assert path == pathlib.Path("/fake/store") / "damos-corpus"
    # progress is reported before and after
    assert any("fetching" in p for p in progress)
    assert any("stored" in p for p in progress)


# ── PARITY: the CLI and the TUI cannot show different numbers ──────────────────
def test_balance_parity_cli_and_tui_produce_identical_rows_for_ht13() -> None:
    """The anti-drift contract for accounting: the CLI's balance command and the
    TUI adapter both route through `aegean._view.balance_rows`, so their rows are
    identical by construction. This pins it as a permanent regression."""
    from aegean._view import balance_rows as view_rows

    corpus = aegean.load("lineara")
    doc = corpus.get("HT13")
    assert doc is not None

    cli_rows = view_rows(doc)  # exactly what `aegean balance` emits
    tui_rows = adapter.balance_rows(doc)

    # the adapter's dataclass rows carry the same field values as the CLI dicts
    assert len(cli_rows) == len(tui_rows) == 1
    cli, tui = cli_rows[0], tui_rows[0]
    assert cli["doc"] == tui.doc
    assert cli["marker"] == tui.marker
    assert cli["stated"] == tui.stated
    assert cli["computed"] == tui.computed
    assert cli["difference"] == tui.difference
    assert cli["items"] == tui.items
    assert cli["balances"] == tui.balances


def test_pipeline_parity_cli_and_tui_produce_identical_rows_for_iliad_1_1() -> None:
    """The anti-drift contract for the Greek pipeline: the CLI's pipeline output
    and the TUI adapter both route through `aegean._view.pipeline_rows`, so a
    token row is identical across surfaces."""
    from aegean._view import pipeline_rows

    line = "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"
    cli_rows = pipeline_rows(line)  # what `aegean greek pipeline` maps from
    tui_result = adapter.greek_pipeline(line)

    assert tui_result.ok
    assert tui_result.rows == cli_rows
    # and the content is the known analysis, not just "equal to itself"
    assert cli_rows[0]["text"] == "μῆνιν"
    assert cli_rows[0]["upos"] == "NOUN"
    assert cli_rows[0]["lemma"] == "μῆνις"


def test_balance_view_matches_a_fresh_balance_check_recompute() -> None:
    """The shared mapping's numbers must match a fresh `analysis.balance_check`,
    so the row shaping never silently diverges from the analysis it reports."""
    from aegean._view import balance_rows as view_rows
    from aegean.analysis import balance_check

    corpus = aegean.load("lineara")
    doc = corpus.get("HT13")
    assert doc is not None

    recomputed = balance_check(doc)
    rows = view_rows(doc)
    assert len(rows) == len(recomputed)
    for row, chk in zip(rows, recomputed):
        assert row["marker"] == chk.marker
        assert row["stated"] == chk.stated_total
        assert row["computed"] == chk.computed_sum
        assert row["difference"] == chk.difference
        assert row["balances"] == chk.balances


def test_cli_pipeline_json_equals_the_shared_view_rows() -> None:
    # The CLI `greek pipeline --json` and the TUI both emit aegean._view's rows,
    # so the two surfaces cannot drift on the pipeline table either (the balance
    # parity above plus this closes both shared surfaces).
    import json as _json

    from typer.testing import CliRunner

    from aegean._view import pipeline_rows
    from aegean.cli import _build_app

    text = "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"
    res = CliRunner().invoke(_build_app(), ["greek", "pipeline", text, "--json"])
    assert res.exit_code == 0, res.output
    assert _json.loads(res.stdout) == pipeline_rows(text)
