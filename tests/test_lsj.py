"""LSJ glossing (opt-in Perseus Liddell-Scott-Jones backend).

Offline: a synthetic TEI fixture is parsed into an index and activated; the network
download path is not exercised in CI (same policy as the treebank/lineara-images).
Every test restores the default (LSJ-off) state afterward.
"""

from __future__ import annotations

import pathlib

import pytest

from aegean import greek
from aegean.greek import lexicon
from aegean.greek.lexicon import LSJLexicon, LexiconNotLoadedError, build_index

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "lsj"


@pytest.fixture(autouse=True)
def _restore_default() -> None:
    yield
    lexicon.disable_lsj()


def _activate(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    build_index(source_dir=FIXTURE_DIR, force=True)
    greek.use_lsj(build=False)


def test_build_parses_betacode_keys_and_senses(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    build_index(source_dir=FIXTURE_DIR, force=True)
    lex = LSJLexicon.load()
    assert len(lex) >= 2

    e = lex.lookup("λόγος")  # Beta Code key lo/gos -> λόγος
    assert e is not None
    assert e.headword == "λόγος"
    assert e.senses[0].marker == "A" and e.senses[0].level == 1
    assert any("reckoning" in s.text for s in e.senses)
    # Beta Code inside <foreign> is converted: le/gw -> λέγω
    assert "λέγω" in e.senses[0].text
    # <bibl> citation is compacted into the sense text, not dropped as raw tags
    assert "Hdt." in e.senses[0].text


def test_gloss_and_lookup_via_module(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    assert greek.lookup("λόγος").headword == "λόγος"
    g = greek.gloss("λόγος")
    assert g is not None and g.startswith("λόγος:")


def test_lookup_lemmatizes_on_miss(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    # Inflected forms aren't headwords; the seed lemmatizer resolves them, then the
    # lemma hits the LSJ index (λόγου -> λόγος, ἀνθρώπων -> ἄνθρωπος).
    assert greek.lookup("λόγου").headword == "λόγος"
    assert greek.lookup("ἀνθρώπων").headword == "ἄνθρωπος"


def test_accent_insensitive_fallback(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    assert greek.lookup("λογος") is not None  # unaccented -> stripped fallback


def test_unknown_word_returns_none(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _activate(tmp_path, monkeypatch)
    assert greek.gloss("ζzzz") is None


def test_gloss_requires_use_lsj() -> None:
    lexicon.disable_lsj()
    with pytest.raises(LexiconNotLoadedError):
        greek.gloss("λόγος")


# ── gated content-word glossing (grounding) ──────────────────────────────────
def test_content_glosses_gates_high_polysemy(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.ai.grounding import content_glosses

    _activate(tmp_path, monkeypatch)
    # ἄνθρωπος has 1 sense, λόγος has 2; a cap of 1 gates λόγος out (its first-sense
    # gloss would be unreliable), keeps the single-sense word, and skips the article.
    items = content_glosses("ὁ λόγος ἄνθρωπος", max_senses=1)
    refs = {g.ref for g in items}
    assert "ἄνθρωπος" in refs
    assert "λόγος" not in refs   # over the polysemy cap
    assert "ὁ" not in refs       # function word
    assert all(g.source == "lexicon:LSJ" and ":" in g.content for g in items)


def test_content_glosses_are_concise(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aegean.ai.grounding import content_glosses

    _activate(tmp_path, monkeypatch)
    by_ref = {g.ref: g.content for g in content_glosses("λόγος ἄνθρωπος", max_senses=6)}
    # citation ("Hdt. 1.1") and the trailing ";"-separated note are trimmed off.
    assert by_ref["λόγος"] == "λόγος: computation, reckoning"
    assert by_ref["ἄνθρωπος"] == "ἄνθρωπος: man, human being"


def test_content_glosses_dedupes_by_lemma(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.ai.grounding import content_glosses

    _activate(tmp_path, monkeypatch)
    assert len(content_glosses("λόγος λόγος", max_senses=6)) == 1


def test_content_glosses_skip_lemmas(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.ai.grounding import content_glosses

    _activate(tmp_path, monkeypatch)
    # a caller-supplied high-frequency set suppresses those lemmas (the frequency gate)
    refs = {g.ref for g in content_glosses("λόγος ἄνθρωπος", max_senses=6, skip_lemmas=frozenset({"λόγος"}))}
    assert "ἄνθρωπος" in refs and "λόγος" not in refs


def test_content_glosses_empty_without_lsj() -> None:
    from aegean.ai.grounding import content_glosses

    lexicon.disable_lsj()
    assert content_glosses("ὁ λόγος ἄνθρωπος") == []


def test_greek_grounding_includes_gated_glosses(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean import translate

    _activate(tmp_path, monkeypatch)
    g = translate.grounding_for("ὁ λόγος ἄνθρωπος", "greek", mode="lemma")
    sources = {item.source for item in g}
    assert "lemmatizer" in sources       # lemma grounding still present
    assert "lexicon:LSJ" in sources      # gated glosses now added too
    assert any("man, human being" in item.content for item in g)


def test_greek_grounding_glosses_toggle(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean import translate

    _activate(tmp_path, monkeypatch)
    # glosses=False on the gloss-bearing lemma mode drops the LSJ glosses, leaving
    # lemma-only grounding.
    off = translate.grounding_for("ὁ λόγος ἄνθρωπος", "greek", mode="lemma", glosses=False)
    assert any(i.source == "lemmatizer" for i in off)   # lemma grounding still present
    assert all(i.source != "lexicon:LSJ" for i in off)  # but no glosses


# ── dialect / register tags ──────────────────────────────────────────────────
def test_usage_dialect_and_register(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _activate(tmp_path, monkeypatch)
    u = greek.usage("κοῦρος")  # fixture: "Dor. and Ep. for …, poet. …, Com. Ar."
    assert set(u.dialects) == {"doric", "epic"}
    assert set(u.registers) == {"poetic", "comic"}
    assert bool(u) is True


def test_usage_empty_for_unmarked_entry(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _activate(tmp_path, monkeypatch)
    u = greek.usage("ἄνθρωπος")  # "man, human being" — no dialect/register markers
    assert u.dialects == () and u.registers == () and not u


def test_usage_requires_use_lsj() -> None:
    lexicon.disable_lsj()
    with pytest.raises(LexiconNotLoadedError):
        greek.usage("κοῦρος")


# ── deterministic sense selection (grounding) ────────────────────────────────
def test_select_sense_picks_non_dominant_on_context(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.ai.sense import select_sense

    _activate(tmp_path, monkeypatch)
    # λόγος has two senses: A "computation, reckoning" (cites λέγω) and the buried
    # II "the word …" (cites ἔπος). A context mentioning ἔπος should surface II over
    # the dominant sense A — exactly the buried-sense case content_glosses refuses.
    cands = select_sense("λόγος", "ἔπος ἄνθρωπος")
    assert cands  # ranked, best first
    assert cands[0].marker == "II"
    assert cands[0].dominant is False
    assert "επος" in cands[0].overlap


def test_select_sense_dominant_without_overlap(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.ai.sense import select_sense

    _activate(tmp_path, monkeypatch)
    # No overlapping Greek in the context: the order/length prior keeps the dominant
    # (sense A) reading on top, the same gloss content_glosses would pick.
    cands = select_sense("λόγος", "ἄνθρωπος")
    assert cands[0].marker == "A" and cands[0].dominant is True
    cands_legw = select_sense("λόγος", "λέγω")  # sense A cites λέγω -> A wins on overlap
    assert cands_legw[0].marker == "A" and "λεγω" in cands_legw[0].overlap


def test_select_sense_respects_max_candidates(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.ai.sense import select_sense

    _activate(tmp_path, monkeypatch)
    assert len(select_sense("λόγος", "ἔπος", max_candidates=1)) == 1


def test_select_sense_empty_without_lsj() -> None:
    from aegean.ai.sense import select_sense

    lexicon.disable_lsj()
    assert select_sense("λόγος", "ἔπος") == []


def test_select_sense_empty_for_unknown_word(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.ai.sense import select_sense

    _activate(tmp_path, monkeypatch)
    assert select_sense("ζzzz", "ἄνθρωπος") == []


# ── grounding-regime detector ────────────────────────────────────────────────
def test_grounding_regime_help_on_rare_vocabulary(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.ai.sense import grounding_regime

    _activate(tmp_path, monkeypatch)
    # Long, rare-looking, low-polysemy vocabulary: the regime where a dominant-sense
    # gloss adds real signal.
    sig = grounding_regime("φαρμακολογικωτάτη συγγραφεύς")
    assert sig.regime == "help" and bool(sig) is True
    assert sig.rarity >= 0.6 and sig.content_words == 2


def test_grounding_regime_neutral_on_empty_content(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aegean.ai.sense import grounding_regime

    _activate(tmp_path, monkeypatch)
    sig = grounding_regime("ὁ καὶ δέ")  # all function words
    assert sig.regime == "neutral" and sig.content_words == 0 and not sig


def test_grounding_regime_degrades_without_lsj() -> None:
    from aegean.ai.sense import grounding_regime

    lexicon.disable_lsj()
    # No LSJ: polysemy/markedness are 0 but the heuristic rarity signal still computes.
    sig = grounding_regime("φαρμακολογικωτάτη συγγραφεύς")
    assert sig.polysemy == 0.0 and sig.markedness == 0.0
    assert sig.content_words == 2 and sig.rarity > 0.0
