"""Tests for the Ancient Greek verse dependency fold: the standard-AGDT build converter
(``scripts/build_verse_fold.py``), the `evaluate_on_verse` wiring + track filtering, the
CLI target, and adversarial inputs.

The build converter is exercised on a hand-checked fixture tree (real Bacchae 5, tlg0006.
tlg017); the evaluator wiring runs through a stubbed active model (the test_papygreek
pattern) and skips if the official conll18 evaluator is not cached (offline). Track
filtering is a pure offline test (no evaluator)."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from aegean import data
from aegean.data import DataNotAvailableError
from aegean.greek import joint, verse_eval

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_verse_fold as bvf  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "verse" / "sample.conllu"


def _sentence(xml: str) -> ET.Element:
    """Parse a ``<sentence>…</sentence>`` XML string into an element."""
    return ET.fromstring(xml)


# A real, hand-checked Bacchae sentence (euripides-ba-1-22 sentence 5), standard AGDT
# ``aldt`` schema: "ἀμπέλου δέ νιν πέριξ ἐγὼ ʼκάλυψα βοτρυώδει χλόῃ ."
_BA5 = """<sentence id="5">
 <word id="1" form="ἀμπέλου" lemma="ἄμπελος" postag="n-s---fg-" relation="ATR" head="8"/>
 <word id="2" form="δέ" lemma="δέ" postag="c--------" relation="COORD" head="0"/>
 <word id="3" form="νιν" lemma="νιν" postag="p3s---ma-" relation="OBJ" head="6"/>
 <word id="4" form="πέριξ" lemma="πέριξ" postag="r--------" relation="AuxP" head="6"/>
 <word id="5" form="ἐγὼ" lemma="ἐγώ" postag="p1s---mn-" relation="SBJ" head="6"/>
 <word id="6" form="ʼκάλυψα" lemma="καλύπτω" postag="v1saia---" relation="PRED_CO" head="2"/>
 <word id="7" form="βοτρυώδει" lemma="βοτρυώδης" postag="a-s---fd-" relation="ATR" head="8"/>
 <word id="8" form="χλόῃ" lemma="χλόη" postag="n-s---fd-" relation="OBJ" head="4"/>
 <word id="9" form="." lemma="punc1" postag="u--------" relation="AuxK" head="0"/>
