"""One sign rule for every sign-level count, and the Linear B apparatus it excludes.

``analysis.stats._bears_signs`` decides whether a token contributes signs. It used to
be restated in ``analysis.clustering`` as a kind-only filter, which let a Mycenaean
edition's apparatus (the Leiden brackets, ``mut.``, ``vest.``) into the sign-bigram
model that ``induce_classes`` clusters: on DAMOS the three commonest items of that
stream were ``[``, ``]`` and ``mut.``. These tests pin the rule to a single
implementation by comparing the two streams token for token, and pin the Linear B
loader's apparatus classification that the rule keys on.
"""

from __future__ import annotations

import pytest

from aegean.analysis import clustering, stats
from aegean.analysis.clustering import _sign_sequences, induce_classes
from aegean.analysis.stats import _items_of
from aegean.core.model import (
    Document,
    DocumentMeta,
    ReadingStatus,
    Token,
    TokenKind,
)
from aegean.scripts.linearb import loader


def _doc(doc_id: str, tokens: list[Token]) -> Document:
    return Document(
        id=doc_id,
        script_id="linearb",
        tokens=tokens,
        lines=[list(range(len(tokens)))] if tokens else [],
        meta=DocumentMeta(),
    )


def _clustering_stream(docs: list[Document]) -> list[str]:
    """The signs the bigram model of ``induce_classes`` is built over, in order."""
    return [
        s
        for seq in _sign_sequences(docs)
        for s in seq
        if s not in (clustering._START, clustering._END)
    ]


def _stats_stream(docs: list[Document]) -> list[str]:
    """The signs ``kind="signs"`` counts (frequency, dispersion, keyness), in order."""
    return [s for d in docs for s in _items_of(d, "signs")]


def _mixed_corpus() -> list[Document]:
    """A document carrying one token of every kind the sign rule must judge."""
    return [
        _doc(
            "MIXED",
            [
                Token("pa-i-to", TokenKind.WORD, ("pa", "i", "to"), None, 0, 0),
                Token("OVIS", TokenKind.LOGOGRAM, ("OVIS",), None, 0, 1),
                # apparatus: destroyed or unread, so not an attested reading
                Token(
                    "mut.", TokenKind.UNKNOWN, (), None, 0, 2,
                    status=ReadingStatus.LOST,
                    annotations={"apparatus": "mutila - mutilated"},
                ),
                # apparatus: notation about the object, between stretches of text
                Token(
                    "vac.", TokenKind.SEPARATOR, (), None, 0, 3,
                    status=ReadingStatus.CERTAIN,
                    annotations={"apparatus": "vacat - space left blank"},
                ),
                # a WORD whose reading is not preserved
                Token(
                    "ke-ro", TokenKind.WORD, ("ke", "ro"), None, 0, 4,
                    status=ReadingStatus.LOST,
                ),
                # a restored reading is kept: the editor is confident of it
                Token(
                    "[KO]", TokenKind.WORD, ("KO",), None, 0, 5,
                    status=ReadingStatus.RESTORED,
                ),
                Token("30", TokenKind.NUMERAL, ("30",), None, 0, 6),
                Token(".", TokenKind.PUNCT, (".",), None, 0, 7),
                # an empty label a decomposition left behind
                Token("wa-na-ka", TokenKind.WORD, ("wa", "", "ka"), None, 0, 8),
            ],
        )
    ]


# -- one rule, two consumers -------------------------------------------------


def test_clustering_and_stats_read_the_same_sign_stream():
    docs = _mixed_corpus()
    assert _clustering_stream(docs) == _stats_stream(docs)


def test_the_shared_stream_is_exactly_the_attested_signs():
    # Stated independently of either implementation: the signs a scribe wrote,
    # in order, with the lacuna reading, the apparatus, the numeral, the
    # punctuation and the empty label left out.
    assert _clustering_stream(_mixed_corpus()) == [
        "pa", "i", "to", "OVIS", "KO", "wa", "ka",
    ]


def test_apparatus_never_reaches_the_sign_stream():
    stream = _clustering_stream(_mixed_corpus())
    for marker in ("mut.", "vac.", "[KO]", "ke", "ro", "30", ".", ""):
        assert marker not in stream


def test_lost_reading_is_not_induced_as_a_sign_class_member():
    # A corpus whose only recurring context is a lacuna token: the lacuna must not
    # become a sign, and must not become the neighbour that defines a class.
    docs = [
        _doc(
            f"D{i}",
            [
                Token("a-ro", TokenKind.WORD, ("a", "ro"), None, 0, 0),
                Token(
                    "mut.", TokenKind.UNKNOWN, (), None, 0, 1,
                    status=ReadingStatus.LOST,
                    annotations={"apparatus": "mutila - mutilated"},
                ),
                Token("ka-ne", TokenKind.WORD, ("ka", "ne"), None, 0, 2),
            ],
        )
        for i in range(4)
    ]
    sc = induce_classes(docs, n_classes=2)
    members = sorted(s for cls in sc.classes() for s in cls)
    assert members == ["a", "ka", "ne", "ro"]
    assert sc.class_of("mut.") == -1
    assert sc.report.n_signs == 4
    assert sc.report.corpus_signs == 16  # 4 documents x 2 words x 2 signs


