"""Tests for the PapyGreek documentary-Koine dependency fold: the AGDT->UD build
converter (``scripts/build_papygreek_fold.py``), the `evaluate_on_papygreek` wiring, the
CLI target, and adversarial inputs.

The build converter is exercised on a hand-checked fixture tree (real bgu.1.261 sentence 2);
the evaluator wiring runs through a stubbed active model (the test_joint pattern) and skips
if the official conll18 evaluator is not cached (offline)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from aegean.data import DataNotAvailableError
from aegean.greek import joint, papygreek

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_papygreek_fold as bpf  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "papygreek" / "sample.conllu"


# --- the hand-checked converter (real bgu.1.261 sentence 2) -----------------------

# reg-layer word dicts, exactly as read off the PapyGreek <word> elements.
def _w(i, form, lemma, postag, rel, head):
    return {
        "id": str(i), "form_reg": form, "lemma_reg": lemma, "postag_reg": postag,
        "relation_reg": rel, "head_reg": str(head), "artificial": None,
        "insertion_id": None, "lang": "grc",
    }


_BGU_SENT2 = [
    _w(1, "γιγνώσκειν", "γιγνώσκω", "v--pna---", "OBJ", 3),
    _w(2, "σε", "σύ", "p2s----a-", "SBJ", 1),
    _w(3, "θέλω", "ἐθέλω", "v1spia---", "PRED", 0),
    _w(4, "ἐγὼ", "ἐγώ", "p1s---fn-", "SBJ_CO", 5),
    _w(5, "καὶ", "καί", "c--------", "COORD", 12),
    _w(6, "Οὐαλερία", "Οὐαλερία", "n-s---fn-", "SBJ_CO", 5),
    _w(7, ",", "punc1", "u--------", "AuxX", 8),
    _w(8, "ἐὰν", "ἐάν", "c--------", "AuxC", 12),
    _w(9, "Ἡροὶς", "Ἡροίς", "n-s---fn-", "SBJ", 10),
    _w(10, "τέκῃ", "τίκτω", "v3sasa---", "ADV", 8),
    _w(11, ",", "punc1", "u--------", "AuxX", 12),
    _w(12, "εὐχόμεθα", "εὔχομαι", "v1ppie---", "OBJ", 1),
    _w(13, "ἐλθεῖν", "ἔρχομαι", "v--ana---", "OBJ", 12),
    _w(14, "πρὸς", "πρός", "r--------", "AuxP", 13),
    _w(15, "σέ", "σύ", "p2s----a-", "OBJ", 14),
    _w(16, ".", "punc1", "u--------", "AuxK", 0),
]


def _rows(block: str) -> list[list[str]]:
    return [ln.split("\t") for ln in block.splitlines() if ln and not ln.startswith("#")]


def test_convert_tree_bgu_sentence_hand_checked() -> None:
    block, forms = bpf.sentence_to_conllu("papygreek:bgu.1.261@2", _BGU_SENT2)
    rows = _rows(block)
    assert len(rows) == 16
    assert all(len(r) == 10 for r in rows)  # CoNLL-U 10 columns
    # by-index: (form, upos, head, deprel) — the AGDT->UD structural conversions
    got = {int(r[0]): (r[1], r[3], r[6], r[7]) for r in rows}
    assert got[3] == ("θέλω", "VERB", "0", "root")          # PRED -> the single root
    # γιγνώσκειν is an infinitive OBJ carrying its own SBJ (σε) -> acc+inf -> ccomp
    assert got[1] == ("γιγνώσκειν", "VERB", "3", "ccomp")
    assert got[2] == ("σε", "PRON", "1", "nsubj")           # SBJ -> nsubj
    assert got[8] == ("ἐὰν", "SCONJ", "10", "mark")         # AuxC subordinator -> mark, SCONJ
    assert got[14] == ("πρὸς", "ADP", "15", "case")         # AuxP preposition -> case (promotes σέ)
    assert got[15] == ("σέ", "PRON", "13", "obl")
    assert got[5] == ("καὶ", "CCONJ", "4", "cc")            # COORD -> cc on the first conjunct
    assert got[6] == ("Οὐαλερία", "NOUN", "4", "conj")      # coordinand -> conj
    assert got[16] == (".", "PUNCT", "3", "punct")          # AuxK final punct -> attaches to root
    # exactly one root
    assert sum(1 for r in rows if r[6] == "0") == 1
    # punctuation lemma reconciled to the surface form (training convention, not "punc1")
    assert {int(r[0]): r[2] for r in rows}[16] == "."
    assert {int(r[0]): r[2] for r in rows}[7] == ","
    # a real lemma is cleaned (γιγνώσκειν -> γιγνώσκω)
    assert {int(r[0]): r[2] for r in rows}[1] == "γιγνώσκω"
    # FEATS rendered from the 9-place postag on the finite verb
    feats = {int(r[0]): r[5] for r in rows}
    assert feats[3] == "Mood=Ind|Number=Sing|Person=1|Tense=Pres|VerbForm=Fin|Voice=Act"
    assert forms[0] == "γιγνώσκειν"


# --- apparatus stripping ----------------------------------------------------------


def test_strip_apparatus_recovers_reading_text() -> None:
    assert bpf.strip_apparatus("Ἀμ[μ]ωνίῳ") == "Ἀμμωνίῳ"      # restoration kept
    assert bpf.strip_apparatus("εὐχαρι<σ>τῶμεν") == "εὐχαριστῶμεν"  # editorial addition kept
    assert bpf.strip_apparatus("(Αὐρ(ήλιος))") == "Αὐρήλιος"   # nested abbreviation expansion
    assert bpf.strip_apparatus("ἐνέγ|και") == "ἐνέγκαι"        # line break removed
    assert bpf.strip_apparatus("〚δεῖ〛") == ""                 # erasure removed entirely
    assert bpf.strip_apparatus("{μοι}") == ""                  # deletion removed
    assert bpf.strip_apparatus("ἐφ᾽") == "ἐφ᾽"                 # koronis/elision preserved


def test_is_clean_reading_rejects_illegibility_residue() -> None:
    assert bpf.is_clean_reading("Ἀμμωνίῳ")
    assert bpf.is_clean_reading("ἐφ᾽")
    assert not bpf.is_clean_reading("")
    # an illegibility marker (_.N) leaves a stray '.'/digit → not clean Greek
    assert not bpf.is_clean_reading(bpf.strip_apparatus("ἀπελυς_.2"))
    assert not bpf.is_clean_reading("abc")  # Latin is not Greek


# --- sentence selection -----------------------------------------------------------


def test_sentence_status_classifies_selection() -> None:
    ok = [_w(1, "θέλω", "ἐθέλω", "v1spia---", "PRED", 0)]
    assert bpf.sentence_status(ok) == "ok"
    assert bpf.sentence_status([]) == "empty"
    art = ok + [{"id": "2", "form_reg": "[0]", "lemma_reg": "-", "postag_reg": "v3s___---",
                 "relation_reg": "PRED", "head_reg": "0", "artificial": "elliptic",
                 "insertion_id": "x", "lang": ""}]
    assert bpf.sentence_status(art) == "artificial"
    partial = [_w(1, "θέλω", "ἐθέλω", "v1spia---", "PRED", 0),
               {"id": "2", "form_reg": "σε", "lemma_reg": "σύ", "postag_reg": "p2s----a-",
                "relation_reg": None, "head_reg": None, "artificial": None,
                "insertion_id": None, "lang": "grc"}]
    assert bpf.sentence_status(partial) == "partial"
    appar = [_w(1, "ἀπελυς_.2", "ἀπολύω", "v1spia---", "PRED", 0)]
    assert bpf.sentence_status(appar) == "apparatus"


# --- leakage helpers --------------------------------------------------------------


def test_leakage_form_tuple_exclusion() -> None:
    keys = {("θέλω", "σε"), ("ἔρρωσο",)}
    assert bpf.is_leaked(("θέλω", "σε"), keys)          # full match
    assert bpf.is_leaked(("ἔρρωσο", "."), keys)         # punct-stripped match
    assert not bpf.is_leaked(("καινός", "λόγος"), keys)


def test_training_form_keys_reads_jsonl(tmp_path: Path) -> None:
    (tmp_path / "full-train.jsonl").write_text(
        json.dumps({"tokens": ["θέλω", "σε", "."]}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    keys = bpf.training_form_keys(tmp_path)
    assert ("θέλω", "σε", ".") in keys           # full tuple
    assert ("θέλω", "σε") in keys                # punctuation-stripped tuple


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


def test_evaluate_on_papygreek_wires_through_official_evaluator(monkeypatch) -> None:
    _require_evaluator()
    monkeypatch.setattr(joint, "_ACTIVE", _StubModel())
    res = papygreek.evaluate_on_papygreek(source=FIXTURE)
    from aegean.greek.ud import load_conllu

    sents = load_conllu(FIXTURE)
    assert res["treebank"] == "papygreek" and res["split"] == "test"
    assert res["parsed"] is True
    assert res["n_sentences"] == len(sents) == 3
    assert res["n_words"] == sum(len(s.tokens) for s in sents)
    for key in ("upos", "xpos", "ufeats", "lemma", "uas", "las", "clas"):
        assert 0.0 <= res[key] <= 1.0
    # DET/PUNCT gold tokens all mislabeled NOUN by the stub → UPOS well under 1.0
    assert res["upos"] < 1.0


def test_evaluate_on_papygreek_parse_false_drops_uas(monkeypatch) -> None:
    _require_evaluator()
    monkeypatch.setattr(joint, "_ACTIVE", None)  # no parser active
    res = papygreek.evaluate_on_papygreek(source=FIXTURE, parse=False)
    assert res["parsed"] is False
    assert res["uas"] is None and res["las"] is None and res["clas"] is None
    assert 0.0 <= res["upos"] <= 1.0


# --- CLI target -------------------------------------------------------------------


def _cli_app():
    from aegean.cli import _build_app

    return _build_app()


def test_cli_papygreek_target_accepted_and_batch_forwarded(monkeypatch) -> None:
    from typer.testing import CliRunner

    seen: list[int | None] = []

    def fake_eval(*, progress: object = None, batch_size: int | None = None) -> dict[str, float]:
        seen.append(batch_size)
        return {"upos": 0.9, "lemma": 0.8, "uas": 0.7, "las": 0.6}

    monkeypatch.setattr("aegean.greek.evaluate_on_papygreek", fake_eval)
    monkeypatch.setattr("aegean.greek.use_neural_pipeline", lambda **kw: None)
    runner = CliRunner()
    r1 = runner.invoke(_cli_app(), ["greek", "eval", "papygreek", "--batch-size", "4", "--json"])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(_cli_app(), ["greek", "eval", "papygreek", "--json"])
    assert r2.exit_code == 0, r2.output
    # forwarded when given; the default invocation carries no batch_size at all
    assert seen == [4, None]


def test_cli_papygreek_rejects_drift_and_bad_batch(monkeypatch) -> None:
    from typer.testing import CliRunner

    monkeypatch.setattr("aegean.greek.use_neural_pipeline", lambda **kw: None)
    runner = CliRunner()
    r = runner.invoke(_cli_app(), ["greek", "eval", "papygreek", "--drift"])
    assert r.exit_code != 0
    assert "drift" in r.output.lower()
    r = runner.invoke(_cli_app(), ["greek", "eval", "papygreek", "--batch-size", "0"])
    assert r.exit_code != 0
    assert "--batch-size must be at least 1" in r.output


# --- adversarial ------------------------------------------------------------------


def test_missing_asset_raises_clean_datanotavailable(monkeypatch, tmp_path: Path) -> None:
    # unregistered/unfetchable asset: fetch raises, and the error must propagate cleanly
    # out of evaluate_on_papygreek (no source), never a swallowed/wrapped traceback
    def boom(name: str, **kw: object) -> Path:
        raise DataNotAvailableError(f"unknown dataset {name!r}")

    monkeypatch.setattr(papygreek, "fetch", boom)
    monkeypatch.setattr(papygreek, "cache_dir", lambda: tmp_path)  # force the cache miss
    with pytest.raises(DataNotAvailableError):
        papygreek.evaluate_on_papygreek()


def test_papygreek_path_propagates_fetch_error(monkeypatch, tmp_path: Path) -> None:
    def boom(name: str, **kw: object) -> Path:
        raise DataNotAvailableError("no pinned URL")

    monkeypatch.setattr(papygreek, "fetch", boom)
    monkeypatch.setattr(papygreek, "cache_dir", lambda: tmp_path)  # ensure the cache miss
    with pytest.raises(DataNotAvailableError):
        papygreek.papygreek_path()


def test_corrupt_gz_asset_raises_clean_oserror(monkeypatch, tmp_path: Path) -> None:
    bad = tmp_path / "papygreek-fold"
    bad.write_bytes(b"this is not gzip data")  # a corrupt/malformed asset

    monkeypatch.setattr(papygreek, "fetch", lambda name, **kw: bad)
    monkeypatch.setattr(papygreek, "cache_dir", lambda: tmp_path / "cache")
    with pytest.raises(OSError):  # gzip.BadGzipFile is an OSError — clean, not a raw traceback
        papygreek.papygreek_path()


def test_convert_tree_survives_dangling_head() -> None:
    # a malformed tree: a head referencing an id not in the sentence → converter must not
    # crash and must still emit a valid single-root CoNLL-U block
    words = [
        _w(1, "θέλω", "ἐθέλω", "v1spia---", "PRED", 0),
        _w(2, "σε", "σύ", "p2s----a-", "SBJ", 99),  # head 99 does not exist
    ]
    block, forms = bpf.sentence_to_conllu("bad@1", words)
    rows = _rows(block)
    assert len(rows) == 2
    assert sum(1 for r in rows if r[6] == "0") == 1  # exactly one root survives


def test_load_conllu_of_malformed_fold_is_lenient() -> None:
    # a malformed CoNLL-U (short/garbled token lines) must not crash the loader
    from aegean.greek.ud import load_conllu

    garbled = FIXTURE.parent / "_garbled.conllu"
    garbled.write_text(
        "# sent_id = x\n1\tθέλω\n2\tσε\tσύ\tPRON\t_\t_\t1\tnsubj\t_\t_\n\n",
        encoding="utf-8",
    )
    try:
        sents = load_conllu(garbled)
        assert len(sents) == 1  # the 1-column line is skipped, the valid one kept
        assert [t.form for t in sents[0].tokens] == ["σε"]
    finally:
        garbled.unlink()