</sentence>"""


def _rows(block: str) -> list[list[str]]:
    return [ln.split("\t") for ln in block.splitlines() if ln and not ln.startswith("#")]


# --- the hand-checked converter (real Bacchae 5) ----------------------------------


def test_convert_verse_sentence_hand_checked() -> None:
    words = bvf.agdt_reg_words(_sentence(_BA5))
    assert bvf.sentence_status(words) == "ok"
    block, forms = bvf.sentence_to_conllu("verse:tragedy:euripides-ba-1-22@5", words)
    rows = _rows(block)
    assert len(rows) == 9
    assert all(len(r) == 10 for r in rows)  # CoNLL-U 10 columns
    got = {int(r[0]): (r[1], r[3], r[6], r[7]) for r in rows}  # (form, upos, head, deprel)
    assert got[6] == ("ʼκάλυψα", "VERB", "0", "root")     # PRED_CO -> the single root
    assert got[2] == ("δέ", "CCONJ", "6", "cc")           # COORD -> cc on the conjunct
    assert got[5] == ("ἐγὼ", "PRON", "6", "nsubj")        # SBJ -> nsubj
    assert got[4] == ("πέριξ", "ADP", "8", "case")        # AuxP -> case (promotes χλόῃ)
    assert got[8] == ("χλόῃ", "NOUN", "6", "obl")         # AuxP complement promoted -> obl
    # exactly one root
    assert sum(1 for r in rows if r[6] == "0") == 1
    # punctuation lemma reconciled to the surface form (training convention, not "punc1")
    assert {int(r[0]): r[2] for r in rows}[9] == "."
    # a prodelided real form's lemma is the clean citation form
    assert {int(r[0]): r[2] for r in rows}[6] == "καλύπτω"
    assert forms[0] == "ἀμπέλου"


def test_agdt_reg_words_flags_artificial_robustly() -> None:
    # elliptic (attribute), bracketed placeholder, and insertion-only nodes must all be
    # flagged so a sentence carrying one is excluded (no reconstructed token can survive)
    xml = """<sentence id="1">
     <word id="1" form="[0]" lemma="-" postag="v3spia---" relation="PRED_CO" head="2"
           artificial="elliptic" insertion_id="0000e"/>
     <word id="2" form="[" lemma="punc1" postag="u--------" relation="AuxG" head="3"/>
     <word id="3" form="θέλω" lemma="ἐθέλω" postag="v1spia---" relation="PRED" head="0"/>
    </sentence>"""
    words = bvf.agdt_reg_words(_sentence(xml))
    assert words[0]["artificial"] == "elliptic"       # the attribute
    assert words[1]["artificial"] == "bracketed"      # a bare '[' placeholder form
    assert words[2]["artificial"] is None             # a real token
    assert bvf.sentence_status(words) == "artificial"  # the whole sentence is dropped


def test_sentence_status_partial_and_ok() -> None:
    ok = bvf.agdt_reg_words(_sentence(
        '<sentence id="1"><word id="1" form="θέλω" lemma="ἐθέλω" postag="v1spia---" '
        'relation="PRED" head="0"/></sentence>'))
    assert bvf.sentence_status(ok) == "ok"
    partial = bvf.agdt_reg_words(_sentence(
        '<sentence id="1"><word id="1" form="θέλω" lemma="ἐθέλω" postag="v1spia---" '
        'relation="PRED" head="0"/>'
        '<word id="2" form="σε" lemma="σύ" postag="p2s----a-"/></sentence>'))  # no head/rel
    assert bvf.sentence_status(partial) == "partial"


# --- work-level disjointness + near-duplicate accounting --------------------------


def test_check_disjointness_passes_when_only_medea_present() -> None:
    train_files = {
        "tlg0003.tlg001.perseus-grc1.1.tb.xml",
        "pedalion:euripides_medea.xml",
        "gorman:Lysias 1 bu1.xml",
    }
    rec = bvf.check_disjointness(train_files)
    assert rec["tragedy"]["forbidden_matches"] == []
    # the same-author (Euripides) training documents are recorded: only Medea
    assert rec["tragedy"]["same_author_in_training"] == ["pedalion:euripides_medea.xml"]
    assert rec["hexameter"]["forbidden_matches"] == []


def test_check_disjointness_fails_on_forbidden_work() -> None:
    # a training set that contained Bacchae (tlg0006.tlg017) must fail the build
    with pytest.raises(SystemExit):
        bvf.check_disjointness({"tlg0006.tlg017.perseus-grc2.tb.xml"})
    # ...or Maximus (the hexameter source)
    with pytest.raises(SystemExit):
        bvf.check_disjointness({"maximus-astrol-1-4.xml"})


def test_near_duplicates_documented() -> None:
    # both near-duplicate annotations are recorded as excluded, with a reason each
    assert set(bvf.EXCLUDED_NEAR_DUPS) == {
        "public/xml/eur-ba-23-169.xml",
        "public/xml/max-astrol-I-4-1-14.xml",
    }
    assert all(bvf.EXCLUDED_NEAR_DUPS.values())


# --- track filtering (pure, no evaluator needed) ----------------------------------


def test_read_track_filters_by_prefix() -> None:
    all_sents, all_text = verse_eval._read_track(FIXTURE, None)
    trag_sents, trag_text = verse_eval._read_track(FIXTURE, "tragedy")
    hex_sents, hex_text = verse_eval._read_track(FIXTURE, "hexameter")
    assert len(all_sents) == 3
    assert len(trag_sents) == 2
    assert len(hex_sents) == 1
    assert all(s.sent_id.startswith("verse:tragedy:") for s in trag_sents)
    assert all(s.sent_id.startswith("verse:hexameter:") for s in hex_sents)
    # the filtered gold text is the concatenation of exactly those blocks (byte-aligned)
    assert "verse:hexameter:" not in trag_text
    assert "verse:tragedy:" not in hex_text
    assert len(trag_text) + len(hex_text) == len(all_text)


# --- evaluator wiring (stubbed active model; skips without the cached evaluator) ---


class _StubModel:
    """A minimal joint model: tags every token NOUN, a single-root flat tree."""

    def analyze(self, forms: list[str]) -> joint.SentenceAnalysis:
        n = len(forms)
        return joint.SentenceAnalysis(
            tokens=tuple(forms),
            upos=tuple("NOUN" for _ in forms),
            xpos=tuple("n--------" for _ in forms),
            feats=tuple("_" for _ in forms),
            head=tuple(0 if i == 0 else 1 for i in range(n)),
            deprel=tuple("root" if i == 0 else "dep" for i in range(n)),
            lemma=tuple(forms),
        )


def _require_evaluator() -> None:
    from aegean.data import cache_dir
    from aegean.greek.ud import _CACHE_SUBDIR, _eval_module

    if not (cache_dir() / _CACHE_SUBDIR / "conll18_ud_eval.py").exists():
        try:
            _eval_module()
        except Exception as exc:  # pragma: no cover - offline
            pytest.skip(f"official evaluator unavailable offline: {exc}")


def test_evaluate_on_verse_wires_through_official_evaluator(monkeypatch) -> None:
    _require_evaluator()
    monkeypatch.setattr(joint, "_ACTIVE", _StubModel())
    res = verse_eval.evaluate_on_verse(source=FIXTURE)
    from aegean.greek.ud import load_conllu

    sents = load_conllu(FIXTURE)
    assert res["treebank"] == "verse" and res["track"] == "all" and res["split"] == "test"
    assert res["parsed"] is True
    assert res["n_sentences"] == len(sents) == 3
    assert res["n_words"] == sum(len(s.tokens) for s in sents)
    for key in ("upos", "xpos", "ufeats", "lemma", "uas", "las", "clas"):
        assert 0.0 <= res[key] <= 1.0
    # DET/PUNCT/VERB gold tokens all mislabeled NOUN by the stub → UPOS well under 1.0
    assert res["upos"] < 1.0


def test_evaluate_on_verse_track_scopes_the_score(monkeypatch) -> None:
    _require_evaluator()
    monkeypatch.setattr(joint, "_ACTIVE", _StubModel())
    trag = verse_eval.evaluate_on_verse(track="tragedy", source=FIXTURE)
    everything = verse_eval.evaluate_on_verse(source=FIXTURE)
    assert trag["track"] == "tragedy" and trag["n_sentences"] == 2
    # 'all' (the default) scores the whole fold; tragedy is the proper subset
    assert everything["track"] == "all" and everything["n_sentences"] == 3
    assert trag["n_words"] < everything["n_words"]
    # the removed hexameter filter gets its own clean rejection
    with pytest.raises(ValueError, match="prose paraphrase"):
        verse_eval.evaluate_on_verse(track="hexameter", source=FIXTURE)


def test_evaluate_on_verse_parse_false_drops_uas(monkeypatch) -> None:
    _require_evaluator()
    monkeypatch.setattr(joint, "_ACTIVE", None)  # no parser active
    res = verse_eval.evaluate_on_verse(source=FIXTURE, parse=False)
    assert res["parsed"] is False
    assert res["uas"] is None and res["las"] is None and res["clas"] is None
    assert 0.0 <= res["upos"] <= 1.0


def test_evaluate_on_verse_rejects_bad_track() -> None:
    with pytest.raises(ValueError):
        verse_eval.evaluate_on_verse(track="epic", source=FIXTURE)


# --- CLI target -------------------------------------------------------------------


def _cli_app():
    from aegean.cli import _build_app

    return _build_app()


def test_cli_verse_target_accepted_and_track_batch_forwarded(monkeypatch) -> None:
    from typer.testing import CliRunner

    seen: list[tuple[str | None, int | None]] = []

    def fake_eval(*, track: str | None = None, progress: object = None,
                  batch_size: int | None = None) -> dict[str, float]:
        seen.append((track, batch_size))
        return {"upos": 0.9, "lemma": 0.8, "uas": 0.7, "las": 0.6}

    monkeypatch.setattr("aegean.greek.evaluate_on_verse", fake_eval)
    monkeypatch.setattr("aegean.greek.use_neural_pipeline", lambda **kw: None)
    runner = CliRunner()
    r1 = runner.invoke(_cli_app(),
                       ["greek", "eval", "verse", "--track", "tragedy", "--batch-size", "4", "--json"])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(_cli_app(), ["greek", "eval", "verse", "--json"])
    assert r2.exit_code == 0, r2.output
    # track forwarded as the value; "all" -> None; batch forwarded when given, else absent
    assert seen == [("tragedy", 4), (None, None)]


def test_cli_verse_rejects_track_on_other_target(monkeypatch) -> None:
    from typer.testing import CliRunner

    monkeypatch.setattr("aegean.greek.use_neural_pipeline", lambda **kw: None)
    runner = CliRunner()
    r = runner.invoke(_cli_app(), ["greek", "eval", "ud", "--track", "tragedy"])
    assert r.exit_code != 0
    assert "--track applies to `eval verse`" in r.output


def test_cli_verse_rejects_bad_track_and_drift(monkeypatch) -> None:
    from typer.testing import CliRunner

    monkeypatch.setattr("aegean.greek.use_neural_pipeline", lambda **kw: None)
    runner = CliRunner()
    r = runner.invoke(_cli_app(), ["greek", "eval", "verse", "--track", "bogus"])
    assert r.exit_code != 0
    assert "--track must be tragedy or all" in r.output
    # the removed hexameter track is rejected with the reason, before any model load
    r = runner.invoke(_cli_app(), ["greek", "eval", "verse", "--track", "hexameter"])
    assert r.exit_code != 0
    assert "prose paraphrase" in r.output
    # verse has no --drift decomposition
    r = runner.invoke(_cli_app(), ["greek", "eval", "verse", "--drift"])
    assert r.exit_code != 0
    assert "no --drift" in r.output


# --- adversarial ------------------------------------------------------------------


def test_missing_asset_raises_clean_datanotavailable(monkeypatch, tmp_path: Path) -> None:
    def boom(name: str, **kw: object) -> Path:
        raise DataNotAvailableError(f"unknown dataset {name!r}")

    monkeypatch.setattr(data, "fetch", boom)
    monkeypatch.setattr(verse_eval, "cache_dir", lambda: tmp_path)  # force the cache miss
    with pytest.raises(DataNotAvailableError):
        verse_eval.evaluate_on_verse()


def test_verse_path_propagates_fetch_error(monkeypatch, tmp_path: Path) -> None:
    def boom(name: str, **kw: object) -> Path:
        raise DataNotAvailableError("no pinned URL")

    monkeypatch.setattr(data, "fetch", boom)
    monkeypatch.setattr(verse_eval, "cache_dir", lambda: tmp_path)
    with pytest.raises(DataNotAvailableError):
        verse_eval.verse_path()


def test_corrupt_gz_asset_refused_cleanly(monkeypatch, tmp_path: Path) -> None:
    bad = tmp_path / "verse-fold"
    bad.write_bytes(b"this is not gzip data")  # a corrupt/malformed asset

    monkeypatch.setattr(data, "fetch", lambda name, **kw: bad)
    monkeypatch.setattr(verse_eval, "cache_dir", lambda: tmp_path / "cache")
    # the fold asset is declared gzip (expect_gzip=True): a non-gzip body is refused, never
    # materialized as the fold
    with pytest.raises(DataNotAvailableError):
        verse_eval.verse_path()
