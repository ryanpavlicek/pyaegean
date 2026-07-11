"""Tests for the DBBE Byzantine book-epigram tagging-fold evaluation wiring: the
`aegean.greek.evaluate_on_dbbe` / `dbbe_path` entry points, the `aegean greek eval dbbe`
CLI target, the ``--layer`` flag on `eval papygreek`, and adversarial inputs.

The scorer wiring runs through a stubbed active model (the test_joint / test_papygreek
pattern) on a hand-built two-sentence CoNLL-U fixture, and skips if the official conll18
evaluator is not cached (offline). The DBBE builder itself is covered by test_fix_dbbe.py;
this file covers the eval/CLI surface the fold plugs into.

Plain-module test: imports only the stdlib, pytest, and the installed ``aegean`` package."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegean import data
from aegean.data import DataNotAvailableError
from aegean.greek import dbbe, joint


# --- a tiny tagging fold fixture (no trees needed: parse is forced False) ----------


def _write_fold(path: Path) -> Path:
    # Two sentences of gold tagging: a noun, a coordinator, a verb, and punctuation. The stub
    # model tags everything NOUN, so UPOS is well under 1.0 and CCONJ/PUNCT/VERB are misses.
    path.write_text(
        "# sent_id = dbbe:lingann@0\n"
        "1\tλόγος\tλόγος\tNOUN\tn-s---mn-\tCase=Nom|Gender=Masc|Number=Sing\t0\troot\t_\t_\n"
        "2\tκαὶ\tκαί\tCCONJ\tc--------\t_\t1\tcc\t_\t_\n"
        "3\t·\t·\tPUNCT\tu--------\t_\t1\tpunct\t_\t_\n"
        "\n"
        "# sent_id = dbbe:lingann@1\n"
        "1\tλάμπει\tλάμπω\tVERB\tv3spia---\tMood=Ind|Number=Sing|Person=3|Tense=Pres|VerbForm=Fin|Voice=Act\t0\troot\t_\t_\n"
        "2\tφῶς\tφῶς\tNOUN\tn-s---na-\tCase=Nom|Gender=Neut|Number=Sing\t1\tnsubj\t_\t_\n"
        "\n",
        encoding="utf-8",
    )
    return path


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


# --- evaluate_on_dbbe is tagging-only (no UAS/LAS/CLAS) ----------------------------


def test_evaluate_on_dbbe_reports_tagging_metrics_only(monkeypatch, tmp_path: Path) -> None:
    _require_evaluator()
    fold = _write_fold(tmp_path / "dbbe.conllu")
    monkeypatch.setattr(joint, "_ACTIVE", _StubModel())
    res = dbbe.evaluate_on_dbbe(source=fold)

    from aegean.greek.ud import load_conllu

    sents = load_conllu(fold)
    assert res["treebank"] == "dbbe" and res["split"] == "test"
    # tagging-only: parse forced False, so the parse metrics are None (not a number)
    assert res["parsed"] is False
    assert res["uas"] is None and res["las"] is None and res["clas"] is None
    # the tagging metrics are real accuracies in range
    for key in ("upos", "xpos", "ufeats", "lemma"):
        assert 0.0 <= res[key] <= 1.0
    # CCONJ/PUNCT/VERB gold tokens all mislabeled NOUN by the stub → UPOS under 1.0
    assert res["upos"] < 1.0
    assert res["n_sentences"] == len(sents) == 2
    assert res["n_words"] == sum(len(s.tokens) for s in sents) == 5


def test_evaluate_on_dbbe_batch_matches_sequential(monkeypatch, tmp_path: Path) -> None:
    # batch_size is a throughput convenience; on the stub it must not change the scores.
    _require_evaluator()
    fold = _write_fold(tmp_path / "dbbe.conllu")
    monkeypatch.setattr(joint, "_ACTIVE", _StubModel())

    class _BatchStub(_StubModel):
        def analyze_batch(self, chunk: list[list[str]]) -> list[joint.SentenceAnalysis]:
            return [self.analyze(forms) for forms in chunk]

    seq = dbbe.evaluate_on_dbbe(source=fold)
    monkeypatch.setattr(joint, "_ACTIVE", _BatchStub())
    bat = dbbe.evaluate_on_dbbe(source=fold, batch_size=2)
    for key in ("upos", "xpos", "ufeats", "lemma"):
        assert seq[key] == bat[key]


# --- dbbe_path fetch mechanics ----------------------------------------------------


def test_dbbe_path_fetches_the_dbbe_asset(monkeypatch, tmp_path: Path) -> None:
    seen: list[tuple[str, bool | None]] = []

    def fake_fetch_text(name: str, dest: Path, **kw: object) -> Path:
        seen.append((name, kw.get("expect_gzip")))  # type: ignore[arg-type]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("# sent_id = x\n1\tα\tα\tNOUN\tn\t_\t0\troot\t_\t_\n\n", encoding="utf-8")
        return dest

    monkeypatch.setattr(data, "fetch_text", fake_fetch_text)
    monkeypatch.setattr(dbbe, "cache_dir", lambda: tmp_path)
    p = dbbe.dbbe_path()
    # fetched the right asset, declared it gzip, and landed at the register-specific name
    assert seen == [("dbbe-lingann-fold", True)]
    assert p.name == "dbbe-lingann-test.conllu"


def test_dbbe_path_propagates_fetch_error(monkeypatch, tmp_path: Path) -> None:
    def boom(name: str, **kw: object) -> Path:
        raise DataNotAvailableError("no pinned URL")

    monkeypatch.setattr(data, "fetch", boom)
    monkeypatch.setattr(dbbe, "cache_dir", lambda: tmp_path)
    with pytest.raises(DataNotAvailableError):
        dbbe.dbbe_path()


def test_corrupt_gz_asset_refused_cleanly(monkeypatch, tmp_path: Path) -> None:
    bad = tmp_path / "dbbe-lingann-fold"
    bad.write_bytes(b"this is not gzip data")  # a corrupt/malformed asset

    monkeypatch.setattr(data, "fetch", lambda name, **kw: bad)
    monkeypatch.setattr(dbbe, "cache_dir", lambda: tmp_path / "cache")
    # the fold asset is declared gzip (expect_gzip=True), so a non-gzip body is refused with
    # the clean data error, never materialized as the fold
    with pytest.raises(DataNotAvailableError):
        dbbe.dbbe_path()


def test_missing_asset_raises_clean_datanotavailable(monkeypatch, tmp_path: Path) -> None:
    def boom(name: str, **kw: object) -> Path:
        raise DataNotAvailableError(f"unknown dataset {name!r}")

    monkeypatch.setattr(data, "fetch", boom)
    monkeypatch.setattr(dbbe, "cache_dir", lambda: tmp_path)
    with pytest.raises(DataNotAvailableError):
        dbbe.evaluate_on_dbbe()


# --- CLI target -------------------------------------------------------------------


def _cli_app():
    from aegean.cli import _build_app

    return _build_app()


def test_cli_dbbe_target_accepted_and_batch_forwarded(monkeypatch) -> None:
    from typer.testing import CliRunner

    seen: list[int | None] = []

    def fake_eval(*, progress: object = None, batch_size: int | None = None) -> dict[str, object]:
        seen.append(batch_size)
        return {"upos": 0.5, "xpos": 0.4, "ufeats": 0.4, "lemma": 0.6,
                "uas": None, "las": None, "clas": None}

    monkeypatch.setattr("aegean.greek.evaluate_on_dbbe", fake_eval)
    monkeypatch.setattr("aegean.greek.use_neural_pipeline", lambda **kw: None)
    runner = CliRunner()
    r1 = runner.invoke(_cli_app(), ["greek", "eval", "dbbe", "--batch-size", "4", "--json"])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(_cli_app(), ["greek", "eval", "dbbe", "--json"])
    assert r2.exit_code == 0, r2.output
    # forwarded when given; the default invocation carries no batch_size at all
    assert seen == [4, None]


def test_cli_dbbe_rejects_drift_bygenre_bootstrap(monkeypatch) -> None:
    from typer.testing import CliRunner

    monkeypatch.setattr("aegean.greek.use_neural_pipeline", lambda **kw: None)
    runner = CliRunner()
    for flag in ("--drift", "--by-genre", "--bootstrap"):
        r = runner.invoke(_cli_app(), ["greek", "eval", "dbbe", flag])
        assert r.exit_code != 0, f"{flag} should be rejected: {r.output}"
        assert "tagging-only" in r.output


def test_cli_dbbe_rejects_bad_batch(monkeypatch) -> None:
    from typer.testing import CliRunner

    monkeypatch.setattr("aegean.greek.use_neural_pipeline", lambda **kw: None)
    runner = CliRunner()
    r = runner.invoke(_cli_app(), ["greek", "eval", "dbbe", "--batch-size", "0"])
    assert r.exit_code != 0
    assert "--batch-size must be at least 1" in r.output


# --- the --layer flag on eval papygreek -------------------------------------------


def test_cli_papygreek_layer_threads_through(monkeypatch) -> None:
    from typer.testing import CliRunner

    seen: list[str | None] = []

    def fake_eval(*, layer: str = "reg", progress: object = None,
                  batch_size: int | None = None) -> dict[str, object]:
        seen.append(layer)
        return {"upos": 0.9, "lemma": 0.8, "uas": 0.7, "las": 0.6, "layer": layer}

    monkeypatch.setattr("aegean.greek.evaluate_on_papygreek", fake_eval)
    monkeypatch.setattr("aegean.greek.use_neural_pipeline", lambda **kw: None)
    runner = CliRunner()
    r = runner.invoke(_cli_app(), ["greek", "eval", "papygreek", "--layer", "orig", "--json"])
    assert r.exit_code == 0, r.output
    assert seen == ["orig"]


def test_cli_papygreek_default_layer_call_stays_reg(monkeypatch) -> None:
    # the default (reg) invocation must NOT pass layer= at all, so it stays byte-identical to
    # the recorded protocol's call — a fake that rejects an unexpected layer kwarg confirms it.
    from typer.testing import CliRunner

    seen: list[bool] = []

    def fake_eval(*, progress: object = None, batch_size: int | None = None) -> dict[str, object]:
        seen.append(True)
        return {"upos": 0.9, "lemma": 0.8, "uas": 0.7, "las": 0.6}

    monkeypatch.setattr("aegean.greek.evaluate_on_papygreek", fake_eval)
    monkeypatch.setattr("aegean.greek.use_neural_pipeline", lambda **kw: None)
    runner = CliRunner()
    r = runner.invoke(_cli_app(), ["greek", "eval", "papygreek", "--json"])
    assert r.exit_code == 0, r.output
    assert seen == [True]


def test_cli_layer_guards(monkeypatch) -> None:
    from typer.testing import CliRunner

    monkeypatch.setattr("aegean.greek.use_neural_pipeline", lambda **kw: None)
    runner = CliRunner()
    # a bogus layer value is rejected
    r = runner.invoke(_cli_app(), ["greek", "eval", "papygreek", "--layer", "diplomatic"])
    assert r.exit_code != 0
    assert "--layer must be reg or orig" in r.output
    # --layer orig only applies to papygreek
    r = runner.invoke(_cli_app(), ["greek", "eval", "ud", "--layer", "orig"])
    assert r.exit_code != 0
    assert "--layer applies to" in r.output
    # --layer orig does not combine with --drift (the drift decomposition is the reg reproduction)
    r = runner.invoke(_cli_app(), ["greek", "eval", "papygreek", "--layer", "orig", "--drift"])
    assert r.exit_code != 0
    assert "does not combine with --drift" in r.output


# --- plain-module import (no heavy deps at import time) ----------------------------


def test_dbbe_module_imports_and_exports() -> None:
    from aegean.greek import dbbe as mod

    assert mod.__all__ == ["dbbe_path", "evaluate_on_dbbe"]
    from aegean import greek

    assert greek.evaluate_on_dbbe is mod.evaluate_on_dbbe
    assert greek.dbbe_path is mod.dbbe_path
    # the papygreek orig entry point is exported alongside
    assert hasattr(greek, "papygreek_orig_path")
