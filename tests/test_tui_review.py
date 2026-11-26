"""Headless session and Textual Pilot tests for interactive annotation review."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from aegean.core.corpus import Corpus
from aegean.core.model import Document, Token, TokenKind
from aegean.io.review import from_review_table, to_review_table
from aegean.tui._review_data import ReviewSession


def _sample_corpus(*, with_confidence: bool = False) -> Corpus:
    t0_ann = {
        "lemma": "ἄνθρωπος",
        "upos": "NOUN",
        "morph": "N-NSM",
        "lemma_source": "lexicon",
    }
    t1_ann = {
        "lemma": "λέγω",
        "upos": "VERB",
        "morph": "V-PAI-3S",
        "lemma_source": "identity",
        "review_recommended": "true",
    }
    t2_ann = {
        "lemma": "λόγος",
        "upos": "NOUN",
        "morph": "N-ASM",
        "lemma_source": "lexicon",
    }
    if with_confidence:
        t0_ann["confidence_lemma"] = "0.95"
        t1_ann["confidence_lemma"] = "0.41"
        t2_ann["confidence_lemma"] = "0.78"
    doc = Document(
        id="doc1",
        script_id="greek",
        tokens=(
            Token(text="ἄνθρωπος", kind=TokenKind.WORD, position=0, line_no=1, annotations=t0_ann),
            Token(text="λέγει", kind=TokenKind.WORD, position=1, line_no=1, annotations=t1_ann),
            Token(text="λόγον", kind=TokenKind.WORD, position=2, line_no=1, annotations=t2_ann),
        ),
        lines=((0, 1, 2),),
    )
    return Corpus(documents=(doc,), script_id="greek")


def test_review_session_editable_round_trip(tmp_path: Path) -> None:
    corpus = _sample_corpus()
    csv_path = tmp_path / "editable.csv"
    to_review_table(
        corpus,
        csv_path,
        fields=("lemma", "pos"),
        layout="editable",
        reviewer="alice",
    )

    session = ReviewSession.from_csv(csv_path, corpus=corpus)
    assert session.layout == "editable"
    assert len(session.items) == 3
    assert session.items[1].needs_review is True
    assert "[λέγει]" in session.items[1].sentence_context

    # Accept row 0, correct row 1 lemma, pass identical value on row 2 (auto-accepts)
    assert session.accept_item(0) == ["lemma", "pos"]
    assert session.correct_field(1, "lemma", "λαλέω", note="contextual sense") == "correct"
    assert session.correct_field(2, "lemma", "λόγος") == "accept"
    assert session.dirty is True

    saved = session.save()
    assert saved == csv_path
    assert session.dirty is False

    # Must pass cryptographic snapshot & companion verification in from_review_table
    updated = from_review_table(csv_path, corpus)
    toks = updated.documents[0].tokens
    assert toks[0].annotations["lemma_verified"] == "true"
    assert toks[1].annotations["lemma"] == "λαλέω"
    assert toks[1].annotations["lemma__pred"] == "λέγω"
    assert toks[1].annotations["review_note"] == "contextual sense"
    assert toks[2].annotations["lemma_verified"] == "true"


def test_review_session_multi_reviewer_conflict_adjudication(tmp_path: Path) -> None:
    corpus = _sample_corpus()
    alice_csv = tmp_path / "alice.csv"
    bob_csv = tmp_path / "bob.csv"
    to_review_table(corpus, alice_csv, fields=("lemma",), layout="editable", reviewer="alice")
    to_review_table(corpus, bob_csv, fields=("lemma",), layout="editable", reviewer="bob")

    s_alice = ReviewSession.from_csv(alice_csv, corpus=corpus, reviewer="alice")
    s_alice.accept_item(0)
    s_alice.correct_field(1, "lemma", "λαλέω", note="alice reading")
    s_alice.save()

    s_bob = ReviewSession.from_csv(bob_csv, corpus=corpus, reviewer="bob")
    s_bob.accept_item(0)
    s_bob.correct_field(1, "lemma", "εἴρω", note="bob reading")
    s_bob.save()

    merged_session = ReviewSession.from_merge([alice_csv, bob_csv], corpus, reviewer="editor")
    counts = merged_session.summary_counts()
    assert counts["conflicts"] == 1
    assert merged_session.filtered_indices("conflicts") == [1]

    conflict_item = merged_session.items[1]
    assert "lemma" in conflict_item.unresolved_conflicts
    assert len(conflict_item.unresolved_conflicts["lemma"]) == 2

    chosen = merged_session.pick_conflict_option(1, "lemma", 0)
    assert chosen.value in ("λαλέω", "εἴρω")
    assert merged_session.summary_counts()["conflicts"] == 0

    resolved_csv = tmp_path / "resolved.csv"
    merged_session.save(resolved_csv)
    applied = from_review_table(resolved_csv, corpus)
    assert applied.documents[0].tokens[1].annotations["lemma"] == chosen.value
    assert applied.documents[0].tokens[0].annotations["lemma_verified"] == "true"


def test_review_session_live_calibrated_risk_queue(tmp_path: Path) -> None:
    corpus = _sample_corpus(with_confidence=True)
    save_path = tmp_path / "risk.csv"
    session = ReviewSession.from_corpus(
        corpus,
        save_path=save_path,
        fields=("lemma",),
        priority="auto",
        reviewer="scholar",
    )
    # Lowest calibrated confidence (0.41 -> λέγει) must come first
    assert [it.token for it in session.items] == ["λέγει", "λόγον", "ἄνθρωπος"]
    assert session.items[0].confidence == pytest.approx(0.41)
    assert session.next_unresolved(0) == 1
    assert session.prev_unresolved(0) == 2

    session.accept_item(0)
    updated, count = session.apply_to_corpus(output_path=tmp_path / "reviewed.json")
    assert count == 1
    assert (tmp_path / "reviewed.json").is_file()
    assert updated.documents[0].tokens[1].annotations["lemma_verified"] == "true"


def test_tui_review_screen_pilot_workflow(tmp_path: Path) -> None:
    pytest.importorskip("textual")
    from textual.widgets import Static

    from aegean.tui.app import AegeanApp, CorpusCommands
    from aegean.tui.screens.review import ReviewScreen

    corpus = _sample_corpus(with_confidence=True)
    corpus_json = tmp_path / "corpus.json"
    corpus.to_json(corpus_json)

    csv_path = tmp_path / "queue.csv"
    to_review_table(
        corpus,
        csv_path,
        fields=("lemma",),
        layout="editable",
        priority="calibrated_risk",
        reviewer="pilot",
    )

    async def body() -> None:
        # 1. Command palette lists Annotation review & 'r' switches to ReviewScreen
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            provider = CorpusCommands(app.screen)
            hits = [h async for h in provider.search("Annotation review")]
            assert any("Annotation review" in str(h.text) for h in hits)
            await pilot.press("r")
            await pilot.pause()
            assert isinstance(app.screen, ReviewScreen)

        # 2. Direct launch via review_paths + corpus opens ReviewScreen and resolves via keys
        app2 = AegeanApp(corpus=str(corpus_json), review_paths=(str(csv_path),))
        async with app2.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app2.screen, ReviewScreen)
            screen = app2.screen
            assert screen.session is not None
            assert len(screen.session.items) == 3

            # Accept first (highest-risk) token with 'a', then save with 's'
            await pilot.press("a")
            await pilot.pause()
            assert screen.session.items[0].decisions["lemma"] == "accept"
            assert screen.session.dirty is True

            await pilot.press("s")
            await pilot.pause()
            assert screen.session.dirty is False
            status_text = str(screen.query_one("#review-status", Static).content)
            assert "[green]1[/green]/3" in status_text

            # Cycle filter with 'f'
            await pilot.press("f")
            await pilot.pause()
            assert screen.filter_mode == "unresolved"

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(body())
    finally:
        loop.close()

    # Saved CSV from TUI must pass full cryptographic verification on apply
    applied = from_review_table(csv_path, corpus)
    assert applied.documents[0].tokens[1].annotations["lemma_verified"] == "true"


def test_tui_review_screen_pilot_conflict_resolution(tmp_path: Path) -> None:
    pytest.importorskip("textual")
    from aegean.tui.app import AegeanApp
    from aegean.tui.screens.review import ReviewScreen

    corpus = _sample_corpus()
    corpus_json = tmp_path / "corpus.json"
    corpus.to_json(corpus_json)

    a_csv = tmp_path / "alice.csv"
    b_csv = tmp_path / "bob.csv"
    to_review_table(corpus, a_csv, fields=("lemma",), layout="editable", reviewer="alice")
    to_review_table(corpus, b_csv, fields=("lemma",), layout="editable", reviewer="bob")

    s_a = ReviewSession.from_csv(a_csv, corpus=corpus, reviewer="alice")
    s_a.correct_field(1, "lemma", "λαλέω")
    s_a.save()

    s_b = ReviewSession.from_csv(b_csv, corpus=corpus, reviewer="bob")
    s_b.correct_field(1, "lemma", "εἴρω")
    s_b.save()

    async def body() -> None:
        app = AegeanApp(corpus=str(corpus_json), review_paths=(str(a_csv), str(b_csv)))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, ReviewScreen)
            screen = app.screen
            assert screen.session is not None
            assert screen.filter_mode == "conflicts"
            assert screen.session.summary_counts()["conflicts"] == 1

            # Resolve disagreement with key '1'
            await pilot.press("1")
            await pilot.pause()
            assert screen.session.summary_counts()["conflicts"] == 0
            assert screen.session.items[1].corrections["lemma"] in ("λαλέω", "εἴρω")

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(body())
    finally:
        loop.close()