def test_a_corpus_of_apparatus_alone_raises_rather_than_clustering_it():
    docs = [
        _doc(
            "ALL-LOST",
            [
                Token(
                    "]vest.[", TokenKind.UNKNOWN, (), None, 0, 0,
                    status=ReadingStatus.LOST,
                    annotations={"apparatus": "vestigia - traces of signs, not read"},
                ),
                Token("1", TokenKind.NUMERAL, ("1",), None, 0, 1),
            ],
        )
    ]
    with pytest.raises(ValueError, match="no signs"):
        induce_classes(docs, n_classes=2)


def test_clustering_imports_the_rule_rather_than_restating_it():
    assert clustering._bears_signs is stats._bears_signs
    assert clustering._sign_labels is stats._sign_labels


# -- the Linear B loader the rule keys on ------------------------------------


@pytest.mark.parametrize(
    ("text", "kind", "status"),
    [
        # destroyed or unread: nothing is preserved there
        ("mut.", TokenKind.UNKNOWN, ReadingStatus.LOST),
        ("vest.", TokenKind.UNKNOWN, ReadingStatus.LOST),
        ("]vest.[", TokenKind.UNKNOWN, ReadingStatus.LOST),
        ("deest", TokenKind.UNKNOWN, ReadingStatus.LOST),
        ("[", TokenKind.UNKNOWN, ReadingStatus.LOST),
        ("]", TokenKind.UNKNOWN, ReadingStatus.LOST),
        # notation about the object: text stands on either side of it
        ("vac.", TokenKind.SEPARATOR, ReadingStatus.CERTAIN),
        ("v.", TokenKind.SEPARATOR, ReadingStatus.CERTAIN),
        ("lat. dex.".split()[1], TokenKind.SEPARATOR, ReadingStatus.CERTAIN),
        ("⟦⟧", TokenKind.SEPARATOR, ReadingStatus.CERTAIN),
    ],
)
def test_apparatus_token_carries_no_signs(text, kind, status):
    t = loader.classify(text, 0, 0)
    assert (t.kind, t.status) == (kind, status)
    assert t.signs == ()
    assert "apparatus" in t.annotations
    assert not stats._bears_signs(t)


@pytest.mark.parametrize(
    ("text", "kind", "signs", "status"),
    [
        ("pa-i-to", TokenKind.WORD, ("pa", "i", "to"), ReadingStatus.CERTAIN),
        # a restored reading is classified on the text inside its brackets
        ("[ko-no]", TokenKind.WORD, ("ko", "no"), ReadingStatus.RESTORED),
        ("[KO]", TokenKind.LOGOGRAM, ("KO",), ReadingStatus.RESTORED),
        ("OVIS", TokenKind.LOGOGRAM, ("OVIS",), ReadingStatus.CERTAIN),
        ("VIR+[?]", TokenKind.LOGOGRAM, ("VIR+[?]",), ReadingStatus.UNCLEAR),
        ("𐄁", TokenKind.SEPARATOR, ("𐄁",), ReadingStatus.CERTAIN),
        ("30", TokenKind.NUMERAL, ("30",), ReadingStatus.CERTAIN),
    ],
)
def test_reading_keeps_its_signs_and_status(text, kind, signs, status):
    t = loader.classify(text, 0, 0)
    assert (t.kind, t.signs, t.status) == (kind, signs, status)
    assert "apparatus" not in t.annotations


def test_bracket_status_is_the_only_reader_of_the_brackets():
    # A reading and an apparatus token bracketed the same way get the same status,
    # because both ask `_bracket_status`. A second inline copy of the rule would
    # let the two drift.
    for text in ("[KO]", "VIR+[?]", "pa-i-to", "]ke", "ki[", "a-?"):
        assert loader.classify(text, 0, 0).status == loader._bracket_status(text)
    assert loader._bracket_status("[KO]") is ReadingStatus.RESTORED
    assert loader._bracket_status("VIR+[?]") is ReadingStatus.UNCLEAR
    assert loader._bracket_status("]ke") is ReadingStatus.UNCLEAR
    assert loader._bracket_status("pa-i-to") is ReadingStatus.CERTAIN


def test_apparatus_marker_is_module_private():
    # Nothing outside the loader consumes it; the expansion travels in
    # `annotations["apparatus"]`.
    assert "apparatus_marker" not in vars(loader)
    assert callable(loader._apparatus_marker)
    assert loader._apparatus_marker("mut.") == ("mut.", "mutila — mutilated")
    assert loader._apparatus_marker("pa-i-to") is None


def test_loader_built_document_excludes_its_apparatus_from_the_sign_stream():
    # The real classification path, over a transliteration line as an edition
    # prints it.
    line = ["pa-i-to", "]vest.[", "OVIS", "mut.", "30", "vac.", "ka-ne"]
    docs = [_doc("PY-Ln", [loader.classify(w, 0, i) for i, w in enumerate(line)])]
    assert _clustering_stream(docs) == ["pa", "i", "to", "OVIS", "ka", "ne"]
    assert _clustering_stream(docs) == _stats_stream(docs)
