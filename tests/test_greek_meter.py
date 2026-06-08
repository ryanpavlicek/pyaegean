"""Greek metrical scansion (dactylic hexameter + elegiac pentameter)."""

from __future__ import annotations

import pytest

from aegean.greek import (
    LineScansion,
    ScansionError,
    scan_hexameter,
    scan_line,
    scan_pentameter,
    syllable_options,
)
from aegean.greek.meter import ANCEPS, HEAVY, LIGHT

# Canonical scansions (independently stated from standard editions/commentaries,
# not read off the scanner). Glyphs: — heavy, ⏑ light, × anceps.
HEXAMETERS = [
    # Odyssey 1.1 — five dactyls; μοι shortened by correptio before ἔννεπε.
    ("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ",
     "—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×"),
    # Odyssey 1.2 — πλάγχθη must shorten (correptio) for the line to scan.
    ("πλάγχθη, ἐπεὶ Τροίης ἱερὸν πτολίεθρον ἔπερσεν",
     "—⏑⏑|——|—⏑⏑|—⏑⏑|—⏑⏑|—×"),
    # Iliad 1.2 — two spondees (feet 2 and 4); elisions μυρί'/ἄλγε'.
    ("οὐλομένην, ἣ μυρίʼ Ἀχαιοῖς ἄλγεʼ ἔθηκε,",
     "—⏑⏑|——|—⏑⏑|——|—⏑⏑|—×"),
    # Iliad 1.5 — opens with a spondee (ὦ.../οἰωνοῖσι).
    ("οἰωνοῖσί τε πᾶσι, Διὸς δʼ ἐτελείετο βουλή,",
     "——|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×"),
]


@pytest.mark.parametrize("line,pattern", HEXAMETERS)
def test_hexameter_scansion(line: str, pattern: str) -> None:
    sc = scan_hexameter(line)
    assert sc.pattern == pattern
    assert sc.meter == "hexameter"
    assert len(sc.feet) == 6


@pytest.mark.parametrize("line,pattern", HEXAMETERS)
def test_hexameter_structure_invariants(line: str, pattern: str) -> None:
    sc = scan_hexameter(line)
    # Feet 1–5 are dactyls or spondees; the closing foot is — × (two syllables).
    for foot in sc.feet[:5]:
        assert foot.name in {"dactyl", "spondee"}
        assert len(foot.syllables) == len(foot.quantities)
        assert len(foot.quantities) in {2, 3}
    assert sc.feet[5].name == "final"
    assert sc.feet[5].quantities == (HEAVY, ANCEPS)
    # The resolved quantity of every syllable is one its analysis allowed.
    opts = dict(syllable_options(line))
    for syl, q in zip(sc.syllables, sc.quantities):
        if q is ANCEPS:
            continue
        assert q in opts[syl]


def test_pentameter_scansion() -> None:
    # Simonides' Thermopylae epitaph (pentameter of the couplet).
    sc = scan_pentameter("κείμεθα τοῖς κείνων ῥήμασι πειθόμενοι.")
    assert sc.pattern == "—⏑⏑|——|—|—⏑⏑|—⏑⏑|×"
    assert sc.meter == "pentameter"
    # Second hemiepes is two obligatory dactyls then the final longum.
    assert [f.name for f in sc.feet[3:]] == ["dactyl", "dactyl", "longum"]


def test_caesura_detection() -> None:
    # Penthemimeral: word break after the longum of the third foot.
    sc = scan_hexameter("πλάγχθη, ἐπεὶ Τροίης ἱερὸν πτολίεθρον ἔπερσεν")
    assert sc.caesura == "penthemimeral"
    assert sc.syllables[sc.caesura_index].startswith("ἱ")
    # Trochaic (feminine): break after the first short of the third foot.
    sc2 = scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ")
    assert sc2.caesura == "trochaic"


def test_correptio_is_required_not_optional() -> None:
    # Without correptio (μοι staying heavy) Od.1.1 would not scan; the scanner
    # must apply it. The first foot is a clean dactyl with μοι light.
    sc = scan_hexameter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ")
    assert sc.feet[0].quantities == (HEAVY, LIGHT, LIGHT)
    assert sc.syllables[2] == "μοι"
    assert sc.quantities[2] is LIGHT


def test_muta_cum_liquida_is_ambiguous() -> None:
    # A short vowel before a stop+liquid cluster may scan heavy or light.
    opts = dict(syllable_options("πατρός"))
    assert set(opts["πα"]) == {HEAVY, LIGHT}


def test_diaeresis_blocks_diphthong() -> None:
    # ϊ carries a diaeresis: Πηληϊάδεω is not Πηλη + ιάδεω with an ηι diphthong.
    sylls = [s for s, _ in syllable_options("Πηληϊάδεω")]
    assert "λη" in sylls and "ϊ" in sylls


def test_double_consonant_makes_position() -> None:
    # ζ counts as two consonants, closing the preceding syllable (heavy).
    opts = dict(syllable_options("τράπεζα"))
    assert opts["πε"] == [HEAVY]


def test_scan_line_dispatch_and_unknown_meter() -> None:
    sc = scan_line("κείμεθα τοῖς κείνων ῥήμασι πειθόμενοι.", "pentameter")
    assert isinstance(sc, LineScansion)
    assert sc.meter == "pentameter"
    with pytest.raises(ScansionError):
        scan_line("foo", "limerick")


def test_non_metrical_line_raises() -> None:
    # A single prose word is not a hexameter.
    with pytest.raises(ScansionError):
        scan_hexameter("ἄνθρωπος")


def test_synizesis_limitation_is_explicit() -> None:
    # Iliad 1.1 needs synizesis (Πηληϊάδεω → -δεω one syllable), which is not
    # inferred; the scanner declines rather than guessing.
    with pytest.raises(ScansionError):
        scan_hexameter("μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος")


def test_pattern_str_round_trips_glyphs() -> None:
    sc = scan_hexameter("οἰωνοῖσί τε πᾶσι, Διὸς δʼ ἐτελείετο βουλή,")
    assert str(sc) == sc.pattern
    assert sc.pattern.count("|") == 5  # six feet
