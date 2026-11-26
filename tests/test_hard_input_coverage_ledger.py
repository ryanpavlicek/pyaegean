"""Regression checks for the deterministic Hard-Input Scholarly Coverage Ledger."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "scripts" / "build_hard_input_ledger.py"
_LEDGER = _ROOT / "training" / "results" / "hard-input-coverage-ledger-v1.json"


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_hard_input_ledger", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hard_input_ledger_matches_checked_in_json() -> None:
    assert _LEDGER.is_file(), f"missing checked-in ledger at {_LEDGER}"
    checked_in = json.loads(_LEDGER.read_text(encoding="utf-8"))
    live = _load_builder().build_ledger()
    assert live == checked_in


def test_hard_input_ledger_invariants_and_honesty_controls() -> None:
    data = json.loads(_LEDGER.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1"
    assert data["locked_folds_used"] is False

    summary = data["summary"]
    assert summary["ocr_cases"] == 4
    assert summary["cypriot_bridge_read_tokens"] == 100
    assert summary["cypriot_bridge_word_tokens"] == 572
    assert summary["sandhi_resolved"] == 3
    assert summary["sandhi_total"] == 4
    assert summary["dialect_cohorts"] == 5
    assert summary["attested_verse_scanned"] == 7
    assert summary["attested_verse_total"] == 7
    assert summary["prose_negative_control_rejected"] is True

    # OCR lenient mode must repair both Latin lookalikes and Beta-Code remnants with warnings.
    ocr_repair = data["cohorts"]["ocr_and_lunate"][0]
    assert ocr_repair["id"] == "ocr_latin_and_betacode_repair"
    assert ocr_repair["normalized"] == "Ἐν ἀρχῇ ἦν ὁ Λόγος, βασιλευς"
    assert len(ocr_repair["repair_warnings"]) == 2

    # EpiDoc XML Leiden control must preserve restored and unclear statuses.
    epidoc_tokens = data["cohorts"]["leiden_damage_restoration"]["epidoc_xml_apparatus_control"]["tokens"]
    statuses = {t["text"]: t["status"] for t in epidoc_tokens}
    assert statuses["ἔδοξεν"] == "certain"
    assert statuses["βουλῇ"] == "restored"
    assert statuses["καὶ"] == "unclear"

    # Explicit conservative abstention on unlisted crasis form must remain honest.
    crasis = {c["form"]: c for c in data["cohorts"]["spelling_variation_and_crasis"]["crasis"]}
    assert crasis["κἀγὼ"]["resolved"] == ["καί", "ἐγώ"]
    assert crasis["τἀγαθά"]["resolved"] == []
    assert crasis["τἀγαθά"]["uncertain"] is True

    # Unevaluated gaps must stay explicit and non-empty.
    gaps = data["unevaluated_gaps"]
    assert len(gaps) == 4
    assert all(g["status"] == "unevaluated" and g["reason"] for g in gaps)
