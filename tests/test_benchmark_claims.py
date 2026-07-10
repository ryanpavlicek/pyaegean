"""The published benchmark numbers stay pinned to their evidence registry.

Every measured figure in docs/benchmarks.md (and its README / wiki echoes) must match
training/results/published-claims.json, the single canonical registry. This makes number
drift a test failure instead of a silent divergence: editing a doc number without
re-measuring (or re-measuring without updating the docs) fails here. The registry itself
is checked against reality by ``scripts/check_benchmarks.py --measure`` (weekly CI + the
pre-cut gate), which re-runs the offline-stack rows; the neural rows are pinned by the
immutable sha256 release asset and the training/results evidence files.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _claims() -> dict:
    return json.loads((ROOT / "training/results/published-claims.json").read_text(encoding="utf-8"))


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_registry_agrees_with_the_remeasure_evidence() -> None:
    """Every neural accuracy row must equal the newest full-protocol evidence file
    (the 2026-07-09 re-measure, taken with the 0.32.0 lemma-composition fix). The v3
    quantize report stays as the historical record backing the size claims; its
    accuracy cells reflect the 2026-06 evaluation path and are superseded."""
    claims = _claims()
    rem = json.loads(_read("training/results/lemma-remeasure-2026-07-09.json"))
    res = rem["results_full_precision"]
    row = claims["neural_ud_perseus_test"]
    for metric in ("lemma", "uas", "las", "upos", "ufeats", "xpos"):
        assert row[metric] == round(res["perseus_test"][metric] * 100, 2), metric
    prow = claims["neural_ud_proiel_test"]
    for metric in ("lemma", "uas", "las", "upos", "ufeats"):
        assert prow[metric] == round(res["proiel_ud_test"][metric] * 100, 2), metric
    nt = claims["neural_nt"]
    assert nt["lemma"] == round(res["nt_whole"]["lemma"] * 100, 2)
    assert nt["upos_reconciled"] == round(res["nt_whole"]["upos_reconciled"] * 100, 2)
    assert nt["n_tokens"] == res["nt_whole"]["n_tokens"]


def test_doc_confidence_intervals_match_the_bootstrap_evidence() -> None:
    """The stated 95% CI cells must come from the recorded bootstrap evidence file,
    and the evidence's point estimates must agree with the registry pins."""
    claims = _claims()["neural_ud_perseus_test"]
    doc = _read("docs/benchmarks.md")
    page = _read("wiki/Benchmarks.md")
    ev = _read("training/results/v3-bootstrap-ci-2026-07-10.txt")
    for line in ev.strip().splitlines():
        metric, point, _, _, low, high = line.split()
        assert float(point) == claims[metric], metric
        cell = f"[{low.strip('[,')}, {high.strip(']')}]"
        assert cell in doc, f"{metric} CI {cell} missing from docs/benchmarks.md"
        assert cell in page, f"{metric} CI {cell} missing from wiki/Benchmarks.md"


def test_registry_agrees_with_the_quantize_size_evidence() -> None:
    claims = _claims()
    v3 = json.loads(_read("training/results/v3-quantize-report.json"))
    q = claims["quantization"]
    assert q["tar_gz_bytes"] == v3["shipped_bytes"]["tar_gz"]
    assert q["onnx_bytes"] == v3["shipped_bytes"]["model.onnx"]
    assert q["fp32_tar_gz_bytes"] == v3["shipped_bytes"]["fp32_reference"]["tar_gz"]


def test_registry_agrees_with_the_seed_replicate_evidence() -> None:
    claims = _claims()["neural_seed_replicates"]
    summary = json.loads(_read("training/results/seed-grc-joint-v2/summary.json"))
    assert round(summary["las"]["mean"], 2) == claims["las_mean"]
    assert round(summary["las"]["std"], 2) == claims["las_std"]
    assert round(summary["uas"]["mean"], 2) == claims["uas_mean"]
    assert round(summary["uas"]["std"], 2) == claims["uas_std"]


def test_benchmarks_doc_carries_the_neural_rows() -> None:
    claims = _claims()
    doc = _read("docs/benchmarks.md")
    for metric, v in claims["neural_ud_perseus_test"].items():
        if isinstance(v, float):
            assert f"{v:.2f}" in doc, f"Perseus {metric} {v} missing from docs/benchmarks.md"
    for metric in ("lemma", "uas", "las", "upos", "ufeats"):
        v = claims["neural_ud_proiel_test"][metric]
        assert f"{v:.2f}" in doc, f"PROIEL {metric} {v} missing from docs/benchmarks.md"
    seeds = claims["neural_seed_replicates"]
    assert f"LAS {seeds['las_mean']:.2f} ± {seeds['las_std']:.2f}" in doc


def test_benchmarks_doc_carries_the_offline_baseline_rows() -> None:
    claims = _claims()["offline_baseline_ud"]
    doc = _read("docs/benchmarks.md")
    for fold in ("perseus_test", "proiel_test"):
        for metric, v in claims[fold].items():
            assert f"{v:.2f}" in doc, f"baseline {fold} {metric} {v} missing from docs/benchmarks.md"
    assert f"{claims['proiel_lemma_with_neural_lemmatizer']:.2f}" in doc


def test_benchmarks_doc_carries_the_nt_row() -> None:
    claims = _claims()["neural_nt"]
    doc = _read("docs/benchmarks.md")
    assert f"{claims['lemma']:.2f}" in doc
    assert f"{claims['upos_reconciled']:.2f}" in doc
    assert f"{claims['n_tokens']:,}" in doc


