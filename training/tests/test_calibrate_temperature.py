"""Offline tests for training/calibrate_temperature.py collector and dev-only default."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

np = pytest.importorskip("numpy")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "training") not in sys.path:
    sys.path.insert(0, str(ROOT / "training"))

import calibrate_temperature  # noqa: E402
from aegean.greek import joint  # noqa: E402


def _make_sentence(items: list[tuple[str, str, str]]) -> Any:
    return SimpleNamespace(
        tokens=[
            SimpleNamespace(form=form, upos=upos, lemma=lemma)
            for form, upos, lemma in items
        ]
    )


def _stub_model() -> tuple[Any, dict[str, int]]:
    """Controllable _JointModel covering lookup, edit-script, and identity lemma routes."""
    m = object.__new__(joint._JointModel)
    m._np = np
    m.inv = {"upos": {0: "NOUN", 1: "VERB", 2: "ADJ"}}
    # Tree 0: replaces whole stem "λόγον" -> "λόγος" (non-identity edit script)
    # Tree 1: identity script (empty edits -> falls through to identity fallback)
    m.trees = [
        ["sub", "λόγος"],
        ["keep"],
    ]
    m.lookup_form_upos = {"ἀρχῇ|NOUN": "ἀρχή"}
    m.lookup_form = {}
    m.lookup_lower = {}
    m._sess = SimpleNamespace(get_providers=lambda: ["CPUExecutionProvider"])

    calls = {"run": 0, "run_batch": 0}

    def fake_run(words: list[str]) -> dict[str, Any]:
        calls["run"] += 1
        nw = len(words)
        seq = nw + 2
        upos = np.full((1, seq, 3), -5.0, dtype=np.float64)
        lem = np.full((1, nw, 2), -5.0, dtype=np.float64)
        for i, w in enumerate(words):
            upos[0, i + 1, 0] = 5.0  # NOUN
            if w == "λόγον":
                lem[0, i, 0] = 4.0  # script 0 -> edit_script ("λόγος")
            else:
                lem[0, i, 1] = 4.0  # script 1 -> identity (lookup overrides for "ἀρχῇ")
        return {
            "upos": upos,
            "lemma": lem,
            "_word_pos": [i + 1 for i in range(nw)],
            "_kept": list(range(nw)),
        }

    def fake_run_batch(batch: list[list[str]]) -> list[dict[str, Any]]:
        calls["run_batch"] += 1
        return [fake_run(words) for words in batch]

    m._run = fake_run  # type: ignore[method-assign]
    m._run_batch = fake_run_batch  # type: ignore[method-assign]
    return m, calls


def test_collect_unpacks_three_tuple_preserves_routes_and_uses_sequential_default() -> None:
    model, calls = _stub_model()
    sent = _make_sentence([
        ("ἀρχῇ", "NOUN", "ἀρχή"),     # neural_lookup -> correct
        ("λόγον", "NOUN", "λόγος"),   # neural_edit   -> correct
        ("ἄγνωστον", "NOUN", "ἄγνωστος"),  # identity -> incorrect
    ])

    data = calibrate_temperature._collect(
        model,
        [sent],
        need_lemma_grid=True,
        lemma_temp=None,
        tag="dev/unit",
    )

    assert calls["run"] == 1
    assert calls["run_batch"] == 0
    assert data["n_tokens"] == 3
    assert data["lemma_sources"] == ["neural_lookup", "neural_edit", "identity"]
    assert data["lemma_correct"].tolist() == [1, 1, 0]
    assert data["upos_correct"].tolist() == [1, 1, 1]
    assert data["lemma_conf_grid"].shape == (3, len(calibrate_temperature._LEMMA_GRID))


def test_main_defaults_to_dev_only_and_sequential_without_opening_locked_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, calls = _stub_model()
    dev_sentences = [
        _make_sentence([
            ("ἀρχῇ", "NOUN", "ἀρχή"),
            ("λόγον", "NOUN", "λόγος"),
            ("ἄγνωστον", "NOUN", "ἄγνωστος"),
        ]),
        _make_sentence([
            ("ἀρχῇ", "VERB", "ἀρχή"),  # wrong UPOS to give non-degenerate fit
        ]),
    ]
    opened_splits: list[tuple[str, str]] = []

    def fake_ud_path(treebank: str, split: str) -> Path:
        opened_splits.append((treebank, split))
        if split == "test":
            raise AssertionError("locked test fold must not be opened without --include-locked-test")
        return tmp_path / f"{treebank}-{split}.conllu"

    monkeypatch.setattr(calibrate_temperature, "fetch", lambda _name: tmp_path)
    monkeypatch.setattr(calibrate_temperature, "_JointModel", lambda _dir: model)
    monkeypatch.setattr(calibrate_temperature, "ud_path", fake_ud_path)
    monkeypatch.setattr(calibrate_temperature, "load_conllu", lambda _path: dev_sentences)

    out_path = tmp_path / "cal-dev.json"
    calibrate_temperature.main(["--out", str(out_path)])

    assert opened_splits == [("perseus", "dev")]
    assert calls["run"] == 2
    assert calls["run_batch"] == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "test" not in payload
    assert payload["protocol"]["batch_size"] is None
    assert payload["protocol"]["include_locked_test"] is False
    assert set(payload["dev"]["lemma"]["by_source_after"]) == {
        "neural_lookup",
        "neural_edit",
        "identity",
    }
