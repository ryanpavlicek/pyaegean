"""Regressions for search, lenient repair, and model-output validity.

* ``db.search`` folded case with ``str.casefold``, which decomposes the iota subscript,
  so a dative singular matched a nominative plural and the answer depended on whether
  the database happened to carry an FTS index.
* ``normalize(lenient=True)`` read an editorial parenthesis as a Beta-Code breathing and
  deleted it, mangling the Leiden abbreviation convention that the shipped epigraphic
  corpora are full of.
* the neural parser could label a token ``root`` while its HEAD pointed at another word,
  producing a tree that is invalid UD and a self-contradictory analysis.
* the PapyGreek drift report used the strict long-input policy and so crashed on a
  181-token sentence inside the very fold it documents itself as decomposing.
* an evaluation receipt hashed whether datasets were cached on THIS machine, so the same
  evaluation produced a different id elsewhere and ``verify`` rejected an honest receipt.
* the treebank lexicon answered one- and two-letter tokenization fragments with the whole
  word's lemma, asserted as attested.
"""

from __future__ import annotations

import unicodedata
import warnings
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True, scope="module")
def _restore_backends():
    """Leave the process as this module found it.

    Backend activation is global session state, so a module that turns one on and walks
    away changes what unrelated tests see -- which under ``pytest -n`` means a different
    worker, and a failure with no visible cause. Everything this file activates is turned
    off again here."""
    yield
    from aegean import greek

    for name in (
        "disable_neural_pipeline",
        "disable_treebank",
        "disable_lsj",
        "disable_lexicon",
        "disable_paradigms",
        "disable_tagger",
        "disable_parser",
        "disable_lemmatizer",
        "disable_neural_lemmatizer",
        "disable_calibration",
    ):
        try:
            getattr(greek, name)()
        except Exception:  # pragma: no cover - a backend that was never active
            pass



# --- search folds case without folding a diacritic --------------------------- #


def test_fold_keeps_the_iota_subscript() -> None:
    from aegean.db import _fold

    assert _fold("ἐκκλησίᾳ") != _fold("ἐκκλησίαι")
    assert _fold("καρδίᾳ") != _fold("καρδίαις")
    # what it must still fold: case, and the final sigma
    assert _fold("ΛΌΓΟΣ") == _fold("λόγος")
    assert _fold("λόγος") == _fold("λόγοσ")
    assert _fold("ᾼΔΗΣ") == _fold("ᾳδης")


@pytest.fixture(scope="module")
def search_databases(tmp_path_factory):
    import aegean.db as db
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, Token, TokenKind

    directory = tmp_path_factory.mktemp("dbfold")
    forms = ["ἐκκλησίᾳ", "ἐκκλησίαι", "καρδίᾳ", "καρδίαις", "λόγος", "ΛΌΓΟΣ"]
    corpus = Corpus(
        [Document(
            id="search-fixture", script_id="greek",
            tokens=[Token(form, TokenKind.WORD, position=i) for i, form in enumerate(forms)],
            lines=[list(range(len(forms)))],
        )],
        script_id="greek",
    )
    with_fts = directory / "fts.db"
    without_fts = directory / "nofts.db"
    db.to_sqlite(corpus, with_fts)
    db.to_sqlite(corpus, without_fts, fts=False)
    return with_fts, without_fts


@pytest.mark.parametrize("query", ["ἐκκλησίᾳ", "καρδίᾳ", "λόγος"])
def test_the_two_build_modes_return_the_same_hits(search_databases, query: str) -> None:
    import aegean.db as db

    with_fts, without_fts = search_databases
    assert sorted(db.search(with_fts, query, limit=0)) == sorted(
        db.search(without_fts, query, limit=0)
    )


def test_token_search_returns_only_the_queried_form(search_databases) -> None:
    import aegean.db as db

    with_fts, _ = search_databases
    texts = {text for _doc, _pos, text in db.search(with_fts, "ἐκκλησίᾳ", limit=0)}
    assert texts == {"ἐκκλησίᾳ"}


def test_substring_hits_actually_contain_the_query(search_databases) -> None:
    import aegean.db as db
    from aegean.db import _fold

    with_fts, _ = search_databases
    hits = db.search(with_fts, "καρδίᾳ", mode="substring", limit=0)
    assert hits
    for _doc, _pos, text in hits:
        assert _fold("καρδίᾳ") in _fold(text), text


