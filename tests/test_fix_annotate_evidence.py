"""Annotation replacement keeps current evidence separate from review history."""

from __future__ import annotations

import csv
import importlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Literal

import pytest

from aegean.core.corpus import Corpus
from aegean.core.model import Document, SourceAlignment, Token, TokenFormState, TokenKind
from aegean.core.provenance import Provenance
from aegean.greek import LemmaSource, joint
from aegean.greek.annotate import annotate_corpus
from aegean.greek.joint import SentenceAnalysis
from aegean.io.review import REVIEW_COLUMNS, from_review_table, to_review_table


Backend = Literal["baseline", "neural", "custom"]

_OLD_EVIDENCE = {
    "lemma_source": "user",
    "lemma_resolved": "true",
    "lemma_verified": "true",
    "review_recommended": "false",
    "lemma_known": "true",
    "neural_analyzed": "false",
    "analysis_complete": "false",
    "analysis_warning": "earlier partial analysis",
}
_HISTORY = {
    "lemma__pred": "EARLIER-PREDICTION",
    "lemma_source__pred": "identity",
    "lemma_verified__pred": "false",
    "analysis_warning__pred": "historical warning",
    "review_status": "corrected",
    "reviewed_by": "prior-reviewer",
    "reviewers": "prior-reviewer",
    "review_note": "prior correction",
}
_UNRELATED = {
    "morph": "source morphology",
    "custom_id": "source-word-1",
    "other_lemma_source": "source-specific evidence",
    "analysis_warning_extra": "custom diagnostic",
}


class _NeuralBackend:
    """Return deterministic predictions through the real typed-token pipeline."""

    def __init__(self, lemma: str, *, partial: bool = False) -> None:
        self.lemma = lemma
        self.partial = partial
        self.calls: list[tuple[list[str], str]] = []

    def analyze(
        self,
        words: list[str],
        *,
        with_probs: bool = False,
        long_input: str = "strict",
    ) -> SentenceAnalysis:
        del with_probs
        self.calls.append((list(words), long_input))
        n = len(words)
        return SentenceAnalysis(
            tokens=tuple(words),
            upos=("X",) * n,
            xpos=("---------",) * n,
            feats=("_",) * n,
            head=(0,) * n,
            deprel=("root",) * n,
            lemma=(self.lemma,) * n,
            lemma_resolved=(not self.partial,) * n,
            lemma_source=(
                LemmaSource.IDENTITY if self.partial else LemmaSource.NEURAL_EDIT,
            ) * n,
            lemma_verified=(False,) * n,
            analyzed=(not self.partial,) * n,
            complete=not self.partial,
            truncated=self.partial,
            warnings=("current partial analysis",) if self.partial else (),
        )


def _corpus(*, old_evidence: bool = True) -> Corpus:
    annotations = {
        "lemma": "HUMAN-LEMMA",
        "upos": "NOUN",
        **_HISTORY,
        **_UNRELATED,
        **(_OLD_EVIDENCE if old_evidence else {}),
    }
    source = "λόγον.10"
    tokens = [
        Token(
            "λόγον", TokenKind.WORD, line_no=0, position=0,
            annotations=annotations,
            alignment=SourceAlignment(
                document_id="d", sentence_id=None, source_token_id="word-1",
                original_text="λόγον", start_char=0, end_char=5,
                whitespace_before="", normalized_text="λόγον",
            ),
            form_state=TokenFormState(diplomatic="λόγον", regularized="λόγος"),
        ),
    ]
    for position, (text, kind, start, end) in enumerate(
        ((".", TokenKind.PUNCT, 5, 6), ("10", TokenKind.NUMERAL, 6, 8)), start=1,
    ):
        tokens.append(Token(
            text, kind, line_no=0, position=position,
            annotations={**_OLD_EVIDENCE, "nonword": text},
            alignment=SourceAlignment(
                document_id="d", sentence_id=None, source_token_id=f"nonword-{position}",
                original_text=text, start_char=start, end_char=end,
                whitespace_before="", normalized_text=text,
            ),
        ))
    return Corpus(
        [Document("d", "greek", tokens, [[0, 1, 2]], source_text=source)],
        script_id="greek",
        provenance=Provenance(
            source="fixture", license="test", citation="Fixture citation",
            notes=("source history",),
        ),
    )


