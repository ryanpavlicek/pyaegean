"""The PapyGreek ORIG (diplomatic) surface-layer fold: the ``--layer orig`` build mode of
``scripts/build_papygreek_fold.py`` and the `evaluate_on_papygreek(layer="orig")` entry point.

The orig fold keeps the SAME sentences and the SAME gold columns as the reg fold and swaps
only the emitted FORM to the raw documentary orthography (itacism, phonetic spelling). These
tests pin the two invariants that make the orig row comparable to the reg row — the default
(reg) build stays byte-identical, and the orig overlay is a pure column-2 swap — plus the
surface-disposition accounting, the mandatory orig leakage recheck, and the eval wiring.

Correctness is verified against outputs known by construction (a hand-built two-layer treebank
fixture); the eval wiring runs through a stubbed active model (the test_joint pattern) and
skips if the official conll18 evaluator is not cached (offline)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from aegean import data
from aegean.greek import joint, papygreek

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_papygreek_fold as bpf  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "papygreek" / "sample.conllu"


# --- a two-layer word dict (both orig_form and the reg keys) ----------------------


def _w(i, orig_form, form_reg, lemma, postag, rel, head):
    return {
        "id": str(i), "orig_form": orig_form,
        "form_reg": form_reg, "lemma_reg": lemma, "postag_reg": postag,
        "relation_reg": rel, "head_reg": str(head), "artificial": None,
        "insertion_id": None, "lang": "grc",
    }


# γεινώσκειν/γιγνώσκειν = itacistic diplomatic spelling; θέλω identical; '.' punctuation.
_SENT = [
    _w(1, "γεινώσκειν", "γιγνώσκειν", "γιγνώσκω", "v--pna---", "OBJ", 2),
    _w(2, "θέλω", "θέλω", "ἐθέλω", "v1spia---", "PRED", 0),
    _w(3, ".", ".", "punc1", "u--------", "AuxK", 0),
]


def _rows(block: str) -> list[list[str]]:
    return [ln.split("\t") for ln in block.splitlines() if ln and not ln.startswith("#")]


def _text_line(block: str) -> str:
    return next(ln for ln in block.splitlines() if ln.startswith("# text"))


# --- byte-identity of the default (reg) path --------------------------------------


def test_default_build_byte_identical_to_no_surface() -> None:
    # surface_forms=None (the default) must be byte-for-byte the reg build: adding the orig
    # overlay parameter cannot perturb the shipped reg fold.
    a, af = bpf.sentence_to_conllu("papygreek:x@1", _SENT)
    b, bf = bpf.sentence_to_conllu("papygreek:x@1", _SENT, surface_forms=None)
    assert a == b
    assert af == bf
    # column 2 (FORM) is the reg reading, not the diplomatic one
    assert [r[1] for r in _rows(a)] == ["γιγνώσκειν", "θέλω", "."]
    assert af == ("γιγνώσκειν", "θέλω", ".")


# --- the per-token diplomatic-reading disposition helper --------------------------


def test_orig_token_reading_dispositions() -> None:
    # a genuine diplomatic spelling unlike reg
    assert bpf.orig_token_reading("γεινώσκειν", "γιγνώσκειν", is_punct=False) == (
        "γεινώσκειν", "diplomatic_diff",
    )
    # the diplomatic reading equals reg (no phonetic divergence)
    assert bpf.orig_token_reading("θέλω", "θέλω", is_punct=False) == ("θέλω", "diplomatic_same")
    # apparatus in the orig form is stripped the same way (restoration kept)
    assert bpf.orig_token_reading("Ἀμ[μ]ωνίῳ", "Ἀμμωνίῳ", is_punct=False) == (
        "Ἀμμωνίῳ", "diplomatic_same",
    )
    # a fully-lost diplomatic reading ('$') cannot be recovered → falls back to reg, counted
    assert bpf.orig_token_reading("$", "τοὺς", is_punct=False) == ("τοὺς", "fallback_unclean")
    # an illegibility residue that strips to non-Greek → fallback
    read, disp = bpf.orig_token_reading("ἀ✕πὸ", "ἀπὸ", is_punct=False)
    assert read == "ἀπὸ" and disp == "fallback_unclean"
    # punctuation: layer-invariant here
    assert bpf.orig_token_reading(".", ".", is_punct=True) == (".", "punct")
    # an empty diplomatic form → fallback to the reg reading
    assert bpf.orig_token_reading("", "τοὺς", is_punct=False) == ("τοὺς", "fallback_empty")


# --- the overlay is a PURE form swap (the comparability invariant) -----------------


def test_orig_overlay_swaps_only_the_form_column() -> None:
    reg_block, _ = bpf.sentence_to_conllu("papygreek:x@1", _SENT)
    surface = ["γεινώσκειν", "θέλω", "."]  # the diplomatic readings
    orig_block, orig_forms = bpf.sentence_to_conllu(
        "papygreek:x@1", _SENT, surface_forms=surface,
    )
    reg_rows, orig_rows = _rows(reg_block), _rows(orig_block)
    assert len(reg_rows) == len(orig_rows) == 3
    for rr, orr in zip(reg_rows, orig_rows):
        # EVERY column except FORM (index 1) is identical — same gold analysis
        assert [rr[0]] + rr[2:] == [orr[0]] + orr[2:]
    # only the FORM differs, exactly where the diplomatic spelling diverges
    assert [r[1] for r in orig_rows] == ["γεινώσκειν", "θέλω", "."]
    assert orig_forms == ("γεινώσκειν", "θέλω", ".")
    # the gold LEMMA of the diplomatic word is still the regularized lemma (γιγνώσκω)
    assert orig_rows[0][2] == "γιγνώσκω"
    # the # text header carries the diplomatic reading
    assert "γεινώσκειν" in _text_line(orig_block)
    assert "γεινώσκειν" not in _text_line(reg_block)


# --- the whole build path on a two-layer fixture repo -----------------------------


def _write_treebank(path: Path, sentences: list[str]) -> None:
    body = "\n".join(sentences)
    path.write_text(f"<treebank>\n{body}\n</treebank>\n", encoding="utf-8")


def _sentence_xml(sid: str, words: list[dict[str, str]]) -> str:
    ws = []
    for w in words:
        attrs = " ".join(f'{k}="{v}"' for k, v in w.items())
        ws.append(f"    <word {attrs}/>")
    return f'  <sentence id="{sid}">\n' + "\n".join(ws) + "\n  </sentence>"


def _xw(i, orig_form, form_reg, lemma, postag, rel, head):
    return {
        "id": str(i), "orig_form": orig_form, "form_reg": form_reg,
        "lemma_reg": lemma, "postag_reg": postag, "relation_reg": rel,
        "head_reg": str(head), "lang": "grc",
    }


def _build_fixture_repo(tmp_path: Path) -> Path:
    docdir = tmp_path / "documentary" / "test"
    docdir.mkdir(parents=True)
    s1 = _sentence_xml("1", [
        _xw(1, "γεινώσκειν", "γιγνώσκειν", "γιγνώσκω", "v--pna---", "OBJ", 2),
        _xw(2, "θέλω", "θέλω", "ἐθέλω", "v1spia---", "PRED", 0),
        _xw(3, ".", ".", "punc1", "u--------", "AuxK", 0),
    ])
    s2 = _sentence_xml("2", [
        _xw(1, "$", "τοὺς", "ὁ", "l-p---ma-", "OBJ", 2),  # lost diplomatic → fallback
        _xw(2, "ἔπεμψα", "ἔπεμψα", "πέμπω", "v1saia---", "PRED", 0),
    ])
    _write_treebank(docdir / "test.xml", [s1, s2])
    return tmp_path


def test_build_orig_same_selection_form_only_diff(tmp_path: Path) -> None:
    repo = _build_fixture_repo(tmp_path)
    training = tmp_path / "training"  # empty → no leakage keys
    training.mkdir()

    reg_conllu, reg_manifest = bpf.build(repo, training, layer="reg")
    orig_conllu, orig_manifest = bpf.build(repo, training, layer="orig")

    # same sentence selection: same sentence and token counts
    assert reg_manifest["sentences_kept"] == orig_manifest["sentences_kept"] == 2
    assert reg_manifest["tokens_kept"] == orig_manifest["tokens_kept"] == 5

    # the orig manifest's disposition accounting sums to every token
    disp = orig_manifest["surface_disposition"]
    assert sum(disp.values()) == 5
    assert disp["diplomatic_diff"] == 1        # γεινώσκειν
    assert disp["diplomatic_same"] == 2        # θέλω, ἔπεμψα
    assert disp["punct"] == 1                  # .
    assert disp["fallback_unclean"] == 1       # $ → τοὺς
    assert orig_manifest["tokens_diplomatic_differ_from_reg"] == 1
    assert orig_manifest["orig_leakage_rechecked_and_dropped"] == 0
    assert orig_manifest["layer"].startswith("orig")

    # the two folds differ ONLY in the FORM column and the # text header
    reg_lines = reg_conllu.splitlines()
    orig_lines = orig_conllu.splitlines()
    assert len(reg_lines) == len(orig_lines)
    non_form_diffs = 0
    form_diffs = 0
    for lr, lo in zip(reg_lines, orig_lines):
        if lr.startswith("#") or not lr.strip():
            assert lr.startswith("# text") or lr == lo  # sent_id/blank identical
            continue
        cr, co = lr.split("\t"), lo.split("\t")
        if [cr[0]] + cr[2:] != [co[0]] + co[2:]:
            non_form_diffs += 1
        if cr[1] != co[1]:
            form_diffs += 1
    assert non_form_diffs == 0     # pure form swap
    assert form_diffs == 1         # only γεινώσκειν
    # the fallback token emits the reg reading in the orig fold (τοὺς, not $)
    assert "τοὺς" in orig_conllu and "$" not in orig_conllu


def test_build_orig_leakage_recheck_drops_orig_only_leak(tmp_path: Path) -> None:
    # a sentence that passes the reg leakage check but whose ORIG form tuple is in the training
    # keys must be dropped by the mandatory orig recheck (and only that sentence).
    repo = _build_fixture_repo(tmp_path)
    training = tmp_path / "training"
    training.mkdir()
    # the ORIG tuple of sentence 1 is ("γεινώσκειν","θέλω","."); its reg tuple differs
    # ("γιγνώσκειν",...), so reg selection keeps it but orig leakage must drop it.
    (training / "full-train.jsonl").write_text(
        json.dumps({"tokens": ["γεινώσκειν", "θέλω", "."]}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _, reg_manifest = bpf.build(repo, training, layer="reg")
    orig_conllu, orig_manifest = bpf.build(repo, training, layer="orig")

    # reg keeps both sentences (its tuple is not in the keys)
    assert reg_manifest["sentences_kept"] == 2
    assert reg_manifest["excluded"].get("leaked", 0) == 0
    # orig drops sentence 1 via the recheck
    assert orig_manifest["orig_leakage_rechecked_and_dropped"] == 1
    assert orig_manifest["sentences_kept"] == 1
    assert any("@1" in sid for sid in orig_manifest["orig_leaked_sent_ids"])
    # the surviving orig sentence is sentence 2 (ἔπεμψα)
    assert "ἔπεμψα" in orig_conllu and "γεινώσκειν" not in orig_conllu


def test_build_rejects_bad_layer(tmp_path: Path) -> None:
    repo = _build_fixture_repo(tmp_path)
    training = tmp_path / "training"
    training.mkdir()
    with pytest.raises(ValueError, match="layer must be"):
        bpf.build(repo, training, layer="bogus")


# --- the evaluate_on_papygreek(layer=...) entry point ------------------------------


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


def test_evaluate_on_papygreek_orig_layer_scores_and_labels(monkeypatch) -> None:
    _require_evaluator()
    monkeypatch.setattr(joint, "_ACTIVE", _StubModel())
    res = papygreek.evaluate_on_papygreek(layer="orig", source=FIXTURE)
    assert res["treebank"] == "papygreek"
    assert res["layer"] == "orig"
    for key in ("upos", "xpos", "ufeats", "lemma", "uas", "las", "clas"):
        assert 0.0 <= res[key] <= 1.0
    # the default layer still labels reg
    res_reg = papygreek.evaluate_on_papygreek(source=FIXTURE)
    assert res_reg["layer"] == "reg"


def test_evaluate_on_papygreek_rejects_bad_layer() -> None:
    with pytest.raises(ValueError, match="layer must be"):
        papygreek.evaluate_on_papygreek(layer="diplomatic")


def test_papygreek_orig_path_fetches_the_orig_asset(monkeypatch, tmp_path: Path) -> None:
    # layer='orig' with no source must fetch the papygreek-fold-orig asset (not the reg fold).
    seen: list[str] = []

    def fake_fetch_conllu(asset: str, dest: Path, *, download: bool) -> Path:
        seen.append(asset)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("# sent_id = x\n1\tα\tα\tNOUN\tn\t_\t0\troot\t_\t_\n\n", encoding="utf-8")
        return dest

    monkeypatch.setattr(papygreek, "_fetch_conllu", fake_fetch_conllu)
    monkeypatch.setattr(papygreek, "cache_dir", lambda: tmp_path)
    p = papygreek.papygreek_orig_path()
    assert seen == ["papygreek-fold-orig"]
    assert p.name == "papygreek-test-orig.conllu"


def test_orig_path_propagates_fetch_error(monkeypatch, tmp_path: Path) -> None:
    from aegean.data import DataNotAvailableError

    def boom(name: str, **kw: object) -> Path:
        raise DataNotAvailableError("no pinned URL")

    monkeypatch.setattr(data, "fetch", boom)
    monkeypatch.setattr(papygreek, "cache_dir", lambda: tmp_path)
    with pytest.raises(DataNotAvailableError):
        papygreek.papygreek_orig_path()
