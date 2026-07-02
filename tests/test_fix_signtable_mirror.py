"""Linear A sign-table mirror + workbench 1.6.0 round-trip regressions.

Pins three fixes mirrored from the Linear A Research Workbench 1.6.0 release
(the workbench's sign aligner no longer counts the unassigned U+1076B damage
marker as a sign, growing the alignment evidence base from 127 to 236
inscriptions and the aligned table from 84 to 95 signs, with AB-shared
classification now following the Unicode 16.0 code chart):

* the bundled ``lineara/signs.json`` aligned section equals the corrected
  workbench table: 95 transliteration-aligned signs (15 recovered, incl. QI,
  PU, PU2), re-tallied totals/confidence, chart-rule ``sharedWithLinearB``,
  and the four old entries whose "glyphs" were unassigned codepoints (VS,
  *408, *409, *810 - U+1076B/U+106A8-as-drifted/U+1076D) dropped, with the
  released assigned codepoints back-filled as UCD entries;
* the ``workbench-app`` asset pin moves to 1.6.0 (the stored-XSS-fixed build);
* `from_workbench_export` reads the schema-v1 export's real field spellings:
  the dating period as ``period`` and imagery nested under an ``images``
  object (``facsimile``/``photograph``), not only the plain-array shape's
  ``context`` + flat lists. Before the fix a schema-v1 export lost its period
  and read the images object's KEYS ("facsimile", "photograph", ...) as
  image paths.
"""

from __future__ import annotations

import re
import warnings

import pytest

from aegean import data
from aegean.data import load_bundled_json
from aegean.io import from_workbench_export, to_workbench
from aegean.scripts.lineara.inventory import linear_a_inventory

# ---------------------------------------------------------------------------
# the sign-table mirror
# ---------------------------------------------------------------------------

# The Unicode 16.0 Linear A block's three assigned ranges (the rest of
# U+10600-U+1077F is unassigned; upstream renders damage with U+1076B).
_ASSIGNED = ((0x10600, 0x10736), (0x10740, 0x10755), (0x10760, 0x10767))
# The codepoints whose Unicode names are "LINEAR A SIGN ABnnn": the signs
# Linear A shares with Linear B, per the code chart.
_AB_SERIES = (
    (0x10600, 0x1061A),
    (0x1061C, 0x10646),
    (0x10648, 0x10649),
    (0x1064B, 0x1064E),
    (0x10650, 0x10654),
)

# The 15 signs the corrected aligner recovered (they previously sat in the
# inventory as bare UCD entries with no alignment evidence).
_RECOVERED = {
    "*305": 1, "*310": 1, "*312": 1, "*321": 1, "*323": 1, "*331": 1,
    "*34": 1, "*358": 1, "*363": 1, "*47": 3, "*802": 1,
    "PU": 4, "PU2": 4, "QI": 1, "VIN+TE": 1,
}