def _annotate(
    corpus: Corpus,
    *,
    monkeypatch: pytest.MonkeyPatch,
    backend: Backend,
    lemma: str,
    with_evidence: bool,
) -> Corpus:
    model = _NeuralBackend(lemma)
    if backend == "neural":
        monkeypatch.setattr(joint, "_ACTIVE", model)
    elif backend == "custom":
        # The explicit callback must win even when a neural backend is active.
        monkeypatch.setattr(joint, "_ACTIVE", model)
    else:
        monkeypatch.setattr(joint, "_ACTIVE", None)
        monkeypatch.setattr(
            importlib.import_module("aegean.greek.lemmatize"),
            "lemmatize_sourced", lambda _form: (lemma, LemmaSource.SEED),
        )
        monkeypatch.setattr(
            importlib.import_module("aegean.greek.pos"), "pos_tag", lambda _form: "X",
        )

    if backend == "custom":
        seen: list[list[str]] = []

        def tag(forms: list[str]) -> list[tuple[str, str]]:
            seen.append(list(forms))
            return [(lemma, "X") for _form in forms]

        out = annotate_corpus(corpus, tag_sentence=tag, with_evidence=with_evidence)
        assert seen == [["λόγος"]]
        assert model.calls == []
    else:
        out = annotate_corpus(corpus, with_evidence=with_evidence)
        if backend == "neural":
            assert model.calls == [(["λόγος"], "strict")]
    return out


def _expected_evidence(backend: Backend, with_evidence: bool) -> dict[str, str]:
    if not with_evidence or backend == "custom":
        return {}
    evidence = {
        "lemma_source": "seed" if backend == "baseline" else "neural_edit",
        "lemma_resolved": "true",
        "lemma_verified": "false",
        "review_recommended": "false",
        "lemma_known": "true",
    }
    if backend == "neural":
        evidence.update(neural_analyzed="true", analysis_complete="true")
    return evidence


@pytest.mark.parametrize("backend", ["baseline", "neural", "custom"])
@pytest.mark.parametrize("with_evidence", [False, True])
@pytest.mark.parametrize("same_lemma", [False, True])
def test_new_annotation_replaces_current_evidence_preserves_history_and_source(
    monkeypatch: pytest.MonkeyPatch,
    backend: Backend,
    with_evidence: bool,
    same_lemma: bool,
) -> None:
    corpus = _corpus()
    before = corpus.to_json()
    lemma = "HUMAN-LEMMA" if same_lemma else "NEW-PREDICTION"

    out = _annotate(
        corpus, monkeypatch=monkeypatch, backend=backend,
        lemma=lemma, with_evidence=with_evidence,
    )

    assert out.documents[0].tokens[0].annotations == {
        "lemma": lemma, "upos": "X", **_HISTORY, **_UNRELATED,
        **_expected_evidence(backend, with_evidence),
    }
    assert corpus.to_json() == before
    assert out.provenance == corpus.provenance
    assert out.documents[0].source_text == corpus.documents[0].source_text
    assert out.documents[0].tokens[0].alignment == corpus.documents[0].tokens[0].alignment
    assert out.documents[0].tokens[0].form_state == replace(
        corpus.documents[0].tokens[0].form_state,
        model_input="λόγος", model_input_source="regularized",
    )
    assert out.documents[0].tokens[1:] == corpus.documents[0].tokens[1:]


@pytest.mark.parametrize("backend", ["baseline", "neural", "custom"])
@pytest.mark.parametrize("with_evidence", [False, True])
@pytest.mark.parametrize("same_lemma", [False, True])
def test_reannotation_invalidates_only_replaced_field_reviews(
    monkeypatch: pytest.MonkeyPatch,
    backend: Backend,
    with_evidence: bool,
    same_lemma: bool,
) -> None:
    corpus = _corpus()
    token = corpus.documents[0].tokens[0]
    history = json.dumps([
        {"field": "lemma", "decision": "accept", "value": "HUMAN-LEMMA"},
        {"field": "upos", "decision": "correct", "value": "NOUN"},
        {"field": "morph", "decision": "accept", "value": "source morphology"},
    ])
    token.annotations.update({
        "lemma_review_decision": "accept",
        "lemma_reviewed_by": "lemma-reviewer",
        "lemma_review_note": "checked this contextual analysis",
        "upos_review_decision": "correct",
        "upos_verified": "true",
        "upos_reviewed_by": "syntax-reviewer",
        "morph_review_decision": "accept",
        "morph_verified": "true",
        "morph_reviewed_by": "edition-reviewer",
        "review_history": history,
    })
    original = corpus.to_json()

    result = _annotate(
        corpus, monkeypatch=monkeypatch, backend=backend,
        lemma="HUMAN-LEMMA" if same_lemma else "NEW-PREDICTION",
        with_evidence=with_evidence,
    )
    annotations = result.documents[0].tokens[0].annotations
    assert annotations["lemma_review_decision"] == "stale"
    assert annotations["upos_review_decision"] == "stale"
    assert annotations.get("lemma_verified") != "true"
    assert "upos_verified" not in annotations
    assert annotations["morph_review_decision"] == "accept"
    assert annotations["morph_verified"] == "true"
    assert annotations["morph"] == "source morphology"
    assert annotations["lemma_reviewed_by"] == "lemma-reviewer"
    assert annotations["lemma_review_note"] == "checked this contextual analysis"
    assert annotations["review_history"] == history
    assert corpus.to_json() == original


