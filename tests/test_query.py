"""Parity with the workbench queryEngine.ts behavior, adapted to the
script-agnostic Document/Corpus model. Mirrors queryEngine.test.ts."""

from __future__ import annotations

from aegean.analysis import (
    FilterRow,
    build_cooccurrence_map,
    build_word_index,
    default_value,
    eval_query,
    inscription_matches,
    run_query,
    summarize_filters,
    word_matches,
)
from aegean.core.model import Document, DocumentMeta
from aegean.scripts.lineara.loader import classify


def doc(id_: str, site: str, words: list[str], *, scribe: str = "S1",
        period: str = "LMIB", support: str = "tablet",
        images: tuple[str, ...] = ()) -> Document:
    tokens = [classify(w, 0, i) for i, w in enumerate(words)]
    return Document(
        id=id_,
        script_id="lineara",
        tokens=tokens,
        lines=[list(range(len(tokens)))] if tokens else [],
        meta=DocumentMeta(site=site, scribe=scribe, period=period, support=support,
                          images=images),
    )


def row(field: str, value: object, **extra: object) -> FilterRow:
    return FilterRow(field=field, value=value, **extra)  # type: ignore[arg-type]


# ── defaultValue ─────────────────────────────────────────────────────────────
def test_default_value_by_kind():
    assert default_value("word-min-syllables") == 2   # number
    assert default_value("has-image") is True          # boolean
    assert default_value("id-contains") == ""          # text


# ── inscription predicates + AND/OR/NOT ──────────────────────────────────────
def test_inscription_single_and_empty():
    ht1 = doc("HT1", "HT", ["KU-RO"], images=("img.jpg",))
    assert inscription_matches(ht1, [], set()) is True
    assert inscription_matches(ht1, [row("site-is", "HT")], set()) is True
    assert inscription_matches(ht1, [row("site-is", "ZA")], set()) is False


def test_inscription_not_flips():
    ht1 = doc("HT1", "HT", ["KU-RO"])
    assert inscription_matches(ht1, [row("site-is", "ZA", negate=True)], set()) is True


def test_inscription_and_or():
    ht1 = doc("HT1", "HT", ["KU-RO"])
    and_ok = [row("site-is", "HT"), row("scribe-is", "S1", connector="and")]
    and_bad = [row("site-is", "HT"), row("scribe-is", "SX", connector="and")]
    or_ok = [row("site-is", "ZA"), row("scribe-is", "S1", connector="or")]
    assert inscription_matches(ht1, and_ok, set()) is True
    assert inscription_matches(ht1, and_bad, set()) is False
    assert inscription_matches(ht1, or_ok, set()) is True


def test_inscription_boolean_predicates():
    ht1 = doc("HT1", "HT", ["KU-RO"], images=("img.jpg",))
    no_img = doc("HT2", "HT", ["A-B"])
    assert inscription_matches(ht1, [row("has-image", True)], set()) is True
    assert inscription_matches(no_img, [row("has-image", True)], set()) is False
    assert inscription_matches(ht1, [row("has-annotation", True)], {"HT1"}) is True


def test_ins_contains_word():
    ht1 = doc("HT1", "HT", ["KU-RO"])
    assert inscription_matches(ht1, [row("ins-contains-word", "KU-RO")], set()) is True
    assert inscription_matches(ht1, [row("ins-contains-word", "PA-I-TO")], set()) is False


# ── word-scope predicates ────────────────────────────────────────────────────
COOC = {"KU-RO": {"PA-I-TO"}}


def test_word_prefix_suffix_syllables():
    assert word_matches("KU-RO", [row("word-prefix", "KU")], COOC) is True
    assert word_matches("PA-RO", [row("word-prefix", "KU")], COOC) is False
    assert word_matches("KU-RO", [row("word-suffix", "RO")], COOC) is True
    assert word_matches("KU-NE-RO", [row("word-min-syllables", 3)], COOC) is True
    assert word_matches("KU-RO", [row("word-min-syllables", 3)], COOC) is False
    assert word_matches("KU-RO", [row("word-max-syllables", 2)], COOC) is True


