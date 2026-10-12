"""Retained reader context reaches translation separately from the selected line."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from typing import Any

import pytest

from aegean import ai, translate
from aegean.ai.cache import ResponseCache
from aegean.ai.client import LLMClient, LLMResponse
from aegean.core.corpus import Corpus
from aegean.core.model import (
    Document,
    DocumentMeta,
    FormSegment,
    ReadingStatus,
    SourceMarkupRef,
    TokenFormState,
)
from aegean.core.provenance import Provenance
from aegean.greek.tokenize import tokenize_aligned
from aegean.tui import data as adapter


def _document(doc_id: str, source: str, *, aligned: bool = True) -> Document:
    tokens = list(tokenize_aligned(source, document_id=doc_id))
    lines: list[list[int]] = []
    offset = 0
    for index, line in enumerate(source.splitlines(keepends=True)):
        indices = [
            i for i, token in enumerate(tokens)
            if token.alignment is not None
            and offset <= token.alignment.start_char < offset + len(line)
        ]
        for i in indices:
            annotations = {"lemma": "MODEL_ONLY_LEMMA", "morph": "MODEL_ONLY_MORPH"}
            if index in (1, 3):
                annotations.update({
                    "who": "#hermes" if index == 1 else "#kore",
                    "speaker": "hermes" if index == 1 else "kore",
                    "speaker_label": "ΕΡ." if index == 1 else "ΚΟ.",
                    "speech_id": f"said[{index}]", "ref": f"edition:{index + 1}",
                })
            tokens[i] = replace(
                tokens[i], position=0, line_no=index, annotations=annotations,
                alignment=tokens[i].alignment if aligned else None,
            )
        lines.append(indices)
        offset += len(line)
    return Document(
        id=doc_id, script_id="greek", tokens=tokens, lines=lines,
        source_text=source if aligned else None, meta=DocumentMeta(name=f"Title {doc_id}"),
    )


def _corpus(*, aligned: bool = True) -> Corpus:
    return Corpus(
        script_id="greek",
        documents=[
            _document("first", "πρότερον\tτι\nλόγος\nἐγώ\r\nλόγος\nὕστερον", aligned=aligned),
            _document("other", "ἄλλος\nλόγος\nτέλος", aligned=aligned),
        ],
        provenance=Provenance(
            source="Fixture source", citation="Exact citation\r\nretained ",
            url="https://example.test/edition", edition_fidelity="apparatus-preserved",
        ),
    )


def _context(corpus: Corpus, doc_id: str, line: int) -> dict[str, Any]:
    context = adapter._line_source_context(corpus, doc_id, line)
    assert context is not None
    return json.loads(context)


def test_context_preserves_aligned_source_and_only_source_annotations() -> None:
    corpus = _corpus()
    context = _context(corpus, "first", 2)
    assert [line["reader_line"] for line in context["lines"]] == [1, 2, 3]
    assert [line["selected"] for line in context["lines"]] == [False, True, False]
    assert [line["text"] for line in context["lines"]] == ["πρότερον\tτι", "λόγος", "ἐγώ"]
    assert all(line["text_origin"] == "aligned_source_slice" for line in context["lines"])
    assert context["source"]["citation"] == "Exact citation\r\nretained "
    metadata = context["lines"][1]["tokens"][0]["source_metadata"]
    assert metadata["who"] == "#hermes"
    assert metadata["speaker_label"] == "ΕΡ."
    assert "lemma" not in metadata and "morph" not in metadata
    assert "MODEL_ONLY" not in json.dumps(context)
    assert adapter._line_source_context(corpus, "first", 2) == adapter._line_source_context(
        corpus, "first", 2,
    )


def test_reconstructed_context_retains_damage_alternates_and_editorial_segments() -> None:
    corpus = _corpus(aligned=False)
    document = corpus.documents[0]
    index = document.lines[1][0]
    ref = SourceMarkupRef("edition", "supplied[1]", "supplied", (("reason", "lost"),))
    document.tokens[index] = replace(
        document.tokens[index], status=ReadingStatus.RESTORED, alt=("λόγον",),
        form_state=TokenFormState(
            diplomatic="λο̄γος", regularized="", normalized="MODEL_ONLY_NORMALIZED",
            model_input="MODEL_ONLY_INPUT", model_input_source="explicit",
            segments=(
                FormSegment("λό", ReadingStatus.UNCLEAR),
                FormSegment("γος", ReadingStatus.RESTORED, ref),
                FormSegment("", ReadingStatus.LOST),
            ),
        ),
    )
    context = _context(corpus, "first", 2)
    assert all(line["text_origin"] == "reconstructed_token_text" for line in context["lines"])
    token = context["lines"][1]["tokens"][0]
    assert token["text"] == "λόγος"
    assert token["status"] == "restored"
    assert token["alternates"] == ["λόγον"]
    assert token["editorial_state"] == {
        "diplomatic": "λο̄γος", "regularized": "",
        "segments": [
            {"text": "λό", "status": "unclear", "source_ref": None},
            {"text": "γος", "status": "restored", "source_ref": ref.to_dict()},
            {"text": "", "status": "lost", "source_ref": None},
        ],
    }
    assert "MODEL_ONLY" not in json.dumps(context)


@pytest.mark.parametrize(("line", "expected"), [(1, [1, 2]), (5, [4, 5])])
def test_neighbor_window_stops_at_document_boundaries(line: int, expected: list[int]) -> None:
    context = _context(_corpus(), "first", line)
    assert [row["reader_line"] for row in context["lines"]] == expected
    assert "ἄλλος" not in json.dumps(context, ensure_ascii=False)
    assert "τέλος" not in json.dumps(context, ensure_ascii=False)


def test_repeated_text_and_duplicate_token_positions_do_not_select_another_occurrence() -> None:
    corpus = _corpus()
    assert all(token.position == 0 for document in corpus for token in document.tokens)
    first = _context(corpus, "first", 2)
    later = _context(corpus, "first", 4)
    other = _context(corpus, "other", 2)
    assert first["lines"][1]["text"] == later["lines"][1]["text"] == "λόγος"
    assert later["selected_reader_line"] == 4
    assert [row["reader_line"] for row in later["lines"]] == [3, 4, 5]
    assert later["lines"][1]["tokens"][0]["source_metadata"]["who"] == "#kore"
    assert other["document_id"] == "other"
    assert [row["text"] for row in other["lines"]] == ["ἄλλος", "λόγος", "τέλος"]


@pytest.mark.parametrize(("doc_id", "line"), [(None, 1), ("missing", 1), ("first", 0), ("first", 6)])
def test_unavailable_document_or_line_does_not_invent_context(doc_id: str | None, line: int) -> None:
    assert adapter._line_source_context(_corpus(), doc_id, line) is None


def test_missing_source_metadata_is_not_filled_from_analysis_annotations() -> None:
    document = _document("bare", "λόγος", aligned=False)
    document.meta = DocumentMeta()
    context = _context(Corpus(documents=[document], script_id="greek"), "bare", 1)
    assert "source" not in context and "document_name" not in context
    assert len(context["lines"]) == 1
    assert "source_metadata" not in context["lines"][0]["tokens"][0]
    assert context["lines"][0]["text_origin"] == "reconstructed_token_text"


def test_selection_mismatch_and_bad_alignment_do_not_claim_an_exact_source() -> None:
    corpus = _corpus()
    assert adapter._line_source_context(corpus, "first", 2, token_texts=("different",)) is None
    document = corpus.documents[0]
    alignment = document.tokens[0].alignment
    assert alignment is not None
    document.tokens[0] = replace(
        document.tokens[0], alignment=replace(alignment, document_id="other"),
    )
    assert _context(corpus, "first", 1)["lines"][0]["text_origin"] == "reconstructed_token_text"
    # Noncontiguous line endpoints may enclose text belonging to another line.
    document.tokens[0] = replace(document.tokens[0], alignment=alignment)
    document.lines[0] = [0, 2]
    line = _context(corpus, "first", 1)["lines"][0]
    assert line["text_origin"] == "reconstructed_token_text"
    assert line["text"] == "πρότερον λόγος"


def test_context_does_not_change_other_line_analyses(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def ipa(text: str) -> adapter.AnalysisResult:
        seen.append(text)
        return adapter.AnalysisResult(ok=True, text="fixture IPA")

    monkeypatch.setattr(adapter, "_greek_ipa_result", ipa)
    result = adapter.run_line_analysis(
        "ipa", script_id="greek", text="λόγος", token_texts=("λόγος",),
        source_context="Surrounding text",
    )
    assert result.text == "fixture IPA"
    assert seen == ["λόγος"]


class ReaderClient(LLMClient):
    provider = "fixture"

    def __init__(self) -> None:
        super().__init__("reader-fixture", cache=ResponseCache())
        self.calls: list[str] = []

    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        self.calls.append(prompt)
        return LLMResponse(json.dumps({
            "translation": f"Fixture translation {len(self.calls)}",
            "uncertainties": [], "changes": [],
        }), self.provider, self.model)


def _fake_translation(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ReaderClient, list[str]]:
    client = ReaderClient()
    analyzed: list[str] = []

    def grounding(text: str, script: str, **kwargs: Any) -> Any:
        analyzed.append(text)
        return translate._GroundingOutcome([], {"mode": kwargs["mode"]})

    monkeypatch.setattr(adapter, "_usable_providers", lambda: ["fixture"])
    monkeypatch.setattr(ai, "get_client", lambda provider: client)
    monkeypatch.setattr(translate, "_build_grounding", grounding)
    monkeypatch.setattr(translate, "_rich_lemmatizer_active", lambda pipeline: True)
    return client, analyzed


def test_translation_adapter_preserves_selected_text_and_absent_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, analyzed = _fake_translation(monkeypatch)
    target = "  λόγος\r\n"
    result = adapter.translate_line(target)
    assert result.ok and result.text == "Fixture translation 1"
    assert analyzed == [target]
    assert target in client.calls[0]


@pytest.mark.xdist_group("tui")
def test_reader_selection_worker_and_translation_keep_target_and_document_context_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("textual")
    from aegean.tui.app import AegeanApp
    from aegean.tui.screens.analysis import LineAnalysisScreen
    from aegean.tui.screens.corpus import CorpusBrowserScreen
    from aegean.tui.widgets import DetailPane, DocTable

    corpus = _corpus()
    client, analyzed = _fake_translation(monkeypatch)
    monkeypatch.setattr(adapter, "read_corpus_spec", lambda spec: corpus)
    monkeypatch.setattr(adapter, "fetched_work_entries", lambda: [])
    monkeypatch.setattr(adapter, "line_analyses", lambda script_id: [
        adapter.AnalysisOption("translate", "translation", True),
    ])
    # Prime a real response cache with this same target without source context.
    assert adapter.translate_line("λόγος").text == "Fixture translation 1"

    async def journey() -> None:
        app = AegeanApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.open_corpus("fixture-reader")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CorpusBrowserScreen)
            for call, (doc_id, number) in enumerate((("first", 2), ("first", 4), ("other", 2)), 2):
                docs = screen.query_one("#corpus-docs", DocTable)
                docs.move_cursor(row=docs.get_row_index(doc_id))
                docs.focus()
                await pilot.press("enter")
                await pilot.pause()
                reader = screen.query_one("#corpus-detail", DetailPane)
                reader.focus()
                for _ in range(number - 1):
                    await pilot.press("down")
                await pilot.press("enter")
                await pilot.pause()
                await app.workers.wait_for_complete()
                await pilot.pause()
                modal = app.screen
                assert isinstance(modal, LineAnalysisScreen)
                context = adapter._line_source_context(corpus, doc_id, number)
                assert context is not None and modal._source_context == context
                assert modal._line_text == "λόγος"
                assert analyzed[-1] == "λόγος"
                assert len(client.calls) == call
                assert context in client.calls[-1]
                assert f"Fixture translation {call}" in str(modal.output_text())
                await pilot.press("escape")
                await pilot.pause()
            assert analyzed == ["λόγος"] * 4

    asyncio.run(journey())
