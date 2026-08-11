"""``kind="signs"`` counts signs, not the marks an edition writes around them.

Word/entry dividers, transcribed numerals, punctuation, and the placeholders that
stand for an unpreserved reading are excluded from the sign stream, so sign
frequency, dispersion, and keyness tables describe the script. ``kind="words"``
keeps its previous behaviour exactly, including for tokens whose reading is lost.
"""

from __future__ import annotations

import pytest

import aegean
from aegean.analysis import stats
from aegean.core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind

# The Linear A word divider and the upstream erased/illegible marker; neither is a
# sign of the script, and both used to head the bundled corpus's sign tables.
DIVIDER = "\U00010101"
ERASED = "\U0001076B"


def _doc(doc_id: str, tokens: list[Token]) -> Document:
    placed = [
        Token(
            t.text,
            t.kind,
            t.signs,
            t.glyphs,
            0,
            i,
            status=t.status,
        )
        for i, t in enumerate(tokens)
    ]
    return Document(
        id=doc_id,
        script_id="lineara",
        tokens=placed,
        lines=[list(range(len(placed)))] if placed else [],
        meta=DocumentMeta(),
    )


def _tok(
    text: str,
    kind: TokenKind,
    signs: tuple[str, ...] = (),
    status: ReadingStatus = ReadingStatus.CERTAIN,
) -> Token:
    return Token(text, kind, signs, None, 0, 0, status=status)


# ── the exact item streams of one hand-built document ───────────────────────


def _mixed_document() -> Document:
    """One document holding every token kind and every reading status."""
    return _doc(
        "MIXED",
        [
            _tok("KU-RO", TokenKind.WORD, ("KU", "RO")),
            _tok(DIVIDER, TokenKind.SEPARATOR, (DIVIDER,)),
            _tok("GRA", TokenKind.LOGOGRAM, ("GRA",)),
            _tok("20", TokenKind.NUMERAL, ("20",)),
            _tok("¹⁄₂", TokenKind.NUMERAL, ("¹⁄₂",)),
            _tok(ERASED, TokenKind.UNKNOWN, (ERASED,), ReadingStatus.LOST),
            _tok("𐝉", TokenKind.UNKNOWN, ("𐝉",)),
            _tok("PA-I-TO", TokenKind.WORD, ("PA", "I", "TO"), ReadingStatus.UNCLEAR),
            _tok("DA-RE", TokenKind.WORD, ("DA", "RE"), ReadingStatus.RESTORED),
            _tok(".", TokenKind.PUNCT, (".",)),
        ],
    )


def test_signs_stream_is_exactly_the_sign_bearing_labels():
    # Dividers, both numerals, the lost placeholder and the punctuation mark are
    # gone; the logogram, the metrological sign, and the damaged and restored
    # readings all stay, because each of those is a sign the edition reports.
    assert stats._items_of(_mixed_document(), "signs") == [
        "KU",
        "RO",
        "GRA",
        "𐝉",
        "PA",
        "I",
        "TO",
        "DA",
        "RE",
    ]


def test_words_stream_is_unchanged_by_the_sign_rule():
    # Every WORD token, whatever its status; no kind or status filtering applies.
    assert stats._items_of(_mixed_document(), "words") == ["KU-RO", "PA-I-TO", "DA-RE"]


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        (_tok(DIVIDER, TokenKind.SEPARATOR, (DIVIDER,)), []),
        (_tok("—", TokenKind.SEPARATOR, ("—",)), []),
        (_tok("20", TokenKind.NUMERAL, ("20",)), []),
        (_tok(",", TokenKind.PUNCT, (",",)), []),
        (_tok(ERASED, TokenKind.UNKNOWN, (ERASED,), ReadingStatus.LOST), []),
        (_tok("A-BC", TokenKind.WORD, (), ReadingStatus.LOST), []),
        (_tok("𐝉", TokenKind.UNKNOWN, ("𐝉",)), ["𐝉"]),
        (_tok("GRA", TokenKind.LOGOGRAM, ("GRA",), ReadingStatus.UNCLEAR), ["GRA"]),
        (_tok("GRA", TokenKind.LOGOGRAM, ("GRA",), ReadingStatus.RESTORED), ["GRA"]),
        (_tok("A-B", TokenKind.WORD, ("A", "B")), ["A", "B"]),
        (_tok("A-B", TokenKind.WORD, ()), ["A", "B"]),  # decomposed from the text
    ],
)
def test_one_token_at_a_time(token: Token, expected: list[str]):
    assert stats._items_of(_doc("D", [token]), "signs") == expected