def test_case_folding_still_works(search_databases) -> None:
    import aegean.db as db

    with_fts, _ = search_databases
    lower = db.search(with_fts, "λόγος", limit=0)
    upper = db.search(with_fts, "ΛΌΓΟΣ", limit=0)
    assert lower and sorted(lower) == sorted(upper)


# --- lenient repair leaves editorial markup alone ---------------------------- #

EDITORIAL = [
    "Αὐρ(ήλιος)",
    "τοῦ Θεοῦ).",
    "ζήσασα(ν)",
    "μετ(ὰ)",
    "λί(τρα)",
    "(ε)ἰς",
    "Ἰη(σοῦς)",
    "Μ(ί)ν(ω)α",
    "λόγος(",
]


@pytest.mark.parametrize("text", EDITORIAL)
def test_lenient_normalize_preserves_editorial_markup(text: str) -> None:
    from aegean import greek

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert greek.normalize(text, lenient=True) == unicodedata.normalize("NFC", text)


@pytest.mark.parametrize(
    "text,expected",
    [("μη=νιν", "μῆνιν"), ("τω|", "τῳ"), ("α)νηρ", "ἀνηρ"), ("ο(δος", "ὁδος"), ("αι)ει", "αἰει")],
)
def test_genuine_betacode_remnants_still_repair(text: str, expected: str) -> None:
    from aegean import greek

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert greek.normalize(text, lenient=True) == expected


def test_no_cached_inscription_loses_a_parenthesis(monkeypatch) -> None:
    import aegean
    from aegean import data, greek

    cached = [
        name for name in ("edh", "iip")
        if data.is_downloaded(data._REMOTE[f"{name}-corpus"], data.cache_dir())
    ]
    if not cached:
        pytest.skip("inscription corpora are not cached")

    def no_download(*args, **kwargs):
        pytest.fail("cached inscription check attempted a download")

    monkeypatch.setattr(data, "_download", no_download)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for corpus_id in cached:
            corpus = aegean.load(corpus_id)
            seen: set[str] = set()
            for document in list(corpus.documents)[:400]:
                for token in document.tokens:
                    if not token.text or token.text in seen or "(" not in token.text:
                        continue
                    seen.add(token.text)
                    repaired = greek.normalize(token.text, lenient=True)
                    assert repaired.count("(") == token.text.count("("), token.text


# --- the parser emits a valid UD tree ---------------------------------------- #


def test_only_the_head_zero_token_is_labelled_root(cached_neural_model) -> None:
    from aegean import greek

    records = greek.pipeline("πλῆθός σο̣ι τῶν ἱππαρίων καὶ", parse=True)
    roots = [r.index for r in records if r.relation == "root"]
    zero_heads = [r.index for r in records if r.head == 0]
    assert roots == zero_heads
    assert len(roots) == 1


@pytest.mark.parametrize("root_index", [0, 1, 2])
def test_decoder_remaps_root_labels_on_non_root_arcs(root_index: int) -> None:
    """Synthetic logits test tree structure, not linguistic annotations."""
    np = pytest.importorskip("numpy")
    from aegean.greek import joint

    model = object.__new__(joint._JointModel)
    model._np = np
    model.inv = {"upos": {0: "X"}, "deprel": {0: "root", 1: "dep", 2: "obj"}}
    for i in range(9):
        model.inv[f"x{i}"] = {0: "-"}
    model.trees = [["keep"]]
    model.lookup_form = model.lookup_form_upos = model.lookup_lower = {}
    n = 3
    out = {"upos": np.zeros((1, n, 1)), "lemma": np.zeros((1, n, 1))}
    for i in range(9):
        out[f"x{i}"] = np.zeros((1, n, 1))
    out["arc"] = np.full((1, n, n + 1), -20.0)
    out["rel"] = np.zeros((1, 3, n, n + 1))
    expected_heads = tuple(0 if i == root_index else root_index + 1 for i in range(n))
    for i, head in enumerate(expected_heads):
        out["arc"][0, i, head] = 20.0
        out["rel"][0, :, i, head] = [30.0, 10.0, 20.0]
    out["_word_pos"] = list(range(n))
    out["_kept"] = list(range(n))

    analysis = model._decode(["α", "β", "γ"], out)
    assert analysis.head == expected_heads
    assert analysis.deprel == tuple("root" if i == root_index else "obj" for i in range(n))
    assert analysis.complete and analysis.analyzed == (True, True, True)