@pytest.mark.parametrize("with_evidence", [False, True])
def test_complete_neural_annotation_drops_prior_partial_warning(
    monkeypatch: pytest.MonkeyPatch, with_evidence: bool,
) -> None:
    model = _NeuralBackend("PARTIAL-PREDICTION", partial=True)
    monkeypatch.setattr(joint, "_ACTIVE", model)
    partial = annotate_corpus(_corpus(old_evidence=False), long_input="partial")
    assert model.calls == [(["λόγος"], "partial")]
    old = partial.documents[0].tokens[0].annotations
    assert old["neural_analyzed"] == "false"
    assert old["analysis_complete"] == "false"
    assert old["analysis_warning"] == "current partial analysis"
    before = partial.to_json()

    complete = _annotate(
        partial, monkeypatch=monkeypatch, backend="neural",
        lemma="COMPLETE-PREDICTION", with_evidence=with_evidence,
    )

    ann = complete.documents[0].tokens[0].annotations
    assert ann == {
        "lemma": "COMPLETE-PREDICTION", "upos": "X", **_HISTORY, **_UNRELATED,
        **_expected_evidence("neural", with_evidence),
    }
    assert partial.to_json() == before


@pytest.mark.parametrize("with_evidence", [False, True])
def test_baseline_annotation_drops_prior_neural_coverage(
    monkeypatch: pytest.MonkeyPatch, with_evidence: bool,
) -> None:
    neural = _annotate(
        _corpus(old_evidence=False), monkeypatch=monkeypatch, backend="neural",
        lemma="NEURAL-PREDICTION", with_evidence=True,
    )
    assert neural.documents[0].tokens[0].annotations["neural_analyzed"] == "true"
    before = neural.to_json()

    baseline = _annotate(
        neural, monkeypatch=monkeypatch, backend="baseline",
        lemma="BASELINE-PREDICTION", with_evidence=with_evidence,
    )

    assert baseline.documents[0].tokens[0].annotations == {
        "lemma": "BASELINE-PREDICTION", "upos": "X", **_HISTORY, **_UNRELATED,
        **_expected_evidence("baseline", with_evidence),
    }
    assert neural.to_json() == before


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames or ()) == REVIEW_COLUMNS
        return list(reader)


@pytest.mark.parametrize("backend", ["baseline", "neural", "custom"])
@pytest.mark.parametrize("with_evidence", [False, True])
@pytest.mark.parametrize("same_lemma", [False, True])
def test_reviewed_lemma_reannotation_roundtrips_as_unverified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backend: Backend,
    with_evidence: bool,
    same_lemma: bool,
) -> None:
    corpus = _corpus(old_evidence=False)
    token = corpus.documents[0].tokens[0]
    corpus.documents[0].tokens[0] = replace(
        token, annotations={"lemma": "INITIAL-PREDICTION", "upos": "X", **_UNRELATED},
    )
    review = tmp_path / "review.csv"
    assert to_review_table(corpus, review) == 1
    rows = _read_rows(review)
    rows[0]["correct_lemma"] = "HUMAN-CORRECTION"
    rows[0]["reviewer_note"] = "correction history"
    with review.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    corrected = from_review_table(review, corpus, reviewer="reviewer-1")
    corrected_path = tmp_path / "corrected.json"
    corrected.to_json(corrected_path)
    corrected = Corpus.from_json(corrected_path)
    old = corrected.documents[0].tokens[0].annotations
    assert old["lemma"] == "HUMAN-CORRECTION"
    assert old["lemma_source"] == "user" and old["lemma_verified"] == "true"
    assert old["lemma__pred"] == "INITIAL-PREDICTION"
    assert to_review_table(
        corrected, tmp_path / "verified.csv", selection="unverified",
    ) == 0
    before = corrected.to_json()
    lemma = "HUMAN-CORRECTION" if same_lemma else "FRESH-PREDICTION"

    reannotated = _annotate(
        corrected, monkeypatch=monkeypatch, backend=backend,
        lemma=lemma, with_evidence=with_evidence,
    )
    reannotated_path = tmp_path / "reannotated.json"
    reannotated.to_json(reannotated_path)
    persisted = Corpus.from_json(reannotated_path)

    ann = persisted.documents[0].tokens[0].annotations
    history = {key: value for key, value in old.items() if key not in _OLD_EVIDENCE}
    assert ann == {
        **history, "lemma": lemma, "upos": "X",
        "lemma_review_decision": "stale",
        **_expected_evidence(backend, with_evidence),
    }
    assert corrected.to_json() == before
    assert persisted.provenance == corrected.provenance
    unverified = tmp_path / "unverified.csv"
    assert to_review_table(persisted, unverified, selection="unverified") == 1
    rows = _read_rows(unverified)
    assert rows[0]["pred_lemma"] == lemma
    assert rows[0]["evidence_class"] == _expected_evidence(
        backend, with_evidence,
    ).get("lemma_source", "")
    assert rows[0]["needs_review"] == ""