def test_unclear_and_restored_readings_are_kept_but_lost_is_not():
    # The boundary that matters editorially: damaged-but-read and editorially
    # supplied text are readings; a lacuna is not.
    kept = _doc(
        "K",
        [
            _tok("A", TokenKind.WORD, ("A",), ReadingStatus.UNCLEAR),
            _tok("B", TokenKind.WORD, ("B",), ReadingStatus.RESTORED),
            _tok("C", TokenKind.WORD, ("C",), ReadingStatus.CERTAIN),
            _tok("D", TokenKind.WORD, ("D",), ReadingStatus.LOST),
        ],
    )
    assert stats._items_of(kept, "signs") == ["A", "B", "C"]
    # ...while the words stream still reports all four, lacuna included.
    assert stats._items_of(kept, "words") == ["A", "B", "C", "D"]


def test_empty_sign_labels_never_enter_the_stream():
    # The Cypriot illegible run "-..-" carries no signs, so the hyphen split of
    # its text yields leading and trailing empty labels; an empty string is not
    # a countable sign under any reading.
    doc = _doc(
        "E",
        [
            _tok("-..-", TokenKind.UNKNOWN, ()),
            _tok("-A-", TokenKind.WORD, ()),
            _tok("-", TokenKind.WORD, ()),
        ],
    )
    assert "" not in stats._items_of(doc, "signs")
    assert stats._items_of(doc, "signs") == ["..", "A"]


# ── adversarial / degenerate input ──────────────────────────────────────────


def test_document_of_nothing_but_non_signs_yields_no_items():
    doc = _doc(
        "N",
        [
            _tok(DIVIDER, TokenKind.SEPARATOR, (DIVIDER,)),
            _tok("1", TokenKind.NUMERAL, ("1",)),
            _tok(ERASED, TokenKind.UNKNOWN, (ERASED,), ReadingStatus.LOST),
        ],
    )
    assert stats._items_of(doc, "signs") == []
    assert stats._items_of(doc, "words") == []


def test_corpus_of_nothing_but_non_signs_raises_the_documented_error():
    # A clean ValueError from the documented guard, never a ZeroDivisionError or
    # an IndexError out of the DP tables.
    docs = [
        _doc("A", [_tok("1", TokenKind.NUMERAL, ("1",))]),
        _doc("B", [_tok(DIVIDER, TokenKind.SEPARATOR, (DIVIDER,))]),
    ]
    with pytest.raises(ValueError, match="no countable items"):
        stats.dispersions(docs, kind="signs")
    with pytest.raises(ValueError, match="no countable items"):
        stats.dispersion(docs, "1", kind="signs")
    with pytest.raises(ValueError, match="both corpora must contain countable items"):
        stats.keyness(docs, docs, kind="signs")


def test_asking_for_an_excluded_item_is_a_clean_error():
    docs = [
        _doc(
            "A",
            [
                _tok("KU-RO", TokenKind.WORD, ("KU", "RO")),
                _tok(DIVIDER, TokenKind.SEPARATOR, (DIVIDER,)),
            ],
        )
    ]
    with pytest.raises(ValueError, match="does not occur"):
        stats.dispersion(docs, DIVIDER, kind="signs")