def test_word_contains_sign_pattern_cooccurs():
    assert word_matches("KU-NE-RO", [row("word-contains-sign", "NE")], COOC) is True
    assert word_matches("KU-NE-RO", [row("word-sign-pattern", "KU-*-RO")], COOC) is True
    assert word_matches("KU-RO", [row("word-cooccurs-with", "PA-I-TO")], COOC) is True
    assert word_matches("KU-RO", [row("word-cooccurs-with", "ZZ")], COOC) is False


# ── evalQuery ────────────────────────────────────────────────────────────────
def _eval_corpus():
    corpus = [
        doc("HT1", "HT", ["KU-RO", "PA-I-TO"]),
        doc("HT2", "HT", ["KU-NE-RO"]),
        doc("ZA1", "ZA", ["PA-I-TO"]),
    ]
    return corpus, build_word_index(corpus), build_cooccurrence_map(corpus)


def test_eval_inscription_scope():
    corpus, idx, cooc = _eval_corpus()
    res = eval_query([row("site-is", "HT")], "inscriptions", corpus, idx, set(), cooc)
    assert sorted(i.id for i in res.inscriptions) == ["HT1", "HT2"]


def test_eval_word_filter_intersects_inscriptions():
    corpus, idx, cooc = _eval_corpus()
    res = eval_query([row("word-suffix", "RO")], "inscriptions", corpus, idx, set(), cooc)
    assert sorted(i.id for i in res.inscriptions) == ["HT1", "HT2"]


def test_eval_word_output_sorted_desc():
    corpus, idx, cooc = _eval_corpus()
    res = eval_query([row("word-suffix", "O")], "words", corpus, idx, set(), cooc)
    assert res.words[0] == ("PA-I-TO", 2)


def test_word_output_count_is_document_frequency_not_token_count():
    """`output="words"` counts distinct inscriptions (document frequency), not
    tokens. Fixture: KU-RO is written twice in HT1 and once in HT2 — token
    frequency 3, but document frequency 2. The query count must be 2, and it
    must differ from the token frequency the corpus reports for the same word."""
    corpus = [
        doc("HT1", "HT", ["KU-RO", "PA-I-TO", "KU-RO"]),  # KU-RO twice in one doc
        doc("HT2", "HT", ["KU-RO"]),                        # and once in another
    ]
    idx = build_word_index(corpus)
    cooc = build_cooccurrence_map(corpus)

    res = eval_query([row("word-prefix", "KU")], "words", corpus, idx, set(), cooc)
    assert dict(res.words)["KU-RO"] == 2  # document frequency: HT1, HT2 — not 3

    # The token frequency (every occurrence) is 3, so the two semantics differ
    # here: this is what guards the docstring claim that they are distinct.
    token_freq = sum(1 for d in corpus for t in d.tokens if t.text == "KU-RO")
    assert token_freq == 3
    assert dict(res.words)["KU-RO"] != token_freq


def test_corpus_query_word_count_is_document_frequency():
    """The public `Corpus.query` path agrees: document frequency, not tokens.
    `Corpus.word_frequencies` reports the token frequency for the same word, so
    the two `(word, count)` APIs return different numbers on this fixture."""
    from aegean.core.corpus import Corpus

    c = Corpus(
        [
            doc("HT1", "HT", ["KU-RO", "KU-RO"]),  # written twice in one document
            doc("HT2", "HT", ["KU-RO"]),
            doc("ZA1", "ZA", ["KU-RO"]),
        ],
        script_id="lineara",
    )
    qcount = dict(c.query([row("word-prefix", "KU")], output="words").words)["KU-RO"]
    assert qcount == 3  # distinct documents: HT1, HT2, ZA1

    token_count = dict(c.word_frequencies())["KU-RO"]
    assert token_count == 4  # four written occurrences
    assert qcount != token_count


def test_run_query_over_corpus_object():
    corpus, _, _ = _eval_corpus()

    class _C:
        def __iter__(self):
            return iter(corpus)

    res = run_query(_C(), [row("site-is", "HT")], "inscriptions")
    assert sorted(i.id for i in res.inscriptions) == ["HT1", "HT2"]


# ── summarizeFilters ─────────────────────────────────────────────────────────
def test_summarize_filters():
    assert summarize_filters([row("site-is", "HT")]) == "Site is: HT"
    assert summarize_filters([row("has-image", True)]) == "Has facsimile image: yes"
    assert summarize_filters([row("site-is", "ZA", negate=True)]) == "NOT Site is: ZA"
    assert summarize_filters([]) == "(no filters)"