def test_benchmarks_doc_quantization_sizes_match_evidence() -> None:
    q = _claims()["quantization"]
    doc = _read("docs/benchmarks.md")
    # the doc states rounded MB figures; they must round from the measured bytes
    for label, b in (("173 MB", q["tar_gz_bytes"]), ("182 MB", q["onnx_bytes"]),
                     ("518 MB", q["fp32_tar_gz_bytes"]), ("556 MB", q["fp32_onnx_bytes"])):
        assert label in doc, label
        assert int(label.split()[0]) == round(b / 1e6) or int(label.split()[0]) == b // 10**6, label


def test_throughput_claims_match_the_registry() -> None:
    """The CPU-throughput figures (quantized range + fp32 comparison) must match the
    registry wherever they are stated — the 450-words/s figure drifted for two model
    generations before this pin."""
    t = _claims()["throughput_cpu"]
    rng = t["quantized_words_per_s"]
    for rel in ("docs/benchmarks.md", "wiki/Greek-NLP.md"):
        assert f"{rng} words/s" in _read(rel).replace("words/second", "words/s"), rel
    assert f"{t['fp32_words_per_s_approx']} words/s" in _read("docs/benchmarks.md")


def test_benchmarks_doc_bootstrap_count_matches_the_default() -> None:
    """The stated resample count must be bootstrap_ud's actual default, so the
    documented reproduction command runs the documented protocol."""
    import inspect

    from aegean import greek

    n = _claims()["bootstrap"]["n_resamples"]
    default = inspect.signature(greek.bootstrap_ud).parameters["n_resamples"].default
    assert default == n
    assert f"{n} resamples" in _read("docs/benchmarks.md")


def test_benchmarks_doc_out_of_domain_lead_is_reconstructible() -> None:
    """The stated lead must be derivable from the two datapoints the doc itself cites."""
    lead = _claims()["out_of_domain_lead"]
    doc = _read("docs/benchmarks.md")
    assert round(lead["pyaegean_proiel_uas"] - lead["stanza_perseus_proiel_uas"]) == lead["stated_lead"]
    assert f"{lead['pyaegean_proiel_uas']:.2f}" in doc
    assert f"{lead['stanza_perseus_proiel_uas']:.2f}" in doc
    assert f"~{lead['stated_lead']} UAS" in doc


def test_readme_and_wiki_echoes_match_the_registry() -> None:
    """The 1-decimal headline echoes outside docs/benchmarks.md must round from the
    registry values (the drift class where an echo outlives a re-measurement).
    README and Home state them as prose ("97.0 UPOS / ..."); Greek-NLP as a table row,
    so each page is checked for the rounded values it actually carries. The 1-decimal
    figures round from the FULL-PRECISION evidence, not from the registry's 2-decimal
    cells: re-rounding an already-rounded pin double-rounds (85.648 -> 85.65 -> 85.7,
    overstating a measured 85.6)."""
    rem = json.loads(_read("training/results/lemma-remeasure-2026-07-09.json"))
    per = rem["results_full_precision"]["perseus_test"]
    row = _claims()["neural_ud_perseus_test"]
    rounded = {m: f"{per[m] * 100:.1f}" for m in ("upos", "ufeats", "lemma", "uas", "las")}
    # each 1-decimal echo must also be consistent with the registry's 2-decimal pin
    for m, v in rounded.items():
        assert abs(float(v) - row[m]) < 0.06, m
    prose = f"{rounded['upos']} UPOS / {rounded['ufeats']} UFeats / {rounded['lemma']} lemma"
    for rel in ("README.md", "wiki/Home.md"):
        text = _read(rel)
        assert prose in text, f"{rel} headline echo does not match the registry"
        assert f"{rounded['uas']} UAS" in text
        assert f"{rounded['las']} LAS" in text
    # Greek-NLP.md carries the same figures as a comparison-table row
    table_row = f"**{rounded['upos']}** | **{rounded['ufeats']}** | **{rounded['lemma']}** | **{rounded['uas']}** | **{rounded['las']}**"
    assert table_row in _read("wiki/Greek-NLP.md"), (
        "wiki/Greek-NLP.md neural table row does not match the registry"
    )


def test_limitations_offline_lemma_claim_matches_the_registry() -> None:
    claims = _claims()["offline_nt_lemma"]
    text = _read("wiki/Limitations.md")
    assert f"~{round(claims['lemma'])}%" in text  # "~66% on the full NT"


def test_wiki_benchmarks_page_matches_the_registry() -> None:
    """The public wiki Benchmarks page (which, per the 2026-07 convention override, may now
    carry the cross-tool comparison tables) must keep every measured figure pinned to the
    registry — the "accurate and factual" condition the override is granted under. Number drift
    on that page is a test failure, exactly as for docs/benchmarks.md."""
    claims = _claims()
    page = _read("wiki/Benchmarks.md")
    for metric, v in claims["neural_ud_perseus_test"].items():
        if isinstance(v, float):
            assert f"{v:.2f}" in page, f"Perseus {metric} {v} missing from wiki/Benchmarks.md"
    for metric in ("lemma", "uas", "las", "upos", "ufeats"):
        v = claims["neural_ud_proiel_test"][metric]
        assert f"{v:.2f}" in page, f"PROIEL {metric} {v} missing from wiki/Benchmarks.md"
    for fold in ("perseus_test", "proiel_test"):
        for metric, v in claims["offline_baseline_ud"][fold].items():
            assert f"{v:.2f}" in page, f"baseline {fold} {metric} {v} missing from wiki/Benchmarks.md"
    assert f"{claims['neural_nt']['lemma']:.2f}" in page
    assert f"{claims['neural_nt']['upos_reconciled']:.2f}" in page
    assert f"~{round(claims['offline_nt_lemma']['lemma'])}%" in page  # "~66% on the full NT"
