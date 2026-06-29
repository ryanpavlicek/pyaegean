"""Greek metrical scansion (dactylic hexameter + elegiac pentameter)."""

from __future__ import annotations

import pytest

from aegean.greek import (
    AEOLIC_LINES,
    LineScansion,
    ScansionError,
    scan_aeolic,
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


# Lines whose correct scansion turns on a vowel quantity the spelling cannot give
# (the third foot of Il. 1.3 needs ψῡ- long) or on a word-final consonant before a
# vowel-initial word. Patterns are from standard editions, not read off the scanner.
def test_iliad_1_3_scans_to_canonical_pattern() -> None:
    # Il. 1.3 πολλὰς δ' ἰφθίμους ψυχὰς Ἄϊδι προΐαψεν is — — | — — | — — | — ⏑⏑ |
    # — ⏑⏑ | — ×: feet 1–3 spondees, 4–5 dactyls. ψυχάς has a long υ by nature
    # (ψῡχή) and the long acc.-pl. ending -ᾱς, so the third foot is a spondee, not
    # the greedy dactyl μους–ψυ–χας the scanner used to return.
    sc = scan_hexameter("πολλὰς δ' ἰφθίμους ψυχὰς Ἄϊδι προΐαψεν")
    assert sc.meter == "hexameter"
    assert sc.pattern == "——|——|——|—⏑⏑|—⏑⏑|—×"
    assert not sc.ambiguous          # the scansion is now unique, not a coin-flip
    # ψυ and the closing χὰς are both heavy here.
    assert dict(zip(sc.syllables, sc.quantities))["ψυ"] is HEAVY


def test_odyssey_1_7_scans_to_canonical_pattern() -> None:
    # Od. 1.7 αὐτῶν γὰρ σφετέρῃσιν ἀτασθαλίῃσιν ὄλοντο is a spondee then four
    # dactyls: — — | — ⏑⏑ | — ⏑⏑ | — ⏑⏑ | — ⏑⏑ | — ×. Both word-final -σιν before a
    # vowel are LIGHT (the ν runs over the boundary, no position made).
    sc = scan_hexameter("αὐτῶν γὰρ σφετέρῃσιν ἀτασθαλίῃσιν ὄλοντο,")
    assert sc.meter == "hexameter"
    assert sc.pattern == "——|—⏑⏑|—⏑⏑|—⏑⏑|—⏑⏑|—×"
    assert not sc.ambiguous


def test_long_by_nature_entry_is_required(monkeypatch) -> None:
    # Without its lexicon entry, Il. 1.3 reverts to the wrong, ambiguous reading —
    # proving ψυχάς's long υ is load-bearing, not redundant with the rules.
    from aegean.greek import meter

    monkeypatch.setattr(meter, "_LONG_BY_NATURE", {})
    sc = scan_hexameter("πολλὰς δ' ἰφθίμους ψυχὰς Ἄϊδι προΐαψεν")
    assert sc.pattern != "——|——|——|—⏑⏑|—⏑⏑|—×"
    assert sc.ambiguous          # the line is genuinely ambiguous without the entry


def test_long_by_nature_entries_make_their_vowels_long() -> None:
    # Every entry must actually force a dichronon long where the rules leave it
    # common — a dead entry (vowel already determined, or never present) is rejected,
    # like a syllabify exception the rules already get right.
    from aegean.greek.meter import _LONG_BY_NATURE, _quantity_is_forced_long

    for word, vowels in _LONG_BY_NATURE.items():
        for v in vowels:
            assert _quantity_is_forced_long(word, v), f"{word!r}/{v!r} not forced long"


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


def test_synizesis_lexicon_lets_iliad_1_1_scan() -> None:
    # Iliad 1.1 needs synizesis (Πηληϊάδεω → the -εω is one syllable). With the
    # word in the synizesis lexicon the line now scans as a clean hexameter.
    sc = scan_hexameter("μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος")
    assert sc.meter == "hexameter"
    assert sc.pattern == "—⏑⏑|—⏑⏑|——|—⏑⏑|—⏑⏑|—×"


def test_synizesis_entry_is_required(monkeypatch) -> None:
    # Without its lexicon entry, Iliad 1.1 must NOT scan — proving the entry is
    # load-bearing (the synizesis is genuinely required by the line, not noise).
    from aegean.greek import meter

    pruned = {k: v for k, v in meter._SYNIZESIS.items() if k != "πηληιαδεω"}
    monkeypatch.setattr(meter, "_SYNIZESIS", pruned)
    with pytest.raises(ScansionError):
        scan_hexameter("μῆνιν ἄειδε θεὰ Πηληϊάδεω Ἀχιλῆος")


def test_synizesis_entries_coalesce_vowels() -> None:
    # Every lexicon entry must actually merge its two or three written vowels into one
    # nucleus (i.e. change the analysis) — a dead entry is rejected, like a syllabify
    # exception that the rules already get right. Accent-insensitive: the coalesced nucleus
    # keeps its accent (e.g. θεούς -> εού), so compare on the plain vowels.
    from aegean.greek.meter import _SYNIZESIS, _items, _strip_combining

    for word, vowels in _SYNIZESIS.items():
        merged = [it for it in _items(word) if it.is_vowel and len(it.text) >= 2]
        assert any(
            vowels in _strip_combining(it.text).lower() for it in merged
        ), f"{word!r} did not coalesce"


def test_three_vowel_synizesis() -> None:
    # θεούς takes three-vowel synizesis (εου -> one syllable); without the lexicon entry
    # the natural ου diphthong would still leave it two syllables (θε-ούς).
    from aegean.greek.meter import _analyze

    assert len(_analyze("θεούς")) == 1


def test_pattern_str_round_trips_glyphs() -> None:
    sc = scan_hexameter("οἰωνοῖσί τε πᾶσι, Διὸς δʼ ἐτελείετο βουλή,")
    assert str(sc) == sc.pattern
    assert sc.pattern.count("|") == 5  # six feet


# --- iambic trimeter ---------------------------------------------------------

# Canonical tragic openings — all are clean iambic trimeters (no resolution),
# so the realised pattern is the basic ×—⏑—|×—⏑—|×—⏑× three times over.
TRIMETERS = [
    "Εἴθ' ὤφελ' Ἀργοῦς μὴ διαπτάσθαι σκάφος",       # Eur. Medea 1
    "ὦ κοινὸν αὐτάδελφον Ἰσμήνης κάρα",            # Soph. Antigone 1
    "ἥκω Διὸς παῖς τήνδε Θηβαίων χθόνα",           # Eur. Bacchae 1
    "ὦ τέκνα, Κάδμου τοῦ πάλαι νέα τροφή",          # Soph. OT 1
    "πολλὴ μὲν ἐν βροτοῖσι κοὐκ ἀνώνυμος",          # Eur. Hippolytus 1
]


@pytest.mark.parametrize("line", TRIMETERS)
def test_trimeter_scansion(line: str) -> None:
    from aegean.greek import scan_trimeter

    sc = scan_trimeter(line)
    assert sc.meter == "trimeter"
    assert sc.pattern == "×—⏑—|×—⏑—|×—⏑×"   # three metra, basic shape
    assert len(sc.feet) == 3 and all(f.name == "metron" for f in sc.feet)
    # every realised quantity is one the syllable's analysis allowed
    opts = dict(syllable_options(line))
    for syl, q in zip(sc.syllables, sc.quantities):
        if q is ANCEPS:
            continue
        assert q in opts[syl]


def test_trimeter_caesura() -> None:
    from aegean.greek import scan_trimeter

    sc = scan_trimeter("ὦ κοινὸν αὐτάδελφον Ἰσμήνης κάρα")  # Antigone 1
    assert sc.caesura in {"penthemimeral", "hephthemimeral"}
    assert sc.syllables[sc.caesura_index] is not None


def test_trimeter_resolution() -> None:
    # A resolved long element (— → ⏑⏑) makes a 13-syllable line. Bacchae 2
    # resolves in the first metron (Διό- = ⏑⏑); the scanner must allow it.
    from aegean.greek import scan_trimeter

    sc = scan_trimeter("Διόνυσον, ὃν τίκτει ποθ' ἡ Κάδμου κόρη")
    assert sc.meter == "trimeter"
    assert len(sc.syllables) == 13                  # one element resolved
    assert sc.pattern == "×⏑⏑⏑—|×—⏑—|×—⏑×"


def test_trimeter_rejects_a_hexameter() -> None:
    from aegean.greek import scan_trimeter

    with pytest.raises(ScansionError):
        scan_trimeter("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ")


def test_scan_line_dispatches_trimeter() -> None:
    sc = scan_line("ἥκω Διὸς παῖς τήνδε Θηβαίων χθόνα", "trimeter")
    assert sc.meter == "trimeter" and len(sc.feet) == 3


# --- aeolic lyric lines ------------------------------------------------------

# Real lines, scanned against the standard aeolic templates (— ⏑ × notation).
def test_sapphic_hendecasyllable() -> None:
    sc = scan_aeolic("φαίνεταί μοι κῆνος ἴσος θέοισιν", "sapphic_hendecasyllable")  # Sappho 31.1
    assert sc.meter == "sapphic_hendecasyllable"
    assert sc.pattern == "—⏑—×—⏑⏑—⏑—×"
    assert len(sc.syllables) == 11


def test_alcaic_hendecasyllable() -> None:
    sc = scan_aeolic("ἀσυννέτημμι τὼν ἀνέμων στάσιν", "alcaic_hendecasyllable")  # Alcaeus 326.1
    assert sc.pattern == "×—⏑—×—⏑⏑—⏑×"


def test_glyconic() -> None:
    sc = scan_aeolic("Ἀφροδίτα δολόπλοκε", "glyconic")
    assert sc.pattern == "××—⏑⏑—⏑×" and len(sc.syllables) == 8


def test_scan_line_dispatches_aeolic() -> None:
    sc = scan_line("φαίνεταί μοι κῆνος ἴσος θέοισιν", "sapphic_hendecasyllable")
    assert sc.meter == "sapphic_hendecasyllable"


def test_aeolic_rejects_wrong_length() -> None:
    # a hexameter line is far too long for any aeolic colon
    with pytest.raises(ScansionError):
        scan_aeolic("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ", "glyconic")


def test_aeolic_unknown_line_type() -> None:
    with pytest.raises(ScansionError, match="unknown aeolic line"):
        scan_aeolic("φαίνεταί μοι κῆνος ἴσος θέοισιν", "not_a_metre")


def test_aeolic_lines_constant() -> None:
    assert "sapphic_hendecasyllable" in AEOLIC_LINES and "glyconic" in AEOLIC_LINES
    # every advertised line type is dispatchable through scan_line
    for name in AEOLIC_LINES:
        assert callable(__import__("aegean.greek.meter", fromlist=["_SCANNERS"])._SCANNERS[name])
