"""Regression: the OOV-lemma protection measures per-OOV-token lemma accuracy.

The model-selection gate names a "lemma@oov" protection, but its ``oov`` slice is
whole sentences that contain any OOV token, so the slice-summed lemma value was
dominated by those sentences' in-vocabulary tokens: a candidate could get every
OOV lemma wrong and still pass at the 0.0001 floor. The gate now protects
``lemma@oov-token``, read from the per-OOV-token band already in the error
anatomy. This measures the regression class the safeguard is named for.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

TRAINING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING))

import artifact_qualification as qualification  # noqa: E402
import model_selection as selection  # noqa: E402


def _report(oov_tokens: int, oov_lemma_correct: int) -> dict[str, Any]:
    # Two "oov"-slice sentences, each one OOV token plus nine in-vocabulary
    # tokens whose lemma is right, so the whole-sentence lemma over the slice is
    # a diluted 0.9. The per-OOV-token truth is oov_lemma_correct / oov_tokens.
    sentence = {
        "slice_ids": ["oov"],
        "metrics": {"lemma": {"value": 0.9, "numerator": 9, "denominator": 10}},
    }
    return {
        "metrics": {"lemma": {"value": 0.9, "numerator": 90, "denominator": 100}},
        "items": [dict(sentence), dict(sentence)],
        "error_anatomy": {
            "overall": {
                "frequency_bands": {
                    "oov": {
                        "tokens": oov_tokens,
                        "upos_correct": 0,
                        "lemma_correct": oov_lemma_correct,
                    }
                }
            }
        },
    }


def test_oov_token_reads_the_per_token_band_not_the_diluted_sentence_slice() -> None:
    report = _report(oov_tokens=2, oov_lemma_correct=0)
    # The old, diluted protection: whole-sentence lemma over OOV-containing sentences.
    assert selection._metric_value(report, "lemma", "oov") == 0.9
    # The fix: true per-OOV-token lemma accuracy (every OOV lemma is wrong here).
    assert selection._metric_value(report, "lemma", "oov-token") == 0.0
    # Both gate implementations agree.
    assert qualification._metric_value(report, "lemma", "oov-token") == 0.0


def test_oov_token_value_equals_the_band_ratio() -> None:
    report = _report(oov_tokens=8, oov_lemma_correct=6)
    assert selection._metric_value(report, "lemma", "oov-token") == 6 / 8
    assert qualification._metric_value(report, "lemma", "oov-token") == 6 / 8


def test_oov_token_is_unavailable_when_the_band_is_missing_or_empty() -> None:
    reports: list[dict[str, Any]] = [
        {"error_anatomy": {"overall": {"frequency_bands": {}}}},
        {"error_anatomy": {"overall": {"frequency_bands": {"oov": {"tokens": 0, "lemma_correct": 0}}}}},
        {"metrics": {}},  # no anatomy at all
    ]
    for report in reports:
        assert selection._metric_value(report, "lemma", "oov-token") is None
        assert qualification._metric_value(report, "lemma", "oov-token") is None


def test_default_selection_gate_protects_lemma_at_oov_token() -> None:
    gate = selection.load_gate(TRAINING / "model-selection-gate-v3.json")
    protected = {(entry["metric"], entry["slice"]) for entry in gate["protected_metrics"]}
    assert ("lemma", "oov-token") in protected
    assert ("lemma", "oov") not in protected
