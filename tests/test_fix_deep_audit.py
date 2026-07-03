"""Correctness regressions across the Greek, Aegean-script, data, and interface layers.

Each test pins the corrected OUTPUT of one fixed defect against a known/hand-computed answer
or a property invariant (round-trip, range bound, cross-surface agreement), not merely that
the call runs. Grouped by area.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import aegean
from aegean.core.model import Document, Token, TokenKind


# ── [0] Corpus.copy / cached load: per-token annotations are independent ──────


def test_copy_gives_each_token_an_independent_annotations_dict() -> None:
    c = aegean.load("lineara")
    cc = c.copy()
    assert cc.fingerprint() == c.fingerprint()  # copy fingerprints identically
    cc.documents[0].tokens[0].annotations["note"] = "x"
    # editing the copy must not reach the original (or a sibling copy)
    assert "note" not in c.documents[0].tokens[0].annotations


def test_editing_a_loaded_corpus_does_not_leak_into_a_later_load() -> None:
    fp_before = aegean.load("lineara").fingerprint()
    c1 = aegean.load("lineara")
    c1.documents[0].tokens[0].annotations["note"] = "my analysis"
    fresh = aegean.load("lineara")
    assert "note" not in fresh.documents[0].tokens[0].annotations
    assert fresh.fingerprint() == fp_before  # the analysis-cache key is not poisoned


def test_copy_gives_each_sign_an_independent_attrs_dict() -> None:
    c = aegean.load("lineara")
    assert c.sign_inventory is not None
    cc = c.copy()
    cc.sign_inventory.signs[0].attrs["z"] = "1"
    assert "z" not in c.sign_inventory.signs[0].attrs


# ── [1] lemmatizer: no fabricated -ω non-words; 3rd-decl datives seeded ────────


def test_third_declension_datives_lemmatize_to_the_noun_not_a_fabricated_verb() -> None:
    from aegean.greek import lemmatize

    assert lemmatize("πόλει") == "πόλις"
    assert lemmatize("πίστει") == "πίστις"
    assert lemmatize("δυνάμει") == "δύναμις"
    assert lemmatize("ὄρει") == "ὄρος"


def test_verbal_ei_strip_still_recovers_genuine_present_verbs() -> None:
    from aegean.greek import lemmatize

    assert lemmatize("λέγει") == "λέγω"
    assert lemmatize("ἔχει") == "ἔχω"
    assert lemmatize("πείθεις") == "πείθω"   # 2sg present, accent not on -εις
    assert lemmatize("πράσσει") == "πράσσω"  # genuine double-σ present


def test_ei_strip_does_not_fabricate_on_participles_futures_or_indeclinables() -> None:
    from aegean.greek import lemmatize

    # aorist-passive participle (accent on the diphthong), sigmatic future, -εί indeclinable
    for form in ("ἀποκριθεὶς", "δώσει", "ἐπεὶ"):
        assert not lemmatize(form).endswith("ω"), form


# ── [2] elegiac pentameter: the final anceps accepts a short syllable ──────────


def test_pentameter_accepts_a_short_final_syllable_brevis_in_longo() -> None:
    from aegean.greek.meter import scan_pentameter

    # identical line, short vs long final: both must scan
    short = scan_pentameter("τεθναίην ὅτε μοι μηκέτι ταῦτα μένε")
    long = scan_pentameter("τεθναίην ὅτε μοι μηκέτι ταῦτα μένω")
    assert short is not None and long is not None


# ── [3][18][20] phonetic maps are case-insensitive on lowercase input ─────────


def test_linearb_word_to_phonetic_folds_case() -> None:
    from aegean.scripts.linearb.phonetic import word_to_phonetic

    assert word_to_phonetic("qa-si-re-u") == word_to_phonetic("QA-SI-RE-U") == "kwasireu"


def test_cypriot_word_to_phonetic_folds_case() -> None:
    from aegean.scripts.cypriot.phonetic import word_to_phonetic

    assert word_to_phonetic("pa-si-le-u-se") == word_to_phonetic("PA-SI-LE-U-SE")


# ── [4] clean_gloss: derivation pointers yield "", real glosses survive ───────


def test_clean_gloss_drops_derivation_pointer_fragments() -> None:
    from aegean.ai.grounding import clean_gloss

    assert clean_gloss("adverb of ἀγαθῶς") == ""
    assert clean_gloss("comp. of ἀγαθός") == ""
    assert clean_gloss("a strengthd. form of βαίνω") == ""
    assert clean_gloss("as if contr. from ἐάω") == ""


def test_clean_gloss_keeps_real_meanings_that_merely_contain_of_or_from() -> None:
    from aegean.ai.grounding import clean_gloss

    assert clean_gloss("fond of, devoted to") == "fond of, devoted to"
    assert clean_gloss("from, away from") == "from, away from"
    assert clean_gloss("reckoning (cf. λέγω)") == "reckoning"


# ── [5] db.search: an all-separator token is found in token mode ──────────────


def test_search_finds_a_punctuation_token_in_token_mode(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from aegean import db

    doc = Document(
        id="d1", script_id="greek",
        tokens=[Token("λόγος", TokenKind.WORD, position=0),
                Token("·", TokenKind.PUNCT, position=1)],
        lines=[[0, 1]],
    )
    path = tmp_path / "c.db"
    db.to_sqlite(aegean.Corpus([doc], script_id="greek"), path)
    hits = db.search(str(path), "·", mode="token")
    assert [t for _, _, t in hits] == ["·"]  # the punctuation token is found


# ── [6] from_csv strips a UTF-8 BOM so the id column is not lost ───────────────


def test_from_csv_reads_a_bom_prefixed_header(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from aegean.io import from_csv

    p = tmp_path / "x.csv"
    p.write_bytes("﻿id,text\r\nA1,λόγος\r\n".encode("utf-8"))
    c = from_csv(p, id_col="id")
    assert c.documents[0].id == "A1"  # not "<stem>:1" — the BOM-prefixed id col is read


# ── [7] MCP query_corpus: negate is coerced, not raw bool() ───────────────────


def test_mcp_query_corpus_does_not_negate_on_a_false_string() -> None:
    from aegean import mcp_server

    site = "Haghia Triada"
    plain = mcp_server.query_corpus("lineara", [{"field": "site-is", "value": site}])
    # "false" must read as no-negation (same result as omitting negate), and must differ
    # from a real negation — a raw bool("false") would wrongly make all three identical.
    as_false = mcp_server.query_corpus(
        "lineara", [{"field": "site-is", "value": site, "negate": "false"}]
    )
    negated = mcp_server.query_corpus(
        "lineara", [{"field": "site-is", "value": site, "negate": True}]
    )
    assert plain["total_inscriptions"] == as_false["total_inscriptions"] > 0
    assert negated["total_inscriptions"] != plain["total_inscriptions"]


# ── [8] data-store visibility reaches MCP and the TUI ─────────────────────────


def test_mcp_data_status_and_tui_rows_agree_with_the_cli_probe() -> None:
    from aegean import mcp_server
    from aegean.data import _REMOTE, cache_dir, is_downloaded
    from aegean.tui.data import dataset_rows

    root = cache_dir()
    expected = {name: is_downloaded(spec, root) for name, spec in _REMOTE.items()}
    mcp = {d["name"]: d["downloaded"] for d in mcp_server.data_status()["datasets"]}
    tui = {r.name: r.downloaded for r in dataset_rows()}
    assert mcp == expected
    assert tui == expected


# ── [9] check_balances: a marker-set mismatch does not raise ──────────────────


def test_check_balances_no_stopiteration_on_marker_mismatch() -> None:
    from aegean.core.numerals import Markers, check_balances, parse_account_lines

    # role-assign with the default markers, then check with a disjoint marker set
    lines = parse_account_lines(["A 1", "B 2", "KU-RO 3"])
    other = Markers(total={"NONSUCH"}, grand_total=set(), deficit=set())
    checks = check_balances(lines, other)  # must not raise StopIteration
    assert isinstance(checks, list)


# ── [10][12] sandhi: capitalized elision + unaccented enclitic movable-nu ──────


def test_capitalized_elision_is_restored() -> None:
    from aegean.greek.sandhi import resolve_sandhi

    assert resolve_sandhi("Ταῦτ'").words == ("Ταῦτα",)
    assert resolve_sandhi("Πάντ'").words == ("Πάντα",)


def test_unaccented_enclitic_copula_is_movable_nu() -> None:
    from aegean.greek.sandhi import resolve_sandhi

    assert resolve_sandhi("ἐστιν").kind == "movable-nu"
    assert resolve_sandhi("εἰσιν").kind == "movable-nu"
    # the i-stem accusative look-alike stays unclaimed
    assert resolve_sandhi("γνῶσιν").kind is None


# ── [11][15] tokenize: leading-apostrophe prodelision agrees with words ────────


def test_prodelision_word_is_consistent_between_tokenize_and_tokenize_words() -> None:
    from aegean.greek.tokenize import tokenize, tokenize_words

    text = "ποῦ 'στι"
    words = [t.text for t in tokenize(text) if t.kind == TokenKind.WORD]
    assert words == tokenize_words(text) == ["ποῦ", "'στι"]


# ── [13] lunate sigma: capital form does not leak verbatim ────────────────────


def test_capital_lunate_sigma_maps_to_beta_code_s() -> None:
    from aegean.greek.normalize import unicode_to_betacode

    assert unicode_to_betacode("Ϲ") == "*s"
    assert unicode_to_betacode("ϲ") == "s"


# ── [14] morphology: demonstratives resolve to PRON with features ─────────────


def test_demonstrative_oblique_forms_are_pron_not_noun() -> None:
    from aegean.greek import morphology

    for form, lemma in [("τούτου", "οὗτος"), ("ἐκείνων", "ἐκεῖνος"),
                        ("ταύτην", "οὗτος"), ("ταῦτα", "οὗτος")]:
        analyses = morphology.analyze(form)
        assert {a.pos for a in analyses} == {"PRON"}, form
        assert analyses[0].lemma == lemma
    # the smooth intensive αὐτή must not be read as the demonstrative
    assert all(a.lemma != "οὗτος" for a in morphology.analyze("αὐτή"))


# ── [16] wiki KU total; [17] subscript by_label folding ───────────────────────


def test_subscript_sign_labels_resolve_both_ways() -> None:
    inv = aegean.load("lineara").sign_inventory
    assert inv is not None
    # the corpus prints RA₂; the inventory stores RA2 — both must resolve to the same sign
    assert inv.by_label("RA₂") is inv.by_label("RA2")
    assert inv.by_label("RA₂") is not None


# ── [19] Cypriot/Linear B lexicon: the Leiden underdot is a known reading ──────


def test_cypriot_lexicon_reads_a_damaged_but_legible_token() -> None:
    from aegean.scripts.cypriot import lexicon

    dotted = "P" + "Ạ" + "-SI-LE-U-SE"  # underdotted alpha = damaged but legible
    assert lexicon.greek_reading(dotted) == lexicon.greek_reading("PA-SI-LE-U-SE")
    assert lexicon.greek_reading(dotted) is not None


# ── [21] sense.py rarity uses the ordinary phi, not the phi symbol ────────────


def test_rarity_heuristic_counts_ordinary_phi() -> None:
    from aegean.ai.sense import _heuristic_rarity

    assert _heuristic_rarity(["φιλοσοφία", "φύσις"]) > _heuristic_rarity(["λογος", "λογος"])


# ── [22] EpiDoc strips XML-invalid control chars so the doc re-parses ──────────


def test_to_epidoc_strips_control_characters_and_re_parses() -> None:
    from aegean.io.epidoc import to_epidoc

    doc = Document(
        id="t1", script_id="greek",
        tokens=[Token("λό\x0cγ\x00ος", TokenKind.WORD)], lines=[[0]],
    )
    xml = to_epidoc(doc)
    root = ET.fromstring(xml)  # must not raise
    words = [e.text for e in root.iter() if e.tag.endswith("}w")]
    assert words == ["λόγος"]


# ── [23] word-scope queries work on alphabetic Greek (not just hyphenated) ─────


def test_word_scope_query_matches_greek_words() -> None:
    from aegean.analysis.query import FilterRow, run_query

    nt = aegean.greek.load_nt()
    sub = nt.subset([d.id for d in nt.documents[:3]])
    res = run_query(sub, [FilterRow(field="word-prefix", value="Χριστ")], output="words")
    assert len(res.words) > 0
    assert all(w.upper().startswith("ΧΡΙΣΤ") for w, _ in res.words)


# ── [24] quickstart: seven commands across eight steps ────────────────────────


def test_quickstart_step_and_command_counts() -> None:
    from aegean.cli._quickstart import STEPS

    assert len(STEPS) == 8
    assert sum(1 for s in STEPS if s.args is not None) == 7


# ── [25] format_value: a tiny negative rounds to "0", never "-0" ──────────────


def test_format_value_never_renders_negative_zero() -> None:
    from aegean.core.numerals import format_value

    assert format_value(-0.0001) == "0"
    assert format_value(-1.5) == "-1½"
    assert format_value(-2.75) == "-2¾"