def test_the_helper_prefers_the_best_non_root_label() -> None:
    np = pytest.importorskip("numpy")

    from aegean.greek.joint import _best_non_root_relation

    labels = {0: "nsubj", 1: "root", 2: "obj"}
    assert _best_non_root_relation(np.array([0.1, 0.9, 0.5]), labels) == 2
    assert _best_non_root_relation(np.array([0.9, 0.1, 0.5]), labels) == 0
    # a label set with nothing else keeps the argmax rather than failing
    assert _best_non_root_relation(np.array([1.0]), {0: "root"}) == 0


# --- the drift report survives its own fold ---------------------------------- #


@pytest.mark.parametrize("batch_size", [None, 1, 2])
def test_convention_report_uses_the_windowed_policy(tmp_path, monkeypatch, batch_size) -> None:
    """Mechanical rows and predictions verify dispatch and accounting only."""
    from aegean import greek
    from aegean.greek import joint

    lengths = (181, 1)
    path = tmp_path / "one_long.conllu"
    path.write_text("".join(
        f"# sent_id = mechanical-{s}\n" + "".join(
            f"{i}\tα\t_\tX\t---------\t_\t{0 if i == 1 else 1}"
            f"\t{'root' if i == 1 else 'dep'}\t_\t_\n"
            for i in range(1, length + 1)
        ) + "\n"
        for s, length in enumerate(lengths)
    ), encoding="utf-8")
    seen = []

    class PolicyCheckingModel:
        def analyze(self, forms, *, long_input):
            assert long_input == "windowed"
            seen.append(tuple(forms))
            return SimpleNamespace(upos=("X",) * len(forms), xpos=("---------",) * len(forms))

        def analyze_batch(self, sentences, *, long_input):
            assert batch_size is not None and len(sentences) <= batch_size
            return [self.analyze(forms, long_input=long_input) for forms in sentences]

    monkeypatch.setattr(joint, "active", lambda: PolicyCheckingModel())
    progress = []
    report = greek.papygreek_convention_report(
        source=path, batch_size=batch_size, progress=lambda done, total: progress.append((done, total)),
    )
    assert [len(forms) for forms in seen] == list(lengths)
    assert report.n_words == report.upos_correct == report.xpos_correct == sum(lengths)
    assert report.upos_other_errors == report.upos_coordinator_errors == 0
    assert progress == [(1, 2), (2, 2)]


# --- a receipt identifies the evaluation, not the machine -------------------- #


def test_receipt_id_ignores_local_cache_state(monkeypatch) -> None:
    from aegean import data
    from aegean.greek.eval_receipt import eval_receipt

    scores = {"upos": 0.9702, "lemma": 0.9427, "las": 0.8565}
    real = data.versions()

    def with_cache_flags(cached: bool):
        manifest = {
            **real,
            "fetched": {
                name: {**entry, "cached": cached, "history": [] if cached else [{"sha256": "x"}]}
                for name, entry in real["fetched"].items()
            },
        }
        return lambda: manifest

    monkeypatch.setattr(data, "versions", with_cache_flags(True))
    populated = eval_receipt(scores, treebank="perseus", split="test", protocol="p")
    monkeypatch.setattr(data, "versions", with_cache_flags(False))
    fresh = eval_receipt(scores, treebank="perseus", split="test", protocol="p")
    assert populated.id == fresh.id
    assert populated.verify(fresh)


def test_receipt_id_still_reacts_to_a_pin_change(monkeypatch) -> None:
    from aegean import data
    from aegean.greek.eval_receipt import eval_receipt

    scores = {"upos": 0.9702}
    real = data.versions()
    baseline = eval_receipt(scores, treebank="perseus", split="test", protocol="p")
    name = next(iter(real["fetched"]))
    tampered = {
        **real,
        "fetched": {**real["fetched"], name: {**real["fetched"][name], "sha256": "0" * 64}},
    }
    monkeypatch.setattr(data, "versions", lambda: tampered)
    assert eval_receipt(scores, treebank="perseus", split="test", protocol="p").id != baseline.id