def test_empty_and_whitespace_token_text_is_survivable():
    doc = _doc(
        "W",
        [
            _tok("", TokenKind.UNKNOWN, ()),
            _tok("   ", TokenKind.UNKNOWN, ()),
            _tok("A", TokenKind.WORD, ("A",)),
        ],
    )
    assert stats._items_of(doc, "signs") == ["   ", "A"]


def test_unknown_kind_still_rejected():
    with pytest.raises(ValueError, match="kind must be 'words' or 'signs'"):
        stats._items_of(_mixed_document(), "letters")


def test_a_long_run_of_placeholders_costs_nothing():
    # Pathological size: a document that is one long lacuna contributes no signs
    # and no item types at all.
    doc = _doc(
        "L",
        [_tok(ERASED, TokenKind.UNKNOWN, (ERASED,), ReadingStatus.LOST)] * 20_000,
    )
    assert stats._items_of(doc, "signs") == []


# ── the bundled corpora ─────────────────────────────────────────────────────


def test_bundled_lineara_sign_totals():
    la = aegean.load("lineara")
    items = [s for d in la.documents for s in stats._items_of(d, "signs")]
    # 9,063 raw items before the rule; the 2,697 excluded are 1,621 numerals,
    # 524 dividers/rulings and 552 erased-sign placeholders.
    assert len(items) == 6366
    assert len(set(items)) == 350
    assert ERASED not in items
    assert DIVIDER not in items
    assert "" not in items


