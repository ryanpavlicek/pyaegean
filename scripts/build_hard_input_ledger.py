#!/usr/bin/env python3
"""Build the deterministic offline Hard-Input Scholarly Coverage Ledger.

Measures PyAegean's zero-dependency Greek + Cypriot processing across six
challenging real-world input classes without touching any locked NLP test fold:

1. OCR / lunate-sigma / diacritic-degraded inputs
2. Epigraphic Leiden damage, restorations, underdots, and lacunae
3. Koine / documentary orthographic variation, crasis, and iota-subscript safety
4. Ellipsis, long periodic clauses, and named sentence-segmentation policies
5. Dialectal and genre diversity (Epic, Aeolic, Ionic, Attic, Koine/LXX, Cypriot)
6. Quantitative metrical scansion dossier (hexameter, pentameter, trimeter, aeolic)

Every record explicitly declares ``evidence_kind`` (``"attested"`` vs
``"constructed"``), exact source citation, and reproducible offline outputs,
and the ledger records remaining unevaluated gaps explicitly.

Usage::

    python3 scripts/build_hard_input_ledger.py
    python3 scripts/build_hard_input_ledger.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any

import aegean
from aegean.greek import (
    GreekPipeline,
    normalize,
    resolve_sandhi,
    score_scansion,
    segment_sentences,
    strip_diacritics,
    tokenize,
)
from aegean.scripts.cypriot import lexicon_entry
from aegean.scripts.cypriot.analysis import bridge_coverage
from aegean.search import fold_greek

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "training" / "results" / "hard-input-coverage-ledger-v1.json"


def build_ledger() -> dict[str, Any]:
    """Generate the deterministic hard-input coverage ledger dictionary."""
    # Explicit baseline pipeline instance guarantees isolation from any active global facade backend.
    pipe = GreekPipeline()

    # 1. OCR, Latin-lookalike repair & lunate sigma cohort
    ocr_cases = [
        {
            "id": "ocr_latin_and_betacode_repair",
            "evidence_kind": "constructed",
            "source": "OCR-degraded Greek with Latin lookalikes (o/v) and Beta-Code accent remnant",
            "raw": "Ἐν ἀρχῇ ἦν ὁ Λο/γoς, βασιλεvς",
            "lenient": True,
        },
        {
            "id": "ocr_lunate_koine",
            "evidence_kind": "constructed",
            "source": "John 1:1 with lunate sigma (U+03F2/U+03F9) & NFD combining marks (honest preservation)",
            "raw": "Ἐν ἀρχῇ ἦν ὁ Λόγοϲ, καὶ ὁ Λόγοϲ ἦν πρὸϲ τὸν Θεόν.",
            "lenient": False,
        },
        {
            "id": "ocr_unaccented_uppercase",
            "evidence_kind": "attested",
            "source": "Swete Septuagint Genesis 1:1 style uppercase unaccented opening",
            "raw": "ΕΝ ΑΡΧΗ ΕΠΟΙΗΣΕΝ Ο ΘΕΟΣ ΤΟΝ ΟΥΡΑΝΟΝ ΚΑΙ ΤΗΝ ΓΗΝ",
            "lenient": False,
        },
        {
            "id": "ocr_pg_noisy_diacritics",
            "evidence_kind": "constructed",
            "source": "Patrologia Graeca CGPG-style OCR noise (missing breathing + diacritics)",
            "raw": "Εν αρχη ην ο λογος και ο λογος ην προς τον θεον",
            "lenient": False,
        },
    ]
    ocr_results: list[dict[str, Any]] = []
    for case in ocr_cases:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            normed = normalize(case["raw"], lenient=bool(case["lenient"]))
        toks = tokenize(normed)
        analyzed = pipe.analyze(normed)
        ocr_results.append(
            {
                "id": case["id"],
                "evidence_kind": case["evidence_kind"],
                "source": case["source"],
                "lenient": bool(case["lenient"]),
                "repair_warnings": [str(w.message) for w in caught],
                "normalized": normed,
                "folded": fold_greek(normed),
                "token_count": len(toks),
                "lemmas": [r.lemma for r in analyzed if r.upos != "PUNCT"],
                "upos": [r.upos for r in analyzed if r.upos != "PUNCT"],
            }
        )

    # 2. Epigraphic Leiden damage & restorations
    cyp = aegean.load("cypriot")
    cyp_cov = bridge_coverage(cyp)
    ig95 = next(d for d in cyp if d.id == "IG XV 1, 95")
    ig192 = next(d for d in cyp if d.id == "IG XV 1, 192")
    leiden_greek = "ἔδοξεν [τῇ βουλ]ῇ καὶ τῷ δήμῳ· Αὐρ(ήλιος) ⟨Θεό⟩δωρος {τὸν} [---] ἀνέθηκεν."
    leiden_doc = next(iter(aegean.io.from_text(leiden_greek, doc_id="leiden_control")))
    epidoc_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt>'
        "<title>Attic decree control</title></titleStmt><publicationStmt><p/></publicationStmt>"
        "<sourceDesc><p/></sourceDesc></fileDesc></teiHeader><text><body>"
        '<div type="edition"><ab><w>ἔδοξεν</w> '
        '<supplied reason="lost"><w>τῇ</w> <w>βουλῇ</w></supplied> '
        '<unclear><w>καὶ</w></unclear> <w>τῷ</w> '
        '<gap reason="lost" extent="unknown"/> <w>δήμῳ</w></ab></div>'
        "</body></text></TEI>"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        ep_path = Path(tmpdir) / "control.xml"
        ep_path.write_text(epidoc_xml, encoding="utf-8")
        epidoc_doc = aegean.io.read_epidoc(ep_path)[0]
    leiden_cohort = {
        "cypriot_ig_xv1_attested": {
            "evidence_kind": "attested",
            "source": "Inscriptiones Graecae XV 1 (BBAW, CC BY 4.0) bundled corpus",
            "documents": len(cyp),
            "word_tokens": cyp_cov.word_tokens,
            "read_tokens": cyp_cov.read_tokens,
            "coverage_pct": round(cyp_cov.coverage_pct, 2),
            "distinct_read_forms": cyp_cov.distinct_read_forms,
            "read_by_status": cyp_cov.read_by_status,
            "ig_95_sample_lemmas": [
                entry.lemma
                for t in ig95.words
                if (entry := lexicon_entry(t.text)) is not None
            ],
            "ig_192_restored_tokens": [
                {"text": t.text, "status": t.status.value, "leiden": t.annotations.get("leiden", "")}
                for t in ig192.tokens
                if t.annotations.get("leiden")
            ],
        },
        "greek_leiden_constructed_control": {
            "evidence_kind": "constructed",
            "source": "Standard Attic decree formula with Leiden [], <>, {}, (), [---] marks",
            "raw": leiden_greek,
            "word_count": len(leiden_doc.words),
            "words": [t.text for t in leiden_doc.words],
        },
        "epidoc_xml_apparatus_control": {
            "evidence_kind": "constructed",
            "source": "Minimal TEI/EpiDoc XML with <w>, <supplied>, <unclear>, and <gap>",
            "tokens": [
                {"text": t.text, "kind": t.kind.value, "status": t.status.value}
                for t in epidoc_doc.tokens
            ],
        },
    }

    # 3. Orthographic variation, crasis & iota-subscript safety
    sandhi_cases = [
        ("κἀγὼ", "attested", "Attic/Koine crasis with grave accent (καί + ἐγώ)"),
        ("ἁνήρ", "attested", "Attic crasis with rough breathing (ὁ + ἀνήρ)"),
        ("τἀληθῆ", "attested", "Attic crasis in curated lexicon (τά + ἀληθῆ)"),
        ("τἀγαθά", "attested", "Attic crasis outside curated lexicon (conservative abstention control)"),
    ]
    sandhi_results = []
    for form, kind, src in sandhi_cases:
        res = resolve_sandhi(form)
        sandhi_results.append(
            {
                "form": form,
                "evidence_kind": kind,
                "source": src,
                "resolved": list(res.words) if res.resolved else [],
                "kind": res.kind,
                "uncertain": res.uncertain,
            }
        )
    iota_pair = {
        "evidence_kind": "attested",
        "source": "Dative sg. ἐκκλησίᾳ vs. nominative pl. ἐκκλησίαι",
        "dat_sg": "ἐκκλησίᾳ",
        "nom_pl": "ἐκκλησίαι",
        "exact_lower_distinct": normalize("ἐκκλησίᾳ").lower() != normalize("ἐκκλησίαι").lower(),
        "stripped_distinct": strip_diacritics("ἐκκλησίᾳ") != strip_diacritics("ἐκκλησίαι"),
    }

    # 4. Ellipsis, long periods & named sentence policies
    periodic_text = (
        "Ἡροδότου Ἁλικαρνησσέος ἱστορίης ἀπόδεξις ἥδε, ὡς μήτε τὰ γενόμενα ἐξ ἀνθρώπων "
        "τῷ χρόνῳ ἐξίτηλα γένηται, μήτε ἔργα μεγάλα τε καὶ θωμαστά, τὰ μὲν Ἕλλησι, "
        "τὰ δὲ βαρβάροισι ἀποδεχθέντα, ἀκλεᾶ γένηται, τά τε ἄλλα καὶ δι᾽ ἣν αἰτίην "
        "ἐπολέμησαν ἀλλήλοισι."
    )
    multi_sent = (
        "Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος. "
        "οὗτος ἦν ἐν ἀρχῇ πρὸς τὸν θεόν· πάντα δι’ αὐτοῦ ἐγένετο."
    )
    seg_policies = {
        policy: len(segment_sentences(multi_sent, policy=policy).sentences)
        for policy in ("default", "prose", "verse", "inscription", "papyrus")
    }
    periodic_analyzed = pipe.analyze(periodic_text)
    ellipsis_and_periods = {
        "herodotus_proem_attested": {
            "evidence_kind": "attested",
            "source": "Herodotus, Histories 1.1.0 (Ionic periodic proem, bundled sample)",
            "word_count": sum(1 for r in periodic_analyzed if r.upos != "PUNCT"),
            "sentence_count": len(segment_sentences(periodic_text, policy="prose").sentences),
            "sample_lemmas": [r.lemma for r in periodic_analyzed[:8] if r.upos != "PUNCT"],
        },
        "policy_segmentation_matrix": {
            "evidence_kind": "attested",
            "source": "Gospel of John 1:1-3 (Nestle 1904 punctuation incl. raised dot ·)",
            "sentence_counts_by_policy": seg_policies,
        },
    }

    # 5. Dialect & genre cohort (zero locked-test reuse)
    dialect_samples = [
        ("epic_homer", "attested", "Homer, Iliad 1.1 (Epic)", "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"),
        ("aeolic_sappho", "attested", "Sappho fr. 1.1 (Aeolic)", "ποικιλόθρον’ ἀθανάτ’ Ἀφρόδιτα"),
        ("attic_tragedy", "attested", "Sophocles, Antigone 1 (Attic trimeter, non-locked)", "ὦ κοινὸν αὐτάδελφον Ἰσμήνης κάρα"),
        ("koine_nt", "attested", "John 1:1 (Koine NT)", "Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν."),
        ("lxx_genesis", "attested", "Septuagint Genesis 1:1 (Swete LXX)", "Ἐν ἀρχῇ ἐποίησεν ὁ θεὸς τὸν οὐρανὸν καὶ τὴν γῆν."),
    ]
    dialect_results = []
    for cid, kind, src, txt in dialect_samples:
        recs = pipe.analyze(txt)
        words = [r for r in recs if r.upos != "PUNCT"]
        dialect_results.append(
            {
                "id": cid,
                "evidence_kind": kind,
                "source": src,
                "word_count": len(words),
                "lemmas": [r.lemma for r in words],
                "upos": [r.upos for r in words],
            }
        )

    # 6. Quantitative metrical scansion dossier (attested verse + prose control)
    meter_samples = [
        ("iliad_1_1", "attested", "Homer, Iliad 1.1", "hexameter", "μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος"),
        ("iliad_1_3", "attested", "Homer, Iliad 1.3", "hexameter", "πολλὰς δ’ ἰφθίμους ψυχὰς Ἄϊδι προΐαψεν"),
        ("iliad_1_18", "attested", "Homer, Iliad 1.18 (optional synizesis θεοὶ)", "hexameter", "ὑμῖν μὲν θεοὶ δοῖεν Ὀλύμπια δώματ’ ἔχοντες"),
        ("odyssey_1_1", "attested", "Homer, Odyssey 1.1", "hexameter", "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"),
        ("antigone_1", "attested", "Sophocles, Antigone 1 (non-locked)", "trimeter", "ὦ κοινὸν αὐτάδελφον Ἰσμήνης κάρα"),
        ("sappho_31_1", "attested", "Sappho fr. 31.1", "sapphic_hendecasyllable", "φαίνεταί μοι κῆνος ἴσος θέοισιν"),
        ("alcaeus_326_1", "attested", "Alcaeus fr. 326.1", "alcaic_hendecasyllable", "ἀσυννέτημμι τὼν ἀνέμων στάσιν"),
        ("prose_negative_control", "constructed", "Constructed prose negative control", "hexameter", "τοῦτο πεζός ἐστι λόγος"),
    ]
    meter_results = []
    for mid, kind, src, meter_name, line in meter_samples:
        sc = score_scansion(line, meter=meter_name)
        meter_results.append(
            {
                "id": mid,
                "evidence_kind": kind,
                "source": src,
                "meter": meter_name,
                "scans": sc.scans,
                "pattern": sc.scansion.pattern if sc.scansion else None,
                "syllable_count": sc.syllable_count,
                "caesura": sc.scansion.caesura if sc.scansion else None,
                "canonical_caesura": sc.canonical_caesura,
                "ambiguous": sc.ambiguous,
                "dactyl_ratio": sc.dactyl_ratio,
                "spondaic_fifth": sc.spondaic_fifth,
                "resolved_count": sc.resolved_count,
                "synizesis_used": list(sc.synizesis_used),
                "long_by_nature_used": list(sc.long_by_nature_used),
                "error": sc.error,
            }
        )

    attested_verse = [m for m in meter_results if m["evidence_kind"] == "attested"]
    return {
        "schema_version": "1",
        "name": "pyaegean-hard-input-coverage-ledger-v1",
        "description": (
            "Deterministic offline scholarly coverage ledger across OCR/lunate text, "
            "Leiden epigraphic apparatus, orthographic variation/crasis, long periods, "
            "dialectal genres, and quantitative metrical scansion. Separates attested "
            "references, constructed controls, and explicitly unevaluated gaps; uses "
            "no locked NLP test folds."
        ),
        "locked_folds_used": False,
        "summary": {
            "ocr_cases": len(ocr_results),
            "cypriot_bridge_read_tokens": cyp_cov.read_tokens,
            "cypriot_bridge_word_tokens": cyp_cov.word_tokens,
            "sandhi_resolved": sum(1 for r in sandhi_results if r["resolved"]),
            "sandhi_total": len(sandhi_results),
            "dialect_cohorts": len(dialect_results),
            "attested_verse_scanned": sum(1 for m in attested_verse if m["scans"]),
            "attested_verse_total": len(attested_verse),
            "prose_negative_control_rejected": not meter_results[-1]["scans"],
        },
        "cohorts": {
            "ocr_and_lunate": ocr_results,
            "leiden_damage_restoration": leiden_cohort,
            "spelling_variation_and_crasis": {
                "crasis": sandhi_results,
                "iota_subscript_safety": iota_pair,
            },
            "ellipsis_and_long_periods": ellipsis_and_periods,
            "dialect_and_genre_coverage": dialect_results,
            "metrical_scansion_dossier": meter_results,
        },
        "unevaluated_gaps": [
            {
                "area": "Multi-work adjudicated Greek tragedy syntax & lemmas beyond Bacchae",
                "status": "unevaluated",
                "reason": "Awaits external human two-reader adjudication of archived Daphne Philoctetes & Iphigenia in Tauris packets.",
            },
            {
                "area": "Raw Patrologia Graeca CGPG OCR word-error-rate vs. manual collation",
                "status": "unevaluated",
                "reason": "No aligned manual gold collation exists in-repo for CGPG OCR volumes (edition_fidelity='ocr' remains explicitly labeled).",
            },
            {
                "area": "Dactylo-epitrite and free astrophic choral lyric scansion",
                "status": "unevaluated",
                "reason": "Outside the fixed-template meter family (hexameter, pentameter, trimeter, aeolic) currently implemented in aegean.greek.meter.",
            },
            {
                "area": "Neural translation fidelity on unseen passage families",
                "status": "unevaluated",
                "reason": "Requires live provider API evaluation and human/rubric grading outside offline deterministic checks.",
            },
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="verify checked-in JSON matches live computation")
    args = ap.parse_args()

    ledger = build_ledger()
    rendered = json.dumps(ledger, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not _OUT.is_file():
            print(f"MISSING {_OUT}", file=sys.stderr)
            return 1
        existing = _OUT.read_text(encoding="utf-8")
        if existing != rendered:
            print(f"DRIFT detected in {_OUT}; re-run scripts/build_hard_input_ledger.py", file=sys.stderr)
            return 1
        print(f"OK {_OUT.relative_to(_ROOT)} matches live computation ({ledger['summary']})")
        return 0

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(rendered, encoding="utf-8")
    print(f"Wrote {_OUT.relative_to(_ROOT)} ({len(rendered)} bytes) | summary={ledger['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
