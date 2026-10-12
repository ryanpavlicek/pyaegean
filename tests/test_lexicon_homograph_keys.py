"""Editorial dictionary keys preserve accent distinctions and homonym ambiguity."""

from __future__ import annotations

import gzip
import importlib
import json
import unicodedata
from collections.abc import Callable
from pathlib import Path

import pytest

from aegean.greek.lexicon import LSJEntry, LSJLexicon
from aegean.greek.lexicons import LexiconInfo
from aegean.greek.lexindex import IndexLexicon, load_index, write_index

Lexicon = IndexLexicon | LSJLexicon
Records = dict[str, tuple[str, str]]
Factory = Callable[[Records], Lexicon]
_INFO = LexiconInfo("fixture", "fixture", "classical", "test", "test", False)


@pytest.fixture(autouse=True)
def _identity_lemma(monkeypatch: pytest.MonkeyPatch) -> None:
    # These checks exercise dictionary decisions independently of any active backend.
    module = importlib.import_module("aegean.greek.lemmatize")
    monkeypatch.setattr(module, "lemmatize", lambda word: word)


@pytest.fixture(params=("index", "lsj"))
def make_lexicon(request: pytest.FixtureRequest) -> Factory:
    def make(records: Records) -> Lexicon:
        if request.param == "index":
            return IndexLexicon(
                _INFO, {key: {"hw": hw, "def": body} for key, (hw, body) in records.items()}
            )
        return LSJLexicon({
            key: {
                "hw": hw, "key": key, "lead": hw, "short": body,
                "senses": [{"m": "A", "l": 1, "t": body}],
            }
            for key, (hw, body) in records.items()
        })

    return make


_PAIRS: Records = {
    "ἅμα1": ("ἅμα", "at the same time"),
    "ἁμᾶ2": ("ἁμᾶ", "another reading"),
    "εἰμί1": ("εἰμί", "to be"),
    "εἶμι2": ("εἶμι", "to go"),
    "μέλλω1": ("μέλλω", "to be about to"),
    "μελλώ2": ("μελλώ", "delay"),
}


@pytest.mark.parametrize("key", tuple(_PAIRS))
def test_numbered_accented_headwords_select_the_correct_record(
    make_lexicon: Factory, key: str,
) -> None:
    lex = make_lexicon(_PAIRS)
    hw, body = _PAIRS[key]
    for query in (hw, unicodedata.normalize("NFD", hw), f"  {hw.upper()}  ", key):
        entry = lex.lookup(query)
        assert entry is not None
        assert entry.headword == hw
        assert lex.gloss(query) == f"{hw}: {body}"
        if isinstance(entry, LSJEntry):
            assert entry.raw_key == key
            assert entry.senses[0].text == body
        else:
            assert entry.body == body
            assert entry.lexicon == "fixture"
    assert len(lex) == len(_PAIRS)


@pytest.mark.parametrize("query", ("αμα", "ειμι", "μελλω"))
def test_accentless_numbered_pairs_remain_ambiguous(
    make_lexicon: Factory, monkeypatch: pytest.MonkeyPatch, query: str,
) -> None:
    lex = make_lexicon(_PAIRS)

    def choose_a_homonym(word: str) -> str:
        pytest.fail(f"ambiguous dictionary query was sent to lemmatization: {word}")

    monkeypatch.setattr(
        importlib.import_module("aegean.greek.lemmatize"), "lemmatize", choose_a_homonym
    )
    assert lex.lookup(query) is None
    assert lex.gloss(query) is None


@pytest.mark.parametrize("key", ("δέω1", "δέω2", "†ἄπειμι1", "†ἄπειμι2"))
def test_same_spelling_homonyms_require_explicit_ids(make_lexicon: Factory, key: str) -> None:
    records: Records = {
        "δέω1": ("δέω", "to bind"), "δέω2": ("δέω", "to lack"),
        "†ἄπειμι1": ("†ἄπειμι1", "to be away"), "†ἄπειμι2": ("†ἄπειμι2", "to go away"),
    }
    for records_in_order in (records, dict(reversed(tuple(records.items())))):
        lex = make_lexicon(records_in_order)
        for query in ("δέω", "δεω", "ἄπειμι", "απειμι", "†ἄπειμι"):
            assert lex.lookup(query) is None
            assert lex.gloss(query) is None
        hw, body = records[key]
        assert lex.gloss(key) == f"{hw}: {body}"