def test_bundled_lineara_top_signs_are_signs():
    la = aegean.load("lineara")
    counts: dict[str, int] = {}
    for d in la.documents:
        for s in stats._items_of(d, "signs"):
            counts[s] = counts.get(s, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    assert top == [("KU", 307), ("KA", 284), ("*301", 274)]


def test_bundled_lineara_dispersion_ranking_is_signs_only():
    la = aegean.load("lineara")
    rows = stats.dispersions(la, kind="signs", top=5)
    assert [r.item for r in rows] == ["TA", "I", "A", "KU", "NA"]
    # Documents that held only numerals, dividers or lacunae are no longer parts
    # of the sign corpus in Gries' sense.
    assert rows[0].parts == 1659
    assert rows[0].frequency == 165
    assert rows[0].dp_norm == pytest.approx(0.667060, abs=1e-6)
    everything = stats.dispersions(la, kind="signs", min_frequency=1)
    ranked = {r.item for r in everything}
    assert DIVIDER not in ranked and ERASED not in ranked and "1" not in ranked


def test_bundled_lineara_words_ranking_is_unchanged():
    # The words stream must not move: this pins the published ranking.
    la = aegean.load("lineara")
    rows = stats.dispersions(la, kind="words", top=5)
    assert [r.item for r in rows] == ["KU-RO", "KI-RO", "SA-RA₂", "KU-PA₃-NU", "A-DU"]
    assert rows[0].parts == 559
    assert rows[0].frequency == 37 and rows[0].range == 34
    assert sum(len(stats._items_of(d, "words")) for d in la.documents) == 1381


def test_bundled_cypriot_illegible_marks_are_gone():
    cy = aegean.load("cypriot")
    items = [s for d in cy.documents for s in stats._items_of(d, "signs")]
    assert len(items) == 1781
    # The Leiden illegible-sign apparatus of IG XV 1: dots, queries, and the
    # empty labels their hyphen-joined runs used to produce.
    for mark in ("", "..", ".", "?", "‒?‒"):
        assert mark not in items


def test_bundled_cyprominoan_and_greek_are_untouched():
    # No dividers, numerals, punctuation or lacunae in these, so the rule is a
    # no-op and their sign statistics must not move.
    for corpus_id, expected in (("cyprominoan", 11), ("greek", 27)):
        c = aegean.load(corpus_id)
        assert sum(len(stats._items_of(d, "signs")) for d in c.documents) == expected


def test_every_bundled_corpus_sign_stream_is_free_of_non_signs():
    # The property, stated once over everything that loads offline.
    for corpus_id in ("lineara", "linearb", "cypriot", "cyprominoan", "greek", "nt"):
        c = aegean.load(corpus_id)
        for d in c.documents:
            for tok in d.tokens:
                labels = stats._items_of(_doc("probe", [tok]), "signs")
                if tok.kind in (TokenKind.SEPARATOR, TokenKind.NUMERAL, TokenKind.PUNCT):
                    assert labels == [], f"{corpus_id}: {tok.kind} contributed {labels}"
                if tok.status is ReadingStatus.LOST:
                    assert labels == [], f"{corpus_id}: lacuna contributed {labels}"
            assert "" not in stats._items_of(d, "signs")


# ── the memoized entry points ───────────────────────────────────────────────


def _mixed_corpus():
    docs = [
        _doc(
            f"D{i}",
            [
                _tok("KU-RO", TokenKind.WORD, ("KU", "RO")),
                _tok(DIVIDER, TokenKind.SEPARATOR, (DIVIDER,)),
                _tok("1", TokenKind.NUMERAL, ("1",)),
            ],
        )
        for i in range(3)
    ]
    return aegean.core.Corpus(script_id="lineara", documents=docs)


def test_cached_results_match_the_direct_computation(tmp_path):
    from aegean import cache

    corpus = _mixed_corpus()
    direct = stats.dispersions.__wrapped__(corpus, kind="signs", min_frequency=1)
    cache.enable(tmp_path / "analysis.sqlite")
    try:
        cold = stats.dispersions(corpus, kind="signs", min_frequency=1)
        warm = stats.dispersions(corpus, kind="signs", min_frequency=1)
    finally:
        cache.disable()
    assert [r.item for r in direct] == ["KU", "RO"]
    assert [(r.item, r.frequency) for r in cold] == [(r.item, r.frequency) for r in direct]
    assert [(r.item, r.frequency) for r in warm] == [(r.item, r.frequency) for r in direct]


@pytest.mark.parametrize("fn", [stats.dispersions, stats.keyness])
def test_a_result_persisted_under_the_previous_rule_is_not_served(tmp_path, fn):
    # dispersions/keyness persist to a store that outlives an upgrade. Their
    # memoize version is part of the key, so a table computed when dividers and
    # numerals were signs can never come back as a hit.
    from aegean import cache
    from aegean.cache import _make_key

    corpus = _mixed_corpus()
    args = (corpus, corpus) if fn is stats.keyness else (corpus,)
    kwargs = {"kind": "signs", "min_frequency": 1}
    if fn is stats.keyness:
        kwargs = {"kind": "signs", "min_target": 1}
    stale_key = _make_key(fn.__wrapped__, "1", args, kwargs)
    assert stale_key is not None, "the corpus must be fingerprintable for this to mean anything"

    store = cache.enable(tmp_path / "analysis.sqlite")
    try:
        store.set(stale_key, ["POISONED"])
        rows = fn(*args, **kwargs)
    finally:
        cache.disable()
    assert rows != ["POISONED"]
    assert all(not isinstance(r, str) for r in rows)


def test_keyness_totals_count_signs_only():
    target = [
        _doc(
            "T",
            [_tok("KU-RO", TokenKind.WORD, ("KU", "RO"))] * 5
            + [_tok("1", TokenKind.NUMERAL, ("1",))] * 50,
        )
    ]
    reference = [
        _doc(
            "R",
            [_tok("PA-RO", TokenKind.WORD, ("PA", "RO"))] * 5
            + [_tok(DIVIDER, TokenKind.SEPARATOR, (DIVIDER,))] * 50,
        )
    ]
    rows = stats.keyness(target, reference, kind="signs", min_target=1)
    # The 50 numerals and 50 dividers contribute nothing to either total, so each
    # corpus totals 10 signs rather than 60.
    assert {r.target_total for r in rows} == {10}
    assert {r.reference_total for r in rows} == {10}
    assert {r.item for r in rows} == {"KU", "RO", "PA"}