def _in(ranges: tuple[tuple[int, int], ...], cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def _aligned(inv):
    return [s for s in inv if s.attrs.get("source") != "ucd"]


def test_aligned_sign_count_is_95_and_manifest_matches():
    inv = linear_a_inventory()
    aligned = _aligned(inv)
    assert len(aligned) == 95
    manifest = load_bundled_json("lineara", "manifest.json")
    assert manifest["signCount"] == 95
    # every aligned sign carries real alignment evidence (or is *903, kept
    # unrendered on purpose)
    assert all(s.attrs.get("total", 0) >= 1 for s in aligned)


def test_manifest_parity_sha_unchanged_by_the_sign_mirror():
    """The sign table is derived data; the corpus parity contract with the
    workbench (fields + sha over the canonical projection) must not move."""
    manifest = load_bundled_json("lineara", "manifest.json")
    assert manifest["paritySha256"] == (
        "9cf53d8f3b9220888d502dc09efd9d3771d5a68b7dad1446827c96f3ea5de9f9"
    )
    assert manifest["inscriptionCount"] == 1721


def test_recovered_signs_carry_alignment_attrs():
    inv = linear_a_inventory()
    for label, total in _RECOVERED.items():
        s = inv.by_label(label)
        assert s is not None, label
        assert s.attrs.get("source") != "ucd", label
        assert s.attrs["total"] == total, label
        assert 0 < s.attrs["confidence"] <= 1, label
    # PU is the one recovered sign with a shared Linear B sound value
    pu = inv.by_label("PU")
    assert pu.phonetic == "pu"
    # 48 aligned signs now carry a sound value (was 47 before PU)
    assert sum(1 for s in _aligned(inv) if s.phonetic) == 48


def test_realigned_totals_match_the_grown_evidence_base():
    """Spot-check re-tallied totals against the corrected workbench table
    (evidence base 127 -> 236 inscriptions)."""
    inv = linear_a_inventory()
    assert inv.by_label("A").attrs["total"] == 74     # was 35
    assert inv.by_label("KU").attrs["total"] == 29
    i = inv.by_label("I")
    assert i.attrs["total"] == 55
    assert i.attrs["confidence"] == pytest.approx(54 / 55)


def test_ab_shared_follows_the_unicode_chart_rule():
    """A sign is AB-shared iff its codepoint carries a LINEAR A SIGN ABnnn
    name; the old table used a phonetic-value-known proxy that missed the
    AB signs without standard transliterations and the AB-numbered
    ideograms."""
    inv = linear_a_inventory()
    for s in inv:
        if s.codepoint is not None:
            assert s.attrs["sharedWithLinearB"] == _in(_AB_SERIES, s.codepoint), s.label
    # the reclassified signs, previously linearAOnly under the proxy
    for label in ("RA2", "PA3", "TA2", "AU", "NWA", "ZU", "GRA", "VIN",
                  "OLIV", "*86", "*118", "*164", "*188", "*21F"):
        s = inv.by_label(label)
        assert s is not None and s.attrs["sharedWithLinearB"] is True, label
        assert s.attrs["linearAOnly"] is False, label
    # a *-labeled sign outside the AB ranges stays Linear-A-only
    s305 = inv.by_label("*305")
    assert s305.attrs["sharedWithLinearB"] is False
    assert s305.attrs["linearAOnly"] is True


def test_unassigned_codepoint_entries_are_gone():
    """VS, *408, *409, and *810 wore codepoints the aligner should never have
    tallied (U+1076B is upstream's damage marker; the block above U+10767 is
    unassigned); the corrected aligner drops them, and the two *assigned*
    codepoints they had shadowed (A408-VAS/A409-VAS) return as UCD entries."""
    inv = linear_a_inventory()
    for label in ("VS", "*408", "*409", "*810"):
        assert inv.by_label(label) is None, label
    for cp in (0x1076B, 0x1076D):
        assert inv.by_codepoint(cp) is None, hex(cp)
    for label, cp in (("A408-VAS", 0x106A8), ("A409-VAS", 0x106A9)):
        s = inv.by_label(label)
        assert s is not None and s.codepoint == cp
        assert s.attrs.get("source") == "ucd"


def test_inventory_covers_the_assigned_block_exactly_once():
    """Every assigned Linear A codepoint appears exactly once (full-repertoire
    coverage with injective glyph/codepoint maps); *903 is the one aligned
    sign without a codepoint. No entry ships an unassigned codepoint."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        inv = linear_a_inventory()
    assert len(inv) == 342
    cps = [s.codepoint for s in inv if s.codepoint is not None]
    assert len(cps) == len(set(cps))
    assigned = {cp for lo, hi in _ASSIGNED for cp in range(lo, hi + 1)}
    assert set(cps) == assigned
    no_cp = [s.label for s in inv if s.codepoint is None]
    assert no_cp == ["*903"]


# ---------------------------------------------------------------------------
# the workbench-app 1.6.0 pin
# ---------------------------------------------------------------------------


def test_workbench_app_pin_is_the_1_6_0_build():
    """1.6.0 carries the workbench's stored-XSS fixes (and the regenerated
    95-sign table this bundled mirror matches)."""
    spec = data._REMOTE["workbench-app"]
    m = re.search(r"workbench-app-v(\d+)\.(\d+)\.(\d+)/", spec.url)
    assert m is not None
    assert tuple(int(g) for g in m.groups()) == (1, 6, 0)
    assert spec.sha256 == (
        "caf00eabd61332683b758e154cd3c2d8a431f468f221ee2a714953e3fc08fdf6"
    )


# ---------------------------------------------------------------------------
# the schema-v1 (1.6.0) export shape: period + nested images
# ---------------------------------------------------------------------------


def _schema_v1_export() -> dict:
    """A real 1.6.0-shaped export record set, per the workbench's
    corpusExport.ts: the dating period is ``period`` (not ``context``) and
    imagery is nested under ``images`` (not flat arrays)."""
    return {
        "_meta": {
            "exportedAt": "2026-07-01T00:00:00Z",
            "tool": "Linear A Research Workbench",
            "toolRepo": "ryanpavlicek/linearaworkbench",
            "schemaVersion": 1,
            "scopeSummary": "whole corpus",
            "inscriptionCount": 1,
        },
        "inscriptions": [
            {
                "id": "HT13",
                "site": "Haghia Triada",
                "period": "LMIB",
                "scribe": "Scribe 9",
                "support": "tablet",
                "findspot": "Casa del Lebete",
                "name": "HT13",
                "words": ["KA-U-DE-TA", "KU-RO"],
                "translations": ["", "total"],
                "lines": [["KA-U-DE-TA"], ["KU-RO"]],
                "glyphs": "\U00010613",
                "transcription": "KA-U-DE-TA KU-RO",
                "images": {
                    "facsimile": ["images/HT13.png"],
                    "photograph": ["photos/HT13.jpg"],
                    "rights": "GORILA",
                    "rightsUrl": "https://example.invalid/rights",
                },
                "derived": {
                    "multiSignWordCount": 2,
                    "tabletStructureHeuristic": "accounting",
                    "tabletStructureCategory": "accounting",
                    "tabletStructureOverridden": False,
                },
            }
        ],
    }


def test_schema_v1_export_period_and_nested_images_are_read():
    corpus = from_workbench_export(_schema_v1_export())
    doc = corpus.get("HT13")
    assert doc is not None
    assert doc.meta.period == "LMIB"  # was lost: only "context" was read
    assert doc.meta.images == ("images/HT13.png", "photos/HT13.jpg")
    # the failure mode of the old flat-list read: the images OBJECT's keys
    # must never come through as image "paths"
    assert "facsimile" not in doc.meta.images
    assert "photograph" not in doc.meta.images
    assert doc.meta.site == "Haghia Triada"
    assert [t.text for t in doc.tokens] == ["KA-U-DE-TA", "KU-RO"]


def test_legacy_array_shape_still_reads_context_and_flat_images():
    corpus = from_workbench_export(
        [
            {
                "id": "X1",
                "context": "LMIB",
                "words": ["A-DU"],
                "facsimileImages": ["images/X1.png"],
                "images": ["photos/X1.jpg"],
            }
        ]
    )
    doc = corpus.get("X1")
    assert doc is not None
    assert doc.meta.period == "LMIB"
    assert doc.meta.images == ("images/X1.png", "photos/X1.jpg")


def test_schema_v1_round_trips_through_the_workbench_shape():
    """import (schema-v1) -> to_workbench -> import again: the period and the
    imagery survive both directions, so a workbench export re-imports
    losslessly on this surface."""
    first = from_workbench_export(_schema_v1_export())
    back = from_workbench_export(to_workbench(first))
    a, b = first.get("HT13"), back.get("HT13")
    assert b is not None
    assert b.meta.period == a.meta.period == "LMIB"
    assert b.meta.images == a.meta.images
    assert [t.text for t in b.tokens] == [t.text for t in a.tokens]
    assert b.translations == a.translations