def test_decorated_ambiguous_query_cannot_be_resolved_by_lemmatizer(
    make_lexicon: Factory, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def choose_a_homonym(word: str) -> str:
        calls.append(word)
        return "†ἄπειμι1"

    monkeypatch.setattr(
        importlib.import_module("aegean.greek.lemmatize"), "lemmatize", choose_a_homonym
    )
    lex = make_lexicon({
        "†ἄπειμι1": ("†ἄπειμι1", "to be away"),
        "†ἄπειμι2": ("†ἄπειμι2", "to go away"),
    })
    for query in ("ἄπειμι", "απειμι", "†ἄπειμι", "†απειμι", "†ἄπειμι3"):
        assert lex.lookup(query) is None
        assert lex.gloss(query) is None
    assert lex.gloss("†ἄπειμι1") == "†ἄπειμι1: to be away"
    assert lex.gloss("†ἄπειμι2") == "†ἄπειμι2: to go away"
    assert calls == []


def test_clean_exact_key_wins_but_alias_collision_stays_ambiguous(make_lexicon: Factory) -> None:
    records: Records = {
        "δέω": ("δέω", "clean entry"), "δέω_1": ("δέω_1", "numbered entry"),
    }
    for records_in_order in (records, dict(reversed(tuple(records.items())))):
        lex = make_lexicon(records_in_order)
        assert lex.gloss("δέω") == "δέω: clean entry"
        assert lex.gloss("δέω_1") == "δέω_1: numbered entry"
        assert lex.lookup("δεω") is None
        assert len(lex) == 2


def test_grave_levelled_collision_does_not_select_first_record(make_lexicon: Factory) -> None:
    records: Records = {"καλός1": ("καλός", "first"), "καλὸς2": ("καλὸς", "second")}
    for records_in_order in (records, dict(reversed(tuple(records.items())))):
        lex = make_lexicon(records_in_order)
        assert lex.lookup("καλός") is None
        assert lex.lookup("καλὸς") is None
        assert lex.lookup("καλος") is None
        assert lex.gloss("καλός1") == "καλός: first"
        assert lex.gloss("καλὸς2") == "καλὸς: second"


@pytest.mark.parametrize(
    ("key", "hw", "query", "body"),
    (
        ("ἀριστότοκος2", "ἀριστότοκος2", "ἀριστότοκος", "born of the best parents"),
        ("λειστός2", "λειστός2", "λειστὸς", "of or for the people, public"),
        ("ἄν_1", "ἄν_1", "ἄν", "a conditional particle"),
        ("†εἰμί", "†εἰμί", "εἰμὶ", "to be"),
        ("†εἶμι", "†εἶμι", "εἶμι", "to go"),
    ),
)
def test_editorial_aliases_keep_source_display_and_definition(
    make_lexicon: Factory, key: str, hw: str, query: str, body: str,
) -> None:
    lex = make_lexicon({key: (hw, body)})
    for word in (query, unicodedata.normalize("NFD", query), key):
        entry = lex.lookup(word)
        assert entry is not None and entry.headword == hw
        assert lex.gloss(word) == f"{hw}: {body}"


@pytest.mark.parametrize("key", ("ἄνθρωπος1", "†ἄνθρωπος"))
def test_enclitic_throwback_remains_compatible(make_lexicon: Factory, key: str) -> None:
    lex = make_lexicon({key: (key, "human being")})
    assert lex.gloss("ἄνθρωπός") == f"{key}: human being"
    if key.startswith("†"):
        assert lex.gloss("†ἄνθρωπός") == f"{key}: human being"


@pytest.mark.parametrize(
    ("key", "query"),
    (("εἷ2", "εἰ"), ("λᾶος1", "λαός"), ("κάλως1", "καλῶς"), ("ἀν1", "ἁν")),
)
def test_alias_does_not_erase_accents_or_breathings(
    make_lexicon: Factory, key: str, query: str,
) -> None:
    lex = make_lexicon({key: (key, "different word")})
    assert lex.lookup(query) is None
    assert lex.gloss(query) is None


@pytest.mark.parametrize("query", ("εἰμί2", "εἰμί_2", "εἰμί#1", "εἰμί†"))
def test_unknown_editorial_ids_are_not_rewritten(make_lexicon: Factory, query: str) -> None:
    lex = make_lexicon({"εἰμί1": ("εἰμί", "to be")})
    assert lex.lookup(query) is None


@pytest.mark.parametrize("key", ("*εἰμί", "εἰμί†", "εἰμί#1", "εἰμί-1", "†", "1"))
def test_unrecognized_punctuation_and_empty_alias_are_not_guessed(
    make_lexicon: Factory, key: str,
) -> None:
    lex = make_lexicon({key: (key, "source record")})
    assert lex.gloss(key) == f"{key}: source record"
    assert lex.lookup("εἰμί") is None
    assert lex.lookup("") is None


def test_nfd_index_key_supports_alias_and_numbered_query(make_lexicon: Factory) -> None:
    key = unicodedata.normalize("NFD", "λειστός2")
    lex = make_lexicon({key: ("λειστός2", "public")})
    for query in ("λειστός", "λειστὸς", "λειστός2", key):
        assert lex.gloss(query) == "λειστός2: public"


def test_genuine_inflected_miss_still_uses_lemma_alias(
    make_lexicon: Factory, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def lemma(word: str) -> str:
        calls.append(word)
        return "λόγος"

    monkeypatch.setattr(importlib.import_module("aegean.greek.lemmatize"), "lemmatize", lemma)
    lex = make_lexicon({"λόγος2": ("λόγος", "word")})
    assert lex.gloss("λόγου") == "λόγος: word"
    assert calls == ["λόγου"]


@pytest.mark.parametrize(("query", "lemma"), (("ᾧ", "ὅς"), ("ᾗ", "ὅς"), ("ἡ", "ὁ")))
def test_marked_inflections_keep_real_seed_fallback_despite_fold_collisions(
    make_lexicon: Factory, monkeypatch: pytest.MonkeyPatch, query: str, lemma: str,
) -> None:
    module = importlib.import_module("aegean.greek.lemmatize")
    calls: list[str] = []

    def seed(word: str) -> str:
        calls.append(word)
        return module.seed_lemma_verbose(word)[0]

    monkeypatch.setattr(module, "lemmatize", seed)
    # Abbott-Smith has these letter/interjection/conjunction collisions; LSJ's
    # numbered ὦ entries add the same collision after editorial aliases are built.
    lex = make_lexicon({
        "ω": ("Ω", "omega"), "ὦ": ("ὦ", "O"),
        "ὦ1": ("ὦ", "O!"), "ὦ2": ("ὦ τᾶν,", "see τᾶν"),
        "η": ("Η", "eta"), "ἤ": ("ἤ", "or"),
        "ὅς": ("ὅς", "who"), "ὁ": ("ὁ", "the"),
    })
    for word in (query, unicodedata.normalize("NFD", query)):
        entry = lex.lookup(word)
        assert entry is not None and entry.headword == lemma
        assert lex.gloss(word) == ("ὅς: who" if lemma == "ὅς" else "ὁ: the")
    assert calls == [query, query, unicodedata.normalize("NFD", query),
                     unicodedata.normalize("NFD", query)]


@pytest.mark.parametrize(
    ("dictionary", "query", "lemma"),
    (("abbott-smith", "ᾧ", "ὅς"), ("abbott-smith", "ᾗ", "ὅς"),
     ("abbott-smith", "ἡ", "ὁ"), ("lsj-perseus", "ᾧ", "ὅς")),
)
def test_cached_marked_inflections_keep_the_canonical_entry(
    monkeypatch: pytest.MonkeyPatch, dictionary: str, query: str, lemma: str,
) -> None:
    from aegean.data import cache_dir

    path = cache_dir() / f"{dictionary}-index.json.gz"
    if not path.exists():
        pytest.skip(f"{dictionary} index not cached")
    module = importlib.import_module("aegean.greek.lemmatize")
    monkeypatch.setattr(module, "lemmatize", lambda word: module.seed_lemma_verbose(word)[0])
    lex: Lexicon = (
        LSJLexicon.load(path) if dictionary == "lsj-perseus"
        else IndexLexicon(_INFO, load_index(path))
    )
    entry = lex.lookup(query)
    assert entry is not None and entry.headword == lemma
    assert entry == lex.lookup(lemma)
    assert lex.gloss(query) == lex.gloss(lemma)


@pytest.mark.parametrize("kind", ("index", "lsj"))
def test_loaded_real_shaped_numbered_records_lookup_and_gloss(
    tmp_path: Path, kind: str,
) -> None:
    path = tmp_path / "index.json.gz"
    if kind == "index":
        write_index(path, {"λειστός2": {"hw": "λειστός2", "def": "public"}})
        lex: Lexicon = IndexLexicon(_INFO, load_index(path))
        query, hw, body = "λειστός", "λειστός2", "public"
    else:
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            json.dump({"ἅμα1": {
                "hw": "ἅμα", "key": "a(/ma1", "lead": "Adv.", "short": "at once",
                "senses": [{"m": "A", "l": 1, "t": "at once"}],
            }}, stream, ensure_ascii=False)
        lex = LSJLexicon.load(path)
        query, hw, body = "ἅμα", "ἅμα", "at once"
    entry = lex.lookup(query)
    assert entry is not None and entry.headword == hw
    assert lex.gloss(query) == f"{hw}: {body}"
    if isinstance(entry, LSJEntry):
        assert entry.raw_key == "a(/ma1"
        assert entry.lead == "Adv."
        assert entry.senses[0].text == "at once"
