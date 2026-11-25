"""Tests for the Biblical & Koine Greek specialist pillar (aegean.biblical, CLI, TUI)."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

import aegean.biblical as bib


def test_biblical_is_lazily_exported_from_top_level():
    """Importing aegean must not eagerly load aegean.biblical."""
    code = (
        "import sys, aegean\n"
        "assert 'aegean.biblical' not in sys.modules\n"
        "assert 'biblical' in dir(aegean)\n"
        "mod = aegean.biblical\n"
        "assert 'aegean.biblical' in sys.modules\n"
        "assert hasattr(mod, 'compare_editions')\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert res.returncode == 0, res.stderr


def test_lxx_catalog_matches_bundled_works_catalogue():
    """All 55 LXX books must map to real TLG IDs in bundled works_catalogue.json."""
    from aegean.data import load_bundled_json

    cat = load_bundled_json("greek", "works_catalogue.json")
    valid_ids = {w["id"] for w in cat["works"]}
    books = bib.lxx_books()
    assert len(books) == 55
    for b in books:
        assert b["work_id"] in valid_ids, b

    assert bib.resolve_lxx_book("Gen").work_id == "tlg0527.tlg001"
    assert bib.resolve_lxx_book("Psalms").work_id == "tlg0527.tlg027"
    assert bib.resolve_lxx_book("1Sam").work_id == "tlg0527.tlg011"
    assert bib.resolve_lxx_book("Sirach").work_id == "tlg0527.tlg034"
    assert bib.resolve_lxx_book("Dan-OG").work_id == "tlg0527.tlg056"
    assert bib.resolve_lxx_book("Dan").work_id == "tlg0527.tlg057"
    assert len(bib.lxx_books(section="Pentateuch")) == 5
    with pytest.raises(ValueError, match="unknown LXX book"):
        bib.resolve_lxx_book("NotABook")


def test_psalm_lxx_mt_numbering_roundtrip():
    assert bib.psalm_lxx_to_mt(1) == (1,)
    assert bib.psalm_lxx_to_mt(8) == (8,)
    assert bib.psalm_lxx_to_mt(9) == (9, 10)
    assert bib.psalm_lxx_to_mt(22) == (23,)
    assert bib.psalm_lxx_to_mt(113) == (114, 115)
    assert bib.psalm_lxx_to_mt(114) == (116,)
    assert bib.psalm_lxx_to_mt(115) == (116,)
    assert bib.psalm_lxx_to_mt(146) == (147,)
    assert bib.psalm_lxx_to_mt(147) == (147,)
    assert bib.psalm_lxx_to_mt(150) == (150,)
    assert bib.psalm_lxx_to_mt(151) == ()

    assert bib.psalm_mt_to_lxx(9) == (9,)
    assert bib.psalm_mt_to_lxx(10) == (9,)
    assert bib.psalm_mt_to_lxx(23) == (22,)
    assert bib.psalm_mt_to_lxx(116) == (114, 115)
    assert bib.psalm_mt_to_lxx(147) == (146, 147)

    with pytest.raises(ValueError):
        bib.psalm_lxx_to_mt(152)
    with pytest.raises(ValueError):
        bib.psalm_mt_to_lxx(151)


def test_patristic_commentaries_match_bundled_works_catalogue():
    """All 48 patristic commentaries (30 Catenae + 18 Origen) must exist in works_catalogue.json."""
    from aegean.data import load_bundled_json

    cat = load_bundled_json("greek", "works_catalogue.json")
    valid_ids = {w["id"] for w in cat["works"]}
    comms = bib.patristic_commentaries()
    assert len(comms) == 48
    assert len(bib.patristic_commentaries(kind="catena")) == 30
    assert len(bib.patristic_commentaries(kind="origen")) == 18
    for c in comms:
        assert c["work_id"] in valid_ids, c

    john = bib.patristic_commentaries("John")
    assert any(c["work_id"] == "tlg4102.tlg005" for c in john)
    assert any(c["work_id"] == "tlg2042.tlg005" for c in john)


def test_mes_parser_nomina_sacra_and_scribal_hands():
    sinaiticus_jn118 = (
        "/=θν ουδεισ εωρα/κεν πωποτε μο/νογενησ =θσ x{} {ο ων} εισ το¯ "
        "/κολπον του πα/τροσ εκεινοσ εξη/γησατο"
    )
    orig = bib.parse_mes(sinaiticus_jn118, hand="original")
    corr = bib.parse_mes(sinaiticus_jn118, hand="corrected")
    assert "Θεόν" in orig.readable
    assert "Θεός" in orig.readable
    assert "τον κολπον" in orig.readable  # superline nu-bar resolved
    assert "ο ων" not in orig.readable
    assert "ο ων" in corr.readable
    assert ("=θν", "Θεόν") in orig.nomina_sacra
    assert ("=θσ", "Θεός") in orig.nomina_sacra
    assert ("", "ο ων") in orig.corrections

    raw_abbrev = bib.parse_mes(sinaiticus_jn118, expand_nomina_sacra=False)
    assert "=θσ" in raw_abbrev.readable

    p52_jn1837 = (
        "\\&*τ^ο^υτο γε^γεννη%μαι% /~και ~εληλυθα ~εισ ~τον κ^ο^σμον "
        "ινα ~μαρτυ/ρ^η^σ^ω^ +τη +αληθεια"
    )
    r_incl = bib.parse_mes(p52_jn1837, include_supplied=True)
    r_excl = bib.parse_mes(p52_jn1837, include_supplied=False)
    assert r_incl.has_lacuna is True
    assert "τουτο γεγεννημαι και εληλυθα" in r_incl.readable
    assert "[…]" in r_excl.readable


def test_strongs_offline_dodson_and_extended_fixture(monkeypatch):
    import aegean.biblical._strongs as mod

    # Force offline Dodson fallback
    monkeypatch.setattr(mod, "_load_extended_if_cached", lambda: None)
    e = bib.strongs_entry("G3056")
    assert e is not None
    assert e.strongs == "G3056"
    assert e.lemma == "λόγος"
    assert "dodson" in e.source

    e2 = bib.strongs_entry("λόγος")
    assert e2 is not None and e2.strongs == "G3056"

    hits = bib.search_strongs("word", limit=5)
    assert len(hits) >= 1

    # Now test Extended Strong's + root tree via synthetic fixture
    fake_entries = {
        "G3056": bib.StrongsEntry(
            strongs="G3056",
            lemma="λόγος",
            translit="logos",
            morph="G:N-M",
            gloss="word",
            definition="speech, word",
            derivation="from G3004 (λέγω);",
            roots=("G3004",),
            hebrew=("H1697",),
            source="strongs-greek",
        ),
        "G3004": bib.StrongsEntry(
            strongs="G3004",
            lemma="λέγω",
            translit="legō",
            morph="G:V",
            gloss="to say",
            definition="to speak, say",
            derivation="a primary verb;",
            roots=(),
            source="strongs-greek",
        ),
    }
    monkeypatch.setattr(mod, "_load_extended_if_cached", lambda: mod._ExtendedStrongsIndex(fake_entries, {}))
    tree = bib.strongs_roots("G3056")
    assert tree["strongs"] == "G3056"
    assert tree["roots"][0]["strongs"] == "G3004"
    assert tree["roots"][0]["lemma"] == "λέγω"


def test_compare_editions_and_witnesses_with_fixtures(monkeypatch):
    import aegean.biblical._editions as ed_mod
    import aegean.biblical._witnesses as wit_mod

    fake_ed_bundle = {
        "_meta": {"license": "test"},
        "editions": {
            "sblgnt": {
                "_info": {"name": "SBLGNT", "license": "CC BY 4.0"},
                "books": {"John": {"1.18": "θεὸν οὐδεὶς ἑώρακεν πώποτε· ⸂μονογενὴς θεὸς⸃ ὁ ὢν εἰς τὸν κόλπον τοῦ πατρὸς ἐκεῖνος ἐξηγήσατο."}},
            },
            "byz": {
                "_info": {"name": "BYZ", "license": "PD"},
                "books": {"John": {"1.18": "Θεὸν οὐδεὶς ἑώρακεν πώποτε· ὁ μονογενὴς υἱός, ὁ ὢν εἰς τὸν κόλπον τοῦ πατρός, ἐκεῖνος ἐξηγήσατο."}},
            },
        },
    }
    monkeypatch.setattr(ed_mod, "_load_editions_bundle", lambda allow_fetch=True: fake_ed_bundle)

    cmp = bib.compare_editions("John", "1.18", editions=["sblgnt", "byz"], offline=True)
    assert cmp.variant_verse_count == 1
    assert not cmp.verses[0].identical
    assert any(v.edition == "byz" and "υἱός" in v.edition_words for v in cmp.verses[0].variants)

    corp = bib.load_nt("John", "1.18", edition="byz", offline=True)
    assert len(corp) == 1
    assert any(t.text == "υἱός" for t in corp.documents[0].tokens)

    fake_wit_bundle = {
        "_meta": {"license": "CC BY-SA 4.0", "source_url": "https://example.org"},
        "witnesses": {
            "P66": {
                "_info": {"siglum": "P66", "alias": "𝔓66", "name": "Papyrus 66", "century": "c. 200 CE"},
                "books": {"John": {"1.18": "/=θν ουδεισ εωρακεν πωποται μονογενησ =θσ"}},
            },
            "02": {
                "_info": {"siglum": "02", "alias": "A", "name": "Codex Alexandrinus", "century": "5th c. CE"},
                "books": {"John": {"1.18": "=θν ουδεισ εωρακεν πωποτε ο μονογενησ υιοσ"}},
            },
        },
    }
    monkeypatch.setattr(wit_mod, "_load_witnesses_bundle", lambda allow_fetch=True: fake_wit_bundle)

    rows = bib.compare_witnesses("John", "1.18", sigla=["P66", "A"], offline=True)
    assert len(rows) == 1
    assert len(rows[0].witnesses) == 2
    assert "Θεός" in rows[0].witnesses[0].reading.readable
    assert "υιος" in rows[0].witnesses[1].reading.readable

    wcorp = bib.load_witness("P66", "John", "1.18", offline=True)
    assert len(wcorp) == 1
    assert wcorp.documents[0].tokens[0].text == "Θεόν"


def test_word_study_and_concordance_search_offline():
    ws = bib.word_study("G3056", book="John", offline=True)
    assert ws.lemma == "λόγος"
    assert ws.total_occurrences >= 4  # John 1 has 4 occurrences of λόγος
    assert "John" in ws.by_book

    hits = bib.search_bible("λόγος", by="lemma", book="John", offline=True, limit=10)
    assert len(hits) >= 4
    assert hits[0].ref.startswith("John 1:")

    morph_hits = bib.search_bible("V-IAI", by="morph", book="John", offline=True, limit=5)
    assert len(morph_hits) >= 1


def test_cli_bible_commands_json():
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    runner = CliRunner()
    app = _build_app()

    r1 = runner.invoke(app, ["bible", "psalm", "23", "--from", "mt", "--json"])
    assert r1.exit_code == 0, r1.output
    assert json.loads(r1.output)["psalms"] == [22]

    r2 = runner.invoke(app, ["bible", "books", "lxx", "--json"])
    assert r2.exit_code == 0, r2.output
    assert len(json.loads(r2.output)) == 55

    r3 = runner.invoke(app, ["bible", "books", "witnesses", "--json"])
    assert r3.exit_code == 0, r3.output
    assert len(json.loads(r3.output)) == 13

    r4 = runner.invoke(app, ["bible", "read", "John", "1.1", "--offline", "--json"])
    assert r4.exit_code == 0, r4.output
    data = json.loads(r4.output)
    assert len(data["verses"]) == 1
    assert "Λόγος" in data["verses"][0]["text"]

    r5 = runner.invoke(app, ["bible", "commentary", "John", "--json"])
    assert r5.exit_code == 0, r5.output
    assert len(json.loads(r5.output)) >= 5

    r6 = runner.invoke(app, ["bible", "read", "Gen", "1.1-3", "--lxx", "--offline", "--json"])
    assert r6.exit_code == 0, r6.output
    lxx_data = json.loads(r6.output)
    assert lxx_data["source"] == "lxx" and len(lxx_data["verses"]) == 3
    assert "θεὸς" in lxx_data["verses"][0]["text"]

    r7 = runner.invoke(app, ["bible", "search", "φῶς", "--lxx", "--offline", "--json"])
    assert r7.exit_code == 0, r7.output
    assert len(json.loads(r7.output)) >= 3


def test_lxx_offline_subverses_psalm_and_nomina_sacra(monkeypatch):
    from aegean.biblical import _lxx as lxx_mod
    from aegean.data import DataNotAvailableError
    from aegean.tui import data as tui_data

    # 1. Offline Swete LXX sample (Gen 1:1-5 & Ps 22:1-6) when full bundle is absent
    monkeypatch.setattr(lxx_mod, "_load_lxx_bundle", lambda *, allow_fetch=True, force=False: None)
    gen = bib.load_lxx("Gen", ref="1.1-5", offline=True)
    assert len(gen) == 1
    assert gen.documents[0].id == "Gen 1"
    assert len(gen.documents[0].lines) == 5

    ps = bib.load_lxx("Ps", ref="22.1-6", offline=True)
    assert ps.documents[0].id == "Ps 22"
    assert any(t.text == "ποιμαίνει" for t in ps.documents[0].tokens)

    with pytest.raises(DataNotAvailableError):
        bib.load_lxx("Isa", ref="53.1", offline=True)

    hits = bib.search_lxx("φῶς", offline=True)
    assert len(hits) == 3
    assert hits[0].ref == "Gen 1:3"
    with pytest.raises(ValueError):
        bib.search_lxx("   ", offline=True)

    # 2. LXX-plus sub-verses (e.g. Josh 15.59 vs 15.59a, Esth prologue) stay distinct & ordered
    fake_lxx = {
        "_meta": {"license": "CC BY-SA 4.0", "source_commit": "4c9c843"},
        "books": {
            "Josh": {
                "verses": {
                    "15.59a": "Θεκὼ καὶ Ἐφραθά, αὕτη ἐστὶν Βαιθλέεμ.",
                    "15.59": "καὶ Μααρὼθ καὶ Βαιθανάμ.",
                    "15.60": "Καριαθβαάλ, αὕτη Καριαθιαρείμ.",
                }
            },
            "Esth": {
                "verses": {
                    "prologue.1": "Ἔτους δευτέρου βασιλεύοντος Ἀρταξέρξου.",
                    "1.1": "Καὶ ἐγένετο μετὰ τοὺς λόγους τούτους.",
                }
            },
        },
    }
    monkeypatch.setattr(lxx_mod, "_load_lxx_bundle", lambda *, allow_fetch=True, force=False: fake_lxx)
    josh = bib.load_lxx("Josh", ref="15.59-60", offline=True)
    refs_in_order = list(dict.fromkeys(t.annotations["ref"] for t in josh.documents[0].tokens))
    assert refs_in_order == ["Josh.15.59", "Josh.15.59a", "Josh.15.60"]

    esth = bib.load_lxx("Esth", ref="prologue", offline=True)
    assert esth.documents[0].id == "Esth prologue"
    assert esth.documents[0].tokens[0].annotations["ref"] == "Esth.prologue.1"

    # 3. convert_psalm & expand_nomina_sacra
    c23 = bib.convert_psalm(23, system="mt")
    assert c23 == {
        "system": "mt",
        "input": 23,
        "mt": [23],
        "lxx": [22],
        "lxx_work_id": "tlg0527.tlg027",
        "note": "",
    }
    assert bib.convert_psalm(151, system="lxx")["mt"] == []
    with pytest.raises(ValueError):
        bib.convert_psalm(0)

    expanded, notes = bib.expand_nomina_sacra("θς ην ο λογος, και πνα αγιον.")
    assert expanded == "Θεός ην ο λογος, και Πνεῦμα αγιον."
    assert len(notes) == 2

    # 4. TUI helpers (LXX fallback in bible_read_text + inline search/passage in bible_lxx_and_catenae_text)
    monkeypatch.setattr(lxx_mod, "_load_lxx_bundle", lambda *, allow_fetch=True, force=False: None)
    assert "ἐποίησεν" in tui_data.bible_read_text("Gen 1.1-2", offline=True)
    assert "Gen 1:3" in tui_data.bible_lxx_and_catenae_text("φῶς")
    assert "ποιμαίνει" in tui_data.bible_lxx_and_catenae_text("Ps 22.1-2")


def test_commentary_excerpt_search(monkeypatch):
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, DocumentMeta, Token, TokenKind
    from aegean.scripts.greek import perseus

    toks_hit = [
        Token(text="Ἐν", kind=TokenKind.WORD, glyphs="Ἐν", line_no=1, position=0),
        Token(text="ἀρχῇ", kind=TokenKind.WORD, glyphs="ἀρχῇ", line_no=1, position=1),
        Token(text="Λόγος", kind=TokenKind.WORD, glyphs="Λόγος", line_no=1, position=2),
    ]
    toks_false_substr = [
        Token(text="πυρὸς", kind=TokenKind.WORD, glyphs="πυρὸς", line_no=1, position=0),
        Token(text="φλογὸς", kind=TokenKind.WORD, glyphs="φλογὸς", line_no=1, position=1),
    ]
    fake_corp = Corpus(
        [
            Document(id="1.0", script_id="greek", tokens=toks_false_substr, lines=[[0, 1]], meta=DocumentMeta(name="1.0")),
            Document(id="1.1", script_id="greek", tokens=toks_hit, lines=[[0, 1, 2]], meta=DocumentMeta(name="1.1")),
        ],
        script_id="greek",
    )
    monkeypatch.setattr(perseus, "load_work", lambda wid, ref=None, source=None, force=False: fake_corp)
    excerpts = bib.commentary_excerpt("John", query="λογος", limit=3)
    assert len(excerpts) == 1
    assert excerpts[0].section_id == "1.1"
    assert excerpts[0].work_id == "tlg4102.tlg005"
    assert excerpts[0].matched_words == ("Λόγος",)


@pytest.mark.xdist_group("tui")
def test_tui_biblical_screen_smoke():
    import asyncio

    pytest.importorskip("textual")
    from textual.widgets import Input, Static

    from aegean.tui.app import AegeanApp
    from aegean.tui.screens.bible import BiblicalScreen

    async def _run() -> None:
        app = AegeanApp()
        async with app.run_test() as pilot:
            await pilot.press("b")
            await pilot.pause()
            assert isinstance(app.screen, BiblicalScreen)
            inter = app.screen.query_one("#bible-interlinear", Static).render()
            assert "Λόγος" in str(inter)
            study = app.screen.query_one("#bible-study", Static).render()
            assert "λόγος" in str(study)
            lxx_inp = app.screen.query_one("#bible-lxx-filter", Input)
            lxx_inp.value = "23"
            await pilot.pause()
            lxx_txt = str(app.screen.query_one("#bible-lxx", Static).render())
            assert "LXX Psalm 22" in lxx_txt

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()