# --- a tokenization fragment is not lexical evidence ------------------------- #

FRAGMENTS = ["α", "ε", "η", "ο", "ς", "ας", "αν"]
REAL_SHORT_WORDS = {"ᾖ": "εἰμί", "ὁ": "ὁ", "ἡ": "ὁ", "ὦ": "ὦ", "τῷ": "ὁ", "ἦν": "εἰμί", "ἐν": "ἐν"}


@pytest.fixture
def treebank_lexicon():
    """The treebank tier alone: an earlier test may have left the neural pipeline
    active, which would answer these lookups from the model instead."""
    from aegean import greek
    from aegean import data
    from aegean.greek import joint, runtime, treebank

    if not (data.cache_dir() / treebank._LEXICON_NAME).exists():
        pytest.skip("treebank lexicon not cached")
    previous_pipeline = runtime.default_pipeline()
    previous_joint = joint._ACTIVE
    previous_treebank = treebank._ACTIVE
    try:
        greek.disable_neural_pipeline()
        yield greek.use_treebank(build=False)
    finally:
        runtime._set_default_pipeline(previous_pipeline)
        joint._ACTIVE = previous_joint
        treebank._ACTIVE = previous_treebank


@pytest.mark.parametrize("fragment", FRAGMENTS)
def test_fragments_are_not_attested(treebank_lexicon, fragment: str) -> None:
    from aegean import greek
    from aegean.greek.lemmatize import needs_review

    assert treebank_lexicon.analyze(fragment) == ()
    _lemma, source = greek.lemmatize_sourced(fragment)
    assert needs_review(source), f"{fragment} still claims a grounded lemma"


@pytest.mark.parametrize("form,lemma", sorted(REAL_SHORT_WORDS.items()))
def test_real_short_words_still_resolve(treebank_lexicon, form: str, lemma: str) -> None:
    from aegean import greek

    value, source = greek.lemmatize_sourced(form)
    assert (value, source.name) == (lemma, "ATTESTED")


def test_the_fragment_rule_needs_both_conditions() -> None:
    """Two conditions together: no diacritic AND an implausibly longer lemma.

    Each alone is wrong, and both mistakes were made before this settled. Keying on
    "no Greek word is a lone consonant" swept up 2,655 elided Perseus test tokens
    (``δ̓`` = ``δέ``) the treebank lemmatizes correctly and moved three published
    baseline numbers. Keying on "carries no diacritic" alone swept up the unaccented
    enclitics and closed-class forms (``τε``, ``γε``, ``με``, ``σε``, ``τι``) and every
    punctuation token."""
    from aegean.greek.treebank import _is_fragment_analysis as artifact

    # the artifacts: a bare letter whose "lemma" is a whole different word
    assert artifact("α", "Λητογενής")
    assert artifact("ε", "προσβλώσκω")
    assert artifact("ας", "ὑγίεια")
    assert artifact("κα", "ἀλκή")
    # not artifacts: unaccented enclitics and closed-class forms
    assert not artifact("τε", "τε")
    assert not artifact("με", "ἐγώ")
    assert not artifact("τι", "τις")
    # not artifacts: elided forms, which carry the mark of elision
    assert not artifact("δ̓", "δέ")
    assert not artifact("κ̓", "ἄν")
    # not artifacts: punctuation, whose lemma is itself
    assert not artifact(",", ",")
    assert not artifact("·", "·")
    # not artifacts: anything longer than two letters is out of scope entirely
    assert not artifact("λόγος", "λόγος")


ENCLITICS = {"τε": "τε", "γε": "γε", "με": "ἐγώ", "σε": "σύ", "τι": "τις"}


@pytest.mark.parametrize("form,lemma", sorted(ENCLITICS.items()))
def test_unaccented_enclitics_still_resolve(treebank_lexicon, form: str, lemma: str) -> None:
    from aegean import greek

    value, source = greek.lemmatize_sourced(form)
    assert (value, source.name) == (lemma, "ATTESTED")


@pytest.mark.parametrize("mark", [",", ".", "·"])
def test_punctuation_still_resolves(treebank_lexicon, mark: str) -> None:
    assert treebank_lexicon.analyze(mark) != ()
