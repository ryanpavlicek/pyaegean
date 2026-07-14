"""A6 typed-token analysis path tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from aegean.core.corpus import Corpus
from aegean.core.model import (
    Document,
    SourceAlignment,
    Token,
    TokenFormState,
    TokenKind,
)
from aegean.greek import LemmaSource, joint
from aegean.greek.joint import SentenceAnalysis
from aegean.greek.pipeline import pipeline, pipeline_tokens
from aegean.greek.runtime import GreekPipeline
from aegean.greek.annotate import annotate_corpus


def _state(form: str = "regularized") -> TokenFormState:
    return TokenFormState(
        diplomatic="diplomatic",
        regularized=form,
        normalized="normalized",
        model_input=None,
        segments=(),
        model_input_ops=(),
        model_input_source=None,
    )


class _NeuralStub:
    def __init__(self, *, nfc: bool = False, mismatch: bool = False) -> None:
        self.words: list[list[str]] = []
        self.nfc = nfc
        self.mismatch = mismatch

    def analyze(self, words: list[str]) -> SentenceAnalysis:
        self.words.append(words)
        returned = ["ά" if self.nfc and word == "α\u0301" else word for word in words]
        if self.mismatch:
            returned = returned[:-1]
        n = len(returned)
        return SentenceAnalysis(
            tokens=tuple(returned),
            upos=tuple("NOUN" for _ in returned),
            xpos=tuple("n-s---mn-" for _ in returned),
            feats=tuple("Case=Nom" for _ in returned),
            head=tuple(0 for _ in returned),
            deprel=tuple("root" for _ in returned),
            lemma=tuple(word for word in returned),
            lemma_resolved=tuple(True for _ in returned),
            lemma_source=tuple(LemmaSource.NEURAL for _ in returned),
            analyzed=tuple(True for _ in range(n)),
        )


def _typed_token(text: str = "legacy", *, state: TokenFormState | None = None) -> Token:
    return Token(text, TokenKind.WORD, position=0, form_state=state)


def test_explicit_regularized_form_is_selected_and_facade_matches_instance() -> None:
    token = _typed_token(state=_state())
    facade = pipeline_tokens([token])
    instance = GreekPipeline().analyze_tokens([token])
    assert [(r.text, r.lemma, r.upos) for r in facade] == [
        (r.text, r.lemma, r.upos) for r in instance
    ]
    assert facade[0].text == "regularized"
    assert facade[0].form_state is not None
    assert facade[0].form_state.model_input == "regularized"
    assert facade[0].form_state.model_input_source == "regularized"
    assert facade[0].form_state.model_input_ops == ()


def test_neural_model_input_records_nfc_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _NeuralStub(nfc=True)
    monkeypatch.setattr(joint, "_ACTIVE", stub)
    state = TokenFormState(
        diplomatic="α\u0301",
        model_input="α\u0301",
        model_input_ops=("editorial:choice",),
        model_input_source="explicit",
    )
    token = _typed_token("legacy", state=state)
    (record,) = pipeline_tokens([token])
    assert stub.words == [["α\u0301"]]
    assert record.text == "ά"
    assert record.form_state is not None
    assert record.form_state.model_input == "ά"
    assert record.form_state.model_input_source == "explicit"
    assert record.form_state.model_input_ops == ("editorial:choice", "unicode:nfc")


def test_punctuation_sentence_mapping_and_alignment_survive() -> None:
    first = _typed_token("λόγος")
    punct = Token(".", TokenKind.PUNCT, position=1)
    second = Token("καί", TokenKind.WORD, position=2)
    records = pipeline_tokens([first, punct, second])
    assert [(record.text, record.sentence, record.index) for record in records] == [
        ("λόγος", 0, 1), (".", 0, 2), ("καί", 1, 1)
    ]

    alignment = SourceAlignment(
        document_id="d",
        sentence_id=None,
        source_token_id="w1",
        original_text="λόγος",
        start_char=0,
        end_char=5,
        whitespace_before="",
        normalized_text="λόγος",
    )
    aligned = replace(first, alignment=alignment)
    assert pipeline_tokens([aligned])[0].alignment == alignment


def test_empty_selected_form_fails_before_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    state = TokenFormState(diplomatic="seen", regularized="")

    def explode(*args: object, **kwargs: object) -> object:
        raise AssertionError("backend was consulted")

    import aegean.greek.pos as pos_module

    monkeypatch.setattr(pos_module, "pos_tags", explode)
    with pytest.raises(ValueError, match="selected token form must be non-empty"):
        pipeline_tokens([_typed_token(state=state)])


def test_empty_diplomatic_fallback_is_not_mislabeled_as_diplomatic() -> None:
    state = TokenFormState(diplomatic="")
    record = pipeline_tokens([_typed_token("legacy", state=state)])[0]
    assert record.form_state is not None
    assert record.form_state.model_input == "legacy"
    assert record.form_state.model_input_source == "explicit"


def test_neural_count_mismatch_is_clean_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(joint, "_ACTIVE", _NeuralStub(mismatch=True))
    with pytest.raises(ValueError, match="different token count"):
        pipeline_tokens([_typed_token(), _typed_token("second")])


def test_annotate_uses_typed_form_and_preserves_state_alignment() -> None:
    state = _state("regularized")
    alignment = SourceAlignment(
        document_id="d",
        sentence_id=None,
        source_token_id="w1",
        original_text="legacy",
        start_char=0,
        end_char=6,
        whitespace_before="",
        normalized_text="legacy",
    )
    token = Token("legacy", TokenKind.WORD, line_no=0, position=0, form_state=state, alignment=alignment)
    corpus = Corpus(
        [Document("d", "greek", [token], [[0]], source_text="legacy")],
        script_id="greek",
    )
    out = annotate_corpus(corpus)
    annotated = out.documents[0].tokens[0]
    assert annotated.annotations["lemma"] == "regularized"
    assert annotated.form_state is not None
    assert annotated.form_state.model_input == "regularized"
    assert annotated.alignment == alignment
    restored = Corpus.from_json(out.to_json())
    assert restored.documents[0].tokens[0].form_state == annotated.form_state
    assert restored.documents[0].tokens[0].alignment == alignment


def test_annotate_baseline_keeps_the_legacy_per_token_tagger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aegean.greek.pos as pos_module

    seen: list[str] = []

    def tag_one(form: str) -> str:
        seen.append(form)
        return "NOUN"

    def contextual_changed(_text: str) -> list[tuple[str, str]]:
        raise AssertionError("the contextual tagger would change the legacy path")

    monkeypatch.setattr(pos_module, "pos_tag", tag_one)
    monkeypatch.setattr(pos_module, "pos_tags", contextual_changed)
    token = Token(
        "legacy",
        TokenKind.WORD,
        line_no=0,
        position=0,
        form_state=_state("regularized"),
    )
    corpus = Corpus([Document("d", "greek", [token], [[0]])], script_id="greek")
    annotated = annotate_corpus(corpus).documents[0].tokens[0]
    assert seen == ["regularized"]
    assert annotated.annotations["upos"] == "NOUN"


def test_annotate_does_not_invent_form_state_for_legacy_tokens() -> None:
    token = Token("λόγος", TokenKind.WORD, line_no=0, position=0)
    corpus = Corpus([Document("d", "greek", [token], [[0]])], script_id="greek")
    annotated = annotate_corpus(corpus).documents[0].tokens[0]
    assert annotated.form_state is None


def test_plain_pipeline_pre_a6_fields_remain_unchanged() -> None:
    records = pipeline("λόγος.")
    assert [(r.sentence, r.index, r.text, r.upos, r.lemma, r.lemma_source,
              r.head, r.relation, r.xpos, r.feats, r.alignment is not None)
             for r in records] == [
        (0, 1, "λόγος", "NOUN", "λόγος", LemmaSource.SEED, None, None, None, None, True),
        (0, 2, ".", "PUNCT", ".", LemmaSource.PUNCT, None, None, None, None, True),
    ]
