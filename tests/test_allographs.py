"""Catalogued sign-variant groups: correctness against the live inventories + honesty.

The module is EXPLORATORY and deliberately narrow: it reports only the variant relationships
the inventory's own labels encode (numbered homophone series; Cypro-Minoan catalogue-letter
suffixes), never palaeographic allography. The tests assert the exact groupings each script's
inventory supports and that compounds/ligatures are kept out of the variant groups.
"""

import pytest

from aegean.analysis.allographs import (
    AllographReport,
    VariantGroup,
    variant_groups,
)
from aegean.core.script import get_script, registered_scripts


# --------------------------------------------------------------------------- #
# Correctness: the exact groupings each live inventory supports
# --------------------------------------------------------------------------- #


def _groups_as_dict(report: AllographReport) -> dict[str, tuple[str, ...]]:
    return {g.base: g.members for g in report.groups}


def test_linear_a_numbered_variant_groups():
    rep = variant_groups("lineara")
    groups = _groups_as_dict(rep)
    # The four numbered homophone series the Linear A inventory records.
    assert groups == {
        "PA": ("PA", "PA3"),
        "PU": ("PU", "PU2"),
        "RA": ("RA", "RA2"),
        "TA": ("TA", "TA2"),
    }
    assert all(g.kind == "homophone-number" for g in rep.groups)
    assert all(g.script_id == "lineara" for g in rep.groups)


def test_linear_a_composites_reported_separately_not_grouped():
    rep = variant_groups("lineara")
    # Ligatures/compounds are carried but never folded into a variant group.
    assert "SI+SE" in rep.composite_signs
    assert "VIR+KA" in rep.composite_signs
    for g in rep.groups:
        assert all("+" not in m for m in g.members)


def test_linear_b_numbered_variant_groups():
    rep = variant_groups("linearb")
    groups = _groups_as_dict(rep)
    assert groups == {
        "A": ("A", "A2", "A3"),
        "PU": ("PU", "PU2"),
        "RA": ("RA", "RA2", "RA3"),
        "RO": ("RO", "RO2"),
        "TA": ("TA", "TA2"),
    }
    # TURO2 has no bare "TURO" base sign, so it forms no group (a 1-member set is dropped).
    assert "TURO" not in groups


def test_cypriot_records_no_variant_structure():
    rep = variant_groups("cypriot")
    assert rep.groups == ()
    assert rep.composite_signs == ()
    assert "no variant groupings" in rep.notes.lower()


def test_cyprominoan_catalogue_suffix_variants():
    rep = variant_groups("cyprominoan")
    groups = _groups_as_dict(rep)
    assert groups == {
        "CM012": ("CM012", "CM012B"),
        "CM075": ("CM075", "CM075B"),
    }
    assert all(g.kind == "catalog-suffix" for g in rep.groups)


# --------------------------------------------------------------------------- #
# Properties that must hold for every script
# --------------------------------------------------------------------------- #


def test_every_group_member_is_a_real_sign():
    for sid in ["lineara", "linearb", "cypriot", "cyprominoan"]:
        inv = get_script(sid).sign_inventory
        labels = {s.label for s in inv}
        rep = variant_groups(sid)
        for g in rep.groups:
            for m in g.members:
                assert m in labels, f"{sid}: {m} not a real sign"


def test_groups_have_at_least_two_members():
    for sid in registered_scripts():
        if sid == "greek":
            continue  # alphabetic script: no Aegean-style numbered variants expected
        rep = variant_groups(sid)
        for g in rep.groups:
            assert len(g.members) >= 2


def test_n_signs_matches_inventory():
    for sid in ["lineara", "linearb", "cypriot", "cyprominoan"]:
        rep = variant_groups(sid)
        assert rep.n_signs == len(get_script(sid).sign_inventory.signs)


def test_group_for_lookup():
    rep = variant_groups("linearb")
    g = rep.group_for("RA2")
    assert g is not None
    assert g.base == "RA"
    assert "RA3" in g.members
    assert rep.group_for("NOSUCH") is None


def test_groups_deterministically_ordered_by_base():
    rep = variant_groups("linearb")
    bases = [g.base for g in rep.groups]
    assert bases == sorted(bases)


def test_notes_state_the_palaeography_caveat():
    for sid in ["lineara", "linearb", "cyprominoan"]:
        rep = variant_groups(sid)
        # The honesty line must be present whenever groupings exist.
        assert "palaeographic allography" in rep.notes.lower()


# --------------------------------------------------------------------------- #
# Adversarial / bad input
# --------------------------------------------------------------------------- #


def test_unknown_script_raises_keyerror():
    with pytest.raises(KeyError):
        variant_groups("nonesuch")


def test_report_is_frozen_value_object():
    rep = variant_groups("lineara")
    assert isinstance(rep, AllographReport)
    assert isinstance(rep.groups[0], VariantGroup)
    with pytest.raises((AttributeError, TypeError)):
        rep.groups[0].base = "X"  # type: ignore[misc]
